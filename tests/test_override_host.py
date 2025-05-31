#!/usr/bin/env python3

import requests

print("=" * 60)
print("TESTING OVERRIDE HOST HEADER FUNCTIONALITY")
print("=" * 60)

base_url = "http://localhost:8080/default?token=your-secret-token-here"

# Test the specific URL you provided
test_url = f"{base_url}&url=https://1.1.1.1&override_host_header=one.one.one.one&skip_tls_checks=all"

print(f"\nTesting URL: {test_url}")
print("-" * 60)

try:
    print("Making request...")
    response = requests.get(test_url, timeout=15)
    
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    print(f"Response size: {len(response.content)} bytes")
    
    if response.status_code == 200:
        print("SUCCESS: Request completed successfully!")
        print("Response preview:")
        print(response.text[:500])
    else:
        print(f"Got status {response.status_code}")
        print("Response:")
        print(response.text[:500])
        
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("Test completed!")
print("=" * 60) 