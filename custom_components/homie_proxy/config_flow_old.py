"""Config flow for Homie Proxy integration."""

import logging
import uuid
import ipaddress
from typing import Any, Dict, Optional, List
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import selector
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
        if user_input is not None:
            # Generate an initial token for the new instance
            initial_token = generate_token()
            
            return self.async_create_entry(
                title=f"Homie Proxy - {user_input[CONF_NAME]}",
                data={
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_TOKENS: [initial_token],
                    CONF_RESTRICT_OUT: DEFAULT_RESTRICT_OUT,
                    CONF_RESTRICT_IN: None,
                },
            )

        data_schema = vol.Schema({
            vol.Required(CONF_NAME, default=DEFAULT_NAME): selector({
                "text": {}
            })
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
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
        # Don't set self.config_entry - this is deprecated and causes 400 errors
        # Use self.config_entry property instead which is provided by the base class
        pass

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Show the main options menu with current tokens."""
        if user_input is not None:
            menu_choice = user_input.get("menu_choice")
            if menu_choice == "restrictions":
                return await self.async_step_restrictions()
            elif menu_choice == "tokens":
                return await self.async_step_tokens()

        # Get current tokens and instance info safely
        try:
            current_data = dict(self.config_entry.data)
            tokens = current_data.get(CONF_TOKENS, [])
            instance_name = current_data.get(CONF_NAME, "unknown")
            restrict_out = current_data.get(CONF_RESTRICT_OUT, DEFAULT_RESTRICT_OUT)
            restrict_in = current_data.get(CONF_RESTRICT_IN)
        except Exception:
            tokens = []
            instance_name = "unknown"
            restrict_out = DEFAULT_RESTRICT_OUT
            restrict_in = None

        # Generate current configuration summary
        config_summary = []
        config_summary.append(f"**Endpoint Name:** `{instance_name}`")
        config_summary.append(f"**Outbound Access:** {restrict_out}")
        if restrict_in:
            config_summary.append(f"**Inbound Restriction:** {restrict_in}")
        else:
            config_summary.append(f"**Inbound Restriction:** No restrictions")
        config_summary.append("")

        # Generate token info for display
        if tokens:
            config_summary.append(f"**Active Tokens ({len(tokens)}):**")
            for i, token in enumerate(tokens, 1):
                # Show more of the token for better identification
                masked_token = f"{token[:12]}...{token[-8:]}"
                endpoint_url = f"/api/homie_proxy/{instance_name}?token={token}&url={{target_url}}"
                
                config_summary.append(f"• **Token {i}:** `{masked_token}`")
                config_summary.append(f"  **Endpoint:** `{endpoint_url}`")
                config_summary.append("")
        else:
            config_summary.append("**Active Tokens:** None configured")
            config_summary.append("")
        
        config_summary.append("Choose what you want to configure:")

        data_schema = vol.Schema({
            vol.Required("menu_choice"): selector({
                "select": {
                    "options": [
                        {"value": "restrictions", "label": "🌐 Access Restrictions"},
                        {"value": "tokens", "label": "🔑 Manage Tokens"},
                    ],
                    "mode": "dropdown"
                }
            }),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            description_placeholders={
                "config_summary": "\n".join(config_summary),
            },
        )

    async def async_step_restrictions(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Configure access restrictions."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            restrict_out = user_input.get(CONF_RESTRICT_OUT)
            restrict_out_custom = user_input.get("restrict_out_custom", "").strip()

            # Validate restrict_out_custom if custom is selected
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

                # Get current data and update
                try:
                    current_data = dict(self.config_entry.data)
                    current_data.update({
                        CONF_RESTRICT_OUT: final_restrict_out,
                        CONF_RESTRICT_IN: restrict_in if restrict_in else None,
                    })
                    
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data=current_data,
                    )
                    return self.async_create_entry(title="", data={})
                except Exception as e:
                    _LOGGER.error("Error updating restrictions: %s", e)
                    errors["base"] = "unknown"

        # Get current values safely
        try:
            current_data = dict(self.config_entry.data)
            current_restrict_out = current_data.get(CONF_RESTRICT_OUT, DEFAULT_RESTRICT_OUT)
            current_restrict_in = current_data.get(CONF_RESTRICT_IN, "")
        except Exception:
            current_restrict_out = DEFAULT_RESTRICT_OUT
            current_restrict_in = ""

        # Determine if current restrict_out is custom
        restrict_out_type = current_restrict_out
        restrict_out_custom = ""
        
        known_types = [opt[0] for opt in RESTRICT_OPTIONS if opt[0] != "custom"]
        if current_restrict_out not in known_types:
            restrict_out_type = "custom"
            restrict_out_custom = current_restrict_out

        # Build schema with correct selector syntax
        data_schema = {
            vol.Required(CONF_RESTRICT_OUT, default=restrict_out_type): selector({
                "select": {
                    "options": [{"value": key, "label": label} for key, label in RESTRICT_OPTIONS],
                    "mode": "dropdown"
                }
            }),
            vol.Optional("restrict_out_custom", default=restrict_out_custom): selector({
                "text": {
                    "placeholder": "e.g., 10.0.0.0/8 or 203.0.113.0/24"
                }
            }),
            vol.Optional(CONF_RESTRICT_IN, default=current_restrict_in): selector({
                "text": {
                    "placeholder": "e.g., 192.168.1.0/24 (optional)"
                }
            }),
        }

        return self.async_show_form(
            step_id="restrictions",
            data_schema=vol.Schema(data_schema),
            errors=errors,
            description_placeholders={
                "current_name": current_data.get(CONF_NAME, "unknown"),
                "private_networks": "10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16",
                "local_network": "192.168.0.0/16",
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

        # Get current tokens safely
        try:
            current_data = dict(self.config_entry.data)
            tokens = current_data.get(CONF_TOKENS, [])
            instance_name = current_data.get(CONF_NAME, "unknown")
        except Exception:
            tokens = []
            instance_name = "unknown"

        # Generate token info for display
        if tokens:
            token_info = []
            for i, token in enumerate(tokens, 1):
                # Show more of the token for better identification
                masked_token = f"{token[:12]}...{token[-8:]}"
                endpoint_url = f"/api/homie_proxy/{instance_name}?token={token}&url={{target_url}}"
                
                token_info.append(f"**Token {i}:** `{masked_token}`")
                token_info.append(f"**Endpoint:** `{endpoint_url}`")
                token_info.append("")
            
            tokens_display = "\n".join(token_info)
        else:
            tokens_display = "No tokens configured yet. Click 'Add New Token' to create your first access token."

        data_schema = vol.Schema({
            vol.Required("action"): selector({
                "select": {
                    "options": [
                        {"value": "add", "label": "🔑 Add New Token"},
                        {"value": "remove", "label": "🗑️ Remove Token"},
                    ],
                    "mode": "dropdown"
                }
            }),
        })

        return self.async_show_form(
            step_id="tokens",
            data_schema=data_schema,
            description_placeholders={
                "current_tokens": tokens_display,
                "token_count": str(len(tokens)),
            },
        )

    async def async_step_add_token(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Add a new access token."""
        if user_input is not None:
            try:
                # Generate new token and add to list
                current_data = dict(self.config_entry.data)
                tokens = current_data.get(CONF_TOKENS, [])
                new_token = generate_token()
                tokens.append(new_token)

                current_data[CONF_TOKENS] = tokens
                
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=current_data,
                )
                return self.async_create_entry(title="", data={})
            except Exception as e:
                _LOGGER.error("Error adding token: %s", e)
                return self.async_abort(reason="unknown")

        instance_name = self.config_entry.data.get(CONF_NAME, "unknown")
        new_token = generate_token()
        new_endpoint = f"/api/homie_proxy/{instance_name}?token={new_token}&url={{target_url}}"

        data_schema = {
            vol.Required("confirm", default=True): bool,
        }

        return self.async_show_form(
            step_id="add_token",
            data_schema=vol.Schema(data_schema),
            description_placeholders={
                "new_token": new_token,
                "new_endpoint": new_endpoint,
            },
        )

    async def async_step_remove_token(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Remove an access token."""
        try:
            current_data = dict(self.config_entry.data)
            tokens = current_data.get(CONF_TOKENS, [])
        except Exception:
            tokens = []

        if not tokens:
            return self.async_abort(reason="no_tokens")

        if user_input is not None:
            try:
                token_to_remove = user_input.get("token_to_remove")
                if token_to_remove and token_to_remove in tokens:
                    tokens.remove(token_to_remove)
                    current_data[CONF_TOKENS] = tokens
                    
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data=current_data,
                    )
                return self.async_create_entry(title="", data={})
            except Exception as e:
                _LOGGER.error("Error removing token: %s", e)
                return self.async_abort(reason="unknown")

        # Create options for token selection
        token_options = []
        for i, token in enumerate(tokens, 1):
            masked_token = f"{token[:12]}...{token[-8:]}"
            label = f"Token {i}: {masked_token}"
            token_options.append({"value": token, "label": label})

        data_schema = {
            vol.Required("token_to_remove"): selector({
                "select": {
                    "options": token_options,
                    "mode": "dropdown"
                }
            }),
        }

        return self.async_show_form(
            step_id="remove_token",
            data_schema=vol.Schema(data_schema),
            description_placeholders={
                "token_count": str(len(tokens)),
            },
        )


class InvalidCIDR(HomeAssistantError):
    """Error to indicate an invalid CIDR.""" 