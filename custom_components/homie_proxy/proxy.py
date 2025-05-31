"""Homie Proxy service for Home Assistant integration - using standalone proxy code."""

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
    import requests
    from requests.adapters import HTTPAdapter
    import urllib3
    from urllib3.exceptions import InsecureRequestWarning
    # Note: SubjectAltNameWarning may not exist in newer urllib3 versions
    try:
        from urllib3.exceptions import SubjectAltNameWarning
    except ImportError:
        SubjectAltNameWarning = None
except ImportError:
    raise ImportError("'requests' library is required for HomieProxy")

from homeassistant.core import HomeAssistant
from homeassistant.components.http import HomeAssistantView
from aiohttp import web
from aiohttp.web_request import Request

from .const import PRIVATE_CIDRS, LOCAL_CIDRS

_LOGGER = logging.getLogger(__name__)

# Global registry to track all instances
_HOMIE_PROXY_INSTANCES = {}


class CustomHTTPSAdapter(HTTPAdapter):
    """Custom HTTPS adapter that allows selective TLS error ignoring"""
    
    def __init__(self, skip_tls_checks=None, *args, **kwargs):
        self.skip_tls_checks = skip_tls_checks or []
        super().__init__(*args, **kwargs)
    
    def init_poolmanager(self, *args, **kwargs):
        # Configure SSL context based on ignored errors
        ssl_context = ssl.create_default_context()
        
        # Check for ALL option - disables all TLS verification
        if 'all' in [error.lower() for error in self.skip_tls_checks]:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            kwargs['ssl_context'] = ssl_context
            # Suppress all urllib3 warnings for ALL option
            urllib3.disable_warnings(InsecureRequestWarning)
            if SubjectAltNameWarning is not None:
                urllib3.disable_warnings(SubjectAltNameWarning)
        else:
            # Handle specific TLS error types
            if 'expired_cert' in self.skip_tls_checks:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            elif 'self_signed' in self.skip_tls_checks:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            elif 'hostname_mismatch' in self.skip_tls_checks:
                ssl_context.check_hostname = False
            elif 'cert_authority' in self.skip_tls_checks:
                ssl_context.verify_mode = ssl.CERT_NONE
            elif 'weak_cipher' in self.skip_tls_checks:
                ssl_context.set_ciphers('ALL:@SECLEVEL=0')
            
            # If any TLS errors should be ignored, apply the configuration
            if self.skip_tls_checks:
                kwargs['ssl_context'] = ssl_context
                # Suppress specific urllib3 warnings
                if 'expired_cert' in self.skip_tls_checks or 'self_signed' in self.skip_tls_checks:
                    urllib3.disable_warnings(InsecureRequestWarning)
                if 'hostname_mismatch' in self.skip_tls_checks and SubjectAltNameWarning is not None:
                    urllib3.disable_warnings(SubjectAltNameWarning)
        
        return super().init_poolmanager(*args, **kwargs)


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
        if not self.tokens:
            return True  # No tokens required
        return token in self.tokens


