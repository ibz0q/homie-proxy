#!/usr/bin/env python3
"""
Modern Python Reverse Proxy Server
Minimal dependencies, configurable instances with authentication and restrictions.
"""

import json
import ipaddress
import socket
import ssl
import urllib.parse
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Optional, Any
import hashlib
import time
import threading
import os
import pickle
import warnings

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
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
    
    def __init__(self, ignore_tls_errors=None, *args, **kwargs):
        self.ignore_tls_errors = ignore_tls_errors or []
        super().__init__(*args, **kwargs)
    
    def init_poolmanager(self, *args, **kwargs):
        # Configure SSL context based on ignored errors
        ssl_context = ssl.create_default_context()
        
        if 'expired_cert' in self.ignore_tls_errors:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        elif 'self_signed' in self.ignore_tls_errors:
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        elif 'hostname_mismatch' in self.ignore_tls_errors:
            ssl_context.check_hostname = False
        elif 'cert_authority' in self.ignore_tls_errors:
            ssl_context.verify_mode = ssl.CERT_NONE
        elif 'weak_cipher' in self.ignore_tls_errors:
            ssl_context.set_ciphers('ALL:@SECLEVEL=0')
        
        # If any TLS errors should be ignored, disable verification
        if self.ignore_tls_errors:
            kwargs['ssl_context'] = ssl_context
            # Suppress specific urllib3 warnings
            if 'expired_cert' in self.ignore_tls_errors or 'self_signed' in self.ignore_tls_errors:
                urllib3.disable_warnings(InsecureRequestWarning)
            if 'hostname_mismatch' in self.ignore_tls_errors and SubjectAltNameWarning is not None:
                urllib3.disable_warnings(SubjectAltNameWarning)
        
        return super().init_poolmanager(*args, **kwargs)


