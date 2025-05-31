"""Homie Proxy service for Home Assistant integration."""

import logging
import ipaddress
from typing import Optional, List
from aiohttp import web
from aiohttp.web_request import Request

from homeassistant.core import HomeAssistant
from homeassistant.components.http import HomeAssistantView

from .const import PRIVATE_CIDRS, LOCAL_CIDRS

_LOGGER = logging.getLogger(__name__)


class HomieProxyService:
    """Homie Proxy service instance."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        tokens: List[str],
        restrict_out: str,
        restrict_in: Optional[str] = None,
    ):
        """Initialize the proxy service."""
        self.hass = hass
        self.name = name
        self.tokens = tokens
        self.restrict_out = restrict_out
        self.restrict_in = restrict_in
        self.view: Optional[HomieProxyView] = None

    async def setup(self):
        """Set up the proxy service."""
        _LOGGER.info("Setting up Homie Proxy service: %s", self.name)
        
        # Create and register the HTTP view
        self.view = HomieProxyView(
            name=self.name,
            tokens=self.tokens,
            restrict_out=self.restrict_out,
            restrict_in=self.restrict_in,
        )
        self.view.hass = self.hass
        self.hass.http.register_view(self.view)
        
        _LOGGER.info(
            "Homie Proxy service '%s' is ready at /api/homie_proxy/%s with %d token(s)", 
            self.name, self.name, len(self.tokens)
        )

    async def update(self, tokens: List[str], restrict_out: str, restrict_in: Optional[str] = None):
        """Update the proxy configuration."""
        self.tokens = tokens
        self.restrict_out = restrict_out
        self.restrict_in = restrict_in
        
        if self.view:
            self.view.tokens = tokens
            self.view.restrict_out = restrict_out
            self.view.restrict_in = restrict_in
            
        _LOGGER.info(
            "Updated Homie Proxy service '%s' with %d token(s)", 
            self.name, len(self.tokens)
        )

    async def cleanup(self):
        """Clean up the proxy service."""
        _LOGGER.info("Cleaning up Homie Proxy service: %s", self.name)
        # Note: Home Assistant doesn't provide a way to unregister views
        # The view will be cleaned up when HA restarts


class HomieProxyView(HomeAssistantView):
    """HTTP view for Homie Proxy."""

    def __init__(self, name: str, tokens: List[str], restrict_out: str, restrict_in: Optional[str] = None):
        """Initialize the view."""
        self.proxy_name = name
        self.tokens = tokens
        self.restrict_out = restrict_out
        self.restrict_in = restrict_in
        
        # Set view properties
        self.url = f"/api/homie_proxy/{name}"
        self.name = f"api:homie_proxy:{name}"
        self.requires_auth = False  # We handle auth with tokens

    def _check_token(self, request: Request) -> bool:
        """Check if the request has a valid token."""
        token = request.query.get("token")
        return token is not None and token in self.tokens

    def _get_client_ip(self, request: Request) -> str:
        """Get the client IP address."""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to remote address
        return request.remote

    def _is_ip_allowed_in(self, client_ip: str) -> bool:
        """Check if client IP is allowed to access this proxy."""
        if not self.restrict_in:
            return True  # No restriction
        
        try:
            client_addr = ipaddress.ip_address(client_ip)
            allowed_network = ipaddress.ip_network(self.restrict_in, strict=False)
            return client_addr in allowed_network
        except (ipaddress.AddressValueError, ValueError) as e:
            _LOGGER.warning("Invalid IP address or network: %s", e)
            return False

    def _is_destination_allowed(self, url: str) -> bool:
        """Check if the destination URL is allowed."""
        if self.restrict_out == "any":
            return True
        
        try:
            # Extract hostname from URL
            if "://" not in url:
                url = "http://" + url
            
            from urllib.parse import urlparse
            parsed = urlparse(url)
            hostname = parsed.hostname
            
            if not hostname:
                return False
            
            # Resolve to IP and check against restrictions
            import socket
            try:
                ip = socket.gethostbyname(hostname)
                target_addr = ipaddress.ip_address(ip)
            except (socket.gaierror, ipaddress.AddressValueError):
                return False
            
            # Check against restriction rules
            if self.restrict_out == "private":
                return any(target_addr in ipaddress.ip_network(cidr) for cidr in PRIVATE_CIDRS)
            elif self.restrict_out == "local":
                return any(target_addr in ipaddress.ip_network(cidr) for cidr in LOCAL_CIDRS)
            else:
                # Custom CIDR
                try:
                    allowed_network = ipaddress.ip_network(self.restrict_out, strict=False)
                    return target_addr in allowed_network
                except ValueError:
                    return False
                    
        except Exception as e:
            _LOGGER.warning("Error checking destination %s: %s", url, e)
            return False

    async def get(self, request: Request) -> web.Response:
        """Handle GET request."""
        # Check token
        if not self._check_token(request):
            return web.Response(
                text="Unauthorized: Invalid or missing token",
                status=401
            )
        
        # Check client IP restrictions
        client_ip = self._get_client_ip(request)
        if not self._is_ip_allowed_in(client_ip):
            return web.Response(
                text=f"Forbidden: Client IP {client_ip} not allowed",
                status=403
            )
        
        # Get target URL
        target_url = request.query.get("url")
        if not target_url:
            return web.Response(
                text="Bad Request: Missing 'url' parameter",
                status=400
            )
        
        # Check destination restrictions
        if not self._is_destination_allowed(target_url):
            return web.Response(
                text=f"Forbidden: Destination {target_url} not allowed",
                status=403
            )
        
        # Import the proxy functionality from the main module
        try:
            import sys
            import os
            
            # Add the project root to Python path to import homie_proxy
            project_root = os.path.join(os.path.dirname(__file__), "..", "..", "..")
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            from homie_proxy import make_request
            
            # Make the proxied request
            response_data, status_code, content_type = await make_request(
                session=None,  # Will create its own session
                url=target_url,
                method="GET",
                headers=dict(request.headers),
                data=None
            )
            
            return web.Response(
                body=response_data,
                status=status_code,
                content_type=content_type
            )
            
        except ImportError as e:
            _LOGGER.error("Failed to import homie_proxy module: %s", e)
            return web.Response(
                text="Internal Server Error: Proxy module not available",
                status=500
            )
        except Exception as e:
            _LOGGER.error("Proxy request failed: %s", e)
            return web.Response(
                text=f"Proxy Error: {str(e)}",
                status=502
            )

    async def post(self, request: Request) -> web.Response:
        """Handle POST request."""
        # Check token
        if not self._check_token(request):
            return web.Response(
                text="Unauthorized: Invalid or missing token",
                status=401
            )
        
        # Check client IP restrictions
        client_ip = self._get_client_ip(request)
        if not self._is_ip_allowed_in(client_ip):
            return web.Response(
                text=f"Forbidden: Client IP {client_ip} not allowed",
                status=403
            )
        
        # Get target URL
        target_url = request.query.get("url")
        if not target_url:
            return web.Response(
                text="Bad Request: Missing 'url' parameter",
                status=400
            )
        
        # Check destination restrictions
        if not self._is_destination_allowed(target_url):
            return web.Response(
                text=f"Forbidden: Destination {target_url} not allowed",
                status=403
            )
        
        # Get request body
        try:
            body = await request.read()
        except Exception as e:
            _LOGGER.error("Failed to read request body: %s", e)
            return web.Response(
                text="Bad Request: Failed to read body",
                status=400
            )
        
        # Import the proxy functionality from the main module
        try:
            import sys
            import os
            
            # Add the project root to Python path to import homie_proxy
            project_root = os.path.join(os.path.dirname(__file__), "..", "..", "..")
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            from homie_proxy import make_request
            
            # Make the proxied request
            response_data, status_code, content_type = await make_request(
                session=None,  # Will create its own session
                url=target_url,
                method="POST",
                headers=dict(request.headers),
                data=body
            )
            
            return web.Response(
                body=response_data,
                status=status_code,
                content_type=content_type
            )
            
        except ImportError as e:
            _LOGGER.error("Failed to import homie_proxy module: %s", e)
            return web.Response(
                text="Internal Server Error: Proxy module not available",
                status=500
            )
        except Exception as e:
            _LOGGER.error("Proxy request failed: %s", e)
            return web.Response(
                text=f"Proxy Error: {str(e)}",
                status=502
            ) 