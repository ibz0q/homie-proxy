"""Homie Proxy service for Home Assistant integration."""

import logging
import ipaddress
import socket
import ssl
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse, parse_qs
from aiohttp import web, ClientSession, ClientTimeout, ClientError, ClientConnectorError
from aiohttp.web_request import Request
from aiohttp.connector import TCPConnector

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
        if not self.tokens:
            return True  # No tokens required
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

    def _parse_skip_tls_checks(self, query_params: Dict) -> List[str]:
        """Parse skip_tls_checks parameter."""
        skip_tls_param = query_params.get('skip_tls_checks', [''])
        if not skip_tls_param[0]:
            return []
        
        skip_tls_value = skip_tls_param[0].lower()
        
        # Handle boolean-style values
        if skip_tls_value in ['true', '1', 'yes']:
            _LOGGER.info("TLS parameter 'true' detected, ignoring ALL TLS errors")
            return ['all']
        
        # Parse comma-separated list
        skip_tls_checks = [error.strip().lower() for error in skip_tls_value.split(',')]
        _LOGGER.info("Ignoring specific TLS errors: %s", ', '.join(skip_tls_checks))
        return skip_tls_checks

    def _create_ssl_context(self, skip_tls_checks: List[str]) -> Optional[ssl.SSLContext]:
        """Create SSL context based on TLS error handling preferences."""
        if not skip_tls_checks:
            return None
        
        ssl_context = ssl.create_default_context()
        
        # Check for ALL option - disables all TLS verification
        if 'all' in skip_tls_checks:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            _LOGGER.info("Ignoring ALL TLS errors - complete TLS verification disabled")
            return ssl_context
        
        # Handle specific TLS error types
        if any(check in skip_tls_checks for check in ['expired_cert', 'self_signed', 'cert_authority']):
            ssl_context.verify_mode = ssl.CERT_NONE
        
        if any(check in skip_tls_checks for check in ['hostname_mismatch', 'expired_cert', 'self_signed']):
            ssl_context.check_hostname = False
        
        if 'weak_cipher' in skip_tls_checks:
            try:
                ssl_context.set_ciphers('ALL:@SECLEVEL=0')
            except ssl.SSLError:
                _LOGGER.warning("Could not set weak cipher support")
        
        return ssl_context

    def _prepare_headers(self, request: Request, target_url: str, query_params: Dict) -> Dict[str, str]:
        """Prepare headers for the outgoing request."""
        headers = {}
        excluded_headers = {
            'connection', 'upgrade', 'proxy-authenticate', 
            'proxy-authorization', 'te', 'trailers', 'transfer-encoding',
            'host'  # We'll handle host separately
        }
        
        # Copy headers excluding hop-by-hop headers
        for key, value in request.headers.items():
            if key.lower() not in excluded_headers:
                headers[key] = value
        
        # Add custom request headers from query parameters
        for key, values in query_params.items():
            if key.startswith('request_headers[') and key.endswith(']'):
                header_name = key[16:-1]  # Remove 'request_headers[' and ']'
                headers[header_name] = values[0]
                _LOGGER.debug("Added custom request header: %s = %s", header_name, values[0])
        
        # Handle Host header logic
        override_host_header = query_params.get('override_host_header', [''])[0]
        
        try:
            parsed_url = urlparse(target_url)
            hostname = parsed_url.hostname
            
            if override_host_header:
                # Use explicit override
                headers['Host'] = override_host_header
                _LOGGER.debug("Override Host header set to: %s", override_host_header)
            elif hostname:
                # Check if hostname is an IP address
                try:
                    ipaddress.ip_address(hostname)
                    # It's an IP address - don't set Host header
                    headers.pop('Host', None)
                    _LOGGER.debug("Target is IP address (%s) - no Host header set", hostname)
                except ValueError:
                    # It's a hostname - set Host header
                    headers['Host'] = hostname
                    _LOGGER.debug("Fixed Host header to hostname: %s", headers['Host'])
        except Exception as e:
            _LOGGER.warning("Error handling Host header: %s", e)
        
        # Ensure User-Agent is explicitly set
        user_agent_set = any(key.lower() == 'user-agent' for key in headers.keys())
        if not user_agent_set:
            headers['User-Agent'] = ''
            _LOGGER.debug("Setting blank User-Agent (no User-Agent provided)")
        
        return headers

    def _log_request_details(self, method: str, target_url: str, headers: Dict, body: Optional[bytes]):
        """Log detailed request information."""
        _LOGGER.info("REQUEST to %s", target_url)
        _LOGGER.info("Request method: %s", method)
        
        if headers:
            _LOGGER.debug("Request headers being sent to target:")
            for header_name, header_value in headers.items():
                # Truncate very long header values for readability
                display_value = str(header_value)[:97] + "..." if len(str(header_value)) > 100 else header_value
                _LOGGER.debug("  %s: %s", header_name, display_value)
        
        if body:
            body_size = len(body)
            if body_size > 1024:
                _LOGGER.debug("Request body: %d bytes", body_size)
            else:
                body_preview = body[:100].decode('utf-8', errors='ignore')
                _LOGGER.debug("Request body: %d bytes - %s%s", body_size, body_preview, '...' if len(body) > 100 else '')

    def _log_response_details(self, response, target_url: str):
        """Log detailed response information."""
        _LOGGER.info("RESPONSE from %s", target_url)
        _LOGGER.info("Response status: %d", response.status)
        
        if response.headers:
            _LOGGER.debug("Response headers received from target:")
            for header_name, header_value in response.headers.items():
                display_value = str(header_value)[:97] + "..." if len(str(header_value)) > 100 else header_value
                _LOGGER.debug("  %s: %s", header_name, display_value)

    async def _make_request(self, method: str, url: str, headers: Dict, data: Optional[bytes], query_params: Dict):
        """Make the actual HTTP request with all advanced features."""
        # Parse configuration from query parameters
        skip_tls_checks = self._parse_skip_tls_checks(query_params)
        follow_redirects = query_params.get('follow_redirects', ['false'])[0].lower() in ['true', '1', 'yes']
        
        _LOGGER.debug("Redirect following: %s", "enabled" if follow_redirects else "disabled")
        
        # Create SSL context
        ssl_context = self._create_ssl_context(skip_tls_checks)
        
        # Create connector with SSL configuration
        connector = TCPConnector(ssl=ssl_context) if ssl_context else TCPConnector()
        timeout = ClientTimeout(total=30)
        
        try:
            async with ClientSession(timeout=timeout, connector=connector) as session:
                # Log request details
                self._log_request_details(method, url, headers, data)
                
                async with session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=data,
                    allow_redirects=follow_redirects
                ) as response:
                    # Log response details
                    self._log_response_details(response, url)
                    
                    # Read response content with streaming
                    content = await response.read()
                    
                    # Prepare response headers
                    response_headers = {}
                    excluded_response_headers = {
                        'connection', 'transfer-encoding', 'content-encoding'
                    }
                    
                    for key, value in response.headers.items():
                        if key.lower() not in excluded_response_headers:
                            response_headers[key] = value
                    
                    # Add custom response headers
                    for key, values in query_params.items():
                        if key.startswith('response_header[') and key.endswith(']'):
                            header_name = key[16:-1]  # Remove 'response_header[' and ']'
                            response_headers[header_name] = values[0]
                            _LOGGER.debug("Added custom response header: %s = %s", header_name, values[0])
                    
                    _LOGGER.info("Transferred %d bytes successfully", len(content))
                    
                    return {
                        'content': content,
                        'status': response.status,
                        'headers': response_headers,
                        'content_type': response.headers.get('Content-Type', 'text/plain')
                    }
        finally:
            await connector.close()

    def _send_error_response(self, code: int, message: str) -> web.Response:
        """Send a JSON error response."""
        error_response = {
            'error': message,
            'code': code,
            'timestamp': datetime.now().isoformat(),
            'instance': self.proxy_name
        }
        return web.Response(
            text=json.dumps(error_response, indent=2),
            status=code,
            headers={'Content-Type': 'application/json'}
        )

    async def get(self, request: Request) -> web.Response:
        """Handle GET request."""
        return await self._handle_request(request, "GET")

    async def post(self, request: Request) -> web.Response:
        """Handle POST request."""
        return await self._handle_request(request, "POST")

    async def _handle_request(self, request: Request, method: str) -> web.Response:
        """Handle HTTP request of any method with full HomieProxy functionality."""
        # Parse query parameters
        query_params = {k: v for k, v in request.query.items()}
        
        # Check token
        if not self._check_token(request):
            return self._send_error_response(401, "Unauthorized: Invalid or missing token")
        
        # Check client IP restrictions
        client_ip = self._get_client_ip(request)
        if not self._is_ip_allowed_in(client_ip):
            _LOGGER.warning("Client IP access denied: %s not allowed for instance '%s'", client_ip, self.proxy_name)
            return self._send_error_response(403, f"Forbidden: Client IP {client_ip} not allowed")
        
        _LOGGER.info("Client IP access allowed: %s for instance '%s'", client_ip, self.proxy_name)
        
        # Get target URL
        target_url = request.query.get("url")
        if not target_url:
            return self._send_error_response(400, "Bad Request: Missing 'url' parameter")
        
        # Check destination restrictions
        if not self._is_destination_allowed(target_url):
            _LOGGER.warning("Target URL access denied: %s not allowed for restrict_out '%s'", target_url, self.restrict_out)
            return self._send_error_response(403, f"Forbidden: Destination {target_url} not allowed")
        
        _LOGGER.info("Target URL access allowed: %s for restrict_out '%s'", target_url, self.restrict_out)
        
        # Get request body for methods that might have one
        data = None
        if method in ['POST', 'PUT', 'PATCH']:
            try:
                data = await request.read()
            except Exception as e:
                _LOGGER.error("Failed to read request body: %s", e)
                return self._send_error_response(400, "Bad Request: Failed to read body")
        
        # Prepare headers with all advanced features
        headers = self._prepare_headers(request, target_url, query_params)
        
        # Make the proxied request with all features
        try:
            result = await self._make_request(method, target_url, headers, data, query_params)
            
            return web.Response(
                body=result['content'],
                status=result['status'],
                headers=result['headers']
            )
            
        except ClientError as e:
            _LOGGER.error("Client error during proxy request: %s", e)
            return self._send_error_response(502, f"Bad Gateway: {str(e)}")
        except Exception as e:
            _LOGGER.error("Proxy request failed: %s", e)
            return self._send_error_response(502, f"Proxy Error: {str(e)}") 