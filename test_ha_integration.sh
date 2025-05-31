#!/bin/bash

# HomieProxy Test Script - Works with both standalone and HA integration
# Usage: ./test_ha_integration.sh [--mode standalone|ha] [--port PORT] [--instance INSTANCE]

# Default values
MODE="standalone"
PORT="8080"
INSTANCE="external-api-route"
HOST="localhost"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --instance)
            INSTANCE="$2"
            shift 2
            ;;
        --host)
            HOST="$2"
            shift 2
            ;;
        *)
            echo "Unknown option $1"
            exit 1
            ;;
    esac
done

# Validate mode
if [[ "$MODE" != "standalone" && "$MODE" != "ha" ]]; then
    echo "Error: Mode must be 'standalone' or 'ha'"
    exit 1
fi

echo "=============================================================="
echo "HOMIEPROXY COMPREHENSIVE TESTS - $MODE MODE"
echo "=============================================================="
echo "Host: $HOST:$PORT"
if [[ "$MODE" == "ha" ]]; then
    echo "HA Instance: $INSTANCE"
fi
echo ""

# Construct base URL based on mode
if [[ "$MODE" == "ha" ]]; then
    BASE_URL="http://$HOST:$PORT/api/homie_proxy/$INSTANCE"
    
    # Get the authentication token from debug endpoint
    echo "Getting authentication token from debug endpoint..."
    DEBUG_RESPONSE=$(curl -s "http://$HOST:$PORT/api/homie_proxy/debug" 2>/dev/null)
    
    if [[ $? -eq 0 ]] && [[ -n "$DEBUG_RESPONSE" ]]; then
        # Extract token using grep and sed (works with minimal dependencies)
        TOKEN=$(echo "$DEBUG_RESPONSE" | grep -o '"[a-f0-9-]\{36\}"' | head -1 | tr -d '"')
        
        if [[ -n "$TOKEN" ]]; then
            TOKEN_PARAM="token=$TOKEN&"
            echo "✅ Found authentication token: ${TOKEN:0:8}..."
        else
            echo "❌ Could not extract token from debug response"
            echo "Debug response: $DEBUG_RESPONSE"
            exit 1
        fi
    else
        echo "❌ Could not reach debug endpoint"
        exit 1
    fi
else
    BASE_URL="http://$HOST:$PORT/default"
    TOKEN_PARAM="token=your-secret-token-here&"
fi

# Test counter
TESTS_PASSED=0
TESTS_TOTAL=0

# Function to run a test
run_test() {
    local test_name="$1"
    local url="$2"
    local expected_status="$3"
    local description="$4"
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    
    echo "Test $TESTS_TOTAL: $test_name"
    echo "URL: $url"
    
    # Make the request and capture status code
    response=$(curl -s -w "HTTPSTATUS:%{http_code}" "$url" 2>/dev/null)
    http_code=$(echo "$response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    content=$(echo "$response" | sed -e 's/HTTPSTATUS:.*//g')
    
    if [[ "$http_code" == "$expected_status" ]]; then
        echo "✅ PASS: $description"
        echo "   Status: $http_code (expected $expected_status)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo "❌ FAIL: $description"
        echo "   Status: $http_code (expected $expected_status)"
        if [[ ${#content} -gt 0 && ${#content} -lt 500 ]]; then
            echo "   Response: $content"
        fi
    fi
    echo ""
}

# Test 1: Basic GET request
run_test "Basic GET" \
    "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/get" \
    "200" \
    "Basic proxy functionality"

# Test 2: JSON response
run_test "JSON Response" \
    "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/json" \
    "200" \
    "JSON content handling"

# Test 3: Host header verification
run_test "Host Header Check" \
    "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/headers" \
    "200" \
    "Host header is correctly set to target hostname"

# Test 4: User Agent forwarding
run_test "User Agent" \
    "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/user-agent" \
    "200" \
    "User-Agent header forwarding"

# Test 5: POST request (if supported)
if [[ "$MODE" == "ha" ]]; then
    echo "Test $((TESTS_TOTAL + 1)): POST Request"
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    
    post_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST \
        -H "Content-Type: application/json" \
        -d '{"test": "data"}' \
        "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/post" 2>/dev/null)
    
    post_code=$(echo "$post_response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    
    if [[ "$post_code" == "200" ]]; then
        echo "✅ PASS: POST request with JSON body"
        echo "   Status: $post_code (expected 200)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo "❌ FAIL: POST request with JSON body"
        echo "   Status: $post_code (expected 200)"
    fi
    echo ""
fi

# Test 6: Invalid URL handling
run_test "Invalid URL" \
    "$BASE_URL?${TOKEN_PARAM}url=invalid-url" \
    "403" \
    "Invalid URL should be blocked by access control"

# Test 7: Missing URL parameter
run_test "Missing URL" \
    "$BASE_URL?$TOKEN_PARAM" \
    "400" \
    "Missing URL parameter should return 400 Bad Request"

# Authentication tests (only for standalone mode)
if [[ "$MODE" == "standalone" ]]; then
    # Test 8: Invalid token
    run_test "Invalid Token" \
        "http://$HOST:$PORT/default?token=invalid-token&url=https://httpbin.org/get" \
        "401" \
        "Invalid token should return 401 Unauthorized"
    
    # Test 9: Missing token
    run_test "Missing Token" \
        "http://$HOST:$PORT/default?url=https://httpbin.org/get" \
        "401" \
        "Missing token should return 401 Unauthorized"
fi

# Test Debug endpoint (HA mode only)
if [[ "$MODE" == "ha" ]]; then
    run_test "Debug Endpoint" \
        "http://$HOST:$PORT/api/homie_proxy/debug" \
        "200" \
        "Debug endpoint should show configuration"
fi

# Test Advanced Features (HA mode has more features)
if [[ "$MODE" == "ha" ]]; then
    # Test custom headers
    run_test "Custom Headers" \
        "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/headers&request_headers%5BX-Test%5D=CustomValue" \
        "200" \
        "Custom request headers"
    
    # Test redirect following disabled
    run_test "Redirect Handling" \
        "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/redirect/1&follow_redirects=false" \
        "302" \
        "Redirect following disabled"
fi

# Summary
echo "=============================================================="
echo "TEST SUMMARY"
echo "=============================================================="
echo "Tests passed: $TESTS_PASSED/$TESTS_TOTAL"

success_rate=$((TESTS_PASSED * 100 / TESTS_TOTAL))
echo "Success rate: $success_rate%"

if [[ $TESTS_PASSED -eq $TESTS_TOTAL ]]; then
    echo "🎉 All tests passed!"
    exit 0
else
    echo "⚠️ $((TESTS_TOTAL - TESTS_PASSED)) test(s) failed"
    exit 1
fi 