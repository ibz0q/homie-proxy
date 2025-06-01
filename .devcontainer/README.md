# Home Assistant + Homie Proxy Development Environment

This devcontainer provides a complete development environment for **Homie Proxy** - a powerful HTTP reverse proxy with native Home Assistant integration, streaming performance optimization, and comprehensive security features.

## 🚀 Quick Start

1. **Open in VS Code** with Dev Containers extension
2. **Reopen in Container** when prompted  
3. **Wait for setup** to complete (containers will build and start)
4. **Access services:**
   - **Home Assistant**: http://localhost:8123
   - **Homie Proxy**: Via HA integration at `/api/homie_proxy/`

## 🌟 What's Included

### Home Assistant with Homie Proxy Integration
- **Latest Home Assistant** container with development config
- **Homie Proxy integration** pre-installed and configured
- **Multiple proxy instances** with different security settings
- **Token-based authentication** with automatic UUID generation
- **Streaming performance** optimized for large files/videos
- **Debug endpoints** for real-time configuration management

### Development Tools
- **VS Code** with Python, YAML, JSON extensions
- **Comprehensive test suite** (21 tests with 100% success rate)
- **Live reload** for integration development
- **Docker integration** for consistent environments

## 📝 Testing the Homie Proxy Integration

### Get Authentication Token

```bash
# View all configured instances and their tokens
curl http://localhost:8123/api/homie_proxy/debug

# Example response shows your actual tokens:
# {
#   "instances": {
#     "external-api-route": {
#       "tokens": ["93f00721-b834-460e-96f0-9978eb594e3f"]
#     }
#   }
# }
```

### Basic Proxy Functionality

```bash
# Replace TOKEN with your actual token from debug endpoint
TOKEN="your-actual-token-from-debug"

# Basic GET request
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=$TOKEN&url=https://httpbin.org/get"

# POST with JSON data
curl -X POST "http://localhost:8123/api/homie_proxy/external-api-route?token=$TOKEN&url=https://httpbin.org/post" \
     -H "Content-Type: application/json" \
     -d '{"test": "development data"}'

# Test all HTTP methods
curl -X PUT "http://localhost:8123/api/homie_proxy/external-api-route?token=$TOKEN&url=https://httpbin.org/put" -d '{"method":"PUT"}'
curl -X DELETE "http://localhost:8123/api/homie_proxy/external-api-route?token=$TOKEN&url=https://httpbin.org/anything"
```

### Advanced Features Testing

```bash
# Custom headers
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=$TOKEN&url=https://httpbin.org/headers&request_header%5BX-Custom%5D=TestValue"

# TLS bypass for development
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=$TOKEN&url=https://self-signed.badssl.com&skip_tls_checks=all"

# Host header override
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=$TOKEN&url=https://httpbin.org/headers&request_header%5BHost%5D=custom.example.com"

# Redirect control
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=$TOKEN&url=https://httpbin.org/redirect/1&follow_redirects=true"
```

### Security Testing

```bash
# Authentication testing (should fail with 401)
curl "http://localhost:8123/api/homie_proxy/external-api-route?url=https://httpbin.org/get"

# Invalid token (should fail with 401)
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=invalid-token&url=https://httpbin.org/get"

# Network access control (try internal IP - should be blocked)
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=$TOKEN&url=http://192.168.1.1"
```

### Performance Testing

```bash
# Stream large content (1MB) - optimized streaming
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=$TOKEN&url=https://httpbin.org/bytes/1048576" -o test_download.bin

# Check download speed and size
ls -lh test_download.bin
```

## 🧪 Comprehensive Test Suite

Run the complete test suite with **21 comprehensive tests**:

```bash
# Run all integration tests (should show 21/21 passing)
./test_ha_integration.sh --mode ha --port 8123

# Run with verbose output
./test_ha_integration.sh --mode ha --port 8123 | tee test_results.log
```

### Test Coverage Includes:
- ✅ **Core HTTP methods** (GET, POST, PUT, PATCH, DELETE, HEAD)
- ✅ **Authentication** (valid tokens, invalid tokens, missing tokens)
- ✅ **Security controls** (network access, URL validation)
- ✅ **Advanced features** (custom headers, TLS bypass, redirects)
- ✅ **Performance** (streaming large content)

