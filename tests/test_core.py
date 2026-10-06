"""Core tests use synthetic responses, never claim real router compatibility."""

import asyncio
import importlib
import pathlib
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch

# Load the independent modules without importing the Home Assistant entrypoint.
ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE = "detector_test_package"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / "custom_components" / "wifi_phone_detector")]
sys.modules[PACKAGE] = package
parser = importlib.import_module(f"{PACKAGE}.parser")
models = importlib.import_module(f"{PACKAGE}.models")
classifier = importlib.import_module(f"{PACKAGE}.classifier")
router = importlib.import_module(f"{PACKAGE}.router")

MAC = "02:11:22:33:44:55"
OTHER = "aa:bb:cc:dd:ee:ff"
STATIONS = f"| BSSID | Station MAC | Associated | RSSI |\n| {OTHER} | {MAC} | Yes | -50 |\n/cli>"
LEASES = f"| IP Address | MAC Address | Hostname |\n| 192.168.1.10 | {MAC} | My-iPhone |\n/cli>"


class ParserTests(unittest.TestCase):
    def test_station_column_excludes_access_point_mac(self):
        self.assertEqual(parser.parse_stations(STATIONS), frozenset({MAC}))

    def test_normalizes_all_supported_mac_inputs(self):
        for value in (MAC.upper(), MAC.replace(":", "-"), "021122334455", "0211.2233.4455"):
            with self.subTest(value=value):
                self.assertEqual(parser.normalize_mac(value), MAC)

    def test_lease_correlation_excludes_disconnected_lease(self):
        leases = parser.parse_leases(LEASES + f"\n| 192.168.1.11 | {OTHER} | iPhone |")
        clients = parser.correlate(frozenset({MAC}), leases)
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0].hostname, "My-iPhone")

    def test_station_without_lease_remains_present(self):
        self.assertEqual(parser.correlate(frozenset({MAC}), {}), (models.Client(MAC),))

    def test_explicit_empty_output(self):
        self.assertFalse(parser.parse_stations("Stations count: 0\n/cli>"))
        self.assertFalse(parser.parse_stations("| Station MAC | Associated | RSSI |\n+----+----+\n/cli>"))
        self.assertFalse(parser.parse_leases("No DHCP leases\n/cli>"))

    def test_unknown_output_never_means_empty(self):
        for text in ("", "/cli>", "Unknown command", "Usage: command", "No stations\n" + MAC):
            with self.subTest(text=text), self.assertRaises(parser.ParseError):
                parser.parse_stations(text)

    def test_malformed_rows_never_mean_empty(self):
        for text in ("| MAC | Associated | RSSI |\n| invalid-mac | Yes | -40 |", "| MAC | Associated | RSSI |\n| 02:11:22:33:44:55 |"):
            with self.subTest(text=text), self.assertRaises(parser.ParseError):
                parser.parse_stations(text)

    def test_compact_mac_in_named_table(self):
        self.assertEqual(parser.parse_stations("| MAC | Associated | RSSI |\n| 021122334455 | Yes | -40 |"), frozenset({MAC}))

    def test_reference_association_marker_filters_disconnected_rows(self):
        text = f"| 1 | {MAC.upper()} | Yes | -50 |\n| 2 | {OTHER} | No | -40 |\ncli>"
        self.assertEqual(parser.parse_stations(text), frozenset({MAC}))

    def test_all_disconnected_is_a_valid_empty_result(self):
        self.assertFalse(parser.parse_stations(f"| {MAC} | No | -40 |\ncli>"))

    def test_lowercase_and_hyphenated_association_rows(self):
        self.assertEqual(parser.parse_stations(f"| {MAC.replace(':', '-')} | yes | -50 |"), frozenset({MAC}))

    def test_unknown_status_is_never_silently_discarded(self):
        text = f"| {MAC} | Yes |\n| {OTHER} | Maybe |"
        with self.assertRaises(parser.ParseError):
            parser.parse_stations(text)

    def test_inventory_without_association_state_is_rejected(self):
        text = f"| MAC | RSSI |\n| {MAC} | -50 |"
        with self.assertRaises(parser.ParseError):
            parser.parse_stations(text)

    def test_optional_station_names_are_automatically_available(self):
        text = f"| MAC | Associated | Hostname | IPv4 Address |\n| {MAC} | Yes | Guest-iPhone | 192.168.1.20 |"
        stations = parser.parse_stations(text)
        metadata = parser.parse_station_metadata(text, stations)
        clients = parser.correlate(stations, {}, metadata)
        self.assertEqual(clients[0], models.Client(MAC, "192.168.1.20", "Guest-iPhone"))
        self.assertTrue(classifier.classify(clients[0]).matched_keywords)

    def test_invalid_and_conflicting_dhcp(self):
        for text in (LEASES.replace("192.168.1.10", "999.1.1.1"), LEASES + f"\n| 192.168.1.12 | {MAC} | Other |"):
            with self.subTest(text=text), self.assertRaises(parser.ParseError):
                parser.parse_leases(text)

    def test_mac_list_rejects_bad_address(self):
        with self.assertRaises(ValueError):
            parser.parse_mac_list(MAC + ",bad")


