#!/usr/bin/env python3
"""
Streaming and performance test for HomieProxy integration
Tests streaming capabilities, large responses, and performance scenarios
"""

import requests
import json
import time
import io
import os

# Configuration - can be overridden by environment variables
PROXY_HOST = os.getenv("PROXY_HOST", "localhost")
PROXY_PORT = int(os.getenv("PROXY_PORT", "8123"))  # Home Assistant default port
PROXY_NAME = os.getenv("PROXY_NAME", "external-api-route")
PROXY_TOKEN = os.getenv("PROXY_TOKEN", "93f00721-b834-460e-96f0-9978eb594e3f")

BASE_URL = f"http://{PROXY_HOST}:{PROXY_PORT}/api/homie_proxy"

def test_streaming_response():
    """Test streaming response handling"""
    print("Testing streaming response...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    # Use httpbin's stream endpoint which returns data in chunks
    params = {
        'url': 'https://httpbin.org/stream/10',  # 10 lines of JSON
        'token': token
    }
    
    try:
        start_time = time.time()
        response = requests.get(url, params=params, timeout=30, stream=True)
        headers_time = time.time()
        
        print(f"Stream response status: {response.status_code}")
        print(f"Time to headers: {headers_time - start_time:.3f}s")
        
        if response.status_code == 200:
            lines_received = 0
            total_bytes = 0
            
            for line in response.iter_lines():
                if line:
                    lines_received += 1
                    total_bytes += len(line)
                    
                    # Try to parse each line as JSON
                    try:
                        data = json.loads(line.decode('utf-8'))
                        if 'id' in data:
                            print(f"  Received stream line {data['id']}: {len(line)} bytes")
                    except json.JSONDecodeError:
                        print(f"  Received non-JSON line: {len(line)} bytes")
            
            end_time = time.time()
            total_time = end_time - start_time
            
            print(f"✓ Streaming test completed:")
            print(f"  Lines received: {lines_received}")
            print(f"  Total bytes: {total_bytes}")
            print(f"  Total time: {total_time:.3f}s")
            print(f"  Throughput: {total_bytes / total_time:.0f} bytes/sec")
            
        else:
            print(f"✗ Streaming test failed - status {response.status_code}")
            
    except Exception as e:
        print(f"✗ Streaming test failed: {e}")

def test_large_response():
    """Test handling of large responses"""
    print("\nTesting large response handling...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    # Request a larger amount of data
    params = {
        'url': 'https://httpbin.org/base64/SFRUUEJJTiBpcyBhd2Vzb21l' * 1000,  # Large base64 string
        'token': token
    }
    
    try:
        start_time = time.time()
        response = requests.get(url, params=params, timeout=60)
        end_time = time.time()
        
        print(f"Large response status: {response.status_code}")
        print(f"Response time: {end_time - start_time:.3f}s")
        
        if response.status_code == 200:
            response_size = len(response.content)
            print(f"✓ Large response test passed:")
            print(f"  Response size: {response_size} bytes")
            print(f"  Throughput: {response_size / (end_time - start_time):.0f} bytes/sec")
        else:
            print(f"✗ Large response test failed - status {response.status_code}")
            
    except Exception as e:
        print(f"✗ Large response test failed: {e}")

def test_concurrent_requests():
    """Test handling multiple concurrent requests"""
    print("\nTesting concurrent requests...")
    
    import threading
    import queue
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    results = queue.Queue()
    num_threads = 5
    
    def make_request(thread_id):
        params = {
            'url': f'https://httpbin.org/delay/1?thread={thread_id}',
            'token': token,
            'request_headers[X-Thread-ID]': str(thread_id)
        }
        
        try:
            start_time = time.time()
            response = requests.get(url, params=params, timeout=15)
            end_time = time.time()
            
            results.put({
                'thread_id': thread_id,
                'status': response.status_code,
                'time': end_time - start_time,
                'success': response.status_code == 200
            })
            
        except Exception as e:
            results.put({
                'thread_id': thread_id,
                'status': 0,
                'time': 0,
                'success': False,
                'error': str(e)
            })
    
    # Start all threads
    start_time = time.time()
    threads = []
    
    for i in range(num_threads):
        thread = threading.Thread(target=make_request, args=(i,))
        thread.start()
        threads.append(thread)
    
    # Wait for all threads to complete
    for thread in threads:
        thread.join()
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Collect results
    all_results = []
    while not results.empty():
        all_results.append(results.get())
    
    successful_requests = sum(1 for r in all_results if r['success'])
    avg_response_time = sum(r['time'] for r in all_results if r['success']) / max(successful_requests, 1)
    
    print(f"✓ Concurrent requests test completed:")
    print(f"  Total threads: {num_threads}")
    print(f"  Successful requests: {successful_requests}")
    print(f"  Total time: {total_time:.3f}s")
    print(f"  Average response time: {avg_response_time:.3f}s")
    
    for result in all_results:
        status = "✓" if result['success'] else "✗"
        thread_id = result['thread_id']
        time_taken = result['time']
        print(f"  {status} Thread {thread_id}: {time_taken:.3f}s")

def test_timeout_handling():
    """Test timeout handling"""
    print("\nTesting timeout handling...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    # Test with a URL that should trigger timeout (use a longer delay that exceeds proxy timeout)
    # The proxy has a 30s timeout, so we use 40s delay and 20s client timeout
    params = {
        'url': 'https://httpbin.org/delay/40',  # 40 second delay (exceeds proxy 30s timeout)
        'token': token
    }
    
    try:
        start_time = time.time()
        response = requests.get(url, params=params, timeout=35)  # Client timeout longer than proxy
        end_time = time.time()
        
        print(f"Timeout test status: {response.status_code}")
        print(f"Time taken: {end_time - start_time:.3f}s")
        
        # We expect either a 504 (Gateway Timeout) from proxy or timeout between 25-35 seconds
        elapsed_time = end_time - start_time
        if response.status_code == 504:
            print("✓ Timeout properly handled by proxy (504 Gateway Timeout)")
        elif 25 <= elapsed_time <= 35:
            print("✓ Timeout properly handled within expected timeframe")
        elif response.status_code == 200 and elapsed_time < 20:
            print(f"? Timeout test - request completed faster than expected ({elapsed_time:.1f}s)")
            print("  This might be due to httpbin.org not honoring the delay parameter")
        else:
            print(f"✗ Timeout test - unexpected behavior: {response.status_code} in {elapsed_time:.1f}s")
            
    except requests.exceptions.Timeout:
        end_time = time.time()
        elapsed_time = end_time - start_time
        print(f"✓ Timeout properly handled by client after {elapsed_time:.1f}s")
    except requests.exceptions.RequestException as e:
        end_time = time.time()
        elapsed_time = end_time - start_time
        if "timed out" in str(e).lower() or "timeout" in str(e).lower():
            print(f"✓ Timeout properly handled (exception) after {elapsed_time:.1f}s")
        else:
            print(f"✗ Timeout test failed with unexpected error: {e}")
    except Exception as e:
        print(f"✗ Timeout test failed: {e}")

def test_binary_content():
    """Test handling of binary content"""
    print("\nTesting binary content handling...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    # Test with an image URL
    params = {
        'url': 'https://httpbin.org/image/png',
        'token': token
    }
    
    try:
        start_time = time.time()
        response = requests.get(url, params=params, timeout=30)
        end_time = time.time()
        
        print(f"Binary content status: {response.status_code}")
        print(f"Response time: {end_time - start_time:.3f}s")
        
        if response.status_code == 200:
            content_type = response.headers.get('content-type', '')
            content_length = len(response.content)
            
            print(f"✓ Binary content test passed:")
            print(f"  Content-Type: {content_type}")
            print(f"  Content-Length: {content_length} bytes")
            
            # Check if it looks like a PNG
            if response.content.startswith(b'\x89PNG'):
                print("  ✓ Valid PNG file detected")
            else:
                print("  ? Content may not be a valid PNG")
                
        else:
            print(f"✗ Binary content test failed - status {response.status_code}")
            
    except Exception as e:
        print(f"✗ Binary content test failed: {e}")

def test_response_headers_preservation():
    """Test that response headers are properly preserved"""
    print("\nTesting response headers preservation...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    params = {
        'url': 'https://httpbin.org/response-headers?X-Custom-Header=test-value&Cache-Control=max-age=3600',
        'token': token
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            # Check if custom headers are preserved
            custom_header = response.headers.get('X-Custom-Header')
            cache_control = response.headers.get('Cache-Control')
            content_type = response.headers.get('Content-Type')
            
            print(f"✓ Response headers test completed:")
            print(f"  X-Custom-Header: {custom_header}")
            print(f"  Cache-Control: {cache_control}")
            print(f"  Content-Type: {content_type}")
            
            if custom_header == 'test-value':
                print("  ✓ Custom header properly preserved")
            else:
                print("  ✗ Custom header not preserved")
                
            if cache_control == 'max-age=3600':
                print("  ✓ Cache-Control header properly preserved")
            else:
                print("  ✗ Cache-Control header not preserved")
                
        else:
            print(f"✗ Response headers test failed - status {response.status_code}")
            
    except Exception as e:
        print(f"✗ Response headers test failed: {e}")

def test_compression_handling():
    """Test handling of compressed responses"""
    print("\nTesting compression handling...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    params = {
        'url': 'https://httpbin.org/gzip',
        'token': token,
        'request_headers[Accept-Encoding]': 'gzip, deflate'
    }
    
    try:
        response = requests.get(url, params=params, timeout=15)
        
        if response.status_code == 200:
            # Check if response was decompressed properly
            try:
                data = response.json()
                if 'gzipped' in data and data['gzipped'] is True:
                    print("✓ Compression test passed - gzipped response properly handled")
                    print(f"  Response size: {len(response.content)} bytes")
                    print(f"  Content-Encoding header: {response.headers.get('Content-Encoding', 'none')}")
                else:
                    print("✗ Compression test failed - unexpected response content")
            except json.JSONDecodeError:
                print("✗ Compression test failed - response not valid JSON")
        else:
            print(f"✗ Compression test failed - status {response.status_code}")
            
    except Exception as e:
        print(f"✗ Compression test failed: {e}")

def main():
    """Run all streaming and performance tests"""
    print("=" * 60)
    print("STREAMING & PERFORMANCE TESTS - HOMIE PROXY INTEGRATION")
    print("=" * 60)
    print("Note: Make sure Home Assistant is running with HomieProxy configured")
    print("      and accessible at localhost:8123")
    print("")
    
    tests = [
        test_streaming_response,
        test_large_response,
        test_concurrent_requests,
        test_timeout_handling,
        test_binary_content,
        test_response_headers_preservation,
        test_compression_handling
    ]
    
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
        
        time.sleep(2)  # Longer pause between these intensive tests
    
    print("\n" + "=" * 60)
    print("Streaming & performance tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    main() 