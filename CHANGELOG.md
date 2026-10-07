# v0.4.0

- Broaden the integration to **FiberGateway**, with reusable actions in Home Assistant scripts, automations and Developer Tools.
- Add read-router-information, refresh-devices, read/create/remove internet restrictions, and execute-router-command actions.
- Use existing configured credentials; select the router explicitly when multiple entries are loaded.
- Allow any single command exposed by the router’s Telnet CLI; validate native schedules, preserve conflicting rules, verify writes and never retry uncertain writes.
- Make phone detection optional; device inventory and controls work without matching names when it is disabled.
- Keep existing configuration, HACS repository URL, integration domain and entity IDs.
- Test command transport, actual Home Assistant actions, administrator access, multi-router selection and upgrade behavior with simulated responses.

# v0.3.0

- Emit phone-arrival events when new matching devices join, even if presence is already on.
- Add a Phone arrival event entity and a Connected devices inventory sensor.
- Add a configurable departure delay, defaulting to 120 seconds.
- Suppress repeated arrival events during brief reconnections and baseline events after startup, reload or router outages.
- Prepare HACS manifests, brand assets, validation and automatic release packaging.
- Preserve hostname-only matching and both Wi-Fi radio reads, verified for HOME and GUEST.
- Validate with core tests and an actual Home Assistant runtime using simulated router responses.
