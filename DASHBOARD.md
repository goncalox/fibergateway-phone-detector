# Live device list

Open the **Connected devices** sensor to inspect its current device names and `devices` attributes.

Each device includes its name, IP address, MAC, phone-match status and matching keywords.

The list contains only currently associated Wi-Fi devices across both radio tables, including HOME and GUEST on the tested firmware.

For a readable dashboard list, add a **Markdown** card and paste this configuration.

Replace the entity ID if Home Assistant assigned a different one; upgrades may retain the earlier `wi_fi_phone_detector` prefix.

```yaml
type: markdown
title: Connected Wi-Fi devices
content: >-
  {% set inventory = 'sensor.fibergateway_phone_detector_connected_devices' %}
  {% if states(inventory) in ['unavailable', 'unknown'] %}
  Router readings unavailable.
  {% else %}
  {% for device in state_attr(inventory, 'devices') or [] %}
  - **{{ device.name | e }}** — {{ ('matches: ' ~ (device.matched_keywords | join(', '))) if device.is_phone else 'no keyword match' }}

  {% else %}
  No connected Wi-Fi devices.
  {% endfor %}
  {% endif %}
```

The inventory changes immediately with each successful scan; departure grace applies to the presence sensor separately.

The inventory attributes are excluded from recorder history to avoid storing a continuous device-name and address history.
