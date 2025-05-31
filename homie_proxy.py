#!/usr/bin/env python3
"""
Homie Proxy Server
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
import time

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
        # New naming scheme for network access control
        self.restrict_out = config.get('restrict_out', 'both')  # external, internal, both
        self.restrict_out_cidrs = [ipaddress.ip_network(cidr) for cidr in config.get('restrict_out_cidrs', [])]
        self.tokens = set(config.get('tokens', []))
        self.restrict_in_cidrs = [ipaddress.ip_network(cidr) for cidr in config.get('restrict_in_cidrs', [])]
        
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
                    import socket
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
        """Check if provided token is valid"""
        if not self.tokens:
            return True  # No tokens required
        return token in self.tokens


class HomieProxyHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the homie proxy"""
    
    def __init__(self, *args, proxy_config=None, **kwargs):
        self.proxy_config = proxy_config or {}
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        """Override to provide better logging"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {format % args}")
    
    def handle_one_request(self):
        """Override to handle connection errors gracefully"""
        try:
            super().handle_one_request()
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass
        except Exception as e:
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
            if not instance.is_client_access_allowed(client_ip):
                self.log_message(f"Client IP access denied: {client_ip} not allowed for instance '{instance_name}'")
                if instance.restrict_in_cidrs:
                    allowed_cidrs_str = ', '.join(str(cidr) for cidr in instance.restrict_in_cidrs)
                    self.log_message(f"Instance allowed CIDRs: {allowed_cidrs_str}")
                else:
                    self.log_message("Instance has no restrict_in_cidrs specified - allowing all IPs (0.0.0.0/0)")
                self.send_error_response(403, "Access denied from your IP")
                return
            
            self.log_message(f"Client IP access allowed: {client_ip} for instance '{instance_name}'")
            
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
            
            # Check target URL access
            if not instance.is_target_url_allowed(target_url):
                if instance.restrict_out_cidrs:
                    cidrs_str = ', '.join(str(cidr) for cidr in instance.restrict_out_cidrs)
                    self.log_message(f"Target URL access denied: {target_url} not in restrict_out_cidrs '{cidrs_str}'")
                else:
                    self.log_message(f"Target URL access denied: {target_url} not allowed for restrict_out '{instance.restrict_out}'")
                self.send_error_response(403, "Access denied to the target URL")
                return
            
            if instance.restrict_out_cidrs:
                cidrs_str = ', '.join(str(cidr) for cidr in instance.restrict_out_cidrs)
                self.log_message(f"Target URL access allowed: {target_url} matches restrict_out_cidrs '{cidrs_str}'")
            else:
                self.log_message(f"Target URL access allowed: {target_url} for restrict_out '{instance.restrict_out}'")
            
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
            
            # Handle Host header override logic
            override_host_header_param = query_params.get('override_host_header', [''])
            override_host_header = override_host_header_param[0] if override_host_header_param[0] else None
            
            # Parse target URL for hostname
            parsed_target = urllib.parse.urlparse(target_url)
            original_hostname = parsed_target.hostname
            
            # Prepare headers - start with original headers from client
            headers = dict(self.headers)
            
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
            
            try:
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
                
                # Send headers - pass through all headers from target
                for header, value in response.headers.items():
                    self.send_header(header, value)
                
                # Add custom response headers
                for key, values in query_params.items():
                    if key.startswith('response_header[') and key.endswith(']'):
                        header_name = key[16:-1]  # Remove 'response_header[' and ']'
                        self.send_header(header_name, values[0])
                
                self.end_headers()
                
                # Stream response data directly with connection abort detection
                self.log_message("Streaming response directly")
                bytes_transferred = 0
                connection_aborted = False
                
                try:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            try:
                                self.wfile.write(chunk)
                                self.wfile.flush()  # Ensure data is sent immediately
                                bytes_transferred += len(chunk)
                            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                                self.log_message(f"Client disconnected during streaming, {bytes_transferred} bytes sent")
                                connection_aborted = True
                                break
                            except OSError as e:
                                self.log_message(f"Connection aborted during streaming, {bytes_transferred} bytes sent - cancelling request")
                                connection_aborted = True
                                break
                
                    if not connection_aborted and bytes_transferred > 0:
                        self.log_message(f"Streamed {bytes_transferred} bytes successfully")
                    elif connection_aborted:
                        self.log_message(f"Request cancelled due to connection issues")
                        
                except Exception as stream_error:
                    self.log_message(f"Streaming error: {stream_error}")
                    connection_aborted = True
                
                # If connection was aborted, don't continue processing
                if connection_aborted:
                    return  # Exit early to prevent further errors
                
            except requests.exceptions.RequestException as e:
                self.log_message(f"Request error: {e}")
                self.send_error_response(502, f"Bad Gateway: {str(e)}")
                    
            except OSError as e:
                self.log_message(f"OS error: {e}")
                self.send_error_response(500, "Internal server error")
            
            finally:
                # Always close the session to prevent connection pooling issues
                session.close()
            
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


class HomieProxyServer:
    """Main homie proxy server"""
    
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
                    "restrict_out": "both",
                    "tokens": ["your-secret-token-here"],
                    "restrict_in_cidrs": []
                },
                "internal-only": {
                    "restrict_out": "internal",
                    "tokens": [],
                    "restrict_in_cidrs": []
                },
                "custom-networks": {
                    "restrict_out": "both",
                    "restrict_out_cidrs": ["8.8.8.0/24", "1.1.1.0/24"],
                    "tokens": ["custom-token"],
                    "restrict_in_cidrs": []
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
            return HomieProxyHandler(*args, proxy_config=self.instances, **kwargs)
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
                    result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
                    for line in result.stdout.split('\n'):
                        if f':{port}' in line and 'LISTENING' in line:
                            print(f"   Process using port: {line.strip()}")
                            break
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
            if "Address already in use" in str(e):
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
        
        print(f"Homie Proxy Server starting on {host}:{port}")
        print(f"Available instances: {list(self.instances.keys())}")
        print("Multi-threaded server - supports concurrent requests")
        print("Server ready! Press Ctrl+C to stop")
        
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            server.shutdown()
            server.server_close()
            print("Server stopped successfully")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Homie Proxy Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to (default: 8080)')
    parser.add_argument('--config', default='proxy_config.json', help='Configuration file (default: proxy_config.json)')
    
    args = parser.parse_args()
    
    server = HomieProxyServer(args.config)
    server.run(args.host, args.port) 