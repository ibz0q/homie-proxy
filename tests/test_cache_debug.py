#!/usr/bin/env python3

import requests
import time

print("=" * 60)
print("CACHE DEBUG TEST - REVERSE PROXY")
print("=" * 60)

base_url = "http://localhost:8080/default?token=your-secret-token-here"

# Test 1: Simple JSON caching (should definitely work)
print("\n📄 Test 1: JSON file caching")
json_url = f"{base_url}&url=https://httpbin.org/json&cache=true"
try:
    print("📥 First request to JSON endpoint...")
    response1 = requests.get(json_url)
    
    print(f"✅ First - Status: {response1.status_code}")
    print(f"📥 First - Content-Type: {response1.headers.get('Content-Type', 'N/A')}")
    print(f"📥 First - Content-Length: {response1.headers.get('Content-Length', 'N/A')}")
    cache_header1 = response1.headers.get('X-Cache', 'NOT FOUND')
    print(f"📥 First - X-Cache: {cache_header1}")
    print(f"📊 First - Size: {len(response1.content)} bytes")
    
    print("\n📥 Second request to same JSON endpoint...")
    response2 = requests.get(json_url)
    
    print(f"✅ Second - Status: {response2.status_code}")
    cache_header2 = response2.headers.get('X-Cache', 'NOT FOUND')
    print(f"📥 Second - X-Cache: {cache_header2}")
    print(f"📊 Second - Size: {len(response2.content)} bytes")
    
    if 'DISK' in cache_header2:
        print("✅ JSON file correctly cached!")
    else:
        print(f"❌ JSON file not cached: {cache_header2}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Very small binary file
print("\n📄 Test 2: Very small binary file (1KB)")
small_binary_url = f"{base_url}&url=https://httpbin.org/bytes/1024&cache=true"
try:
    print("📥 First request to 1KB binary...")
    response1 = requests.get(small_binary_url)
    
    print(f"✅ First - Status: {response1.status_code}")
    print(f"📥 First - Content-Type: {response1.headers.get('Content-Type', 'N/A')}")
    print(f"📥 First - Content-Length: {response1.headers.get('Content-Length', 'N/A')}")
    cache_header1 = response1.headers.get('X-Cache', 'NOT FOUND')
    print(f"📥 First - X-Cache: {cache_header1}")
    print(f"📊 First - Size: {len(response1.content)} bytes")
    
    print("\n📥 Second request to same 1KB binary...")
    response2 = requests.get(small_binary_url)
    
    print(f"✅ Second - Status: {response2.status_code}")
    cache_header2 = response2.headers.get('X-Cache', 'NOT FOUND')
    print(f"📥 Second - X-Cache: {cache_header2}")
    print(f"📊 Second - Size: {len(response2.content)} bytes")
    
    if 'DISK' in cache_header2:
        print("✅ Small binary file correctly cached!")
    else:
        print(f"❌ Small binary file not cached: {cache_header2}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Check cache directory
print("\n📁 Test 3: Cache directory check")
import os
cache_dir = "cache"
if os.path.exists(cache_dir):
    cache_files = [f for f in os.listdir(cache_dir) if f.endswith('.cache')]
    print(f"✅ Cache directory exists: {cache_dir}")
    print(f"📁 Cache files found: {len(cache_files)}")
    
    if cache_files:
        print("📄 Cache files:")
        for i, filename in enumerate(cache_files[:5]):
            filepath = os.path.join(cache_dir, filename)
            size = os.path.getsize(filepath)
            print(f"   {i+1}. {filename} ({size} bytes)")
    else:
        print("❌ No cache files found")
else:
    print(f"❌ Cache directory not found: {cache_dir}")

print("\n" + "=" * 60)
print("🎯 Cache debug test completed!")
print("=" * 60) 