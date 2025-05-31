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
    
    # Test 1: Default instance - should allow localhost (empty restrict_in_cidrs = allow all)
    tests_total += 1
    if test_request('default', 'https://httpbin.org/get', 'your-secret-token-here', 200, 
                   "Default instance - localhost access (empty restrict_in_cidrs = allow all)"):
        tests_passed += 1
    
    # Test 2: External instance - should deny localhost (restrict_in_cidrs doesn't include localhost)
    tests_total += 1
    if test_request('external-only', 'https://httpbin.org/get', 'external-token-123', 403,
                   "External instance - localhost denied (not in restrict_in_cidrs)"):
        tests_passed += 1
    
    # Test 3: Internal instance - should allow localhost (empty restrict_in_cidrs = allow all)
    tests_total += 1 
    if test_request('internal-only', 'https://httpbin.org/get', None, 403,
                   "Internal instance - external URL denied (restrict_out=internal)"):
        tests_passed += 1
    
    print()
    print("🧪 Testing Target Network Access Control...")
    print("-" * 40)
    
    # Test 4: Default instance (both) - should allow external URLs
    tests_total += 1
    if test_request('default', 'https://httpbin.org/get', 'your-secret-token-here', 200,
                   "Default instance - external URL allowed (restrict_out=both)"):
        tests_passed += 1
    
    # Test 5: External instance - would allow external URLs if client IP was allowed
    tests_total += 1
    if test_request('external-only', 'https://httpbin.org/get', 'external-token-123', 403,
                   "External instance - client IP denied (restrict_in_cidrs)"):
        tests_passed += 1
    
    # Test 6: Internal instance - should deny external URLs (restrict_out=internal)
    tests_total += 1
    if test_request('internal-only', 'https://httpbin.org/get', None, 403,
                   "Internal instance - external URL denied (restrict_out=internal)"):
        tests_passed += 1
    
    # Test 7: Internal instance - should allow internal URLs (localhost)
    tests_total += 1
    if test_request('internal-only', 'http://127.0.0.1:8080/test', None, 400,
                   "Internal instance - localhost URL allowed (400=connection issue, not access denied)"):
        tests_passed += 1
    
    # Test 8: Internal instance - should allow private IP ranges
    tests_total += 1
    if test_request('internal-only', 'http://192.168.1.1/test', None, 502,
                   "Internal instance - private IP allowed (502=unreachable but access allowed)"):
        tests_passed += 1
    
    print()
    print("🧪 Testing Custom Network CIDRs...")
    print("-" * 40)
    
    # Test 9: Restricted-out instance - should allow 1.1.1.1 (in restrict_out_cidrs)
    tests_total += 1
    if test_request('restricted-out', 'https://1.1.1.1/test', 'your-secret-token-here', 301,
                   "Restricted-out instance - 1.1.1.1 allowed (in restrict_out_cidrs)"):
        tests_passed += 1
    
    # Test 10: Restricted-out instance - should deny httpbin.org (not in restrict_out_cidrs)
    tests_total += 1
    if test_request('restricted-out', 'https://httpbin.org/get', 'your-secret-token-here', 403,
                   "Restricted-out instance - httpbin.org denied (not in restrict_out_cidrs)"):
        tests_passed += 1
    
    # Test 11: Custom networks instance - should allow 8.8.8.8 (in 8.8.8.0/24)
    tests_total += 1
    if test_request('custom-networks', 'https://8.8.8.8/test', 'custom-token', 502,
                   "Custom networks - 8.8.8.8 allowed (502=unreachable but access allowed)"):
        tests_passed += 1
    
    # Test 12: Custom networks - should allow 1.1.1.1 (in 1.1.1.0/24)
    tests_total += 1
    if test_request('custom-networks', 'https://1.1.1.1/test', 'custom-token', 301,
                   "Custom networks - 1.1.1.1 allowed (in restrict_out_cidrs)"):
        tests_passed += 1
    
    # Test 13: Custom networks - should deny external URL not in CIDRs
    tests_total += 1
    if test_request('custom-networks', 'https://httpbin.org/get', 'custom-token', 403,
                   "Custom networks - httpbin.org denied (not in restrict_out_cidrs)"):
        tests_passed += 1
    
    # Test 14: Test authentication failure
    tests_total += 1
    if test_request('custom-networks', 'https://8.8.8.8/test', 'wrong-token', 401,
                   "Custom networks - wrong token (authentication failure)"):
        tests_passed += 1
    
    # Test 15: Test missing token
    tests_total += 1
    if test_request('default', 'https://httpbin.org/get', None, 401,
                   "Default instance - missing token (authentication required)"):
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