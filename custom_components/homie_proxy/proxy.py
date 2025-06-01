"""Homie Proxy service for Home Assistant integration - using aiohttp for outbound requests and WebSocket support."""

import logging
import ipaddress
import socket
import ssl
import json
import urllib.parse
import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    import aiohttp
    import websockets
    from websockets.exceptions import WebSocketException
except ImportError:
    raise ImportError("'aiohttp' and 'websockets' libraries are required for HomieProxy")

from homeassistant.core import HomeAssistant
from homeassistant.components.http import HomeAssistantView
from aiohttp import web
from aiohttp.web_request import Request

from .const import PRIVATE_CIDRS, LOCAL_CIDRS

_LOGGER = logging.getLogger(__name__)

# Global registry to track all instances
_HOMIE_PROXY_INSTANCES = {}


class ProxyInstance:
    """Configuration for a proxy instance"""
    
    def __init__(self, name: str, tokens: List[str], restrict_out: str, restrict_in: Optional[str] = None):
        self.name = name
        self.restrict_out = restrict_out
        self.restrict_out_cidrs = []
        self.tokens = set(tokens)
        self.restrict_in_cidrs = []
        
        # Handle custom CIDR for restrict_out
        if restrict_out not in ['any', 'external', 'internal']:
            try:
                self.restrict_out_cidrs = [ipaddress.ip_network(restrict_out, strict=False)]
                self.restrict_out = 'custom'
            except ValueError:
                _LOGGER.warning("Invalid restrict_out CIDR: %s, defaulting to 'any'", restrict_out)
                self.restrict_out = 'any'
        
        # Handle restrict_in CIDR
        if restrict_in:
            try:
                self.restrict_in_cidrs = [ipaddress.ip_network(restrict_in, strict=False)]
            except ValueError:
                _LOGGER.warning("Invalid restrict_in CIDR: %s, ignoring", restrict_in)
                self.restrict_in_cidrs = []
    
    def is_client_access_allowed(self, client_ip: str) -> bool:
        """Check if client IP is allowed to access this proxy instance"""
        if not self.restrict_in_cidrs:
            return True  # No restrictions = allow all
            
        try:
            client_addr = ipaddress.ip_address(client_ip)
            return any(client_addr in cidr for cidr in self.restrict_in_cidrs)
        except (ipaddress.AddressValueError, ValueError):
            return False
    
    def is_target_url_allowed(self, target_url: str) -> bool:
        """Check if the target URL is allowed based on network access configuration"""
        try:
            parsed_url = urllib.parse.urlparse(target_url)
            hostname = parsed_url.hostname
            
            if not hostname:
                return False
            
            # Resolve hostname to IP for checking
            try:
                # For IP addresses, use directly
                target_ip = ipaddress.ip_address(hostname)
            except ValueError:
                # For hostnames, resolve to IP
                try:
                    resolved_ip = socket.gethostbyname(hostname)
                    target_ip = ipaddress.ip_address(resolved_ip)
                except (socket.gaierror, ValueError):
                    # If resolution fails, deny access for safety
                    return False
            
            # If restrict_out_cidrs is specified, use it (custom CIDR mode)
            if self.restrict_out_cidrs:
                return any(target_ip in cidr for cidr in self.restrict_out_cidrs)
            
            # Otherwise, use restrict_out mode
            if self.restrict_out == 'external':
                # Only allow external (non-private) IPs - use const.py definitions
                return not any(target_ip in ipaddress.ip_network(cidr) for cidr in PRIVATE_CIDRS)
            elif self.restrict_out == 'internal':
                # Only allow internal (private) IPs - use const.py definitions  
                return any(target_ip in ipaddress.ip_network(cidr) for cidr in PRIVATE_CIDRS)
            else:  # any
                # Allow everything (0.0.0.0/0)
                return True
                
        except Exception:
            # If anything goes wrong, deny access for safety
            return False
    
    def is_token_valid(self, token: str) -> bool:
        """Check if provided token is valid"""
        # If no tokens are configured, deny all access for security
        if not self.tokens:
            return False
        
        # Token must be provided and must be in the configured tokens list
        if not token:
            return False
            
        return token in self.tokens


