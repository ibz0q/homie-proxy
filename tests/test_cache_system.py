#!/usr/bin/env python3

import requests
import json
import time
import os

print("=" * 60)
print("CACHE SYSTEM TEST - REVERSE PROXY")
print("=" * 60)

base_url = "http://localhost:8080/default?token=your-secret-token-here"

print("\n📋 HOW TO USE CACHING:")
print("-" * 40)
print("Add &cache=true to any URL to enable caching")
print("Example:")
print(f"{base_url}&url=https://httpbin.org/get&cache=true")

print("\n🧪 TESTING CACHE FUNCTIONALITY:")
print("-" * 40)

# Test 1: First request (should be MISS)
print("\n🔸 Test 1: First request (cache MISS expected)")
cache_url = f"{base_url}&url=https://httpbin.org/get&cache=true"
try:
    start_time = time.time()
    response1 = requests.get(cache_url)
    end_time = time.time()
    
    print(f"✅ Status: {response1.status_code}")
    print(f"⏱️  Response time: {(end_time - start_time):.3f} seconds")
    cache_header = response1.headers.get('X-Cache', 'NOT FOUND')
    print(f"📥 X-Cache header: {cache_header}")
    
    if 'MISS' in cache_header or cache_header == 'NOT FOUND':
        print("✅ First request correctly shows cache MISS")
    else:
        print(f"❌ Expected cache MISS, got: {cache_header}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Second request immediately (should be HIT)
print("\n🔸 Test 2: Second request (cache HIT expected)")
try:
    start_time = time.time()
    response2 = requests.get(cache_url)
    end_time = time.time()
    
    print(f"✅ Status: {response2.status_code}")
    print(f"⏱️  Response time: {(end_time - start_time):.3f} seconds")
    cache_header = response2.headers.get('X-Cache', 'NOT FOUND')
    print(f"📥 X-Cache header: {cache_header}")
    
    if 'HIT' in cache_header or 'DISK' in cache_header:
        print("✅ Second request correctly shows cache HIT")
    else:
        print(f"❌ Expected cache HIT, got: {cache_header}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Different URL (should be MISS)
print("\n🔸 Test 3: Different URL (cache MISS expected)")
different_url = f"{base_url}&url=https://httpbin.org/uuid&cache=true"
try:
    response3 = requests.get(different_url)
    cache_header = response3.headers.get('X-Cache', 'NOT FOUND')
    print(f"✅ Status: {response3.status_code}")
    print(f"📥 X-Cache header: {cache_header}")
    
    if 'MISS' in cache_header or cache_header == 'NOT FOUND':
        print("✅ Different URL correctly shows cache MISS")
    else:
        print(f"❌ Expected cache MISS for different URL, got: {cache_header}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 4: POST request with body (test cache key generation)
print("\n🔸 Test 4: POST request with body")
post_url = f"{base_url}&url=https://httpbin.org/post&cache=true"
test_data = {"test": "cache_with_body", "timestamp": time.time()}

try:
    # First POST
    response4a = requests.post(post_url, json=test_data)
    cache_header4a = response4a.headers.get('X-Cache', 'NOT FOUND')
    print(f"✅ First POST Status: {response4a.status_code}")
    print(f"📥 First POST X-Cache: {cache_header4a}")
    
    # Second POST with same data
    response4b = requests.post(post_url, json=test_data)
    cache_header4b = response4b.headers.get('X-Cache', 'NOT FOUND')
    print(f"✅ Second POST Status: {response4b.status_code}")
    print(f"📥 Second POST X-Cache: {cache_header4b}")
    
    if 'HIT' in cache_header4b or 'DISK' in cache_header4b:
        print("✅ POST caching working correctly")
    else:
        print(f"❌ POST caching may not be working: {cache_header4b}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 5: Check cache directory
print("\n🔸 Test 5: Cache directory inspection")
cache_dir = "cache"
if os.path.exists(cache_dir):
    cache_files = [f for f in os.listdir(cache_dir) if f.endswith('.cache')]
    print(f"✅ Cache directory exists: {cache_dir}")
    print(f"📁 Cache files found: {len(cache_files)}")
    
    if cache_files:
        print("📄 Cache files:")
        for i, filename in enumerate(cache_files[:5]):  # Show first 5
            filepath = os.path.join(cache_dir, filename)
            size = os.path.getsize(filepath)
            print(f"   {i+1}. {filename} ({size} bytes)")
        if len(cache_files) > 5:
            print(f"   ... and {len(cache_files) - 5} more files")
    else:
        print("❌ No cache files found")
else:
    print(f"❌ Cache directory not found: {cache_dir}")

# Test 6: Cache without cache=true (should not cache)
print("\n🔸 Test 6: Request without cache=true (no caching)")
no_cache_url = f"{base_url}&url=https://httpbin.org/get"
try:
    response6 = requests.get(no_cache_url)
    cache_header = response6.headers.get('X-Cache', 'NOT FOUND')
    print(f"✅ Status: {response6.status_code}")
    print(f"📥 X-Cache header: {cache_header}")
    
    if cache_header == 'NOT FOUND':
        print("✅ No caching when cache=true not specified")
    else:
        print(f"❌ Unexpected cache header: {cache_header}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 7: Cache statistics
print("\n🔸 Test 7: Show cache statistics")
if os.path.exists(cache_dir):
    total_size = 0
    file_count = 0
    
    for filename in os.listdir(cache_dir):
        if filename.endswith('.cache'):
            filepath = os.path.join(cache_dir, filename)
            try:
                size = os.path.getsize(filepath)
                total_size += size
                file_count += 1
            except:
                pass
    
    print(f"📊 Cache Statistics:")
    print(f"   Total files: {file_count}")
    print(f"   Total size: {total_size} bytes ({total_size/1024:.2f} KB)")
    print(f"   Average file size: {total_size/file_count if file_count > 0 else 0:.2f} bytes")

print("\n" + "=" * 60)
print("🎯 Cache system test completed!")
print("=" * 60) 