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

from .const import DOMAIN
from .proxy import HomieProxyService

_LOGGER = logging.getLogger(__name__)

# Platforms that this integration supports
PLATFORMS: list[Platform] = []

# Configuration schema for YAML setup
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional("timeout", default=300): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
    })
}, extra=vol.ALLOW_EXTRA)


def migrate_config_data(config: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate configuration data to support multiple tokens."""
    config = dict(config)  # Create a copy
    
    # Migrate single token to tokens list if needed
    if "token" in config and "tokens" not in config:
        tokens = [config["token"]]
        config["tokens"] = tokens
        del config["token"]
        _LOGGER.info("Migrated single token to tokens list")
    elif "tokens" not in config:
        # No tokens at all, this shouldn't happen but handle gracefully
        config["tokens"] = []
        _LOGGER.warning("No tokens found in config, initialized empty list")
    
    return config


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Homie Proxy integration."""
    _LOGGER.info("Setting up Homie Proxy integration")
    
    # Initialize domain data
    hass.data.setdefault(DOMAIN, {})
    
    # Read global configuration from YAML
    homie_config = config.get(DOMAIN, {})
    global_timeout = homie_config.get("timeout", 300)
    
    # Store global configuration
    hass.data[DOMAIN]["global_config"] = {
        "timeout": global_timeout
    }
    
    _LOGGER.info("HomieProxy global config: timeout=%ds", global_timeout)
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homie Proxy from a config entry."""
    _LOGGER.info("Setting up Homie Proxy instance: %s", entry.data.get("name"))
    
    # Migrate configuration if needed
    config = migrate_config_data(entry.data)
    
    # Update entry with migrated data if necessary
    if config != entry.data:
        hass.config_entries.async_update_entry(entry, data=config)
        _LOGGER.info("Updated config entry with migrated data")
    
    # Get configuration
    name = config.get("name")
    tokens = config.get("tokens", [])
    restrict_out = config.get("restrict_out")
    restrict_in = config.get("restrict_in")
    
    # Get global timeout configuration
    global_config = hass.data[DOMAIN].get("global_config", {})
    timeout = global_config.get("timeout", 300)
    
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
            restrict_in=restrict_in,
            timeout=timeout
        )
        
        # Store service instance
        hass.data[DOMAIN][entry.entry_id] = {
            "service": proxy_service,
            "config": config
        }
        
        # Register the proxy endpoint
        await proxy_service.setup()
        
        _LOGGER.info("Homie Proxy instance '%s' setup completed with %d token(s)", name, len(tokens))
        
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
    
    return True


async def async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle configuration updates."""
    _LOGGER.info("Updating Homie Proxy instance: %s", entry.data.get("name"))
    
    # Get service instance
    instance_data = hass.data[DOMAIN].get(entry.entry_id)
    if not instance_data:
        _LOGGER.error("No service instance found for entry %s", entry.entry_id)
        return
    
    proxy_service = instance_data["service"]
    
    # Migrate configuration if needed
    config = migrate_config_data(entry.data)
    
    # Get updated configuration
    tokens = config.get("tokens", [])
    restrict_out = config.get("restrict_out")
    restrict_in = config.get("restrict_in")
    
    # Get global timeout configuration
    global_config = hass.data[DOMAIN].get("global_config", {})
    timeout = global_config.get("timeout", 300)
    
    # Update the service
    await proxy_service.update(
        tokens=tokens,
        restrict_out=restrict_out,
        restrict_in=restrict_in,
        timeout=timeout
    )
    
    # Update stored config
    instance_data["config"] = config


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a Homie Proxy config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry) 