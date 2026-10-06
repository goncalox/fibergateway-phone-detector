"""Provisional table parsers; unknown formats must never report absence."""

import ipaddress
import re

from .models import Client

MAC = re.compile(r"(?<![0-9a-f])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f])", re.I)
ERROR = re.compile(
    r"unknown command|invalid command|command not found|permission denied|"
    r"access denied|not authorized|unsupported command|syntax error|^\s*usage:",
    re.I | re.M,
)
MAC_HEADERS = {"mac", "macaddress", "clientmac", "stationmac", "stationaddress"}
IP_HEADERS = {"ip", "ipaddress", "ipv4address", "clientip"}
NAME_HEADERS = {"hostname", "clientname", "devicename", "host"}
ASSOCIATION_ROW = re.compile(
    r"(?P<mac>(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2})\s*\|\s*"
    r"(?P<connected>yes|no)\s*(?:\||$)", re.I,
)
CONNECTED_HEADERS = {"associated", "association", "connected", "authenticated", "auth", "authentication",
                     "isassociated", "isconnected", "associationstatus"}


class ParseError(Exception):
    """A command failed or the response format is not supported."""


def normalize_mac(value: str) -> str:
    """Normalize colon, hyphen, compact or Cisco MAC notation."""
    compact = re.sub(r"[:.\-]", "", value.strip())
    if not re.fullmatch(r"[0-9a-fA-F]{12}", compact):
        raise ValueError("Invalid MAC address")
    return ":".join(compact[i:i + 2].lower() for i in range(0, 12, 2))


def parse_mac_list(value: str) -> frozenset[str]:
    """Accept addresses separated by commas, spaces or newlines."""
    return frozenset(normalize_mac(item) for item in re.split(r"[,\s]+", value.strip()) if item)


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _cells(line: str) -> list[str]:
    return [item.strip() for item in line.strip().strip("|").split("|")]


def _clean(text: str) -> str:
    text = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text).replace("\r", "")
    if ERROR.search(text):
        raise ParseError("Router rejected the read command")
    return text


def _table_rows(text: str, require_ip: bool) -> tuple[bool, list[Client]]:
    """Read pipe tables with named columns, rejecting malformed data rows."""
    columns: list[str] | None = None
    recognized = False
    clients: list[Client] = []
    for line in text.splitlines():
        if "|" not in line:
            continue
        cells = _cells(line)
        keys = [_key(cell) for cell in cells]
        if any(key in MAC_HEADERS for key in keys) and (
            not require_ip or any(key in IP_HEADERS for key in keys)
        ):
            columns = keys
            recognized = True
            continue
        if not columns or not any(cells):
            continue
        if len(cells) != len(columns):
            raise ParseError("Unexpected router table width")
        row = dict(zip(columns, cells))
        raw_mac = next(row[key] for key in columns if key in MAC_HEADERS)
        try:
            mac = normalize_mac(raw_mac)
        except ValueError as err:
            raise ParseError("Invalid station MAC in router table") from err
        ip = None
        if require_ip:
            raw_ip = next(row[key] for key in columns if key in IP_HEADERS)
            try:
                ip = str(ipaddress.IPv4Address(raw_ip))
            except ipaddress.AddressValueError as err:
                raise ParseError("Invalid DHCP address in router table") from err
        hostname = next((row[key] for key in columns if key in NAME_HEADERS), None)
        if hostname in {"", "-", "*", "N/A"}:
            hostname = None
        clients.append(Client(mac, ip, hostname))
    return recognized, clients


def parse_stations(text: str) -> frozenset[str]:
    """Match the reference's MAC/Yes association protocol for one Wi-Fi band.

    The reference selects MACs followed by a Yes column, excluding No rows.
    Named synthetic tables remain supported, with explicit connection filtering.
    """
    text = _clean(text)
    association_rows = list(ASSOCIATION_ROW.finditer(text))
    if association_rows:
        # Do not silently discard a changed row format beside recognized rows.
        for line in text.splitlines():
            if MAC.search(line) and not ASSOCIATION_ROW.search(line):
                raise ParseError("Unrecognized association row beside known rows")
        return frozenset(
            normalize_mac(row.group("mac")) for row in association_rows
            if row.group("connected").lower() == "yes"
        )
    # A status column may appear elsewhere in a named table.
    columns = None
    present = set()
    for line in text.splitlines():
        if "|" not in line:
            continue
        cells = _cells(line)
        keys = [_key(cell) for cell in cells]
        if any(key in MAC_HEADERS for key in keys) and any(key in CONNECTED_HEADERS for key in keys):
            columns = keys
            continue
        if columns is None or not any(cells):
            continue
        if len(cells) != len(columns):
            raise ParseError("Unexpected association table width")
        row = dict(zip(columns, cells))
        try:
            mac = normalize_mac(next(row[key] for key in columns if key in MAC_HEADERS))
        except ValueError as err:
            raise ParseError("Invalid association MAC") from err
        connected = next(row[key].lower() for key in columns if key in CONNECTED_HEADERS)
        if connected not in {"yes", "no"}:
            raise ParseError("Unrecognized association state")
        if connected == "yes":
            present.add(mac)
    if columns is not None:
        return frozenset(present)
    if re.search(r"\bno (?:connected )?(?:stations|clients)\b|"
                 r"\b(?:station|client)s?\s*(?:count|number)?\s*[:=]\s*0\b", text, re.I):
        if not MAC.search(text):
            return frozenset()
    raise ParseError("Unrecognized Wi-Fi association response; capture router output")


def parse_leases(text: str) -> dict[str, Client]:
    """Read a named DHCP table; leases alone never establish presence."""
    text = _clean(text)
    recognized, clients = _table_rows(text, require_ip=True)
    if recognized:
        if not clients and MAC.search(text):
            raise ParseError("Unrecognized DHCP rows")
        result = {}
        for client in clients:
            if client.mac in result and result[client.mac] != client:
                raise ParseError("Conflicting DHCP entries for one MAC")
            result[client.mac] = client
        return result
    if re.search(r"\bno (?:dhcp )?leases\b|\bleases?\s*(?:count)?\s*[:=]\s*0\b", text, re.I):
        if not MAC.search(text):
            return {}
    raise ParseError("Unrecognized DHCP response; capture router output")


def parse_station_metadata(text: str, stations: frozenset[str]) -> dict[str, Client]:
    """Use optional named IP/hostname columns without assuming they exist."""
    for require_ip in (True, False):
        try:
            recognized, clients = _table_rows(_clean(text), require_ip=require_ip)
        except ParseError:
            continue
        if recognized:
            return {client.mac: client for client in clients if client.mac in stations}
    return {}


def correlate(stations: frozenset[str], leases: dict[str, Client],
              metadata: dict[str, Client] | None = None) -> tuple[Client, ...]:
    """Include associated stations even if DHCP has no lease for them."""
    metadata = metadata or {}
    result = []
    for mac in sorted(stations):
        station = metadata.get(mac, Client(mac))
        lease = leases.get(mac, Client(mac))
        result.append(Client(mac, lease.ip or station.ip, lease.hostname or station.hostname))
    return tuple(result)
