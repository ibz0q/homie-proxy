#!/usr/bin/env python3
"""
Homie Proxy Server
Minimal dependencies, configurable instances with authentication and restrictions.

This module can be used both as a standalone script and as an importable module.

Example usage as a module:
    from homie_proxy import HomieProxyServer, ProxyInstance
    
    # Create and configure server
    server = HomieProxyServer('my_config.json')
    
    # Run server
    server.run(host='localhost', port=8080)

Example programmatic configuration:
    from homie_proxy import HomieProxyServer, create_proxy_config
    
    # Create configuration programmatically
    config = create_proxy_config({
        'default': {
            'restrict_out': 'both',
            'tokens': ['my-token'],
            'restrict_in_cidrs': []
        }
    })
    
    # Create server with config
    server = HomieProxyServer()
    server.instances = config
    server.run()
"""

import json
import ipaddress
import ssl
import urllib.parse
import asyncio
import aiohttp
from aiohttp import web
from datetime import datetime
from typing import Dict, List, Optional
import socket
import os
import time

try:
    import websockets
except ImportError:
    print("Warning: 'websockets' library not found. WebSocket proxying will be disabled.")
    websockets = None

# Module exports for when used as an import
__all__ = [
    'HomieProxyServer',
    'ProxyInstance', 
    'HomieProxyRequestHandler',
    'create_proxy_config',
    'create_default_config'
]

def create_proxy_config(instances_dict: Dict) -> Dict[str, 'ProxyInstance']:
    """
    Create proxy instances from a configuration dictionary.
    
    Args:
        instances_dict: Dictionary mapping instance names to configuration dicts
        
    Returns:
        Dictionary mapping instance names to ProxyInstance objects
        
    Example:
        config = create_proxy_config({
            'api': {
                'restrict_out': 'external',
                'tokens': ['api-key-123'],
                'restrict_in_cidrs': ['192.168.1.0/24']
            },
            'internal': {
                'restrict_out': 'internal',
                'tokens': [],
                'restrict_in_cidrs': []
            }
        })
    """
    instances = {}
    for name, config in instances_dict.items():
        instances[name] = ProxyInstance(name, config)
    return instances

def create_default_config() -> Dict:
    """
    Create a default configuration dictionary.
    
    Returns:
        Default configuration dictionary
    """
    return {
        "instances": {
            "default": {
                "restrict_out": "both",
                "tokens": ["your-secret-token-here"],
                "restrict_in_cidrs": [],
                "timeout": 300
            },
            "internal-only": {
                "restrict_out": "internal",
                "tokens": [],
                "restrict_in_cidrs": [],
                "timeout": 300
            },
            "custom-networks": {
                "restrict_out": "both",
                "restrict_out_cidrs": ["8.8.8.0/24", "1.1.1.0/24"],
                "tokens": ["custom-token"],
                "restrict_in_cidrs": [],
                "timeout": 300
            }
        }
    }

def create_ssl_context(skip_tls_checks: List[str]) -> Optional[ssl.SSLContext]:
    """Create SSL context based on TLS checks to skip"""
    if not skip_tls_checks:
        return None
    
    ssl_context = ssl.create_default_context()
    
    # Check for ALL option - disables all TLS verification
    if 'all' in [error.lower() for error in skip_tls_checks]:
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context
    
    # Handle specific TLS error types
    modified = False
    if any(check in skip_tls_checks for check in ['expired_cert', 'self_signed', 'cert_authority']):
        ssl_context.verify_mode = ssl.CERT_NONE
        modified = True
    
    if 'hostname_mismatch' in skip_tls_checks:
        ssl_context.check_hostname = False
        modified = True
    
    if 'weak_cipher' in skip_tls_checks:
        ssl_context.set_ciphers('ALL:@SECLEVEL=0')
        modified = True
    
    return ssl_context if modified else None


