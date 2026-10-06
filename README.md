# FiberGateway Phone Detector — v0.3.0

A Home Assistant custom integration for the MEO/Altice FiberGateway GR141DG.

Enter a list of name keywords; when any currently connected Wi-Fi device has a matching hostname, the **Phone connected** presence sensor turns on.

Matching is case-insensitive and checks whether a keyword occurs anywhere in the name.

For example, `iphone` matches both `Sam-iPhone` and `iPhone`, while `android` matches `android-abcd`.

Visitors are picked up automatically if the name reported by the router contains a configured keyword.

## Install

1. Extract the v0.3.0 ZIP and copy `custom_components/wifi_phone_detector` into your Home Assistant `/config/custom_components/` directory.
2. Restart Home Assistant.
3. Open **Settings → Devices & services → Add integration → FiberGateway Phone Detector**.
4. Enter the router address (normally `192.168.1.254`), Telnet port (normally `23`), and router login.
5. Review the name keywords and polling interval.

Home Assistant 2025.3 or newer is required.

HACS packaging, validation and release workflows are prepared; publication to the approved public GitHub repository is in progress.

See [HACS.md](HACS.md) for installation and update steps once the repository is published.

Router Telnet access sends its login without encryption, so use it on your trusted local network.

No Mac password, packet capture, mDNS discovery, device registration or external service is used.

## Configure name matching

The default list is:

```text
iphone, phone, android, pixel, galaxy, oneplus, xiaomi, redmi, poco, huawei, honor, moto, oppo, realme, vivo
```

Edit it in the integration's **Configure** options at any time.

Commas and newlines separate keywords; spaces within names are preserved.

The departure delay defaults to 120 seconds and can be set to 0–1800 seconds in **Configure**.

A matching phone is detected immediately at the next successful poll; presence stays on through brief disconnections and turns off after the grace period expires, at the next successful poll.

The grace period begins at the first successful scan that no longer sees that matching phone.

You can use typical names, custom device names, or both.

A non-phone with a matching name also counts, intentionally; edit the list or rename that device if needed.

Devices with no hostname or no matching keyword do not count.

A phone called only `Alice` will need an `Alice` keyword.

The sensor checks every 45 seconds by default; the configurable range is 15–300 seconds.

## Entities and automations

- **Phone connected**: on when a device matches or is within its departure grace period.
- **Phone arrival**: event entity updated when a new matching phone joins, even if presence stays on.
- **Connected devices**: current inventory, including names and matched keywords in its attributes.
- **Detected phones**: count of matching devices, with each device counted once.
- **Wi-Fi clients**: count of currently associated devices.
- **Wi-Fi clients without a name**: count of devices that cannot match a keyword.

The presence sensor includes `matched_names`, `phone_count` and `name_keywords` attributes.

Select **Phone connected** as a state trigger in Home Assistant's automation editor, from **off** to **on**, then add your desired actions.

For absence, trigger from **on** to **off**; the integration already applies the configured departure delay.

For individual arrivals while another phone is connected, use the `wifi_phone_detector_phone_arrived` event.

See [AUTOMATIONS.md](AUTOMATIONS.md) for examples and [DASHBOARD.md](DASHBOARD.md) for a readable device list.

Initial startup, integration reload and the first successful reading after a router outage establish a baseline and do not emit arrival events.

A brief reconnection with the same MAC within the grace period does not emit another arrival.

Arrivals identify Wi-Fi MAC addresses, not people; a phone switching private MAC or networks can appear as a new arrival.

Router association or DHCP-name failures make entities unavailable instead of reporting a false absence.

Old DHCP leases are never sufficient for presence: a matching MAC must also appear as currently associated in a Wi-Fi station table.

## Verified scope

Both radio indexes (2.4 GHz and 5 GHz) are read and duplicate MACs are merged.

Live router checks on GR141DG firmware `3GN8020900r29` verified HOME and GUEST in the station tables.

The tested phone matched the `iphone` keyword on both HOME and GUEST.

See [STANDALONE.md](STANDALONE.md) for testing outside Home Assistant and [GR141DG-compatibility.md](GR141DG-compatibility.md) for validation results.

The router transport follows [queimadus/fgw_router](https://github.com/queimadus/fgw_router/blob/master/custom_components/fgw_router/device_tracker.py).

Configuration options follow [Home Assistant's options-flow documentation](https://developers.home-assistant.io/docs/core/integration/options_flow/).
