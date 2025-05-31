# Homie Proxy

A lightweight, configurable HTTP proxy server with authentication, TLS bypass capabilities, and robust connection handling.

## ✨ Features

- **Multi-instance support** with individual authentication
- **TLS error bypassing** for development and testing
- **Host header manipulation** for virtual host compatibility  
- **Request/response header modification**
- **Concurrent request handling** with threading
- **Docker support** for consistent deployment

## 📦 Installation

### Method 1: Package Installation (Recommended for Module Use)

```bash
# Install from source (in project directory)
pip install -e .

# Or install from Git repository
pip install git+https://github.com/yourusername/homie-proxy.git

# Then use as command-line tool
homie-proxy --host localhost --port 8080

# Or import in Python scripts
python -c "from homie_proxy import HomieProxyServer; print('Module ready!')"
```

### Method 2: Direct File Usage

```bash
# Clone and use directly
git clone https://github.com/yourusername/homie-proxy.git
cd homie-proxy
pip install -r requirements.txt
python homie_proxy.py
```

### Method 3: Docker (Standalone)

```bash
# Use without installing Python dependencies
docker-compose up
```

## 🚀 Quick Start

### Method 1: Docker Compose (Recommended for Development)

```bash
# Start the proxy for development
docker-compose up

# Run in background (detached mode)
docker-compose up -d

# Stop the proxy (immediate shutdown)
docker-compose down
```

### Method 2: Docker Manual (Production)

```bash
# Build and run manually
docker build -t homie-proxy .
docker run -p 8080:8080 -v $(pwd)/proxy_config.json:/app/proxy_config.json:ro homie-proxy
```

### Method 3: Direct Python (Not Recommended - Use Docker)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the server
python homie_proxy.py --host 0.0.0.0 --port 8080
```

## 🐳 Docker Deployment

### Development with Docker Compose

**Recommended for development** - provides the best development experience:

- **Instant shutdown** (`stop_grace_period: 0s`) for fast iteration
- **Live configuration reloading** via volume mounts
- **Consistent environment** across all developers
- **Easy port management** and networking

```yaml
# docker-compose.yml
services:
  homie-proxy:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./proxy_config.json:/app/proxy_config.json:ro
    restart: unless-stopped
    stop_grace_period: 0s
```

### Production Deployment

Running in Docker Linux provides several advantages:

- **Consistent behavior** across all environments
- **Production-ready** networking stack
- **Easy scaling** and deployment

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

## 🐍 Using as a Python Module

The proxy can be imported and used as a module in your Python applications:

### Basic Module Usage

```python
from homie_proxy import HomieProxyServer, create_proxy_config

# Method 1: File-based configuration
server = HomieProxyServer('proxy_config.json')
server.run(host='localhost', port=8080)

# Method 2: Programmatic configuration
server = HomieProxyServer()
server.add_instance('api', {
    'restrict_out': 'external',
    'tokens': ['secret-key'],
    'restrict_in_cidrs': []
})
server.run()
```

### Advanced Module Usage

```python
import threading
from homie_proxy import HomieProxyServer, create_proxy_config

# Create instances programmatically
instances_config = {
    'web_scraper': {
        'restrict_out': 'external',
        'tokens': ['scraper-token'],
        'restrict_in_cidrs': []
    },
    'api_gateway': {
        'restrict_out': 'both',
        'restrict_out_cidrs': ['192.168.0.0/16'],
        'tokens': ['gateway-key'],
        'restrict_in_cidrs': ['172.16.0.0/12']
    }
}

instances = create_proxy_config(instances_config)
server = HomieProxyServer(instances=instances)

# Run in background thread
def run_proxy():
    server.run(host='localhost', port=8080)

proxy_thread = threading.Thread(target=run_proxy, daemon=True)
proxy_thread.start()
```

### Module API Reference

**HomieProxyServer Methods:**
- `add_instance(name, config)` - Add proxy instance
- `remove_instance(name)` - Remove proxy instance  
- `list_instances()` - Get list of instance names
- `get_instance_config(name)` - Get instance configuration
- `run(host, port)` - Start the proxy server

**Helper Functions:**
- `create_proxy_config(instances_dict)` - Create instances from dict
- `create_default_config()` - Get default configuration

See `example_module_usage.py` for complete examples.

## 📁 Configuration

Edit `proxy_config.json`:

```json
{
  "instances": {
    "default": {
      "restrict_out": "both",
      "tokens": ["your-secret-token-here"],
      "restrict_in_cidrs": []
    },
    "external-only": {
      "restrict_out": "external",
      "tokens": ["external-token-123"],
      "restrict_in_cidrs": ["192.168.1.0/24", "10.0.0.0/8"]
    },
    "internal-only": {
      "restrict_out": "internal", 
      "tokens": [],
      "restrict_in_cidrs": []
    },
    "custom-networks": {
      "restrict_out": "both",
      "restrict_out_cidrs": ["8.8.8.0/24", "1.1.1.0/24", "192.168.0.0/16"],
      "tokens": ["custom-token"],
      "restrict_in_cidrs": []
    }
  }
}
```

### Configuration Options

**`restrict_out`** - Controls which target networks the proxy can reach:
- `"external"`: Only external/public IPs (denies private/internal IPs like 192.168.x.x, 10.x.x.x, 172.16-31.x.x)
- `"internal"`: Only internal/private IPs (allows only 192.168.x.x, 10.x.x.x, 172.16-31.x.x, 127.x.x.x)  
- `"both"`: Allow all IPs (0.0.0.0/0 - no restrictions)

**`restrict_out_cidrs`** - Specific CIDR ranges for outbound access:
- If specified: Only allow requests to these specific CIDR ranges (overrides `restrict_out`)
- If empty/not specified: Use `restrict_out` mode
- Provides fine-grained control over exactly which networks can be accessed

**`restrict_in_cidrs`** - Controls which client IPs can access this proxy instance:
- If specified: Only allow requests from these CIDR ranges
- If empty/not specified: Allow all IPs (0.0.0.0/0 - no restrictions)

**`tokens`** - Authentication tokens required for this instance:
- If empty: No authentication required
- If specified: Must provide valid token in `?token=` parameter

### Example Use Cases

- **`custom-networks`**: Allow access only to specific services (DNS servers, specific subnets)
- **`external-only`**: Block access to internal networks (prevent SSRF attacks)
- **`internal-only`**: Only allow access to internal services (development/testing)

## 🛠 Development

### Recommended Development Workflow

```bash
# Start the proxy for development (with live config reloading)
docker-compose up