def sync_proxy_request(proxy_instance: ProxyInstance, request_data: dict) -> dict:
    """Synchronous proxy request function that runs in a thread executor"""
    try:
        client_ip = request_data['client_ip']
        method = request_data['method']
        query_params = request_data['query_params']
        headers = request_data['headers']
        body = request_data['body']
        target_url = request_data['target_url']
        
        # All the logging and validation has already been done
        # This function just does the actual HTTP request
        
        # Prepare request session
        session = requests.Session()
        
        # Clear any default User-Agent from the session
        session.headers.pop('User-Agent', None)
        
        # Configure TLS error handling
        skip_tls_checks_param = query_params.get('skip_tls_checks', [''])
        if skip_tls_checks_param[0]:
            skip_tls_value = skip_tls_checks_param[0].lower()
            
            # Handle boolean-style values (true/false) and convert to 'all'
            if skip_tls_value in ['true', '1', 'yes']:
                skip_tls_checks = ['all']
                _LOGGER.info("TLS parameter 'true' detected, ignoring ALL TLS errors")
            else:
                # Parse comma-separated list of TLS errors to ignore
                skip_tls_checks = [error.strip().lower() for error in skip_tls_value.split(',')]
            
            # Check for ALL option - completely disable TLS verification
            if 'all' in skip_tls_checks:
                session.verify = False
                urllib3.disable_warnings(InsecureRequestWarning)
                if SubjectAltNameWarning is not None:
                    urllib3.disable_warnings(SubjectAltNameWarning)
                _LOGGER.info("Ignoring ALL TLS errors - complete TLS verification disabled")
            else:
                # Mount custom HTTPS adapter for specific error types
                https_adapter = CustomHTTPSAdapter(skip_tls_checks=skip_tls_checks)
                session.mount('https://', https_adapter)
                _LOGGER.info(f"Ignoring specific TLS errors: {', '.join(skip_tls_checks)}")
        
        # Configure redirect following
        follow_redirects_param = query_params.get('follow_redirects', ['false'])
        follow_redirects = follow_redirects_param[0].lower() in ['true', '1', 'yes']
        
        # Make the request
        request_kwargs = {
            'method': method,
            'url': target_url,
            'headers': headers,
            'stream': True,
            'timeout': 30,
            'allow_redirects': follow_redirects
        }
        
        # Add body for methods that support it
        if body is not None:
            request_kwargs['data'] = body
        
        try:
            response = session.request(**request_kwargs)
            
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
                    header_name = key[16:-1]  # Remove 'response_header[' and ']'
                    response_headers[header_name] = values[0]
            
            # Return response object for streaming - don't buffer content
            return {
                'success': True,
                'response': response,  # Return the response object itself
                'status': response.status_code,
                'headers': response_headers,
                'session': session  # Keep session alive for streaming
            }
                    
        except requests.exceptions.RequestException as e:
            session.close()
            return {'success': False, 'error': f"Bad Gateway: {str(e)}", 'status': 502}
                
        except OSError as e:
            session.close()
            return {'success': False, 'error': "Internal server error", 'status': 500}
        
    except Exception as e:
        return {'success': False, 'error': "Internal server error", 'status': 500}


async def stream_response_content(response, session):
    """Async generator to stream response content"""
    try:
        # Stream in 64KB chunks for better performance with large files
        for chunk in response.iter_content(chunk_size=65536):
            if chunk:
                yield chunk
    finally:
        # Always close the session when streaming is done
        session.close()


