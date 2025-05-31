#!/usr/bin/env python3

import requests
import argparse
import os

# Parse command line arguments or use environment variable
parser = argparse.ArgumentParser(description='Test reverse proxy basic functionality')
parser.add_argument('--port', type=int, 
                   default=int(os.environ.get('PROXY_PORT', 8080)),
                   help='Proxy server port (default: 8080, or PROXY_PORT env var)')
parser.add_argument('--mode', choices=['standalone', 'ha'], default='standalone',
                   help='Test mode: standalone proxy or Home Assistant integration (default: standalone)')
parser.add_argument('--instance', default='external-api-route',
                   help='HA integration instance name (default: external-api-route)')
args = parser.parse_args()

print("=" * 60)
print(f"SIMPLE BASIC TEST - REVERSE PROXY ({args.mode.upper()})")
print("=" * 60)

# Construct base URL based on mode
if args.mode == 'ha':
    base_url = f"http://localhost:{args.port}/api/homie_proxy/{args.instance}"
    token_param = ""  # HA integration has auth disabled for testing
else:
    base_url = f"http://localhost:{args.port}/default"
    token_param = "token=your-secret-token-here&"

print(f"\nTesting proxy at localhost:{args.port} ({args.mode} mode)")
print("-" * 50)

# Test 1: Simple GET request
print("\nTest 1: Basic GET request")
test_url = f"{base_url}?{token_param}url=https://httpbin.org/get"

try:
    print("Making request...")
    response = requests.get(test_url, timeout=8)
    
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    print(f"Response size: {len(response.content)} bytes")
    
    if response.status_code == 200:
        print("SUCCESS: Basic GET request working!")
    else:
        print(f"FAILED: Unexpected status {response.status_code}")
        
except Exception as e:
    print(f"ERROR: {e}")

# Test 2: Host header check
print("\nTest 2: Host header verification")
test_url2 = f"{base_url}?{token_param}url=https://httpbin.org/headers"

try:
    print("Making headers request...")
    response = requests.get(test_url2, timeout=8)
    
    if response.status_code == 200:
        import json
        data = response.json()
        host_header = data.get('headers', {}).get('Host', 'NOT FOUND')
        print(f"Host header received by target: {host_header}")
        
        if host_header == 'httpbin.org':
            print("SUCCESS: Host header fix working correctly!")
        else:
            print(f"FAILED: Host header incorrect - {host_header}")
    else:
        print(f"FAILED: Status {response.status_code}")
        
except Exception as e:
    print(f"ERROR: {e}")

print("\n" + "=" * 60)
print("Simple test completed!")
print("=" * 60) 