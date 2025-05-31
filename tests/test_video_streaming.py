#!/usr/bin/env python3

import requests
import time

print("=" * 60)
print("VIDEO STREAMING TEST - REVERSE PROXY")
print("=" * 60)

base_url = "http://localhost:8080/default?token=your-secret-token-here"

print("\n📋 TESTING VIDEO & LARGE FILE STREAMING:")
print("-" * 50)

# Test 1: Video content type (should not cache)
print("\n🎥 Test 1: Video content type detection")
video_url = f"{base_url}&url=https://httpbin.org/response-headers?Content-Type=video/mp4&Content-Length=50000000&cache=true"
try:
    print("📥 Making request with video/mp4 content type...")
    response = requests.get(video_url)
    
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    cache_header = response.headers.get('X-Cache', 'NOT FOUND')
    print(f"📥 X-Cache: {cache_header}")
    
    if cache_header == 'NOT FOUND':
        print("✅ Video content correctly NOT cached (streamed directly)")
    else:
        print(f"❌ Video content was cached: {cache_header}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Audio content type (should not cache)
print("\n🎵 Test 2: Audio content type detection")
audio_url = f"{base_url}&url=https://httpbin.org/response-headers?Content-Type=audio/mpeg&Content-Length=20000000&cache=true"
try:
    print("📥 Making request with audio/mpeg content type...")
    response = requests.get(audio_url)
    
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    cache_header = response.headers.get('X-Cache', 'NOT FOUND')
    print(f"📥 X-Cache: {cache_header}")
    
    if cache_header == 'NOT FOUND':
        print("✅ Audio content correctly NOT cached (streamed directly)")
    else:
        print(f"❌ Audio content was cached: {cache_header}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Large file size (should not cache due to size)
print("\n📁 Test 3: Large file size detection")
large_file_url = f"{base_url}&url=https://httpbin.org/bytes/15000000&cache=true"  # 15MB
try:
    print("📥 Making request for 15MB file (exceeds 10MB cache limit)...")
    start_time = time.time()
    
    response = requests.get(large_file_url, stream=True)
    
    # Read the response in chunks to measure streaming
    total_bytes = 0
    chunk_count = 0
    for chunk in response.iter_content(chunk_size=8192):
        if chunk:
            total_bytes += len(chunk)
            chunk_count += 1
            # Stop after reading 1MB to avoid long download
            if total_bytes > 1024 * 1024:
                break
    
    end_time = time.time()
    
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    print(f"📥 Content-Length: {response.headers.get('Content-Length', 'N/A')} bytes")
    cache_header = response.headers.get('X-Cache', 'NOT FOUND')
    print(f"📥 X-Cache: {cache_header}")
    print(f"📊 Streamed {total_bytes} bytes in {chunk_count} chunks")
    print(f"⏱️  Time: {(end_time - start_time):.3f} seconds")
    
    if cache_header == 'NOT FOUND':
        print("✅ Large file correctly NOT cached (streamed directly)")
    else:
        print(f"❌ Large file was cached: {cache_header}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 4: Small file (should cache)
print("\n📄 Test 4: Small file (should cache)")
small_file_url = f"{base_url}&url=https://httpbin.org/bytes/5000&cache=true"  # 5KB
try:
    print("📥 Making request for 5KB file (should cache)...")
    
    # First request
    response1 = requests.get(small_file_url)
    cache_header1 = response1.headers.get('X-Cache', 'NOT FOUND')
    print(f"✅ First request - Status: {response1.status_code}")
    print(f"📥 First request - X-Cache: {cache_header1}")
    
    # Second request (should hit cache)
    response2 = requests.get(small_file_url)
    cache_header2 = response2.headers.get('X-Cache', 'NOT FOUND')
    print(f"✅ Second request - Status: {response2.status_code}")
    print(f"📥 Second request - X-Cache: {cache_header2}")
    
    if 'DISK' in cache_header2:
        print("✅ Small file correctly cached")
    else:
        print(f"❌ Small file not cached: {cache_header2}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 5: Demonstrate memory efficiency
print("\n💾 Test 5: Memory efficiency summary")
print("📊 Streaming behavior based on content:")
print("   🎥 video/* → Streamed directly (no caching)")
print("   🎵 audio/* → Streamed directly (no caching)")
print("   📁 Files >10MB → Streamed directly (no caching)")
print("   📄 Files <10MB → Cached normally (fast repeat access)")
print("   🔄 8KB chunks → Constant memory usage")

print("\n" + "=" * 60)
print("🎯 Video streaming test completed!")
print("=" * 60) 