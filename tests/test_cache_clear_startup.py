#!/usr/bin/env python3

import json
import os
import requests
import time

print("=" * 60)
print("CACHE CLEAR ON STARTUP TEST")
print("=" * 60)

base_url = "http://localhost:8080/default?token=your-secret-token-here"

print("\nThis test demonstrates the clear_cache_on_start feature")
print("You need to manually edit proxy_config.json to test this feature")
print("-" * 60)

# Step 1: Check current cache status
print("\nStep 1: Check current cache status")
cache_dir = "cache"
if os.path.exists(cache_dir):
    cache_files = [f for f in os.listdir(cache_dir) if f.endswith('.cache')]
    print(f"Cache directory exists with {len(cache_files)} files")
else:
    print("Cache directory does not exist")

# Step 2: Create some cache entries
print("\nStep 2: Creating cache entries for testing...")
test_urls = [
    f"{base_url}&url=https://httpbin.org/uuid&cache=true",
    f"{base_url}&url=https://httpbin.org/json&cache=true",
    f"{base_url}&url=https://httpbin.org/headers&cache=true"
]

for i, url in enumerate(test_urls, 1):
    try:
        print(f"Creating cache entry {i}/3...")
        response = requests.get(url, timeout=8)
        cache_header = response.headers.get('X-Cache', 'MISS')
        print(f"  Status: {response.status_code}, Cache: {cache_header}")
    except Exception as e:
        print(f"  Error: {e}")

# Step 3: Check cache after creating entries
print("\nStep 3: Check cache after creating entries")
if os.path.exists(cache_dir):
    cache_files = [f for f in os.listdir(cache_dir) if f.endswith('.cache')]
    print(f"Cache directory now has {len(cache_files)} files")
    if cache_files:
        total_size = 0
        for filename in cache_files:
            filepath = os.path.join(cache_dir, filename)
            try:
                size = os.path.getsize(filepath)
                total_size += size
                print(f"  {filename} ({size} bytes)")
            except:
                pass
        print(f"Total cache size: {total_size} bytes ({total_size/1024:.1f} KB)")
else:
    print("Cache directory still does not exist")

# Step 4: Instructions for testing
print("\nStep 4: Testing clear_cache_on_start")
print("-" * 40)
print("To test the clear_cache_on_start feature:")
print()
print("1. Stop the reverse proxy server (Ctrl+C)")
print("2. Edit proxy_config.json and set:")
print('   "clear_cache_on_start": true,')
print("3. Restart the server: python reverse_proxy.py")
print("4. Check server console for cache clearing message")
print("5. Run this test again to verify cache was cleared")
print()
print("Example proxy_config.json with cache clearing enabled:")
print("-" * 50)

config_example = {
    "clear_cache_on_start": True,
    "instances": {
        "default": {
            "access_mode": "both",
            "tokens": ["your-secret-token-here"],
            "cache_enabled": True,
            "cache_ttl": 3600,
            "cache_max_size_mb": 0,
            "rate_limit": 100,
            "allowed_cidrs": []
        }
    }
}

print(json.dumps(config_example, indent=2))

print("\nExpected server console output when cache clearing is enabled:")
print("  'Cache cleared on startup: removed X files (Y.ZMB)'")
print("  or")  
print("  'Cache directory didn't exist, nothing to clear'")

print("\nTo disable cache clearing after testing:")
print('Set "clear_cache_on_start": false and restart the server')

print("\n" + "=" * 60)
print("Cache clear on startup test completed!")
print("=" * 60) 