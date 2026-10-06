"""Exercise the shared pipeline without importing Home Assistant."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import AsyncMock, patch


PROJECT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "standalone_test_entrypoint", PROJECT / "tools" / "standalone.py"
)
standalone = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(standalone)


class StandaloneTests(unittest.TestCase):
    def test_demo_covers_presence_absence_and_unnamed(self):
        cases = standalone.demo_snapshots()
        self.assertEqual([case[1].phone_connected for case in cases], [True, False, False])

    def test_reports_preserve_disconnect(self):
        reports = [standalone.report(snapshot, source="demo") for _, snapshot in standalone.demo_snapshots()]
        self.assertEqual([item["phone_connected"] for item in reports], [True, False, False])
        self.assertEqual([item["phone_count"] for item in reports], [1, 0, 0])
        self.assertEqual([item["wifi_client_count"] for item in reports], [2, 1, 1])
        self.assertEqual(reports[2]["unnamed_client_count"], 1)
        for item in reports:
            self.assertEqual(item["source"], "demo")
            self.assertNotIn("password", item)
            self.assertIsInstance(json.loads(json.dumps(item)), dict)

    def test_demo_command_needs_no_home_assistant(self):
        imported = []
        real_import = __import__

        def guarded_import(name, *args, **kwargs):
            imported.append(name)
            if name == "homeassistant" or name.startswith("homeassistant."):
                raise AssertionError("Standalone mode must not import Home Assistant")
            return real_import(name, *args, **kwargs)

        output = io.StringIO()
        with patch.object(sys, "argv", ["standalone.py", "--demo", "--json"]):
            with patch("builtins.__import__", side_effect=guarded_import):
                with contextlib.redirect_stdout(output):
                    self.assertEqual(standalone.main(), 0)
        reports = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual([item["phone_connected"] for item in reports], [True, False, False])
        self.assertFalse(any(name.startswith("homeassistant") for name in imported))


class SharedScannerTests(unittest.IsolatedAsyncioTestCase):
    async def test_automatic_detection_and_departure_use_current_clients(self):
        scanner_class = standalone.core("scanner").PhoneScanner
        snapshots = [snapshot for _, snapshot in standalone.demo_snapshots()]
        router = type("FakeRouter", (), {"dhcp_available": True})()
        router.async_fetch = AsyncMock(side_effect=[snapshot.clients for snapshot in snapshots])
        scanner = scanner_class(router)
        results = [await scanner.async_scan() for _ in snapshots]
        self.assertEqual([snapshot.phone_connected for snapshot in results], [True, False, False])
        self.assertEqual(router.async_fetch.await_count, 3)

    async def test_custom_keywords_override_defaults(self):
        scanner_class = standalone.core("scanner").PhoneScanner
        models = standalone.core("models")
        router = type("FakeRouter", (), {"dhcp_available": True})()
        router.async_fetch = AsyncMock(return_value=(models.Client("aa:bb:cc:dd:ee:ff", hostname="guest-iPhone"),))
        self.assertFalse((await scanner_class(router, name_keywords="Alice").async_scan()).phone_connected)
        self.assertTrue((await scanner_class(router, name_keywords="guest").async_scan()).phone_connected)

    async def test_missing_dhcp_names_is_unavailable(self):
        scanner_class = standalone.core("scanner").PhoneScanner
        router_module = standalone.core("router")
        router = type("FakeRouter", (), {"dhcp_available": False})()
        router.async_fetch = AsyncMock(return_value=())
        with self.assertRaisesRegex(router_module.RouterError, "device names"):
            await scanner_class(router).async_scan()

    async def test_failed_fetch_does_not_produce_false_absence(self):
        scanner_class = standalone.core("scanner").PhoneScanner
        router = type("FakeRouter", (), {"dhcp_available": True})()
        router.async_fetch = AsyncMock(side_effect=RuntimeError("Router unavailable"))
        scanner = scanner_class(router)
        with self.assertRaisesRegex(RuntimeError, "Router unavailable"):
            await scanner.async_scan()

    def test_keyword_list_cannot_be_empty(self):
        with self.assertRaises(ValueError):
            standalone.core("scanner").PhoneScanner(object(), name_keywords=" , ")


if __name__ == "__main__":
    unittest.main()
