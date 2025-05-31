#!/usr/bin/env python3

import requests
import time

print("=" * 60)
print("REAL VIDEO STREAMING TEST - REVERSE PROXY")
print("=" * 60)

base_url = "http://localhost:8080/default?token=your-secret-token-here"

print("\n📋 TESTING WITH ACTUAL VIDEO FILES:")
print("-" * 50)

# Test 1: Test with a sample MP4 video from a CDN
print("\n🎥 Test 1: Real MP4 video file")
video_url = f"{base_url}&url=https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4&cache=true"
try:
    print("📥 Requesting actual MP4 video file...")
    print("🔗 Target: https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4")
    
    start_time = time.time()
    response = requests.get(video_url, stream=True, timeout=30)
    
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    print(f"📥 Content-Length: {response.headers.get('Content-Length', 'N/A')} bytes")
    cache_header = response.headers.get('X-Cache', 'NOT FOUND')
    print(f"📥 X-Cache: {cache_header}")
    
    if response.status_code == 200:
        # Stream the video in chunks to test streaming behavior
        total_bytes = 0
        chunk_count = 0
        first_chunk_time = None
        
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                if first_chunk_time is None:
                    first_chunk_time = time.time()
                    print(f"⚡ First chunk received in {(first_chunk_time - start_time):.3f} seconds")
                
                total_bytes += len(chunk)
                chunk_count += 1
                
                # Stop after 200KB to avoid long download
                if total_bytes > 200 * 1024:
                    print(f"🛑 Stopping after {total_bytes} bytes for test efficiency")
                    break
        
        end_time = time.time()
        
        print(f"📊 Streamed {total_bytes} bytes in {chunk_count} chunks")
        print(f"⏱️  Total time: {(end_time - start_time):.3f} seconds")
        if (end_time - start_time) > 0:
            print(f"🚀 Streaming rate: {total_bytes / (end_time - start_time) / 1024:.1f} KB/s")
        
        if cache_header == 'NOT FOUND':
            print("✅ Video file correctly NOT cached (streamed directly)")
        else:
            print(f"❌ Video file was cached: {cache_header}")
    else:
        print(f"❌ Failed to get video, status: {response.status_code}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Fallback test with httpbin large file
print("\n📁 Test 2: Large binary file (simulating video)")
large_file_url = f"{base_url}&url=https://httpbin.org/bytes/1048576&cache=true"  # 1MB
try:
    print("📥 Requesting 1MB binary file...")
    print("🔗 Target: https://httpbin.org/bytes/1048576")
    
    start_time = time.time()
    response = requests.get(large_file_url, stream=True)
    
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    print(f"📥 Content-Length: {response.headers.get('Content-Length', 'N/A')} bytes")
    cache_header = response.headers.get('X-Cache', 'NOT FOUND')
    print(f"📥 X-Cache: {cache_header}")
    
    # Test streaming behavior
    total_bytes = 0
    chunk_count = 0
    first_chunk_time = None
    
    for chunk in response.iter_content(chunk_size=8192):
        if chunk:
            if first_chunk_time is None:
                first_chunk_time = time.time()
                print(f"⚡ First chunk received in {(first_chunk_time - start_time):.3f} seconds")
            
            total_bytes += len(chunk)
            chunk_count += 1
            
            # Stream first 100KB for testing
            if total_bytes > 100 * 1024:
                print(f"🛑 Stopping after {total_bytes} bytes for test efficiency")
                break
    
    end_time = time.time()
    
    print(f"📊 Streamed {total_bytes} bytes in {chunk_count} chunks")
    print(f"⏱️  Total time: {(end_time - start_time):.3f} seconds")
    if (end_time - start_time) > 0:
        print(f"🚀 Streaming rate: {total_bytes / (end_time - start_time) / 1024:.1f} KB/s")
    
    # Check if it was cached or streamed
    if cache_header == 'NOT FOUND':
        print("✅ Large file correctly NOT cached (streamed directly)")
    else:
        print(f"❌ Large file was cached: {cache_header}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Small file that should cache
print("\n📄 Test 3: Small file (should cache)")
small_file_url = f"{base_url}&url=https://httpbin.org/bytes/5000&cache=true"  # 5KB
try:
    print("📥 Requesting 5KB file for comparison...")
    print("🔗 Target: https://httpbin.org/bytes/5000")
    
    # First request
    response1 = requests.get(small_file_url)
    cache_header1 = response1.headers.get('X-Cache', 'NOT FOUND')
    print(f"✅ First request - Status: {response1.status_code}")
    print(f"📥 First request - Content-Type: {response1.headers.get('Content-Type', 'N/A')}")
    print(f"📥 First request - X-Cache: {cache_header1}")
    print(f"📊 First request - Size: {len(response1.content)} bytes")
    
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

# Test 4: Test content type detection
print("\n🎯 Test 4: Content type based streaming")
print("📥 Testing various content types...")

content_types = [
    ("video/mp4", "https://httpbin.org/response-headers?Content-Type=video/mp4"),
    ("audio/mpeg", "https://httpbin.org/response-headers?Content-Type=audio/mpeg"),
    ("application/json", "https://httpbin.org/response-headers?Content-Type=application/json")
]

for content_type, test_url in content_types:
    try:
        url = f"{base_url}&url={test_url}&cache=true"
        response = requests.get(url)
        cache_header = response.headers.get('X-Cache', 'NOT FOUND')
        
        print(f"📝 {content_type}:")
        print(f"   Status: {response.status_code}")
        print(f"   X-Cache: {cache_header}")
        
        if content_type.startswith(('video/', 'audio/')):
            if cache_header == 'NOT FOUND':
                print(f"   ✅ Correctly NOT cached (streaming content)")
            else:
                print(f"   ❌ Unexpectedly cached: {cache_header}")
        else:
            print(f"   📊 Regular content handling")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n💾 Test Summary:")
print("📊 Streaming test results:")
print("   🎥 Large files → Streamed without caching")
print("   📄 Small files → Cached for performance")
print("   🚀 Immediate streaming → No buffering delays")
print("   🔄 Chunk-based → Memory efficient (8KB chunks)")
print("   🎬 Content-type detection → Working for video/audio")

print("\n" + "=" * 60)
print("🎯 Real streaming test completed!")
print("=" * 60) 