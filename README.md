# Homie Proxy

A lightweight, configurable HTTP proxy server with authentication, TLS bypass capabilities, and robust connection handling.

## ✨ Features

- **Multi-instance support** with individual authentication
- **TLS error bypassing** for development and testing
- **Host header manipulation** for virtual host compatibility  
- **Request/response header modification**
- **Concurrent request handling** with threading
- **Docker support** for consistent deployment

## 🚀 Quick Start

### Method 1: Docker (Recommended)

```bash
# Build and run with Docker Compose
docker-compose up -d

# Or build and run manually
docker build -t homie-proxy .
docker run -p 8080:8080 -v $(pwd)/proxy_config.json:/app/proxy_config.json:ro homie-proxy
```

### Method 2: Direct Python (Not Recommended - Use Linux or Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python homie_proxy.py --host 0.0.0.0 --port 8080
```

## 🐳 Docker Deployment

Running in Docker Linux provides several advantages:

- **Consistent behavior** across all environments
- **Production-ready** networking stack
- **Easy scaling** and deployment

```yaml
# docker-compose.yml
version: '3.8'
services:
  homie-proxy:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./proxy_config.json:/app/proxy_config.json:ro
    restart: unless-stopped
```

## 📖 Usage Examples

```
# Basic proxy request
http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/get

# TLS bypass for self-signed certificates
http://localhost:8080/default?token=your-secret-token-here&url=https://self-signed.badssl.com&skip_tls_checks=true

# Custom request headers
http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/headers&request_headers[User-Agent]=CustomBot/1.0

# Custom response headers (CORS)
http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/get&response_header[Access-Control-Allow-Origin]=*

# POST request with JSON data
curl -X POST "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/post" \
     -H "Content-Type: application/json" \
     -d '{"test": "data"}'

# Host header override for IP addresses
http://localhost:8080/default?token=your-secret-token-here&url=https://1.1.1.1&override_host_header=one.one.one.one&skip_tls_checks=true
```

## 📁 Configuration

Edit `proxy_config.json`:

```json
{
  "instances": {
    "default": {
      "allowed_networks_out": "both",
      "tokens": ["your-secret-token-here"],
      "restrict_access_to_cidrs": []
    },
    "external-only": {
      "allowed_networks_out": "external",
      "tokens": ["external-token-123"],
      "restrict_access_to_cidrs": ["192.168.1.0/24", "10.0.0.0/8"]
    },
    "internal-only": {
      "allowed_networks_out": "internal", 
      "tokens": [],
      "restrict_access_to_cidrs": []
    },
    "custom-networks": {
      "allowed_networks_out": "both",
      "allowed_networks_out_cidrs": ["8.8.8.0/24", "1.1.1.0/24", "192.168.0.0/16"],
      "tokens": ["custom-token"],
      "restrict_access_to_cidrs": []
    }
  }
}
```

### Configuration Options

**`allowed_networks_out`** - Controls which target networks the proxy can reach:
- `"external"`: Only external/public IPs (denies private/internal IPs like 192.168.x.x, 10.x.x.x, 172.16-31.x.x)
- `"internal"`: Only internal/private IPs (allows only 192.168.x.x, 10.x.x.x, 172.16-31.x.x, 127.x.x.x)  
- `"both"`: Allow all IPs (0.0.0.0/0 - no restrictions)

**`allowed_networks_out_cidrs`** - Specific CIDR ranges for outbound access:
- If specified: Only allow requests to these specific CIDR ranges (overrides `allowed_networks_out`)
- If empty/not specified: Use `allowed_networks_out` mode
- Provides fine-grained control over exactly which networks can be accessed

**`restrict_access_to_cidrs`** - Controls which client IPs can access this proxy instance:
- If specified: Only allow requests from these CIDR ranges
- If empty/not specified: Only allow local IPs (127.0.0.1, private networks)

**`tokens`** - Authentication tokens required for this instance:
- If empty: No authentication required
- If specified: Must provide valid token in `?token=` parameter

### Example Use Cases

- **`custom-networks`**: Allow access only to specific services (DNS servers, specific subnets)
- **`external-only`**: Block access to internal networks (prevent SSRF attacks)
- **`internal-only`**: Only allow access to internal services (development/testing)

## 🛠 Development

### Running Tests
```bash
python run_all_tests.py
```

### Local Development
```bash
# Install in development mode
pip install -e .

# Run with auto-reload (if using a tool like nodemon for Python)
python homie_proxy.py --host 127.0.0.1 --port 8080
```

## 🔍 Troubleshooting

### Connection Issues
- **Docker**: Use Linux containers for best performance
- **Ports**: Ensure port 8080 isn't already in use

### TLS Issues  
- Use `skip_tls_checks=true` for development
- Verify target server TLS configuration
- Check certificate validity dates

## 📋 Requirements

- Python 3.8+
- `requests` library
- Docker (recommended)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Test with Docker
4. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details