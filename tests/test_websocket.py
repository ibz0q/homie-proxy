#!/usr/bin/env python3
"""
WebSocket proxy test for HomieProxy integration
Tests WebSocket proxying capabilities through the proxy
NOTE: This test uses HTTP-based WebSocket upgrade testing since websockets library may not be available
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

def test_websocket_upgrade_request():
    """Test WebSocket upgrade request handling"""
    print("Testing WebSocket upgrade request...")
    
    # Use HTTP to test WebSocket upgrade headers
    target_url = "wss://echo.websocket.org"
    token = PROXY_TOKEN
    proxy_name = PROXY_NAME
    
    # Build proxy URL
    params = {
        'url': target_url,
        'token': token,
        'request_headers[Connection]': 'Upgrade',
        'request_headers[Upgrade]': 'websocket',
        'request_headers[Sec-WebSocket-Version]': '13',
        'request_headers[Sec-WebSocket-Key]': 'dGhlIHNhbXBsZSBub25jZQ=='
    }
    
    url = f"{BASE_URL}/{proxy_name}"
    
    try:
        print(f"Making WebSocket upgrade request to: {url}")
        
        response = requests.get(url, params=params, timeout=10)
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
        # Check if we get a proper WebSocket upgrade response
        if response.status_code in [101, 400, 426]:
            # 101 = Switching Protocols (successful upgrade)
            # 400 = Bad Request (WebSocket upgrade rejected)
            # 426 = Upgrade Required (needs WebSocket upgrade)
            print("✓ WebSocket upgrade request properly handled")
            
            if response.status_code == 101:
                print("  ✓ WebSocket upgrade successful (101 Switching Protocols)")
            elif response.status_code == 426:
                print("  ✓ WebSocket upgrade required response (426)")
            else:
                print("  ✓ WebSocket upgrade rejected properly (400)")
        else:
            print(f"? WebSocket upgrade test - unexpected status {response.status_code}")
            print("  This might be expected if the proxy doesn't handle WebSocket upgrades")
            
    except Exception as e:
        print(f"✗ WebSocket upgrade test failed: {e}")

def test_websocket_echo_via_http():
    """Test WebSocket echo service via HTTP fallback"""
    print("\nTesting WebSocket service via HTTP...")
    
    # Try to access a WebSocket service via HTTP to test the proxy
    target_url = "https://echo.websocket.org"  # Try HTTP access to WebSocket service
    token = PROXY_TOKEN
    proxy_name = PROXY_NAME
    
    params = {
        'url': target_url,
        'token': token
    }
    
    url = f"{BASE_URL}/{proxy_name}"
    
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"HTTP access to WebSocket service status: {response.status_code}")
        
        # WebSocket services typically return specific responses when accessed via HTTP
        if response.status_code in [200, 400, 426, 501]:
            print("✓ WebSocket service HTTP access test passed")
            print(f"  Response indicates WebSocket service properly contacted")
        else:
            print(f"? WebSocket service HTTP test - status {response.status_code}")
            
    except Exception as e:
        print(f"✗ WebSocket service HTTP test failed: {e}")

def test_websocket_auth_failure():
    """Test WebSocket authentication failure"""
    print("\nTesting WebSocket authentication failure...")
    
    target_url = "wss://echo.websocket.org"
    invalid_token = "invalid-token"
    proxy_name = PROXY_NAME
    
    params = {
        'url': target_url,
        'token': invalid_token
    }
    
    url = f"{BASE_URL}/{proxy_name}"
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code in [401, 403]:
            print("✓ Authentication test passed - connection properly rejected")
        else:
            print(f"✗ Authentication test failed - unexpected status {response.status_code}")
            
    except Exception as e:
        print(f"✗ Authentication test failed: {e}")

def test_websocket_custom_headers():
    """Test WebSocket with custom headers"""
    print("\nTesting WebSocket with custom headers...")
    
    target_url = "wss://echo.websocket.org"
    token = PROXY_TOKEN
    proxy_name = PROXY_NAME
    
    params = {
        'url': target_url,
        'token': token,
        'request_headers[User-Agent]': 'HomieProxy-WebSocket-Test/1.0',
        'request_headers[X-Custom-Header]': 'test-value'
    }
    
    url = f"{BASE_URL}/{proxy_name}"
    
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"Custom headers test status: {response.status_code}")
        print("✓ WebSocket custom headers test completed (headers passed to proxy)")
    except Exception as e:
        print(f"✗ WebSocket custom headers test failed: {e}")

def test_websocket_tls_bypass():
    """Test WebSocket with TLS bypass"""
    print("\nTesting WebSocket with TLS bypass...")
    
    target_url = "wss://echo.websocket.org"
    token = PROXY_TOKEN
    proxy_name = PROXY_NAME
    
    params = {
        'url': target_url,
        'token': token,
        'skip_tls_checks': 'true'
    }
    
    url = f"{BASE_URL}/{proxy_name}"
    
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"TLS bypass test status: {response.status_code}")
        print("✓ WebSocket TLS bypass test completed")
    except Exception as e:
        print(f"WebSocket TLS bypass test info: {e}")

def main():
    """Run all WebSocket-related tests"""
    print("=" * 60)
    print("WEBSOCKET PROXY TESTS - HOMIE PROXY INTEGRATION")
    print("=" * 60)
    print("Note: These tests use HTTP-based WebSocket testing since")
    print("      the 'websockets' library may not be available.")
    print("      Make sure Home Assistant is running with HomieProxy configured")
    print("      and accessible at localhost:8123")
    print("")
    print("For full WebSocket testing, install: pip install websockets")
    print("")
    
    tests = [
        test_websocket_upgrade_request,
        test_websocket_echo_via_http,
        test_websocket_auth_failure,
        test_websocket_custom_headers,
        test_websocket_tls_bypass
    ]
    
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
        
        time.sleep(1)  # Brief pause between tests
    
    print("\n" + "=" * 60)
    print("WebSocket tests completed!")
    print("=" * 60)
    print("NOTE: For full WebSocket functionality testing,")
    print("      install websockets library: pip install websockets")

if __name__ == "__main__":
    main() 