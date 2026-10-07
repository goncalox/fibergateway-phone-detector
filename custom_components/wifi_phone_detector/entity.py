"""Shared entity identity."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME


class PhoneEntity(CoordinatorEntity):
    """Expose a device representing this configured router."""

    _attr_has_entity_name = True

    def __init__(self, entry, key: str) -> None:
        super().__init__(entry.runtime_data)
        self._phone_feature = key in {"phone_connected", "phone_arrival", "phone_count"}
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=NAME,
            manufacturer="Altice Labs", model="FiberGateway",
        )

    @property
    def available(self):
        return super().available and (not self._phone_feature or self.coordinator.scanner.enabled)
