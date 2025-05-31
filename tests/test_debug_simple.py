#!/usr/bin/env python3

import requests

print("Making test request to see debug logs...")

url = "http://10.5.254.10:8080/default?token=your-secret-token-here&url=https://httpbin.org/response-headers?Content-Type=video/mp4&cache=true"

try:
    response = requests.get(url, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print(f"X-Cache: {response.headers.get('X-Cache', 'MISS')}")
    print("Check server console for debug logs!")
except Exception as e:
    print(f"Error: {e}") 