"""
The Hello World integration for Home Assistant.

This integration demonstrates how to create a simple custom component
that exposes an API endpoint returning a hello world message.
"""

import logging
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.helpers.typing import ConfigType
from homeassistant.components import frontend
from homeassistant.components.http import HomeAssistantView

_LOGGER = logging.getLogger(__name__)

DOMAIN = "hello_world"

# Platforms that this integration supports
PLATFORMS: list[Platform] = []


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Hello World integration."""
    _LOGGER.info("Setting up Hello World integration")
    
    # Store integration data
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["setup_time"] = datetime.now()
    
    # Register API view
    hass.http.register_view(HelloWorldAPIView())
    
    # Register info API view
    hass.http.register_view(HelloWorldInfoAPIView())
    
    # Set a state for demonstration
    hass.states.async_set(
        f"{DOMAIN}.status", 
        "active",
        {
            "friendly_name": "Hello World Status",
            "setup_time": hass.data[DOMAIN]["setup_time"].isoformat(),
            "message": "Hello from the Hello World integration!",
            "api_endpoint": "/api/hello_world"
        }
    )
    
    _LOGGER.info("Hello World integration setup completed successfully")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hello World from a config entry."""
    _LOGGER.info("Setting up Hello World config entry: %s", entry.entry_id)
    
    # Forward setup to platforms if any
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Hello World config entry: %s", entry.entry_id)
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    
    return unload_ok


class HelloWorldAPIView(HomeAssistantView):
    """API view for Hello World integration."""
    
    url = "/api/hello_world"
    name = "api:hello_world"
    requires_auth = False  # Allow unauthenticated access for testing
    
    async def get(self, request):
        """Handle GET request to hello world endpoint."""
        _LOGGER.info("Hello World API endpoint accessed")
        
        # Get current time
        current_time = datetime.now()
        
        # Get setup time if available
        setup_time = None
        if DOMAIN in self.hass.data and "setup_time" in self.hass.data[DOMAIN]:
            setup_time = self.hass.data[DOMAIN]["setup_time"]
        
        # Calculate uptime
        uptime = None
        if setup_time:
            uptime_delta = current_time - setup_time
            uptime = str(uptime_delta)
        
        # Build response
        response_data = {
            "message": "Hello, World! 🌍",
            "status": "success",
            "timestamp": current_time.isoformat(),
            "integration": "hello_world",
            "version": "1.0.0",
            "endpoints": {
                "hello": "/api/hello_world",
                "info": "/api/hello_world/info"
            }
        }
        
        if setup_time:
            response_data["setup_time"] = setup_time.isoformat()
            response_data["uptime"] = uptime
        
        # Check if there are any URL parameters
        name = request.query.get("name")
        if name:
            response_data["message"] = f"Hello, {name}! 🌍"
            response_data["personalized"] = True
        
        # Return JSON response
        return self.json(response_data)
    
    async def post(self, request):
        """Handle POST request to hello world endpoint."""
        _LOGGER.info("Hello World API endpoint accessed via POST")
        
        try:
            # Parse JSON body if present
            data = await request.json() if request.can_read_body else {}
        except Exception:
            data = {}
        
        # Get message from POST data
        custom_message = data.get("message", "Hello, World!")
        name = data.get("name")
        
        response_data = {
            "message": f"{custom_message} 🌍",
            "status": "success", 
            "timestamp": datetime.now().isoformat(),
            "integration": "hello_world",
            "method": "POST",
            "received_data": data
        }
        
        if name:
            response_data["message"] = f"{custom_message}, {name}! 🌍"
            response_data["personalized"] = True
        
        return self.json(response_data)


class HelloWorldInfoAPIView(HomeAssistantView):
    """Info API view for Hello World integration."""
    
    url = "/api/hello_world/info"
    name = "api:hello_world:info"
    requires_auth = False
    
    async def get(self, request):
        """Handle GET request to hello world info endpoint."""
        _LOGGER.info("Hello World Info API endpoint accessed")
        
        # Get integration state
        state = self.hass.states.get(f"{DOMAIN}.status")
        
        response_data = {
            "integration_name": "Hello World",
            "domain": DOMAIN,
            "version": "1.0.0",
            "description": "A simple Hello World integration for Home Assistant development",
            "endpoints": {
                "main": "/api/hello_world",
                "info": "/api/hello_world/info"
            },
            "features": [
                "Custom API endpoints",
                "State management", 
                "Logging integration",
                "GET/POST support",
                "Query parameter support"
            ]
        }
        
        if state:
            response_data["state"] = {
                "entity_id": state.entity_id,
                "state": state.state,
                "attributes": dict(state.attributes)
            }
        
        return self.json(response_data) 