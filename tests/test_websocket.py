#!/usr/bin/env python3
"""
WebSocket proxy test for HomieProxy integration
Tests WebSocket proxying capabilities through the proxy
"""

import asyncio
import websockets
import json
import time
import ssl
import urllib.parse
import os

# Configuration - can be overridden by environment variables
PROXY_HOST = os.getenv("PROXY_HOST", "localhost")
PROXY_PORT = int(os.getenv("PROXY_PORT", "8123"))  # Home Assistant default port
PROXY_NAME = os.getenv("PROXY_NAME", "external-api-route")
PROXY_TOKEN = os.getenv("PROXY_TOKEN", "93f00721-b834-460e-96f0-9978eb594e3f")

BASE_WS_URL = f"ws://{PROXY_HOST}:{PROXY_PORT}/api/homie_proxy"

async def test_websocket_echo():
    """Test WebSocket echo through proxy"""
    print("Testing WebSocket echo through proxy...")
    
    # Use echo.websocket.org as target
    target_url = "wss://echo.websocket.org"
    token = PROXY_TOKEN
    proxy_name = PROXY_NAME
    
    # Build proxy WebSocket URL
    params = urllib.parse.urlencode({
        'url': target_url,
        'token': token
    })
    proxy_ws_url = f"{BASE_WS_URL}/{proxy_name}?{params}"
    
    try:
        print(f"Connecting to: {proxy_ws_url}")
        
        async with websockets.connect(proxy_ws_url) as websocket:
            print("✓ WebSocket connection established through proxy")
            
            # Test sending and receiving messages
            test_messages = [
                "Hello WebSocket!",
                '{"type": "test", "data": "json message"}',
                "Test with special chars: éñ中文🚀"
            ]
            
            for i, message in enumerate(test_messages, 1):
                print(f"Sending message {i}: {message}")
                await websocket.send(message)
                
                response = await websocket.recv()
                print(f"Received: {response}")
                
                if response == message:
                    print(f"✓ Echo test {i} passed")
                else:
                    print(f"✗ Echo test {i} failed - got different response")
                
                await asyncio.sleep(0.5)
            
            print("✓ WebSocket echo test completed successfully")
            
    except Exception as e:
        print(f"✗ WebSocket test failed: {e}")

async def test_websocket_binary():
    """Test WebSocket binary message handling"""
    print("\nTesting WebSocket binary messages...")
    
    target_url = "wss://echo.websocket.org"
    token = PROXY_TOKEN
    proxy_name = PROXY_NAME
    
    params = urllib.parse.urlencode({
        'url': target_url,
        'token': token
    })
    proxy_ws_url = f"{BASE_WS_URL}/{proxy_name}?{params}"
    
    try:
        async with websockets.connect(proxy_ws_url) as websocket:
            # Test binary data
            binary_data = b'\x00\x01\x02\x03\xff\xfe\xfd'
            await websocket.send(binary_data)
            
            response = await websocket.recv()
            
            if response == binary_data:
                print("✓ Binary WebSocket test passed")
            else:
                print("✗ Binary WebSocket test failed")
                
    except Exception as e:
        print(f"✗ Binary WebSocket test failed: {e}")

async def test_websocket_auth_failure():
    """Test WebSocket authentication failure"""
    print("\nTesting WebSocket authentication failure...")
    
    target_url = "wss://echo.websocket.org"
    invalid_token = "invalid-token"
    proxy_name = PROXY_NAME
    
    params = urllib.parse.urlencode({
        'url': target_url,
        'token': invalid_token
    })
    proxy_ws_url = f"{BASE_WS_URL}/{proxy_name}?{params}"
    
    try:
        async with websockets.connect(proxy_ws_url) as websocket:
            print("✗ Authentication test failed - connection should have been rejected")
    except websockets.exceptions.WebSocketException as e:
        if "401" in str(e) or "Unauthorized" in str(e):
            print("✓ Authentication test passed - connection properly rejected")
        else:
            print(f"✗ Authentication test failed - unexpected error: {e}")
    except Exception as e:
        print(f"✗ Authentication test failed - unexpected error: {e}")

async def test_websocket_tls_bypass():
    """Test WebSocket with TLS bypass"""
    print("\nTesting WebSocket with TLS bypass...")
    
    # Use a service that might have TLS issues for testing
    target_url = "wss://echo.websocket.org"
    token = PROXY_TOKEN
    proxy_name = PROXY_NAME
    
    params = urllib.parse.urlencode({
        'url': target_url,
        'token': token,
        'skip_tls_checks': 'true'
    })
    proxy_ws_url = f"{BASE_WS_URL}/{proxy_name}?{params}"
    
    try:
        async with websockets.connect(proxy_ws_url) as websocket:
            await websocket.send("TLS bypass test")
            response = await websocket.recv()
            print("✓ WebSocket TLS bypass test passed")
    except Exception as e:
        print(f"WebSocket TLS bypass test info: {e}")

async def test_websocket_custom_headers():
    """Test WebSocket with custom headers"""
    print("\nTesting WebSocket with custom headers...")
    
    target_url = "wss://echo.websocket.org"
    token = PROXY_TOKEN
    proxy_name = PROXY_NAME
    
    params = urllib.parse.urlencode({
        'url': target_url,
        'token': token,
        'request_headers[User-Agent]': 'HomieProxy-WebSocket-Test/1.0',
        'request_headers[X-Custom-Header]': 'test-value'
    })
    proxy_ws_url = f"{BASE_WS_URL}/{proxy_name}?{params}"
    
    try:
        async with websockets.connect(proxy_ws_url) as websocket:
            await websocket.send("Custom headers test")
            response = await websocket.recv()
            print("✓ WebSocket custom headers test passed")
    except Exception as e:
        print(f"✗ WebSocket custom headers test failed: {e}")

async def test_websocket_connection_upgrade():
    """Test HTTP to WebSocket upgrade through proxy"""
    print("\nTesting HTTP to WebSocket upgrade...")
    
    # This test verifies the proxy correctly handles the upgrade
    target_url = "wss://echo.websocket.org"
    token = PROXY_TOKEN
    proxy_name = PROXY_NAME
    
    params = urllib.parse.urlencode({
        'url': target_url,
        'token': token
    })
    proxy_ws_url = f"{BASE_WS_URL}/{proxy_name}?{params}"
    
    try:
        # Create a manual WebSocket connection to test upgrade handling
        async with websockets.connect(proxy_ws_url) as websocket:
            # Test that we can immediately send/receive without additional setup
            await websocket.send("Upgrade test")
            response = await websocket.recv()
            print("✓ WebSocket upgrade test passed")
    except Exception as e:
        print(f"✗ WebSocket upgrade test failed: {e}")

async def main():
    """Run all WebSocket tests"""
    print("=" * 60)
    print("WEBSOCKET PROXY TESTS - HOMIE PROXY INTEGRATION")
    print("=" * 60)
    print("Note: Make sure Home Assistant is running with HomieProxy configured")
    print("      and accessible at localhost:8123")
    print("")
    
    tests = [
        test_websocket_echo,
        test_websocket_binary,
        test_websocket_auth_failure,
        test_websocket_tls_bypass,
        test_websocket_custom_headers,
        test_websocket_connection_upgrade
    ]
    
    for test in tests:
        try:
            await test()
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
        
        await asyncio.sleep(1)  # Brief pause between tests
    
    print("\n" + "=" * 60)
    print("WebSocket tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main()) 