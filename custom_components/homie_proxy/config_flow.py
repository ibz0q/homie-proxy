"""Config flow for HomieProxy integration."""
from __future__ import annotations

import logging
import uuid
import ipaddress
from typing import Any

import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode

from .const import DOMAIN, RESTRICT_OPTIONS

_LOGGER = logging.getLogger(__name__)

# Schema with proper dropdown selector
DATA_SCHEMA = vol.Schema({
    vol.Required("name", default="external-api-route"): str,
    vol.Required("restrict_out", default="any"): SelectSelector(
        SelectSelectorConfig(
            options=[
                {"value": key, "label": label} 
                for key, label in RESTRICT_OPTIONS
            ],
            mode=SelectSelectorMode.DROPDOWN
        )
    ),
    vol.Optional("restrict_out_cidrs", default=""): str,
    vol.Optional("restrict_in_cidrs", default=""): str,
})


def generate_token() -> str:
    """Generate a secure token."""
    return str(uuid.uuid4())


def validate_cidr(cidr_string: str) -> bool:
    """Validate CIDR notation."""
    if not cidr_string:
        return True
    try:
        ipaddress.ip_network(cidr_string, strict=False)
        return True
    except ValueError:
        return False


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    name = data["name"].strip()
    
    if not name:
        raise InvalidName
    
    if len(name) < 2:
        raise InvalidName
    
    # Check if name already exists
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get("name") == name:
            raise AlreadyConfigured
    
    # Validate outbound restrictions
    restrict_out = data.get("restrict_out", "any")
    restrict_out_cidrs = data.get("restrict_out_cidrs", "").strip()
    
    if restrict_out == "custom":
        if not restrict_out_cidrs:
            raise InvalidCIDR
        if not validate_cidr(restrict_out_cidrs):
            raise InvalidCIDR
    
    # Validate inbound restrictions (optional)
    restrict_in_cidrs = data.get("restrict_in_cidrs", "").strip()
    if restrict_in_cidrs and not validate_cidr(restrict_in_cidrs):
        raise InvalidCIDR
    
    return {"title": f"HomieProxy - {name}"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HomieProxy."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                
                # Prepare final restrict_out value
                restrict_out = user_input.get("restrict_out", "any")
                if restrict_out == "custom":
                    final_restrict_out = user_input.get("restrict_out_cidrs", "").strip()
                else:
                    final_restrict_out = restrict_out
                
                # Prepare inbound restriction
                restrict_in_cidrs = user_input.get("restrict_in_cidrs", "").strip()
                
                # Create initial token
                initial_token = generate_token()
                
                return self.async_create_entry(
                    title=info["title"], 
                    data={
                        "name": user_input["name"],
                        "tokens": [initial_token],
                        "restrict_out": final_restrict_out,
                        "restrict_in": restrict_in_cidrs if restrict_in_cidrs else None,
                    }
                )
            except AlreadyConfigured:
                errors["base"] = "already_configured"
            except InvalidName:
                errors["name"] = "invalid_name"
            except InvalidCIDR:
                errors["base"] = "invalid_cidr"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidName(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid name."""


class InvalidCIDR(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid CIDR."""


class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate device is already configured.""" 