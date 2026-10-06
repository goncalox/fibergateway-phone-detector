# Test without Home Assistant

The standalone tester shares the integration's router parser and hostname matcher.

Python 3.11 or newer is required.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-standalone.txt
.venv/bin/python tools/standalone.py --demo
.venv/bin/python tools/standalone.py --host 192.168.1.254 --watch
```

Live mode prompts for your router username and password locally and does not save the password.

No Mac administrator password is needed.

To customize the list:

```sh
.venv/bin/python tools/standalone.py --watch --names "iphone, android, Alice"
```

The demo uses synthetic station/DHCP tables to show a matching phone connecting, disconnecting while its lease remains, and an unnamed device that does not match.

The last two cases report off.

Use `--json` for a local machine-readable report and `--interval 15` to control the delay between standalone scans.

Home Assistant has a separate polling option, defaulting to 45 seconds.

Stop any older running watcher and restart it to load the v0.3.0 code.

The Mac launchers in this workspace use its existing test environment and are not included in the install ZIP.

```sh
.venv/bin/python -m unittest discover -s tests -v
```

For the actual Home Assistant runtime smoke test, use Python 3.13 in an isolated environment:

```sh
python3.13 -m venv .ha-test
.ha-test/bin/python -m pip install homeassistant==2025.3.0 -r requirements-standalone.txt
.ha-test/bin/python tools/ha_smoke_test.py
```

This uses simulated router responses and a temporary Home Assistant config directory.

It does not connect to the router or to your Home Assistant instance.

Live standalone scans apply the departure grace period and report new arrivals.

Use `--departure-delay 0` for immediate absence or `--departure-delay 120` for the default two-minute grace.

The synthetic demo illustrates raw name matching without the grace period.
