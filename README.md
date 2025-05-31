# HomieProxy

A high-performance HTTP reverse proxy with **Home Assistant integration**, optimized for streaming, authentication, and secure network access control.

## What It Does

HomieProxy acts as a secure reverse proxy that:
- **Proxies HTTP/HTTPS requests** with token-based authentication
- **Streams large files efficiently** (videos, downloads) without memory buffering
- **Controls network access** (internal-only, external-only, or custom CIDR ranges)
- **Handles WebSocket connections** for real-time applications
- **Integrates natively with Home Assistant** as a custom component

Perfect for securely accessing external APIs, streaming media files, or proxying requests through Home Assistant.

## Installation & Usage

### 🏠 Home Assistant Integration (Recommended)

```bash
# 1. Install as custom component
cp -r custom_components/homie_proxy /config/custom_components/

# 2. Restart Home Assistant

# 3. Add via UI (Settings > Integrations > Add Integration > HomieProxy)
# Or add to configuration.yaml:
homie_proxy:
  external-api-route:
    tokens: ["your-generated-token"]
    restrict_out: "external"  # external, internal, any, or CIDR
    restrict_in: "192.168.1.0/24"  # Optional: restrict client IPs

# 4. Use the proxy
curl "http://your-ha:8123/api/homie_proxy/external-api-route?token=TOKEN&url=https://httpbin.org/get"
```

**Debug endpoint** to get your tokens: `http://your-ha:8123/api/homie_proxy/debug`

### ⚡ Standalone Server

```bash
# Install and run
pip install -e .
homie-proxy --host localhost --port 8080

# Use the proxy
curl "http://localhost:8080/default?token=your-secret-token&url=https://httpbin.org/get"
```

### 🐳 Docker

```bash
docker-compose up
# Proxy available at localhost:8080
```

## Development

```bash
# Clone and develop
git clone <repo>
cd python-reverse-proxy

# For HA integration development (DevContainer)
code .  # Open in VS Code
# Reopen in Container when prompted
# HA runs at localhost:8123, standalone at localhost:8080

# Run tests
python tests/run_all_tests.py
```

The DevContainer provides a complete development environment with Home Assistant pre-configured.

## Features

### 🔒 **Security**
- **Required token authentication** - No bypass options
- **Network access control** - Restrict destinations (internal/external/CIDR)
- **Client IP filtering** - CIDR-based access control
- **SSRF protection** - Prevents internal network access

### 🚀 **Performance** 
- **Streaming optimized** - Memory-efficient for large files
- **WebSocket support** - Real-time connections
- **Concurrent handling** - Multiple requests simultaneously
- **All HTTP methods** - GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS

### 🏠 **Home Assistant**
- **Multiple instances** - Different configs per use case
- **Native integration** - Uses HA's HTTP framework
- **Token management** - Automatic UUID generation
- **Debug interface** - Configuration visibility

## Quick Examples

```bash
# Stream a large video file
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=TOKEN&url=https://example.com/video.mp4" -o video.mp4

# POST JSON data
curl -X POST "http://localhost:8123/api/homie_proxy/external-api-route?token=TOKEN&url=https://httpbin.org/post" \
     -H "Content-Type: application/json" -d '{"test": "data"}'

# Custom headers and TLS bypass
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=TOKEN&url=https://self-signed.example.com&skip_tls_checks=all&request_headers%5BUser-Agent%5D=CustomBot"

# Follow redirects
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=TOKEN&url=https://httpbin.org/redirect/3&follow_redirects=true"
```

## Configuration

### Network Access Control
- **`restrict_out: "external"`** - Only allow external/public IPs
- **`restrict_out: "internal"`** - Only allow private network IPs  
- **`restrict_out: "any"`** - Allow all destinations
- **`restrict_out: "10.0.0.0/8"`** - Custom CIDR range

### Client Access Control  
- **`restrict_in: "192.168.1.0/24"`** - Only allow requests from home network
- **No `restrict_in`** - Allow requests from any IP

## Testing

Comprehensive test suite with 10+ test files covering:
- All HTTP methods and data types
- WebSocket functionality  
- Redirect following
- Streaming performance
- Security and authentication
- Network access controls

```bash
# Run all tests
python tests/run_all_tests.py

# Run specific test
python tests/test_http_methods.py
```

## License

MIT License - See LICENSE file for details.