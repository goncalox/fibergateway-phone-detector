#!/usr/bin/env python3
"""Test router association and name-based phone presence without HA.

Python 3.11+ is required; --demo needs only the standard library.
Live mode requires requirements-standalone.txt and prompts for credentials.
"""

import argparse
import asyncio
from datetime import datetime, timezone
import getpass
import importlib
import json
from pathlib import Path
import sys
import types

PROJECT = Path(__file__).resolve().parents[1]
PACKAGE = "wifi_phone_detector_standalone_core"


def core(name):
    """Load shared modules without executing the Home Assistant entrypoint."""
    if PACKAGE not in sys.modules:
        package = types.ModuleType(PACKAGE)
        package.__path__ = [str(PROJECT / "custom_components" / "wifi_phone_detector")]
        sys.modules[PACKAGE] = package
    return importlib.import_module(f"{PACKAGE}.{name}")


def report(snapshot, *, dhcp_available=None, source="live"):
    """Return a local report; credentials never enter the result."""
    phones = {item.client.mac for item in snapshot.phones}
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "phone_connected": snapshot.phone_connected,
        "wifi_client_count": len(snapshot.clients),
        "phone_count": len(snapshot.phones),
        "presence_phone_count": len(snapshot.effective_phones),
        "pending_departure_names": [item.client.hostname for item in snapshot.pending_departures],
        "arrivals": [item.client.hostname for item in snapshot.arrivals],
        "unnamed_client_count": len(snapshot.unnamed),
        "dhcp_enrichment_available": dhcp_available,
        "clients": [
            {
                "mac": item.client.mac, "ip": item.client.ip,
                "hostname": item.client.hostname,
                "classification": "phone" if item.client.mac in phones
                else "not_matched",
                "matched_keywords": list(item.matched_keywords),
            }
            for item in snapshot.detections
        ],
    }


def emit(data, as_json=False, label=None):
    if as_json:
        print(json.dumps(data), flush=True)
        return
    if label:
        print(f"\n{label}")
    if "error" in data:
        print(f"UNAVAILABLE: {data['error']}", flush=True)
        return
    state = {True: "YES", False: "NO", None: "UNKNOWN"}[data["phone_connected"]]
    print(f"Phone connected: {state} | Wi-Fi clients: {data['wifi_client_count']} | "
          f"Phones: {data['phone_count']} | Unnamed: {data['unnamed_client_count']}")
    if data["source"] == "demo":
        print("Synthetic demonstration; no router was contacted.")
    elif not data["dhcp_enrichment_available"]:
        print("DHCP enrichment unavailable; station metadata may still identify devices.")
    for client in data["clients"]:
        name = client["hostname"] or "no hostname"
        address = client["ip"] or "no IP"
        print(f"  {client['mac']}  {address}  {name}  "
              f"{client['classification']}")
        if client["matched_keywords"]:
            print("    Matched keywords: " + ", ".join(client["matched_keywords"]))
    if data.get("pending_departure_names"):
        print("    Awaiting departure confirmation: " + ", ".join(data["pending_departure_names"]))
    if data.get("arrivals"):
        print("    New arrivals: " + ", ".join(data["arrivals"]))
    print(flush=True)


def demo_snapshots(name_keywords=None):
    """Demonstrate new phone detection, disconnection and anonymous clients."""
    models, parser, classifier = core("models"), core("parser"), core("classifier")
    keywords = classifier.parse_name_keywords(name_keywords or core("const").DEFAULT_NAMES)
    phone, computer, anonymous = "02:11:22:33:44:55", "02:22:33:44:55:66", "02:33:44:55:66:77"
    leases = parser.parse_leases(
        "| MAC Address | IP Address | Hostname |\n"
        f"| {phone} | 192.0.2.10 | Guest-iPhone |\n"
        f"| {computer} | 192.0.2.20 | Work-MacBook |"
    )
    cases = (
        ("A new phone connects without registration", f"| {phone} | Yes |\n| {computer} | Yes |"),
        ("Phone disconnects while its DHCP lease remains", f"| {phone} | No |\n| {computer} | Yes |"),
        ("An anonymous device connects", f"| {anonymous} | Yes |"),
    )
    results = []
    for label, text in cases:
        clients = parser.correlate(parser.parse_stations(text), leases)
        detections = tuple(classifier.classify(client, keywords) for client in clients)
        results.append((label, models.Snapshot(clients, detections)))
    return results


async def live(args):
    router_module, scanner_module = core("router"), core("scanner")
    parser_module = core("parser")
    username = args.username or input("Router username: ").strip()
    password = getpass.getpass("Router password (not saved): ")
    router = router_module.RouterClient(args.host, username, password, args.port, args.timeout)
    scanner = scanner_module.PhoneScanner(router, name_keywords=args.names)
    tracker = core("presence").PresenceTracker(args.departure_delay)
    while True:
        try:
            snapshot = tracker.update(await scanner.async_scan())
        except router_module.AuthenticationError:
            tracker.pause()
            emit({"source": "live", "error": "Router rejected credentials"}, args.json)
            return 2
        except (router_module.RouterError, parser_module.ParseError) as err:
            tracker.pause()
            emit({"source": "live", "error": str(err)}, args.json)
            if not args.watch:
                return 2
        else:
            emit(report(snapshot, dhcp_available=router.dhcp_available), args.json)
            if not args.watch:
                return 0
        await asyncio.sleep(args.interval)


def number(minimum, maximum, converter=int):
    def validate(value):
        result = converter(value)
        if not minimum <= result <= maximum:
            raise argparse.ArgumentTypeError(f"Choose a value between {minimum} and {maximum}")
        return result
    return validate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Run synthetic examples with no dependencies or network")
    parser.add_argument("--host", default="192.168.1.254")
    parser.add_argument("--port", type=number(1, 65535), default=23)
    parser.add_argument("--username", help="Optional username; otherwise prompt")
    parser.add_argument("--watch", action="store_true", help="Repeat until Ctrl+C")
    parser.add_argument("--interval", type=number(10, 300), default=15, help="Pause between scans, in seconds")
    parser.add_argument("--timeout", type=number(1, 60, float), default=10, help="Timeout for each network operation")
    parser.add_argument("--names", default=core("const").DEFAULT_NAMES, help="Comma- or newline-separated name keywords")
    parser.add_argument("--departure-delay", type=number(0, 1800), default=120, help="Grace period before confirming departure, in seconds")
    parser.add_argument("--json", action="store_true", help="Print a local JSON report for each scan")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):
        parser.error("Python 3.11 or newer is required")
    try:
        core("classifier").parse_name_keywords(args.names)
    except ValueError as err:
        parser.error(str(err))
    if args.demo:
        for label, snapshot in demo_snapshots(args.names):
            emit(report(snapshot, source="demo"), args.json, label)
        return 0
    try:
        return asyncio.run(live(args))
    except ModuleNotFoundError as err:
        print(f"Missing dependency: {err.name}; install requirements-standalone.txt", file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        return 130
    except (OSError, ValueError, RuntimeError):
        # Avoid accidentally displaying credentials in a library exception.
        print("Unable to start the standalone check; check local network access and input.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
