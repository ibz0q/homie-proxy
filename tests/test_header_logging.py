#!/usr/bin/env python3

import requests

print("=" * 60)
print("REQUEST HEADER LOGGING TEST - REVERSE PROXY")
print("=" * 60)

base_url = "http://localhost:8080/default?token=your-secret-token-here"

print("\n📋 Testing request header logging functionality")
print("-" * 50)

print("\n🧪 Test 1: Simple GET request with custom headers")
simple_url = f"{base_url}&url=https://httpbin.org/headers&request_headers[X-Custom-Header]=MyValue&request_headers[X-Test-ID]=12345"

try:
    print("📥 Making simple GET request...")
    print("🔗 Target: https://httpbin.org/headers")
    print("📤 Custom headers: X-Custom-Header=MyValue, X-Test-ID=12345")
    
    response = requests.get(simple_url)
    
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    
    if response.status_code == 200:
        print("✅ SUCCESS: Check server console for detailed request header logging")
        print("📊 Response preview:")
        try:
            import json
            response_data = response.json()
            print(f"   Headers sent to target: {len(response_data.get('headers', {}))} headers")
        except:
            print(f"   Response size: {len(response.content)} bytes")
    
except Exception as e:
    print(f"❌ Error: {e}")

print("\n🧪 Test 2: POST request with body and headers")
post_url = f"{base_url}&url=https://httpbin.org/post&request_headers[Content-Type]=application/json&request_headers[Authorization]=Bearer test-token"

try:
    print("📥 Making POST request with body...")
    print("🔗 Target: https://httpbin.org/post")
    print("📤 Custom headers: Content-Type=application/json, Authorization=Bearer test-token")
    
    post_data = '{"message": "Hello from proxy", "test": true}'
    response = requests.post(post_url, data=post_data)
    
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    
    if response.status_code == 200:
        print("✅ SUCCESS: Check server console for request body and header logging")
    
except Exception as e:
    print(f"❌ Error: {e}")

print("\n🧪 Test 3: Request with User-Agent override")
ua_url = f"{base_url}&url=https://httpbin.org/user-agent&request_headers[User-Agent]=Custom-Proxy-Client/1.0"

try:
    print("📥 Making request with custom User-Agent...")
    print("🔗 Target: https://httpbin.org/user-agent")
    print("📤 Custom User-Agent: Custom-Proxy-Client/1.0")
    
    response = requests.get(ua_url)
    
    print(f"✅ Status: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ SUCCESS: Check server console for User-Agent logging")
        print("📊 Server response:")
        try:
            import json
            response_data = response.json()
            print(f"   User-Agent seen by target: {response_data.get('user-agent', 'NOT FOUND')}")
        except:
            print(f"   Response size: {len(response.content)} bytes")
    
except Exception as e:
    print(f"❌ Error: {e}")

print("\n🧪 Test 4: Request with many headers (logging truncation test)")
many_headers_url = f"{base_url}&url=https://httpbin.org/headers"
many_headers_url += "&request_headers[X-Long-Header]=" + "A" * 150  # Very long header value
many_headers_url += "&request_headers[X-Short]=value"
many_headers_url += "&request_headers[X-Another]=test"

try:
    print("📥 Making request with many headers including very long one...")
    print("🔗 Target: https://httpbin.org/headers")
    print("📤 Testing header value truncation for very long headers")
    
    response = requests.get(many_headers_url)
    
    print(f"✅ Status: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ SUCCESS: Check server console for header truncation behavior")
    
except Exception as e:
    print(f"❌ Error: {e}")

print("\n💡 What to look for in server console:")
print("   📤 'Request to [URL]' - Shows target URL")
print("   📤 'Method: [METHOD]' - Shows HTTP method")
print("   📤 'Request headers sent to target:' - Lists all headers")
print("   📤 '  [Header-Name]: [Value]' - Individual header entries")
print("   📤 'Request body: [size] bytes' - Shows body size and preview")
print("   📤 Long header values are truncated with '...'")

print("\n" + "=" * 60)
print("🎯 Request header logging test completed!")
print("=" * 60) 