async def async_proxy_request(proxy_instance: 'ProxyInstance', request_data: dict) -> dict:
    """Async proxy request function using aiohttp"""
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
                print(f"TLS parameter 'true' detected, ignoring ALL TLS errors")
            else:
                # Parse comma-separated list of TLS errors to ignore
                skip_tls_checks = [error.strip().lower() for error in skip_tls_value.split(',')]
            
            ssl_context = create_ssl_context(skip_tls_checks)
        
        # Configure redirect following
        follow_redirects_param = query_params.get('follow_redirects', ['false'])
        follow_redirects = follow_redirects_param[0].lower() in ['true', '1', 'yes']
        
        # Configure timeout - configurable via query parameter
        timeout_param = query_params.get('timeout', [''])
        if timeout_param[0] and timeout_param[0].isdigit():
            timeout_seconds = int(timeout_param[0])
        else:
            # Use proxy instance timeout as default
            timeout_seconds = proxy_instance.timeout
        
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        print(f"Using timeout: {timeout_seconds}s for request")
        
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
                response_header = {}
                excluded_response_header = {
                    'connection', 'transfer-encoding', 'content-encoding'
                }
                
                for header, value in response.headers.items():
                    if header.lower() not in excluded_response_header:
                        response_header[header] = value
                
                # Add custom response headers
                for key, values in query_params.items():
                    if key.startswith('response_header[') and key.endswith(']'):
                        header_name = key[16:-1]
                        response_header[header_name] = values[0]
                
                # Read response data
                response_data = await response.read()
                
                return {
                    'success': True,
                    'status': response.status,
                    'headers': response_header,
                    'data': response_data
                }
                        
    except aiohttp.ClientError as e:
        return {'success': False, 'error': f"Bad Gateway: {str(e)}", 'status': 502}
            
    except asyncio.TimeoutError:
        return {'success': False, 'error': "Gateway Timeout", 'status': 504}
    
    except Exception as e:
        print(f"Async proxy request error: {e}")
        return {'success': False, 'error': "Internal server error", 'status': 500}


class ProxyInstance:
    """Configuration for a proxy instance"""
    
    def __init__(self, name: str, config: Dict):
        self.name = name
        # New naming scheme for network access control
        self.restrict_out = config.get('restrict_out', 'both')  # external, internal, both
        self.restrict_out_cidrs = [ipaddress.ip_network(cidr) for cidr in config.get('restrict_out_cidrs', [])]
        self.tokens = set(config.get('tokens', []))
        self.restrict_in_cidrs = [ipaddress.ip_network(cidr) for cidr in config.get('restrict_in_cidrs', [])]
        self.timeout = config.get('timeout', 300)  # Default 5 minutes
        
        # Backward compatibility - support old parameter names
        if 'access_mode' in config:
            self.restrict_out = config['access_mode']
        if 'allowed_networks_out' in config:
            self.restrict_out = config['allowed_networks_out']
        if 'allowed_cidrs' in config:
            self.restrict_in_cidrs = [ipaddress.ip_network(cidr) for cidr in config['allowed_cidrs']]
        if 'restrict_access_to_cidrs' in config:
            self.restrict_in_cidrs = [ipaddress.ip_network(cidr) for cidr in config['restrict_access_to_cidrs']]
        if 'allowed_networks_cidrs' in config:
            self.restrict_out_cidrs = [ipaddress.ip_network(cidr) for cidr in config['allowed_networks_cidrs']]
        if 'allowed_networks_out_cidrs' in config:
            self.restrict_out_cidrs = [ipaddress.ip_network(cidr) for cidr in config['allowed_networks_out_cidrs']]
    
    def is_client_access_allowed(self, client_ip: str) -> bool:
        """Check if client IP is allowed to access this proxy instance"""
        try:
            ip = ipaddress.ip_address(client_ip)
            
            # If restrict_in_cidrs is specified, check against them
            if self.restrict_in_cidrs:
                return any(ip in cidr for cidr in self.restrict_in_cidrs)
            else:
                # If not specified, allow all IPs (0.0.0.0/0)
                return True
                
        except ValueError:
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
            
            # If restrict_out_cidrs is specified, use it (overrides restrict_out)
            if self.restrict_out_cidrs:
                return any(target_ip in cidr for cidr in self.restrict_out_cidrs)
            
            # Otherwise, use restrict_out mode
            if self.restrict_out == 'external':
                # Only allow external (non-private) IPs
                return not target_ip.is_private and not target_ip.is_loopback
            elif self.restrict_out == 'internal':
                # Only allow internal (private/loopback) IPs  
                return target_ip.is_private or target_ip.is_loopback
            else:  # both
                # Allow everything (0.0.0.0/0)
                return True
                
        except Exception:
            # If anything goes wrong, deny access for safety
            return False
    
    def is_token_valid(self, token: str) -> bool:
        """Check if a token is valid for this instance"""
        # If no tokens are configured, allow all requests
        if not self.tokens:
            return True
        return token in self.tokens


