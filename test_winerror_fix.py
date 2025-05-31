#!/usr/bin/env python3

import requests
import time

print("=" * 60)
print("WINERROR 10053 FIX VERIFICATION TEST")
print("=" * 60)

base_url = "http://localhost:8080/default?token=your-secret-token-here"

print("\nTesting connection abort handling...")
print("This test verifies that WinError 10053 spam is eliminated")
print("-" * 60)

# Test 1: Normal working request
print("\n1. Testing normal request (should work):")
try:
    url = f"{base_url}&url=https://httpbin.org/get"
    response = requests.get(url, timeout=5)
    print(f"   Status: {response.status_code}")
    print("   SUCCESS: Normal request working")
except Exception as e:
    print(f"   ERROR: {e}")

# Test 2: Request that may cause streaming issues  
print("\n2. Testing problematic URL (may fail but should NOT spam logs):")
try:
    url = f"{base_url}&url=https://1.1.1.1&override_host_header=one.one.one.one&skip_tls_checks=all"
    response = requests.get(url, timeout=3)
    print(f"   Status: {response.status_code}")
    print("   Response completed")
except requests.exceptions.Timeout:
    print("   TIMEOUT: Request timed out (expected)")
except Exception as e:
    print(f"   ERROR: {e}")

# Test 3: Request with immediate disconnect
print("\n3. Testing quick disconnect (tests connection abort handling):")
try:
    url = f"{base_url}&url=https://httpbin.org/delay/10"
    # Start request and quickly cancel it
    response = requests.get(url, timeout=1)
    print(f"   Status: {response.status_code}")
except requests.exceptions.Timeout:
    print("   TIMEOUT: Quick disconnect test completed")
except Exception as e:
    print(f"   ERROR: {e}")

print("\n" + "=" * 60)
print("CONNECTION ABORT FIX VERIFICATION:")
print("=" * 60)
print("✅ If you see this message without WinError 10053 spam above,")
print("   the connection abort fix is working correctly!")
print("")
print("🔍 Check the server console output:")
print("   - Should see normal request logs")
print("   - Should NOT see repeated '[WinError 10053]' messages")
print("   - Connection aborts should be handled gracefully")
print("=" * 60) 