# Make changes to proxy_config.json - they're reflected immediately
# Changes to homie_proxy.py require restart:
docker-compose down && docker-compose up
```

### Running Tests
```bash
# With proxy running via docker-compose
python run_all_tests.py

# Or run comprehensive shell tests
bash run_manual_tests.sh
```

### Local Development (Alternative)
```bash
# Install in development mode
pip install -e .

# Run the server locally
python homie_proxy.py --host 127.0.0.1 --port 8080
```

## 🏠 Home Assistant Integration Development

This project includes a complete devcontainer setup for developing Home Assistant integrations alongside the Homie Proxy. The setup includes a custom hello-world integration that demonstrates API endpoint creation.

### Quick Start with DevContainer

1. **Open in VS Code** with the Dev Containers extension
2. **Reopen in Container** when prompted
3. **Wait for setup** to complete (containers will build and start)
4. **Test the setup:**
   ```bash
   # Run the test script
   ./test_devcontainer.sh
   
   # Or test manually
   curl http://localhost:8123/api/hello_world
   curl http://localhost:8123/api/hello_world?name=Developer
   ```

### Available Services

- **🏠 Home Assistant**: http://localhost:8123
  - Custom hello-world integration pre-installed
  - API endpoints: `/api/hello_world` and `/api/hello_world/info`
  - Development-friendly configuration with debug logging

- **🌐 Homie Proxy**: http://localhost:8080  
  - Full proxy functionality
  - Network connectivity to Home Assistant
  - Test endpoint integration capabilities

### Hello World Integration

The included integration demonstrates how to create custom Home Assistant components following the [official developer documentation](https://developers.home-assistant.io/docs/creating_component_index/):

**API Endpoints:**
```bash
# Basic hello world
curl http://localhost:8123/api/hello_world

# Personalized greeting  
curl "http://localhost:8123/api/hello_world?name=Developer"

# POST with custom message
curl -X POST http://localhost:8123/api/hello_world \
  -H "Content-Type: application/json" \
  -d '{"message": "Greetings", "name": "World"}'

# Integration info
curl http://localhost:8123/api/hello_world/info

# Integration state
curl http://localhost:8123/api/states/hello_world.status
```

**Expected Response:**
```json
{
  "message": "Hello, World! 🌍",
  "status": "success", 
  "timestamp": "2024-01-15T12:00:00.000000",
  "integration": "hello_world",
  "version": "1.0.0",
  "endpoints": {
    "hello": "/api/hello_world",
    "info": "/api/hello_world/info"
  }
}
```

### Development Commands

```bash
# Container management
docker-compose -f .devcontainer/docker-compose.yml logs -f
docker-compose -f .devcontainer/docker-compose.yml restart homeassistant

# View logs
docker logs ha-dev -f                    # Home Assistant logs
docker logs homie-proxy-dev -f           # Proxy logs  

# Access containers
docker exec -it ha-dev bash              # Home Assistant shell
docker exec -it homie-proxy-dev bash     # Proxy shell

# Integration development
docker restart ha-dev                    # Restart after code changes
```

### File Structure

```
.devcontainer/
├── devcontainer.json       # VS Code configuration
├── docker-compose.yml      # Services definition  
├── configuration.yaml      # Home Assistant config
├── setup.sh               # Environment setup
└── README.md              # DevContainer documentation

custom_components/
└── hello_world/
    ├── manifest.json      # Integration manifest
    └── __init__.py        # Main integration code
```

See `.devcontainer/README.md` for detailed development instructions and troubleshooting.

## 🔍 Troubleshooting

### Connection Issues
- **Docker**: Use Linux containers for best performance
- **Ports**: Ensure port 8080 isn't already in use
- **Quick restart**: Use `docker-compose down && docker-compose up` for instant restart

### TLS Issues  
- Use `skip_tls_checks=true` for development
- Verify target server TLS configuration
- Check certificate validity dates

## 📋 Requirements

- Python 3.8+
- `requests` library
- Docker (recommended)
- Docker Compose (for development)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Test with `docker-compose up` and run tests
4. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details