def create_ssl_context(skip_tls_checks: List[str]) -> Optional[ssl.SSLContext]:
    """Create SSL context based on TLS bypass options"""
    if not skip_tls_checks:
        return None
    
    # Check for ALL option - disables all TLS verification
    if 'all' in [error.lower() for error in skip_tls_checks]:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        _LOGGER.info("SSL Context: Ignoring ALL TLS errors - complete TLS verification disabled")
        return ssl_context
    
    # Handle specific TLS error types
    ssl_context = ssl.create_default_context()
    context_modified = False
    
    # First, handle hostname checking (must be done BEFORE setting verify_mode to CERT_NONE)
    if any(check in skip_tls_checks for check in ['hostname_mismatch', 'expired_cert', 'self_signed']):
        ssl_context.check_hostname = False
        context_modified = True
    
    # Then handle certificate verification
    if any(check in skip_tls_checks for check in ['expired_cert', 'self_signed', 'cert_authority']):
        ssl_context.verify_mode = ssl.CERT_NONE
        context_modified = True
        
    if 'weak_cipher' in skip_tls_checks:
        ssl_context.set_ciphers('ALL:@SECLEVEL=0')
        context_modified = True
    
    if context_modified:
        _LOGGER.info(f"SSL Context: Ignoring specific TLS errors: {', '.join(skip_tls_checks)}")
        return ssl_context
    
    return None


async def handle_websocket_proxy(proxy_instance: ProxyInstance, request_data: dict) -> dict:
    """Handle WebSocket proxy connection"""
    try:
        target_url = request_data['target_url']
        headers = request_data['headers']
        query_params = request_data['query_params']
        
        # Convert HTTP(S) URL to WebSocket URL
        if target_url.startswith('https://'):
            ws_url = target_url.replace('https://', 'wss://', 1)
        elif target_url.startswith('http://'):
            ws_url = target_url.replace('http://', 'ws://', 1)
        else:
            return {'success': False, 'error': 'Invalid URL scheme for WebSocket', 'status': 400}
        
        # Configure SSL context for WebSocket
        skip_tls_checks_param = query_params.get('skip_tls_checks', [''])
        ssl_context = None
        if skip_tls_checks_param[0]:
            skip_tls_value = skip_tls_checks_param[0].lower()
            
            if skip_tls_value in ['true', '1', 'yes']:
                skip_tls_checks = ['all']
            else:
                skip_tls_checks = [error.strip().lower() for error in skip_tls_value.split(',')]
            
            ssl_context = create_ssl_context(skip_tls_checks)
        
        # Prepare WebSocket headers (exclude hop-by-hop headers)
        ws_headers = {}
        excluded_headers = {
            'connection', 'upgrade', 'sec-websocket-key', 'sec-websocket-version',
            'sec-websocket-protocol', 'sec-websocket-extensions', 'host'
        }
        
        for header, value in headers.items():
            if header.lower() not in excluded_headers:
                ws_headers[header] = value
        
        # Add custom request headers
        for key, values in query_params.items():
            if key.startswith('request_headers[') and key.endswith(']'):
                header_name = key[16:-1]
                ws_headers[header_name] = values[0]
        
        return {
            'success': True,
            'websocket_url': ws_url,
            'headers': ws_headers,
            'ssl_context': ssl_context
        }
        
    except Exception as e:
        _LOGGER.error("WebSocket proxy setup error: %s", e)
        return {'success': False, 'error': f"WebSocket setup error: {str(e)}", 'status': 500}


