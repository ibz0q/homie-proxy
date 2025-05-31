#!/usr/bin/env python3
"""
Modern Python Reverse Proxy Server
Minimal dependencies, configurable instances with authentication and restrictions.
"""

import json
import ipaddress
import ssl
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict
import socket
import os
import subprocess
import select

try:
    import requests
    from requests.adapters import HTTPAdapter
    import urllib3
    from urllib3.exceptions import InsecureRequestWarning
    # Note: SubjectAltNameWarning and InsecurePlatformWarning may not exist in newer urllib3 versions
    try:
        from urllib3.exceptions import SubjectAltNameWarning
    except ImportError:
        SubjectAltNameWarning = None
    try:
        from urllib3.exceptions import InsecurePlatformWarning
    except ImportError:
        InsecurePlatformWarning = None
except ImportError:
    print("Error: 'requests' library is required. Install with: pip install requests")
    exit(1)


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
            if InsecurePlatformWarning is not None:
                urllib3.disable_warnings(InsecurePlatformWarning)
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
    
    def __init__(self, name: str, config: Dict):
        self.name = name
        self.access_mode = config.get('access_mode', 'both')  # local, external, both
        self.tokens = set(config.get('tokens', []))
        self.allowed_cidrs = [ipaddress.ip_network(cidr) for cidr in config.get('allowed_cidrs', [])]
    
    def is_access_allowed(self, client_ip: str) -> bool:
        """Check if access is allowed based on IP and access mode"""
        try:
            ip = ipaddress.ip_address(client_ip)
            
            # Check CIDR restrictions first
            if self.allowed_cidrs:
                allowed = any(ip in cidr for cidr in self.allowed_cidrs)
                if not allowed:
                    return False
            
            # Check access mode
            if self.access_mode == 'local':
                return ip.is_private
            elif self.access_mode == 'external':
                return not ip.is_private
            else:  # both
                return True
                
        except ValueError:
            return False
    
    def is_token_valid(self, token: str) -> bool:
        """Check if provided token is valid"""
        if not self.tokens:
            return True  # No tokens required
        return token in self.tokens


class ReverseProxyHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the reverse proxy"""
    
    def __init__(self, *args, proxy_config=None, **kwargs):
        self.proxy_config = proxy_config or {}
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        """Override to provide better logging"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {format % args}")
    
    def handle_one_request(self):
        """Handle a single HTTP request with better error handling"""
        try:
            super().handle_one_request()
        except ConnectionResetError:
            # Client disconnected - this is normal, don't log as error
            pass
        except BrokenPipeError:
            # Client disconnected while we were sending data - this is normal
            pass
        except Exception as e:
            # Log unexpected errors but don't crash
            self.log_message(f"Request handling error: {e}")
    
    def __getattr__(self, name):
        """Handle all HTTP methods generically"""
        if name.startswith('do_'):
            return self.handle_request
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")
    
    def handle_request(self):
        """Main request handler - uses self.command for HTTP method"""
        try:
            # Parse the request path
            path_parts = self.path.lstrip('/').split('?', 1)
            instance_name = path_parts[0] if path_parts else ''
            
            if not instance_name:
                self.send_error_response(400, "Instance name required in path")
                return
            
            # Get instance configuration
            if instance_name not in self.proxy_config:
                self.send_error_response(404, f"Instance '{instance_name}' not found")
                return
            
            instance = self.proxy_config[instance_name]
            client_ip = self.get_client_ip()
            
            # Check IP access
            if not instance.is_access_allowed(client_ip):
                self.send_error_response(403, "Access denied from your IP")
                return
            
            # Parse query parameters
            query_params = {}
            if len(path_parts) > 1:
                query_params = urllib.parse.parse_qs(path_parts[1])
            
            # Get target URL
            target_urls = query_params.get('url', [])
            if not target_urls:
                self.send_error_response(400, "Target URL required")
                return
            
            target_url = target_urls[0]
            
            # Check authentication
            tokens = query_params.get('token', [])
            token = tokens[0] if tokens else None
            if not instance.is_token_valid(token):
                self.send_error_response(401, "Invalid or missing token")
                return
            
            # Get request body for methods that might have a body
            content_length = int(self.headers.get('Content-Length', 0))
            body = None
            if content_length > 0:
                body = self.rfile.read(content_length)
            elif self.command in ['POST', 'PUT', 'PATCH']:
                # Some clients might send body without Content-Length
                try:
                    # Try to read any available data (non-blocking)
                    if select.select([self.rfile], [], [], 0)[0]:
                        body = self.rfile.read()
                except:
                    pass
            
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
                    self.log_message("TLS parameter 'true' detected, ignoring ALL TLS errors")
                else:
                    # Parse comma-separated list of TLS errors to ignore
                    skip_tls_checks = [error.strip().lower() for error in skip_tls_value.split(',')]
                
                # Check for ALL option - completely disable TLS verification
                if 'all' in skip_tls_checks:
                    session.verify = False
                    urllib3.disable_warnings(InsecureRequestWarning)
                    if SubjectAltNameWarning is not None:
                        urllib3.disable_warnings(SubjectAltNameWarning)
                    if InsecurePlatformWarning is not None:
                        urllib3.disable_warnings(InsecurePlatformWarning)
                    self.log_message("Ignoring ALL TLS errors - complete TLS verification disabled")
                else:
                    # Mount custom HTTPS adapter for specific error types
                    https_adapter = CustomHTTPSAdapter(skip_tls_checks=skip_tls_checks)
                    session.mount('https://', https_adapter)
                    self.log_message(f"Ignoring specific TLS errors: {', '.join(skip_tls_checks)}")
            
            # Configure redirect following
            follow_redirects_param = query_params.get('follow_redirects', ['false'])
            follow_redirects = follow_redirects_param[0].lower() in ['true', '1', 'yes']
            if follow_redirects:
                self.log_message("Redirect following enabled")
            else:
                self.log_message("Redirect following disabled (default)")
            
            # Prepare headers
            headers = dict(self.headers)
            
            # Remove hop-by-hop headers and proxy-specific headers
            hop_by_hop = ['connection', 'keep-alive', 'proxy-authenticate', 
                         'proxy-authorization', 'te', 'trailers', 'transfer-encoding', 'upgrade']
            proxy_headers = ['x-forwarded-for', 'x-real-ip', 'x-forwarded-proto', 'x-forwarded-host',
                           'x-forwarded-port', 'x-forwarded-server', 'x-client-ip', 'x-originating-ip',
                           'x-remote-ip', 'x-remote-addr', 'cf-connecting-ip', 'true-client-ip',
                           'x-cluster-client-ip', 'fastly-client-ip', 'x-azure-clientip']
            
            for header in hop_by_hop + proxy_headers:
                headers.pop(header, None)
                headers.pop(header.lower(), None)  # Ensure case-insensitive removal
            
            # Add custom request headers first (so they can override defaults)
            for key, values in query_params.items():
                if key.startswith('request_headers[') and key.endswith(']'):
                    header_name = key[16:-1]  # Remove 'request_headers[' and ']'
                    headers[header_name] = values[0]
            
            # Fix Host header for proper virtual hosting
            parsed_target = urllib.parse.urlparse(target_url)
            if parsed_target.hostname:
                # Check if the hostname is an IP address
                try:
                    ipaddress.ip_address(parsed_target.hostname)
                    # It's an IP address - set Host header to the IP
                    headers['Host'] = parsed_target.hostname
                    self.log_message(f"Fixed Host header to IP: {headers['Host']}")
                except ValueError:
                    # It's a hostname - always use just the hostname (no port for virtual hosts)
                    headers['Host'] = parsed_target.hostname
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
            
            # Ensure proper Content-Type for requests with body
            if body and 'content-type' not in [h.lower() for h in headers.keys()]:
                # Try to detect content type from the original request
                original_content_type = self.headers.get('Content-Type')
                if original_content_type:
                    headers['Content-Type'] = original_content_type
                elif self.command in ['POST', 'PUT', 'PATCH']:
                    # Default to JSON if not specified for methods that typically send JSON
                    try:
                        json.loads(body.decode('utf-8'))
                        headers['Content-Type'] = 'application/json'
                    except:
                        headers['Content-Type'] = 'application/octet-stream'
            
            # Make the request
            request_kwargs = {
                'method': self.command,
                'url': target_url,
                'headers': headers,
                'stream': True,
                'timeout': 30,
                'allow_redirects': follow_redirects
            }
            
            # Add body for methods that support it
            if body is not None:
                request_kwargs['data'] = body
            
            # Log the request headers being sent to target URL
            self.log_message(f"REQUEST to {target_url}")
            self.log_message(f"Request method: {self.command}")
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
            
            response = session.request(**request_kwargs)
            
            # Log the response headers received from target
            self.log_message(f"RESPONSE from {target_url}")
            self.log_message(f"Response status: {response.status_code}")
            if response.headers:
                self.log_message("Response headers received from target:")
                for header_name, header_value in response.headers.items():
                    # Truncate very long header values for readability
                    if len(str(header_value)) > 100:
                        display_value = str(header_value)[:97] + "..."
                    else:
                        display_value = header_value
                    self.log_message(f"  {header_name}: {display_value}")
            else:
                self.log_message("No response headers received from target")
            
            # Send response
            self.send_response(response.status_code)
            
            # Send headers
            for header, value in response.headers.items():
                if header.lower() not in hop_by_hop:
                    self.send_header(header, value)
            
            # Add custom response headers
            for key, values in query_params.items():
                if key.startswith('response_header[') and key.endswith(']'):
                    header_name = key[16:-1]  # Remove 'response_header[' and ']'
                    self.send_header(header_name, values[0])
            
            self.end_headers()
            
            # Stream response data directly (no caching)
            self.log_message("Streaming response directly")
            bytes_transferred = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    self.wfile.write(chunk)
                    bytes_transferred += len(chunk)
            
            if bytes_transferred > 0:
                self.log_message(f"Streamed {bytes_transferred} bytes")
            
        except requests.exceptions.RequestException as e:
            self.log_message(f"Request error: {e}")
            self.send_error_response(502, f"Bad Gateway: {str(e)}")
        except Exception as e:
            self.log_message(f"Proxy error: {e}")
            self.send_error_response(500, "Internal server error")
    
    def send_error_response(self, code: int, message: str):
        """Send an error response"""
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        error_response = json.dumps({
            'error': message,
            'code': code,
            'timestamp': datetime.now().isoformat()
        })
        self.wfile.write(error_response.encode())

    def get_client_ip(self) -> str:
        """Get the real client IP address"""
        # Check for forwarded headers first
        forwarded_for = self.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = self.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return self.client_address[0]


