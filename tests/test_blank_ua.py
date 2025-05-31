#!/usr/bin/env python3

import requests
import json
import argparse
import os

# Parse command line arguments or use environment variable
parser = argparse.ArgumentParser(description='Test reverse proxy User-Agent handling')
parser.add_argument('--port', type=int, 
                   default=int(os.environ.get('PROXY_PORT', 8080)),
                   help='Proxy server port (default: 8080, or PROXY_PORT env var)')
args = parser.parse_args()

print("=" * 60)
print("BLANK USER-AGENT DEFAULT TEST")
print("=" * 60)

base_url = f"http://localhost:{args.port}/default?token=your-secret-token-here&url=https://httpbin.org/get"

print(f"\nTesting proxy at localhost:{args.port}")
print("-" * 50)

# Test 1: No User-Agent provided (should be blank now)
print("\n🔸 Test 1: No User-Agent provided")
print("-" * 40)
try:
    # Remove User-Agent header completely
    session = requests.Session()
    session.headers.pop('User-Agent', None)
    
    response = session.get(base_url)
    data = response.json()
    received_ua = data.get('headers', {}).get('User-Agent', 'NOT FOUND')
    
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Received User-Agent: '{received_ua}'")
    
    if received_ua == '':
        print("✅ SUCCESS: Blank User-Agent working!")
    else:
        print(f"❌ FAILED: Expected blank, got '{received_ua}'")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Custom User-Agent provided (should be preserved)
print("\n🔸 Test 2: Custom User-Agent provided")
print("-" * 40)
custom_ua = "MyCustomAgent/1.0"
try:
    response = requests.get(base_url, headers={'User-Agent': custom_ua})
    data = response.json()
    received_ua = data.get('headers', {}).get('User-Agent', 'NOT FOUND')
    
    print(f"✅ Status: {response.status_code}")
    print(f"📤 Sent User-Agent: '{custom_ua}'")
    print(f"📥 Received User-Agent: '{received_ua}'")
    
    if received_ua == custom_ua:
        print("✅ SUCCESS: Custom User-Agent preserved!")
    else:
        print(f"❌ FAILED: Expected '{custom_ua}', got '{received_ua}'")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Empty User-Agent explicitly set
print("\n🔸 Test 3: Empty User-Agent explicitly set")
print("-" * 40)
try:
    response = requests.get(base_url, headers={'User-Agent': ''})
    data = response.json()
    received_ua = data.get('headers', {}).get('User-Agent', 'NOT FOUND')
    
    print(f"✅ Status: {response.status_code}")
    print(f"📤 Sent User-Agent: '' (empty)")
    print(f"📥 Received User-Agent: '{received_ua}'")
    
    if received_ua == '':
        print("✅ SUCCESS: Explicit empty User-Agent working!")
    else:
        print(f"❌ FAILED: Expected empty, got '{received_ua}'")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 4: User-Agent via request_headers parameter
print("\n🔸 Test 4: User-Agent via request_headers parameter")
print("-" * 40)
url_ua = "URLParamAgent/1.0"
url_with_ua = f"{base_url}&request_headers[User-Agent]={url_ua.replace('/', '%2F')}"
try:
    response = requests.get(url_with_ua)
    data = response.json()
    received_ua = data.get('headers', {}).get('User-Agent', 'NOT FOUND')
    
    print(f"✅ Status: {response.status_code}")
    print(f"📤 URL param User-Agent: '{url_ua}'")
    print(f"📥 Received User-Agent: '{received_ua}'")
    
    if received_ua == url_ua:
        print("✅ SUCCESS: URL parameter User-Agent working!")
    else:
        print(f"❌ FAILED: Expected '{url_ua}', got '{received_ua}'")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)
print("🎯 Blank User-Agent test completed!")
print("=" * 60) 