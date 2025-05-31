#!/usr/bin/env python3

import requests
import json

print("=" * 80)
print("USER-AGENT HEADER MODIFICATION TEST")
print("=" * 80)

# Different User-Agent strings to test
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "curl/7.68.0",
    "MyCustomBot/1.0 (Reverse Proxy Test)",
    "PostmanRuntime/7.28.4",
    "Python-requests-via-reverse-proxy/1.0"
]

base_url = "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/get"

print("\n1. TESTING DIFFERENT USER-AGENT HEADERS")
print("=" * 60)

for i, user_agent in enumerate(user_agents, 1):
    print(f"\n🔸 Test {i}: {user_agent}")
    print("-" * 50)
    
    try:
        # Test with custom User-Agent
        response = requests.get(
            base_url,
            headers={
                'User-Agent': user_agent,
                'X-Test-Number': str(i)
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            received_ua = data.get('headers', {}).get('User-Agent', 'NOT FOUND')
            
            print(f"✅ Status: {response.status_code}")
            print(f"📤 Sent User-Agent: {user_agent}")
            print(f"📥 Received User-Agent: {received_ua}")
            
            if user_agent == received_ua:
                print("✅ User-Agent PRESERVED PERFECTLY!")
            else:
                print("❌ User-Agent was modified or not forwarded")
                
        else:
            print(f"❌ Request failed with status: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

print("\n\n2. TESTING CUSTOM REQUEST HEADERS WITH USER-AGENT")
print("=" * 60)

# Test using the proxy's custom header feature
custom_ua = "CustomProxy/2.0 (via request_headers parameter)"
custom_header_url = f"{base_url}&request_headers[User-Agent]={custom_ua.replace(' ', '%20')}"

print(f"\n🔸 Testing with request_headers parameter...")
print("-" * 50)

try:
    response = requests.get(custom_header_url)
    
    if response.status_code == 200:
        data = response.json()
        received_ua = data.get('headers', {}).get('User-Agent', 'NOT FOUND')
        
        print(f"✅ Status: {response.status_code}")
        print(f"📤 Custom User-Agent via URL: {custom_ua}")
        print(f"📥 Received User-Agent: {received_ua}")
        
        if custom_ua in received_ua:
            print("✅ Custom User-Agent via URL parameter WORKS!")
        else:
            print("❌ Custom User-Agent via URL parameter failed")
    else:
        print(f"❌ Request failed with status: {response.status_code}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n\n3. COMPARING WITH DIRECT REQUEST")
print("=" * 60)

test_ua = "DirectVsProxy-Test/1.0"

print(f"\n🔸 Direct request to httpbin...")
try:
    direct_response = requests.get(
        'https://httpbin.org/get',
        headers={'User-Agent': test_ua}
    )
    direct_ua = direct_response.json().get('headers', {}).get('User-Agent', 'NOT FOUND')
    print(f"📥 Direct User-Agent: {direct_ua}")
except Exception as e:
    print(f"❌ Direct request error: {e}")
    direct_ua = "ERROR"

print(f"\n🔸 Proxied request...")
try:
    proxy_response = requests.get(
        base_url,
        headers={'User-Agent': test_ua}
    )
    proxy_ua = proxy_response.json().get('headers', {}).get('User-Agent', 'NOT FOUND')
    print(f"📥 Proxied User-Agent: {proxy_ua}")
except Exception as e:
    print(f"❌ Proxy request error: {e}")
    proxy_ua = "ERROR"

print(f"\n📊 Comparison:")
if direct_ua == proxy_ua and direct_ua != "ERROR":
    print("✅ User-Agent forwarding is PERFECT - identical to direct requests!")
else:
    print("❌ User-Agent forwarding differs from direct requests")
    print(f"   Direct:  {direct_ua}")
    print(f"   Proxied: {proxy_ua}")

print("\n\n4. TESTING EDGE CASES")
print("=" * 60)

edge_cases = [
    ("Empty User-Agent", ""),
    ("Very long User-Agent", "A" * 500 + "/1.0"),
    ("Special characters", "Test/1.0 (含中文字符) ñoño"),
    ("With quotes", 'Test/1.0 "quoted" \'string\''),
]

for case_name, edge_ua in edge_cases:
    print(f"\n🔸 {case_name}: {edge_ua[:50]}{'...' if len(edge_ua) > 50 else ''}")
    try:
        response = requests.get(
            base_url,
            headers={'User-Agent': edge_ua} if edge_ua else {}
        )
        
        if response.status_code == 200:
            received_ua = response.json().get('headers', {}).get('User-Agent', 'NOT FOUND')
            print(f"✅ Status: {response.status_code}")
            print(f"📥 Received: {received_ua[:100]}{'...' if len(received_ua) > 100 else ''}")
        else:
            print(f"❌ Failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

print("\n" + "=" * 80)
print("🎯 User-Agent modification test completed!")
print("=" * 80) 