class DiskCache:
    """Disk-based cache with SHA1 hashing and TTL support"""
    
    def __init__(self, cache_dir: str = "cache"):
        self.cache_dir = cache_dir
        self.lock = threading.Lock()
        
        # Create cache directory if it doesn't exist
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
    
    def _get_cache_path(self, key: str) -> str:
        """Get the file path for a cache key"""
        return os.path.join(self.cache_dir, f"{key}.cache")
    
    def _create_cache_key(self, method: str, url: str, headers: Dict, body: bytes, query_params: Dict) -> str:
        """Create a SHA1 hash of the complete request"""
        # Create a comprehensive request signature
        request_data = {
            'method': method,
            'url': url,
            'headers': dict(sorted(headers.items())),
            'body': body.hex() if body else '',
            'query_params': dict(sorted(query_params.items()))
        }
        
        # Convert to JSON string for consistent hashing
        request_string = json.dumps(request_data, sort_keys=True)
        
        # Create SHA1 hash
        return hashlib.sha1(request_string.encode()).hexdigest()
    
    def _get_total_cache_size(self) -> int:
        """Get the total size of all cache files in bytes"""
        total_size = 0
        try:
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.cache'):
                    cache_path = os.path.join(self.cache_dir, filename)
                    try:
                        total_size += os.path.getsize(cache_path)
                    except OSError:
                        # File might have been deleted, skip it
                        pass
        except OSError:
            # Directory might not exist or be accessible
            pass
        return total_size
    
    def _cleanup_oldest_files(self, target_size: int):
        """Remove oldest cache files until total size is under target_size"""
        try:
            # Get all cache files with their modification times
            cache_files = []
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.cache'):
                    cache_path = os.path.join(self.cache_dir, filename)
                    try:
                        mtime = os.path.getmtime(cache_path)
                        size = os.path.getsize(cache_path)
                        cache_files.append((cache_path, mtime, size))
                    except OSError:
                        pass
            
            # Sort by modification time (oldest first)
            cache_files.sort(key=lambda x: x[1])
            
            current_size = sum(f[2] for f in cache_files)
            
            # Remove oldest files until we're under the target size
            for cache_path, mtime, size in cache_files:
                if current_size <= target_size:
                    break
                try:
                    os.remove(cache_path)
                    current_size -= size
                except OSError:
                    pass
                    
        except Exception as e:
            print(f"Warning: Error during cache cleanup: {e}")
    
    def get(self, method: str, url: str, headers: Dict, body: bytes, query_params: Dict) -> Optional[Any]:
        """Get cached response if it exists and is not expired"""
        cache_key = self._create_cache_key(method, url, headers, body, query_params)
        cache_path = self._get_cache_path(cache_key)
        
        with self.lock:
            try:
                if os.path.exists(cache_path):
                    with open(cache_path, 'rb') as f:
                        cache_entry = pickle.load(f)
                    
                    # Check if cache entry is still valid
                    if datetime.now() < cache_entry['expires']:
                        return cache_entry['data']
                    else:
                        # Remove expired cache file
                        os.remove(cache_path)
                        
            except (FileNotFoundError, pickle.PickleError, KeyError):
                # Cache file corrupted or missing
                if os.path.exists(cache_path):
                    try:
                        os.remove(cache_path)
                    except:
                        pass
                        
        return None
    
    def set(self, method: str, url: str, headers: Dict, body: bytes, query_params: Dict, 
            data: Any, ttl_seconds: int, max_cache_size_mb: int = 0):
        """Store response in cache if size limits allow"""
        cache_key = self._create_cache_key(method, url, headers, body, query_params)
        cache_path = self._get_cache_path(cache_key)
        
        cache_entry = {
            'data': data,
            'expires': datetime.now() + timedelta(seconds=ttl_seconds),
            'created': datetime.now(),
            'cache_key': cache_key
        }
        
        with self.lock:
            try:
                # Check cache size limit if configured
                if max_cache_size_mb > 0:
                    max_cache_size_bytes = max_cache_size_mb * 1024 * 1024
                    
                    # Estimate the size of the new cache entry
                    temp_data = pickle.dumps(cache_entry)
                    new_entry_size = len(temp_data)
                    
                    current_cache_size = self._get_total_cache_size()
                    
                    # If adding this entry would exceed the limit, check if we can make room
                    if current_cache_size + new_entry_size > max_cache_size_bytes:
                        # Try to cleanup old files to make room
                        target_size = max_cache_size_bytes - new_entry_size
                        if target_size > 0:
                            self._cleanup_oldest_files(target_size)
                            
                            # Check if we now have enough space
                            current_cache_size = self._get_total_cache_size()
                            if current_cache_size + new_entry_size > max_cache_size_bytes:
                                # Still not enough space, skip caching
                                print(f"Warning: Cache size limit ({max_cache_size_mb}MB) exceeded, skipping cache for {cache_key[:8]}...")
                                return
                        else:
                            # New entry is larger than the entire cache limit
                            print(f"Warning: Cache entry too large ({new_entry_size} bytes), skipping cache for {cache_key[:8]}...")
                            return
                
                # Write the cache file
                with open(cache_path, 'wb') as f:
                    pickle.dump(cache_entry, f)
                    
            except Exception as e:
                print(f"Warning: Failed to write cache file {cache_path}: {e}")
    
    def clear_expired(self):
        """Remove expired cache files"""
        with self.lock:
            try:
                for filename in os.listdir(self.cache_dir):
                    if filename.endswith('.cache'):
                        cache_path = os.path.join(self.cache_dir, filename)
                        try:
                            with open(cache_path, 'rb') as f:
                                cache_entry = pickle.load(f)
                            
                            if datetime.now() >= cache_entry['expires']:
                                os.remove(cache_path)
                                
                        except (pickle.PickleError, KeyError, FileNotFoundError):
                            # Remove corrupted cache files
                            try:
                                os.remove(cache_path)
                            except:
                                pass
                                
            except Exception as e:
                print(f"Warning: Error during cache cleanup: {e}")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        stats = {
            'total_files': 0,
            'total_size_bytes': 0,
            'total_size_mb': 0.0,
            'expired_files': 0
        }
        
        try:
            now = datetime.now()
            for filename in os.listdir(self.cache_dir):
                if filename.endswith('.cache'):
                    cache_path = os.path.join(self.cache_dir, filename)
                    try:
                        stats['total_files'] += 1
                        file_size = os.path.getsize(cache_path)
                        stats['total_size_bytes'] += file_size
                        
                        with open(cache_path, 'rb') as f:
                            cache_entry = pickle.load(f)
                        
                        if now >= cache_entry['expires']:
                            stats['expired_files'] += 1
                            
                    except:
                        stats['expired_files'] += 1
                        
            stats['total_size_mb'] = round(stats['total_size_bytes'] / (1024 * 1024), 2)
                        
        except Exception:
            pass
            
        return stats


