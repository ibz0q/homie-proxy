# HomieProxy

A high-performance HTTP reverse proxy with Home Assistant integration, optimized for streaming, authentication, and secure network access control.

## Features

- HTTP/HTTPS proxy with token-based authentication
- Streaming support for large files without memory buffering
- Network access control (internal-only, external-only, custom CIDR)
- WebSocket connection handling
- Native Home Assistant integration
- All HTTP methods support (GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS)
- TLS bypass options for development/testing
- Custom request/response header manipulation
- Redirect following control

## Installation

### Home Assistant Integration

1. Copy integration to custom components:
```bash
cp -r custom_components/homie_proxy /config/custom_components/
```

2. Restart Home Assistant

3. Add via UI: Settings > Integrations > Add Integration > HomieProxy

4. Configure instance with desired settings

### Standalone Server

```bash
pip install -e .
homie-proxy --host localhost --port 8080
```

### Docker

```bash
docker-compose up
```

## Usage

### Basic Request

```bash
curl "http://localhost:8123/api/homie_proxy/INSTANCE_NAME?token=TOKEN&url=TARGET_URL"
```

### Home Assistant Debug Endpoint

Get configuration and tokens: `http://localhost:8123/api/homie_proxy/debug`

## Parameters

### Required Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| `token` | Authentication token | `token=abc123-def456` |
| `url` | Target URL to proxy | `url=https://httpbin.org/get` |

### Optional Parameters

| Parameter | Description | Default | Example |
|-----------|-------------|---------|---------|
| `timeout` | Request timeout in seconds | Instance default | `timeout=60` |
| `follow_redirects` | Follow HTTP redirects | `false` | `follow_redirects=true` |
| `skip_tls_checks` | Skip TLS verification | None | `skip_tls_checks=all` |

### Request Headers

Set custom request headers using `request_header[NAME]` format:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `request_header[Host]` | Override Host header | `request_header[Host]=custom.example.com` |
| `request_header[User-Agent]` | Set User-Agent | `request_header[User-Agent]=MyBot/1.0` |
| `request_header[Authorization]` | Add auth header | `request_header[Authorization]=Bearer token123` |
| `request_header[X-Custom]` | Any custom header | `request_header[X-Custom]=value` |

### Response Headers

Add custom response headers using `response_header[NAME]` format:

| Parameter | Description | Example |
|-----------|-------------|---------|
| `response_header[X-Custom]` | Add custom response header | `response_header[X-Custom]=test` |
| `response_header[Access-Control-Allow-Origin]` | CORS header | `response_header[Access-Control-Allow-Origin]=*` |

### TLS Skip Options

The `skip_tls_checks` parameter accepts:

| Value | Description |
|-------|-------------|
| `all` | Skip all TLS verification |
| `hostname_mismatch` | Skip hostname verification |
| `expired_cert` | Skip certificate expiration check |
| `self_signed` | Skip self-signed certificate check |
| `cert_authority` | Skip certificate authority validation |
| `weak_cipher` | Allow weak ciphers |

Multiple values can be comma-separated: `skip_tls_checks=expired_cert,self_signed`

## Instance Configuration

Configure each proxy instance with:

| Setting | Description | Values | Default |
|---------|-------------|--------|---------|
| **Name** | Unique endpoint identifier | String | `external-api-route` |
| **Timeout** | Request timeout | 30-3600 seconds | 300 |
| **Outbound Access** | Destination restrictions | `any`, `external`, `internal`, CIDR | `any` |
| **Inbound Access** | Client IP restrictions | CIDR range | None |
| **Requires Auth** | HA authentication required | `true`, `false` | `true` |
| **Tokens** | Authentication tokens | List of UUIDs | Auto-generated |

### Network Access Control

**Outbound Access (restrict_out):**
- `any` - Allow all destinations
- `external` - Only external/public IPs
- `internal` - Only private network IPs (10.x, 172.16-31.x, 192.168.x)
- Custom CIDR - Specific IP ranges (e.g., `10.0.0.0/8`)

**Inbound Access (restrict_in):**
- CIDR notation to restrict client IPs (e.g., `192.168.1.0/24`)
- Empty = allow from any IP

## Examples

### Basic GET Request
```bash
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=abc123&url=https://httpbin.org/get"
```

### POST with JSON Data
```bash
curl -X POST "http://localhost:8123/api/homie_proxy/external-api-route?token=abc123&url=https://httpbin.org/post" \
     -H "Content-Type: application/json" \
     -d '{"test": "data"}'
```

### Custom Headers and Host Override
```bash
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=abc123&url=https://httpbin.org/headers&request_header%5BHost%5D=custom.example.com&request_header%5BUser-Agent%5D=MyBot"
```

### TLS Bypass for Self-Signed Certificates
```bash
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=abc123&url=https://self-signed.example.com&skip_tls_checks=self_signed"
```

### Streaming Large Files
```bash
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=abc123&url=https://example.com/largefile.zip" -o download.zip
```

### WebSocket Connections
```bash
curl -H "Connection: Upgrade" -H "Upgrade: websocket" \
     "http://localhost:8123/api/homie_proxy/external-api-route?token=abc123&url=wss://echo.websocket.org"
```

### Custom Response Headers (CORS)
```bash
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=abc123&url=https://httpbin.org/get&response_header%5BAccess-Control-Allow-Origin%5D=*"
```

### Extended Timeout for Long Operations
```bash
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=abc123&url=https://slow-api.example.com&timeout=1800"
```

## URL Encoding

When using special characters in parameter values, ensure proper URL encoding:

| Character | Encoded | Usage |
|-----------|---------|-------|
| `[` | `%5B` | Header parameter names |
| `]` | `%5D` | Header parameter names |
| `=` | `%3D` | Header parameter values |
| `&` | `%26` | Header parameter values |
| `+` | `%2B` | Header parameter values |

## Testing

Run the comprehensive test suite:

```bash
# All tests
python tests/run_all_tests.py

# Bash integration tests
bash test_ha_integration.sh --mode ha --instance INSTANCE_NAME --token TOKEN

# Specific functionality
python tests/test_http_methods.py
python tests/test_websocket.py
python tests/test_streaming_performance.py
```

## Development

```bash
git clone <repo>
cd python-reverse-proxy

# DevContainer with pre-configured Home Assistant
code .  # Open in VS Code and reopen in container

# HA: localhost:8123
# Standalone: localhost:8080
```

## License

MIT License