#!/usr/bin/env python3

import requests
import json

print("=" * 70)
print("RESPONSE HEADERS TEST - INCLUDING CORS HEADERS")
print("=" * 70)

base_url = "http://localhost:8080/default?token=your-secret-token-here"

print("\n1. TESTING BASIC RESPONSE HEADERS FROM HTTPBIN")
print("=" * 60)

# Test basic response from httpbin to see what headers come through
test_url = f"{base_url}&url=https://httpbin.org/get"
try:
    response = requests.get(test_url)
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Response Headers from httpbin (via proxy):")
    for header, value in response.headers.items():
        print(f"   {header}: {value}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n\n2. TESTING CUSTOM RESPONSE HEADERS VIA PROXY")
print("=" * 60)

# Test adding custom response headers via proxy URL parameters
cors_test_url = (f"{base_url}&url=https://httpbin.org/get"
                f"&response_header[Access-Control-Allow-Origin]=*"
                f"&response_header[Access-Control-Allow-Methods]=GET,POST,PUT,DELETE,OPTIONS"
                f"&response_header[Access-Control-Allow-Headers]=Content-Type,Authorization,X-Custom-Header"
                f"&response_header[X-Custom-Response]=ProxyAddedHeader")

print("🔸 Adding CORS and custom headers via proxy parameters...")
try:
    response = requests.get(cors_test_url)
    print(f"✅ Status: {response.status_code}")
    
    # Check for the custom headers we added
    cors_headers = {
        'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
        'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
        'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers'),
        'X-Custom-Response': response.headers.get('X-Custom-Response')
    }
    
    print(f"📥 Custom headers added by proxy:")
    for header, value in cors_headers.items():
        status = "✅" if value else "❌"
        print(f"   {status} {header}: {value or 'NOT FOUND'}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n\n3. TESTING CORS PREFLIGHT SIMULATION")
print("=" * 60)

# Test with OPTIONS method to simulate CORS preflight
options_url = f"{base_url}&url=https://httpbin.org/get&response_header[Access-Control-Allow-Origin]=*"
try:
    response = requests.options(options_url)
    print(f"✅ OPTIONS Status: {response.status_code}")
    print(f"📥 CORS Origin header: {response.headers.get('Access-Control-Allow-Origin', 'NOT FOUND')}")
except Exception as e:
    print(f"❌ OPTIONS Error: {e}")

print("\n\n4. TESTING HTTPBIN CORS ENDPOINT")
print("=" * 60)

# Test httpbin's actual CORS endpoint
cors_endpoint_url = f"{base_url}&url=https://httpbin.org/response-headers?Access-Control-Allow-Origin=*&Custom-Header=test"
try:
    response = requests.get(cors_endpoint_url)
    print(f"✅ Status: {response.status_code}")
    
    # Parse the response to see what httpbin returned
    response_data = response.json()
    print(f"📥 Response from httpbin CORS endpoint:")
    print(json.dumps(response_data, indent=2))
    
    # Check actual response headers
    print(f"📥 Actual response headers:")
    cors_related = ['Access-Control-Allow-Origin', 'Custom-Header', 'Content-Type']
    for header in cors_related:
        value = response.headers.get(header, 'NOT FOUND')
        print(f"   {header}: {value}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n\n5. TESTING MULTIPLE CUSTOM RESPONSE HEADERS")
print("=" * 60)

# Test multiple custom headers
multi_header_url = (f"{base_url}&url=https://httpbin.org/get"
                   f"&response_header[X-API-Version]=1.0"
                   f"&response_header[X-Rate-Limit]=100"
                   f"&response_header[X-Proxy-Source]=Python-Reverse-Proxy"
                   f"&response_header[Cache-Control]=no-cache")

try:
    response = requests.get(multi_header_url)
    print(f"✅ Status: {response.status_code}")
    
    custom_headers = ['X-API-Version', 'X-Rate-Limit', 'X-Proxy-Source', 'Cache-Control']
    print(f"📥 Multiple custom headers:")
    for header in custom_headers:
        value = response.headers.get(header, 'NOT FOUND')
        status = "✅" if value != 'NOT FOUND' else "❌"
        print(f"   {status} {header}: {value}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n\n6. COMPARISON: DIRECT VS PROXIED RESPONSE HEADERS")
print("=" * 60)

# Compare headers from direct request vs proxied request
print("🔸 Direct request to httpbin...")
try:
    direct_response = requests.get('https://httpbin.org/get')
    print(f"   Status: {direct_response.status_code}")
    direct_headers = dict(direct_response.headers)
except Exception as e:
    print(f"   Error: {e}")
    direct_headers = {}

print("🔸 Proxied request to httpbin...")
try:
    proxy_response = requests.get(f"{base_url}&url=https://httpbin.org/get")
    print(f"   Status: {proxy_response.status_code}")
    proxy_headers = dict(proxy_response.headers)
except Exception as e:
    print(f"   Error: {e}")
    proxy_headers = {}

# Compare key headers
if direct_headers and proxy_headers:
    key_headers = ['Content-Type', 'Content-Length', 'Server', 'Date']
    print(f"📊 Header comparison:")
    for header in key_headers:
        direct_val = direct_headers.get(header, 'NOT FOUND')
        proxy_val = proxy_headers.get(header, 'NOT FOUND')
        match = "✅" if direct_val == proxy_val else "❌"
        print(f"   {match} {header}:")
        print(f"      Direct:  {direct_val}")
        print(f"      Proxied: {proxy_val}")

print("\n" + "=" * 70)
print("🎯 Response headers test completed!")
print("=" * 70) 