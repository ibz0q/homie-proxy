#!/usr/bin/env python3
"""
Concurrent connections test for HomieProxy integration
Tests the proxy's ability to handle multiple simultaneous connections
"""

import requests
import time
import threading
import queue
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration - can be overridden by environment variables
PROXY_HOST = os.getenv("PROXY_HOST", "localhost")
PROXY_PORT = int(os.getenv("PROXY_PORT", "8123"))  # Home Assistant default port
PROXY_NAME = os.getenv("PROXY_NAME", "external-api-route")
PROXY_TOKEN = os.getenv("PROXY_TOKEN", "93f00721-b834-460e-96f0-9978eb594e3f")

BASE_URL = f"http://{PROXY_HOST}:{PROXY_PORT}/api/homie_proxy"

def make_concurrent_request(request_id: int, delay: int = 2) -> dict:
    """Make a single request with specified delay"""
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    params = {
        'url': f'https://httpbin.org/delay/{delay}?request_id={request_id}',
        'token': token,
        'request_header[X-Request-ID]': str(request_id)
    }
    
    start_time = time.time()
    try:
        response = requests.get(url, params=params, timeout=15)
        end_time = time.time()
        
        return {
            'request_id': request_id,
            'success': response.status_code == 200,
            'status_code': response.status_code,
            'duration': end_time - start_time,
            'start_time': start_time,
            'end_time': end_time,
            'response_size': len(response.content) if response else 0,
            'error': None
        }
    except Exception as e:
        end_time = time.time()
        return {
            'request_id': request_id,
            'success': False,
            'status_code': 0,
            'duration': end_time - start_time,
            'start_time': start_time,
            'end_time': end_time,
            'response_size': 0,
            'error': str(e)
        }

def test_concurrent_connections_2():
    """Test 2 concurrent connections"""
    print("Testing 2 concurrent connections...")
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(make_concurrent_request, i, 2) for i in range(1, 3)]
        results = [future.result() for future in as_completed(futures)]
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Analyze results
    successful_requests = sum(1 for r in results if r['success'])
    avg_duration = sum(r['duration'] for r in results if r['success']) / max(successful_requests, 1)
    
    print(f"✓ 2 concurrent connections test:")
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Successful requests: {successful_requests}/2")
    print(f"  Average request duration: {avg_duration:.1f}s")
    
    # Check if requests were truly concurrent (should complete in ~2s, not 4s)
    if total_time < 3.5 and successful_requests == 2:
        print(f"  ✓ Requests executed concurrently")
    else:
        print(f"  ? Requests may have been sequential (expected ~2s, got {total_time:.1f}s)")
    
    return successful_requests == 2

def test_concurrent_connections_5():
    """Test 5 concurrent connections"""
    print("\nTesting 5 concurrent connections...")
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_concurrent_request, i, 2) for i in range(1, 6)]
        results = [future.result() for future in as_completed(futures)]
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Analyze results
    successful_requests = sum(1 for r in results if r['success'])
    avg_duration = sum(r['duration'] for r in results if r['success']) / max(successful_requests, 1)
    
    print(f"✓ 5 concurrent connections test:")
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Successful requests: {successful_requests}/5")
    print(f"  Average request duration: {avg_duration:.1f}s")
    
    # Check if requests were truly concurrent (should complete in ~2s, not 10s)
    if total_time < 4.0 and successful_requests >= 4:  # Allow 1 failure
        print(f"  ✓ Requests executed concurrently")
    else:
        print(f"  ? Requests may have been sequential or limited (expected ~2s, got {total_time:.1f}s)")
    
    return successful_requests >= 4

def test_mixed_concurrent_requests():
    """Test mixed request types concurrently"""
    print("\nTesting mixed concurrent request types...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    base_url = f"{BASE_URL}/{proxy_name}"
    
    def make_get_request():
        params = {'url': 'https://httpbin.org/get', 'token': token}
        start = time.time()
        response = requests.get(base_url, params=params, timeout=10)
        return {'type': 'GET', 'success': response.status_code == 200, 'duration': time.time() - start}
    
    def make_post_request():
        params = {'url': 'https://httpbin.org/post', 'token': token}
        data = {'test': 'concurrent_post', 'timestamp': time.time()}
        start = time.time()
        response = requests.post(base_url, params=params, json=data, timeout=10)
        return {'type': 'POST', 'success': response.status_code == 200, 'duration': time.time() - start}
    
    def make_stream_request():
        params = {'url': 'https://httpbin.org/stream/5', 'token': token}
        start = time.time()
        response = requests.get(base_url, params=params, timeout=10)
        return {'type': 'STREAM', 'success': response.status_code == 200, 'duration': time.time() - start}
    
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(make_get_request),
            executor.submit(make_post_request),
            executor.submit(make_stream_request)
        ]
        results = [future.result() for future in as_completed(futures)]
    
    end_time = time.time()
    total_time = end_time - start_time
    
    successful_requests = sum(1 for r in results if r['success'])
    
    print(f"✓ Mixed concurrent requests test:")
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Successful requests: {successful_requests}/3")
    
    for result in results:
        status = "✓" if result['success'] else "✗"
        print(f"  {status} {result['type']}: {result['duration']:.1f}s")
    
    return successful_requests >= 2

