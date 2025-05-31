"""Homie Proxy service for Home Assistant integration."""

import logging
import ipaddress
import socket
import ssl
from typing import Optional, List
from urllib.parse import urlparse
from aiohttp import web, ClientSession, ClientTimeout, ClientError
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
            
            parsed = urlparse(url)
            hostname = parsed.hostname
            
            if not hostname:
                return False
            
            # Resolve to IP and check against restrictions
            try:
                ip = socket.gethostbyname(hostname)
                target_addr = ipaddress.ip_address(ip)
            except (socket.gaierror, ipaddress.AddressValueError):
                return False
            
            # Check against restriction rules
            if self.restrict_out == "external":
                # External networks only - NOT in private ranges
                return not any(target_addr in ipaddress.ip_network(cidr) for cidr in PRIVATE_CIDRS)
            elif self.restrict_out == "internal":
                # Internal networks only - must be in private ranges
                return any(target_addr in ipaddress.ip_network(cidr) for cidr in PRIVATE_CIDRS)
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

    def _prepare_headers(self, request_headers, target_url: str):
        """Prepare headers for the outgoing request."""
        headers = {}
        excluded_headers = {
            'connection', 'upgrade', 'proxy-authenticate', 
            'proxy-authorization', 'te', 'trailers', 'transfer-encoding',
            'host'  # We'll handle host separately
        }
        
        # Copy headers excluding hop-by-hop headers
        for key, value in request_headers.items():
            if key.lower() not in excluded_headers:
                headers[key] = value
        
        # Handle Host header properly
        try:
            parsed_url = urlparse(target_url)
            hostname = parsed_url.hostname
            
            if hostname:
                # Check if hostname is an IP address
                try:
                    ipaddress.ip_address(hostname)
                    # It's an IP address - don't set Host header
                    pass
                except ValueError:
                    # It's a hostname - set Host header
                    headers['Host'] = hostname
        except Exception:
            pass
        
        return headers

    async def _make_request(self, method: str, url: str, headers: dict, data=None):
        """Make the actual HTTP request."""
        timeout = ClientTimeout(total=30)
        
        # Create SSL context that's more permissive
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_OPTIONAL
        
        connector = web.TCPConnector(ssl=ssl_context)
        
        try:
            async with ClientSession(timeout=timeout, connector=connector) as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=data,
                    allow_redirects=True
                ) as response:
                    content = await response.read()
                    
                    # Prepare response headers
                    response_headers = {}
                    excluded_response_headers = {
                        'connection', 'transfer-encoding', 'content-encoding'
                    }
                    
                    for key, value in response.headers.items():
                        if key.lower() not in excluded_response_headers:
                            response_headers[key] = value
                    
                    return {
                        'content': content,
                        'status': response.status,
                        'headers': response_headers,
                        'content_type': response.headers.get('Content-Type', 'text/plain')
                    }
        finally:
            await connector.close()

    async def get(self, request: Request) -> web.Response:
        """Handle GET request."""
        return await self._handle_request(request, "GET")

    async def post(self, request: Request) -> web.Response:
        """Handle POST request."""
        return await self._handle_request(request, "POST")

    async def _handle_request(self, request: Request, method: str) -> web.Response:
        """Handle HTTP request of any method."""
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
        
        # Get request body for methods that might have one
        data = None
        if method in ['POST', 'PUT', 'PATCH']:
            try:
                data = await request.read()
            except Exception as e:
                _LOGGER.error("Failed to read request body: %s", e)
                return web.Response(
                    text="Bad Request: Failed to read body",
                    status=400
                )
        
        # Prepare headers
        headers = self._prepare_headers(request.headers, target_url)
        
        # Make the proxied request
        try:
            result = await self._make_request(method, target_url, headers, data)
            
            return web.Response(
                body=result['content'],
                status=result['status'],
                headers=result['headers']
            )
            
        except ClientError as e:
            _LOGGER.error("Client error during proxy request: %s", e)
            return web.Response(
                text=f"Proxy Error: {str(e)}",
                status=502
            )
        except Exception as e:
            _LOGGER.error("Proxy request failed: %s", e)
            return web.Response(
                text=f"Proxy Error: {str(e)}",
                status=502
            ) 