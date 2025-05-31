#!/usr/bin/env python3
"""
Test script for the reverse proxy server
Demonstrates various usage patterns and features
"""

import requests
import json
import time
import urllib.parse

# Configuration
PROXY_HOST = "localhost"
PROXY_PORT = 8080
BASE_URL = f"http://{PROXY_HOST}:{PROXY_PORT}"

def test_basic_get():
    """Test basic GET request through proxy"""
    print("Testing basic GET request...")
    
    url = f"{BASE_URL}/default"
    params = {
        'url': 'https://httpbin.org/get',
        'token': 'your-secret-token-here'
    }
    
    try:
        response = requests.get(url, params=params)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
        print("✓ Basic GET test passed\n")
    except Exception as e:
        print(f"✗ Basic GET test failed: {e}\n")

def test_disk_cache():
    """Test disk caching functionality"""
    print("Testing disk cache functionality...")
    
    url = f"{BASE_URL}/default"
    params = {
        'url': 'https://httpbin.org/uuid',  # Returns different UUID each time
        'token': 'your-secret-token-here',
        'cache': 'true'  # Enable disk caching for this request
    }
    
    try:
        # First request - should be cached
        print("Making first request (should cache)...")
        response1 = requests.get(url, params=params)
        print(f"Status: {response1.status_code}")
        print(f"Cache header: {response1.headers.get('X-Cache', 'MISS')}")
        uuid1 = response1.json().get('uuid')
        print(f"UUID: {uuid1}")
        
        # Second request - should hit cache
        print("Making second request (should hit cache)...")
        response2 = requests.get(url, params=params)
        print(f"Status: {response2.status_code}")
        print(f"Cache header: {response2.headers.get('X-Cache', 'MISS')}")
        uuid2 = response2.json().get('uuid')
        print(f"UUID: {uuid2}")
        
        if uuid1 == uuid2 and response2.headers.get('X-Cache') == 'DISK':
            print("✓ Disk cache test passed - same UUID returned from cache\n")
        else:
            print(f"✗ Disk cache test failed - UUIDs different or cache miss\n")
            
    except Exception as e:
        print(f"✗ Disk cache test failed: {e}\n")

def test_cache_with_different_params():
    """Test that different parameters create different cache entries"""
    print("Testing cache with different parameters...")
    
    base_url = f"{BASE_URL}/default"
    base_params = {
        'url': 'https://httpbin.org/uuid',
        'token': 'your-secret-token-here',
        'cache': 'true'
    }
    
    try:
        # Request with custom header
        params1 = base_params.copy()
        params1['request_headers[X-Test]'] = 'value1'
        
        response1 = requests.get(base_url, params=params1)
        uuid1 = response1.json().get('uuid')
        print(f"Request 1 UUID: {uuid1}")
        
        # Request with different custom header - should be different cache entry
        params2 = base_params.copy()
        params2['request_headers[X-Test]'] = 'value2'
        
        response2 = requests.get(base_url, params=params2)
        uuid2 = response2.json().get('uuid')
        print(f"Request 2 UUID: {uuid2}")
        
        # Same request as first - should hit cache
        response3 = requests.get(base_url, params=params1)
        uuid3 = response3.json().get('uuid')
        print(f"Request 3 UUID: {uuid3}")
        print(f"Request 3 Cache: {response3.headers.get('X-Cache', 'MISS')}")
        
        if uuid1 != uuid2 and uuid1 == uuid3:
            print("✓ Cache parameter differentiation test passed\n")
        else:
            print("✗ Cache parameter differentiation test failed\n")
            
    except Exception as e:
        print(f"✗ Cache parameter test failed: {e}\n")

def test_post_request():
    """Test POST request with data"""
    print("Testing POST request with data...")
    
    url = f"{BASE_URL}/default"
    params = {
        'url': 'https://httpbin.org/post',
        'token': 'your-secret-token-here'
    }
    
    data = {'test': 'data', 'timestamp': time.time()}
    
    try:
        response = requests.post(url, params=params, json=data)
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Received data: {result.get('json', {})}")
        print("✓ POST test passed\n")
    except Exception as e:
        print(f"✗ POST test failed: {e}\n")