class NameMatchingTests(unittest.TestCase):
    def test_default_keywords_recognize_visitors(self):
        for name in ("Alice-iPhone", "IPHONE", "Pixel-9-Pro", "Galaxy-S24", "OnePlus", "android-abcd", "Redmi", "Guest Phone"):
            with self.subTest(name=name):
                self.assertTrue(classifier.classify(models.Client(MAC, hostname=name)).matched_keywords)

    def test_user_keywords_are_literal_substrings(self):
        keywords = classifier.parse_name_keywords("Alice, Work Phone, phone.*")
        for name, expected in [("alice-device", True), ("MY WORK PHONE", True), ("smartphone", False), ("phone.*", True)]:
            self.assertEqual(bool(classifier.classify(models.Client(MAC, hostname=name), keywords).matched_keywords), expected)

    def test_lists_deduplicate_and_preserve_spaces(self):
        self.assertEqual(classifier.parse_name_keywords(" iPhone, ANDROID\niphone\n Work Phone "), ("iphone", "android", "work phone"))

    def test_empty_and_invalid_lists_are_rejected(self):
        for text in ("", " ,\n ", "phone\x00", None):
            with self.subTest(text=text), self.assertRaises(ValueError):
                classifier.parse_name_keywords(text)

    def test_names_only_no_vendor_or_mac_inference(self):
        self.assertFalse(classifier.classify(models.Client(MAC)).matched_keywords)
        self.assertFalse(classifier.classify(models.Client(MAC, hostname="laptop")).matched_keywords)

    def test_non_phone_with_matching_name_is_accepted(self):
        self.assertTrue(classifier.classify(models.Client(MAC, hostname="android-tv")).matched_keywords)

    def test_one_device_matching_many_keywords_counts_once(self):
        client = models.Client(MAC, hostname="iPhone")
        detection = classifier.classify(client)
        self.assertEqual(detection.matched_keywords, ("iphone", "phone"))
        self.assertEqual(len(models.Snapshot((client,), (detection,)).phones), 1)

    def test_no_matching_clients_is_off_even_with_unnamed_clients(self):
        clients = (models.Client(MAC), models.Client(OTHER, hostname="laptop"))
        snapshot = models.Snapshot(clients, tuple(classifier.classify(c) for c in clients))
        self.assertFalse(snapshot.phone_connected)
        self.assertEqual(len(snapshot.unnamed), 1)

    def test_empty_wifi_is_off(self):
        self.assertFalse(models.Snapshot((), ()).phone_connected)


class FakeReader:
    def __init__(self, responses):
        self.responses = iter(responses)

    async def read(self, size):
        value = next(self.responses, "")
        if isinstance(value, BaseException):
            raise value
        return value


class FakeWriter:
    def __init__(self):
        self.writes = []
        self.closed = False

    def write(self, value):
        self.writes.append(value)

    async def drain(self):
        pass

    def close(self):
        self.closed = True