## 🔧 Development Commands

### Integration Development

```bash
# Restart Home Assistant after code changes
docker restart ha-dev

# View integration logs
docker logs ha-dev -f | grep -i homie

# Check integration status
curl http://localhost:8123/api/homie_proxy/debug | jq

# Test specific functionality
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=TOKEN&url=https://httpbin.org/get"
```

### Container Management

```bash
# View all container logs
docker-compose -f .devcontainer/docker-compose.yml logs -f

# Restart specific services
docker-compose -f .devcontainer/docker-compose.yml restart homeassistant

# Access container shells
docker exec -it ha-dev bash              # Home Assistant shell
docker exec -it homie-proxy-dev bash     # Standalone proxy shell
```

### Development Workflow

```bash
# 1. Make changes to integration code in custom_components/homie_proxy/
# 2. Restart Home Assistant
docker restart ha-dev

# 3. Run tests to verify functionality
./test_ha_integration.sh --mode ha --port 8123

# 4. Check specific features
curl http://localhost:8123/api/homie_proxy/debug
```

## 📁 File Structure

```
.devcontainer/
├── devcontainer.json       # VS Code configuration
├── docker-compose.yml      # HA + Proxy services
├── configuration.yaml      # HA config with Homie Proxy
└── README.md              # This file

custom_components/homie_proxy/
├── __init__.py            # Main integration entry point
├── proxy.py               # Proxy implementation with streaming
├── config_flow.py         # HA configuration UI flow
├── const.py               # Network constants and CIDRs
└── manifest.json          # Integration manifest

test_ha_integration.sh     # Comprehensive test suite (21 tests)
```

## 🐛 Troubleshooting

### Integration Not Loading

```bash
# Check if files are present
docker exec -it ha-dev ls -la /config/custom_components/homie_proxy/

# Check Home Assistant logs for errors
docker logs ha-dev | grep -i homie

# Verify integration loading
curl http://localhost:8123/api/homie_proxy/debug
```

### Authentication Issues

```bash
# Get valid tokens from debug endpoint
curl http://localhost:8123/api/homie_proxy/debug | jq '.instances'

# Test with correct token format
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=93f00721-b834-460e-96f0-9978eb594e3f&url=https://httpbin.org/get"
```

### Performance Issues

```bash
# Check if streaming is working (should be fast)
time curl "http://localhost:8123/api/homie_proxy/external-api-route?token=TOKEN&url=https://httpbin.org/bytes/1048576" -o /dev/null

# Monitor memory usage during large downloads
docker stats ha-dev
```

### Network Access Issues

```bash
# Check configured network restrictions
curl http://localhost:8123/api/homie_proxy/debug | jq '.instances."external-api-route"'

# Test different target URLs to understand restrictions
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=TOKEN&url=https://httpbin.org/get"  # Should work
curl "http://localhost:8123/api/homie_proxy/external-api-route?token=TOKEN&url=http://192.168.1.1"      # Should be blocked
```

## 🚀 Key Features Demonstrated

- **🔒 Security**: Token authentication, network access controls, SSRF protection
- **⚡ Performance**: Streaming for large files, memory efficiency, concurrent handling  
- **🌐 Protocols**: All HTTP methods, custom headers, TLS bypass, redirect control
- **🏠 Integration**: Native HA integration, multiple instances, debug endpoints
- **🧪 Testing**: 21 comprehensive tests, 100% success rate, full feature coverage

## 🎯 Next Steps for Development

1. **Explore the integration** using the examples above
2. **Run the test suite** to understand all capabilities
3. **Modify configuration** in `custom_components/homie_proxy/`
4. **Test changes** with `docker restart ha-dev`
5. **Add new features** following the established patterns
6. **Verify with tests** using `./test_ha_integration.sh`

## 🔗 Useful Links

- **[Home Assistant Integration Docs](https://developers.home-assistant.io/docs/creating_component_index/)**
- **[HTTP View Documentation](https://developers.home-assistant.io/docs/api/rest/)**
- **[Testing with httpbin.org](https://httpbin.org/)** 
- **[aiohttp Documentation](https://docs.aiohttp.org/)** (for HTTP handling) 