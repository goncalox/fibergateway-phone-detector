"""Aggregate name-based phone presence for automations."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from .entity import PhoneEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities([PhoneConnected(entry)])


class PhoneConnected(PhoneEntity, BinarySensorEntity):
    """At least one associated station matches a configured keyword."""
    _attr_name = "Phone connected"
    _attr_icon = "mdi:cellphone-wireless"
    _attr_device_class = BinarySensorDeviceClass.PRESENCE

    def __init__(self, entry) -> None:
        super().__init__(entry, "phone_connected")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.phone_connected

    @property
    def extra_state_attributes(self):
        snapshot = self.coordinator.data
        return {"phone_count": len(snapshot.phones),
                "matched_names": sorted({item.client.hostname for item in snapshot.phones}),
                "name_keywords": list(self.coordinator.scanner.keywords),
                "detection_method": "hostname",
                "presence_phone_count": len(snapshot.effective_phones),
                "pending_departure_names": sorted({item.client.hostname for item in snapshot.pending_departures}),
                "departure_delay": self.coordinator.tracker.departure_delay}
