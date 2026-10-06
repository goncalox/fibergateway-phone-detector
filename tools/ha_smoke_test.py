"""Exercise actual HA flows and entities with simulated router responses."""
import asyncio
import importlib
import json
import logging
from pathlib import Path
import shutil
import tempfile
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntries
from homeassistant import loader
from homeassistant.bootstrap import async_load_base_functionality

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = 'wifi_phone_detector'
logging.basicConfig(level=logging.WARNING)


async def main():
    checks = []
    with tempfile.TemporaryDirectory(prefix='ha-smoke-') as directory:
        shutil.copytree(ROOT / 'custom_components', Path(directory) / 'custom_components', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        hass = HomeAssistant(directory)
        hass.config_entries = ConfigEntries(hass, {})
        loader.async_setup(hass)
        await async_load_base_functionality(hass)
        integration = await loader.async_get_integration(hass, DOMAIN)
        await integration.async_get_component()
        router_module = importlib.import_module(f'custom_components.{DOMAIN}.router')
        models = importlib.import_module(f'custom_components.{DOMAIN}.models')
        clients = [models.Client('02:11:22:33:44:55', '192.0.2.10', 'Guest-iPhone')]
        available = True
        events = []
        hass.bus.async_listen('wifi_phone_detector_phone_arrived', events.append)

        async def fetch(router):
            router.dhcp_available = available
            return tuple(clients)

        try:
            with patch.object(router_module.RouterClient, 'async_fetch', fetch):
                form = await hass.config_entries.flow.async_init(DOMAIN, context={'source': 'user'})
                assert form['step_id'] == 'user', form
                form = await hass.config_entries.flow.async_configure(form['flow_id'], {'host': '192.0.2.1', 'port': 23, 'username': 'test-user', 'password': 'fake-password'})
                assert form['step_id'] == 'names', form
                invalid = await hass.config_entries.flow.async_configure(form['flow_id'], {'phone_name_keywords': '', 'scan_interval': 45})
                assert invalid['errors'] == {'base': 'invalid_names'}, invalid
                result = await hass.config_entries.flow.async_configure(form['flow_id'], {'phone_name_keywords': 'iPhone, ANDROID', 'scan_interval': 45, 'departure_delay': 0})
                assert result['type'] == 'create_entry', result
                entry = result['result']
                assert entry.options['phone_name_keywords'] == 'iphone, android'
                await hass.async_block_till_done()
                checks.append('setup and invalid keyword validation')

                sensors = hass.states.async_all('binary_sensor')
                assert len(sensors) == 1, [(s.entity_id, s.state) for s in hass.states.async_all()]
                entity_id = sensors[0].entity_id
                assert sensors[0].state == 'on', sensors[0]
                assert sensors[0].attributes['matched_names'] == ['Guest-iPhone']
                assert sensors[0].attributes['phone_count'] == 1
                assert not events
                event_entity = hass.states.async_all('event')[0].entity_id
                checks.append('presence entity on, matching attributes and no startup arrival')

                clients[:] = [models.Client('02:22:33:44:55:66', hostname='laptop')]
                await entry.runtime_data.async_refresh()
                await hass.async_block_till_done()
                assert hass.states.get(entity_id).state == 'off'
                checks.append('departure turns presence off')

                available = False
                await entry.runtime_data.async_refresh()
                await hass.async_block_till_done()
                assert hass.states.get(entity_id).state == 'unavailable'
                checks.append('missing DHCP names makes entity unavailable')
                available = True
                clients[:] = [models.Client('02:11:22:33:44:55', hostname='iPhone')]
                await entry.runtime_data.async_refresh()
                await hass.async_block_till_done()
                assert hass.states.get(entity_id).state == 'on'
                checks.append('recovery restores presence')

                options = await hass.config_entries.options.async_init(entry.entry_id)
                assert options['step_id'] == 'init'
                updated = await hass.config_entries.options.async_configure(options['flow_id'], {'phone_name_keywords': 'Pixel', 'scan_interval': 30, 'departure_delay': 120})
                assert updated['type'] == 'create_entry', updated
                await hass.async_block_till_done()
                assert entry.options['phone_name_keywords'] == 'pixel'
                assert entry.runtime_data.update_interval.total_seconds() == 30
                assert hass.states.get(entity_id).state == 'off'
                checks.append('options reload changes keywords and polling interval')

                clients[:] = [models.Client('02:33:44:55:66:77', hostname='Visitor-PIXEL')]
                await entry.runtime_data.async_refresh()
                await hass.async_block_till_done()
                assert hass.states.get(entity_id).state == 'on'
                assert len(events) == 1
                assert events[0].data['name'] == 'Visitor-PIXEL'
                assert hass.states.get(event_entity).attributes['event_type'] == 'phone_arrived'
                checks.append('new visitor matches edited keywords and emits arrival')

                clients.append(models.Client('02:44:55:66:77:88', hostname='Another-Pixel'))
                await entry.runtime_data.async_refresh()
                await hass.async_block_till_done()
                assert hass.states.get(entity_id).state == 'on'
                assert len(events) == 2
                assert events[-1].data['name'] == 'Another-Pixel'
                assert hass.states.get(event_entity).attributes['names'] == ['Another-Pixel']
                device_list = next(s for s in hass.states.async_all('sensor') if s.entity_id.endswith('connected_devices'))
                assert device_list.state == '2'
                assert len(device_list.attributes['devices']) == 2
                assert all(d['matched_keywords'] == ['pixel'] for d in device_list.attributes['devices'])
                assert hass.states.get(entity_id).attributes['phone_count'] == 2
                checks.append('arrival while presence remains on and live device list')

                last_event_timestamp = hass.states.get(event_entity).state
                await entry.runtime_data.async_refresh()
                await hass.async_block_till_done()
                assert len(events) == 2
                assert hass.states.get(event_entity).state == last_event_timestamp
                checks.append('unchanged polls do not repeat arrival events')

                clock = [0]
                entry.runtime_data.tracker.clock = lambda: clock[0]
                clients[:] = [models.Client('02:55:66:77:88:99', hostname='Laptop')]
                await entry.runtime_data.async_refresh()
                await hass.async_block_till_done()
                assert hass.states.get(entity_id).state == 'on'
                assert len(hass.states.get(entity_id).attributes['pending_departure_names']) == 2
                device_list = hass.states.get(device_list.entity_id)
                assert device_list.state == '1'
                assert device_list.attributes['devices'][0]['is_phone'] is False
                clock[0] = 119
                await entry.runtime_data.async_refresh()
                await hass.async_block_till_done()
                assert hass.states.get(entity_id).state == 'on'
                clock[0] = 120
                await entry.runtime_data.async_refresh()
                await hass.async_block_till_done()
                assert hass.states.get(entity_id).state == 'off'
                checks.append('configurable grace period and current inventory during pending departure')

                clients[:] = [models.Client('02:33:44:55:66:77', hostname='Visitor-Pixel')]
                await entry.runtime_data.async_refresh()
                await hass.async_block_till_done()
                assert len(events) == 3
                assert hass.states.get(entity_id).state == 'on'
                checks.append('confirmed departure then return emits a new arrival')

                available = False
                await entry.runtime_data.async_refresh()
                await hass.async_block_till_done()
                assert hass.states.get(entity_id).state == 'unavailable'
                available = True
                clients.append(models.Client('02:66:77:88:99:aa', hostname='Pixel-guest'))
                await entry.runtime_data.async_refresh()
                await hass.async_block_till_done()
                assert hass.states.get(entity_id).state == 'on'
                assert len(events) == 3
                checks.append('outage recovery does not create false visitor arrivals')
                assert await hass.config_entries.async_unload(entry.entry_id)
                await hass.async_block_till_done()
                assert hass.states.get(entity_id).state == 'unavailable', hass.states.get(entity_id)
                checks.append('integration unload marks registered entities unavailable')
                print(json.dumps({'home_assistant_version': '2025.3.0', 'router': 'simulated', 'entity_id': entity_id, 'checks': checks}, indent=2))
        finally:
            await hass.async_stop(force=True)

asyncio.run(main())
