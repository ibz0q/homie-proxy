"""
The Homie Proxy integration for Home Assistant.

This integration provides a configurable HTTP proxy service with 
CIDR-based access controls and token authentication.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.typing import ConfigType
from homeassistant.components.http import HomeAssistantView
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, DEFAULT_TIMEOUT
from .config_flow import _load_entry_data
from .proxy import HomieProxyService, close_shared_session

_LOGGER = logging.getLogger(__name__)

# Platforms that this integration supports
PLATFORMS: list[Platform] = []

# Configuration schema for YAML setup
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional("debug_requires_auth", default=True): bool,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Homie Proxy integration."""
    _LOGGER.info("Setting up Homie Proxy integration")
    
    # Initialize domain data
    hass.data.setdefault(DOMAIN, {})
    
    # Read global configuration from YAML
    homie_config = config.get(DOMAIN, {})
    debug_requires_auth = homie_config.get("debug_requires_auth", True)
    
    # Store global configuration
    hass.data[DOMAIN]["global_config"] = {
        "debug_requires_auth": debug_requires_auth
    }
    
    _LOGGER.info("HomieProxy global config: debug_requires_auth=%s", debug_requires_auth)
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homie Proxy from a config entry."""
    _LOGGER.info("Setting up Homie Proxy instance: %s", entry.data.get("name"))

    # Read entry through canonical loader (handles legacy field migration).
    cfg = _load_entry_data(entry.data)
    name = cfg["name"]
    tokens = cfg["tokens"]
    restrict_out = cfg["restrict_out"]
    restrict_out_cidrs = cfg["restrict_out_cidrs"]
    restrict_in_cidrs = cfg["restrict_in_cidrs"]
    requires_auth = cfg["requires_auth"]
    timeout = cfg["timeout"]

    # Read debug auth from the per-entry config (falls back to the legacy YAML
    # global config so existing deployments don't change behaviour on upgrade).
    debug_requires_auth = cfg.get(
        "debug_requires_auth",
        hass.data[DOMAIN].get("global_config", {}).get("debug_requires_auth", True),
    )

    if not tokens:
        _LOGGER.error("No tokens configured for Homie Proxy instance '%s'", name)
        raise ConfigEntryNotReady("No tokens configured")

    # Create proxy service
    try:
        proxy_service = HomieProxyService(
            hass=hass,
            name=name,
            tokens=tokens,
            restrict_out=restrict_out,
            restrict_out_cidrs=restrict_out_cidrs,
            restrict_in_cidrs=restrict_in_cidrs,
            timeout=timeout,
            requires_auth=requires_auth,
            debug_requires_auth=debug_requires_auth,
        )
        
        # Store service instance
        hass.data[DOMAIN][entry.entry_id] = {
            "service": proxy_service,
            "config": entry.data
        }
        
        # Register the proxy endpoint
        await proxy_service.setup()
        
        _LOGGER.info("Homie Proxy instance '%s' setup completed with %d token(s), timeout=%ds", name, len(tokens), timeout)
        
    except Exception as err:
        _LOGGER.error("Failed to setup Homie Proxy instance '%s': %s", name, err)
        raise ConfigEntryNotReady from err
    
    # Set up update listener for configuration changes
    entry.async_on_unload(entry.add_update_listener(async_update_listener))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Homie Proxy config entry."""
    _LOGGER.info("Unloading Homie Proxy instance: %s", entry.data.get("name"))

    # Get service instance
    instance_data = hass.data[DOMAIN].get(entry.entry_id)
    if instance_data:
        proxy_service = instance_data["service"]
        await proxy_service.cleanup()

        # Remove from domain data
        hass.data[DOMAIN].pop(entry.entry_id, None)

    # If this was the last proxy instance, close the shared keep-alive pool.
    remaining_instances = [
        k for k in hass.data.get(DOMAIN, {}).keys()
        if k not in ("global_config",)
    ]
    if not remaining_instances:
        await close_shared_session()

    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle configuration updates."""
    _LOGGER.info("Updating Homie Proxy instance: %s", entry.data.get("name"))

    instance_data = hass.data[DOMAIN].get(entry.entry_id)
    if not instance_data:
        _LOGGER.error("No service instance found for entry %s", entry.entry_id)
        return

    proxy_service = instance_data["service"]

    cfg = _load_entry_data(entry.data)
    debug_requires_auth = cfg.get(
        "debug_requires_auth",
        hass.data[DOMAIN].get("global_config", {}).get("debug_requires_auth", True),
    )

    await proxy_service.update(
        tokens=cfg["tokens"],
        restrict_out=cfg["restrict_out"],
        restrict_out_cidrs=cfg["restrict_out_cidrs"],
        restrict_in_cidrs=cfg["restrict_in_cidrs"],
        timeout=cfg["timeout"],
        requires_auth=cfg["requires_auth"],
        debug_requires_auth=debug_requires_auth,
    )

    instance_data["config"] = entry.data


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a Homie Proxy config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry) 