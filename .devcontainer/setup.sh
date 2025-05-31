#!/bin/bash
set -e

echo "🚀 Setting up Home Assistant + Homie Proxy development environment..."

# Ensure we're in the right directory
cd /workspaces/python-reverse-proxy

# Install Python dependencies for the proxy
echo "📦 Installing Homie Proxy dependencies..."
pip install -r requirements.txt

# Create required Home Assistant config files if they don't exist
echo "📁 Creating Home Assistant configuration files..."
mkdir -p /config

# Create default automations.yaml, scenes.yaml, scripts.yaml if they don't exist
touch /config/automations.yaml || echo "[]" > /config/automations.yaml
touch /config/scenes.yaml || echo "[]" > /config/scenes.yaml  
touch /config/scripts.yaml || echo "{}" > /config/scripts.yaml

echo "✅ Development environment setup complete!"
echo ""
echo "🌟 Services available:"
echo "  • Home Assistant: http://localhost:8123"
echo "  • Homie Proxy: http://localhost:8080"
echo ""
echo "🔧 Development commands:"
echo "  • Start services: docker-compose up"
echo "  • View logs: docker-compose logs -f"
echo "  • Restart HA: docker-compose restart homeassistant"
echo ""
echo "📝 Test the hello-world integration:"
echo "  curl http://localhost:8123/api/hello_world" 