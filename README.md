# Modern Python Reverse Proxy

A clean, modern Python reverse proxy server with minimal dependencies that supports configurable instances, authentication, IP restrictions, and programmable request/response handling.

## Features

- **Multiple Proxy Instances**: Configure multiple named proxy instances with different settings
- **Concurrent Connections**: Multi-threaded server supports simultaneous requests without blocking
- **IP Access Control**: Restrict access to local/external networks or specific CIDR ranges
- **Token Authentication**: Secure your proxy instances with custom tokens
- **TLS Bypass**: Option to skip TLS certificate verification
- **Custom Headers**: Add custom request and response headers
- **Redirect Following**: Control whether HTTP redirects are followed
- **All HTTP Methods**: Support for GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS
- **Video/Large File Streaming**: Efficient streaming of large files without blocking other requests
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
```

#### Instance Configuration Options

- **access_mode**: 
  - `"local"`: Only allow private IP addresses (Class A, B, C)
  - `"external"`: Only allow public IP addresses
  - `"both"`: Allow all IP addresses (default)

- **tokens**: Array of valid authentication tokens. If empty, no authentication required.

- **allowed_cidrs**: Array of CIDR ranges to restrict access to specific networks

### Example Configuration

```json
{
  "instances": {
    "public": {
      "access_mode": "both",
      "tokens": ["abc123", "def456"],
      "allowed_cidrs": []
    },
    "internal": {
      "access_mode": "local",
      "tokens": [],
      "allowed_cidrs": ["192.168.0.0/16", "10.0.0.0/8"]
    },
    "development": {
      "access_mode": "local",
      "tokens": [],
      "allowed_cidrs": ["127.0.0.0/8"]
    }
  }
}
```

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

## Programmable Options

### Query Parameters

- `url`: Target URL to proxy to (required)
- `token`: Authentication token (required if tokens are configured)
- `skip_tls_checks`: Comma-separated list of TLS errors to ignore, or `all` to bypass all SSL verification
- `request_headers[HeaderName]`: Add custom request headers
- `response_header[HeaderName]`: Add custom response headers
- `dns_server[]`: Custom DNS servers for hostname resolution
- `follow_redirects`: Enable/disable HTTP redirect following

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

### DNS Override

The proxy supports custom DNS servers for hostname resolution, useful for bypassing DNS filtering or using specific DNS providers:

```bash
# Use Google DNS servers
curl "http://localhost:8080/default?url=https://example.com&token=your-token&dns_server[]=8.8.8.8&dns_server[]=8.8.4.4"

# Use Cloudflare DNS servers
curl "http://localhost:8080/default?url=https://example.com&token=your-token&dns_server[]=1.1.1.1&dns_server[]=1.0.0.1"

# Multiple DNS servers with fallback
curl "http://localhost:8080/default?url=https://example.com&token=your-token&dns_server[]=9.9.9.9&dns_server[]=8.8.8.8&dns_server[]=1.1.1.1"
```

#### DNS Features:
- **Multiple DNS servers**: Specify multiple servers for redundancy
- **Automatic fallback**: If one DNS server fails, tries the next one
- **Host header preservation**: Original hostname preserved for virtual hosting
- **IP address caching**: Resolved IPs are used directly in requests
- **Custom DNS logging**: Detailed logs show which DNS server resolved each hostname

#### DNS Server Examples:
- **Google DNS**: `8.8.8.8`, `8.8.4.4`
- **Cloudflare DNS**: `1.1.1.1`, `1.0.0.1`
- **OpenDNS**: `208.67.222.222`, `208.67.220.220`
- **Quad9 DNS**: `9.9.9.9`, `149.112.112.112`

## Concurrent Request Handling

The reverse proxy uses `ThreadingHTTPServer` to handle multiple requests simultaneously:

### Concurrency Features
- **Multiple simultaneous connections**: Each request gets its own thread
- **Non-blocking video/large file streaming**: Large downloads don't block other requests
- **Thread-safe operations**: All operations are thread-safe

### Performance Benefits
```bash
# These two large video files can download simultaneously
# Request 1 (starts immediately):
curl "http://localhost:8080/default?url=https://example.com/large-video.mp4&token=your-token&skip_tls_checks=all" &

# Request 2 (also starts immediately, no waiting for Request 1):
curl "http://localhost:8080/default?url=https://example.com/another-video.mp4&token=your-token&skip_tls_checks=all" &
```

### Concurrent Use Cases
- **Multiple video streams**: Stream different videos to different clients simultaneously
- **API + Video**: Small API requests don't wait for large file downloads
- **Batch processing**: Multiple data requests can run in parallel
- **Mixed workloads**: JSON APIs, file downloads, and streaming can all happen concurrently

## Monitoring and Logging

The proxy provides detailed logging with timestamps:

```
[2024-01-15 10:30:45] 192.168.1.100 - - [15/Jan/2024 10:30:45] "GET /default?url=https://httpbin.org/get HTTP/1.1" 200 -
```

Server startup shows loaded configuration:
```
Loaded 2 proxy instances
Multi-threaded server - supports concurrent requests
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
- `400`: Bad Request (missing URL, invalid parameters)
- `401`: Unauthorized (invalid or missing token)
- `403`: Forbidden (IP access denied)
- `404`: Not Found (instance not found)
- `502`: Bad Gateway (target server error)