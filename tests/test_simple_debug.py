#!/usr/bin/env python3

import requests
import time

print("=" * 60)
print("SIMPLE DEBUG TEST - REVERSE PROXY")
print("=" * 60)

base_url = "http://localhost:8080/default?token=your-secret-token-here"

# Test 1: Simple working request
print("\n🔸 Test 1: Simple JSON request (working)")
try:
    url = f"{base_url}&url=https://httpbin.org/json"
    print(f"URL: {url}")
    response = requests.get(url, timeout=10)
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    print(f"📥 Content-Length: {response.headers.get('Content-Length', 'N/A')}")
    print(f"📊 Response size: {len(response.content)} bytes")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Test video content type detection
print("\n🔸 Test 2: Video content type test")
try:
    url = f"{base_url}&url=https://httpbin.org/response-headers?Content-Type=video/mp4"
    print(f"URL: {url}")
    response = requests.get(url, timeout=10)
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    
    # Check the actual response
    try:
        data = response.json()
        print(f"📊 Response: {data}")
    except:
        print(f"📊 Response text: {response.text[:200]}...")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Small file test
print("\n🔸 Test 3: Small file test")
try:
    url = f"{base_url}&url=https://httpbin.org/bytes/1024"  # 1KB
    print(f"URL: {url}")
    response = requests.get(url, timeout=10)
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    print(f"📥 Content-Length: {response.headers.get('Content-Length', 'N/A')}")
    print(f"📊 Actual size: {len(response.content)} bytes")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 4: Test what happens with the problematic drip URL
print("\n🔸 Test 4: Drip URL test")
try:
    url = f"{base_url}&url=https://httpbin.org/drip?numbytes=100&duration=1"  # Much smaller
    print(f"URL: {url}")
    print("Making request...")
    response = requests.get(url, timeout=15)  # Longer timeout
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    print(f"📊 Actual size: {len(response.content)} bytes")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 60)
print("🎯 Debug test completed!")
print("=" * 60) 