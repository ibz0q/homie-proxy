#!/usr/bin/env python3
"""
Comprehensive redirect following test for HomieProxy integration
Tests redirect handling with various scenarios and configurations
"""

import requests
import json
import time
import urllib.parse
import os

# Configuration - can be overridden by environment variables
PROXY_HOST = os.getenv("PROXY_HOST", "localhost")
PROXY_PORT = int(os.getenv("PROXY_PORT", "8123"))  # Home Assistant default port
PROXY_NAME = os.getenv("PROXY_NAME", "external-api-route")
PROXY_TOKEN = os.getenv("PROXY_TOKEN", "93f00721-b834-460e-96f0-9978eb594e3f")

BASE_URL = f"http://{PROXY_HOST}:{PROXY_PORT}/api/homie_proxy"

def test_basic_redirect_following():
    """Test basic redirect following functionality"""
    print("Testing basic redirect following...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    
    # Test redirect NOT followed (default behavior)
    url = f"{BASE_URL}/{proxy_name}"
    params = {
        'url': 'https://httpbin.org/redirect/1',
        'token': token
    }
    
    try:
        response = requests.get(url, params=params, timeout=10, allow_redirects=False)
        print(f"Default behavior (no follow) - Status: {response.status_code}")
        
        if response.status_code in [301, 302, 303, 307, 308]:
            print("✓ Default behavior test passed - proxy returned redirect status")
        else:
            print("✗ Default behavior test failed - expected redirect status")
        
        # Test redirect followed
        params['follow_redirects'] = 'true'
        response = requests.get(url, params=params, timeout=10, allow_redirects=False)
        print(f"Follow redirects=true - Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                if 'args' in data and 'headers' in data:
                    print("✓ Redirect following test passed - got final JSON response")
                else:
                    print("✗ Redirect following test failed - unexpected response format")
            except json.JSONDecodeError:
                print("✗ Redirect following test failed - response not JSON")
        else:
            print("✗ Redirect following test failed - expected 200 status")
            
    except Exception as e:
        print(f"✗ Basic redirect test failed: {e}")

def test_multiple_redirects():
    """Test following multiple redirects"""
    print("\nTesting multiple redirects...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    test_cases = [
        (2, "2 redirects"),
        (3, "3 redirects"),
        (5, "5 redirects"),
    ]
    
    for redirect_count, description in test_cases:
        print(f"Testing {description}...")
        
        params = {
            'url': f'https://httpbin.org/redirect/{redirect_count}',
            'token': token,
            'follow_redirects': 'true'
        }
        
        try:
            start_time = time.time()
            response = requests.get(url, params=params, timeout=15, allow_redirects=False)
            end_time = time.time()
            
            print(f"  Status: {response.status_code}, Time: {end_time - start_time:.2f}s")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'url' in data and 'get' in data['url']:
                        print(f"  ✓ {description} test passed")
                    else:
                        print(f"  ✗ {description} test failed - unexpected response")
                except json.JSONDecodeError:
                    print(f"  ✗ {description} test failed - response not JSON")
            else:
                print(f"  ✗ {description} test failed - status {response.status_code}")
                
        except Exception as e:
            print(f"  ✗ {description} test failed: {e}")

def test_redirect_parameter_variations():
    """Test different parameter values for follow_redirects"""
    print("\nTesting redirect parameter variations...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    base_params = {
        'url': 'https://httpbin.org/redirect/1',
        'token': token
    }
    
    # Test values that should enable redirect following
    true_values = ['true', 'True', 'TRUE', '1', 'yes', 'Yes', 'YES']
    
    for value in true_values:
        print(f"Testing follow_redirects='{value}'...")
        
        params = base_params.copy()
        params['follow_redirects'] = value
        
        try:
            response = requests.get(url, params=params, timeout=10, allow_redirects=False)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'args' in data:
                        print(f"  ✓ Value '{value}' works correctly")
                    else:
                        print(f"  ✗ Value '{value}' failed - unexpected response")
                except json.JSONDecodeError:
                    print(f"  ✗ Value '{value}' failed - response not JSON")
            else:
                print(f"  ✗ Value '{value}' failed - status {response.status_code}")
                
        except Exception as e:
            print(f"  ✗ Value '{value}' failed: {e}")
    
    # Test values that should NOT enable redirect following
    false_values = ['false', 'False', 'FALSE', '0', 'no', 'No', 'NO', '']
    
    for value in false_values:
        print(f"Testing follow_redirects='{value}'...")
        
        params = base_params.copy()
        params['follow_redirects'] = value
        
        try:
            response = requests.get(url, params=params, timeout=10, allow_redirects=False)
            
            if response.status_code in [301, 302, 303, 307, 308]:
                print(f"  ✓ Value '{value}' correctly disables redirect following")
            else:
                print(f"  ✗ Value '{value}' failed - expected redirect status")
                
        except Exception as e:
            print(f"  ✗ Value '{value}' failed: {e}")

def test_redirect_with_different_methods():
    """Test redirect following with different HTTP methods"""
    print("\nTesting redirects with different HTTP methods...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    # Test POST with redirect
    print("Testing POST redirect...")
    params = {
        'url': 'https://httpbin.org/redirect-to?url=https://httpbin.org/post&status_code=302',
        'token': token,
        'follow_redirects': 'true'
    }
    
    test_data = {'test': 'POST redirect test', 'timestamp': time.time()}
    
    try:
        response = requests.post(url, params=params, json=test_data, timeout=10, allow_redirects=False)
        print(f"  POST redirect status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                if 'json' in data:
                    print("  ✓ POST redirect test passed")
                else:
                    print("  ✗ POST redirect test failed - no JSON data")
            except json.JSONDecodeError:
                print("  ✗ POST redirect test failed - response not JSON")
        else:
            print(f"  ✗ POST redirect test failed - status {response.status_code}")
            
    except Exception as e:
        print(f"  ✗ POST redirect test failed: {e}")

def test_redirect_limits():
    """Test redirect limits and infinite redirect protection"""
    print("\nTesting redirect limits...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    # Test many redirects (should be handled by aiohttp's default limits)
    print("Testing many redirects (10)...")
    params = {
        'url': 'https://httpbin.org/redirect/10',
        'token': token,
        'follow_redirects': 'true'
    }
    
    try:
        start_time = time.time()
        response = requests.get(url, params=params, timeout=20, allow_redirects=False)
        end_time = time.time()
        
        print(f"  Status: {response.status_code}, Time: {end_time - start_time:.2f}s")
        
        if response.status_code == 200:
            print("  ✓ Many redirects test passed")
        else:
            print(f"  ✗ Many redirects test failed or hit limit - status {response.status_code}")
            
    except Exception as e:
        print(f"  ✗ Many redirects test failed: {e}")

def test_redirect_with_custom_headers():
    """Test redirect following preserves custom headers"""
    print("\nTesting redirects with custom headers...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    params = {
        'url': 'https://httpbin.org/redirect/1',
        'token': token,
        'follow_redirects': 'true',
        'request_headers[User-Agent]': 'HomieProxy-Redirect-Test/1.0',
        'request_headers[X-Custom-Header]': 'redirect-test-value'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10, allow_redirects=False)
        
        if response.status_code == 200:
            try:
                data = response.json()
                headers = data.get('headers', {})
                
                user_agent = headers.get('User-Agent', '')
                custom_header = headers.get('X-Custom-Header', '')
                
                if 'HomieProxy-Redirect-Test' in user_agent:
                    print("  ✓ User-Agent header preserved through redirect")
                else:
                    print("  ✗ User-Agent header not preserved")
                
                if custom_header == 'redirect-test-value':
                    print("  ✓ Custom header preserved through redirect")
                else:
                    print("  ✗ Custom header not preserved")
                    
                print("  ✓ Redirect with custom headers test completed")
                
            except json.JSONDecodeError:
                print("  ✗ Redirect with custom headers test failed - response not JSON")
        else:
            print(f"  ✗ Redirect with custom headers test failed - status {response.status_code}")
            
    except Exception as e:
        print(f"  ✗ Redirect with custom headers test failed: {e}")

def test_redirect_chains():
    """Test complex redirect chains and status codes"""
    print("\nTesting different redirect status codes...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    redirect_codes = [301, 302, 303, 307, 308]
    
    for code in redirect_codes:
        print(f"Testing {code} redirect...")
        
        params = {
            'url': f'https://httpbin.org/redirect-to?url=https://httpbin.org/get&status_code={code}',
            'token': token,
            'follow_redirects': 'true'
        }
        
        try:
            response = requests.get(url, params=params, timeout=10, allow_redirects=False)
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'args' in data:
                        print(f"  ✓ {code} redirect test passed")
                    else:
                        print(f"  ✗ {code} redirect test failed - unexpected response")
                except json.JSONDecodeError:
                    print(f"  ✗ {code} redirect test failed - response not JSON")
            else:
                print(f"  ✗ {code} redirect test failed - status {response.status_code}")
                
        except Exception as e:
            print(f"  ✗ {code} redirect test failed: {e}")

def main():
    """Run all redirect following tests"""
    print("=" * 60)
    print("REDIRECT FOLLOWING TESTS - HOMIE PROXY INTEGRATION")
    print("=" * 60)
    print("Note: Make sure Home Assistant is running with HomieProxy configured")
    print("      and accessible at localhost:8123")
    print("")
    
    tests = [
        test_basic_redirect_following,
        test_multiple_redirects,
        test_redirect_parameter_variations,
        test_redirect_with_different_methods,
        test_redirect_limits,
        test_redirect_with_custom_headers,
        test_redirect_chains
    ]
    
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
        
        time.sleep(1)  # Brief pause between tests
    
    print("\n" + "=" * 60)
    print("Redirect following tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    main() 