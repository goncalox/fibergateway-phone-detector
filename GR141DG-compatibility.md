# GR141DG compatibility — v0.4.0

Model: GR141DG.

Firmware tested: `3GN8020900r29`.

Live protocol checks: 6–7 October 2026.

## Live router evidence

Telnet login and both radio tables were verified:

```text
wireless/show-stationinfo --wifi-index=0
wireless/show-stationinfo --wifi-index=1
/lan/dhcp/show
```

Index 0 covers 2.4 GHz; index 1 covers 5 GHz; indexes 2–7 were rejected as unsupported.

The tables have a `Yes` association marker; DHCP provides hostname, MAC and IPv4 metadata.

A connected/disconnected/reconnected iPhone followed counts 1 → 0 → 1 even while its DHCP lease remained.

Moving the phone from the main to guest network showed an associated guest row alongside main-network clients.

Both station tables are read without filtering by SSID name, and duplicate MACs are merged.

The following native commands were also verified by code:

```text
/management/ntp/show
/parental-control/time-restriction/show
/parental-control/time-restriction/create --MACAddress=... --days-week=Mon,Tue,Wed,Thu,Fri --end-time=05:00 --name=... --start-time=00:00
/parental-control/time-restriction/remove --rmv-name=...
```

Creating the weekday midnight–05:00 rule was verified by reading it back; new IPv4 and IPv6 internet connections were blocked during the active window, and the user confirmed the block worked.

No private router reports, credentials or device addresses are included in the public source.

## Current design and limitations

Router control and optional phone detection share the configured login.

Matching uses literal case-insensitive name substrings; presence requires current association, never a DHCP lease alone.

With phone detection enabled, missing DHCP names fail the poll rather than confirm absence.

With phone detection disabled, missing DHCP names do not prevent station inventory from updating.

Native schedules are bound to the chosen MAC and router clock; other interfaces or private-MAC changes need their own rules.

Other generic CLI operations depend on model, firmware and login permissions; every web-interface feature is not guaranteed to be available through Telnet.

## Reproducible validation

The core tests cover parsing, matching, both-radio association, arrival/departure behavior, command validation, serialized sessions, verified schedule writes and preservation of existing rules.

`tools/ha_smoke_test.py` runs 13 checks in Home Assistant 2025.3.0 using simulated router responses for flows, entity states, grace periods, inventory and outage recovery.

`tools/ha_control_smoke_test.py` runs 11 checks in the same actual runtime for six actions, UI selectors, response data, validation, administrator access, multi-router selection, optional matching and upgrade compatibility.

Runtime action tests never write to a real router; live protocol evidence is separate from these simulated checks.

No installation on the user’s Home Assistant instance has been performed.

The release workflow runs source/runtime tests and Home Assistant manifest validation before publishing.
