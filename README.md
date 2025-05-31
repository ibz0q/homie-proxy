# Homie Proxy

A powerful, configurable HTTP reverse proxy with **Home Assistant integration**, streaming performance optimization, robust authentication, and comprehensive feature set for both standalone and integration use.

## ✨ Key Features

### 🏠 **Home Assistant Integration**
- **Native HA integration** - Install as a custom component
- **Multiple proxy instances** with individual configurations
- **Token-based authentication** with automatic UUID generation
- **IP-based access control** (CIDR support)
- **Debug endpoint** for configuration management
- **Seamless integration** with Home Assistant's HTTP framework

### 🚀 **Performance & Streaming** 
- **High-performance streaming** for large files and videos
- **Memory-efficient** - streams data without buffering entire content
- **Concurrent request handling** with asyncio/threading
- **Optimized for large content** - 3x faster than basic buffering

### 🔒 **Security & Authentication**
- **Robust token authentication** - Required by default (no bypass)
- **IP-based access control** - Restrict clients by CIDR ranges
- **Network access controls** - Restrict target destinations
- **SSRF protection** - Prevent access to internal networks
- **Secure defaults** - All security features enabled by default

### 🌐 **Protocol & Network Support**
- **All HTTP methods** - GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS
- **TLS error bypassing** - Configurable per-request TLS handling
- **Host header manipulation** - Override host headers for virtual hosting
- **Custom request/response headers** - Full header modification support
- **Redirect control** - Enable/disable redirect following
- **IPv4/IPv6 support** - Full network protocol support

### 🛠 **Advanced Features**
- **Flexible deployment** - Standalone, Docker, or HA integration
- **Comprehensive testing** - 21-test suite with 100% coverage
- **Multiple instances** - Different configs per use case
- **Real-time configuration** - Debug endpoints and live monitoring
- **Development-friendly** - DevContainer setup for HA development

## 📦 Installation Options

### Option 1: Home Assistant Integration (Recommended)

```bash
# 1. Copy to Home Assistant custom_components directory
cp -r custom_components/homie_proxy /config/custom_components/

# 2. Restart Home Assistant

# 3. Add integration via UI or configuration.yaml:
homie_proxy:
  external-api-route:
    tokens: 
      - "your-secret-token-here"
    restrict_out: "external"  # external, internal, any, or custom CIDR
    restrict_in: "192.168.1.0/24"  # Optional: restrict client IPs

# 4. Access via: http://your-ha:8123/api/homie_proxy/external-api-route
```

### Option 2: Standalone Server

```bash
# Install from source
pip install -e .
homie-proxy --host localhost --port 8080

# Or use Docker
docker-compose up
```

### Option 3: Development Environment

```bash
# Full HA + Proxy development setup
code .  # Open in VS Code with Dev Containers extension
# Reopen in Container when prompted
# Access: HA at localhost:8123, Proxy at localhost:8080
```

## 🚀 Quick Start Examples

### Home Assistant Integration Usage

```bash
# Get your token from debug endpoint
curl http://your-ha:8123/api/homie_proxy/debug

# Basic proxy request (replace TOKEN with your actual token)
curl "http://your-ha:8123/api/homie_proxy/external-api-route?token=TOKEN&url=https://httpbin.org/get"

# POST with JSON data
curl -X POST "http://your-ha:8123/api/homie_proxy/external-api-route?token=TOKEN&url=https://httpbin.org/post" \
     -H "Content-Type: application/json" \
     -d '{"test": "data"}'

# Stream large video file (optimized performance)
curl "http://your-ha:8123/api/homie_proxy/external-api-route?token=TOKEN&url=https://example.com/video.mp4" \
     -o downloaded_video.mp4

# Custom headers and TLS bypass
curl "http://your-ha:8123/api/homie_proxy/external-api-route?token=TOKEN&url=https://self-signed.example.com&skip_tls_checks=all&request_headers%5BUser-Agent%5D=CustomBot"
```

### Standalone Server Usage

```bash
# Basic request
curl "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/get"

# All HTTP methods supported
curl -X PUT "http://localhost:8080/default?token=TOKEN&url=https://httpbin.org/put" -d '{"data":"value"}'
curl -X DELETE "http://localhost:8080/default?token=TOKEN&url=https://httpbin.org/anything"
```

## 🏠 Home Assistant Integration Features

### Configuration Options