class ProxyInstance:
    """Configuration for a proxy instance"""
    
    def __init__(self, name: str, config: Dict):
        self.name = name
        self.access_mode = config.get('access_mode', 'both')  # local, external, both
        self.tokens = set(config.get('tokens', []))
        self.cache_enabled = config.get('cache_enabled', False)
        self.cache_ttl = config.get('cache_ttl', 3600)  # 1 hour default (was disk_cache_ttl)
        self.cache_max_size_mb = config.get('cache_max_size_mb', 0)  # 0 = unlimited (was disk_cache_max_size_mb)
        self.rate_limit = config.get('rate_limit', 100)  # requests per minute
        self.allowed_cidrs = [ipaddress.ip_network(cidr) for cidr in config.get('allowed_cidrs', [])]
        
        # Rate limiting
        self.request_counts: Dict[str, List[float]] = {}
        self.rate_lock = threading.Lock()
    
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
    
    def check_rate_limit(self, client_ip: str) -> bool:
        """Check if client is within rate limits"""
        if self.rate_limit <= 0:
            return True
            
        with self.rate_lock:
            now = time.time()
            minute_ago = now - 60
            
            if client_ip not in self.request_counts:
                self.request_counts[client_ip] = []
            
            # Remove old requests
            self.request_counts[client_ip] = [
                req_time for req_time in self.request_counts[client_ip] 
                if req_time > minute_ago
            ]
            
            # Check limit
            if len(self.request_counts[client_ip]) >= self.rate_limit:
                return False
            
            # Add current request
            self.request_counts[client_ip].append(now)
            return True


class ReverseProxyHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the reverse proxy"""
    
    def __init__(self, *args, proxy_config=None, disk_cache=None, **kwargs):
        self.proxy_config = proxy_config or {}
        self.disk_cache = disk_cache or DiskCache()
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        """Override to provide better logging"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {format % args}")
    
    def do_GET(self):
        self.handle_request('GET')
    
    def do_POST(self):
        self.handle_request('POST')
    
    def do_PUT(self):
        self.handle_request('PUT')
    
    def do_DELETE(self):
        self.handle_request('DELETE')
    
    def do_PATCH(self):
        self.handle_request('PATCH')
    
    def do_HEAD(self):
        self.handle_request('HEAD')
    
    def do_OPTIONS(self):
        self.handle_request('OPTIONS')
    
    def handle_request(self, method: str):
        """Main request handler"""
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
            
            # Check rate limiting
            if not instance.check_rate_limit(client_ip):
                self.send_error_response(429, "Rate limit exceeded")
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
            
            # Handle the proxy request
            self.proxy_request(method, target_url, query_params, instance)
            
        except Exception as e:
            self.log_message(f"Error handling request: {e}")
            self.send_error_response(500, "Internal server error")
    
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
    
    def proxy_request(self, method: str, target_url: str, query_params: Dict, instance: ProxyInstance):
        """Proxy the request to the target URL"""
        try:
            # Get request body for all methods that might have a body
            content_length = int(self.headers.get('Content-Length', 0))
            body = None
            if content_length > 0:
                body = self.rfile.read(content_length)
            elif method in ['POST', 'PUT', 'PATCH']:
                # Some clients might send body without Content-Length
                try:
                    # Try to read any available data (non-blocking)
                    import select
                    if select.select([self.rfile], [], [], 0)[0]:
                        body = self.rfile.read()
                except:
                    pass
            
            # Prepare headers for caching (remove proxy-specific headers)
            cache_headers = dict(self.headers)
            hop_by_hop = ['connection', 'keep-alive', 'proxy-authenticate', 
                         'proxy-authorization', 'te', 'trailers', 'transfer-encoding', 'upgrade']
            proxy_headers = ['x-forwarded-for', 'x-real-ip', 'x-forwarded-proto', 'x-forwarded-host',
                           'x-forwarded-port', 'x-forwarded-server', 'x-client-ip', 'x-originating-ip',
                           'x-remote-ip', 'x-remote-addr', 'cf-connecting-ip', 'true-client-ip',
                           'x-cluster-client-ip', 'fastly-client-ip', 'x-azure-clientip']
            
            for header in hop_by_hop + proxy_headers:
                cache_headers.pop(header, None)
                cache_headers.pop(header.lower(), None)  # Ensure case-insensitive removal
            
            # Check if caching is requested for this specific request
            cache_requested = query_params.get('cache', ['false'])[0].lower() == 'true'
            use_disk_cache = cache_requested and instance.cache_enabled
            
            # Check disk cache first (if enabled for this request)
            if use_disk_cache:
                cached_response = self.disk_cache.get(method, target_url, cache_headers, body or b'', query_params)
                if cached_response:
                    self.send_cached_response(cached_response, cache_type='DISK')
                    return
            
            # Prepare request session
            session = requests.Session()
            
            # Clear any default User-Agent from the session
            session.headers.pop('User-Agent', None)
            
            # Configure TLS error handling
            ignore_tls_errors_param = query_params.get('ignore_tls_errors', [''])
            if ignore_tls_errors_param[0]:
                # Parse comma-separated list of TLS errors to ignore
                ignore_tls_errors = [error.strip().lower() for error in ignore_tls_errors_param[0].split(',')]
                
                # Mount custom HTTPS adapter
                https_adapter = CustomHTTPSAdapter(ignore_tls_errors=ignore_tls_errors)
                session.mount('https://', https_adapter)
                
                self.log_message(f"Ignoring TLS errors: {', '.join(ignore_tls_errors)}")
            
            # Legacy support for skip_tls_checks (maps to ignoring all errors)
            skip_tls = query_params.get('skip_tls_checks', ['false'])[0].lower() == 'true'
            if skip_tls:
                session.verify = False
                urllib3.disable_warnings(InsecureRequestWarning)
                self.log_message("Legacy skip_tls_checks enabled - ignoring all TLS errors")
            
            # Configure DNS servers (basic implementation)
            dns_servers = query_params.get('dns_server[]', [])
            if dns_servers:
                # Note: Python's requests doesn't directly support custom DNS
                # This would require additional libraries like dnspython
                pass
            
            # Prepare headers
            headers = dict(self.headers)
            
            # Remove hop-by-hop headers and proxy-specific headers
            for header in hop_by_hop + proxy_headers:
                headers.pop(header, None)
                headers.pop(header.lower(), None)  # Ensure case-insensitive removal
            
            # Add custom request headers first (so they can override defaults)
            for key, values in query_params.items():
                if key.startswith('request_headers[') and key.endswith(']'):
                    header_name = key[16:-1]  # Remove 'request_headers[' and ']'
                    headers[header_name] = values[0]
            
            # Always ensure User-Agent is explicitly set (use blank if none provided)
            # This prevents urllib3 from adding its own default
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
                elif method in ['POST', 'PUT', 'PATCH']:
                    # Default to JSON if not specified for methods that typically send JSON
                    try:
                        json.loads(body.decode('utf-8'))
                        headers['Content-Type'] = 'application/json'
                    except:
                        headers['Content-Type'] = 'application/octet-stream'
            
            # Make the request
            request_kwargs = {
                'method': method,
                'url': target_url,
                'headers': headers,
                'stream': True,
                'timeout': 30
            }
            
            # Add body for methods that support it
            if body is not None:
                request_kwargs['data'] = body
            
            response = session.request(**request_kwargs)
            
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
            
            # Determine if response should be cached based on size and content type
            content_length = response.headers.get('Content-Length')
            content_type = response.headers.get('Content-Type', '').lower()
            
            # Define cache size limit (default 10MB) and non-cacheable content types
            max_cache_size = 10 * 1024 * 1024  # 10MB
            streaming_content_types = [
                'video/', 'audio/', 'application/octet-stream',
                'application/zip', 'application/x-tar', 'application/gzip',
                'image/gif', 'image/png', 'image/jpeg'  # Large images
            ]
            
            should_cache = use_disk_cache and response.status_code == 200
            is_large_content = False
            is_streaming_content = any(content_type.startswith(ct) for ct in streaming_content_types)
            
            if content_length:
                try:
                    size = int(content_length)
                    if size > max_cache_size:
                        is_large_content = True
                        should_cache = False
                        self.log_message(f"Large content ({size} bytes), streaming without caching")
                except:
                    pass
            
            if is_streaming_content:
                should_cache = False
                self.log_message(f"Streaming content type ({content_type}), streaming without caching")
            
            # Stream response data
            if should_cache and not is_large_content and not is_streaming_content:
                # Cache small responses
                response_data = b''
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        self.wfile.write(chunk)
                        response_data += chunk
                        
                        # Safety check: if response grows too large, stop caching
                        if len(response_data) > max_cache_size:
                            self.log_message(f"Response exceeded cache size limit, continuing stream without caching")
                            # Continue streaming remaining chunks without caching
                            for remaining_chunk in response.iter_content(chunk_size=8192):
                                if remaining_chunk:
                                    self.wfile.write(remaining_chunk)
                            should_cache = False
                            break
                
                # Cache the response if it was small enough
                if should_cache and len(response_data) <= max_cache_size:
                    cached_response = {
                        'status_code': response.status_code,
                        'headers': dict(response.headers),
                        'content': response_data
                    }
                    
                    self.disk_cache.set(
                        method, target_url, cache_headers, body or b'', query_params,
                        cached_response, instance.cache_ttl, instance.cache_max_size_mb
                    )
                    self.log_message(f"Cached response ({len(response_data)} bytes)")
            else:
                # Stream large files directly without buffering in memory
                self.log_message("Streaming response directly (no caching)")
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
    
    def send_cached_response(self, cached_response: Dict, cache_type: str = 'HIT'):
        """Send a cached response"""
        self.send_response(cached_response['status_code'])
        for header, value in cached_response['headers'].items():
            self.send_header(header, value)
        self.send_header('X-Cache', cache_type)
        self.end_headers()
        self.wfile.write(cached_response['content'])
    
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


