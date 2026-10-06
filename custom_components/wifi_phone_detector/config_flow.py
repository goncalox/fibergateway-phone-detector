"""UI setup, credential replacement and detection settings."""

try:
    import probatio as vol
except ImportError:
    import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_INTERVAL, CONF_NAMES, DEFAULT_NAMES, CONF_DEPARTURE_DELAY, DEFAULT_DEPARTURE_DELAY,
    DEFAULT_INTERVAL, DEFAULT_PORT, DOMAIN, NAME,
)
from .parser import ParseError
from .classifier import parse_name_keywords
from .router import AuthenticationError, RouterClient, RouterError


def connection_schema(defaults=None):
    """Never prefill stored passwords into form responses."""
    defaults = defaults or {}
    return vol.Schema({
        vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "192.168.1.254")): str,
        vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        vol.Required(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
        vol.Required(CONF_PASSWORD): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
    })


async def validate_connection(data):
    """Validate authentication and association parsing on both radio indexes."""
    try:
        client = RouterClient(data[CONF_HOST], data[CONF_USERNAME], data[CONF_PASSWORD], data[CONF_PORT])
        await client.async_fetch()
        if not client.dhcp_available:
            return "cannot_read_names"
    except AuthenticationError:
        return "invalid_auth"
    except RouterError:
        return "cannot_connect"
    except ParseError:
        return "unsupported_response"
    except ValueError:
        return "invalid_input"
    return None


class PhoneConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure one router per entry."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            user_input = {**user_input, CONF_HOST: user_input[CONF_HOST].strip().lower()}
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]})
            if error := await validate_connection(user_input):
                errors["base"] = error
            else:
                self._connection_data = user_input
                return await self.async_step_names()
        return self.async_show_form(step_id="user", data_schema=connection_schema(user_input), errors=errors)

    async def async_step_names(self, user_input=None):
        """Configure name keywords during setup."""
        errors = {}
        if user_input is not None:
            try:
                options = detection_options(user_input)
            except ValueError:
                errors["base"] = "invalid_names"
            else:
                return self.async_create_entry(title=NAME, data=self._connection_data, options=options)
        return self.async_show_form(step_id="names", data_schema=detection_schema(user_input), errors=errors)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        entry = self._get_reauth_entry()
        errors = {}
        if user_input is not None:
            data = {**entry.data, **user_input}
            if error := await validate_connection(data):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(
            step_id="reauth_confirm", errors=errors,
            data_schema=vol.Schema({
                vol.Required(CONF_USERNAME, default=entry.data[CONF_USERNAME]): str,
                vol.Required(CONF_PASSWORD): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            }),
        )

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            user_input = {**user_input, CONF_HOST: user_input[CONF_HOST].strip().lower()}
            if any(other.entry_id != entry.entry_id and
                   other.data.get(CONF_HOST) == user_input[CONF_HOST] and
                   other.data.get(CONF_PORT) == user_input[CONF_PORT]
                   for other in self._async_current_entries()):
                return self.async_abort(reason="already_configured")
            if error := await validate_connection(user_input):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input, reason="reconfigure_successful")
        return self.async_show_form(step_id="reconfigure", data_schema=connection_schema(entry.data), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PhoneOptionsFlow()


def detection_schema(defaults=None):
    """One comma- or newline-separated keyword list and a polling interval."""
    defaults = defaults or {}
    return vol.Schema({
        vol.Required(CONF_NAMES, default=defaults.get(CONF_NAMES, DEFAULT_NAMES)):
            selector.TextSelector(selector.TextSelectorConfig(multiline=True)),
        vol.Required(CONF_INTERVAL, default=defaults.get(CONF_INTERVAL, DEFAULT_INTERVAL)):
            vol.All(vol.Coerce(int), vol.Range(min=15, max=300)),
        vol.Required(CONF_DEPARTURE_DELAY, default=defaults.get(CONF_DEPARTURE_DELAY, DEFAULT_DEPARTURE_DELAY)):
            vol.All(vol.Coerce(int), vol.Range(min=0, max=1800)),
    })


def detection_options(user_input):
    keywords = parse_name_keywords(user_input[CONF_NAMES])
    return {CONF_NAMES: ", ".join(keywords), CONF_INTERVAL: user_input[CONF_INTERVAL],
            CONF_DEPARTURE_DELAY: user_input.get(CONF_DEPARTURE_DELAY, DEFAULT_DEPARTURE_DELAY)}


class PhoneOptionsFlow(config_entries.OptionsFlow):
    """Edit name keywords without changing router credentials."""
    async def async_step_init(self, user_input=None):
        errors = {}
        defaults = self.config_entry.options
        if user_input is not None:
            try:
                options = detection_options(user_input)
            except ValueError:
                errors["base"] = "invalid_names"
                defaults = user_input
            else:
                return self.async_create_entry(title="", data=options)
        return self.async_show_form(step_id="init", errors=errors, data_schema=detection_schema(defaults))