def test_high_frequency_requests():
    """Test high frequency concurrent requests"""
    print("\nTesting high frequency concurrent requests...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    def make_quick_request(request_id):
        params = {
            'url': f'https://httpbin.org/uuid?id={request_id}',
            'token': token
        }
        start = time.time()
        try:
            response = requests.get(url, params=params, timeout=5)
            return {
                'id': request_id, 
                'success': response.status_code == 200, 
                'duration': time.time() - start
            }
        except Exception as e:
            return {
                'id': request_id, 
                'success': False, 
                'duration': time.time() - start,
                'error': str(e)
            }
    
    start_time = time.time()
    
    # Launch 10 quick requests
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_quick_request, i) for i in range(10)]
        results = [future.result() for future in as_completed(futures)]
    
    end_time = time.time()
    total_time = end_time - start_time
    
    successful_requests = sum(1 for r in results if r['success'])
    avg_duration = sum(r['duration'] for r in results if r['success']) / max(successful_requests, 1)
    
    print(f"✓ High frequency requests test:")
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Successful requests: {successful_requests}/10")
    print(f"  Average request duration: {avg_duration:.2f}s")
    print(f"  Requests per second: {successful_requests / total_time:.1f}")
    
    return successful_requests >= 8

def test_connection_stress():
    """Test connection under stress (multiple rapid connections)"""
    print("\nTesting connection stress...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    def stress_request(request_id):
        params = {
            'url': f'https://httpbin.org/delay/1?stress_id={request_id}',
            'token': token
        }
        start = time.time()
        try:
            response = requests.get(url, params=params, timeout=8)
            return {
                'id': request_id, 
                'success': response.status_code == 200, 
                'duration': time.time() - start
            }
        except Exception as e:
            return {
                'id': request_id, 
                'success': False, 
                'duration': time.time() - start,
                'error': str(e)
            }
    
    start_time = time.time()
    
    # Launch 5 stress requests with 1s delay each
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(stress_request, i) for i in range(1, 6)]
        results = [future.result() for future in as_completed(futures)]
    
    end_time = time.time()
    total_time = end_time - start_time
    
    successful_requests = sum(1 for r in results if r['success'])
    
    print(f"✓ Connection stress test:")
    print(f"  Total time: {total_time:.1f}s")
    print(f"  Successful requests: {successful_requests}/5")
    
    # Should complete in ~1-2s if truly concurrent
    if total_time < 3.0 and successful_requests >= 4:
        print(f"  ✓ Stress test passed - good concurrent handling")
    else:
        print(f"  ? Stress test marginal - may have connection limits")
    
    return successful_requests >= 4

def main():
    """Run all concurrent connection tests"""
    print("=" * 60)
    print("CONCURRENT CONNECTIONS TESTS - HOMIE PROXY INTEGRATION")
    print("=" * 60)
    print("Note: Make sure Home Assistant is running with HomieProxy configured")
    print("      and accessible at localhost:8123")
    print("")
    
    tests = [
        test_concurrent_connections_2,
        test_concurrent_connections_5,
        test_mixed_concurrent_requests,
        test_high_frequency_requests,
        test_connection_stress
    ]
    
    results = []
    
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
            results.append(False)
        
        time.sleep(1)  # Brief pause between tests
    
    print("\n" + "=" * 60)
    print("CONCURRENT CONNECTIONS TEST SUMMARY")
    print("=" * 60)
    
    passed_tests = sum(results)
    total_tests = len(results)
    
    print(f"Tests passed: {passed_tests}/{total_tests}")
    
    if passed_tests == total_tests:
        print("🎉 All concurrent connection tests passed!")
        print("✓ Proxy handles multiple simultaneous connections well")
    elif passed_tests >= total_tests * 0.8:
        print("⚠️  Most concurrent connection tests passed")
        print("✓ Proxy handles concurrent connections adequately")
    else:
        print("❌ Several concurrent connection tests failed")
        print("? Proxy may have concurrency limitations")

if __name__ == "__main__":
    main() 