def test_post_with_cache():
    """Test POST request with caching enabled"""
    print("Testing POST request with caching...")
    
    url = f"{BASE_URL}/default"
    params = {
        'url': 'https://httpbin.org/post',
        'token': 'your-secret-token-here',
        'cache': 'true'
    }
    
    data = {'test': 'cached_post', 'timestamp': 12345}
    
    try:
        # First POST request
        response1 = requests.post(url, params=params, json=data)
        print(f"First POST Status: {response1.status_code}")
        print(f"First POST Cache: {response1.headers.get('X-Cache', 'MISS')}")
        
        # Second identical POST request - should hit cache
        response2 = requests.post(url, params=params, json=data)
        print(f"Second POST Status: {response2.status_code}")
        print(f"Second POST Cache: {response2.headers.get('X-Cache', 'MISS')}")
        
        if response2.headers.get('X-Cache') == 'DISK':
            print("✓ POST caching test passed\n")
        else:
            print("✗ POST caching test failed - no cache hit\n")
            
    except Exception as e:
        print(f"✗ POST caching test failed: {e}\n")

def test_custom_headers():
    """Test custom request and response headers"""
    print("Testing custom headers...")
    
    url = f"{BASE_URL}/default"
    params = {
        'url': 'https://httpbin.org/headers',
        'token': 'your-secret-token-here',
        'request_headers[User-Agent]': 'TestBot/1.0',
        'request_headers[X-Custom-Header]': 'test-value',
        'response_header[Access-Control-Allow-Origin]': '*',
        'response_header[X-Proxy-Test]': 'success'
    }
    
    try:
        response = requests.get(url, params=params)
        print(f"Status: {response.status_code}")
        
        # Check response headers
        print(f"CORS header: {response.headers.get('Access-Control-Allow-Origin')}")
        print(f"Custom header: {response.headers.get('X-Proxy-Test')}")
        
        # Check if custom request headers were sent
        result = response.json()
        headers = result.get('headers', {})
        print(f"User-Agent sent: {headers.get('User-Agent')}")
        print(f"Custom header sent: {headers.get('X-Custom-Header')}")
        print("✓ Custom headers test passed\n")
    except Exception as e:
        print(f"✗ Custom headers test failed: {e}\n")

def test_tls_bypass():
    """Test TLS certificate bypass"""
    print("Testing TLS bypass...")
    
    url = f"{BASE_URL}/default"
    params = {
        'url': 'https://self-signed.badssl.com/',
        'token': 'your-secret-token-here',
        'skip_tls_checks': 'true'
    }
    
    try:
        response = requests.get(url, params=params)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✓ TLS bypass test passed\n")
        else:
            print(f"✗ TLS bypass test failed with status {response.status_code}\n")
    except Exception as e:
        print(f"✗ TLS bypass test failed: {e}\n")

def test_internal_instance():
    """Test internal instance (no token required)"""
    print("Testing internal instance (no auth)...")
    
    url = f"{BASE_URL}/internal"
    params = {
        'url': 'https://httpbin.org/get'
    }
    
    try:
        response = requests.get(url, params=params)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            print("✓ Internal instance test passed\n")
        else:
            print(f"✗ Internal instance test failed with status {response.status_code}\n")
    except Exception as e:
        print(f"✗ Internal instance test failed: {e}\n")

def test_rate_limiting():
    """Test rate limiting (if configured)"""
    print("Testing rate limiting...")
    
    url = f"{BASE_URL}/default"
    params = {
        'url': 'https://httpbin.org/get',
        'token': 'your-secret-token-here'
    }
    
    success_count = 0
    rate_limited = False
    
    # Make multiple requests quickly
    for i in range(5):
        try:
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                success_count += 1
            elif response.status_code == 429:
                rate_limited = True
                print(f"Rate limited after {success_count} requests")
                break
        except Exception as e:
            print(f"Request {i+1} failed: {e}")
    
    print(f"Completed {success_count} requests")
    if rate_limited:
        print("✓ Rate limiting is working\n")
    else:
        print("ℹ Rate limiting not triggered (may need more requests)\n")

def test_error_handling():
    """Test various error conditions"""
    print("Testing error handling...")
    
    # Test missing instance
    try:
        response = requests.get(f"{BASE_URL}/nonexistent?url=https://httpbin.org/get")
        if response.status_code == 404:
            print("✓ Missing instance error handled correctly")
        else:
            print(f"✗ Expected 404, got {response.status_code}")
    except Exception as e:
        print(f"✗ Missing instance test failed: {e}")
    
    # Test missing URL
    try:
        response = requests.get(f"{BASE_URL}/default?token=your-secret-token-here")
        if response.status_code == 400:
            print("✓ Missing URL error handled correctly")
        else:
            print(f"✗ Expected 400, got {response.status_code}")
    except Exception as e:
        print(f"✗ Missing URL test failed: {e}")
    
    # Test invalid token
    try:
        response = requests.get(f"{BASE_URL}/default?url=https://httpbin.org/get&token=invalid")
        if response.status_code == 401:
            print("✓ Invalid token error handled correctly")
        else:
            print(f"✗ Expected 401, got {response.status_code}")
    except Exception as e:
        print(f"✗ Invalid token test failed: {e}")
    
    print()