async def async_proxy_request(proxy_instance: ProxyInstance, request_data: dict, aiohttp_request: Optional[object] = None) -> dict:
    """Async proxy request function using aiohttp with clean streaming"""
    try:
        client_ip = request_data['client_ip']
        method = request_data['method']
        query_params = request_data['query_params']
        headers = request_data['headers']
        body = request_data['body']
        target_url = request_data['target_url']
        
        # Configure TLS/SSL settings
        skip_tls_checks_param = query_params.get('skip_tls_checks', [''])
        ssl_context = None
        if skip_tls_checks_param[0]:
            skip_tls_value = skip_tls_checks_param[0].lower()
            
            # Handle boolean-style values (true/false) and convert to 'all'
            if skip_tls_value in ['true', '1', 'yes']:
                skip_tls_checks = ['all']
                _LOGGER.info("TLS parameter 'true' detected, ignoring ALL TLS errors")
            else:
                # Parse comma-separated list of TLS errors to ignore
                skip_tls_checks = [error.strip().lower() for error in skip_tls_value.split(',')]
            
            ssl_context = create_ssl_context(skip_tls_checks)
        
        # Configure redirect following
        follow_redirects_param = query_params.get('follow_redirects', ['false'])
        follow_redirects = follow_redirects_param[0].lower() in ['true', '1', 'yes']
        
        # Configure timeout
        timeout = aiohttp.ClientTimeout(total=30)
        
        # Configure connector with SSL context
        connector = aiohttp.TCPConnector(ssl=ssl_context) if ssl_context else None
        
        # Create aiohttp session
        async with aiohttp.ClientSession(
            timeout=timeout,
            connector=connector
        ) as session:
            
            # Make the request
            request_kwargs = {
                'method': method,
                'url': target_url,
                'headers': headers,
                'allow_redirects': follow_redirects
            }
            
            # Add body for methods that support it
            if body is not None:
                request_kwargs['data'] = body
            
            async with session.request(**request_kwargs) as response:
                
                # Prepare response headers - pass through all headers from target
                response_headers = {}
                excluded_response_headers = {
                    'connection', 'transfer-encoding', 'content-encoding'
                }
                
                for header, value in response.headers.items():
                    if header.lower() not in excluded_response_headers:
                        response_headers[header] = value
                
                # Add custom response headers
                for key, values in query_params.items():
                    if key.startswith('response_header[') and key.endswith(']'):
                        header_name = key[16:-1]
                        response_headers[header_name] = values[0]
                
                # If we have the aiohttp request object, do streaming
                if aiohttp_request:
                    # Create streaming response
                    stream_response = web.StreamResponse(
                        status=response.status,
                        headers=response_headers
                    )
                    
                    await stream_response.prepare(aiohttp_request)
                    
                    bytes_transferred = 0
                    # Stream the response data
                    async for chunk in response.content.iter_chunked(8192):
                        if chunk:
                            await stream_response.write(chunk)
                            bytes_transferred += len(chunk)
                    
                    await stream_response.write_eof()
                    _LOGGER.info(f"Streamed response: {bytes_transferred} bytes")
                    
                    return {
                        'success': True,
                        'stream_response': stream_response
                    }
                else:
                    # Fallback for non-streaming responses
                    response_data = await response.read()
                    
                    return {
                        'success': True,
                        'status': response.status,
                        'headers': response_headers,
                        'data': response_data,
                        'is_websocket': False
                    }
                        
    except aiohttp.ClientError as e:
        return {'success': False, 'error': f"Bad Gateway: {str(e)}", 'status': 502}
            
    except asyncio.TimeoutError:
        return {'success': False, 'error': "Gateway Timeout", 'status': 504}
    
    except Exception as e:
        _LOGGER.error("Async proxy request error: %s", e)
        return {'success': False, 'error': "Internal server error", 'status': 500}