class ReverseProxyServer:
    """Main reverse proxy server"""
    
    def __init__(self, config_file: str = 'proxy_config.json'):
        self.config_file = config_file
        self.instances: Dict[str, ProxyInstance] = {}
        self.disk_cache = DiskCache()
        self.load_config()
        
        # Start cache cleanup thread
        self.cleanup_thread = threading.Thread(target=self.cache_cleanup_worker, daemon=True)
        self.cleanup_thread.start()
    
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
                    "cache_enabled": True,
                    "cache_ttl": 3600,
                    "cache_max_size_mb": 0,
                    "rate_limit": 100,
                    "allowed_cidrs": []
                },
                "internal": {
                    "access_mode": "local",
                    "tokens": [],
                    "cache_enabled": False,
                    "cache_ttl": 0,
                    "cache_max_size_mb": 0,
                    "rate_limit": 0,
                    "allowed_cidrs": ["192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12"]
                }
            }
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        print(f"Created default config file: {self.config_file}")
        self.load_config()
    
    def cache_cleanup_worker(self):
        """Background worker to clean up expired cache entries"""
        while True:
            time.sleep(300)  # Clean up every 5 minutes
            self.disk_cache.clear_expired()
    
    def create_handler(self):
        """Create a request handler with the current configuration"""
        def handler(*args, **kwargs):
            return ReverseProxyHandler(*args, proxy_config=self.instances, disk_cache=self.disk_cache, **kwargs)
        return handler
    
    def run(self, host: str = '0.0.0.0', port: int = 8080):
        """Run the proxy server"""
        # Check if port is already in use
        import socket
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            test_socket.bind((host, port))
            test_socket.close()
        except OSError as e:
            if e.errno == 98 or "Address already in use" in str(e):
                print(f"❌ ERROR: Port {port} is already in use!")
                print(f"   Another server instance may be running on {host}:{port}")
                print(f"   Please stop the other instance or use a different port with --port")
                exit(1)
            else:
                print(f"❌ ERROR: Cannot bind to {host}:{port} - {e}")
                exit(1)
        
        handler = self.create_handler()
        server = HTTPServer((host, port), handler)
        
        print(f"Reverse Proxy Server starting on {host}:{port}")
        print(f"Available instances: {list(self.instances.keys())}")
        
        # Print cache stats
        cache_stats = self.disk_cache.get_cache_stats()
        print(f"Disk cache: {cache_stats['total_files']} files, {cache_stats['total_size_mb']}MB ({cache_stats['total_size_bytes']} bytes)")
        if cache_stats['expired_files'] > 0:
            print(f"Cache cleanup needed: {cache_stats['expired_files']} expired files")
        
        print("Press Ctrl+C to stop")
        
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            server.shutdown()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Modern Python Reverse Proxy Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to (default: 8080)')
    parser.add_argument('--config', default='proxy_config.json', help='Configuration file (default: proxy_config.json)')
    
    args = parser.parse_args()
    
    server = ReverseProxyServer(args.config)
    server.run(args.host, args.port) 