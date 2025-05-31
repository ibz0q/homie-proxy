# Modern Python Reverse Proxy

A clean, modern Python reverse proxy server with minimal dependencies that supports configurable instances, authentication, IP restrictions, caching, and programmable request/response handling.

## Features

- **Multiple Proxy Instances**: Configure multiple named proxy instances with different settings
- **Concurrent Connections**: Multi-threaded server supports simultaneous requests
- **IP Access Control**: Restrict access to local/external networks or specific CIDR ranges
- **Token Authentication**: Secure your proxy instances with custom tokens
- **Rate Limiting**: Per-IP rate limiting to prevent abuse
- **Persistent Disk Caching**: SHA1-based disk caching with size limits and TTL
- **Per-Request Caching**: Enable caching on individual requests with `&cache=true`
- **TLS Bypass**: Option to skip TLS certificate verification
- **Custom Headers**: Add custom request and response headers
- **Redirect Following**: Control whether HTTP redirects are followed
- **All HTTP Methods**: Support for GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS
- **Minimal Dependencies**: Only requires the `requests` library

## Installation

1. Clone or download the script
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the proxy:
```bash
python reverse_proxy.py
```

## Configuration

The proxy server is configured via `proxy_config.json`. Here's the configuration structure:

```json
{
  "clear_cache_on_start": false,
  "instances": {
    "default": {
      "access_mode": "both",
      "tokens": ["your-secret-token-here"],
      "cache_enabled": true,
      "cache_ttl": 3600,
      "cache_max_size_mb": 0,
      "rate_limit": 100,
      "allowed_cidrs": []
    },
    "internal": {
      "access_mode": "local",
      "tokens": [],
      "cache_enabled": false,
      "cache_ttl": 0,
      "cache_max_size_mb": 0,
      "rate_limit": 0,
      "allowed_cidrs": ["192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12"]
    }
  }
}
```

#### Global Configuration Options

- **clear_cache_on_start**: (boolean) If set to `true`, clears the entire cache directory when the server starts up. Useful for development and testing. Default: `false`

#### Instance Configuration Options

- **access_mode**: 
  - `"local"`: Only allow private IP addresses (Class A, B, C)
  - `"external"`: Only allow public IP addresses
  - `"both"`: Allow all IP addresses (default)

- **tokens**: Array of valid authentication tokens. If empty, no authentication required.

- **cache_enabled**: Enable/disable persistent disk caching (default: false)

- **cache_ttl**: Cache time-to-live in seconds (default: 3600)

- **cache_max_size_mb**: Maximum cache size in MB (0 = unlimited, default: 0)

- **rate_limit**: Maximum requests per minute per IP (0 = unlimited)

- **allowed_cidrs**: Array of CIDR ranges to restrict access to specific networks

### Example Configuration

```json
{
  "instances": {
    "public": {
      "access_mode": "both",
      "tokens": ["abc123", "def456"],
      "cache_enabled": true,
      "cache_ttl": 600,
      "cache_max_size_mb": 0,
      "rate_limit": 50,
      "allowed_cidrs": []
    },
    "internal": {
      "access_mode": "local",
      "tokens": [],
      "cache_enabled": false,
      "cache_ttl": 0,
      "cache_max_size_mb": 0,
      "rate_limit": 0,
      "allowed_cidrs": ["192.168.0.0/16", "10.0.0.0/8"]
    },
    "development": {
      "access_mode": "local",
      "tokens": [],
      "cache_enabled": false,
      "cache_ttl": 0,
      "cache_max_size_mb": 0,
      "rate_limit": 0,
      "allowed_cidrs": ["127.0.0.0/8"]
    }
  }
}
```

## Caching System

The proxy features persistent disk caching with SHA1-based cache keys:

### Disk Cache (SHA1-based)
- Enabled per instance with `cache_enabled: true`
- Activated per request with `&cache=true` parameter
- Persistent across server restarts
- SHA1 hash includes complete request signature:
  - HTTP method
  - Target URL
  - All headers (sorted)
  - Request body (if any)
  - All query parameters (sorted)
- Stored in `proxy_cache/` directory
- Configurable TTL with `cache_ttl`
- Configurable size limit with `cache_max_size_mb`

### Cache Headers
- `X-Cache: DISK` - Response served from disk cache
- No header - Fresh response from target server

