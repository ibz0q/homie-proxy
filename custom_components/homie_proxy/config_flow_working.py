"""Minimal config flow for testing."""

import logging
import uuid
from typing import Any, Dict, Optional
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_NAME, DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)


class HomieProxyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homie Proxy."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            name = user_input.get(CONF_NAME, "").strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            
            if not errors:
                return self.async_create_entry(
                    title=f"Homie Proxy: {name}",
                    data={
                        CONF_NAME: name,
                    },
                )

        schema = vol.Schema({
            vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return HomieProxyOptionsFlowHandler(config_entry)


class HomieProxyOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Homie Proxy."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Show basic options."""
        return self.async_create_entry(title="", data={}) 