class ReverseProxyServer:
    """Main reverse proxy server"""
    
    def __init__(self, config_file: str = 'proxy_config.json'):
        self.config_file = config_file
        self.instances: Dict[str, ProxyInstance] = {}
        self.load_config()
    
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
        default_config = {
            "instances": {
                "default": {
                    "access_mode": "both",
                    "tokens": ["your-secret-token-here"],
                    "allowed_cidrs": []
                },
                "internal": {
                    "access_mode": "local",
                    "tokens": [],
                    "allowed_cidrs": ["192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12"]
                }
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        print(f"Created default config file: {self.config_file}")
        self.load_config()
    
    def create_handler(self):
        """Create a request handler with the current configuration"""
        def handler(*args, **kwargs):
            return ReverseProxyHandler(*args, proxy_config=self.instances, **kwargs)
        return handler
    
    def run(self, host: str = '0.0.0.0', port: int = 8080):
        """Run the proxy server"""
        # Check if port is already in use with multiple methods
        
        # Method 1: Try to connect to the port (most reliable)
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(1)
            result = test_socket.connect_ex((host if host != '0.0.0.0' else 'localhost', port))
            test_socket.close()
            
            if result == 0:
                print(f"ERROR: Port {port} is already in use!")
                print(f"   Another service is already running on {host}:{port}")
                print(f"   Please stop the other service or use a different port with --port")
                
                # Try to show what's using the port
                try:
                    if os.name == 'nt':  # Windows
                        result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
                        for line in result.stdout.split('\n'):
                            if f':{port}' in line and 'LISTENING' in line:
                                print(f"   Process using port: {line.strip()}")
                                break
                    else:  # Unix/Linux
                        result = subprocess.run(['lsof', '-i', f':{port}'], capture_output=True, text=True)
                        if result.stdout:
                            print(f"   Process using port: {result.stdout}")
                except:
                    pass
                
                exit(1)
        except Exception:
            pass  # If connection test fails, port is likely free
        
        # Method 2: Try to bind without SO_REUSEADDR (backup check)
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Don't set SO_REUSEADDR for the test - this was the bug!
            test_socket.bind((host, port))
            test_socket.close()
        except OSError as e:
            print(f"ERROR: Cannot bind to {host}:{port}")
            if "Address already in use" in str(e) or e.errno == 98:
                print(f"   Port {port} is already in use by another process")
                print(f"   Please stop the other process or use a different port with --port")
            else:
                print(f"   Error details: {e}")
            exit(1)
        
        # Create and start the server
        handler = self.create_handler()
        
        try:
            server = ThreadingHTTPServer((host, port), handler)
            # Only set SO_REUSEADDR on the actual server, not the test socket
            server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except OSError as e:
            print(f"ERROR: Failed to create server on {host}:{port}")
            print(f"   Error details: {e}")
            exit(1)
        
        print(f"Reverse Proxy Server starting on {host}:{port}")
        print(f"Available instances: {list(self.instances.keys())}")
        print("Multi-threaded server - supports concurrent requests")
        print("Server ready! Press Ctrl+C to stop")
        
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            server.shutdown()
            print("Server stopped successfully")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Modern Python Reverse Proxy Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to (default: 8080)')
    parser.add_argument('--config', default='proxy_config.json', help='Configuration file (default: proxy_config.json)')
    
    args = parser.parse_args()
    
    server = ReverseProxyServer(args.config)
    server.run(args.host, args.port) 