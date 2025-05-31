#!/usr/bin/env python3

import requests
import time

print("=" * 60)
print("HEADER LOGGING DEMONSTRATION")
print("=" * 60)

base_url = "http://localhost:8080/default?token=your-secret-token-here"

print("\nMaking a simple request to demonstrate header logging...")
print("Check the server console for detailed request/response headers!")
print("-" * 60)

# Test 1: Simple GET with custom headers
print("\nTest 1: GET request with custom headers")
try:
    url = f"{base_url}&url=https://httpbin.org/headers&request_headers[User-Agent]=HeaderTest/1.0&request_headers[X-Custom]=TestValue"
    response = requests.get(url, timeout=8)
    print(f"Response status: {response.status_code}")
    if response.status_code == 200:
        print("SUCCESS: Check server console for REQUEST and RESPONSE header details")
    else:
        print(f"Unexpected status: {response.status_code}")
except Exception as e:
    print(f"Error: {e}")

# Test 2: POST request 
print("\nTest 2: POST request with JSON body")
try:
    url = f"{base_url}&url=https://httpbin.org/post"
    data = {"test": "data", "demo": "header_logging"}
    response = requests.post(url, json=data, timeout=8)
    print(f"Response status: {response.status_code}")
    if response.status_code == 200:
        print("SUCCESS: Check server console for POST request headers and body logging")
    else:
        print(f"Unexpected status: {response.status_code}")
except Exception as e:
    print(f"Error: {e}")

# Test 3: Redirect to see both original and final request/response
print("\nTest 3: Redirect following to see multiple request/response cycles")
try:
    url = f"{base_url}&url=https://httpbin.org/redirect/1&follow_redirects=true"
    response = requests.get(url, timeout=8)
    print(f"Final response status: {response.status_code}")
    if response.status_code == 200:
        print("SUCCESS: Check server console for redirect chain logging")
    else:
        print(f"Unexpected status: {response.status_code}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("WHAT TO LOOK FOR IN SERVER CONSOLE:")
print("=" * 60)
print("REQUEST sections show:")
print("- REQUEST to [URL]")
print("- Request method: [METHOD]") 
print("- Request headers being sent to target:")
print("- Request body details (if any)")
print()
print("RESPONSE sections show:")
print("- RESPONSE from [URL]")
print("- Response status: [CODE]")
print("- Response headers received from target:")
print()
print("All headers are properly formatted and long values are truncated")
print("=" * 60) 