"""Config & options flow for HomieProxy.

The options flow is menu-driven so each concern (tokens, restrictions, settings,
info) lives in its own focused step. Each form uses HA's `selector` helpers so
labels stay translatable and validation is delegated to the frontend.

Storage shape (canonical):
    {
        "name": str,
        "tokens": list[str],            # 1+ access tokens
        "restrict_out": str,            # "any" | "external" | "internal" | "custom"
        "restrict_out_cidrs": list[str],# only meaningful when restrict_out == "custom"
        "restrict_in_cidrs": list[str], # always a list, may be empty
        "requires_auth": bool,
        "timeout": int,                 # seconds, 30..3600
    }

Legacy entries (created before this rewrite) had:
    - `restrict_out` as EITHER a mode string OR a single CIDR string
    - `restrict_in` as a single optional CIDR string
We migrate those at read-time via `_load_entry_data`.
"""
from __future__ import annotations

import ipaddress
import logging
import uuid
from typing import Any, Dict, List, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import DOMAIN, DEFAULT_TIMEOUT

_LOGGER = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

RESTRICT_MODES = ["any", "external", "internal", "custom"]

# Selector definitions (HA shows the .label, ships the .value as form data — no
# fragile reverse mapping needed).
RESTRICT_MODE_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(value="any",      label="Allow all networks"),
            selector.SelectOptionDict(value="external", label="External networks only"),
            selector.SelectOptionDict(value="internal", label="Internal networks only"),
            selector.SelectOptionDict(value="custom",   label="Custom CIDR list"),
        ],
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)

CIDR_LIST_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(
        type=selector.TextSelectorType.TEXT,
        multiline=True,
    )
)

TOKEN_LIST_SELECTOR = selector.TextSelector(
    selector.TextSelectorConfig(
        type=selector.TextSelectorType.TEXT,
        multiline=True,
    )
)

TIMEOUT_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=30, max=3600, step=1, unit_of_measurement="seconds",
        mode=selector.NumberSelectorMode.BOX,
    )
)

# Stream chunk size — 0 means "low-latency mode" (yields whatever's in the
# socket buffer immediately; right default for live MJPEG/HLS). Anything
# >0 buffers up to N bytes per write, trading latency for throughput.
STREAM_CHUNK_SIZE_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0, max=1048576, step=1, unit_of_measurement="bytes",
        mode=selector.NumberSelectorMode.BOX,
    )
)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _generate_token() -> str:
    """Generate a UUIDv4 access token."""
    return str(uuid.uuid4())


def _parse_cidr_list(text: str) -> List[str]:
    """Parse newline / comma separated CIDR text into a validated list.
    Raises `vol.Invalid` if any entry is malformed."""
    if not text:
        return []
    raw = [p.strip() for p in text.replace(",", "\n").splitlines()]
    parsed: List[str] = []
    for item in raw:
        if not item:
            continue
        try:
            ipaddress.ip_network(item, strict=False)
        except ValueError as e:
            raise vol.Invalid(f"Invalid CIDR '{item}': {e}") from e
        parsed.append(item)
    return parsed


def _parse_token_list(text: str) -> List[str]:
    """Parse newline / comma separated tokens. Empty lines ignored."""
    if not text:
        return []
    raw = [p.strip() for p in text.replace(",", "\n").splitlines()]
    return [r for r in raw if r]


def _format_list(items: List[str]) -> str:
    """Format a list back into newline-joined text for re-editing."""
    return "\n".join(items or [])


def _load_entry_data(entry_data: Dict[str, Any]) -> Dict[str, Any]:
    """Read a config entry into the canonical shape, migrating legacy fields.

    Old entries stored:
      - `restrict_out`: mode OR a CIDR string (when "custom")
      - `restrict_in`: a single optional CIDR string
    New entries store explicit `restrict_out_cidrs` and `restrict_in_cidrs`
    lists with `restrict_out` always being one of the four modes.
    """
    raw_out = entry_data.get("restrict_out", "any")
    out_cidrs = entry_data.get("restrict_out_cidrs")

    if out_cidrs is None:
        # Legacy: `restrict_out` was either a mode or a CIDR.
        if raw_out in RESTRICT_MODES:
            mode = raw_out
            out_cidrs = []
        else:
            # Treat as a single custom CIDR.
            try:
                ipaddress.ip_network(raw_out, strict=False)
                mode = "custom"
                out_cidrs = [raw_out]
            except ValueError:
                mode = "any"
                out_cidrs = []
    else:
        mode = raw_out if raw_out in RESTRICT_MODES else "any"

    in_cidrs = entry_data.get("restrict_in_cidrs")
    if in_cidrs is None:
        legacy_in = entry_data.get("restrict_in")
        in_cidrs = [legacy_in] if legacy_in else []

    return {
        "name": entry_data.get("name", "external-api-route"),
        "tokens": list(entry_data.get("tokens") or []),
        "restrict_out": mode,
        "restrict_out_cidrs": list(out_cidrs or []),
        "restrict_in_cidrs": list(in_cidrs or []),
        "requires_auth": bool(entry_data.get("requires_auth", True)),
        "debug_requires_auth": bool(entry_data.get("debug_requires_auth", True)),
        "timeout": int(entry_data.get("timeout", DEFAULT_TIMEOUT)),
        # 0 = low-latency (iter_any) — recommended for live streams.
        "stream_chunk_size": max(0, int(entry_data.get("stream_chunk_size", 0))),
    }