class HomieProxyRequestHandler:
    """Request handler that mimics BaseHTTPRequestHandler but works with aiohttp"""
    
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
    
    async def handle_request(self, request: Request, method: str) -> web.Response:
        """Main request handler - uses method parameter for HTTP method"""
        try:
            client_ip = self.get_client_ip(request)
            
            # Check IP access
            if not self.proxy_instance.is_client_access_allowed(client_ip):
                self.log_message(f"Client IP access denied: {client_ip} not allowed for instance '{self.proxy_instance.name}'")
                if self.proxy_instance.restrict_in_cidrs:
                    allowed_cidrs_str = ', '.join(str(cidr) for cidr in self.proxy_instance.restrict_in_cidrs)
                    self.log_message(f"Instance allowed CIDRs: {allowed_cidrs_str}")
                else:
                    self.log_message("Instance has no restrict_in_cidrs specified - allowing all IPs (0.0.0.0/0)")
                return self.send_error_response(403, "Access denied from your IP")
            
            self.log_message(f"Client IP access allowed: {client_ip} for instance '{self.proxy_instance.name}'")
            
            # Parse query parameters
            query_params = dict(request.query)
            # Convert single values to lists for compatibility with standalone code
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
                if self.proxy_instance.restrict_out_cidrs:
                    cidrs_str = ', '.join(str(cidr) for cidr in self.proxy_instance.restrict_out_cidrs)
                    self.log_message(f"Target URL access denied: {target_url} not in restrict_out_cidrs '{cidrs_str}'")
                else:
                    self.log_message(f"Target URL access denied: {target_url} not allowed for restrict_out '{self.proxy_instance.restrict_out}'")
                return self.send_error_response(403, "Access denied to the target URL")
            
            if self.proxy_instance.restrict_out_cidrs:
                cidrs_str = ', '.join(str(cidr) for cidr in self.proxy_instance.restrict_out_cidrs)
                self.log_message(f"Target URL access allowed: {target_url} matches restrict_out_cidrs '{cidrs_str}'")
            else:
                self.log_message(f"Target URL access allowed: {target_url} for restrict_out '{self.proxy_instance.restrict_out}'")
            
            # Check authentication
            tokens = query_params.get('token', [])
            token = tokens[0] if tokens else None
            
            # TEMPORARY: Allow unauthenticated access for testing
            # if not self.proxy_instance.is_token_valid(token):
            #     return self.send_error_response(401, "Invalid or missing token")
            
            # Get request body for methods that might have a body
            body = None
            if method in ['POST', 'PUT', 'PATCH']:
                try:
                    body = await request.read()
                except Exception as e:
                    _LOGGER.error("Failed to read request body: %s", e)
                    return self.send_error_response(400, "Failed to read request body")
            
            # Handle Host header override logic
            override_host_header_param = query_params.get('override_host_header', [''])
            override_host_header = override_host_header_param[0] if override_host_header_param[0] else None
            
            # Parse target URL for hostname
            parsed_target = urllib.parse.urlparse(target_url)
            original_hostname = parsed_target.hostname
            
            # Prepare headers - start with original headers from client
            headers = dict(request.headers)
            
            # Add custom request headers first (so they can override defaults)
            for key, values in query_params.items():
                if key.startswith('request_headers[') and key.endswith(']'):
                    header_name = key[16:-1]  # Remove 'request_headers[' and ']'
                    headers[header_name] = values[0]
            
            # Handle Host header logic AFTER custom headers so override takes precedence
            if override_host_header:
                # Use explicit override
                headers['Host'] = override_host_header
                self.log_message(f"Override Host header set to: {override_host_header}")
            elif original_hostname:
                # Check if the hostname is an IP address
                try:
                    ipaddress.ip_address(original_hostname)
                    # It's an IP address - don't set Host header
                    headers.pop('Host', None)
                    self.log_message(f"Target is IP address ({original_hostname}) - no Host header set")
                except ValueError:
                    # It's a hostname - set Host header to hostname only (no port)
                    headers['Host'] = original_hostname
                    self.log_message(f"Fixed Host header to hostname: {headers['Host']}")
            
            # Always ensure User-Agent is explicitly set (use blank if none provided)
            user_agent_set = False
            for header_name in headers.keys():
                if header_name.lower() == 'user-agent':
                    user_agent_set = True
                    break
            
            if not user_agent_set:
                headers['User-Agent'] = ''
                self.log_message("Setting blank User-Agent (no User-Agent provided)")
            else:
                self.log_message(f"User-Agent already provided: {headers.get('User-Agent', headers.get('user-agent', 'NOT FOUND'))}")
            
            # Log the request details
            self.log_message(f"REQUEST to {target_url}")
            self.log_message(f"Request method: {method}")
            if headers:
                self.log_message("Request headers being sent to target:")
                for header_name, header_value in headers.items():
                    # Truncate very long header values for readability
                    if len(str(header_value)) > 100:
                        display_value = str(header_value)[:97] + "..."
                    else:
                        display_value = header_value
                    self.log_message(f"  {header_name}: {display_value}")
            else:
                self.log_message("No custom headers being sent to target")
            
            if body:
                body_size = len(body)
                if body_size > 1024:
                    self.log_message(f"Request body: {body_size} bytes")
                else:
                    self.log_message(f"Request body: {body_size} bytes - {body[:100]}{'...' if len(body) > 100 else ''}")
            
            # Prepare data for the synchronous function
            request_data = {
                'client_ip': client_ip,
                'method': method,
                'query_params': query_params,
                'headers': headers,
                'body': body,
                'target_url': target_url
            }
            
            # Run the synchronous proxy request in a thread executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                sync_proxy_request, 
                self.proxy_instance, 
                request_data
            )
            
            if result['success']:
                # For successful responses, create a streaming response
                response_obj = result['response']
                session = result['session']
                
                # Create a streaming response
                stream_response = web.StreamResponse(
                    status=result['status'],
                    headers=result['headers']
                )
                
                # Prepare the streaming response
                await stream_response.prepare(request)
                
                bytes_transferred = 0
                try:
                    # Stream content in chunks using thread executor
                    loop = asyncio.get_event_loop()
                    
                    # Create iterator once
                    content_iter = response_obj.iter_content(chunk_size=65536)
                    
                    while True:
                        # Get next chunk in thread executor to avoid blocking
                        try:
                            chunk = await loop.run_in_executor(None, lambda: next(content_iter, None))
                            if chunk is None:
                                break
                            await stream_response.write(chunk)
                            bytes_transferred += len(chunk)
                        except StopIteration:
                            break
                    
                    self.log_message(f"Streamed {bytes_transferred} bytes successfully")
                    
                finally:
                    # Always close the session when done
                    session.close()
                
                return stream_response
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
        
        # Create proxy instance using standalone proxy logic
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
            "Homie Proxy service '%s' is ready at /api/homie_proxy/%s with %d token(s)", 
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
        
        # Note: Home Assistant doesn't provide a way to unregister views
        # The view will be cleaned up when HA restarts


