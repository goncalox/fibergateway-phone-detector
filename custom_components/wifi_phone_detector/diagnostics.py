"""Diagnostics omit credentials and identifying device data."""


async def async_get_config_entry_diagnostics(hass, entry):
    coordinator = entry.runtime_data
    snapshot = coordinator.data
    return {
        "last_update_success": coordinator.last_update_success,
        "scan_interval": coordinator.update_interval.total_seconds(),
        "detection_method": "hostname",
        "keyword_count": len(coordinator.scanner.keywords),
        "departure_delay": coordinator.tracker.departure_delay,
        "pending_departure_count": len(snapshot.pending_departures) if snapshot else None,
        "dhcp_names_available": coordinator.router.dhcp_available,
        "wifi_client_count": len(snapshot.clients) if snapshot else None,
        "phone_count": len(snapshot.phones) if snapshot else None,
        "unnamed_client_count": len(snapshot.unnamed) if snapshot else None,
    }
