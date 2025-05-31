#!/usr/bin/env python3

import requests

print("=" * 60)
print("HOST HEADER FIX TEST - REVERSE PROXY")
print("=" * 60)

base_url = "http://localhost:8080/default?token=your-secret-token-here"

print("\n🌐 Testing Host header correction")
print("-" * 50)

test_cases = [
    {
        'name': 'Standard HTTPS (port 443)',
        'url': 'https://httpbin.org/headers',
        'expected_host': 'httpbin.org'
    },
    {
        'name': 'Standard HTTP (port 80)', 
        'url': 'http://httpbin.org/headers',
        'expected_host': 'httpbin.org'
    },
    {
        'name': 'HTTPS with custom port',
        'url': 'https://httpbin.org:8443/headers',
        'expected_host': 'httpbin.org:8443'
    },
    {
        'name': 'Different domain',
        'url': 'https://jsonplaceholder.typicode.com/posts/1',
        'expected_host': 'jsonplaceholder.typicode.com'
    }
]

for i, test_case in enumerate(test_cases, 1):
    print(f"\n🧪 Test {i}: {test_case['name']}")
    print(f"   Target URL: {test_case['url']}")
    print(f"   Expected Host header: {test_case['expected_host']}")
    
    test_url = f"{base_url}&url={test_case['url']}"
    
    try:
        print("   📥 Making request...")
        response = requests.get(test_url, timeout=8)
        
        print(f"   ✅ Status: {response.status_code}")
        
        if response.status_code == 200:
            print("   ✅ SUCCESS: Check server console for Host header logging")
            
            # For httpbin, we can verify the Host header in the response
            if 'httpbin.org' in test_case['url']:
                try:
                    response_data = response.json()
                    actual_host = response_data.get('headers', {}).get('Host', 'NOT FOUND')
                    print(f"   📥 Host header received by target: {actual_host}")
                    
                    if actual_host == test_case['expected_host']:
                        print(f"   ✅ Host header correct!")
                    else:
                        print(f"   ❌ Host header mismatch! Expected: {test_case['expected_host']}, Got: {actual_host}")
                except:
                    print(f"   📊 Response size: {len(response.content)} bytes")
            else:
                print(f"   📊 Response size: {len(response.content)} bytes")
        else:
            print(f"   ⚠️  Unexpected status: {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n🧪 Test 5: Manual Host header override")
print("   Testing if custom Host header via request_headers overrides the fix")

override_url = f"{base_url}&url=https://httpbin.org/headers&request_headers[Host]=custom.example.com"
try:
    print("   📥 Making request with custom Host header...")
    response = requests.get(override_url, timeout=8)
    
    print(f"   ✅ Status: {response.status_code}")
    
    if response.status_code == 200:
        response_data = response.json()
        actual_host = response_data.get('headers', {}).get('Host', 'NOT FOUND')
        print(f"   📥 Host header received by target: {actual_host}")
        
        if actual_host == 'custom.example.com':
            print(f"   ✅ Custom Host header override working!")
        else:
            print(f"   ❌ Custom Host header not applied! Got: {actual_host}")
        
except Exception as e:
    print(f"   ❌ Error: {e}")

print("\n💡 What to look for in server console:")
print("   📤 'Fixed Host header to: [hostname]' - Shows the corrected Host header")
print("   📤 '  Host: [hostname]' - Should show target hostname, not proxy server")
print("   🔧 Before fix: Host: 10.5.254.10:8080 (wrong)")
print("   ✅ After fix: Host: sylvan.apple.com (correct)")

print("\n" + "=" * 60)
print("🎯 Host header fix test completed!")
print("=" * 60) 