#!/usr/bin/env python3
"""
POST Method Test Script for HomieProxy
Tests POST functionality on both standalone and HA integration
"""

import requests
import json
import sys
import time

def test_standalone_post():
    """Test POST on standalone server (port 8080)"""
    print("=" * 60)
    print("TESTING STANDALONE SERVER POST FUNCTIONALITY")
    print("=" * 60)
    
    base_url = "http://localhost:8080/default"
    token = "your-secret-token-here"
    
    test_cases = [
        {
            "name": "JSON POST to httpbin",
            "target_url": "https://httpbin.org/post",
            "data": {"test": "standalone POST", "timestamp": time.time()},
            "content_type": "application/json"
        },
        {
            "name": "Form POST to httpbin", 
            "target_url": "https://httpbin.org/post",
            "data": "key1=value1&key2=value2",
            "content_type": "application/x-www-form-urlencoded"
        },
        {
            "name": "Plain text POST",
            "target_url": "https://httpbin.org/post", 
            "data": "This is plain text data",
            "content_type": "text/plain"
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test['name']}")
        print(f"Target: {test['target_url']}")
        print(f"Content-Type: {test['content_type']}")
        
        params = {
            "token": token,
            "url": test['target_url']
        }
        
        headers = {
            "Content-Type": test['content_type']
        }
        
        try:
            if test['content_type'] == 'application/json':
                response = requests.post(base_url, params=params, json=test['data'], timeout=10)
            else:
                response = requests.post(base_url, params=params, data=test['data'], headers=headers, timeout=10)
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ SUCCESS")
                try:
                    resp_data = response.json()
                    if 'json' in resp_data or 'data' in resp_data or 'form' in resp_data:
                        print("✅ Data successfully sent and received")
                        if test['content_type'] == 'application/json' and 'json' in resp_data:
                            print(f"   JSON received: {resp_data['json']}")
                        elif 'data' in resp_data:
                            print(f"   Data received: {resp_data['data'][:100]}...")
                        elif 'form' in resp_data:
                            print(f"   Form received: {resp_data['form']}")
                    else:
                        print("❓ Unexpected response format")
                except:
                    print("❓ Non-JSON response")
            else:
                print(f"❌ FAILED - HTTP {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                
        except Exception as e:
            print(f"❌ FAILED - Exception: {e}")

def test_ha_integration_post():
    """Test POST on HA integration (port 8123)"""
    print("\n" + "=" * 60)
    print("TESTING HA INTEGRATION POST FUNCTIONALITY")
    print("=" * 60)
    
    # First get token from debug endpoint
    try:
        debug_response = requests.get("http://localhost:8123/api/homie_proxy/debug", timeout=5)
        if debug_response.status_code != 200:
            print("❌ Cannot access HA debug endpoint - HA might not be running")
            return
            
        debug_data = debug_response.json()
        if not debug_data.get('tokens'):
            print("❌ No tokens found in HA debug response")
            return
            
        token = debug_data['tokens'][0]
        print(f"✅ Got HA token: {token[:8]}...")
        
    except Exception as e:
        print(f"❌ Failed to get HA token: {e}")
        return
    
    base_url = "http://localhost:8123/api/homie_proxy/external-api-route"
    
    test_cases = [
        {
            "name": "JSON POST to httpbin via HA",
            "target_url": "https://httpbin.org/post",
            "data": {"test": "HA integration POST", "timestamp": time.time()},
            "content_type": "application/json"
        },
        {
            "name": "Form POST to httpbin via HA",
            "target_url": "https://httpbin.org/post", 
            "data": "ha_key1=ha_value1&ha_key2=ha_value2",
            "content_type": "application/x-www-form-urlencoded"
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\nTest {i}: {test['name']}")
        print(f"Target: {test['target_url']}")
        print(f"Content-Type: {test['content_type']}")
        
        params = {
            "token": token,
            "url": test['target_url']
        }
        
        headers = {
            "Content-Type": test['content_type']
        }
        
        try:
            if test['content_type'] == 'application/json':
                response = requests.post(base_url, params=params, json=test['data'], timeout=10)
            else:
                response = requests.post(base_url, params=params, data=test['data'], headers=headers, timeout=10)
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                print("✅ SUCCESS")
                try:
                    resp_data = response.json()
                    if 'json' in resp_data or 'data' in resp_data or 'form' in resp_data:
                        print("✅ Data successfully sent and received")
                        if test['content_type'] == 'application/json' and 'json' in resp_data:
                            print(f"   JSON received: {resp_data['json']}")
                        elif 'data' in resp_data:
                            print(f"   Data received: {resp_data['data'][:100]}...")
                        elif 'form' in resp_data:
                            print(f"   Form received: {resp_data['form']}")
                    else:
                        print("❓ Unexpected response format")
                except:
                    print("❓ Non-JSON response")
            else:
                print(f"❌ FAILED - HTTP {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                
        except Exception as e:
            print(f"❌ FAILED - Exception: {e}")

def test_your_specific_case():
    """Test the specific case you mentioned"""
    print("\n" + "=" * 60)
    print("TESTING YOUR SPECIFIC CASE")
    print("=" * 60)
    
    # Fixed URL (removed double ampersand)
    test_url = "http://localhost:8123/api/homie_proxy/external-api-route"
    
    params = {
        "token": "6d6fdb4c-3b4a-40d4-a54b-116b7a09ddfe", 
        "url": "https://httpbin.org/headers"
    }
    
    print("Testing POST to your exact endpoint...")
    print(f"URL: {test_url}")
    print(f"Token: {params['token'][:8]}...")
    print(f"Target: {params['url']}")
    
    # Test with JSON data
    test_data = {"test": "your specific case", "method": "POST"}
    
    try:
        response = requests.post(test_url, params=params, json=test_data, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ SUCCESS - POST works!")
            try:
                data = response.json()
                print("Response preview:")
                print(json.dumps(data, indent=2)[:500])
            except:
                print("Non-JSON response")
                print(response.text[:200])
        else:
            print(f"❌ FAILED - HTTP {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ FAILED - Exception: {e}")

def main():
    print("HomieProxy POST Method Testing")
    print("Testing POST functionality on both standalone and HA integration")
    
    # Test standalone server first
    test_standalone_post()
    
    # Test HA integration
    test_ha_integration_post()
    
    # Test your specific case
    test_your_specific_case()
    
    print("\n" + "=" * 60)
    print("POST TESTING COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main() 