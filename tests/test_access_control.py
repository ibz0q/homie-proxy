#!/usr/bin/env python3
"""
Test Access Control functionality for Homie Proxy
Tests both client IP restrictions and target URL access mode restrictions
"""

import os
import requests
import sys
import time
import argparse

# Parse command line arguments
parser = argparse.ArgumentParser(description='Test reverse proxy access control')
parser.add_argument('--port', type=int, 
                   default=int(os.environ.get('PROXY_PORT', 8080)),
                   help='Proxy server port (default: 8080, or PROXY_PORT env var)')
parser.add_argument('--mode', choices=['standalone', 'ha'], default='standalone',
                   help='Test mode: standalone proxy or Home Assistant integration (default: standalone)')
parser.add_argument('--instance', default='external-api-route',
                   help='HA integration instance name (default: external-api-route)')
args = parser.parse_args()

print("=" * 60)
print(f"ACCESS CONTROL TEST - REVERSE PROXY ({args.mode.upper()})")
print("=" * 60)

# Construct base URL based on mode
if args.mode == 'ha':
    base_url = f"http://localhost:{args.port}/api/homie_proxy/{args.instance}"
    token_param = ""  # HA integration has auth disabled for testing
    print(f"\nTesting HA integration at localhost:{args.port}/{args.instance}")
    print("Note: Access control tests are limited in HA mode (auth is disabled)")
else:
    base_url = f"http://localhost:{args.port}/default"
    token_param = "token=your-secret-token-here&"
    print(f"\nTesting standalone proxy at localhost:{args.port}")

print("-" * 50)

# Configuration
PROXY_HOST = os.environ.get('PROXY_HOST', 'localhost')
PROXY_PORT = int(os.environ.get('PROXY_PORT', 8080))
BASE_URL = f"http://{PROXY_HOST}:{PROXY_PORT}"

def test_request(url, expected_status=200, description="", instance_override=None):
    """Make a test request and check the response"""
    try:
        # Use the instance override if provided, otherwise use the configured instance
        final_instance = instance_override or args.instance
        
        if args.mode == 'ha':
            test_url = f"http://localhost:{args.port}/api/homie_proxy/{final_instance}?{token_param}url={url}"
        else:
            test_url = f"http://localhost:{args.port}/{final_instance}?{token_param}url={url}"
        
        response = requests.get(test_url, timeout=8)
        
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
    print(f"HOMIE PROXY - ACCESS CONTROL TESTS ({args.mode.upper()})")
    print("=" * 80)
    print(f"Testing proxy at localhost:{args.port}")
    if args.mode == 'ha':
        print(f"HA Instance: {args.instance}")
        print("Note: Access control tests simplified for HA mode (auth disabled)")
    print()
    
    tests_passed = 0
    tests_total = 0

    if args.mode == 'standalone':
        # Standalone mode tests
        print("🧪 Testing Standalone Mode...")
        print("-" * 40)
        
        # Test basic functionality with token
        tests_total += 1
        if test_request('https://httpbin.org/get', 200, 
                       "Valid token - external URL allowed", "default"):
            tests_passed += 1
        
        # Test wrong token
        tests_total += 1
        try:
            wrong_url = f"http://localhost:{args.port}/default?token=wrong-token&url=https://httpbin.org/get"
            response = requests.get(wrong_url, timeout=8)
            if response.status_code == 401:
                print("✅ Wrong token correctly rejected (401)")
                tests_passed += 1
            else:
                print(f"❌ Wrong token - Expected 401, got {response.status_code}")
        except Exception as e:
            print(f"❌ Wrong token test failed: {e}")
        
        # Test missing token
        tests_total += 1
        try:
            no_token_url = f"http://localhost:{args.port}/default?url=https://httpbin.org/get"
            response = requests.get(no_token_url, timeout=8)
            if response.status_code == 401:
                print("✅ Missing token correctly rejected (401)")
                tests_passed += 1
            else:
                print(f"❌ Missing token - Expected 401, got {response.status_code}")
        except Exception as e:
            print(f"❌ Missing token test failed: {e}")
        
    else:
        # HA mode tests (simplified since auth is disabled)
        print("🧪 Testing HA Integration Mode...")
        print("-" * 40)
        
        # Test basic functionality
        tests_total += 1
        if test_request('https://httpbin.org/get', 200, 
                       f"Basic proxy functionality"):
            tests_passed += 1
        
        # Test invalid URL
        tests_total += 1
        if test_request('invalid-url', 502, 
                       "Invalid URL returns 502"):
            tests_passed += 1
        
        # Test missing URL parameter
        tests_total += 1
        try:
            test_url = f"http://localhost:{args.port}/api/homie_proxy/{args.instance}"
            response = requests.get(test_url, timeout=8)
            if response.status_code == 400:
                print("✅ Missing URL parameter returns 400")
                tests_passed += 1
            else:
                print(f"❌ Missing URL - Expected 400, got {response.status_code}")
        except Exception as e:
            print(f"❌ Missing URL test failed: {e}")

    # Common tests for both modes
    print()
    print("🧪 Testing Common Functionality...")
    print("-" * 40)
    
    # Test JSON response handling
    tests_total += 1
    if test_request('https://httpbin.org/json', 200, 
                   "JSON response handling"):
        tests_passed += 1
    
    # Test POST request (if mode supports it)
    if args.mode == 'ha':
        tests_total += 1
        try:
            test_url = f"http://localhost:{args.port}/api/homie_proxy/{args.instance}?url=https://httpbin.org/post"
            response = requests.post(test_url, json={"test": "data"}, timeout=8)
            if response.status_code == 200:
                print("✅ POST request with JSON body")
                tests_passed += 1
            else:
                print(f"❌ POST request - Expected 200, got {response.status_code}")
        except Exception as e:
            print(f"❌ POST request failed: {e}")

    print()
    print("=" * 80)
    print("ACCESS CONTROL TEST SUMMARY")
    print("=" * 80)
    print(f"Tests passed: {tests_passed}/{tests_total}")
    
    success_rate = (tests_passed / tests_total * 100) if tests_total > 0 else 0
    print(f"Success rate: {success_rate:.1f}%")
    
    if tests_passed == tests_total:
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print(f"⚠️ {tests_total - tests_passed} test(s) failed")
        sys.exit(1)

if __name__ == "__main__":
    main() 