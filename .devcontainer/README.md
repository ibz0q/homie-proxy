# Home Assistant + Homie Proxy Development Environment

This devcontainer provides a complete development environment for both Home Assistant integration development and the Homie Proxy server.

## 🚀 Quick Start

1. **Open in VS Code with Dev Containers extension**
2. **Reopen in Container** when prompted
3. **Wait for setup** to complete (containers will build and start)
4. **Access services:**
   - Home Assistant: http://localhost:8123
   - Homie Proxy: http://localhost:8080

## 🌟 What's Included

### Home Assistant
- Latest Home Assistant container
- Custom hello-world integration pre-installed
- Development-friendly configuration
- API endpoints enabled
- Debug logging for custom components

### Homie Proxy  
- Full proxy server with configuration
- Network connectivity to Home Assistant
- Docker-based setup matching production

### Development Tools
- Python with VS Code extensions
- YAML/JSON editing support
- Git integration
- Port forwarding for easy access

## 📝 Testing the Hello World Integration

The custom hello-world integration creates several API endpoints you can test:

### Main Hello World Endpoint
```bash
# Basic hello world
curl http://localhost:8123/api/hello_world

# Personalized greeting
curl "http://localhost:8123/api/hello_world?name=Developer"

# POST with custom message
curl -X POST http://localhost:8123/api/hello_world \
  -H "Content-Type: application/json" \
  -d '{"message": "Greetings", "name": "World"}'
```

### Integration Info Endpoint
```bash
# Get integration information
curl http://localhost:8123/api/hello_world/info
```

### Expected Response Format
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
  },
  "setup_time": "2024-01-15T11:59:30.000000",
  "uptime": "0:00:30.000000"
}
```

## 🔧 Development Commands

### Container Management
```bash
# View logs
docker-compose -f .devcontainer/docker-compose.yml logs -f

# Restart Home Assistant only
docker-compose -f .devcontainer/docker-compose.yml restart homeassistant

# Restart everything
docker-compose -f .devcontainer/docker-compose.yml down
docker-compose -f .devcontainer/docker-compose.yml up -d

# Access Home Assistant container shell
docker exec -it ha-dev bash

# Access Homie Proxy container shell  
docker exec -it homie-proxy-dev bash
```

### Integration Development
```bash
# View Home Assistant logs
docker-compose -f .devcontainer/docker-compose.yml logs -f homeassistant

# Check integration status in Home Assistant
curl http://localhost:8123/api/states/hello_world.status

# Reload custom integrations (requires restart)
docker-compose -f .devcontainer/docker-compose.yml restart homeassistant
```

## 📁 File Structure

```
.devcontainer/
├── devcontainer.json       # VS Code devcontainer configuration
├── docker-compose.yml      # Services definition
├── configuration.yaml      # Home Assistant config
├── setup.sh               # Environment setup script
├── automations.yaml       # HA automations (empty)
├── scenes.yaml            # HA scenes (empty)  
├── scripts.yaml           # HA scripts (empty)
└── README.md              # This file

custom_components/
└── hello_world/
    ├── manifest.json      # Integration manifest
    └── __init__.py        # Main integration code
```

## 🐛 Troubleshooting

### Home Assistant Not Starting
```bash
# Check logs for errors
docker-compose -f .devcontainer/docker-compose.yml logs homeassistant

# Verify configuration
docker exec -it ha-dev python -m homeassistant --script check_config --config /config
```

### Integration Not Loading
```bash
# Check if integration files are copied
docker exec -it ha-dev ls -la /config/custom_components/hello_world/

# View integration-specific logs
docker-compose -f .devcontainer/docker-compose.yml logs homeassistant | grep hello_world
```

### API Endpoints Not Working
```bash
# Check if Home Assistant is fully started
curl http://localhost:8123/api/

# Verify integration state
curl http://localhost:8123/api/states/hello_world.status
```

## 🎯 Next Steps

1. **Modify the integration** in `custom_components/hello_world/`
2. **Restart Home Assistant** to reload changes
3. **Test endpoints** with curl or browser
4. **View logs** for debugging
5. **Extend functionality** as needed

## 🔗 Useful Links

- [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- [Integration Development](https://developers.home-assistant.io/docs/creating_component_index/)
- [API Documentation](https://developers.home-assistant.io/docs/api/rest/)
- [Custom Components](https://developers.home-assistant.io/docs/creating_integration_file_structure) 