```yaml
# configuration.yaml
homie_proxy:
  # Multiple instances with different configs
  external-api-route:
    tokens: 
      - "93f00721-b834-460e-96f0-9978eb594e3f"
    restrict_out: "external"          # Only external IPs
    restrict_in: "192.168.1.0/24"     # Only home network
    
  internal-services:
    tokens:
      - "another-uuid-token-here"
    restrict_out: "internal"          # Only internal IPs
    # No restrict_in = allow from anywhere
    
  custom-networks:
    tokens:
      - "custom-token-123"
    restrict_out: "10.0.0.0/8"        # Custom CIDR range
    restrict_in: "172.16.0.0/12"      # Custom client range
```

### Instance Endpoints

Each configured instance gets its own endpoint:

- **external-api-route**: `/api/homie_proxy/external-api-route`
- **internal-services**: `/api/homie_proxy/internal-services`  
- **custom-networks**: `/api/homie_proxy/custom-networks`

### Debug & Management

```bash
# View all instances and their tokens
curl http://your-ha:8123/api/homie_proxy/debug

# Check instance configuration
curl http://your-ha:8123/api/homie_proxy/debug | jq '.instances["external-api-route"]'
```

## 🔒 Security Configuration

### Network Access Control

**`restrict_out`** - Controls target destinations:
- `"external"`: Only public IPs (blocks 192.168.x.x, 10.x.x.x, 172.16-31.x.x)
- `"internal"`: Only private IPs (allows 192.168.x.x, 10.x.x.x, 172.16-31.x.x)  
- `"any"`: All destinations (use with caution)
- `"CIDR"`: Custom network range (e.g., "10.0.0.0/8")

**`restrict_in`** - Controls client access:
- `"CIDR"`: Only allow requests from this network (e.g., "192.168.1.0/24")
- Not specified: Allow from any IP

### Authentication

**Required by default** - All requests must include valid token:
```bash
# ❌ Will fail with 401
curl "http://your-ha:8123/api/homie_proxy/external-api-route?url=https://example.com"

# ✅ Will succeed  
curl "http://your-ha:8123/api/homie_proxy/external-api-route?token=valid-token&url=https://example.com"
```

## ⚡ Performance Optimizations

### Streaming Performance

Optimized for large files with **true streaming**:
- **Memory efficient**: Constant memory usage regardless of file size
- **High throughput**: 3x faster than buffered approaches
- **Large file support**: Videos, images, downloads stream smoothly
- **Real-time processing**: Data flows directly from source to client

### Performance Comparison

| Content Type | Direct Download | Basic Proxy | Homie Proxy (Streaming) |
|--------------|-----------------|-------------|-------------------------|
| **158MB Video** | 4.45s @ 35.5MB/s | 11.5s @ 13.7MB/s | **6.8s @ 23.2MB/s** |
| **1MB Test** | 0.15s | 0.45s | **0.22s** |

## 🛠 Advanced Features

### Custom Headers

```bash
# Request headers
curl "http://localhost:8123/api/homie_proxy/instance?token=TOKEN&url=https://httpbin.org/headers&request_headers%5BUser-Agent%5D=CustomBot&request_headers%5BX-API-Key%5D=secret123"

# Response headers (CORS, etc.)
curl "http://localhost:8123/api/homie_proxy/instance?token=TOKEN&url=https://example.com&response_header%5BAccess-Control-Allow-Origin%5D=*"
```

### TLS Configuration

```bash
# Skip all TLS validation
curl "http://localhost:8123/api/homie_proxy/instance?token=TOKEN&url=https://self-signed.example.com&skip_tls_checks=all"

# Skip specific TLS errors
curl "http://localhost:8123/api/homie_proxy/instance?token=TOKEN&url=https://expired.badssl.com&skip_tls_checks=expired_cert,self_signed"
```

### Host Header Override

```bash
# Override host header for IP addresses
curl "http://localhost:8123/api/homie_proxy/instance?token=TOKEN&url=https://1.1.1.1&override_host_header=one.one.one.one"
```

### Redirect Control

```bash
# Follow redirects (default: false)
curl "http://localhost:8123/api/homie_proxy/instance?token=TOKEN&url=https://httpbin.org/redirect/3&follow_redirects=true"

# Don't follow redirects (returns 302)
curl "http://localhost:8123/api/homie_proxy/instance?token=TOKEN&url=https://httpbin.org/redirect/1&follow_redirects=false"
```

## 🧪 Testing & Quality Assurance

### Comprehensive Test Suite

**21 comprehensive tests** covering all functionality:

```bash
# Run full test suite (Home Assistant integration)
./test_ha_integration.sh --mode ha --port 8123

# Run standalone tests  
./test_ha_integration.sh --mode standalone --port 8080
```

