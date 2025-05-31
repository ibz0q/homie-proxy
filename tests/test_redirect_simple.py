#!/usr/bin/env python3

import subprocess
import json

print("=" * 60)
print("REDIRECT FOLLOWING TEST - REVERSE PROXY")
print("=" * 60)

base_url = "http://localhost:8080/default?token=your-secret-token-here"

def run_curl(url, follow_client_redirects=False):
    """Run curl command and return response"""
    cmd = ["curl", "-s"]
    if not follow_client_redirects:
        cmd.append("--max-redirs")
        cmd.append("0")
    cmd.append(url)
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"

print("\nTest 1: Default behavior (redirects NOT followed by proxy)")
print("-" * 50)
url1 = f"{base_url}&url=https://httpbin.org/redirect/1"
code, stdout, stderr = run_curl(url1)
print(f"URL: {url1}")
print(f"Exit code: {code}")
if "Redirecting..." in stdout:
    print("SUCCESS: Proxy returned redirect response (not followed)")
    print("Response contains redirect HTML page")
else:
    print("Response preview:", stdout[:200])

print("\nTest 2: Redirect following enabled")
print("-" * 50)
url2 = f"{base_url}&url=https://httpbin.org/redirect/1&follow_redirects=true"
code, stdout, stderr = run_curl(url2)
print(f"URL: {url2}")
print(f"Exit code: {code}")
try:
    data = json.loads(stdout)
    if 'args' in data and 'headers' in data:
        print("SUCCESS: Proxy followed redirect and returned final JSON response")
        print(f"Final URL was httpbin.org/get (confirmed by JSON structure)")
    else:
        print("Response is not the expected JSON format")
except json.JSONDecodeError:
    print("Response is not JSON:", stdout[:200])

print("\nTest 3: Multiple redirects")
print("-" * 50)
url3 = f"{base_url}&url=https://httpbin.org/redirect/3&follow_redirects=true"
code, stdout, stderr = run_curl(url3)
print(f"URL: {url3}")
print(f"Exit code: {code}")
try:
    data = json.loads(stdout)
    if 'args' in data and 'headers' in data:
        print("SUCCESS: Proxy followed multiple redirects successfully")
    else:
        print("Unexpected response format")
except json.JSONDecodeError:
    print("Response is not JSON:", stdout[:200])

print("\nTest 4: Different parameter values")
print("-" * 50)
test_values = ['1', 'yes', 'TRUE']
for value in test_values:
    url = f"{base_url}&url=https://httpbin.org/redirect/1&follow_redirects={value}"
    code, stdout, stderr = run_curl(url)
    try:
        data = json.loads(stdout)
        if 'args' in data:
            print(f"SUCCESS: follow_redirects={value} works")
        else:
            print(f"FAILED: follow_redirects={value}")
    except:
        print(f"FAILED: follow_redirects={value} (not JSON)")

print("\nTest 5: Verify logging")
print("-" * 50)
print("Check server console for these log messages:")
print("- 'Redirect following enabled' when follow_redirects=true")
print("- 'Redirect following disabled (default)' when not specified")

print("\n" + "=" * 60)
print("Redirect test completed!")
print("=" * 60) 