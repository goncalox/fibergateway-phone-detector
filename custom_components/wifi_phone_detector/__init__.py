"""Home Assistant entry lifecycle."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

from .coordinator import PhoneCoordinator
from .const import NAME
from .services import async_register_services

PLATFORMS = (Platform.BINARY_SENSOR, Platform.SENSOR, Platform.EVENT)
PhoneConfigEntry = ConfigEntry[PhoneCoordinator]


async def async_setup(hass, config) -> bool:
    """Register reusable router actions independently of entry availability."""
    async_register_services(hass)
    return True


async def async_setup_entry(hass, entry: PhoneConfigEntry) -> bool:
    """Perform the first refresh before exposing entities."""
    coordinator = PhoneCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    if entry.title in {"FiberGateway Phone Detector", "Wi-Fi Phone Detector"}:
        hass.config_entries.async_update_entry(entry, title=NAME)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass, entry: PhoneConfigEntry) -> None:
    """Apply changed options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry: PhoneConfigEntry) -> bool:
    """Unload all entities; router connections are scoped to each poll."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