class HomieProxyView(HomeAssistantView):
    """HTTP view for Homie Proxy using standalone proxy code."""

    def __init__(self, proxy_instance: ProxyInstance):
        """Initialize the view."""
        self.proxy_instance = proxy_instance
        self.handler = HomieProxyRequestHandler(proxy_instance)
        
        # Set view properties
        self.url = f"/api/homie_proxy/{proxy_instance.name}"
        self.name = f"api:homie_proxy:{proxy_instance.name}"
        self.requires_auth = False  # We handle auth with tokens

    async def get(self, request: Request) -> web.Response:
        """Handle GET request."""
        return await self.handler.handle_request(request, "GET")

    async def post(self, request: Request) -> web.Response:
        """Handle POST request."""
        return await self.handler.handle_request(request, "POST")

    async def put(self, request: Request) -> web.Response:
        """Handle PUT request."""
        return await self.handler.handle_request(request, "PUT")

    async def patch(self, request: Request) -> web.Response:
        """Handle PATCH request."""
        return await self.handler.handle_request(request, "PATCH")

    async def delete(self, request: Request) -> web.Response:
        """Handle DELETE request."""
        return await self.handler.handle_request(request, "DELETE")

    async def head(self, request: Request) -> web.Response:
        """Handle HEAD request."""
        return await self.handler.handle_request(request, "HEAD")


class HomieProxyDebugView(HomeAssistantView):
    """Debug view for HomieProxy showing all instances and configuration."""
    
    url = "/api/homie_proxy/debug"
    name = "api:homie_proxy:debug"
    requires_auth = False  # For debugging, but could be secured if needed
    
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
                "tokens": service.tokens,  # Show full tokens
                "restrict_out": service.restrict_out,
                "restrict_in": service.restrict_in,
                "endpoint_url": f"/api/homie_proxy/{service.name}",
                "status": "active" if service.view else "inactive"
            }
        
        # Add system information
        debug_info["system"] = {
            "private_cidrs": PRIVATE_CIDRS,
            "local_cidrs": LOCAL_CIDRS,
            "available_restrictions": ["any", "external", "internal", "custom"],
            "proxy_implementation": "standalone_proxy_code_with_thread_executor"
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