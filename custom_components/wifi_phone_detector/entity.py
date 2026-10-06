"""Shared entity identity."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME


class PhoneEntity(CoordinatorEntity):
    """Expose a device representing this configured router."""

    _attr_has_entity_name = True

    def __init__(self, entry, key: str) -> None:
        super().__init__(entry.runtime_data)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=NAME,
            manufacturer="Altice Labs", model="FiberGateway",
        )
