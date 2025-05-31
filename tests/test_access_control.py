#!/usr/bin/env python3
"""
Test Access Control functionality for Homie Proxy
Tests both client IP restrictions and target URL access mode restrictions
"""

import os
import requests
import sys
import time

# Configuration
PROXY_HOST = os.environ.get('PROXY_HOST', 'localhost')
PROXY_PORT = int(os.environ.get('PROXY_PORT', 8080))
BASE_URL = f"http://{PROXY_HOST}:{PROXY_PORT}"

def test_request(instance, url, token=None, expected_status=200, description=""):
    """Make a test request and check the response"""
    try:
        params = {'url': url}
        if token:
            params['token'] = token
            
        response = requests.get(f"{BASE_URL}/{instance}", params=params, timeout=8)
        
        status_match = response.status_code == expected_status
        print(f"{'✅' if status_match else '❌'} {description}")
        print(f"   Expected: {expected_status}, Got: {response.status_code}")
        
        if not status_match and response.status_code in [400, 401, 403, 404]:
            try:
                error_data = response.json()
                print(f"   Error: {error_data.get('error', 'Unknown error')}")
            except:
                print(f"   Error response: {response.text[:100]}")
        
        return status_match
        
    except Exception as e:
        print(f"❌ {description}")
        print(f"   Exception: {e}")
        return False

def main():
    print("=" * 80)
    print("HOMIE PROXY - NETWORK ACCESS CONTROL TESTS")
    print("=" * 80)
    print(f"Testing proxy at {PROXY_HOST}:{PROXY_PORT}")
    print()
    
    # Give server time to start if needed
    time.sleep(1)
    
    tests_passed = 0
    tests_total = 0
    
    print("🧪 Testing Client IP Access Control...")
    print("-" * 40)
    
    # Test 1: Default instance - should allow localhost (no restrict_access_to_cidrs specified)
    tests_total += 1
    if test_request('default', 'https://httpbin.org/get', 'your-secret-token-here', 200, 
                   "Default instance - localhost access (no CIDR restrictions)"):
        tests_passed += 1
    
    # Test 2: External instance - should allow from specified CIDRs (but we're localhost so might fail)
    tests_total += 1
    if test_request('external-only', 'https://httpbin.org/get', 'external-token-123', 403,
                   "External instance - CIDR restrictions (localhost not in allowed CIDRs)"):
        tests_passed += 1
    
    # Test 3: Internal instance - should allow localhost (no CIDR restrictions, defaults to local only)
    tests_total += 1 
    if test_request('internal-only', 'https://httpbin.org/get', None, 200,
                   "Internal instance - localhost access (no token required)"):
        tests_passed += 1
    
    print()
    print("🧪 Testing Target Network Access Control...")
    print("-" * 40)
    
    # Test 4: Default instance (both) - should allow external URLs
    tests_total += 1
    if test_request('default', 'https://httpbin.org/get', 'your-secret-token-here', 200,
                   "Default instance - external URL (allowed_networks_out=both)"):
        tests_passed += 1
    
    # Test 5: External instance - should allow external URLs  
    tests_total += 1
    if test_request('external-only', 'https://httpbin.org/get', 'external-token-123', 200,
                   "External instance - external URL (allowed_networks_out=external)"):
        tests_passed += 1
    
    # Test 6: External instance - should deny internal URLs (localhost)
    tests_total += 1
    if test_request('external-only', 'http://127.0.0.1:80/test', 'external-token-123', 403,
                   "External instance - internal URL denied (allowed_networks_out=external)"):
        tests_passed += 1
    
    # Test 7: Internal instance - should allow internal URLs (localhost)
    tests_total += 1
    if test_request('internal-only', 'http://127.0.0.1:8080/test', None, 200,
                   "Internal instance - localhost URL (allowed_networks_out=internal)"):
        tests_passed += 1
    
    # Test 8: Internal instance - should deny external URLs
    tests_total += 1
    if test_request('internal-only', 'https://httpbin.org/get', None, 403,
                   "Internal instance - external URL denied (allowed_networks_out=internal)"):
        tests_passed += 1
    
    # Test 9: Test private IP ranges (internal)
    tests_total += 1
    if test_request('internal-only', 'http://192.168.1.1/test', None, 200,
                   "Internal instance - private IP (192.168.x.x)"):
        tests_passed += 1
    
    print()
    print("🧪 Testing Custom Network CIDRs...")
    print("-" * 40)
    
    # Test 10: Custom networks - should allow 1.1.1.1 (in allowed_networks_out_cidrs)
    tests_total += 1
    if test_request('both-test', 'https://1.1.1.1/test', 'your-secret-token-here', 200,
                   "Both-test instance - 1.1.1.1 allowed (in allowed_networks_out_cidrs)"):
        tests_passed += 1
    
    # Test 11: Custom networks - should deny httpbin.org (not in allowed_networks_out_cidrs)
    tests_total += 1
    if test_request('both-test', 'https://httpbin.org/get', 'your-secret-token-here', 403,
                   "Both-test instance - httpbin.org denied (not in allowed_networks_out_cidrs)"):
        tests_passed += 1
    
    # Test 12: Custom networks instance - should allow 8.8.8.8 (in 8.8.8.0/24)
    tests_total += 1
    if test_request('custom-networks', 'https://8.8.8.8/test', 'custom-token', 200,
                   "Custom networks - 8.8.8.8 allowed (in 8.8.8.0/24)"):
        tests_passed += 1
    
    # Test 13: Custom networks - should deny external URL not in CIDRs
    tests_total += 1
    if test_request('custom-networks', 'https://httpbin.org/get', 'custom-token', 403,
                   "Custom networks - httpbin.org denied (not in allowed_networks_out_cidrs)"):
        tests_passed += 1
    
    # Test 14: Test authentication on custom-networks instance
    tests_total += 1
    if test_request('custom-networks', 'https://8.8.8.8/test', 'wrong-token', 401,
                   "Custom networks - wrong token"):
        tests_passed += 1
    
    print()
    print("=" * 80)
    print("NETWORK ACCESS CONTROL TEST SUMMARY")
    print("=" * 80)
    print(f"Tests passed: {tests_passed}/{tests_total}")
    
    success_rate = (tests_passed / tests_total * 100) if tests_total > 0 else 0
    print(f"Success rate: {success_rate:.1f}%")
    
    if tests_passed == tests_total:
        print("🎉 All network access control tests passed!")
        sys.exit(0)
    else:
        print(f"⚠️ {tests_total - tests_passed} test(s) failed")
        sys.exit(1)

if __name__ == "__main__":
    main() 