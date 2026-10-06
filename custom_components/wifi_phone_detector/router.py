"""Async FiberGateway access using the user-tested fgw_router protocol.

Query both radio indexes and filter the association marker; DHCP is optional.
Reference: https://github.com/queimadus/fgw_router
"""

import asyncio
import re

import telnetlib3

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

    async def async_fetch(self) -> tuple[Client, ...]:
        """Fetch association data and lease metadata, closing even on cancellation."""
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
                # Association data is already complete; optional enrichment must
                # not prevent known phones from being tracked.
                pass
            return correlate(frozenset(stations), leases, metadata)
        except (OSError, TimeoutError, UnicodeError) as err:
            raise RouterError("Unable to read router; check reachability and Telnet access") from err
        finally:
            if writer is not None:
                writer.close()
