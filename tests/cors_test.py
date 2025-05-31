#!/usr/bin/env python3

import requests
import json

print("=" * 60)
print("CORS HEADERS TEST - REVERSE PROXY")
print("=" * 60)

print("\n📋 HOW TO SET CORS HEADERS VIA REVERSE PROXY:")
print("-" * 50)

# Show the exact URL structure for setting CORS headers
base_url = "http://localhost:8080/default?token=your-secret-token-here"
target_url = "https://httpbin.org/get"

# Example 1: Basic CORS header
cors_url_1 = f"{base_url}&url={target_url}&response_header[Access-Control-Allow-Origin]=*"
print(f"Example 1 - Basic CORS:")
print(f"URL: {cors_url_1}")

# Example 2: Full CORS headers
cors_url_2 = (f"{base_url}&url={target_url}"
              f"&response_header[Access-Control-Allow-Origin]=*"
              f"&response_header[Access-Control-Allow-Methods]=GET,POST,PUT,DELETE,OPTIONS"
              f"&response_header[Access-Control-Allow-Headers]=Content-Type,Authorization,X-Custom-Header"
              f"&response_header[Access-Control-Max-Age]=86400")

print(f"\nExample 2 - Full CORS headers:")
print(f"URL: {cors_url_2}")

print(f"\n📋 CURL COMMAND EXAMPLES:")
print("-" * 50)
print(f"curl \"{cors_url_1}\"")
print(f"\ncurl \"{cors_url_2}\"")

print("\n🧪 TESTING CORS HEADERS:")
print("-" * 50)

# Test 1: Basic CORS
print("\n🔸 Test 1: Basic CORS header")
try:
    response = requests.get(cors_url_1)
    cors_origin = response.headers.get('Access-Control-Allow-Origin', 'NOT FOUND')
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Access-Control-Allow-Origin: {cors_origin}")
    print(f"✅ SUCCESS!" if cors_origin == '*' else f"❌ FAILED - Expected '*', got '{cors_origin}'")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Multiple CORS headers
print("\n🔸 Test 2: Multiple CORS headers")
try:
    response = requests.get(cors_url_2)
    cors_headers = {
        'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
        'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
        'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers'),
        'Access-Control-Max-Age': response.headers.get('Access-Control-Max-Age')
    }
    
    print(f"✅ Status: {response.status_code}")
    for header, value in cors_headers.items():
        status = "✅" if value else "❌"
        print(f"{status} {header}: {value or 'NOT FOUND'}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: OPTIONS preflight request
print("\n🔸 Test 3: OPTIONS preflight request")
try:
    response = requests.options(cors_url_2)
    print(f"✅ OPTIONS Status: {response.status_code}")
    print(f"📥 Allow-Origin: {response.headers.get('Access-Control-Allow-Origin', 'NOT FOUND')}")
    print(f"📥 Allow-Methods: {response.headers.get('Access-Control-Allow-Methods', 'NOT FOUND')}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 4: Show what the client receives
print("\n🔸 Test 4: Full response details")
try:
    response = requests.get(cors_url_1)
    print(f"✅ Status: {response.status_code}")
    print(f"📥 ALL Response Headers:")
    for header, value in response.headers.items():
        if 'access-control' in header.lower() or 'cors' in header.lower():
            print(f"   🎯 {header}: {value}")
        else:
            print(f"      {header}: {value}")
            
    # Show what httpbin received
    response_data = response.json()
    print(f"\n📥 What httpbin.org received:")
    print(f"   URL: {response_data.get('url', 'N/A')}")
    print(f"   Method: {response_data.get('method', 'N/A')}")
    
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)
print("🎯 CORS test completed!")
print("=" * 60) 