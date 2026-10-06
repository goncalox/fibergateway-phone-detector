"""Home Assistant entry lifecycle."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

from .coordinator import PhoneCoordinator

PLATFORMS = (Platform.BINARY_SENSOR, Platform.SENSOR, Platform.EVENT)
PhoneConfigEntry = ConfigEntry[PhoneCoordinator]


async def async_setup_entry(hass, entry: PhoneConfigEntry) -> bool:
    """Perform the first refresh before exposing entities."""
    coordinator = PhoneCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass, entry: PhoneConfigEntry) -> None:
    """Apply changed options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry: PhoneConfigEntry) -> bool:
    """Unload all entities; router connections are scoped to each poll."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