# ─── Initial config flow ──────────────────────────────────────────────────────

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Create a new HomieProxy instance.

    Single step: name + restriction settings + auto-generated initial token.
    Token management and CIDR list editing happen in the options flow afterwards.
    """

    VERSION = 1

    def __init__(self) -> None:
        self._user_input: Dict[str, Any] = {}

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        errors: Dict[str, str] = {}

        if user_input is not None:
            name = (user_input.get("name") or "").strip()
            if len(name) < 2:
                errors["name"] = "invalid_name"
            elif any(
                e.data.get("name") == name
                for e in self.hass.config_entries.async_entries(DOMAIN)
            ):
                errors["base"] = "already_configured"

            mode = user_input.get("restrict_out", "any")
            out_cidrs_text = user_input.get("restrict_out_cidrs", "") or ""
            in_cidrs_text = user_input.get("restrict_in_cidrs", "") or ""

            out_cidrs: List[str] = []
            in_cidrs: List[str] = []

            try:
                out_cidrs = _parse_cidr_list(out_cidrs_text)
            except vol.Invalid as e:
                errors["restrict_out_cidrs"] = "invalid_cidr"
                _LOGGER.warning("Outbound CIDR parse failed: %s", e)

            try:
                in_cidrs = _parse_cidr_list(in_cidrs_text)
            except vol.Invalid as e:
                errors["restrict_in_cidrs"] = "invalid_cidr"
                _LOGGER.warning("Inbound CIDR parse failed: %s", e)

            if mode == "custom" and not out_cidrs:
                errors["restrict_out_cidrs"] = "custom_requires_cidrs"

            if not errors:
                data = {
                    "name": name,
                    "tokens": [_generate_token()],
                    "restrict_out": mode,
                    "restrict_out_cidrs": out_cidrs,
                    "restrict_in_cidrs": in_cidrs,
                    "requires_auth": user_input.get("requires_auth", True),
                    "timeout": int(user_input.get("timeout", DEFAULT_TIMEOUT)),
                }
                return self.async_create_entry(title=f"HomieProxy — {name}", data=data)

        schema = vol.Schema({
            vol.Required("name", default=user_input.get("name") if user_input else "external-api-route"): str,
            vol.Required("restrict_out", default=user_input.get("restrict_out") if user_input else "external"): RESTRICT_MODE_SELECTOR,
            vol.Optional("restrict_out_cidrs", default=user_input.get("restrict_out_cidrs") if user_input else ""): CIDR_LIST_SELECTOR,
            vol.Optional("restrict_in_cidrs", default=user_input.get("restrict_in_cidrs") if user_input else ""): CIDR_LIST_SELECTOR,
            vol.Required("requires_auth", default=user_input.get("requires_auth", True) if user_input else True): selector.BooleanSelector(),
            vol.Required("timeout", default=user_input.get("timeout", DEFAULT_TIMEOUT) if user_input else DEFAULT_TIMEOUT): TIMEOUT_SELECTOR,
        })

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        return OptionsFlow()


# ─── Options flow (menu-driven) ───────────────────────────────────────────────

class OptionsFlow(config_entries.OptionsFlow):
    """Menu-driven options flow.

    The main step (`init`) shows a menu with five entries. Each leaf step edits
    one concern, persists, and returns to the menu so users can keep editing
    before exiting.
    """

    # The current canonical view of the entry's data — refreshed every time we
    # come back to the menu so concurrent edits don't get lost.
    def _data(self) -> Dict[str, Any]:
        return _load_entry_data(self.config_entry.data)

    def _persist(self, patch: Dict[str, Any]) -> None:
        merged = {**self.config_entry.data, **patch}
        self.hass.config_entries.async_update_entry(self.config_entry, data=merged)

    async def _reload(self) -> None:
        await self.hass.config_entries.async_reload(self.config_entry.entry_id)

    # ── Main menu ────────────────────────────────────────────────────────────

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["rename", "tokens", "restrictions", "settings", "info"],
        )

    # ── Rename ───────────────────────────────────────────────────────────────

    async def async_step_rename(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Let the user change the endpoint name (the URL path segment)."""
        errors: Dict[str, str] = {}
        data = self._data()

        if user_input is not None:
            new_name = (user_input.get("name") or "").strip()

            if len(new_name) < 2:
                errors["name"] = "invalid_name"
            elif new_name != data["name"] and any(
                e.data.get("name") == new_name
                for e in self.hass.config_entries.async_entries(DOMAIN)
                if e.entry_id != self.config_entry.entry_id
            ):
                errors["name"] = "already_configured"

            if not errors:
                self._persist({"name": new_name})
                # Update the integration title shown in the UI.
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    title=f"HomieProxy — {new_name}",
                )
                await self._reload()
                return await self.async_step_init()

        schema = vol.Schema({
            vol.Required("name", default=user_input.get("name") if user_input else data["name"]): str,
        })

        return self.async_show_form(
            step_id="rename",
            data_schema=schema,
            errors=errors,
            description_placeholders={"current_name": data["name"]},
        )

    # ── Tokens ───────────────────────────────────────────────────────────────

    async def async_step_tokens(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        errors: Dict[str, str] = {}
        data = self._data()

        if user_input is not None:
            action = user_input.get("action", "save")
            text = user_input.get("tokens_text", "") or ""
            tokens = _parse_token_list(text)

            if action == "generate_new":
                tokens = list(tokens) + [_generate_token()]
            elif action == "regenerate_all":
                tokens = [_generate_token()]
            # else: action == "save" → keep tokens as parsed

            if not tokens:
                errors["base"] = "tokens_empty"
            else:
                self._persist({"tokens": tokens})
                if action == "save":
                    await self._reload()
                    return await self.async_step_init()
                # Regenerate flows: re-show with the new list pre-filled.
                data = {**data, "tokens": tokens}

        schema = vol.Schema({
            vol.Required(
                "tokens_text",
                default=_format_list(data["tokens"]),
            ): TOKEN_LIST_SELECTOR,
            vol.Required("action", default="save"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value="save",            label="Save changes"),
                        selector.SelectOptionDict(value="generate_new",    label="Append a new generated token"),
                        selector.SelectOptionDict(value="regenerate_all",  label="Replace all tokens with one new token"),
                    ],
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        })

        return self.async_show_form(
            step_id="tokens",
            data_schema=schema,
            errors=errors,
            description_placeholders={"count": str(len(data["tokens"]))},
        )

    # ── Restrictions ─────────────────────────────────────────────────────────

    async def async_step_restrictions(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        errors: Dict[str, str] = {}
        data = self._data()

        if user_input is not None:
            mode = user_input.get("restrict_out", "any")
            out_text = user_input.get("restrict_out_cidrs", "") or ""
            in_text = user_input.get("restrict_in_cidrs", "") or ""

            try:
                out_cidrs = _parse_cidr_list(out_text)
            except vol.Invalid:
                errors["restrict_out_cidrs"] = "invalid_cidr"
                out_cidrs = []

            try:
                in_cidrs = _parse_cidr_list(in_text)
            except vol.Invalid:
                errors["restrict_in_cidrs"] = "invalid_cidr"
                in_cidrs = []

            if mode == "custom" and not out_cidrs and "restrict_out_cidrs" not in errors:
                errors["restrict_out_cidrs"] = "custom_requires_cidrs"

            if not errors:
                self._persist({
                    "restrict_out": mode,
                    "restrict_out_cidrs": out_cidrs,
                    "restrict_in_cidrs": in_cidrs,
                    # Drop legacy single-CIDR field if it lingered.
                    "restrict_in": None,
                })
                await self._reload()
                return await self.async_step_init()

        schema = vol.Schema({
            vol.Required("restrict_out", default=data["restrict_out"]): RESTRICT_MODE_SELECTOR,
            vol.Optional(
                "restrict_out_cidrs",
                default=_format_list(data["restrict_out_cidrs"]),
            ): CIDR_LIST_SELECTOR,
            vol.Optional(
                "restrict_in_cidrs",
                default=_format_list(data["restrict_in_cidrs"]),
            ): CIDR_LIST_SELECTOR,
        })

        return self.async_show_form(
            step_id="restrictions", data_schema=schema, errors=errors,
        )

    # ── Settings (auth + timeout) ────────────────────────────────────────────

    async def async_step_settings(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        data = self._data()

        if user_input is not None:
            self._persist({
                "requires_auth": bool(user_input.get("requires_auth", True)),
                "debug_requires_auth": bool(user_input.get("debug_requires_auth", True)),
                "timeout": int(user_input.get("timeout", DEFAULT_TIMEOUT)),
                "stream_chunk_size": max(0, int(user_input.get("stream_chunk_size", 0))),
            })
            await self._reload()
            return await self.async_step_init()

        schema = vol.Schema({
            vol.Required("requires_auth", default=data["requires_auth"]): selector.BooleanSelector(),
            vol.Required("debug_requires_auth", default=data["debug_requires_auth"]): selector.BooleanSelector(),
            vol.Required("timeout", default=data["timeout"]): TIMEOUT_SELECTOR,
            vol.Required("stream_chunk_size", default=data["stream_chunk_size"]): STREAM_CHUNK_SIZE_SELECTOR,
        })
        return self.async_show_form(step_id="settings", data_schema=schema)

    # ── Read-only info ───────────────────────────────────────────────────────

    async def async_step_info(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return await self.async_step_init()

        data = self._data()
        first_token = data["tokens"][0] if data["tokens"] else "(no tokens)"
        endpoint = f"/api/homie_proxy/{data['name']}"

        # Placeholder hostname shown in examples. Avoid `<…>` because HA's
        # markdown renderer parses those as unclosed HTML tags (UNCLOSED_TAG
        # translation error).
        base = "HA_HOST:8123"
        proxy_base = f"http://{base}{endpoint}"

        curl_sample = (
            f"curl -G '{proxy_base}' \\\n"
            f"  --data-urlencode 'token={first_token}' \\\n"
            f"  --data-urlencode 'url=https://httpbin.org/get'"
        )

        post_sample = (
            f"curl -X POST '{proxy_base}' \\\n"
            f"  --data-urlencode 'token={first_token}' \\\n"
            f"  --data-urlencode 'url=http://192.168.1.50/api/preset' \\\n"
            f"  -H 'Content-Type: application/json' \\\n"
            f"  -d '{{\"preset\": 1}}'"
        )

        auth_sample = (
            f"curl -G '{proxy_base}' \\\n"
            f"  --data-urlencode 'token={first_token}' \\\n"
            f"  --data-urlencode 'url=https://api.example.com/data' \\\n"
            f"  --data-urlencode 'request_header[Authorization]=Bearer upstream-secret' \\\n"
            f"  --data-urlencode 'response_header[Access-Control-Allow-Origin]=*'"
        )

        preflight_sample = (
            f"curl -X OPTIONS -G '{proxy_base}' \\\n"
            f"  --data-urlencode 'token={first_token}' \\\n"
            f"  --data-urlencode 'url=http://192.168.1.50/api' \\\n"
            f"  --data-urlencode 'cors_preflight=1' \\\n"
            f"  --data-urlencode 'response_header[Access-Control-Allow-Origin]=*' \\\n"
            f"  --data-urlencode 'response_header[Access-Control-Allow-Methods]=GET, POST, PUT' \\\n"
            f"  --data-urlencode 'response_header[Access-Control-Allow-Headers]=Content-Type'"
        )

        tls_sample = (
            f"curl -G '{proxy_base}' \\\n"
            f"  --data-urlencode 'token={first_token}' \\\n"
            f"  --data-urlencode 'url=https://192.168.1.50/api' \\\n"
            f"  --data-urlencode 'skip_tls_checks=all'"
        )

        js_sample = (
            f"const params = new URLSearchParams({{\n"
            f"  token: '{first_token}',\n"
            f"  url:   'http://192.168.1.50/api/status',\n"
            f"  'request_header[Authorization]': 'Basic ' + btoa('user:pass'),\n"
            f"  'response_header[Access-Control-Allow-Origin]': '*',\n"
            f"}});\n"
            f"const resp = await fetch(`{proxy_base}?${{params}}`);\n"
            f"const data = await resp.json();"
        )

        return self.async_show_form(
            step_id="info",
            data_schema=vol.Schema({}),
            description_placeholders={
                "name": data["name"],
                "endpoint": endpoint,
                "token_count": str(len(data["tokens"])),
                "first_token": first_token,
                "restrict_out": data["restrict_out"],
                "restrict_out_cidrs": _format_list(data["restrict_out_cidrs"]) or "(none)",
                "restrict_in_cidrs": _format_list(data["restrict_in_cidrs"]) or "(none)",
                "requires_auth": "yes" if data["requires_auth"] else "no",
                "debug_requires_auth": "yes" if data["debug_requires_auth"] else "**no (open)**",
                "timeout": str(data["timeout"]),
                "stream_chunk_size": (
                    "0 (low-latency / iter_any)"
                    if data["stream_chunk_size"] == 0
                    else f"{data['stream_chunk_size']} bytes"
                ),
                "curl_sample": curl_sample,
                "post_sample": post_sample,
                "auth_sample": auth_sample,
                "preflight_sample": preflight_sample,
                "tls_sample": tls_sample,
                "js_sample": js_sample,
                "debug_endpoint": f"http://{base}/api/homie_proxy/debug",
            },
        )