class HomieProxyRequestHandler:
    """Async request handler that processes proxy requests"""
    
    def __init__(self, proxy_instance: ProxyInstance):
        self.proxy_instance = proxy_instance
    
    def log_message(self, format_str, *args):
        """Log a message with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {format_str % args}")
    
    def get_client_ip(self, request: web.Request) -> str:
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
    
    async def handle_request(self, request: web.Request) -> web.Response:
        """Main request handler for all HTTP methods"""
        try:
            method = request.method
            client_ip = self.get_client_ip(request)
            
            # Parse query parameters
            query_params = dict(request.query)
            # Convert single values to lists for consistency with old code
            for key, value in query_params.items():
                if not isinstance(value, list):
                    query_params[key] = [value]
            
            # Get target URL
            target_urls = query_params.get('url', [])
            if not target_urls:
                return self.send_error_response(400, "Target URL required")
            
            target_url = target_urls[0]
            
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
            if not self.proxy_instance.is_token_valid(token):
                return self.send_error_response(401, "Invalid or missing token")
            
            # Get request body
            body = None
            if request.can_read_body:
                body = await request.read()
            
            # Parse target URL for hostname
            parsed_target = urllib.parse.urlparse(target_url)
            original_hostname = parsed_target.hostname
            
            # Prepare headers - start with original headers from client
            headers = dict(request.headers)
            
            # Remove aiohttp-specific headers that shouldn't be forwarded
            excluded_headers = {
                'host'  # Will be set properly below
            }
            for header in excluded_headers:
                headers.pop(header, None)
            
            # Check if Host header was provided via request_header[Host] parameter
            host_header_override = None
            for key, values in query_params.items():
                if key.startswith('request_header[') and key.endswith(']'):
                    header_name = key[15:-1]  # Remove 'request_header[' and ']'
                    if header_name.lower() == 'host':
                        host_header_override = values[0]
                    else:
                        headers[header_name] = values[0]
            
            # Handle Host header logic AFTER custom headers so override takes precedence
            if host_header_override:
                # Use explicit override
                headers['Host'] = host_header_override
                self.log_message(f"Host header override set to: {host_header_override}")
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
                    self.log_message(f"Set Host header to hostname: {headers['Host']}")
            
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
            
            # Prepare request data for async proxy
            request_data = {
                'client_ip': client_ip,
                'method': method,
                'query_params': query_params,
                'headers': headers,
                'body': body,
                'target_url': target_url
            }
            
            # Log the request
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
                    self.log_message(f"Request body: {body_size} bytes - {body[:100]}{b'...' if len(body) > 100 else b''}")
            
            # Make the async proxy request
            response_data = await async_proxy_request(self.proxy_instance, request_data)
            
            if not response_data['success']:
                return self.send_error_response(
                    response_data.get('status', 500),
                    response_data['error']
                )
            
            # Log the response
            self.log_message(f"RESPONSE from {target_url}")
            self.log_message(f"Response status: {response_data['status']}")
            if response_data['headers']:
                self.log_message("Response headers received from target:")
                for header_name, header_value in response_data['headers'].items():
                    # Truncate very long header values for readability
                    if len(str(header_value)) > 100:
                        display_value = str(header_value)[:97] + "..."
                    else:
                        display_value = header_value
                    self.log_message(f"  {header_name}: {display_value}")
            else:
                self.log_message("No response headers received from target")
            
            # Create and return response
            response = web.Response(
                body=response_data['data'],
                status=response_data['status'],
                headers=response_data['headers']
            )
            
            data_size = len(response_data['data'])
            self.log_message(f"Returned response: {data_size} bytes")
            
            return response
            
        except Exception as e:
            self.log_message(f"Proxy error: {e}")
            return self.send_error_response(500, "Internal server error")


class HomieProxyServer:
    """
    Main homie proxy server using aiohttp.
    
    Can be used with file-based configuration or programmatic configuration.
    
    Example file-based usage:
        server = HomieProxyServer('my_config.json')
        server.run()
    
    Example programmatic usage:
        server = HomieProxyServer()
        server.add_instance('api', {
            'restrict_out': 'external',
            'tokens': ['secret-key'],
            'restrict_in_cidrs': []
        })
        server.run(host='localhost', port=8080)
    """
    
    def __init__(self, config_file: Optional[str] = None, instances: Optional[Dict[str, ProxyInstance]] = None):
        """
        Initialize the proxy server.
        
        Args:
            config_file: Path to JSON configuration file (optional)
            instances: Dictionary of ProxyInstance objects (optional)
            
        If neither config_file nor instances is provided, creates default configuration.
        If both are provided, instances takes precedence.
        """
        self.config_file = config_file
        self.instances: Dict[str, ProxyInstance] = {}
        self.app = None
        
        if instances:
            self.instances = instances
            print(f"Loaded {len(self.instances)} proxy instances from provided configuration")
        elif config_file:
            self.load_config()
        else:
            # Neither provided, create default instances
            self.instances = create_proxy_config(create_default_config()['instances'])
            print(f"Created {len(self.instances)} default proxy instances")
    
    def add_instance(self, name: str, config: Dict) -> None:
        """
        Add a proxy instance programmatically.
        
        Args:
            name: Instance name
            config: Instance configuration dictionary
            
        Example:
            server.add_instance('api', {
                'restrict_out': 'external',
                'tokens': ['api-key-123'],
                'restrict_in_cidrs': ['192.168.1.0/24']
            })
        """
        self.instances[name] = ProxyInstance(name, config)
        print(f"Added proxy instance: {name}")
    
    def remove_instance(self, name: str) -> bool:
        """
        Remove a proxy instance.
        
        Args:
            name: Instance name to remove
            
        Returns:
            True if instance was removed, False if it didn't exist
        """
        if name in self.instances:
            del self.instances[name]
            print(f"Removed proxy instance: {name}")
            return True
        return False
    
    def list_instances(self) -> List[str]:
        """
        Get list of configured instance names.
        
        Returns:
            List of instance names
        """
        return list(self.instances.keys())
    
    def get_instance_config(self, name: str) -> Optional[Dict]:
        """
        Get configuration for a specific instance.
        
        Args:
            name: Instance name
            
        Returns:
            Instance configuration dictionary or None if not found
        """
        if name in self.instances:
            instance = self.instances[name]
            return {
                'restrict_out': instance.restrict_out,
                'restrict_out_cidrs': [str(cidr) for cidr in instance.restrict_out_cidrs],
                'restrict_in_cidrs': [str(cidr) for cidr in instance.restrict_in_cidrs],
                'tokens': list(instance.tokens),
                'timeout': instance.timeout
            }
        return None
    
    def load_config(self):
        """Load configuration from file"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            self.instances = {}
            for name, instance_config in config.get('instances', {}).items():
                self.instances[name] = ProxyInstance(name, instance_config)
            
            print(f"Loaded {len(self.instances)} proxy instances")
            
        except FileNotFoundError:
            print(f"Config file {self.config_file} not found. Creating default config.")
            self.create_default_config()
        except json.JSONDecodeError as e:
            print(f"Error parsing config file: {e}")
            exit(1)
    
    def create_default_config(self):
        """Create a default configuration file"""
        default_config = create_default_config()
        
        with open(self.config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        print(f"Created default config file: {self.config_file}")
        self.load_config()
    
    def create_app(self) -> web.Application:
        """Create the aiohttp application with routes"""
        app = web.Application()
        
        # Add route for each instance
        for instance_name, instance in self.instances.items():
            handler = HomieProxyRequestHandler(instance)
            
            # Create route pattern
            route_path = f'/{instance_name}'
            
            # Add route for all HTTP methods
            app.router.add_route('*', route_path, handler.handle_request)
        
        # Add debug route to show all instances
        async def debug_handler(request):
            debug_info = {
                'timestamp': datetime.now().isoformat(),
                'instances': {}
            }
            
            for name, instance in self.instances.items():
                debug_info['instances'][name] = {
                    'restrict_out': instance.restrict_out,
                    'restrict_out_cidrs': [str(cidr) for cidr in instance.restrict_out_cidrs],
                    'restrict_in_cidrs': [str(cidr) for cidr in instance.restrict_in_cidrs],
                    'tokens': list(instance.tokens),
                    'timeout': instance.timeout
                }
            
            return web.Response(
                text=json.dumps(debug_info, indent=2),
                headers={'Content-Type': 'application/json'}
            )
        
        app.router.add_get('/debug', debug_handler)
        
        return app
    
    async def init_server(self, host: str = '0.0.0.0', port: int = 8080):
        """Initialize the aiohttp server"""
        # Check if port is in use
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(1)
            result = test_socket.connect_ex((host if host != '0.0.0.0' else 'localhost', port))
            test_socket.close()
            
            if result == 0:
                print(f"ERROR: Port {port} is already in use!")
                print(f"   Another service is already running on {host}:{port}")
                print(f"   Please stop the other service or use a different port with --port")
                exit(1)
        except Exception:
            pass  # If connection test fails, port is likely free
        
        # Create the app
        self.app = self.create_app()
        
        print(f"Homie Proxy Server starting on {host}:{port}")
        print(f"Available instances: {list(self.instances.keys())}")
        print("Async server - supports concurrent requests")
        print("Server ready! Press Ctrl+C to stop")
        
        return self.app
    
    def run(self, host: str = '0.0.0.0', port: int = 8080):
        """Run the proxy server"""
        async def start_server():
            app = await self.init_server(host, port)
            runner = web.AppRunner(app)
            await runner.setup()
            
            site = web.TCPSite(runner, host, port)
            await site.start()
            
            print("Server running. Press Ctrl+C to stop...")
            
            # Keep the server running
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down server...")
                await runner.cleanup()
                print("Server stopped successfully")
        
        # Run the async server
        try:
            asyncio.run(start_server())
        except KeyboardInterrupt:
            print("\nServer interrupted")


def main():
    """Main entry point for console script"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Homie Proxy Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to (default: 8080)')
    parser.add_argument('--config', default='proxy_config.json', help='Configuration file (default: proxy_config.json)')
    
    args = parser.parse_args()
    
    server = HomieProxyServer(args.config)
    server.run(args.host, args.port)


if __name__ == '__main__':
    main() 