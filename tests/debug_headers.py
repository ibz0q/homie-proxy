#!/usr/bin/env python3

import requests
import json

print("=" * 60)
print("DEBUG: HEADER INSPECTION")
print("=" * 60)

# Test what happens when we send no User-Agent at all
print("\n🔍 Testing header removal...")

# Create a session and see what default headers it has
session = requests.Session()
print(f"Default session headers: {dict(session.headers)}")

# Remove User-Agent
session.headers.pop('User-Agent', None)
print(f"After removing User-Agent: {dict(session.headers)}")

# Test direct request to see what headers httpbin receives
print(f"\n🔍 Direct test to httpbin...")
try:
    response = session.get('https://httpbin.org/get')
    data = response.json()
    print(f"Headers received by httpbin:")
    for header, value in data.get('headers', {}).items():
        print(f"  {header}: {value}")
except Exception as e:
    print(f"Error: {e}")

# Test with explicit blank User-Agent
print(f"\n🔍 With explicit blank User-Agent...")
try:
    response = session.get('https://httpbin.org/get', headers={'User-Agent': ''})
    data = response.json()
    received_ua = data.get('headers', {}).get('User-Agent', 'NOT FOUND')
    print(f"User-Agent received: '{received_ua}'")
except Exception as e:
    print(f"Error: {e}")

# Test what urllib3 is doing
print(f"\n🔍 Testing urllib3 directly...")
try:
    import urllib3
    http = urllib3.PoolManager()
    response = http.request('GET', 'https://httpbin.org/get', headers={'User-Agent': ''})
    data = json.loads(response.data.decode('utf-8'))
    received_ua = data.get('headers', {}).get('User-Agent', 'NOT FOUND')
    print(f"urllib3 User-Agent received: '{received_ua}'")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60) 