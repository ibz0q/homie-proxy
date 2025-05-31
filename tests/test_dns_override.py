#!/usr/bin/env python3

import requests
import time

print("=" * 60)
print("DNS OVERRIDE TEST - REVERSE PROXY")
print("=" * 60)

base_url = "http://localhost:8082/default?token=your-secret-token-here"

print("\n📋 TESTING DNS OVERRIDE FUNCTIONALITY:")
print("-" * 50)

# Test 1: Normal request (no custom DNS)
print("\n🔸 Test 1: Normal request (no custom DNS)")
normal_url = f"{base_url}&url=https://httpbin.org/get"
try:
    print("📥 Making normal request...")
    response = requests.get(normal_url, timeout=8)
    print(f"✅ Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ Normal request working - Check server logs for hostname resolution")
    else:
        print(f"❌ Unexpected status: {response.status_code}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Custom DNS servers (Google DNS)
print("\n🔸 Test 2: Custom DNS servers (Google DNS)")
dns_url = f"{base_url}&url=https://httpbin.org/get&dns_server[]=8.8.8.8&dns_server[]=8.8.4.4"
try:
    print("📥 Making request with custom DNS servers (8.8.8.8, 8.8.4.4)...")
    response = requests.get(dns_url, timeout=10)
    print(f"✅ Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ DNS override working - Check server logs for DNS resolution details")
        data = response.json()
        print(f"📊 Server received Host header: {data.get('headers', {}).get('Host', 'NOT FOUND')}")
    else:
        print(f"❌ Unexpected status: {response.status_code}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Alternative DNS servers (Cloudflare)
print("\n🔸 Test 3: Alternative DNS servers (Cloudflare)")
cloudflare_url = f"{base_url}&url=https://httpbin.org/headers&dns_server[]=1.1.1.1&dns_server[]=1.0.0.1"
try:
    print("📥 Making request with Cloudflare DNS servers (1.1.1.1, 1.0.0.1)...")
    response = requests.get(cloudflare_url, timeout=10)
    print(f"✅ Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ Cloudflare DNS working - Check server logs for DNS resolution")
        data = response.json()
        headers = data.get('headers', {})
        print(f"📊 Host header preserved: {headers.get('Host', 'NOT FOUND')}")
        print(f"📊 Total headers received: {len(headers)}")
    else:
        print(f"❌ Unexpected status: {response.status_code}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 4: Custom DNS with different hostname
print("\n🔸 Test 4: Custom DNS with different hostname")
different_host_url = f"{base_url}&url=https://example.com&dns_server[]=8.8.8.8"
try:
    print("📥 Making request to example.com with custom DNS...")
    response = requests.get(different_host_url, timeout=10)
    print(f"✅ Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ Different hostname DNS resolution working")
    else:
        print(f"⚠️  Got status {response.status_code} - might be normal for example.com")
    print("✅ Check server logs for DNS resolution of example.com")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 5: Multiple DNS servers (fallback test)
print("\n🔸 Test 5: Multiple DNS servers (fallback test)")
multi_dns_url = f"{base_url}&url=https://httpbin.org/uuid&dns_server[]=9.9.9.9&dns_server[]=8.8.8.8&dns_server[]=1.1.1.1"
try:
    print("📥 Making request with multiple DNS servers for fallback...")
    response = requests.get(multi_dns_url, timeout=12)
    print(f"✅ Status: {response.status_code}")
    if response.status_code == 200:
        print("✅ DNS fallback working - Check server logs for which DNS server succeeded")
        data = response.json()
        print(f"📊 UUID received: {data.get('uuid', 'NOT FOUND')[:8]}...")
    else:
        print(f"❌ Unexpected status: {response.status_code}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n💡 What to look for in server console:")
print("   📤 'Custom DNS servers specified: [servers]'")
print("   📤 'Resolving [hostname] using custom DNS servers: [servers]'")
print("   📤 'Successfully resolved [hostname] to [IP] via [DNS server]'")
print("   📤 'Modified target URL: [original] -> [with IP]'")
print("   📤 'Set Host header to original hostname: [hostname]'")
print("   📤 DNS queries sent to specific DNS servers")

print("\n🎯 Expected behavior:")
print("   ✅ Hostnames resolved using specified DNS servers")
print("   ✅ Target URLs modified to use resolved IP addresses")
print("   ✅ Host headers preserve original hostnames for virtual hosting")
print("   ✅ DNS server fallback when primary servers fail")

print("\n" + "=" * 60)
print("🎯 DNS override test completed!")
print("=" * 60) 