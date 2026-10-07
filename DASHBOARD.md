# Live device list

Open the **Connected devices** sensor to inspect its current device names and `devices` attributes.

Each device includes its name, IP address, MAC, phone-match status and matching keywords.

The list contains only currently associated Wi-Fi devices across both radio tables, including main and guest clients on the tested firmware; network names are not filters.

For a readable dashboard list, add a **Markdown** card and paste this configuration.

Replace the entity ID if Home Assistant assigned a different one; upgrades retain their existing IDs, which may use `fibergateway_phone_detector` or `wi_fi_phone_detector`.

```yaml
type: markdown
title: Connected Wi-Fi devices
content: >-
  {% set inventory = 'sensor.fibergateway_connected_devices' %}
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
