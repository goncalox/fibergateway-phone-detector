"""Plain models shared by Home Assistant and the standalone tester."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Client:
    """A currently associated Wi-Fi station with optional DHCP metadata."""
    mac: str
    ip: str | None = None
    hostname: str | None = None


@dataclass(frozen=True)
class Detection:
    """Configured keywords found in a hostname."""
    client: Client
    matched_keywords: tuple[str, ...]


@dataclass(frozen=True)
class Snapshot:
    """One successful router poll with names available for matching."""
    clients: tuple[Client, ...]
    detections: tuple[Detection, ...]
    presence_phones: tuple[Detection, ...] | None = None
    arrivals: tuple[Detection, ...] = ()
    sequence: int = 0

    @property
    def phones(self) -> tuple[Detection, ...]:
        return tuple(item for item in self.detections if item.matched_keywords)

    @property
    def unnamed(self) -> tuple[Client, ...]:
        return tuple(client for client in self.clients if not client.hostname)

    @property
    def effective_phones(self) -> tuple[Detection, ...]:
        """Include devices awaiting confirmation of departure."""
        return self.phones if self.presence_phones is None else self.presence_phones

    @property
    def pending_departures(self) -> tuple[Detection, ...]:
        current = {item.client.mac for item in self.phones}
        return tuple(item for item in self.effective_phones if item.client.mac not in current)

    @property
    def phone_connected(self) -> bool:
        return bool(self.effective_phones)
