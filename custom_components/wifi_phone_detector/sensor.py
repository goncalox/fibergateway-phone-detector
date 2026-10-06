"""Current device inventory and diagnostic counts."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory

from .entity import PhoneEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    async_add_entities([DeviceList(entry), CountSensor(entry, "wifi_clients", "Wi-Fi clients"),
                        CountSensor(entry, "phone_count", "Detected phones"),
                        CountSensor(entry, "unnamed_clients", "Wi-Fi clients without a name")])


class CountSensor(PhoneEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:wifi"

    def __init__(self, entry, key: str, name: str) -> None:
        super().__init__(entry, key)
        self.key = key
        self._attr_name = name

    @property
    def native_value(self) -> int:
        snapshot = self.coordinator.data
        if self.key == "wifi_clients":
            return len(snapshot.clients)
        if self.key == "unnamed_clients":
            return len(snapshot.unnamed)
        return len(snapshot.phones)


class DeviceList(PhoneEntity, SensorEntity):
    """An inventory sensor: count as state, current devices as attributes."""
    _attr_name = "Connected devices"
    _attr_icon = "mdi:format-list-bulleted"
    _unrecorded_attributes = frozenset({"devices", "device_names", "matched_names"})

    def __init__(self, entry):
        super().__init__(entry, "connected_devices")

    @property
    def native_value(self):
        return len(self.coordinator.data.clients)

    @property
    def extra_state_attributes(self):
        snapshot = self.coordinator.data
        return {
            "device_names": sorted(client.hostname or "Unnamed device" for client in snapshot.clients),
            "matched_names": sorted({item.client.hostname for item in snapshot.phones}),
            "devices": [{"name": item.client.hostname or "Unnamed device", "mac": item.client.mac,
                         "ip": item.client.ip, "is_phone": bool(item.matched_keywords),
                         "matched_keywords": list(item.matched_keywords)} for item in snapshot.detections],
        }
