"""Validated command builders and parsers for FiberGateway operations."""
from dataclasses import asdict, dataclass
import re

from .parser import ParseError, normalize_mac

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
TIME_RESTRICTIONS = "/parental-control/time-restriction/"


def rule_name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
        raise ValueError("Rule names must use 1–64 letters, numbers, underscores or hyphens")
    return value


def clock_time(value):
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d(?::00)?", value):
        raise ValueError("Use a time with minute precision, for example 05:00")
    return value[:5]


def weekdays(values):
    if not isinstance(values, (list, tuple)) or not values or any(day not in DAYS for day in values):
        raise ValueError("Select at least one weekday")
    return tuple(day for day in DAYS if day in values)


def device_mac(value):
    mac = normalize_mac(value)
    if int(mac[:2], 16) & 1 or mac == "00:00:00:00:00:00":
        raise ValueError("Specify one device's unicast MAC address")
    return mac


def validate_command(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError("Enter one router CLI command")
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Router commands must be a single line without control characters")
    return value.strip()


@dataclass(frozen=True)
class TimeRestriction:
    name: str
    mac: str
    days: tuple[str, ...]
    start_time: str
    end_time: str

    def as_dict(self):
        return {**asdict(self), "days": list(self.days)}


def restriction(name, mac, days, start_time, end_time):
    start, end = clock_time(start_time), clock_time(end_time)
    if start == end:
        raise ValueError("Start and end times must differ")
    return TimeRestriction(rule_name(name), device_mac(mac), weekdays(days), start, end)


def create_restriction_command(rule):
    return (TIME_RESTRICTIONS + f"create --MACAddress={rule.mac} --days-week={','.join(rule.days)} "
            f"--end-time={rule.end_time} --name={rule.name} --start-time={rule.start_time}")


def remove_restriction_command(name):
    return TIME_RESTRICTIONS + f"remove --rmv-name={rule_name(name)}"


def parse_time_restrictions(text):
    """Read the table observed on GR141DG; unknown output never means no rules."""
    columns = None
    results = []
    headers = ("name", "macaddress", "daysofweek", "starttime", "endtime")
    for line in text.splitlines():
        if "|" not in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        keys = [re.sub(r"[^a-z]", "", cell.lower()) for cell in cells]
        if tuple(keys) == headers:
            columns = keys
            continue
        if columns is None:
            continue
        if len(cells) != 5:
            raise ParseError("Unsupported time restriction row")
        name, mac, days, start, end = cells
        try:
            # Existing router rules may have spaces in their names; retain them when reading.
            results.append(TimeRestriction(name, normalize_mac(mac), weekdays(days.split(",")),
                                           clock_time(start), clock_time(end)))
        except ValueError as error:
            raise ParseError("Invalid time restriction row") from error
    if columns is None and text.strip() not in ("Nothing found. Try again.", "No time restrictions"):
        raise ParseError("Unsupported time restriction output")
    if len({item.name for item in results}) != len(results):
        raise ParseError("Duplicate time restriction names")
    return tuple(results)
