# GR141DG compatibility — v0.3.0

Model: GR141DG.

Firmware tested: `3GN8020900r29`.

Validation date: 6 October 2026.

## Live router evidence

Telnet login and the two radio commands were verified:

```text
wireless/show-stationinfo --wifi-index=0
wireless/show-stationinfo --wifi-index=1
/lan/dhcp/show
```

Index 0 covers 2.4 GHz; index 1 covers 5 GHz.

Indexes 2–7 were explicitly rejected as unsupported.

The tables use a `Yes` association marker and DHCP includes hostnames, MACs and IPv4 addresses.

A connected/disconnected/reconnected iPhone followed counts 1 → 0 → 1, despite its DHCP lease remaining after disconnection.

Moving the phone from HOME to GUEST produced an associated GUEST row on index 1, alongside HOME devices.

The phone reported an iPhone hostname on each network, with a different MAC and guest-subnet address on GUEST.

This confirms the existing station reads cover both HOME and GUEST on this firmware.

## Current design

Version 0.3.0 intentionally uses configured hostname keywords only.

Structured model discovery, heuristic scores and packet-capture experiments are removed from the integration.

All keywords are literal case-insensitive substrings.

Anonymous devices and names outside the configured list do not match.

DHCP output must be available; otherwise the poll fails and entities become unavailable.

Presence depends on current association, never a DHCP lease alone.

## Validation

Automated tests and saved live-response replays are run against the shared parser and matcher.

All 61 automated core tests and Python syntax checks pass.

Replaying the saved HOME and GUEST station/DHCP tables through the new matcher detected one phone in each case.

An actual Home Assistant 2025.3.0 runtime smoke test passed 13 checks using simulated router responses: setup and validation, presence and arrival behavior, grace periods, current device inventory, outage recovery, options reload and unload.

This validates the Home Assistant flow and entity plumbing separately from the live router protocol evidence.

The reproducible smoke test is `tools/ha_smoke_test.py` and runs in CI after installing Home Assistant.

No installation on the user's Home Assistant instance has been performed.

Departure tracking uses monotonic time and successful polls, with separate timers per matching device.

Public GitHub publication, HACS remote validation, and installation on the user’s Home Assistant remain pending.