### Cache Size Management
- When cache size exceeds `cache_max_size_mb`, oldest files are automatically removed
- Individual cache entries larger than the total limit are skipped
- Requests are always served normally, even when caching is skipped due to size limits

## Usage

### Basic Usage

```bash
# Start the server (default: localhost:8080)
python reverse_proxy.py

# Start on custom host/port
python reverse_proxy.py --host 0.0.0.0 --port 9000

# Use custom config file
python reverse_proxy.py --config my_config.json
```

### Making Requests

The proxy URL format is: `http://localhost:8080/INSTANCE_NAME?url=TARGET_URL&[options]`

#### Basic Examples

```bash
# Simple GET request through 'default' instance
curl "http://localhost:8080/default?url=https://httpbin.org/get&token=your-secret-token-here"

# POST request with JSON data
curl -X POST -H "Content-Type: application/json" -d '{"name":"John","email":"john@example.com"}' \
  "http://localhost:8080/default?url=https://httpbin.org/post&token=your-secret-token-here"

# PUT request with data
curl -X PUT -H "Content-Type: application/json" -d '{"id":1,"status":"updated"}' \
  "http://localhost:8080/default?url=https://api.example.com/users/1&token=your-secret-token-here"

# Granular TLS error handling
curl "http://localhost:8080/default?url=https://self-signed.example.com&token=your-secret-token-here&skip_tls_checks=self_signed,hostname_mismatch"

# Legacy TLS bypass (still works but use specific error types for better security)
curl "http://localhost:8080/default?url=https://self-signed.badssl.com&skip_tls_checks=all&token=your-secret-token-here"
```

#### Caching Examples

```bash
# Enable disk caching for this request
curl "http://localhost:8080/default?url=https://api.example.com/data&token=your-token&cache=true"

# Second identical request will hit disk cache
curl "http://localhost:8080/default?url=https://api.example.com/data&token=your-token&cache=true"

# Different parameters create different cache entries
curl "http://localhost:8080/default?url=https://api.example.com/data&token=your-token&cache=true&request_headers[User-Agent]=Bot1"
curl "http://localhost:8080/default?url=https://api.example.com/data&token=your-token&cache=true&request_headers[User-Agent]=Bot2"

# POST requests can also be cached
curl -X POST -d '{"query": "data"}' \
  "http://localhost:8080/default?url=https://api.example.com/search&token=your-token&cache=true"
```

#### Redirect Following Examples

```bash
# Default behavior - redirects are NOT followed (returns redirect response)
curl "http://localhost:8080/default?url=https://httpbin.org/redirect/1&token=your-token"

# Enable redirect following to get final response
curl "http://localhost:8080/default?url=https://httpbin.org/redirect/1&token=your-token&follow_redirects=true"

# Follow multiple redirects
curl "http://localhost:8080/default?url=https://httpbin.org/redirect/3&token=your-token&follow_redirects=true"

# Alternative parameter values (all equivalent to true)
curl "http://localhost:8080/default?url=https://httpbin.org/redirect/1&token=your-token&follow_redirects=1"
curl "http://localhost:8080/default?url=https://httpbin.org/redirect/1&token=your-token&follow_redirects=yes"

# Explicit disable (same as default)
curl "http://localhost:8080/default?url=https://httpbin.org/redirect/1&token=your-token&follow_redirects=false"
```

#### Advanced Examples

```bash
# Add custom request headers
curl "http://localhost:8080/default?url=https://httpbin.org/headers&token=your-secret-token-here&request_headers[User-Agent]=MyBot/1.0&request_headers[Referer]=https://example.com"

# Add custom response headers (useful for CORS)
curl "http://localhost:8080/default?url=https://httpbin.org/get&token=your-secret-token-here&response_header[Access-Control-Allow-Origin]=*&response_header[Access-Control-Allow-Methods]=GET,POST,PUT,DELETE"

# Complex example with caching and custom headers
curl "http://localhost:8080/default?url=https://api.example.com/data&token=your-secret-token-here&cache=true&skip_tls_checks=true&request_headers[Authorization]=Bearer%20xyz123&response_header[Access-Control-Allow-Origin]=*"
```

### URL Encoding

Remember to URL-encode special characters in your parameters:

