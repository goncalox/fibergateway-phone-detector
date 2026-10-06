"""A selectable event entity for arrivals while presence is already on."""
from homeassistant.components.event import EventEntity
from homeassistant.core import callback
from .entity import PhoneEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([PhoneArrival(entry)])


class PhoneArrival(PhoneEntity, EventEntity):
    _attr_name = "Phone arrival"
    _attr_icon = "mdi:cellphone-arrow-down"
    _attr_event_types = ["phone_arrived"]

    def __init__(self, entry):
        super().__init__(entry, "phone_arrival")
        self._last_sequence = 0

    @callback
    def _handle_coordinator_update(self):
        snapshot = self.coordinator.data
        if self.coordinator.last_update_success and snapshot.sequence != self._last_sequence:
            self._last_sequence = snapshot.sequence
            if snapshot.arrivals:
                self._trigger_event("phone_arrived", {
                    "names": [item.client.hostname for item in snapshot.arrivals],
                    "count": len(snapshot.arrivals),
                    "devices": [{"name": item.client.hostname, "mac": item.client.mac,
                                 "matched_keywords": list(item.matched_keywords)} for item in snapshot.arrivals],
                })
        self.async_write_ha_state()
