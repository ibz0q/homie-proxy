#!/usr/bin/env python3
"""
Comprehensive HTTP methods test for HomieProxy integration
Tests all supported HTTP methods and their proper handling
"""

import requests
import json
import time
import os

# Configuration - can be overridden by environment variables
PROXY_HOST = os.getenv("PROXY_HOST", "localhost")
PROXY_PORT = int(os.getenv("PROXY_PORT", "8123"))  # Home Assistant default port
PROXY_NAME = os.getenv("PROXY_NAME", "external-api-route")
PROXY_TOKEN = os.getenv("PROXY_TOKEN", "93f00721-b834-460e-96f0-9978eb594e3f")

BASE_URL = f"http://{PROXY_HOST}:{PROXY_PORT}/api/homie_proxy"

def test_get_method():
    """Test GET method"""
    print("Testing GET method...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    params = {
        'url': 'https://httpbin.org/get',
        'token': token,
        'request_headers[X-Test-Method]': 'GET'
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        print(f"GET Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'args' in data and 'headers' in data:
                method_header = data['headers'].get('X-Test-Method', '')
                if method_header == 'GET':
                    print("✓ GET method test passed")
                else:
                    print("✗ GET method test failed - header not preserved")
            else:
                print("✗ GET method test failed - unexpected response format")
        else:
            print(f"✗ GET method test failed - status {response.status_code}")
            
    except Exception as e:
        print(f"✗ GET method test failed: {e}")

def test_post_method():
    """Test POST method with JSON data"""
    print("\nTesting POST method...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    params = {
        'url': 'https://httpbin.org/post',
        'token': token,
        'request_headers[X-Test-Method]': 'POST'
    }
    
    test_data = {
        'test': 'POST method test',
        'timestamp': time.time(),
        'data': ['item1', 'item2', 'item3']
    }
    
    try:
        response = requests.post(url, params=params, json=test_data, timeout=10)
        print(f"POST Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'json' in data and 'headers' in data:
                received_data = data['json']
                method_header = data['headers'].get('X-Test-Method', '')
                
                if received_data == test_data and method_header == 'POST':
                    print("✓ POST method test passed")
                else:
                    print("✗ POST method test failed - data or header mismatch")
            else:
                print("✗ POST method test failed - unexpected response format")
        else:
            print(f"✗ POST method test failed - status {response.status_code}")
            
    except Exception as e:
        print(f"✗ POST method test failed: {e}")

def test_put_method():
    """Test PUT method with data"""
    print("\nTesting PUT method...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    params = {
        'url': 'https://httpbin.org/put',
        'token': token,
        'request_headers[X-Test-Method]': 'PUT'
    }
    
    test_data = {
        'test': 'PUT method test',
        'timestamp': time.time(),
        'action': 'update'
    }
    
    try:
        response = requests.put(url, params=params, json=test_data, timeout=10)
        print(f"PUT Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'json' in data and 'headers' in data:
                received_data = data['json']
                method_header = data['headers'].get('X-Test-Method', '')
                
                if received_data == test_data and method_header == 'PUT':
                    print("✓ PUT method test passed")
                else:
                    print("✗ PUT method test failed - data or header mismatch")
            else:
                print("✗ PUT method test failed - unexpected response format")
        else:
            print(f"✗ PUT method test failed - status {response.status_code}")
            
    except Exception as e:
        print(f"✗ PUT method test failed: {e}")

def test_patch_method():
    """Test PATCH method with data"""
    print("\nTesting PATCH method...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    params = {
        'url': 'https://httpbin.org/patch',
        'token': token,
        'request_headers[X-Test-Method]': 'PATCH'
    }
    
    test_data = {
        'test': 'PATCH method test',
        'timestamp': time.time(),
        'action': 'partial_update'
    }
    
    try:
        response = requests.patch(url, params=params, json=test_data, timeout=10)
        print(f"PATCH Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'json' in data and 'headers' in data:
                received_data = data['json']
                method_header = data['headers'].get('X-Test-Method', '')
                
                if received_data == test_data and method_header == 'PATCH':
                    print("✓ PATCH method test passed")
                else:
                    print("✗ PATCH method test failed - data or header mismatch")
            else:
                print("✗ PATCH method test failed - unexpected response format")
        else:
            print(f"✗ PATCH method test failed - status {response.status_code}")
            
    except Exception as e:
        print(f"✗ PATCH method test failed: {e}")

def test_delete_method():
    """Test DELETE method"""
    print("\nTesting DELETE method...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    params = {
        'url': 'https://httpbin.org/delete',
        'token': token,
        'request_headers[X-Test-Method]': 'DELETE'
    }
    
    try:
        response = requests.delete(url, params=params, timeout=10)
        print(f"DELETE Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'args' in data and 'headers' in data:
                method_header = data['headers'].get('X-Test-Method', '')
                if method_header == 'DELETE':
                    print("✓ DELETE method test passed")
                else:
                    print("✗ DELETE method test failed - header not preserved")
            else:
                print("✗ DELETE method test failed - unexpected response format")
        else:
            print(f"✗ DELETE method test failed - status {response.status_code}")
            
    except Exception as e:
        print(f"✗ DELETE method test failed: {e}")

def test_head_method():
    """Test HEAD method"""
    print("\nTesting HEAD method...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    params = {
        'url': 'https://httpbin.org/get',
        'token': token,
        'request_headers[X-Test-Method]': 'HEAD'
    }
    
    try:
        response = requests.head(url, params=params, timeout=10)
        print(f"HEAD Status: {response.status_code}")
        
        if response.status_code == 200:
            # HEAD should return headers but no body
            if len(response.content) == 0:
                print("✓ HEAD method test passed - no body returned")
            else:
                print("✗ HEAD method test failed - body was returned")
        else:
            print(f"✗ HEAD method test failed - status {response.status_code}")
            
    except Exception as e:
        print(f"✗ HEAD method test failed: {e}")

def test_options_method():
    """Test OPTIONS method (if supported)"""
    print("\nTesting OPTIONS method...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    params = {
        'url': 'https://httpbin.org/',
        'token': token
    }
    
    try:
        response = requests.options(url, params=params, timeout=10)
        print(f"OPTIONS Status: {response.status_code}")
        
        if response.status_code in [200, 405]:  # 405 = Method Not Allowed is also acceptable
            print("✓ OPTIONS method test passed")
        else:
            print(f"✗ OPTIONS method test failed - status {response.status_code}")
            
    except Exception as e:
        print(f"✗ OPTIONS method test failed: {e}")

def test_method_with_form_data():
    """Test POST method with form data instead of JSON"""
    print("\nTesting POST with form data...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    params = {
        'url': 'https://httpbin.org/post',
        'token': token,
        'request_headers[Content-Type]': 'application/x-www-form-urlencoded'
    }
    
    form_data = {
        'field1': 'value1',
        'field2': 'value2',
        'timestamp': str(time.time())
    }
    
    try:
        response = requests.post(url, params=params, data=form_data, timeout=10)
        print(f"Form POST Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'form' in data:
                received_form = data['form']
                if received_form.get('field1') == 'value1' and received_form.get('field2') == 'value2':
                    print("✓ Form data POST test passed")
                else:
                    print("✗ Form data POST test failed - data mismatch")
            else:
                print("✗ Form data POST test failed - no form data in response")
        else:
            print(f"✗ Form data POST test failed - status {response.status_code}")
            
    except Exception as e:
        print(f"✗ Form data POST test failed: {e}")

def test_method_with_raw_data():
    """Test POST method with raw data"""
    print("\nTesting POST with raw data...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    params = {
        'url': 'https://httpbin.org/post',
        'token': token,
        'request_headers[Content-Type]': 'text/plain'
    }
    
    raw_data = "This is raw text data for testing POST method with custom content type."
    
    try:
        response = requests.post(url, params=params, data=raw_data, timeout=10)
        print(f"Raw POST Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                received_data = data['data']
                if received_data == raw_data:
                    print("✓ Raw data POST test passed")
                else:
                    print("✗ Raw data POST test failed - data mismatch")
            else:
                print("✗ Raw data POST test failed - no data in response")
        else:
            print(f"✗ Raw data POST test failed - status {response.status_code}")
            
    except Exception as e:
        print(f"✗ Raw data POST test failed: {e}")

def test_large_request_body():
    """Test handling of large request bodies"""
    print("\nTesting large request body...")
    
    proxy_name = PROXY_NAME
    token = PROXY_TOKEN
    url = f"{BASE_URL}/{proxy_name}"
    
    params = {
        'url': 'https://httpbin.org/post',
        'token': token
    }
    
    # Create a moderately large JSON payload (about 1MB)
    large_data = {
        'test': 'large request body test',
        'large_array': ['x' * 1000] * 1000,  # 1000 strings of 1000 chars each
        'timestamp': time.time()
    }
    
    try:
        print(f"Sending large payload (~{len(json.dumps(large_data))} bytes)...")
        response = requests.post(url, params=params, json=large_data, timeout=30)
        print(f"Large body Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'json' in data:
                received_data = data['json']
                if received_data.get('test') == 'large request body test':
                    print("✓ Large request body test passed")
                else:
                    print("✗ Large request body test failed - data mismatch")
            else:
                print("✗ Large request body test failed - no JSON in response")
        else:
            print(f"✗ Large request body test failed - status {response.status_code}")
            
    except Exception as e:
        print(f"✗ Large request body test failed: {e}")

def main():
    """Run all HTTP methods tests"""
    print("=" * 60)
    print("HTTP METHODS TESTS - HOMIE PROXY INTEGRATION")
    print("=" * 60)
    print("Note: Make sure Home Assistant is running with HomieProxy configured")
    print("      and accessible at localhost:8123")
    print("")
    
    tests = [
        test_get_method,
        test_post_method,
        test_put_method,
        test_patch_method,
        test_delete_method,
        test_head_method,
        test_options_method,
        test_method_with_form_data,
        test_method_with_raw_data,
        test_large_request_body
    ]
    
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
        
        time.sleep(1)  # Brief pause between tests
    
    print("\n" + "=" * 60)
    print("HTTP methods tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    main() 