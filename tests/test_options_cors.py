#!/usr/bin/env python3

import requests
import argparse
import os
import json

# Parse command line arguments or use environment variable
parser = argparse.ArgumentParser(description='Test OPTIONS request with CORS headers')
parser.add_argument('--port', type=int, 
                   default=int(os.environ.get('PROXY_PORT', 8080)),
                   help='Proxy server port (default: 8080, or PROXY_PORT env var)')
parser.add_argument('--mode', choices=['standalone', 'ha'], default='standalone',
                   help='Test mode: standalone proxy or Home Assistant integration (default: standalone)')
parser.add_argument('--instance', default='external-api-route',
                   help='HA integration instance name (default: external-api-route)')
args = parser.parse_args()

print("=" * 60)
print(f"OPTIONS REQUEST WITH CORS HEADERS TEST ({args.mode.upper()})")
print("=" * 60)

# Construct base URL based on mode
if args.mode == 'ha':
    # Get the authentication token from debug endpoint
    print("Getting authentication token from debug endpoint...")
    try:
        debug_response = requests.get(f"http://localhost:{args.port}/api/homie_proxy/debug", timeout=5)
        if debug_response.status_code == 200:
            debug_data = debug_response.json()
            instance_data = debug_data.get('instances', {}).get(args.instance, {})
            tokens = instance_data.get('tokens', [])
            if tokens:
                token = tokens[0]
                base_url = f"http://localhost:{args.port}/api/homie_proxy/{args.instance}"
                token_param = f"token={token}&"
                print(f"✅ Found authentication token: {token[:12]}...")
            else:
                print("❌ No tokens found in debug response")
                exit(1)
        else:
            print(f"❌ Debug endpoint returned status {debug_response.status_code}")
            exit(1)
    except Exception as e:
        print(f"❌ Failed to get token: {e}")
        exit(1)
else:
    base_url = f"http://localhost:{args.port}/default"
    token_param = "token=your-secret-token-here&"

print(f"\nTesting proxy at localhost:{args.port}")
print("-" * 50)

print("\n🔸 Test 1: OPTIONS with single CORS header")
print("-" * 40)

# Test 1: Basic OPTIONS request with CORS header
cors_url = f"{base_url}?{token_param}url=https://httpbin.org/anything&response_header[Access-Control-Allow-Origin]=*"

try:
    print("📥 Making OPTIONS request with CORS header...")
    response = requests.options(cors_url, timeout=10)
    
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Response Headers:")
    for header_name, header_value in response.headers.items():
        print(f"  {header_name}: {header_value}")
    
    # Check for our custom CORS header
    cors_header = response.headers.get('Access-Control-Allow-Origin')
    if cors_header:
        print(f"\n✅ SUCCESS: CORS header found!")
        print(f"   Access-Control-Allow-Origin: {cors_header}")
        
        if cors_header == '*':
            print("✅ CORS header has correct value: *")
        else:
            print(f"⚠️  CORS header has unexpected value: {cors_header}")
    else:
        print(f"\n❌ FAIL: CORS header 'Access-Control-Allow-Origin' not found")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n🔸 Test 2: OPTIONS with multiple CORS headers")
print("-" * 40)

# Test 2: OPTIONS with multiple CORS headers
multi_cors_url = (f"{base_url}?{token_param}url=https://httpbin.org/anything"
                  f"&response_header[Access-Control-Allow-Origin]=*"
                  f"&response_header[Access-Control-Allow-Methods]=GET,POST,PUT,DELETE,OPTIONS"
                  f"&response_header[Access-Control-Allow-Headers]=Content-Type,Authorization,X-Custom-Header"
                  f"&response_header[Access-Control-Max-Age]=86400")

try:
    print("📥 Making OPTIONS request with multiple CORS headers...")
    response = requests.options(multi_cors_url, timeout=10)
    
    print(f"✅ Status: {response.status_code}")
    
    # Check for multiple CORS headers
    cors_headers = {
        'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
        'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
        'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers'),
        'Access-Control-Max-Age': response.headers.get('Access-Control-Max-Age')
    }
    
    print(f"📥 CORS headers:")
    all_present = True
    for header, value in cors_headers.items():
        status = "✅" if value else "❌"
        print(f"   {status} {header}: {value or 'NOT FOUND'}")
        if not value:
            all_present = False
    
    if all_present:
        print("✅ SUCCESS: All CORS headers present!")
    else:
        print("❌ FAIL: Some CORS headers missing")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n🔸 Test 3: Compare OPTIONS vs GET with same CORS header")
print("-" * 40)

cors_test_url = f"{base_url}?{token_param}url=https://httpbin.org/anything&response_header[Access-Control-Allow-Origin]=*"

try:
    print("📥 Making GET request...")
    get_response = requests.get(cors_test_url, timeout=10)
    get_cors = get_response.headers.get('Access-Control-Allow-Origin')
    
    print("📥 Making OPTIONS request...")
    options_response = requests.options(cors_test_url, timeout=10)
    options_cors = options_response.headers.get('Access-Control-Allow-Origin')
    
    print(f"✅ GET Status: {get_response.status_code}")
    print(f"✅ OPTIONS Status: {options_response.status_code}")
    print(f"📥 GET CORS header: {get_cors or 'NOT FOUND'}")
    print(f"📥 OPTIONS CORS header: {options_cors or 'NOT FOUND'}")
    
    if get_cors == options_cors == '*':
        print("✅ SUCCESS: CORS header consistent between GET and OPTIONS!")
    else:
        print("❌ FAIL: CORS headers inconsistent between methods")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n🔸 Test 4: OPTIONS with custom response header")
print("-" * 40)

# Test 4: OPTIONS with custom non-CORS header
custom_url = f"{base_url}&url=https://httpbin.org/anything&response_header[X-Custom-Test]=OPTIONS-Test-Value"

try:
    print("📥 Making OPTIONS request with custom header...")
    response = requests.options(custom_url, timeout=10)
    
    print(f"✅ Status: {response.status_code}")
    
    custom_header = response.headers.get('X-Custom-Test')
    if custom_header:
        print(f"✅ SUCCESS: Custom header found!")
        print(f"   X-Custom-Test: {custom_header}")
        
        if custom_header == 'OPTIONS-Test-Value':
            print("✅ Custom header has correct value!")
        else:
            print(f"⚠️  Custom header has unexpected value: {custom_header}")
    else:
        print(f"❌ FAIL: Custom header 'X-Custom-Test' not found")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n💡 Usage Examples:")
print("   🔗 Single CORS header:")
print("      &response_header[Access-Control-Allow-Origin]=*")
print("   🔗 Multiple CORS headers:")
print("      &response_header[Access-Control-Allow-Origin]=*")
print("      &response_header[Access-Control-Allow-Methods]=GET,POST,OPTIONS")
print("   🔗 Custom headers:")
print("      &response_header[X-Custom-Header]=MyValue")

print("\n" + "=" * 60)
print("🎯 OPTIONS with CORS headers test completed!")
print("=" * 60) 