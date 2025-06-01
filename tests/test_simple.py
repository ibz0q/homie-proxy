#!/usr/bin/env python3

import requests
import argparse
import os

# Parse command line arguments or use environment variable
parser = argparse.ArgumentParser(description='Test reverse proxy basic functionality')
parser.add_argument('--host', default=os.environ.get('PROXY_HOST', 'localhost'),
                   help='Proxy host (default: localhost)')
parser.add_argument('--port', type=int, 
                   default=int(os.environ.get('PROXY_PORT', 8080)),
                   help='Proxy server port (default: 8080, or PROXY_PORT env var)')
parser.add_argument('--name', default=os.environ.get('PROXY_NAME', 'external-api-route'),
                   help='HA integration instance name (default: external-api-route)')
parser.add_argument('--token', default=os.environ.get('PROXY_TOKEN', ''),
                   help='Authentication token (auto-detected if not provided)')
parser.add_argument('--mode', choices=['standalone', 'ha'], default='ha',
                   help='Test mode: standalone proxy or Home Assistant integration (default: ha)')
args = parser.parse_args()

print("=" * 60)
print(f"SIMPLE BASIC TEST - REVERSE PROXY ({args.mode.upper()})")
print("=" * 60)

# Construct base URL based on mode
if args.mode == 'ha':
    base_url = f"http://{args.host}:{args.port}/api/homie_proxy/{args.name}"
    # Use provided token or auto-detect from debug endpoint
    if args.token:
        token_param = f"token={args.token}&"
        print(f"Using provided token: {args.token[:8]}...")
    else:
        print("No token provided - this test requires a token for HA mode")
        print("Please provide token via --token argument or PROXY_TOKEN environment variable")
        exit(1)
else:
    base_url = f"http://{args.host}:{args.port}/default"
    token_param = f"token={args.token or 'your-secret-token-here'}&"

print(f"\nTesting proxy at {args.host}:{args.port} ({args.mode} mode)")
print(f"Instance: {args.name}")
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