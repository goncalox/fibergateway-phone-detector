"""Test router actions and optional phone detection in actual HA, without a router."""
import asyncio
import importlib
import json
import logging
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant import loader
from homeassistant.auth import AuthManager, auth_manager_from_config
from homeassistant.bootstrap import async_load_base_functionality
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError, Unauthorized
from homeassistant.helpers import entity_registry, service
import voluptuous as vol

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "wifi_phone_detector"
logging.basicConfig(level=logging.WARNING)


async def main():
    checks = []
    with tempfile.TemporaryDirectory(prefix="ha-control-") as directory:
        shutil.copytree(ROOT / "custom_components", Path(directory) / "custom_components",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        hass = HomeAssistant(directory)
        hass.config_entries = ConfigEntries(hass, {})
        loader.async_setup(hass)
        await async_load_base_functionality(hass)
        hass.auth = await auth_manager_from_config(hass, [], [])
        integration = await loader.async_get_integration(hass, DOMAIN)
        await integration.async_get_component()
        router_module = importlib.import_module(f"custom_components.{DOMAIN}.router")
        models = importlib.import_module(f"custom_components.{DOMAIN}.models")
        commands = importlib.import_module(f"custom_components.{DOMAIN}.commands")
        rule = commands.restriction("Weekday-Night", "02:11:22:33:44:55",
                                    ["Mon", "Tue", "Wed", "Thu", "Fri"], "00:00", "05:00")
        dhcp_available = False
        clients = (models.Client(rule.mac, "192.0.2.10", "Visitor-iPhone"),)
        writes = []
        events = []
        hass.bus.async_listen("wifi_phone_detector_phone_arrived", events.append)

        async def fetch(router):
            router.dhcp_available = dhcp_available
            return clients

        async def execute(router, command):
            writes.append((router.host, command))
            return "simulated response"

        async def create(router, requested):
            writes.append((router.host, requested))
            return {"created": True, "rule": requested.as_dict()}

        async def remove(router, name):
            writes.append((router.host, name))
            return {"removed": True, "name": name}

        async def get_rules(router):
            return (rule,)

        async def action(name, data=None, context=None):
            return await hass.services.async_call(DOMAIN, name, data or {}, blocking=True,
                                                  return_response=True, context=context)

        async def setup(host):
            form = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
            form = await hass.config_entries.flow.async_configure(form["flow_id"], {
                "host": host, "port": 23, "username": "test-user", "password": "fake-password"})
            result = await hass.config_entries.flow.async_configure(form["flow_id"], {
                "phone_detection": False, "phone_name_keywords": "", "scan_interval": 45,
                "departure_delay": 0})
            assert result["type"] == "create_entry", result
            await hass.async_block_till_done()
            return result["result"]

        async def rejected(name, data, exception=ServiceValidationError, context=None):
            before = len(writes)
            try:
                await action(name, data, context)
            except exception:
                pass
            else:
                raise AssertionError(f"{name} unexpectedly succeeded")
            assert len(writes) == before, writes

        try:
            with patch.object(router_module.RouterClient, "async_fetch", fetch), \
                 patch.object(router_module.RouterClient, "async_execute", execute), \
                 patch.object(router_module.RouterClient, "async_create_time_restriction", create), \
                 patch.object(router_module.RouterClient, "async_remove_time_restriction", remove), \
                 patch.object(router_module.RouterClient, "async_get_time_restrictions", get_rules):
                entry = await setup("192.0.2.1")
                assert not entry.options["phone_detection"]
                presence = hass.states.async_all("binary_sensor")[0]
                assert presence.state == "unavailable"
                inventory = next(s for s in hass.states.async_all("sensor") if s.entity_id.endswith("connected_devices"))
                assert inventory.state == "1"
                assert not inventory.attributes["devices"][0]["is_phone"]
                assert not events
                checks.append("router setup and inventory work without phone keywords or DHCP names")

                descriptions = (await service.async_get_all_descriptions(hass))[DOMAIN]
                assert set(descriptions) == {"execute_command", "create_time_restriction",
                    "remove_time_restriction", "get_time_restrictions", "get_router_info", "refresh_devices"}
                assert descriptions["create_time_restriction"]["fields"]["days"]["selector"]["select"]["multiple"]
                assert descriptions["execute_command"]["fields"]["config_entry_id"]["selector"]["config_entry"]["integration"] == DOMAIN
                assert all("password" not in item["fields"] for item in descriptions.values())
                checks.append("all six actions expose translated fields and valid HA selectors")

                assert await action("execute_command", {"command": "tree"}) == {"output": "simulated response"}
                assert writes[-1] == (entry.data["host"], "tree")
                assert await action("get_router_info") == {"output": "simulated response"}
                assert writes[-1][1] == "/device-info/show"
                assert await action("get_time_restrictions") == {"rules": [rule.as_dict()]}
                assert await action("refresh_devices") == {"device_count": 1}
                checks.append("read actions reuse configured router and return automation responses")

                data = {**rule.as_dict(), "start_time": "00:00:00", "end_time": "05:00:00"}
                assert (await action("create_time_restriction", data))["created"]
                assert writes[-1] == (entry.data["host"], rule)
                assert (await action("remove_time_restriction", {"name": rule.name}))["removed"]
                checks.append("native schedule actions normalize UI times and return verified-operation data")

                for overrides in ({"mac": "ff:ff:ff:ff:ff:ff"}, {"days": ["Monday"]},
                                  {"end_time": "00:00"}, {"name": "Night --other=bad"},
                                  {"start_time": "25:00"}):
                    await rejected("create_time_restriction", {**data, **overrides})
                await rejected("execute_command", {"command": "tree\nquit"}, vol.Invalid)
                await rejected("remove_time_restriction", {"name": "Night\nquit"}, vol.Invalid)
                checks.append("invalid schedule values and multiline commands never reach router")

                with patch.object(AuthManager, "async_get_user", AsyncMock(return_value=SimpleNamespace(is_admin=False))):
                    await rejected("execute_command", {"command": "tree"}, Unauthorized, Context(user_id="non-admin"))
                with patch.object(AuthManager, "async_get_user", AsyncMock(return_value=None)):
                    await rejected("get_router_info", {}, Unauthorized, Context(user_id="missing-user"))
                with patch.object(AuthManager, "async_get_user", AsyncMock(return_value=SimpleNamespace(is_admin=True))):
                    await action("get_router_info", context=Context(user_id="admin"))
                checks.append("administrator actions allowed; non-admin and unknown users denied")

                with patch.object(router_module.RouterClient, "async_execute", AsyncMock(side_effect=router_module.AuthenticationError("denied"))):
                    await rejected("get_router_info", {}, HomeAssistantError)
                checks.append("router authentication failures surface as Home Assistant action errors")

                ids = {e.unique_id: e.entity_id for e in entity_registry.async_get(hass).entities.values()}
                hass.config_entries.async_update_entry(entry, title="FiberGateway Phone Detector")
                dhcp_available = True
                options = await hass.config_entries.options.async_init(entry.entry_id)
                await hass.config_entries.options.async_configure(options["flow_id"], {
                    "phone_detection": True, "phone_name_keywords": "iphone", "scan_interval": 30,
                    "departure_delay": 0})
                await hass.async_block_till_done()
                assert hass.states.get(presence.entity_id).state == "on"
                assert entry.title == "FiberGateway"
                assert {e.unique_id: e.entity_id for e in entity_registry.async_get(hass).entities.values()} == ids
                assert not events
                checks.append("enable phone feature preserves entity IDs, migrates old title and starts without arrival")

                # Legacy entries have no feature flag and must retain phone detection.
                legacy_options = {k: v for k, v in entry.options.items() if k != "phone_detection"}
                hass.config_entries.async_update_entry(entry, options=legacy_options, title="My router")
                await hass.async_block_till_done()
                assert hass.states.get(presence.entity_id).state == "on"
                assert entry.title == "My router"
                checks.append("legacy options keep phone matching enabled and custom entry titles survive")

                second = await setup("192.0.2.2")
                await rejected("get_router_info", {})
                await rejected("get_router_info", {"config_entry_id": "missing-entry"})
                await action("execute_command", {"config_entry_id": second.entry_id, "command": "tree"})
                assert writes[-1] == ("192.0.2.2", "tree")
                await action("execute_command", {"config_entry_id": entry.entry_id, "command": "tree"})
                assert writes[-1] == ("192.0.2.1", "tree")
                checks.append("multiple routers require selection and commands reach only the chosen router")

                assert await hass.config_entries.async_unload(entry.entry_id)
                assert await hass.config_entries.async_unload(second.entry_id)
                await hass.async_block_till_done()
                assert hass.services.has_service(DOMAIN, "execute_command")
                await rejected("get_router_info", {})
                checks.append("actions remain registered after unload but cannot use unloaded routers")
                print(json.dumps({"home_assistant_version": "2025.3.0", "router": "simulated",
                                  "checks": checks}, indent=2))
        finally:
            await hass.async_stop(force=True)


asyncio.run(main())
