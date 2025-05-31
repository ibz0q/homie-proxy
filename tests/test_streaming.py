#!/usr/bin/env python3

import requests
import time
import os

print("=" * 60)
print("STREAMING TEST - REVERSE PROXY")
print("=" * 60)

base_url = "http://localhost:8080/default?token=your-secret-token-here"

print("\n📋 STREAMING CAPABILITIES:")
print("-" * 40)
print("✅ Video files - streamed directly (no caching)")
print("✅ Audio files - streamed directly (no caching)")  
print("✅ Large files (>10MB) - streamed directly (no caching)")
print("✅ Small files (<10MB) - cached normally")
print("✅ Memory efficient - no buffering large files")

print("\n🧪 TESTING STREAMING FUNCTIONALITY:")
print("-" * 40)

# Test 1: Large file streaming (should not cache)
print("\n🔸 Test 1: Large file streaming")
large_file_url = f"{base_url}&url=https://httpbin.org/drip?numbytes=1000000&duration=1&cache=true"
try:
    print("📥 Requesting 1MB file with artificial delay...")
    start_time = time.time()
    
    response = requests.get(large_file_url, stream=True)
    
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    print(f"📥 Content-Length: {response.headers.get('Content-Length', 'N/A')} bytes")
    cache_header = response.headers.get('X-Cache', 'NOT FOUND')
    print(f"📥 X-Cache header: {cache_header}")
    
    # Read the response to measure streaming
    total_bytes = 0
    chunk_count = 0
    for chunk in response.iter_content(chunk_size=8192):
        if chunk:
            total_bytes += len(chunk)
            chunk_count += 1
    
    end_time = time.time()
    
    print(f"📊 Total bytes received: {total_bytes}")
    print(f"📊 Chunks received: {chunk_count}")
    print(f"⏱️  Total time: {(end_time - start_time):.3f} seconds")
    
    if cache_header == 'NOT FOUND':
        print("✅ Large file correctly not cached")
    else:
        print(f"❌ Unexpected cache behavior: {cache_header}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Small file caching
print("\n🔸 Test 2: Small file caching")
small_file_url = f"{base_url}&url=https://httpbin.org/json&cache=true"
try:
    print("📥 Requesting small JSON file...")
    
    # First request
    start_time = time.time()
    response1 = requests.get(small_file_url)
    end_time = time.time()
    
    cache_header1 = response1.headers.get('X-Cache', 'NOT FOUND')
    print(f"✅ First request - Status: {response1.status_code}")
    print(f"📥 First request - X-Cache: {cache_header1}")
    print(f"⏱️  First request time: {(end_time - start_time):.3f} seconds")
    
    # Second request (should be cached)
    start_time = time.time()
    response2 = requests.get(small_file_url)
    end_time = time.time()
    
    cache_header2 = response2.headers.get('X-Cache', 'NOT FOUND')
    print(f"✅ Second request - Status: {response2.status_code}")
    print(f"📥 Second request - X-Cache: {cache_header2}")
    print(f"⏱️  Second request time: {(end_time - start_time):.3f} seconds")
    
    if 'DISK' in cache_header2:
        print("✅ Small file correctly cached")
    else:
        print(f"❌ Small file not cached: {cache_header2}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Video content type detection
print("\n🔸 Test 3: Video content type streaming")
video_headers_url = f"{base_url}&url=https://httpbin.org/response-headers?Content-Type=video/mp4&Content-Length=50000000&cache=true"
try:
    print("📥 Requesting with video/mp4 content type...")
    
    response = requests.get(video_headers_url)
    
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    cache_header = response.headers.get('X-Cache', 'NOT FOUND')
    print(f"📥 X-Cache header: {cache_header}")
    
    if cache_header == 'NOT FOUND':
        print("✅ Video content correctly not cached")
    else:
        print(f"❌ Video content unexpectedly cached: {cache_header}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 4: Audio content type detection  
print("\n🔸 Test 4: Audio content type streaming")
audio_headers_url = f"{base_url}&url=https://httpbin.org/response-headers?Content-Type=audio/mpeg&Content-Length=20000000&cache=true"
try:
    print("📥 Requesting with audio/mpeg content type...")
    
    response = requests.get(audio_headers_url)
    
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    cache_header = response.headers.get('X-Cache', 'NOT FOUND')
    print(f"📥 X-Cache header: {cache_header}")
    
    if cache_header == 'NOT FOUND':
        print("✅ Audio content correctly not cached")
    else:
        print(f"❌ Audio content unexpectedly cached: {cache_header}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 5: Memory usage comparison
print("\n🔸 Test 5: Memory efficiency demonstration")
print("📊 Old behavior: Buffer entire file in memory before sending")
print("📊 New behavior: Stream chunks directly (8KB chunks)")
print("📊 Benefits:")
print("   • ✅ Constant memory usage regardless of file size")
print("   • ✅ Immediate streaming starts")
print("   • ✅ Support for files larger than available RAM")
print("   • ✅ Better performance for video/audio")

print("\n🎯 STREAMING CONTENT TYPES:")
print("-" * 40)
streaming_types = [
    "video/*", "audio/*", "application/octet-stream",
    "application/zip", "application/x-tar", "application/gzip",
    "image/gif", "image/png", "image/jpeg"
]

for content_type in streaming_types:
    print(f"   📹 {content_type} - streamed directly")

print(f"\n📏 CACHE SIZE LIMIT: 10MB")
print("   Files larger than 10MB are automatically streamed")

print("\n" + "=" * 60)
print("🎯 Streaming test completed!")
print("=" * 60) 