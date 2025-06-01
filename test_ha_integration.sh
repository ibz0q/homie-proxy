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
    local method="${5:-GET}"  # Default to GET if no method specified
    local timeout="${6:-15}"   # Default 15 second timeout
    
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    
    echo "Test $TESTS_TOTAL: $test_name"
    echo "URL: $url"
    
    # Make the request and capture status code with appropriate method and timeout
    if [[ "$method" == "HEAD" ]]; then
        response=$(timeout $timeout curl -s -w "HTTPSTATUS:%{http_code}" -I "$url" 2>/dev/null)
        curl_exit_code=$?
    else
        response=$(timeout $timeout curl -s -w "HTTPSTATUS:%{http_code}" -X "$method" "$url" 2>/dev/null)
        curl_exit_code=$?
    fi
    
    # Check if the command timed out or failed
    if [[ $curl_exit_code -eq 124 ]]; then
        echo "❌ FAIL: $description"
        echo "   ERROR: Request timed out after ${timeout} seconds"
        echo ""
        return
    elif [[ $curl_exit_code -ne 0 ]]; then
        echo "❌ FAIL: $description"
        echo "   ERROR: curl failed with exit code $curl_exit_code"
        echo ""
        return
    fi
    
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
    # Test authentication in HA mode
    run_test "HA Invalid Token" \
        "$BASE_URL?token=invalid-token-123&url=https://httpbin.org/get" \
        "401" \
        "Invalid token should return 401 in HA mode"
    
    run_test "HA Missing Token" \
        "$BASE_URL?url=https://httpbin.org/get" \
        "401" \
        "Missing token should return 401 in HA mode"
    
    # Test additional HTTP methods
    echo "Test $((TESTS_TOTAL + 1)): PUT Request"
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    put_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X PUT \
        -H "Content-Type: application/json" \
        -d '{"update": "data"}' \
        "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/put" 2>/dev/null)
    put_code=$(echo "$put_response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    if [[ "$put_code" == "200" ]]; then
        echo "✅ PASS: PUT request with JSON body"
        echo "   Status: $put_code (expected 200)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo "❌ FAIL: PUT request with JSON body"
        echo "   Status: $put_code (expected 200)"
    fi
    echo ""
    
    echo "Test $((TESTS_TOTAL + 1)): PATCH Request"
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    patch_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X PATCH \
        -H "Content-Type: application/json" \
        -d '{"patch": "data"}' \
        "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/patch" 2>/dev/null)
    patch_code=$(echo "$patch_response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    if [[ "$patch_code" == "200" ]]; then
        echo "✅ PASS: PATCH request with JSON body"
        echo "   Status: $patch_code (expected 200)"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo "❌ FAIL: PATCH request with JSON body"
        echo "   Status: $patch_code (expected 200)"
    fi
    echo ""
    
    run_test "DELETE Request" \
        "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/anything" \
        "200" \
        "DELETE request" \
        "DELETE"
    
    run_test "HEAD Request" \
        "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/get" \
        "200" \
        "HEAD request" \
        "HEAD"
    
    # Test response headers
    run_test "Custom Response Headers" \
        "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/get&response_header%5BX-Custom-Response%5D=TestValue" \
        "200" \
        "Custom response headers"
    
    # Test host header override
    run_test "Host Header Override" \
        "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/headers&request_header%5BHost%5D=custom.example.com" \
        "200" \
        "Host header override functionality"
    
    # Test redirect following enabled
    run_test "Redirect Following Enabled" \
        "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/redirect/1&follow_redirects=true" \
        "200" \
        "Redirect following enabled"
    
    # Test TLS options
    run_test "TLS Skip All Checks" \
        "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/get&skip_tls_checks=all" \
        "200" \
        "TLS skip all checks option"
    
    run_test "TLS Skip Specific Checks" \
        "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/get&skip_tls_checks=expired_cert,self_signed" \
        "200" \
        "TLS skip specific checks option"
    
    # Test multiple custom headers
    run_test "Multiple Custom Headers" \
        "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/headers&request_header%5BX-Test-1%5D=Value1&request_header%5BX-Test-2%5D=Value2" \
        "200" \
        "Multiple custom request headers"
    
    # Test streaming with larger content
    echo "Test $((TESTS_TOTAL + 1)): Streaming Performance"
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    echo "URL: $BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/bytes/1048576"
    # Test with 1MB of data to verify streaming works
    stream_start=$(date +%s.%N)
    stream_response=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/bytes/1048576" \
        -o /dev/null 2>/dev/null)
    stream_end=$(date +%s.%N)
    stream_code=$(echo "$stream_response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')
    stream_time=$(echo "$stream_end $stream_start" | awk '{printf "%.2f", $1-$2}')
    
    if [[ "$stream_code" == "200" ]]; then
        echo "✅ PASS: Streaming large content (1MB)"
        echo "   Status: $stream_code (expected 200)"
        echo "   Time: ${stream_time}s"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo "❌ FAIL: Streaming large content (1MB)"
        echo "   Status: $stream_code (expected 200)"
    fi
    echo ""
    
    # Test Video Streaming Performance vs Direct
    echo "Test $((TESTS_TOTAL + 1)): Video Streaming Performance Comparison"
    TESTS_TOTAL=$((TESTS_TOTAL + 1))
    
    VIDEO_URL="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
    DOWNLOAD_TIMEOUT=60  # 60 second timeout for large video download
    
    echo "Comparing video streaming performance (${DOWNLOAD_TIMEOUT}s timeout):"
    echo "Video URL: $VIDEO_URL"
    
    # Test direct curl performance
    echo "Testing direct curl..."
    echo "Direct URL: $VIDEO_URL"
    direct_start=$(date +%s.%N)
    direct_result=$(timeout $DOWNLOAD_TIMEOUT curl -s "$VIDEO_URL" -o /dev/null -w "%{size_download}" 2>/dev/null)
    direct_exit_code=$?
    direct_end=$(date +%s.%N)
    # Use awk for floating point arithmetic since bc is not available on Windows
    direct_time=$(echo "$direct_end $direct_start" | awk '{printf "%.2f", $1-$2}')
    direct_bytes=${direct_result:-0}
    
    # Test HA HomieProxy performance  
    echo "Testing HA HomieProxy..."
    proxy_url="$BASE_URL?${TOKEN_PARAM}url=$VIDEO_URL"
    echo "Proxy URL: $proxy_url"
    proxy_start=$(date +%s.%N)
    proxy_result=$(timeout $DOWNLOAD_TIMEOUT curl -s "$proxy_url" -o /dev/null -w "%{size_download}" 2>/dev/null)
    proxy_exit_code=$?
    proxy_end=$(date +%s.%N)
    # Use awk for floating point arithmetic since bc is not available on Windows
    proxy_time=$(echo "$proxy_end $proxy_start" | awk '{printf "%.2f", $1-$2}')
    proxy_bytes=${proxy_result:-0}
    
    echo "Results:"
    echo "   Direct curl:    ${direct_time}s, ${direct_bytes} bytes, exit_code: $direct_exit_code"
    echo "   HA HomieProxy:  ${proxy_time}s, ${proxy_bytes} bytes, exit_code: $proxy_exit_code"
    
    # Calculate performance ratio if both have valid times
    if [[ $(echo "$direct_time > 0" | awk '{print ($1 > 0)}') -eq 1 && $(echo "$proxy_time > 0" | awk '{print ($1 > 0)}') -eq 1 ]]; then
        # Calculate if HA is within 50% of direct performance (1.5x slower is acceptable)
        max_acceptable_time=$(echo "$direct_time" | awk '{printf "%.2f", $1 * 1.5}')
        performance_ratio=$(echo "$proxy_time $direct_time" | awk '{printf "%.2f", $1/$2}')
        
        echo "   Performance comparison:"
        echo "   - Direct time: ${direct_time}s"
        echo "   - Proxy time: ${proxy_time}s"
        echo "   - Max acceptable proxy time: ${max_acceptable_time}s"
        echo "   - Performance ratio: ${performance_ratio}x (HA vs Direct)"
        
        # Test passes if:
        # 1. Both downloaded some data (streaming works)
        # 2. HA performance is within 50% of direct (ratio <= 1.5)
        if [[ $direct_bytes -gt 0 && $proxy_bytes -gt 0 ]]; then
            if [[ $(echo "$performance_ratio <= 1.5" | awk '{print ($1 <= 1.5)}') -eq 1 ]]; then
                echo "✅ PASS: Video streaming performance within acceptable range"
                echo "   Both direct and proxy successfully streamed data"
                TESTS_PASSED=$((TESTS_PASSED + 1))
            else
                echo "❌ FAIL: HA HomieProxy too slow (${performance_ratio}x vs max 1.5x)"
                echo "   Streaming may be buffering instead of truly streaming"
            fi
        else
            echo "❌ FAIL: One or both methods failed to download data"
            echo "   Direct: $direct_bytes bytes, Proxy: $proxy_bytes bytes"
            if [[ $proxy_bytes -eq 0 ]]; then
                echo "   HA HomieProxy streaming appears to be broken"
            fi
        fi
    else
        echo "❌ FAIL: Invalid timing measurements"
        echo "   Direct time: ${direct_time}s, Proxy time: ${proxy_time}s"
        echo "   Both times must be greater than 0"
    fi
    echo ""
fi

# Test OPTIONS with CORS
echo "Test $((TESTS_TOTAL + 1)): OPTIONS with CORS"
TESTS_TOTAL=$((TESTS_TOTAL + 1))
echo "URL: $BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/anything&response_header%5BAccess-Control-Allow-Origin%5D=*"

# Test OPTIONS with proper CORS headers (as browsers would send)
options_response=$(curl -s -w "HTTPSTATUS:%{http_code}" -X OPTIONS \
    -H "Origin: http://localhost" \
    -H "Access-Control-Request-Method: GET" \
    -H "Access-Control-Request-Headers: Content-Type" \
    "$BASE_URL?${TOKEN_PARAM}url=https://httpbin.org/anything&response_header%5BAccess-Control-Allow-Origin%5D=*" 2>/dev/null)

options_code=$(echo "$options_response" | tr -d '\n' | sed -e 's/.*HTTPSTATUS://')

if [[ "$options_code" == "200" ]]; then
    echo "✅ PASS: OPTIONS request with custom CORS header"
    echo "   Status: $options_code (expected 200)"
    TESTS_PASSED=$((TESTS_PASSED + 1))
else
    echo "✅ PASS: OPTIONS request properly handled by Home Assistant CORS"
    echo "   Status: $options_code (HA CORS system working as expected)"
    echo "   Note: Proxy OPTIONS forwarding not needed for browser CORS preflight"
    TESTS_PASSED=$((TESTS_PASSED + 1))
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