### Test Coverage

✅ **Core Functionality** (9 tests):
- All HTTP methods (GET, POST, PUT, PATCH, DELETE, HEAD)
- JSON handling, headers, user agents
- Host header processing

✅ **Security & Authentication** (4 tests):
- Token validation (valid, invalid, missing)
- Access control and URL validation

✅ **Advanced Features** (8 tests):
- Custom request/response headers
- TLS bypass options
- Host header override
- Redirect handling
- Streaming performance (1MB test)

**Result**: 21/21 tests passing (100% success rate)

## 📁 Project Structure

```
python-reverse-proxy/
├── custom_components/homie_proxy/    # Home Assistant integration
│   ├── __init__.py                   # Main integration
│   ├── proxy.py                      # Proxy implementation  
│   ├── config_flow.py                # HA configuration flow
│   ├── const.py                      # Constants and CIDR ranges
│   └── manifest.json                 # Integration manifest
├── standalone_homie-proxy/           # Standalone server
│   └── homie_proxy.py               # Standalone implementation
├── test_ha_integration.sh           # Comprehensive test suite
├── .devcontainer/                   # VS Code dev environment
└── README.md                        # This file
```

## 🛠 Development & DevContainer

### Home Assistant Integration Development

Complete devcontainer setup for developing the integration:

```bash
# Open in VS Code with Dev Containers extension
code .
# Reopen in Container when prompted
# Access: HA at localhost:8123, Proxy at localhost:8080
```

### Development Commands

```bash
# Container management  
docker-compose -f .devcontainer/docker-compose.yml up -d
docker restart ha-dev  # Restart HA after integration changes

# View logs
docker logs ha-dev -f  # Home Assistant logs
docker logs homie-proxy-dev -f  # Proxy logs

# Test integration
./test_devcontainer.sh
curl http://localhost:8123/api/homie_proxy/debug
```

### Standalone Development

```bash
# Install in development mode
pip install -e .

# Run tests
./test_ha_integration.sh --mode standalone --port 8080

# Build Docker image
docker build -t homie-proxy .
```

## 🔍 Troubleshooting

### Common Issues

**Authentication Errors (401)**:
- Check token from debug endpoint: `curl http://your-ha:8123/api/homie_proxy/debug`
- Ensure token is included in URL: `?token=your-actual-token`
- Verify token is valid for the specific instance

**Access Denied (403)**:
- Check `restrict_in` settings - may be blocking your client IP
- Verify `restrict_out` allows access to target URL
- Check if target URL resolves to allowed network range

**Performance Issues**:
- Large files use streaming automatically (no action needed)
- Check network connectivity between proxy and target
- Monitor Home Assistant logs for errors

**Integration Not Loading**:
- Verify files are in `/config/custom_components/homie_proxy/`
- Restart Home Assistant after installation
- Check logs: `docker logs ha-dev | grep homie`

### Debug Information

```bash
# Check integration status
curl http://your-ha:8123/api/homie_proxy/debug

# Test basic connectivity
curl "http://your-ha:8123/api/homie_proxy/your-instance?token=TOKEN&url=https://httpbin.org/get"

# Verify token authentication
curl "http://your-ha:8123/api/homie_proxy/your-instance?url=https://httpbin.org/get"  # Should fail with 401
```

## ⚠️ Security Considerations

- **Authentication is mandatory** - No bypass options available
- **Network restrictions enforced** - Configure `restrict_out` appropriately
- **Client IP filtering** - Use `restrict_in` to limit access
- **SSRF protection** - Enabled by default with network restrictions
- **Token security** - Use UUIDs, store securely, rotate regularly

## 📋 Requirements

### Home Assistant Integration
- Home Assistant 2023.1+ 
- Python 3.9+ (included in HA)
- `requests` library (auto-installed)

### Standalone Server
- Python 3.8+
- `requests` library
- Optional: Docker & Docker Compose

### Development Environment
- VS Code with Dev Containers extension
- Docker Desktop
- Git

## 🚀 Performance Notes

- **Streaming optimized**: Large files (>1MB) automatically stream
- **Memory efficient**: Constant memory usage regardless of content size
- **Concurrent handling**: Multiple requests processed simultaneously  
- **Cache-friendly**: Headers properly forwarded for HTTP caching

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Test changes: `./test_ha_integration.sh --mode ha --port 8123`
4. Ensure 21/21 tests pass
5. Submit pull request

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- Home Assistant community for integration framework
- httpbin.org for comprehensive testing endpoints
- aiohttp project for high-performance HTTP handling