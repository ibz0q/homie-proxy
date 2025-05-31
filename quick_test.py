#!/usr/bin/env python3

import requests

print("Quick test of header logging and Host header fix...")

# Test the Host header fix with sylvan.apple.com (from your example)
url = "http://localhost:8080/default?token=your-secret-token-here&url=https://sylvan.apple.com/Videos/&skip_tls_checks=ALL"

try:
    print("📥 Making request to https://sylvan.apple.com/Videos/")
    print("🔧 This should now show Host: sylvan.apple.com instead of 10.5.254.10:8080")
    
    response = requests.get(url)
    print(f"✅ Status: {response.status_code}")
    print("📤 Check server console for:")
    print("   - 'Fixed Host header to: sylvan.apple.com'")
    print("   - '  Host: sylvan.apple.com' (not the proxy server address)")
    
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*50)

# Test with httpbin to verify the Host header
url2 = "http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/headers"

try:
    print("📥 Making test request to httpbin.org/headers...")
    response = requests.get(url2)
    print(f"✅ Status: {response.status_code}")
    
    if response.status_code == 200:
        import json
        data = response.json()
        host_header = data.get('headers', {}).get('Host', 'NOT FOUND')
        print(f"📥 Host header received by target server: {host_header}")
        
        if host_header == 'httpbin.org':
            print("✅ Host header fix working correctly!")
        else:
            print(f"❌ Host header still wrong: {host_header}")
    
except Exception as e:
    print(f"❌ Error: {e}") 