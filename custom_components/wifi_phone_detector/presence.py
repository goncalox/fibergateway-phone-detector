"""Arrival tracking and departure grace periods, independent of HA."""
from dataclasses import replace
from time import monotonic
from .const import DEFAULT_DEPARTURE_DELAY
from .models import Snapshot


class PresenceTracker:
    """Track matching MACs; first readings and outage recovery are baselines."""
    def __init__(self, departure_delay: int = DEFAULT_DEPARTURE_DELAY, *, clock=monotonic):
        if not 0 <= departure_delay <= 1800:
            raise ValueError("Departure delay must be between 0 and 1800 seconds")
        self.departure_delay = departure_delay
        self.clock = clock
        self._present = {}
        self._missing_since = {}
        self._baseline = False
        self._sequence = 0

    def pause(self):
        """Failed reads cannot count toward a confirmed departure or arrival."""
        self._baseline = False
        self._missing_since.clear()

    def update(self, snapshot: Snapshot) -> Snapshot:
        now = self.clock()
        # A return after the grace period is a fresh arrival even when this
        # is the first successful poll since the timer elapsed.
        for mac, since in tuple(self._missing_since.items()):
            if now - since >= self.departure_delay:
                self._present.pop(mac, None)
                del self._missing_since[mac]
        current = {item.client.mac: item for item in snapshot.phones}
        arrivals = tuple(item for mac, item in current.items()
                         if self._baseline and mac not in self._present)
        for mac, item in current.items():
            self._present[mac] = item
            self._missing_since.pop(mac, None)
        for mac in tuple(self._present):
            if mac not in current:
                since = self._missing_since.setdefault(mac, now)
                if now - since >= self.departure_delay:
                    del self._present[mac]
                    del self._missing_since[mac]
        self._baseline = True
        self._sequence += 1
        return replace(snapshot, presence_phones=tuple(self._present[mac] for mac in sorted(self._present)),
                       arrivals=arrivals, sequence=self._sequence)
