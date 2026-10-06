# Automations

## Trigger for each matching phone arrival

The integration emits `wifi_phone_detector_phone_arrived` once per new matching MAC.

This works even when another matching phone is already connected and the presence sensor remains on.

In Home Assistant's automation editor, add an **Event** trigger and enter that event type.

Then add the actions you want.

Example YAML:

```yaml
alias: Phone joined Wi-Fi
triggers:
  - trigger: event
    event_type: wifi_phone_detector_phone_arrived
actions:
  - action: persistent_notification.create
    data:
      title: Phone connected
      message: "{{ trigger.event.data.name }} joined Wi-Fi."
mode: queued
```

Event data includes `entry_id`, `name`, `mac`, `ip` and `matched_keywords`.

If you configure multiple routers, filter `event_data.entry_id` to restrict an automation to one integration entry.

The **Phone arrival** event entity provides the latest arrival timestamp and names for display in your dashboard.

If multiple matching phones join in one scan, the entity contains a grouped arrival while the event bus emits one event per phone.

## Presence and absence

Use **Phone connected** changing from off to on to run an automation when the first matching phone is detected.

Use on to off when the last matching phone has remained absent for the configured departure delay.

The default delay is two minutes, measured from the first successful missing-device scan and confirmed at a later successful scan.

The detected-phone count and connected-device inventory show the current scan immediately, even while aggregate presence remains on during the grace period.

`pending_departure_names` and `presence_phone_count` on the presence sensor show devices still held by the grace period.

A router or DHCP-name failure makes the entities unavailable; it does not confirm absence.

Startup, options reload and recovery after an outage do not emit fresh arrival events for the baseline devices.

Arrival tracking uses the MAC reported by the router, so a private-MAC change or a move between networks may create a new arrival.