class RouterTests(unittest.IsolatedAsyncioTestCase):
    async def run_session(self, responses):
        self.writer = FakeWriter()
        reader = FakeReader(responses)
        with patch.object(router.telnetlib3, "open_connection", AsyncMock(return_value=(reader, self.writer))):
            return await router.RouterClient("router", "user", "secret").async_fetch()

    async def test_successful_read_only_session(self):
        clients = await self.run_session(["Lo", "gin: ", "Password: ", "\n/cli>", STATIONS, STATIONS, LEASES])
        self.assertEqual(clients[0].hostname, "My-iPhone")
        self.assertEqual(self.writer.writes, ["user\r\n", "secret\r\n", "wireless/show-stationinfo --wifi-index=0\r\n", "wireless/show-stationinfo --wifi-index=1\r\n", "/lan/dhcp/show\r\n"])
        self.assertTrue(self.writer.closed)

    async def test_rejected_password_closes_connection(self):
        with self.assertRaises(router.AuthenticationError):
            await self.run_session(["Login:", "Password:", "Login incorrect\nLogin:"])
        self.assertTrue(self.writer.closed)

    async def test_repeated_login_is_authentication_error(self):
        with self.assertRaises(router.AuthenticationError):
            await self.run_session(["Login:", "Password:", "Login:"])
        self.assertTrue(self.writer.closed)

    async def test_unsupported_command_closes_connection(self):
        with self.assertRaises(parser.ParseError):
            await self.run_session(["Login:", "Password:", "\n/cli>", "Unknown command\n/cli>", LEASES])
        self.assertTrue(self.writer.closed)

    async def test_timeout_does_not_return_empty(self):
        with self.assertRaises(router.RouterError):
            await self.run_session(["Login:", "Password:", "\n/cli>", TimeoutError()])
        self.assertTrue(self.writer.closed)

    async def test_cancellation_closes_connection(self):
        with self.assertRaises(asyncio.CancelledError):
            await self.run_session(["Login:", "Password:", "\n/cli>", asyncio.CancelledError()])
        self.assertTrue(self.writer.closed)

    async def test_connection_failure(self):
        with patch.object(router.telnetlib3, "open_connection", AsyncMock(side_effect=OSError("unreachable"))):
            with self.assertRaises(router.RouterError):
                await router.RouterClient("router", "user", "secret").async_fetch()

    async def test_both_bands_are_merged_and_duplicates_removed(self):
        second_band = f"| {MAC} | Yes |\n| {OTHER} | Yes |\ncli>"
        clients = await self.run_session(["Login:", "Password:", "\ncli>", STATIONS, second_band, "Unknown command\ncli>"])
        self.assertEqual({client.mac for client in clients}, {MAC, OTHER})
        self.assertEqual(len(clients), 2)
        self.assertTrue(self.writer.closed)

    async def test_optional_dhcp_timeout_preserves_association(self):
        clients = await self.run_session(["Login:", "Password:", "\ncli>", STATIONS, STATIONS, TimeoutError()])
        self.assertEqual(clients, (models.Client(MAC),))
        self.assertTrue(self.writer.closed)

    async def test_second_band_failure_does_not_report_partial_absence(self):
        with self.assertRaises(parser.ParseError):
            await self.run_session(["Login:", "Password:", "\ncli>", STATIONS, "Unknown command\ncli>"])
        self.assertTrue(self.writer.closed)

    async def test_valid_empty_network_does_not_keep_previous_clients(self):
        clients = await self.run_session(["Login:", "Password:", "\ncli>", f"| {MAC} | No |\ncli>", "No stations\ncli>", "Unknown command\ncli>"])
        self.assertEqual(clients, ())

    async def test_dhcp_authentication_failure_is_not_suppressed(self):
        with self.assertRaises(router.AuthenticationError):
            await self.run_session(["Login:", "Password:", "\ncli>", STATIONS, STATIONS, "Login incorrect\nLogin:"])
        self.assertTrue(self.writer.closed)

    def test_credentials_cannot_inject_cli_commands(self):
        with self.assertRaises(ValueError):
            router.RouterClient("router", "user\ncommand", "secret")


if __name__ == "__main__":
    unittest.main()
