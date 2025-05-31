#!/usr/bin/env python3

import requests
import argparse
import os

# Parse command line arguments or use environment variable
parser = argparse.ArgumentParser(description='Test TLS certificate logging functionality')
parser.add_argument('--port', type=int, 
                   default=int(os.environ.get('PROXY_PORT', 8080)),
                   help='Proxy server port (default: 8080, or PROXY_PORT env var)')
args = parser.parse_args()

print("=" * 70)
print("TLS CERTIFICATE LOGGING TEST - HOMIE PROXY")
print("=" * 70)

base_url = f"http://localhost:{args.port}/default?token=your-secret-token-here"

print(f"\nTesting proxy at localhost:{args.port}")
print("-" * 50)

print("\n🔒 Testing TLS certificate information logging")
print("-" * 50)

test_sites = [
    {
        'name': 'Google',
        'url': 'https://google.com',
        'description': 'Major CA certificate'
    },
    {
        'name': 'GitHub',
        'url': 'https://github.com',
        'description': 'DigiCert certificate'
    },
    {
        'name': 'HTTPBin (Cloudflare)',
        'url': 'https://httpbin.org/get',
        'description': 'Cloudflare certificate with SAN'
    },
    {
        'name': 'Apple',
        'url': 'https://apple.com',
        'description': 'Corporate certificate'
    }
]

for i, site in enumerate(test_sites, 1):
    print(f"\n🧪 Test {i}: {site['name']} ({site['description']})")
    print(f"🔗 URL: {site['url']}")
    print("-" * 40)
    
    # Test URL with TLS logging enabled
    test_url = f"{base_url}&url={site['url']}&log_tls_info=true"
    
    try:
        print("📥 Making request with TLS certificate logging...")
        print("🔍 Check server console for detailed certificate information!")
        
        response = requests.get(test_url, timeout=15)
        
        print(f"✅ Status: {response.status_code}")
        print(f"📥 Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        print(f"📊 Response size: {len(response.content)} bytes")
        
        if response.status_code == 200:
            print("✅ SUCCESS: Request completed - certificate info should be in server logs")
        else:
            print(f"⚠️  Got status {response.status_code} but TLS info should still be logged")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 Certificate info may still have been logged before the error")

print(f"\n🧪 Test 5: Self-signed certificate with TLS bypass")
print("🔗 URL: https://self-signed.badssl.com/")
print("-" * 40)

self_signed_url = f"{base_url}&url=https://self-signed.badssl.com/&log_tls_info=true&skip_tls_checks=all"
try:
    print("📥 Testing self-signed certificate with bypass...")
    response = requests.get(self_signed_url, timeout=15)
    
    print(f"✅ Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ SUCCESS: Self-signed cert accessed with certificate info logged")
    else:
        print(f"⚠️  Status {response.status_code} - certificate info should still be logged")
        
except Exception as e:
    print(f"❌ Error: {e}")

print(f"\n🧪 Test 6: Different port (HTTPS on non-standard port)")
print("🔗 URL: https://badssl.com:443/")
print("-" * 40)

port_test_url = f"{base_url}&url=https://badssl.com:443/&log_tls_info=true"
try:
    print("📥 Testing explicit port 443...")
    response = requests.get(port_test_url, timeout=15)
    
    print(f"✅ Status: {response.status_code}")
    print("✅ Certificate info should show port 443 explicitly")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n💡 What to look for in server console:")
print("🔒 TLS Certificate Info for [hostname]:[port]")
print("📋 Subject: [certificate subject/common name]")
print("🏢 Organization: [certificate organization]")
print("🌍 Country: [certificate country]")
print("📋 Issuer: [certificate authority name]")
print("📅 Valid From: [start date]")
print("📅 Valid Until: [expiry date]")
print("🌐 Alt Names: [subject alternative names]")
print("🔢 Serial: [certificate serial number]")
print("🔐 TLS Version: [TLS protocol version]")
print("🔐 Cipher Suite: [encryption cipher used]")
print("🔐 Key Bits: [key strength]")

print("\n📚 Usage Examples:")
print("🔗 Basic TLS logging:")
print("   &log_tls_info=true")
print("🔗 TLS logging with bypass:")
print("   &log_tls_info=true&skip_tls_checks=all")
print("🔗 TLS logging for specific errors:")
print("   &log_tls_info=true&skip_tls_checks=self_signed,expired_cert")

print("\n🎯 Benefits:")
print("✅ Debug TLS handshake issues")
print("✅ Verify certificate details and validity")
print("✅ Check subject alternative names (SAN)")
print("✅ Monitor cipher suites and TLS versions")
print("✅ Inspect certificate chains and issuers")

print("\n" + "=" * 70)
print("🎯 TLS certificate logging test completed!")
print("=" * 70) 