"""One coordinated router poll for all entities."""
from datetime import timedelta
import logging
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import (CONF_INTERVAL, CONF_NAMES, CONF_PHONE_DETECTION, CONF_DEPARTURE_DELAY, DEFAULT_DEPARTURE_DELAY,
                    DEFAULT_NAMES, DEFAULT_INTERVAL, DEFAULT_PORT, DOMAIN, EVENT_PHONE_ARRIVED)
from .models import Snapshot
from .parser import ParseError
from .router import AuthenticationError, RouterClient, RouterError
from .scanner import PhoneScanner
from .presence import PresenceTracker

_LOGGER = logging.getLogger(__name__)


class PhoneCoordinator(DataUpdateCoordinator[Snapshot]):
    """Keep successful readings separate from connectivity failures."""
    def __init__(self, hass, entry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(seconds=entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL)))
        self.entry_id = entry.entry_id
        self.tracker = PresenceTracker(entry.options.get(CONF_DEPARTURE_DELAY, DEFAULT_DEPARTURE_DELAY))
        self.router = RouterClient(entry.data[CONF_HOST], entry.data[CONF_USERNAME],
                                   entry.data[CONF_PASSWORD], entry.data.get(CONF_PORT, DEFAULT_PORT))
        enabled = entry.options.get(CONF_PHONE_DETECTION, True)
        self.scanner = PhoneScanner(self.router, name_keywords=entry.options.get(CONF_NAMES) or DEFAULT_NAMES,
                                    enabled=enabled)

    async def _async_update_data(self) -> Snapshot:
        try:
            snapshot = self.tracker.update(await self.scanner.async_scan())
            for item in snapshot.arrivals:
                self.hass.bus.async_fire(EVENT_PHONE_ARRIVED, {
                    "entry_id": self.entry_id, "name": item.client.hostname,
                    "mac": item.client.mac, "ip": item.client.ip,
                    "matched_keywords": list(item.matched_keywords),
                })
            return snapshot
        except AuthenticationError as err:
            self.tracker.pause()
            raise ConfigEntryAuthFailed("Router rejected credentials") from err
        except ParseError as err:
            self.tracker.pause()
            raise UpdateFailed("Wi-Fi association output is unsupported") from err
        except RouterError as err:
            self.tracker.pause()
            raise UpdateFailed("Cannot read router association or device names") from err
