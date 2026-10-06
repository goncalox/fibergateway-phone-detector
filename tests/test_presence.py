"""Presence behavior: arrivals, grace periods and outages."""
import importlib
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE = 'presence_test_package'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT / 'custom_components/wifi_phone_detector')]
sys.modules[PACKAGE] = package
models = importlib.import_module(f'{PACKAGE}.models')
classifier = importlib.import_module(f'{PACKAGE}.classifier')
tracker_module = importlib.import_module(f'{PACKAGE}.presence')
A = '02:11:22:33:44:55'
B = '02:22:33:44:55:66'


def snapshot(*names):
    clients = tuple(models.Client(mac, hostname=name) for mac, name in names)
    return models.Snapshot(clients, tuple(classifier.classify(client) for client in clients))


class PresenceTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.tracker = tracker_module.PresenceTracker(120, clock=lambda: self.now)

    def test_startup_does_not_emit_arrivals(self):
        result = self.tracker.update(snapshot((A, 'iPhone')))
        self.assertTrue(result.phone_connected)
        self.assertFalse(result.arrivals)

    def test_new_visitor_arrives_while_another_phone_is_connected(self):
        self.tracker.update(snapshot((A, 'iPhone')))
        result = self.tracker.update(snapshot((A, 'iPhone'), (B, 'android-guest')))
        self.assertTrue(result.phone_connected)
        self.assertEqual([d.client.mac for d in result.arrivals], [B])
        self.assertFalse(self.tracker.update(snapshot((A, 'iPhone'), (B, 'android-guest'))).arrivals)

    def test_each_new_mac_has_its_own_arrival(self):
        self.tracker.update(snapshot())
        result = self.tracker.update(snapshot((A, 'iPhone'), (B, 'iPhone')))
        self.assertEqual(len(result.arrivals), 2)

    def test_nonmatching_devices_do_not_emit_arrivals(self):
        self.tracker.update(snapshot())
        self.assertFalse(self.tracker.update(snapshot((A, 'laptop'))).arrivals)

    def test_departure_waits_from_first_missing_observation(self):
        self.tracker.update(snapshot((A, 'iPhone')))
        self.now = 1000
        result = self.tracker.update(snapshot())
        self.assertTrue(result.phone_connected)
        self.assertFalse(result.phones)
        self.assertEqual(len(result.pending_departures), 1)
        self.now = 1119
        self.assertTrue(self.tracker.update(snapshot()).phone_connected)
        self.now = 1120
        self.assertFalse(self.tracker.update(snapshot()).phone_connected)

    def test_short_dropout_does_not_repeat_arrival(self):
        self.tracker.update(snapshot((A, 'iPhone')))
        self.tracker.update(snapshot())
        self.now = 119
        result = self.tracker.update(snapshot((A, 'iPhone')))
        self.assertFalse(result.arrivals)
        self.assertFalse(result.pending_departures)

    def test_confirmed_departure_then_return_emits_arrival(self):
        self.tracker.update(snapshot((A, 'iPhone')))
        self.tracker.update(snapshot())
        self.now = 120
        self.tracker.update(snapshot())
        self.assertEqual(len(self.tracker.update(snapshot((A, 'iPhone'))).arrivals), 1)

    def test_return_after_grace_without_intermediate_poll_is_an_arrival(self):
        self.tracker.update(snapshot((A, 'iPhone')))
        self.tracker.update(snapshot())
        self.now = 120
        result = self.tracker.update(snapshot((A, 'iPhone')))
        self.assertTrue(result.phone_connected)
        self.assertEqual(len(result.arrivals), 1)

    def test_zero_delay_disables_grace(self):
        tracker = tracker_module.PresenceTracker(0)
        tracker.update(snapshot((A, 'iPhone')))
        self.assertFalse(tracker.update(snapshot()).phone_connected)
        self.assertEqual(len(tracker.update(snapshot((A, 'iPhone'))).arrivals), 1)

    def test_outage_does_not_count_as_confirmed_absence(self):
        self.tracker.update(snapshot((A, 'iPhone')))
        self.tracker.update(snapshot())
        self.now = 10000
        self.tracker.pause()
        self.assertTrue(self.tracker.update(snapshot()).phone_connected)
        self.now = 10120
        self.assertFalse(self.tracker.update(snapshot()).phone_connected)

    def test_recovery_is_a_baseline_not_a_visitor_event(self):
        self.tracker.update(snapshot((A, 'iPhone')))
        self.tracker.pause()
        result = self.tracker.update(snapshot((A, 'iPhone'), (B, 'Galaxy')))
        self.assertTrue(result.phone_connected)
        self.assertFalse(result.arrivals)

    def test_current_names_replace_old_names(self):
        self.tracker.update(snapshot((A, 'iPhone')))
        result = self.tracker.update(snapshot((A, 'Guest-iPhone')))
        self.assertEqual(result.effective_phones[0].client.hostname, 'Guest-iPhone')
        self.assertFalse(result.arrivals)

    def test_each_departure_has_an_independent_timer(self):
        self.tracker.update(snapshot((A, 'iPhone'), (B, 'Galaxy')))
        self.tracker.update(snapshot((B, 'Galaxy')))
        self.now = 100
        self.tracker.update(snapshot())
        self.now = 120
        result = self.tracker.update(snapshot())
        self.assertEqual([d.client.mac for d in result.effective_phones], [B])
        self.now = 220
        self.assertFalse(self.tracker.update(snapshot()).phone_connected)

    def test_sequence_changes_on_every_successful_read(self):
        first = self.tracker.update(snapshot())
        second = self.tracker.update(snapshot())
        self.assertGreater(second.sequence, first.sequence)

    def test_invalid_delay_is_rejected(self):
        for delay in (-1, 1801):
            with self.assertRaises(ValueError):
                tracker_module.PresenceTracker(delay)