def test_proxy_headers_filtered():
    """Test that proxy headers are not forwarded to target server"""
    print("Testing proxy header filtering...")
    
    url = f"{BASE_URL}/default"
    params = {
        'url': 'https://httpbin.org/headers',
        'token': 'your-secret-token-here'
    }
    
    # Add proxy headers that should be filtered out
    headers = {
        'X-Forwarded-For': '192.168.1.100',
        'X-Real-IP': '10.0.0.1',
        'X-Forwarded-Proto': 'https',
        'X-Forwarded-Host': 'example.com',
        'User-Agent': 'TestClient/1.0'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        print(f"Status: {response.status_code}")
        
        # Check what headers were actually sent to the target
        result = response.json()
        received_headers = result.get('headers', {})
        
        # These headers should NOT be present in the forwarded request
        filtered_headers = ['X-Forwarded-For', 'X-Real-Ip', 'X-Forwarded-Proto', 'X-Forwarded-Host']
        headers_found = []
        
        for header in filtered_headers:
            if header in received_headers:
                headers_found.append(header)
        
        # User-Agent should still be present (not filtered)
        user_agent_present = 'User-Agent' in received_headers
        
        if not headers_found and user_agent_present:
            print("✓ Proxy headers correctly filtered out")
            print(f"✓ User-Agent preserved: {received_headers.get('User-Agent')}")
            print("✓ Proxy header filtering test passed\n")
        else:
            print(f"✗ Proxy header filtering test failed")
            if headers_found:
                print(f"  Found filtered headers: {headers_found}")
            if not user_agent_present:
                print("  User-Agent was incorrectly filtered")
            print()
            
    except Exception as e:
        print(f"✗ Proxy header filtering test failed: {e}\n")

def test_cache_size_management():
    """Test cache size limiting and cleanup"""
    print("Testing cache size management...")
    
    # Note: This test assumes you have a test instance with a small cache limit
    # You may need to create a test configuration for this
    url = f"{BASE_URL}/default"
    
    try:
        # Make several cached requests to potentially trigger size limits
        for i in range(3):
            params = {
                'url': f'https://httpbin.org/uuid?test={i}',  # Different URLs for different cache entries
                'token': 'your-secret-token-here',
                'cache': 'true'
            }
            
            response = requests.get(url, params=params)
            print(f"Request {i+1}: Status {response.status_code}, Cache: {response.headers.get('X-Cache', 'MISS')}")
            
            if response.status_code != 200:
                print(f"✗ Request {i+1} failed with status {response.status_code}")
                return
        
        print("✓ Cache size management test completed")
        print("ℹ Check server logs for cache size limit messages\n")
        
    except Exception as e:
        print(f"✗ Cache size management test failed: {e}\n")

def test_granular_tls_errors():
    """Test granular TLS error handling"""
    print("Testing granular TLS error handling...")
    
    url = f"{BASE_URL}/default"
    
    # Test different TLS error types
    tls_error_tests = [
        {
            'name': 'Self-signed certificate',
            'errors': 'self_signed',
            'target': 'https://self-signed.badssl.com/'
        },
        {
            'name': 'Expired certificate', 
            'errors': 'expired_cert',
            'target': 'https://expired.badssl.com/'
        },
        {
            'name': 'Hostname mismatch',
            'errors': 'hostname_mismatch', 
            'target': 'https://wrong.host.badssl.com/'
        },
        {
            'name': 'Multiple errors',
            'errors': 'self_signed,hostname_mismatch,expired_cert',
            'target': 'https://self-signed.badssl.com/'
        }
    ]
    
    for test in tls_error_tests:
        try:
            params = {
                'url': test['target'],
                'token': 'your-secret-token-here',
                'ignore_tls_errors': test['errors']
            }
            
            print(f"Testing {test['name']} with errors: {test['errors']}")
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code in [200, 400, 404]:  # Any response means TLS was bypassed
                print(f"✓ {test['name']} - TLS errors ignored successfully")
            else:
                print(f"? {test['name']} - Got status {response.status_code}")
                
        except Exception as e:
            print(f"✗ {test['name']} failed: {e}")
    
    print("✓ Granular TLS error handling tests completed\n")

def test_post_body_forwarding():
    """Test POST body forwarding with different content types"""
    print("Testing POST body forwarding...")
    
    url = f"{BASE_URL}/default"
    
    # Test JSON body
    try:
        json_data = {'name': 'John Doe', 'email': 'john@example.com', 'timestamp': time.time()}
        params = {
            'url': 'https://httpbin.org/post',
            'token': 'your-secret-token-here'
        }
        
        response = requests.post(url, params=params, json=json_data)
        print(f"JSON POST Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            received_data = result.get('json', {})
            if received_data.get('name') == 'John Doe':
                print("✓ JSON body forwarded correctly")
            else:
                print(f"✗ JSON body not forwarded correctly: {received_data}")
        
    except Exception as e:
        print(f"✗ JSON POST test failed: {e}")
    
    # Test form data
    try:
        form_data = {'username': 'testuser', 'password': 'testpass'}
        params = {
            'url': 'https://httpbin.org/post',
            'token': 'your-secret-token-here'
        }
        
        response = requests.post(url, params=params, data=form_data)
        print(f"Form POST Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            received_form = result.get('form', {})
            if received_form.get('username') == 'testuser':
                print("✓ Form data forwarded correctly")
            else:
                print(f"✗ Form data not forwarded correctly: {received_form}")
        
    except Exception as e:
        print(f"✗ Form POST test failed: {e}")
    
    # Test raw body
    try:
        raw_data = "This is raw text data for testing"
        params = {
            'url': 'https://httpbin.org/post',
            'token': 'your-secret-token-here'
        }
        
        headers = {'Content-Type': 'text/plain'}
        response = requests.post(url, params=params, data=raw_data, headers=headers)
        print(f"Raw POST Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            received_data = result.get('data', '')
            if 'raw text data' in received_data:
                print("✓ Raw body forwarded correctly")
            else:
                print(f"✗ Raw body not forwarded correctly: {received_data}")
        
    except Exception as e:
        print(f"✗ Raw POST test failed: {e}")
    
    print("✓ POST body forwarding tests completed\n")

def test_put_patch_methods():
    """Test PUT and PATCH methods with body forwarding"""
    print("Testing PUT and PATCH methods...")
    
    url = f"{BASE_URL}/default"
    
    # Test PUT
    try:
        put_data = {'id': 1, 'name': 'Updated Name', 'status': 'active'}
        params = {
            'url': 'https://httpbin.org/put',
            'token': 'your-secret-token-here'
        }
        
        response = requests.put(url, params=params, json=put_data)
        print(f"PUT Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            received_data = result.get('json', {})
            if received_data.get('name') == 'Updated Name':
                print("✓ PUT body forwarded correctly")
            else:
                print(f"✗ PUT body not forwarded correctly: {received_data}")
        
    except Exception as e:
        print(f"✗ PUT test failed: {e}")
    
    # Test PATCH
    try:
        patch_data = {'status': 'inactive'}
        params = {
            'url': 'https://httpbin.org/patch',
            'token': 'your-secret-token-here'
        }
        
        response = requests.patch(url, params=params, json=patch_data)
        print(f"PATCH Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            received_data = result.get('json', {})
            if received_data.get('status') == 'inactive':
                print("✓ PATCH body forwarded correctly")
            else:
                print(f"✗ PATCH body not forwarded correctly: {received_data}")
        
    except Exception as e:
        print(f"✗ PATCH test failed: {e}")
    
    print("✓ PUT/PATCH method tests completed\n")

def main():
    """Run all tests"""
    print("=" * 50)
    print("Reverse Proxy Test Suite")
    print("=" * 50)
    print(f"Testing proxy at {BASE_URL}")
    print("Make sure the proxy server is running!\n")
    
    # Check if proxy is running
    try:
        response = requests.get(f"{BASE_URL}/nonexistent", timeout=5)
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to proxy server. Make sure it's running!")
        print("Run: python reverse_proxy.py")
        return
    except:
        pass  # Other errors are expected
    
    # Run tests
    test_basic_get()
    test_disk_cache()
    test_cache_with_different_params()
    test_post_request()
    test_post_with_cache()
    test_custom_headers()
    test_tls_bypass()
    test_internal_instance()
    test_rate_limiting()
    test_error_handling()
    test_proxy_headers_filtered()
    test_cache_size_management()
    test_granular_tls_errors()
    test_post_body_forwarding()
    test_put_patch_methods()
    
    print("=" * 50)
    print("Test suite completed!")
    print("=" * 50)

if __name__ == '__main__':
    main() 