"""Config flow for Homie Proxy integration."""

import logging
import uuid
import ipaddress
from typing import Any, Dict, Optional, List
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_TOKEN,
    CONF_TOKENS,
    CONF_RESTRICT_OUT,
    CONF_RESTRICT_IN,
    DEFAULT_NAME,
    DEFAULT_RESTRICT_OUT,
    RESTRICT_OPTIONS,
    PRIVATE_CIDRS,
    LOCAL_CIDRS,
)

_LOGGER = logging.getLogger(__name__)


def validate_cidr(cidr_string: str) -> bool:
    """Validate CIDR notation."""
    if not cidr_string:
        return True  # Empty is allowed for optional fields
    
    try:
        ipaddress.ip_network(cidr_string, strict=False)
        return True
    except ValueError:
        return False


def generate_token() -> str:
    """Generate a secure token."""
    return str(uuid.uuid4())


def get_endpoint_url(instance_name: str, token: str) -> str:
    """Generate the endpoint URL for the proxy instance."""
    return f"/api/homie_proxy/{instance_name}?token={token}&url={{target_url}}"


def migrate_tokens(data: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate single token to tokens list if needed."""
    if CONF_TOKEN in data and CONF_TOKENS not in data:
        # Migrate old single token format to new multiple tokens format
        tokens = [data[CONF_TOKEN]]
        data = {**data}
        data[CONF_TOKENS] = tokens
        del data[CONF_TOKEN]
    elif CONF_TOKENS not in data:
        # No tokens at all, create empty list
        data = {**data}
        data[CONF_TOKENS] = []
    return data


class HomieProxyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homie Proxy."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self._name: Optional[str] = None
        self._tokens: List[str] = []
        self._restrict_out: Optional[str] = None
        self._restrict_out_custom: Optional[str] = None
        self._restrict_in: Optional[str] = None

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Validate input
            name = user_input.get(CONF_NAME, "").strip()
            if not name:
                errors[CONF_NAME] = "name_required"
            
            # Check for duplicate names
            for entry in self._async_current_entries():
                if entry.data.get(CONF_NAME) == name:
                    errors[CONF_NAME] = "name_exists"
                    break

            # Handle initial token - always generate one to start
            initial_token = generate_token()
            tokens = [initial_token]

            # Validate restrict_out
            restrict_out = user_input.get(CONF_RESTRICT_OUT, DEFAULT_RESTRICT_OUT)
            restrict_out_custom = user_input.get("restrict_out_custom", "").strip()

            if restrict_out == "custom":
                if not restrict_out_custom:
                    errors["restrict_out_custom"] = "custom_cidr_required"
                elif not validate_cidr(restrict_out_custom):
                    errors["restrict_out_custom"] = "invalid_cidr"

            # Validate restrict_in (optional)
            restrict_in = user_input.get(CONF_RESTRICT_IN, "").strip()
            if restrict_in and not validate_cidr(restrict_in):
                errors[CONF_RESTRICT_IN] = "invalid_cidr"

            # If no errors, create entry
            if not errors:
                # Prepare final restrict_out value
                if restrict_out == "custom":
                    final_restrict_out = restrict_out_custom
                else:
                    final_restrict_out = restrict_out

                return self.async_create_entry(
                    title=f"Homie Proxy: {name}",
                    data={
                        CONF_NAME: name,
                        CONF_TOKENS: tokens,
                        CONF_RESTRICT_OUT: final_restrict_out,
                        CONF_RESTRICT_IN: restrict_in if restrict_in else None,
                    },
                )

            # Store values for re-display
            self._name = name
            self._restrict_out = restrict_out
            self._restrict_out_custom = restrict_out_custom
            self._restrict_in = restrict_in

        # Build form schema with improved layout
        schema = vol.Schema({
            vol.Required(CONF_NAME, default=self._name or DEFAULT_NAME): 
                selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT
                    )
                ),
            vol.Required(CONF_RESTRICT_OUT, default=self._restrict_out or DEFAULT_RESTRICT_OUT): 
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[{"value": key, "label": label} for key, label in RESTRICT_OPTIONS],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
            vol.Optional("restrict_out_custom", default=self._restrict_out_custom or ""): 
                selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                        placeholder="e.g., 10.0.0.0/8 or 203.0.113.0/24"
                    )
                ),
            vol.Optional(CONF_RESTRICT_IN, default=self._restrict_in or ""): 
                selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                        placeholder="e.g., 192.168.1.0/24 (optional)"
                    )
                ),
        })

        # Generate sample endpoint URL
        sample_token = generate_token()[:8] + "..."
        sample_name = self._name or DEFAULT_NAME
        sample_endpoint = f"http://localhost:8123/api/homie_proxy/{sample_name}?token={sample_token}&url={{target_url}}"

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "sample_endpoint": sample_endpoint,
                "private_networks": "Includes: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16",
                "local_network": "Includes: 192.168.0.0/16",
            },
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
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Show the main options menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["restrictions", "tokens"],
        )

    async def async_step_restrictions(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage access restrictions."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Validate restrict_out
            restrict_out = user_input.get(CONF_RESTRICT_OUT)
            restrict_out_custom = user_input.get("restrict_out_custom", "").strip()

            if restrict_out == "custom":
                if not restrict_out_custom:
                    errors["restrict_out_custom"] = "custom_cidr_required"
                elif not validate_cidr(restrict_out_custom):
                    errors["restrict_out_custom"] = "invalid_cidr"

            # Validate restrict_in (optional)
            restrict_in = user_input.get(CONF_RESTRICT_IN, "").strip()
            if restrict_in and not validate_cidr(restrict_in):
                errors[CONF_RESTRICT_IN] = "invalid_cidr"

            if not errors:
                # Prepare final restrict_out value
                if restrict_out == "custom":
                    final_restrict_out = restrict_out_custom
                else:
                    final_restrict_out = restrict_out

                # Migrate and update config entry
                data = migrate_tokens(self.config_entry.data)
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **data,
                        CONF_RESTRICT_OUT: final_restrict_out,
                        CONF_RESTRICT_IN: restrict_in if restrict_in else None,
                    },
                )
                return self.async_create_entry(title="", data={})

        # Get current values
        data = migrate_tokens(self.config_entry.data)
        current_restrict_out = data.get(CONF_RESTRICT_OUT, DEFAULT_RESTRICT_OUT)
        current_restrict_in = data.get(CONF_RESTRICT_IN, "")

        # Determine if current restrict_out is custom
        restrict_out_type = current_restrict_out
        restrict_out_custom = ""
        
        known_types = [opt[0] for opt in RESTRICT_OPTIONS if opt[0] != "custom"]
        if current_restrict_out not in known_types:
            restrict_out_type = "custom"
            restrict_out_custom = current_restrict_out

        # Build schema
        schema = vol.Schema({
            vol.Required(CONF_RESTRICT_OUT, default=restrict_out_type): 
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[{"value": key, "label": label} for key, label in RESTRICT_OPTIONS],
                        mode=selector.SelectSelectorMode.DROPDOWN
                    )
                ),
            vol.Optional("restrict_out_custom", default=restrict_out_custom): 
                selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                        placeholder="e.g., 10.0.0.0/8 or 203.0.113.0/24"
                    )
                ),
            vol.Optional(CONF_RESTRICT_IN, default=current_restrict_in): 
                selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.TEXT,
                        placeholder="e.g., 192.168.1.0/24 (optional)"
                    )
                ),
        })

        return self.async_show_form(
            step_id="restrictions",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "current_name": data.get(CONF_NAME),
                "private_networks": "Includes: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16",
                "local_network": "Includes: 192.168.0.0/16",
            },
        )

    async def async_step_tokens(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage access tokens."""
        if user_input is not None:
            action = user_input.get("action")
            if action == "add":
                return await self.async_step_add_token()
            elif action == "remove":
                return await self.async_step_remove_token()

        # Get current tokens
        data = migrate_tokens(self.config_entry.data)
        tokens = data.get(CONF_TOKENS, [])
        instance_name = data.get(CONF_NAME, "unknown")

        # Generate endpoint URLs for each token
        endpoint_info = []
        for i, token in enumerate(tokens, 1):
            endpoint_url = f"http://localhost:8123/api/homie_proxy/{instance_name}?token={token}&url={{target_url}}"
            endpoint_info.append(f"**Token {i}:** `{token[:8]}...{token[-4:]}`")
            endpoint_info.append(f"**Endpoint:** `{endpoint_url}`")
            endpoint_info.append("")

        endpoint_text = "\n".join(endpoint_info) if endpoint_info else "No tokens configured."

        schema = vol.Schema({
            vol.Required("action"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": "add", "label": "🔑 Add New Token"},
                        {"value": "remove", "label": "🗑️ Remove Token"},
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
        })

        return self.async_show_form(
            step_id="tokens",
            data_schema=schema,
            description_placeholders={
                "current_tokens": endpoint_text,
                "token_count": str(len(tokens)),
            },
        )

    async def async_step_add_token(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Add a new access token."""
        if user_input is not None:
            # Generate new token and add to list
            data = migrate_tokens(self.config_entry.data)
            tokens = data.get(CONF_TOKENS, [])
            new_token = generate_token()
            tokens.append(new_token)

            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **data,
                    CONF_TOKENS: tokens,
                },
            )
            return self.async_create_entry(title="", data={})

        instance_name = self.config_entry.data.get(CONF_NAME, "unknown")
        new_token = generate_token()
        new_endpoint = f"http://localhost:8123/api/homie_proxy/{instance_name}?token={new_token}&url={{target_url}}"

        schema = vol.Schema({
            vol.Required("confirm", default=True): bool,
        })

        return self.async_show_form(
            step_id="add_token",
            data_schema=schema,
            description_placeholders={
                "new_token": new_token,
                "new_endpoint": new_endpoint,
            },
        )

    async def async_step_remove_token(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Remove an access token."""
        data = migrate_tokens(self.config_entry.data)
        tokens = data.get(CONF_TOKENS, [])

        if not tokens:
            return self.async_abort(reason="no_tokens")

        if user_input is not None:
            token_to_remove = user_input.get("token_to_remove")
            if token_to_remove and token_to_remove in tokens:
                tokens.remove(token_to_remove)
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data={
                        **data,
                        CONF_TOKENS: tokens,
                    },
                )
            return self.async_create_entry(title="", data={})

        # Create options for token selection
        token_options = []
        for token in tokens:
            label = f"{token[:8]}...{token[-4:]} (Created: {token[:8]})"
            token_options.append({"value": token, "label": label})

        schema = vol.Schema({
            vol.Required("token_to_remove"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=token_options,
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            ),
        })

        return self.async_show_form(
            step_id="remove_token",
            data_schema=schema,
            description_placeholders={
                "token_count": str(len(tokens)),
            },
        )


class InvalidCIDR(HomeAssistantError):
    """Error to indicate an invalid CIDR.""" 