```bash
# Spaces become %20
curl "http://localhost:8080/default?url=https://httpbin.org/get&request_headers[User-Agent]=My%20Custom%20Agent"

# Equals signs become %3D
curl "http://localhost:8080/default?url=https://httpbin.org/get&request_headers[Authorization]=Bearer%3Dtoken123"
```

## Programmable Options

### Query Parameters

- `url`: Target URL to proxy to (required)
- `token`: Authentication token (required if tokens are configured)
- `cache`: Set to `true` to enable disk caching for this request
- `follow_redirects`: Set to `true` to follow HTTP redirects (default: `false`)
- `skip_tls_checks`: Comma-separated list of TLS errors to ignore, or `all` to bypass all SSL verification
- `request_headers[HeaderName]`: Add custom request headers
- `response_header[HeaderName]`: Add custom response headers
- `dns_server[]`: Custom DNS servers (placeholder for future implementation)

### TLS Error Types

The `skip_tls_checks` parameter accepts a comma-separated list of these error types:

- `all`: Bypass all SSL certificate verification (complete TLS bypass)
- `expired_cert`: Ignore expired certificates
- `self_signed`: Ignore self-signed certificates  
- `hostname_mismatch`: Ignore hostname/common name mismatches
- `cert_authority`: Ignore untrusted certificate authority errors
- `weak_cipher`: Allow weak cipher suites

Examples:
```bash
# Bypass all TLS verification (not recommended for production)
skip_tls_checks=all

# Ignore specific error types
skip_tls_checks=expired_cert,hostname_mismatch

# Ignore self-signed certificates only
skip_tls_checks=self_signed

# Ignore multiple error types
skip_tls_checks=expired_cert,self_signed,cert_authority
```

### Examples by Use Case

#### Cached API Gateway
```bash
curl "http://localhost:8080/default?url=https://api.example.com/expensive-operation&token=your-token&cache=true&response_header[Access-Control-Allow-Origin]=*"
```

#### Development Proxy with Granular TLS Control
```bash
curl "http://localhost:8080/internal?url=https://dev-api.local/data&cache=true&skip_tls_checks=self_signed,expired_cert"
```

#### API Integration with Specific TLS Error Handling
```bash
curl -X POST -H "Content-Type: application/json" -d '{"query":"search"}' \
  "http://localhost:8080/default?url=https://legacy-api.company.com/search&token=your-token&skip_tls_checks=weak_cipher,cert_authority"
```

## Cache Management

### Cache Directory Structure
```
proxy_cache/
├── a1b2c3d4e5f6...abc123.cache  # SHA1 hash of request
├── f6e5d4c3b2a1...def456.cache
└── ...
```

### Cache File Format
Each cache file contains:
- Response status code
- Response headers
- Response body
- Expiration timestamp
- Creation timestamp
- Cache key (SHA1 hash)

### Manual Cache Management
```bash
# View cache directory
ls -la proxy_cache/

# Clear all cache files
rm -rf proxy_cache/*.cache

# View cache file details (requires Python)
python -c "import pickle; print(pickle.load(open('proxy_cache/HASH.cache', 'rb')))"
```

## Security Considerations

1. **Token Security**: Use strong, random tokens for authentication
2. **Network Restrictions**: Use `allowed_cidrs` to restrict access to trusted networks
3. **Rate Limiting**: Configure appropriate rate limits to prevent abuse
4. **TLS Verification**: Only disable TLS checks for development/internal services
5. **Access Modes**: Use `local` mode for internal-only proxies
6. **Cache Security**: Cache files contain response data - secure the cache directory
7. **Disk Space**: Monitor cache directory size, especially with long TTLs
8. **Header Filtering**: Proxy headers (`X-Forwarded-For`, `X-Real-IP`, etc.) are automatically filtered out before forwarding requests

## Monitoring and Logging

The proxy provides detailed logging with timestamps:

```
[2024-01-15 10:30:45] 192.168.1.100 - - [15/Jan/2024 10:30:45] "GET /default?url=https://httpbin.org/get HTTP/1.1" 200 -
```

Cache statistics are shown on startup:
```
Disk cache: 42 files, 1048576 bytes
```

## Error Responses

All errors are returned as JSON:

```json
{
  "error": "Invalid or missing token",
  "code": 401,
  "timestamp": "2024-01-15T10:30:45.123456"
}
```

Common error codes:
- `