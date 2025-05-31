#!/usr/bin/env python3

import requests

print("=" * 60)
print("SIMPLE BASIC TEST - REVERSE PROXY")
print("=" * 60)

base_url = "http://localhost:8080/default?token=your-secret-token-here"

print("\nTesting basic functionality...")
print("-" * 50)

# Test 1: Simple GET request
print("\nTest 1: Basic GET request")
test_url = f"{base_url}&url=https://httpbin.org/get"

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
test_url2 = f"{base_url}&url=https://httpbin.org/headers"

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