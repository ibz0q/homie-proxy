#!/bin/bash
set -e

echo "🧪 Testing Home Assistant + Homie Proxy Development Environment"
echo "=============================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to test endpoint
test_endpoint() {
    local url=$1
    local description=$2
    local expected_status=${3:-200}
    
    echo -e "${BLUE}Testing:${NC} $description"
    echo -e "${YELLOW}URL:${NC} $url"
    
    if response=$(curl -s -w "HTTPSTATUS:%{http_code}" "$url" 2>/dev/null); then
        http_code=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
        content=$(echo "$response" | sed -e 's/HTTPSTATUS:.*//g')
        
        if [ "$http_code" -eq "$expected_status" ]; then
            echo -e "${GREEN}✅ SUCCESS${NC} (HTTP $http_code)"
            if echo "$content" | python -m json.tool > /dev/null 2>&1; then
                echo -e "${GREEN}✅ Valid JSON response${NC}"
                # Pretty print first few lines
                echo "$content" | python -m json.tool | head -10
                if [ $(echo "$content" | python -m json.tool | wc -l) -gt 10 ]; then
                    echo "..."
                fi
            else
                echo -e "${YELLOW}⚠️  Non-JSON response:${NC}"
                echo "$content" | head -5
            fi
        else
            echo -e "${RED}❌ FAILED${NC} (Expected HTTP $expected_status, got $http_code)"
            echo "$content" | head -5
        fi
    else
        echo -e "${RED}❌ FAILED${NC} (Connection failed)"
    fi
    echo ""
}

# Wait function
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    echo -e "${BLUE}Waiting for $service_name to be ready...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ $service_name is ready!${NC}"
            return 0
        fi
        
        echo -e "${YELLOW}⏳ Attempt $attempt/$max_attempts - waiting for $service_name...${NC}"
        sleep 5
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}❌ $service_name failed to start after $((max_attempts * 5)) seconds${NC}"
    return 1
}

echo "🔍 Checking if services are running..."

# Check if containers are running
if ! docker ps | grep -q "ha-dev"; then
    echo -e "${RED}❌ Home Assistant container (ha-dev) is not running${NC}"
    echo "Please start the devcontainer first"
    exit 1
fi

if ! docker ps | grep -q "homie-proxy-dev"; then
    echo -e "${RED}❌ Homie Proxy container (homie-proxy-dev) is not running${NC}"
    echo "Please start the devcontainer first"
    exit 1
fi

echo -e "${GREEN}✅ Both containers are running${NC}"
echo ""

# Wait for services to be ready
wait_for_service "http://localhost:8123/api/" "Home Assistant"
wait_for_service "http://localhost:8080/" "Homie Proxy" || echo "⚠️  Homie Proxy might not be fully ready, continuing..."

echo ""
echo "🧪 Running API Tests..."
echo "======================"

# Test Home Assistant API
test_endpoint "http://localhost:8123/api/" "Home Assistant Base API"

# Test Hello World Integration - Main Endpoint
test_endpoint "http://localhost:8123/api/hello_world" "Hello World Integration - Basic"

# Test Hello World Integration - With Parameter
test_endpoint "http://localhost:8123/api/hello_world?name=DevContainer" "Hello World Integration - With Name Parameter"

# Test Hello World Integration - Info Endpoint
test_endpoint "http://localhost:8123/api/hello_world/info" "Hello World Integration - Info Endpoint"

# Test Hello World Integration State
test_endpoint "http://localhost:8123/api/states/hello_world.status" "Hello World Integration - State"

# Test Homie Proxy
test_endpoint "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/get" "Homie Proxy - Basic Test"

echo "🎯 Testing POST Requests..."
echo "=========================="

# Test POST to Hello World
echo -e "${BLUE}Testing:${NC} Hello World Integration - POST with JSON"
echo -e "${YELLOW}URL:${NC} http://localhost:8123/api/hello_world"

if response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "http://localhost:8123/api/hello_world" \
    -H "Content-Type: application/json" \
    -d '{"message": "Hello from DevContainer", "name": "Developer"}' 2>/dev/null); then
    
    http_code=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    content=$(echo "$response" | sed -e 's/HTTPSTATUS:.*//g')
    
    if [ "$http_code" -eq 200 ]; then
        echo -e "${GREEN}✅ POST SUCCESS${NC} (HTTP $http_code)"
        echo "$content" | python -m json.tool
    else
        echo -e "${RED}❌ POST FAILED${NC} (HTTP $http_code)"
        echo "$content"
    fi
else
    echo -e "${RED}❌ POST FAILED${NC} (Connection failed)"
fi

echo ""
echo "📊 Test Summary"
echo "==============="
echo -e "${GREEN}🎉 All tests completed!${NC}"
echo ""
echo "🔗 Access URLs:"
echo "  • Home Assistant: http://localhost:8123"
echo "  • Hello World API: http://localhost:8123/api/hello_world"
echo "  • Hello World Info: http://localhost:8123/api/hello_world/info"
echo "  • Homie Proxy: http://localhost:8080"
echo ""
echo "📚 Development Commands:"
echo "  • View HA logs: docker logs ha-dev -f"
echo "  • View Proxy logs: docker logs homie-proxy-dev -f"
echo "  • Restart HA: docker restart ha-dev"
echo "  • Shell into HA: docker exec -it ha-dev bash" 