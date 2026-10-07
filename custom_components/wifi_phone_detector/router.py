"""Async FiberGateway access using the user-tested fgw_router protocol.

Query both radio indexes and filter the association marker; DHCP is optional.
Reference: https://github.com/queimadus/fgw_router
"""

import asyncio
from contextlib import asynccontextmanager
import re

import telnetlib3

from .commands import (TIME_RESTRICTIONS, create_restriction_command, parse_time_restrictions,
                       remove_restriction_command, validate_command)
from .const import LEASES_COMMAND, STATIONS_COMMANDS
from .models import Client
from .parser import ParseError, correlate, parse_leases, parse_station_metadata, parse_stations

LOGIN = re.compile(r"(?:login|username)\s*:\s*$", re.I)
PASSWORD = re.compile(r"password\s*:\s*$", re.I)
PROMPT = re.compile(r"(?:^|\n)\s*/?cli(?:/[^\r\n>]*)?>\s*$", re.I)
DENIED = re.compile(r"login incorrect|authentication failed|invalid password|"
                    r"incorrect password|login failed|access denied", re.I)
MAX_RESPONSE = 262144


class RouterError(Exception):
    """The router connection or CLI session failed."""


class CommandError(RouterError):
    """The router rejected a command or its saved result could not be verified."""


class AuthenticationError(RouterError):
    """The router rejected the supplied credentials."""


class RouterClient:
    """Open one session per poll; never log credentials or raw output."""

    def __init__(self, host: str, username: str, password: str,
                 port: int = 23, timeout: float = 10) -> None:
        if any(char in username + password for char in "\r\n\x00"):
            raise ValueError("Credentials must not contain control characters")
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self.dhcp_available = False
        self._lock = asyncio.Lock()

    async def _read(self, reader, expected: re.Pattern, *, authenticated: bool = False) -> str:
        buffer = ""
        async with asyncio.timeout(self.timeout):
            while True:
                chunk = await reader.read(1024)
                if not chunk:
                    raise RouterError("Router closed the session")
                buffer += chunk
                if len(buffer) > MAX_RESPONSE:
                    raise RouterError("Router response is too large")
                clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", buffer).replace("\r", "")
                if DENIED.search(clean) or (authenticated and LOGIN.search(clean)):
                    raise AuthenticationError("Router rejected credentials")
                if expected.search(clean):
                    return clean

    async def _write(self, writer, value: str) -> None:
        """Bound writes as well as reads, including backpressure."""
        async with asyncio.timeout(self.timeout):
            writer.write(value + "\r\n")
            await writer.drain()

    @asynccontextmanager
    async def _session(self):
        """Serialize polls and control actions and close on every exit path."""
        async with self._lock:
            writer = None
            try:
                async with asyncio.timeout(self.timeout):
                    reader, writer = await telnetlib3.open_connection(
                        host=self.host, port=self.port, encoding="utf8",
                        connect_minwait=0, connect_maxwait=1,
                    )
                await self._read(reader, LOGIN)
                await self._write(writer, self.username)
                await self._read(reader, PASSWORD)
                await self._write(writer, self.password)
                await self._read(reader, PROMPT, authenticated=True)
                yield reader, writer
            except (OSError, TimeoutError, UnicodeError) as err:
                raise RouterError("Cannot communicate with router; a write may have applied if its reply was lost") from err
            finally:
                if writer is not None:
                    writer.close()

    async def _command(self, reader, writer, command):
        await self._write(writer, validate_command(command))
        response = await self._read(reader, PROMPT, authenticated=True)
        if re.search(r"ERR::|unknown command|invalid command|invalid (?:parameter|argument)|permission denied", response, re.I):
            raise CommandError("Router rejected the command or its arguments")
        if re.search(r"(?m)^\s*Usage:", response) and not command.endswith(("?", "help")):
            raise CommandError("Router returned usage instead of executing the command")
        lines = response.strip().splitlines()
        if lines and lines[0].strip() == command:
            lines.pop(0)
        if lines and PROMPT.search(lines[-1]):
            lines.pop()
        return "\n".join(lines).strip()

    async def async_execute(self, command):
        """Execute one explicitly requested CLI command; never retry a write."""
        command = validate_command(command)
        async with self._session() as (reader, writer):
            output = await self._command(reader, writer, command)
            return output.replace(self.password, "[redacted]") if self.password else output

    async def async_get_time_restrictions(self):
        async with self._session() as (reader, writer):
            return parse_time_restrictions(await self._command(reader, writer, TIME_RESTRICTIONS + "show"))

    async def async_create_time_restriction(self, rule):
        async with self._session() as (reader, writer):
            before = parse_time_restrictions(await self._command(reader, writer, TIME_RESTRICTIONS + "show"))
            existing = next((item for item in before if item.name == rule.name), None)
            if existing is not None:
                if existing == rule:
                    return {"created": False, "rule": rule.as_dict()}
                raise CommandError("Rule name already exists with different settings; remove it before changing it")
            await self._command(reader, writer, create_restriction_command(rule))
            after = parse_time_restrictions(await self._command(reader, writer, TIME_RESTRICTIONS + "show"))
            if rule not in after:
                raise CommandError("Write sent but saved rule did not match; inspect the router's restriction list")
            return {"created": True, "rule": rule.as_dict()}

    async def async_remove_time_restriction(self, name):
        command = remove_restriction_command(name)
        async with self._session() as (reader, writer):
            before = parse_time_restrictions(await self._command(reader, writer, TIME_RESTRICTIONS + "show"))
            if not any(item.name == name for item in before):
                return {"removed": False, "name": name}
            await self._command(reader, writer, command)
            after = parse_time_restrictions(await self._command(reader, writer, TIME_RESTRICTIONS + "show"))
            if any(item.name == name for item in after):
                raise CommandError("Remove sent but rule remains; inspect the router's restriction list")
            return {"removed": True, "name": name}

    async def async_fetch(self) -> tuple[Client, ...]:
        """Fetch both radios and DHCP metadata in one authenticated session."""
        async with self._session() as (reader, writer):
            stations = set()
            metadata = {}
            for command in STATIONS_COMMANDS:
                await self._write(writer, command)
                response = await self._read(reader, PROMPT, authenticated=True)
                band_stations = parse_stations(response)
                stations.update(band_stations)
                metadata.update(parse_station_metadata(response, band_stations))
            leases = {}
            self.dhcp_available = False
            try:
                await self._write(writer, LEASES_COMMAND)
                response = await self._read(reader, PROMPT, authenticated=True)
                leases = parse_leases(response)
                self.dhcp_available = True
            except AuthenticationError:
                raise
            except (ParseError, RouterError, OSError, TimeoutError, UnicodeError):
                pass
            return correlate(frozenset(stations), leases, metadata)