class HomieProxyRequestHandler:
    """Request handler that supports both HTTP and WebSocket proxying"""
    
    def __init__(self, proxy_instance: ProxyInstance):
        self.proxy_instance = proxy_instance
    
    def log_message(self, format_str, *args):
        """Log a message with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        _LOGGER.info(f"[{timestamp}] {format_str % args}")
    
    def get_client_ip(self, request: Request) -> str:
        """Get the real client IP address"""
        # Check for forwarded headers first
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.remote or '127.0.0.1'
    
    def send_error_response(self, code: int, message: str) -> web.Response:
        """Send an error response"""
        error_response = {
            'error': message,
            'code': code,
            'timestamp': datetime.now().isoformat(),
            'instance': self.proxy_instance.name
        }
        return web.Response(
            text=json.dumps(error_response, indent=2),
            status=code,
            headers={'Content-Type': 'application/json'}
        )
    
    def is_websocket_request(self, request: Request) -> bool:
        """Check if request is a WebSocket upgrade request"""
        connection = request.headers.get('Connection', '').lower()
        upgrade = request.headers.get('Upgrade', '').lower()
        return 'upgrade' in connection and upgrade == 'websocket'
    
    async def handle_websocket_request(self, request: Request, target_url: str, headers: dict, query_params: dict) -> web.Response:
        """Handle WebSocket proxy request"""
        try:
            request_data = {
                'target_url': target_url,
                'headers': headers,
                'query_params': query_params
            }
            
            # Get WebSocket configuration
            ws_result = await handle_websocket_proxy(self.proxy_instance, request_data)
            if not ws_result['success']:
                return self.send_error_response(ws_result['status'], ws_result['error'])
            
            ws_url = ws_result['websocket_url']
            ws_headers = ws_result['headers']
            ssl_context = ws_result['ssl_context']
            
            # Prepare WebSocket response
            ws = web.WebSocketResponse()
            await ws.prepare(request)
            
            self.log_message(f"WebSocket upgrade: Connecting to {ws_url}")
            
            # Create connection to target WebSocket
            try:
                # Configure websockets connection parameters
                connect_kwargs = {
                    'extra_headers': ws_headers,
                }
                if ssl_context:
                    connect_kwargs['ssl'] = ssl_context
                
                async with websockets.connect(ws_url, **connect_kwargs) as target_ws:
                    self.log_message(f"WebSocket connected to target: {ws_url}")
                    
                    # Create bidirectional message relay
                    async def relay_client_to_target():
                        try:
                            async for msg in ws:
                                if msg.type == aiohttp.WSMsgType.TEXT:
                                    await target_ws.send(msg.data)
                                elif msg.type == aiohttp.WSMsgType.BINARY:
                                    await target_ws.send(msg.data)
                                elif msg.type == aiohttp.WSMsgType.ERROR:
                                    break
                        except Exception as e:
                            self.log_message(f"WebSocket relay client->target error: {e}")
                    
                    async def relay_target_to_client():
                        try:
                            async for msg in target_ws:
                                if isinstance(msg, str):
                                    await ws.send_str(msg)
                                elif isinstance(msg, bytes):
                                    await ws.send_bytes(msg)
                        except Exception as e:
                            self.log_message(f"WebSocket relay target->client error: {e}")
                    
                    # Run both relay tasks concurrently
                    await asyncio.gather(
                        relay_client_to_target(),
                        relay_target_to_client(),
                        return_exceptions=True
                    )
                    
                    self.log_message("WebSocket connection closed")
                    
            except WebSocketException as e:
                self.log_message(f"WebSocket connection failed: {e}")
                await ws.close(code=aiohttp.WSMsgType.CLOSE, message=f"Target connection failed: {str(e)}".encode())
            except Exception as e:
                self.log_message(f"WebSocket error: {e}")
                await ws.close(code=aiohttp.WSMsgType.CLOSE, message=f"Connection error: {str(e)}".encode())
            
            return ws
            
        except Exception as e:
            self.log_message(f"WebSocket proxy error: {e}")
            return self.send_error_response(500, "WebSocket proxy error")
    
    async def handle_request(self, request: Request, method: str) -> web.Response:
        """Main request handler - supports both HTTP and WebSocket"""
        try:
            client_ip = self.get_client_ip(request)
            
            # Check IP access
            if not self.proxy_instance.is_client_access_allowed(client_ip):
                self.log_message(f"Client IP access denied: {client_ip} not allowed for instance '{self.proxy_instance.name}'")
                return self.send_error_response(403, "Access denied from your IP")
            
            self.log_message(f"Client IP access allowed: {client_ip} for instance '{self.proxy_instance.name}'")
            
            # Parse query parameters
            query_params = dict(request.query)
            # Convert single values to lists for compatibility
            for key, value in query_params.items():
                if isinstance(value, str):
                    query_params[key] = [value]
            
            # Get target URL
            target_urls = query_params.get('url', [])
            if not target_urls:
                return self.send_error_response(400, "Target URL required")
            
            target_url = target_urls[0]
            
            # Check target URL access
            if not self.proxy_instance.is_target_url_allowed(target_url):
                self.log_message(f"Target URL access denied: {target_url}")
                return self.send_error_response(403, "Access denied to the target URL")
            
            self.log_message(f"Target URL access allowed: {target_url}")
            
            # Check authentication
            tokens = query_params.get('token', [])
            token = tokens[0] if tokens else None
            
            if not self.proxy_instance.is_token_valid(token):
                self.log_message(f"Authentication failed: Invalid token for instance '{self.proxy_instance.name}'")
                return self.send_error_response(401, "Invalid or missing authentication token")
            
            self.log_message(f"Authentication successful for instance '{self.proxy_instance.name}'")
            
            # Handle Host header override logic
            override_host_header_param = query_params.get('override_host_header', [''])
            override_host_header = override_host_header_param[0] if override_host_header_param[0] else None
            
            # Parse target URL for hostname
            parsed_target = urllib.parse.urlparse(target_url)
            original_hostname = parsed_target.hostname
            
            # Prepare headers - start with original headers from client
            headers = dict(request.headers)
            
            # Add custom request headers first
            for key, values in query_params.items():
                if key.startswith('request_headers[') and key.endswith(']'):
                    header_name = key[16:-1]
                    headers[header_name] = values[0]
            
            # Handle Host header logic
            if override_host_header:
                headers['Host'] = override_host_header
                self.log_message(f"Override Host header set to: {override_host_header}")
            elif original_hostname:
                try:
                    ipaddress.ip_address(original_hostname)
                    headers.pop('Host', None)
                    self.log_message(f"Target is IP address ({original_hostname}) - no Host header set")
                except ValueError:
                    headers['Host'] = original_hostname
                    self.log_message(f"Fixed Host header to hostname: {headers['Host']}")
            
            # Ensure User-Agent is set
            user_agent_set = any(header.lower() == 'user-agent' for header in headers.keys())
            if not user_agent_set:
                headers['User-Agent'] = ''
                self.log_message("Setting blank User-Agent")
            
            # Check for WebSocket upgrade request
            if self.is_websocket_request(request):
                self.log_message(f"WebSocket upgrade request detected for {target_url}")
                return await self.handle_websocket_request(request, target_url, headers, query_params)
            
            # Handle regular HTTP request
            # Get request body for methods that might have a body
            body = None
            if method in ['POST', 'PUT', 'PATCH']:
                try:
                    body = await request.read()
                except Exception as e:
                    _LOGGER.error("Failed to read request body: %s", e)
                    return self.send_error_response(400, "Failed to read request body")
            
            # Log request details
            self.log_message(f"HTTP {method} REQUEST to {target_url}")
            if body:
                body_size = len(body)
                self.log_message(f"Request body: {body_size} bytes")
            
            # Prepare data for the async proxy request
            request_data = {
                'client_ip': client_ip,
                'method': method,
                'query_params': query_params,
                'headers': headers,
                'body': body,
                'target_url': target_url
            }
            
            # Make the async proxy request with streaming support
            result = await async_proxy_request(self.proxy_instance, request_data, request)
            
            if result['success']:
                # Check if we got a streaming response
                if 'stream_response' in result:
                    return result['stream_response']
                else:
                    # For non-streaming responses
                    response_data = result.get('data', b'')
                    bytes_transferred = len(response_data) if response_data else 0
                    self.log_message(f"Sending response: {bytes_transferred} bytes")
                    
                    return web.Response(
                        body=response_data,
                        status=result['status'],
                        headers=result['headers']
                    )
            else:
                return self.send_error_response(result['status'], result['error'])
            
        except Exception as e:
            self.log_message(f"Proxy error: {e}")
            return self.send_error_response(500, "Internal server error")


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
        self.proxy_instance: Optional[ProxyInstance] = None

    async def setup(self):
        """Set up the proxy service."""
        _LOGGER.info("Setting up Homie Proxy service: %s", self.name)
        
        # Create proxy instance
        self.proxy_instance = ProxyInstance(
            name=self.name,
            tokens=self.tokens,
            restrict_out=self.restrict_out,
            restrict_in=self.restrict_in
        )
        
        # Register this instance in the global registry
        _HOMIE_PROXY_INSTANCES[self.name] = self
        
        # Register debug view once (only for the first instance)
        if len(_HOMIE_PROXY_INSTANCES) == 1:
            debug_view = HomieProxyDebugView()
            debug_view.hass = self.hass
            self.hass.http.register_view(debug_view)
            _LOGGER.info("Registered HomieProxy debug endpoint at /api/homie_proxy/debug")
        
        # Create and register the HTTP view
        self.view = HomieProxyView(proxy_instance=self.proxy_instance)
        self.view.hass = self.hass
        self.hass.http.register_view(self.view)
        
        _LOGGER.info(
            "Homie Proxy service '%s' is ready at /api/homie_proxy/%s with %d token(s) and WebSocket support", 
            self.name, self.name, len(self.tokens)
        )

    async def update(self, tokens: List[str], restrict_out: str, restrict_in: Optional[str] = None):
        """Update the proxy configuration."""
        self.tokens = tokens
        self.restrict_out = restrict_out
        self.restrict_in = restrict_in
        
        # Update the proxy instance
        if self.proxy_instance:
            self.proxy_instance.tokens = set(tokens)
            self.proxy_instance.restrict_out = restrict_out
            
            # Handle custom CIDR for restrict_out
            self.proxy_instance.restrict_out_cidrs = []
            if restrict_out not in ['any', 'external', 'internal']:
                try:
                    self.proxy_instance.restrict_out_cidrs = [ipaddress.ip_network(restrict_out, strict=False)]
                    self.proxy_instance.restrict_out = 'custom'
                except ValueError:
                    _LOGGER.warning("Invalid restrict_out CIDR: %s, defaulting to 'any'", restrict_out)
                    self.proxy_instance.restrict_out = 'any'
            
            # Handle restrict_in CIDR
            self.proxy_instance.restrict_in_cidrs = []
            if restrict_in:
                try:
                    self.proxy_instance.restrict_in_cidrs = [ipaddress.ip_network(restrict_in, strict=False)]
                except ValueError:
                    _LOGGER.warning("Invalid restrict_in CIDR: %s, ignoring", restrict_in)
                    self.proxy_instance.restrict_in_cidrs = []
            
        _LOGGER.info(
            "Updated Homie Proxy service '%s' with %d token(s)", 
            self.name, len(self.tokens)
        )

    async def cleanup(self):
        """Clean up the proxy service."""
        _LOGGER.info("Cleaning up Homie Proxy service: %s", self.name)
        
        # Remove from global registry
        _HOMIE_PROXY_INSTANCES.pop(self.name, None)


class HomieProxyView(HomeAssistantView):
    """HTTP view for Homie Proxy with aiohttp and WebSocket support."""

    def __init__(self, proxy_instance: ProxyInstance):
        """Initialize the view."""
        self.proxy_instance = proxy_instance
        self.handler = HomieProxyRequestHandler(proxy_instance)
        
        # Set view properties
        self.url = f"/api/homie_proxy/{proxy_instance.name}"
        self.name = f"api:homie_proxy:{proxy_instance.name}"
        self.requires_auth = False  # We handle auth with tokens

    async def get(self, request: Request, **kwargs) -> web.Response:
        """Handle GET requests."""
        return await self.handler.handle_request(request, "GET")
    
    async def post(self, request: Request, **kwargs) -> web.Response:
        """Handle POST requests."""
        return await self.handler.handle_request(request, "POST")
    
    async def put(self, request: Request, **kwargs) -> web.Response:
        """Handle PUT requests."""
        return await self.handler.handle_request(request, "PUT")
    
    async def patch(self, request: Request, **kwargs) -> web.Response:
        """Handle PATCH requests."""
        return await self.handler.handle_request(request, "PATCH")
    
    async def delete(self, request: Request, **kwargs) -> web.Response:
        """Handle DELETE requests."""
        return await self.handler.handle_request(request, "DELETE")
    
    async def head(self, request: Request, **kwargs) -> web.Response:
        """Handle HEAD requests."""
        return await self.handler.handle_request(request, "HEAD")
    
    async def options(self, request: Request, **kwargs) -> web.Response:
        """Handle OPTIONS requests."""
        return await self.handler.handle_request(request, "OPTIONS")


class HomieProxyDebugView(HomeAssistantView):
    """Debug view for HomieProxy showing all instances and configuration."""
    
    url = "/api/homie_proxy/debug"
    name = "api:homie_proxy:debug"
    requires_auth = False
    
    async def get(self, request: Request) -> web.Response:
        """Handle GET request for debug information."""
        debug_info = {
            "timestamp": datetime.now().isoformat(),
            "instances": {}
        }
        
        # Collect information about all instances
        for instance_name, service in _HOMIE_PROXY_INSTANCES.items():
            debug_info["instances"][instance_name] = {
                "name": service.name,
                "tokens": service.tokens,
                "restrict_out": service.restrict_out,
                "restrict_in": service.restrict_in,
                "endpoint_url": f"/api/homie_proxy/{service.name}",
                "status": "active" if service.view else "inactive",
                "websocket_support": True
            }
        
        # Add system information
        debug_info["system"] = {
            "private_cidrs": PRIVATE_CIDRS,
            "local_cidrs": LOCAL_CIDRS,
            "available_restrictions": ["any", "external", "internal", "custom"],
            "proxy_implementation": "aiohttp_with_websocket_support",
            "features": [
                "HTTP/HTTPS proxying",
                "WebSocket proxying", 
                "Streaming support",
                "Custom headers",
                "TLS bypass options",
                "Authentication",
                "Network access control"
            ]
        }
        
        # Format as pretty JSON
        response_text = json.dumps(debug_info, indent=2, ensure_ascii=False)
        
        return web.Response(
            text=response_text,
            content_type="application/json",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache"
            }
        ) 