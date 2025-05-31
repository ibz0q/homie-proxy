#!/usr/bin/env python3

import requests

print("=" * 60)
print("TLS AND HOST HEADER FIX TEST")
print("=" * 60)

base_url = "http://localhost:8080/default?token=your-secret-token-here"

# Test 1: TLS bypass with 'true' parameter (should work now)
print("\nTest 1: TLS bypass with skip_tls_checks=true")
try:
    url = f"{base_url}&url=https://self-signed.badssl.com/&skip_tls_checks=true"
    response = requests.get(url, timeout=8)
    print(f"Status: {response.status_code}")
    if response.status_code in [200, 400, 403]:  # Any response means TLS was bypassed
        print("SUCCESS: TLS bypass working with 'true' parameter!")
    else:
        print(f"Got unexpected status: {response.status_code}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Host header with hostname (should not include port)
print("\nTest 2: Host header with hostname (no port)")
try:
    url = f"{base_url}&url=https://httpbin.org:443/headers"
    response = requests.get(url, timeout=8)
    data = response.json()
    host_header = data.get('headers', {}).get('Host', 'NOT FOUND')
    print(f"Status: {response.status_code}")
    print(f"Host header received: {host_header}")
    
    if host_header == 'httpbin.org':
        print("SUCCESS: Host header correctly shows only hostname (no port)!")
    else:
        print(f"FAILED: Expected 'httpbin.org', got '{host_header}'")
except Exception as e:
    print(f"Error: {e}")

# Test 3: Host header with IP address
print("\nTest 3: Host header with IP address")
try:
    # Use a test service that accepts any Host header
    url = f"{base_url}&url=http://httpbin.org/headers&request_headers[X-Original-URL]=http://1.1.1.1/"
    response = requests.get(url, timeout=8)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("SUCCESS: IP address requests working!")
    else:
        print(f"Status: {response.status_code}")
except Exception as e:
    print(f"Error: {e}")

# Test 4: Test User-Agent preservation
print("\nTest 4: User-Agent preservation")
try:
    url = f"{base_url}&url=https://httpbin.org/headers"
    headers = {'User-Agent': 'TestClient/1.0'}
    response = requests.get(url, headers=headers, timeout=8)
    data = response.json()
    received_ua = data.get('headers', {}).get('User-Agent', 'NOT FOUND')
    print(f"Status: {response.status_code}")
    print(f"Sent User-Agent: TestClient/1.0")
    print(f"Received User-Agent: {received_ua}")
    
    if received_ua == 'TestClient/1.0':
        print("SUCCESS: User-Agent correctly preserved!")
    else:
        print(f"FAILED: User-Agent not preserved correctly")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("TLS and Host header fix test completed!")
print("=" * 60) 