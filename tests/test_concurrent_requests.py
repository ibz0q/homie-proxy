#!/usr/bin/env python3

import requests
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import os

# Parse command line arguments or use environment variable
parser = argparse.ArgumentParser(description='Test reverse proxy concurrent requests')
parser.add_argument('--port', type=int, 
                   default=int(os.environ.get('PROXY_PORT', 8080)),
                   help='Proxy server port (default: 8080, or PROXY_PORT env var)')
args = parser.parse_args()

print("=" * 60)
print("CONCURRENT REQUESTS TEST - REVERSE PROXY")
print("=" * 60)

base_url = f"http://localhost:{args.port}/default?token=your-secret-token-here"

print(f"\nTesting proxy at localhost:{args.port}")
print("-" * 50)

def make_request(url, request_id, test_name):
    """Make a request and measure timing"""
    start_time = time.time()
    try:
        print(f"[{request_id}] Starting {test_name}...")
        response = requests.get(url, stream=True, timeout=30)
        
        # For large files, read some chunks to test streaming
        total_bytes = 0
        chunk_count = 0
        first_chunk_time = None
        
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                if first_chunk_time is None:
                    first_chunk_time = time.time()
                    first_byte_latency = first_chunk_time - start_time
                    print(f"[{request_id}] First chunk received in {first_byte_latency:.3f}s")
                
                total_bytes += len(chunk)
                chunk_count += 1
                
                # For testing, only read first 100KB to avoid long downloads
                if total_bytes > 100 * 1024:
                    break
        
        end_time = time.time()
        total_time = end_time - start_time
        
        print(f"[{request_id}] Completed {test_name}")
        print(f"[{request_id}] Status: {response.status_code}")
        print(f"[{request_id}] Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        print(f"[{request_id}] Streamed: {total_bytes} bytes in {chunk_count} chunks")
        print(f"[{request_id}] Total time: {total_time:.3f}s")
        
        return {
            'request_id': request_id,
            'test_name': test_name,
            'status_code': response.status_code,
            'content_type': response.headers.get('Content-Type', 'N/A'),
            'bytes_received': total_bytes,
            'total_time': total_time,
            'first_byte_latency': first_byte_latency if first_chunk_time else None
        }
        
    except Exception as e:
        end_time = time.time()
        total_time = end_time - start_time
        print(f"[{request_id}] Error in {test_name}: {e}")
        return {
            'request_id': request_id,
            'test_name': test_name,
            'error': str(e),
            'total_time': total_time
        }

# Test 1: Concurrent large file requests
print("\nTest 1: Concurrent large file requests")
print("-" * 50)

test_urls = [
    (f"{base_url}&url=https://httpbin.org/drip?numbytes=1000000&duration=2&skip_tls_checks=all", "Large file 1"),
    (f"{base_url}&url=https://httpbin.org/drip?numbytes=500000&duration=1&skip_tls_checks=all", "Large file 2"),
    (f"{base_url}&url=https://httpbin.org/bytes/200000&skip_tls_checks=all", "Binary file"),
]

# Run requests concurrently
print("Starting 3 concurrent requests...")
overall_start = time.time()

with ThreadPoolExecutor(max_workers=3) as executor:
    futures = []
    for i, (url, name) in enumerate(test_urls, 1):
        future = executor.submit(make_request, url, f"REQ{i}", name)
        futures.append(future)
    
    results = []
    for future in as_completed(futures):
        result = future.result()
        results.append(result)

overall_end = time.time()
overall_time = overall_end - overall_start

print(f"\nTest 1 Results:")
print(f"Overall test time: {overall_time:.3f}s")
print("-" * 30)

for result in sorted(results, key=lambda x: x['request_id']):
    if 'error' in result:
        print(f"{result['request_id']}: ERROR - {result['error']} (took {result['total_time']:.3f}s)")
    else:
        print(f"{result['request_id']}: {result['test_name']}")
        print(f"  Status: {result['status_code']}")
        print(f"  Data: {result['bytes_received']} bytes")
        print(f"  Time: {result['total_time']:.3f}s")
        if result['first_byte_latency']:
            print(f"  First byte: {result['first_byte_latency']:.3f}s")

# Test 2: Concurrent video file requests (your actual use case)
print(f"\nTest 2: Concurrent video requests (your use case)")
print("-" * 50)

video_urls = [
    (f"{base_url}&url=https://sylvan.apple.com/Videos/Y003_C009_SDR_2K_AVC.mov&skip_tls_checks=all&cache=true", "Apple Video"),
    (f"{base_url}&url=https://httpbin.org/response-headers?Content-Type=video/mp4&Content-Length=50000000&skip_tls_checks=all", "Video headers test"),
]

print("Starting 2 concurrent video requests...")
video_start = time.time()

with ThreadPoolExecutor(max_workers=2) as executor:
    futures = []
    for i, (url, name) in enumerate(video_urls, 1):
        future = executor.submit(make_request, url, f"VID{i}", name)
        futures.append(future)
    
    video_results = []
    for future in as_completed(futures):
        result = future.result()
        video_results.append(result)

video_end = time.time()
video_time = video_end - video_start

print(f"\nTest 2 Results:")
print(f"Overall video test time: {video_time:.3f}s")
print("-" * 30)

for result in sorted(video_results, key=lambda x: x['request_id']):
    if 'error' in result:
        print(f"{result['request_id']}: ERROR - {result['error']} (took {result['total_time']:.3f}s)")
    else:
        print(f"{result['request_id']}: {result['test_name']}")
        print(f"  Status: {result['status_code']}")
        print(f"  Content-Type: {result['content_type']}")
        print(f"  Data: {result['bytes_received']} bytes")
        print(f"  Time: {result['total_time']:.3f}s")
        if result['first_byte_latency']:
            print(f"  First byte: {result['first_byte_latency']:.3f}s")

# Test 3: Mixed concurrent requests
print(f"\nTest 3: Mixed request types")
print("-" * 50)

mixed_urls = [
    (f"{base_url}&url=https://httpbin.org/json&cache=true", "JSON API"),
    (f"{base_url}&url=https://httpbin.org/headers&cache=true", "Headers"),
    (f"{base_url}&url=https://httpbin.org/uuid", "UUID"),
    (f"{base_url}&url=https://httpbin.org/bytes/50000", "50KB file"),
]

print("Starting 4 concurrent mixed requests...")
mixed_start = time.time()

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = []
    for i, (url, name) in enumerate(mixed_urls, 1):
        future = executor.submit(make_request, url, f"MIX{i}", name)
        futures.append(future)
    
    mixed_results = []
    for future in as_completed(futures):
        result = future.result()
        mixed_results.append(result)

mixed_end = time.time()
mixed_time = mixed_end - mixed_start

print(f"\nTest 3 Results:")
print(f"Overall mixed test time: {mixed_time:.3f}s")
print("-" * 30)

for result in sorted(mixed_results, key=lambda x: x['request_id']):
    if 'error' in result:
        print(f"{result['request_id']}: ERROR - {result['error']} (took {result['total_time']:.3f}s)")
    else:
        print(f"{result['request_id']}: {result['test_name']}")
        print(f"  Status: {result['status_code']}")
        print(f"  Time: {result['total_time']:.3f}s")

print(f"\n" + "=" * 60)
print("CONCURRENCY ANALYSIS")
print("=" * 60)

print("🎯 What to look for:")
print("✅ All requests should start immediately (no waiting)")
print("✅ First byte latency should be similar across concurrent requests")
print("✅ Large files should not block small API requests")
print("✅ Video files should stream concurrently without hanging")

print("\n💡 Before the fix:")
print("❌ Second request would hang until first completes")
print("❌ Large files would block all other requests")
print("❌ Video streaming would be sequential, not concurrent")

print("\n💡 After the fix (ThreadingHTTPServer):")
print("✅ Multiple requests start simultaneously")
print("✅ Each request gets its own thread")
print("✅ Large file streaming doesn't block other requests")
print("✅ True concurrent video file handling")

print("\n" + "=" * 60)
print("Concurrent requests test completed!")
print("=" * 60) 