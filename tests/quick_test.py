import requests
import json

print("Quick User-Agent test...")

# Test with no User-Agent 
session = requests.Session()
session.headers.pop('User-Agent', None)

try:
    response = session.get('http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/get')
    data = response.json()
    ua = data.get('headers', {}).get('User-Agent', 'NOT FOUND')
    print(f"No UA provided - Received: '{ua}'")
    print("SUCCESS!" if ua == '' else "FAILED!")
except Exception as e:
    print(f"Error: {e}")

# Test with custom User-Agent
try:
    response = requests.get('http://localhost:8080/default?token=your-secret-token-here&url=https://httpbin.org/get', 
                          headers={'User-Agent': 'TestAgent/1.0'})
    data = response.json()
    ua = data.get('headers', {}).get('User-Agent', 'NOT FOUND')
    print(f"Custom UA provided - Received: '{ua}'")
    print("SUCCESS!" if ua == 'TestAgent/1.0' else "FAILED!")
except Exception as e:
    print(f"Error: {e}") 