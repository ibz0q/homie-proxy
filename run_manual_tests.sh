#!/bin/bash
# Manual Test Runner for Homie Proxy (Shell Version)
# Tests the Docker container using curl commands

echo "================================================================================"
echo "HOMIE PROXY - MANUAL TEST RUNNER"
echo "================================================================================"
echo "Testing proxy at localhost:8080"
echo "Test started: $(date)"
echo

PASSED=0
FAILED=0
TOTAL=0

# Function to run a test
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_pattern="$3"
    
    echo "🧪 Running: $test_name"
    ((TOTAL++))
    
    if result=$(eval "$test_command" 2>&1); then
        if [[ -z "$expected_pattern" ]] || echo "$result" | grep -q "$expected_pattern"; then
            echo "   ✅ PASSED"
            ((PASSED++))
        else
            echo "   ❌ FAILED: Pattern '$expected_pattern' not found"
            echo "   Result: $result"
            ((FAILED++))
        fi
    else
        echo "   ❌ FAILED: Command failed"
        echo "   Error: $result"
        ((FAILED++))
    fi
    echo
}

echo "Starting test execution..."
echo "--------------------------------------------------------------------------------"

# Test 1: Basic GET Request
run_test "Basic GET Request" \
    'curl -s "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/get"' \
    '"args"'

# Test 2: Host Header Fix
run_test "Host Header Fix" \
    'curl -s "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/headers" | grep -o "\"Host\": \"[^\"]*\""' \
    'httpbin.org'

# Test 3: POST Request
run_test "POST Request" \
    'curl -s "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/post" -X POST -d "{\"test\":\"data\"}" -H "Content-Type: application/json"' \
    '"json"'

# Test 4: TLS Bypass
run_test "TLS Bypass" \
    'curl -w "%{http_code}" -s "http://localhost:8080/default?token=your-secret-token-here&url=https://self-signed.badssl.com/&skip_tls_checks=true" -o /dev/null' \
    '200'

# Test 5: Custom Headers
run_test "Custom Request Headers" \
    'curl -s "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/headers&request_headers%5BX-Custom%5D=TestValue"' \
    'X-Custom.*TestValue'

# Test 6: User-Agent Preservation
run_test "User-Agent Preservation" \
    'curl -s "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/headers" -H "User-Agent: TestAgent/1.0"' \
    'TestAgent/1.0'

# Test 7: PUT Method
run_test "PUT Method" \
    'curl -s "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/put" -X PUT -d "{\"update\":\"data\"}" -H "Content-Type: application/json"' \
    '"json"'

# Test 8: Error Handling (Invalid Token)
run_test "Error Handling (Invalid Token)" \
    'curl -w "%{http_code}" -s "http://localhost:8080/default?token=invalid&url=https://httpbin.org/get" -o /dev/null' \
    '401'

# Test 9: Internal Instance Access (should allow internal URLs but deny external ones)
run_test "Internal Instance (Internal URL)" \
    'curl -w "%{http_code}" -s "http://localhost:8080/internal-only?url=http://127.0.0.1:8080/test" -o /dev/null' \
    '404'

# Test 10: Response Headers (CORS)
run_test "Custom Response Headers" \
    'curl -s "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/get&response_header%5BAccess-Control-Allow-Origin%5D=*" -I' \
    'Access-Control-Allow-Origin: *'

# Summary
echo "================================================================================"
echo "TEST EXECUTION COMPLETE"
echo "================================================================================"
echo
echo "📊 SUMMARY:"
echo "   Total Tests:   $TOTAL"
echo "   ✅ Passed:     $PASSED"
echo "   ❌ Failed:     $FAILED"

if [ $TOTAL -gt 0 ]; then
    SUCCESS_RATE=$((PASSED * 100 / TOTAL))
    echo "   🎯 Success Rate: ${SUCCESS_RATE}%"
fi

echo
echo "🏁 Test run completed: $(date)"

if [ $FAILED -eq 0 ]; then
    echo "🎉 All tests passed successfully!"
    exit 0
else
    echo "⚠️  $FAILED test(s) failed. Check logs above for details."
    exit 1
fi

echo "================================================================================" 