"""Home Assistant actions for a configured FiberGateway router."""
try:
    import probatio as vol
except ImportError:
    import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError, Unauthorized

from .commands import restriction, rule_name, validate_command
from .const import DOMAIN
from .parser import ParseError
from .router import AuthenticationError, RouterError


def schema_validator(validator):
    """Present command validation failures through Home Assistant's form errors."""
    def validate(value):
        try:
            return validator(value)
        except ValueError as error:
            raise vol.Invalid(str(error)) from error
    return validate


def async_register_services(hass):
    """Register once during integration setup, including while entries are unloaded."""
    base = {vol.Optional("config_entry_id"): str}
    schemas = {
        "execute_command": {vol.Required("command"): schema_validator(validate_command)},
        "create_time_restriction": {
            vol.Required("name"): str, vol.Required("mac"): str,
            vol.Required("days"): [str], vol.Required("start_time"): str,
            vol.Required("end_time"): str,
        },
        "remove_time_restriction": {vol.Required("name"): schema_validator(rule_name)},
        "get_time_restrictions": {}, "get_router_info": {}, "refresh_devices": {},
    }

    async def handle(call):
        # Router credentials belong to the administrator; automations have no user context.
        if call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None or not user.is_admin:
                raise Unauthorized(context=call.context)
        entry_id = call.data.get("config_entry_id")
        entries = [entry for entry in hass.config_entries.async_entries(DOMAIN)
                   if entry.state is ConfigEntryState.LOADED and (entry_id is None or entry.entry_id == entry_id)]
        if len(entries) != 1:
            raise ServiceValidationError("Select one loaded FiberGateway router")
        coordinator = entries[0].runtime_data
        router = coordinator.router
        try:
            if call.service == "execute_command":
                return {"output": await router.async_execute(call.data["command"])}
            if call.service == "create_time_restriction":
                rule = restriction(*(call.data[key] for key in ("name", "mac", "days", "start_time", "end_time")))
                return await router.async_create_time_restriction(rule)
            if call.service == "remove_time_restriction":
                return await router.async_remove_time_restriction(call.data["name"])
            if call.service == "get_time_restrictions":
                return {"rules": [rule.as_dict() for rule in await router.async_get_time_restrictions()]}
            if call.service == "get_router_info":
                return {"output": await router.async_execute("/device-info/show")}
            await coordinator.async_request_refresh()
            if not coordinator.last_update_success:
                raise HomeAssistantError("Router device inventory is unavailable")
            return {"device_count": len(coordinator.data.clients)}
        except AuthenticationError as error:
            raise HomeAssistantError("Router rejected credentials; update the integration's login") from error
        except (ValueError, ParseError) as error:
            raise ServiceValidationError(str(error)) from error
        except RouterError as error:
            raise HomeAssistantError(str(error)) from error

    for name, fields in schemas.items():
        hass.services.async_register(DOMAIN, name, handle, schema=vol.Schema({**base, **fields}),
                                     supports_response=SupportsResponse.OPTIONAL)
