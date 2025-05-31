# Homie Reverse Proxy

A lightweight, configurable HTTP reverse proxy server with authentication, TLS bypass capabilities, and robust connection handling.

## ✨ Features

- **Multi-instance support** with individual authentication
- **TLS error bypassing** for development and testing
- **Host header manipulation** for virtual host compatibility  
- **Request/response header modification**
- **Platform-agnostic** connection error handling
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

### Method 2: Direct Python

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python homie_proxy.py --host 0.0.0.0 --port 8080
```

## 🐳 Docker Deployment

Running in Docker Linux provides several advantages:

- **No Windows-specific errors** (eliminates WinError 10053/10054 issues)
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

## 🔧 Platform-Agnostic Error Handling

The proxy now handles connection aborts gracefully across all platforms:

- **Windows**: WinError 10053, 10054, 10055, 10056
- **Linux**: EPIPE (32), ECONNRESET (104), ETIMEDOUT (110), ECONNREFUSED (111)  
- **macOS**: Connection reset (54), Connection refused (61)
- **Pattern matching**: Detects connection errors by message content

## 📖 Usage Examples

### Basic Proxy Request
```bash
curl "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/get"
```

### TLS Bypass
```bash
curl "http://localhost:8080/default?token=your-secret-token-here&url=https://self-signed.badssl.com&skip_tls_checks=all"
```

### Host Header Override
```bash
curl "http://localhost:8080/default?token=your-secret-token-here&url=https://1.1.1.1&override_host_header=one.one.one.one&skip_tls_checks=all"
```

### Custom Headers
```bash
curl "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/headers&request_headers[User-Agent]=CustomBot/1.0&response_header[Access-Control-Allow-Origin]=*"
```

## 📁 Configuration

Edit `proxy_config.json`:

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

## 🛠 Development

### Running Tests
```bash
python test_winerror_fix.py
python tests/test_simple.py
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
- **Windows**: WinError 10053 errors are now handled gracefully
- **Docker**: Use Linux containers to avoid Windows networking quirks
- **Ports**: Ensure port 8080 isn't already in use

### TLS Issues  
- Use `skip_tls_checks=all` for development
- Verify target server TLS configuration
- Check certificate validity dates

## 📋 Requirements

- Python 3.8+
- `requests` library
- Docker (optional, recommended)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Test on multiple platforms (Windows, Linux, macOS)
4. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details