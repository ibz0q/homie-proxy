#!/usr/bin/env python3

import requests
import time

print("=" * 70)
print("COMPREHENSIVE FUNCTIONALITY TEST - REVERSE PROXY")
print("=" * 70)

base_url = "http://localhost:8080/default?token=your-secret-token-here"

tests_passed = 0
total_tests = 0

def run_test(test_name, test_func):
    global tests_passed, total_tests
    total_tests += 1
    print(f"\n🧪 Test {total_tests}: {test_name}")
    print("-" * 50)
    try:
        result = test_func()
        if result:
            tests_passed += 1
            print("✅ PASSED")
        else:
            print("❌ FAILED")
        return result
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_basic_get():
    """Test basic GET request"""
    response = requests.get(f"{base_url}&url=https://httpbin.org/get", timeout=8)
    print(f"Status: {response.status_code}")
    return response.status_code == 200

def test_host_header_fix():
    """Test Host header correction"""
    response = requests.get(f"{base_url}&url=https://httpbin.org/headers", timeout=8)
    if response.status_code == 200:
        data = response.json()
        host = data.get('headers', {}).get('Host', '')
        print(f"Host header: {host}")
        return host == 'httpbin.org'
    return False

def test_override_host_header():
    """Test Host header override"""
    response = requests.get(f"{base_url}&url=https://httpbin.org/headers&override_host_header=custom.test.com", timeout=8)
    if response.status_code == 200:
        data = response.json()
        host = data.get('headers', {}).get('Host', '')
        print(f"Override host header: {host}")
        return host == 'custom.test.com'
    return False

def test_tls_bypass():
    """Test TLS bypass functionality"""
    response = requests.get(f"{base_url}&url=https://httpbin.org/get&skip_tls_checks=all", timeout=8)
    print(f"TLS bypass status: {response.status_code}")
    return response.status_code == 200

def test_user_agent_preservation():
    """Test User-Agent preservation"""
    headers = {'User-Agent': 'TestBot/1.0'}
    response = requests.get(f"{base_url}&url=https://httpbin.org/headers", headers=headers, timeout=8)
    if response.status_code == 200:
        data = response.json()
        ua = data.get('headers', {}).get('User-Agent', '')
        print(f"User-Agent: {ua}")
        return ua == 'TestBot/1.0'
    return False

def test_custom_headers():
    """Test custom headers via URL parameters"""
    url = f"{base_url}&url=https://httpbin.org/headers&request_headers[X-Custom-Test]=success"
    response = requests.get(url, timeout=8)
    if response.status_code == 200:
        data = response.json()
        custom = data.get('headers', {}).get('X-Custom-Test', '')
        print(f"Custom header: {custom}")
        return custom == 'success'
    return False

def test_post_request():
    """Test POST request with data"""
    url = f"{base_url}&url=https://httpbin.org/post"
    data = {'test': 'data', 'working': True}
    response = requests.post(url, json=data, timeout=8)
    if response.status_code == 200:
        result = response.json()
        received = result.get('json', {})
        print(f"POST data received: {received}")
        return received.get('test') == 'data'
    return False

# Run all tests
run_test("Basic GET request", test_basic_get)
run_test("Host header correction", test_host_header_fix)
run_test("Host header override", test_override_host_header)
run_test("TLS bypass", test_tls_bypass)
run_test("User-Agent preservation", test_user_agent_preservation)
run_test("Custom headers via URL", test_custom_headers)
run_test("POST request", test_post_request)

print("\n" + "=" * 70)
print("FINAL RESULTS")
print("=" * 70)
print(f"Tests passed: {tests_passed}/{total_tests}")

if tests_passed == total_tests:
    print("🎉 ALL TESTS PASSED! Reverse proxy is fully functional!")
    print("\n✅ Core functionality verified:")
    print("   • Basic HTTP requests working")
    print("   • Host header correction working")
    print("   • Host header override working")
    print("   • TLS bypass working")
    print("   • User-Agent preservation working")
    print("   • Custom headers working")
    print("   • POST requests working")
else:
    print(f"⚠️  {total_tests - tests_passed} tests failed. Check output above for details.")

print("=" * 70) 