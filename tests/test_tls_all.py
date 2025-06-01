#!/usr/bin/env python3

import requests
import argparse
import os

# Parse command line arguments or use environment variable
parser = argparse.ArgumentParser(description='Test reverse proxy TLS bypass functionality')
parser.add_argument('--port', type=int, 
                   default=int(os.environ.get('PROXY_PORT', 8080)),
                   help='Proxy server port (default: 8080, or PROXY_PORT env var)')
args = parser.parse_args()

print("=" * 60)
print("TLS SKIP_TLS_CHECKS TEST - REVERSE PROXY")
print("=" * 60)

base_url = f"http://localhost:{args.port}/default?token=your-secret-token-here"

print(f"\nTesting proxy at localhost:{args.port}")
print("-" * 50)

print("\n🔐 Testing skip_tls_checks=ALL option")
print("-" * 50)

# Test URLs with different TLS issues (these may or may not be available)
test_cases = [
    {
        'name': 'Self-signed certificate test',
        'url': 'https://self-signed.badssl.com/',
        'description': 'Site with self-signed certificate'
    },
    {
        'name': 'Expired certificate test', 
        'url': 'https://expired.badssl.com/',
        'description': 'Site with expired certificate'
    },
    {
        'name': 'Wrong hostname test',
        'url': 'https://wrong.host.badssl.com/',
        'description': 'Site with hostname mismatch'
    }
]

print("\n🧪 Test 1: Using skip_tls_checks=ALL")
print("   This should disable ALL TLS verification")

for i, test_case in enumerate(test_cases, 1):
    print(f"\n🔗 Test 1.{i}: {test_case['name']}")
    print(f"   Target: {test_case['url']}")
    print(f"   Description: {test_case['description']}")
    
    # Test with ALL option
    test_url = f"{base_url}&url={test_case['url']}&skip_tls_checks=ALL"
    
    try:
        print("   📥 Making request with skip_tls_checks=ALL...")
        response = requests.get(test_url, timeout=10)
        
        print(f"   ✅ Status: {response.status_code}")
        print(f"   📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        print(f"   📊 Response size: {len(response.content)} bytes")
        
        if response.status_code == 200:
            print("   ✅ SUCCESS: TLS errors ignored successfully!")
        else:
            print(f"   ⚠️  Got response but with status {response.status_code}")
            
    except Exception as e:
        print(f"   ❌ Error: {e}")
        if "certificate" in str(e).lower() or "ssl" in str(e).lower():
            print("   💡 This error suggests TLS verification is still active")

print("\n🧪 Test 2: Compare with specific TLS error types")
print("   Testing individual error types vs ALL")

# Test with specific error type first
specific_test_url = f"{base_url}&url=https://self-signed.badssl.com/&skip_tls_checks=self_signed"
print(f"\n🔗 Test 2.1: Using skip_tls_checks=self_signed")
try:
    response = requests.get(specific_test_url, timeout=10)
    print(f"   ✅ Specific error type - Status: {response.status_code}")
except Exception as e:
    print(f"   ❌ Specific error type failed: {e}")

# Test with ALL option
all_test_url = f"{base_url}&url=https://self-signed.badssl.com/&skip_tls_checks=ALL"
print(f"\n🔗 Test 2.2: Using skip_tls_checks=ALL")
try:
    response = requests.get(all_test_url, timeout=10)
    print(f"   ✅ ALL option - Status: {response.status_code}")
except Exception as e:
    print(f"   ❌ ALL option failed: {e}")

print("\n🧪 Test 3: Testing with a working HTTPS site")
print("   This should work regardless of TLS options")

working_url = f"{base_url}&url=https://httpbin.org/get&skip_tls_checks=ALL"
try:
    print("📥 Testing with httpbin.org (valid certificate)...")
    response = requests.get(working_url, timeout=10)
    
    print(f"✅ Status: {response.status_code}")
    print(f"📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
    
    if response.status_code == 200:
        print("✅ Working HTTPS site successful with ALL option")
    else:
        print(f"⚠️  Unexpected status code: {response.status_code}")
        
except Exception as e:
    print(f"❌ Error with working site: {e}")

print("\n🧪 Test 4: Test request header logging")
print("   Adding custom headers to see logging in action")

header_test_url = f"{base_url}&url=https://httpbin.org/headers&skip_tls_checks=ALL&request_header[X-Custom-Header]=test-value&request_header[Authorization]=Bearer test-token"
try:
    print("📥 Testing request header logging...")
    response = requests.get(header_test_url, timeout=10)
    
    print(f"✅ Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ Check server console for detailed request header logging")
    
except Exception as e:
    print(f"❌ Error: {e}")

print("\n💡 Usage Examples:")
print("   🔗 Ignore all TLS errors:")
print("      &skip_tls_checks=ALL")
print("   🔗 Ignore specific errors:")
print("      &skip_tls_checks=expired_cert,self_signed")
print("   🔗 Ignore multiple specific errors:")
print("      &skip_tls_checks=hostname_mismatch,cert_authority")

print("\n" + "=" * 60)
print("🎯 TLS skip_tls_checks test completed!")
print("=" * 60) 