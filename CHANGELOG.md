# v0.3.0

- Emit phone-arrival events when new matching devices join, even if presence is already on.
- Add a Phone arrival event entity and a Connected devices inventory sensor.
- Add a configurable departure delay, defaulting to 120 seconds.
- Suppress repeated arrival events during brief reconnections and baseline events after startup, reload or router outages.
- Prepare HACS manifests, brand assets, validation and automatic release packaging.
- Preserve hostname-only matching and both Wi-Fi radio reads, verified for HOME and GUEST.
- Validate with core tests and an actual Home Assistant runtime using simulated router responses.
