# Homie Proxy

A minimal, high-performance HTTP/HTTPS proxy server built in Python with threading support for concurrent connections.

## Features

- 🚀 **Multi-threading** - ThreadingHTTPServer for concurrent request handling
- 🔐 **TLS Bypass** - Configurable TLS error ignoring (self-signed certs, etc.)
- 🎯 **Instance-based routing** - Multiple proxy configurations in one server
- 🔑 **Token authentication** - Secure access control per instance
- 🌐 **IP-based access control** - Local/external/CIDR restrictions
- 📝 **Custom headers** - Add/modify request and response headers
- 🔄 **Redirect control** - Enable/disable redirect following
- 📊 **Detailed logging** - Request/response header and body logging
- ⚡ **Streaming support** - Direct streaming for large files and videos
- 🎬 **Video friendly** - Optimized for video file proxying

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Server
```bash
python homie_proxy.py --port 8080
```

### 3. Make a Request
```bash
curl "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/get"
```

## Configuration

The server uses `proxy_config.json` for configuration:

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
      "allowed_cidrs": ["192.168.0.0/16", "10.0.0.0/8"]
    }
  }
}
```

### Instance Settings

- **access_mode**: `local`, `external`, or `both`
- **tokens**: Array of valid authentication tokens (empty = no auth required)
- **allowed_cidrs**: IP ranges allowed to access this instance

## Usage Examples

### Basic Request
```bash
curl "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/get"
```

### Custom Request Headers
```bash
curl "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/headers&request_headers[User-Agent]=MyBot/1.0&request_headers[X-Custom]=value"
```

### Custom Response Headers (CORS)
```bash
curl "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/get&response_header[Access-Control-Allow-Origin]=*"
```

### TLS Error Bypass
```bash
# Ignore all TLS errors
curl "http://localhost:8080/default?token=your-secret-token-here&url=https://self-signed.badssl.com&skip_tls_checks=all"

# Ignore specific TLS errors
curl "http://localhost:8080/default?token=your-secret-token-here&url=https://self-signed.badssl.com&skip_tls_checks=self_signed,expired_cert"
```

### Host Header Override
```bash
# For IP-based requests with custom Host header
curl "http://localhost:8080/default?token=your-secret-token-here&url=http://192.168.1.100/api&override_host_header=myapi.example.com"
```

### POST with JSON Body
```bash
curl -X POST "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/post" \
     -H "Content-Type: application/json" \
     -d '{"name": "John", "age": 30}'
```

### Video Streaming
```bash
curl "http://localhost:8080/default?token=your-secret-token-here&url=https://example.com/video.mp4&skip_tls_checks=all" \
     --output video.mp4
```

## URL Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `url` | Target URL to proxy (required) | `url=https://api.example.com/data` |
| `token` | Authentication token | `token=your-secret-token-here` |
| `skip_tls_checks` | TLS errors to ignore | `skip_tls_checks=all` or `skip_tls_checks=self_signed,expired_cert` |
| `follow_redirects` | Enable redirect following | `follow_redirects=true` |
| `override_host_header` | Override Host header | `override_host_header=api.example.com` |
| `request_headers[Name]` | Add custom request header | `request_headers[Authorization]=Bearer token` |
| `response_header[Name]` | Add custom response header | `response_header[Access-Control-Allow-Origin]=*` |

## Host Header Behavior

- **Hostnames**: Automatically sets Host header to hostname (no port)
- **IP Addresses**: No Host header set by default
- **Override**: Use `override_host_header` to force a specific Host header value

## TLS Error Types

- `all` - Ignore all TLS verification (not recommended for production)
- `self_signed` - Allow self-signed certificates
- `expired_cert` - Allow expired certificates  
- `hostname_mismatch` - Allow hostname mismatches
- `cert_authority` - Allow unknown certificate authorities
- `weak_cipher` - Allow weak cipher suites

## Command Line Options

```bash
python homie_proxy.py [options]

Options:
  --host HOST      Host to bind to (default: 0.0.0.0)
  --port PORT      Port to bind to (default: 8080)  
  --config FILE    Configuration file (default: proxy_config.json)
```

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
python run_tests.py --port 8080

# Run specific test
python run_tests.py --port 8080 --test test_simple
```

Available tests:
- `test_simple` - Basic functionality 
- `test_blank_ua` - User-Agent handling
- `test_concurrent_requests` - Concurrent request handling
- `test_tls_all` - TLS bypass functionality
- `cors_test` - CORS header injection
- `test_host_header` - Host header correction

## Architecture

### Multi-threading
- Uses `ThreadingHTTPServer` for concurrent request handling
- Each request gets its own thread
- No blocking between concurrent requests
- Optimized for video streaming and large file downloads

### Streaming
- Direct streaming from target to client
- 8KB chunk size for optimal performance
- No buffering or caching
- Supports HTTP range requests for video seeking

### Security
- Token-based authentication per instance
- IP address and CIDR-based access control  
- Configurable TLS verification levels
- Request/response header filtering options

## Dependencies

- **requests** >= 2.25.0 - HTTP client library
- **Python** >= 3.7 - Core language requirements

Minimal dependency footprint for easy deployment.

## Development

### Project Structure
```
homie-proxy/
├── homie_proxy.py      # Main proxy server
├── proxy_config.json   # Configuration file
├── requirements.txt    # Dependencies
├── run_tests.py       # Test runner
├── tests/             # Test suite
│   ├── test_simple.py
│   ├── test_blank_ua.py
│   ├── cors_test.py
│   └── ...
├── README.md          # This file
└── TESTING.md         # Testing guide
```

### Adding Features
1. Modify `HomieProxyHandler.handle_request()` for request processing
2. Update URL parameter parsing for new options
3. Add corresponding tests in the `tests/` directory
4. Update documentation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality  
4. Update documentation
5. Submit a pull request

## License

This project is open source. Feel free to use, modify, and distribute.