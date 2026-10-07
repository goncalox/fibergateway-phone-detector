# Router control

Open **Developer Tools → Actions**, or add an action in Home Assistant’s automation/script editor, and search for **FiberGateway**.

| Action | Purpose | Response |
| --- | --- | --- |
| Read router information | Read `/device-info/show` | `output` text |
| Refresh connected devices | Update Wi-Fi inventory now | `device_count` |
| Read internet restrictions | List saved native schedules | `rules` list |
| Create internet restriction | Save a device’s blocking schedule | `created`, `rule` |
| Remove internet restriction | Remove one named schedule | `removed`, `name` |
| Execute router command | Run one command supported by Telnet CLI | `output` text |

Each action reuses the integration’s configured router login.

With one loaded router, the **Router** field is optional; with multiple routers, select one.

Interactive calls require a Home Assistant administrator; configured automations and scripts can call the actions without a user context.

## Native weekday internet block

Create the rule once; the router then enforces it without Home Assistant or the blocked device running.

Find the target MAC in **Connected devices** or the router’s device list; the example below uses a placeholder.

```yaml
action: wifi_phone_detector.create_time_restriction
data:
  name: Weekday-Night
  mac: "02:11:22:33:44:55"
  days: [Mon, Tue, Wed, Thu, Fri]
  start_time: "00:00"
  end_time: "05:00"
```

This blocks that MAC from internet access Monday–Friday, midnight–05:00, using the router’s local timezone and clock.

The days indicate when the block starts; an end earlier than the start ends the following day.

Use zero seconds in the time selectors; equal start/end times are rejected because their meaning is ambiguous.

An identical rule is kept; a different rule with the same name is rejected without replacing it.

To change a rule, remove its exact name first, then create the replacement.

A rule covers one MAC/interface; Ethernet, another Wi-Fi network or a changed private MAC may need a separate rule.

```yaml
action: wifi_phone_detector.remove_time_restriction
data:
  name: Weekday-Night
```

Only that rule is removed; other restrictions are preserved.

The integration reads the saved table after writing and reports mismatches; a lost reply is not automatically retried because the change may already have applied.

## Other router operations

Use **Execute router command** for any read or configuration command exposed by the router’s Telnet CLI.

`tree` lists the available command paths; `help` displays help, and a command path followed by `?` can show its arguments.

Use complete paths rather than commands that only navigate to another CLI directory; each action opens a new authenticated session.

Available operations and permissions depend on the model, firmware and router login.

Generic commands return CLI text, not structured entities; friendly actions currently cover information, inventory and native schedules.

Configuration commands run exactly once and are not automatically undone when the integration is unloaded.

For example, read the command tree in a Home Assistant script:

```yaml
sequence:
  - action: wifi_phone_detector.execute_command
    data:
      command: tree
    response_variable: router_response
  - action: persistent_notification.create
    data:
      title: FiberGateway command tree
      message: "{{ router_response.output }}"
```

The integration’s stored password is redacted from generic command responses; arbitrary router configuration output may still contain other sensitive settings.

## Optional phone detection and upgrades

Open the integration’s **Configure** options to enable/disable phone detection and edit name keywords, polling and departure delay.

Disabling it makes phone presence/count/arrival entities unavailable while the current Wi-Fi inventory remains usable.

Existing installations default to enabled and keep credentials, options, registered entity IDs and the `wifi_phone_detector_phone_arrived` event.

New installations use the **FiberGateway** name; `wifi_phone_detector` remains the technical domain so existing installations update normally through the same HACS repository.

## Verified scope

The native schedule commands and their saved-table format were verified on GR141DG firmware `3GN8020900r29`; a live weekday rule blocked new IPv4 and IPv6 internet connections during its active window.

Automated control tests use synthetic responses and never configure a real router.

The generic action exposes available CLI commands; it does not imply that every web-interface setting has a CLI equivalent.
