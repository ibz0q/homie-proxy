import requests
import sys
import os

# Test configuration
HOST = 'localhost'
PORT = '8123'
NAME = 'external-only-route'
TOKEN = '0061b276-ebab-4892-8c7b-13812084f5e9'
BASE_URL = f'http://{HOST}:{PORT}/api/homie_proxy/{NAME}'

print('🚀 HomieProxy Quick Test Suite')
print(f'Testing: {BASE_URL}')
print('=' * 50)

tests = [
    ('Basic GET', f'{BASE_URL}?token={TOKEN}&url=https://httpbin.org/get'),
    ('JSON Response', f'{BASE_URL}?token={TOKEN}&url=https://httpbin.org/json'),
    ('Host Header Override', f'{BASE_URL}?token={TOKEN}&url=https://httpbin.org/headers&request_header%5BHost%5D=custom.example.com'),
    ('User Agent', f'{BASE_URL}?token={TOKEN}&url=https://httpbin.org/user-agent'),
    ('Response Headers', f'{BASE_URL}?token={TOKEN}&url=https://httpbin.org/get&response_header%5BX-Test%5D=Works'),
    ('POST JSON', f'{BASE_URL}?token={TOKEN}&url=https://httpbin.org/post'),
    ('WebSocket Upgrade', f'{BASE_URL}?token={TOKEN}&url=wss://echo.websocket.org'),
]

passed = 0
total = len(tests)

for name, url in tests:
    try:
        if name == 'POST JSON':
            response = requests.post(url, json={'test': 'data'}, timeout=10)
        elif name == 'WebSocket Upgrade':
            # Test WebSocket upgrade request
            headers = {
                'Connection': 'upgrade',
                'Upgrade': 'websocket',
                'Sec-WebSocket-Key': 'dGhlIHNhbXBsZSBub25jZQ==',
                'Sec-WebSocket-Version': '13'
            }
            response = requests.get(url, headers=headers, timeout=10)
        else:
            response = requests.get(url, timeout=10)
            
        if response.status_code in [200, 101]:  # 101 for WebSocket upgrade
            print(f'✅ {name}: PASS (Status: {response.status_code})')
            passed += 1
        else:
            print(f'❌ {name}: FAIL (Status: {response.status_code})')
    except Exception as e:
        print(f'❌ {name}: ERROR - {e}')

print('=' * 50)
print(f'Results: {passed}/{total} tests passed')
if passed == total:
    print('🎉 All tests passed!')
else:
    print(f'⚠️  {total - passed} tests failed')

# Test different HTTP methods
print('\n🔧 Testing HTTP Methods...')
methods_passed = 0
methods_total = 5

method_tests = [
    ('GET', 'get'),
    ('POST', 'post'), 
    ('PUT', 'put'),
    ('PATCH', 'patch'),
    ('DELETE', 'delete')
]

for method_name, endpoint in method_tests:
    try:
        url = f'{BASE_URL}?token={TOKEN}&url=https://httpbin.org/{endpoint}'
        if method_name == 'GET':
            response = requests.get(url, timeout=10)
        elif method_name == 'POST':
            response = requests.post(url, json={'method': 'POST'}, timeout=10)
        elif method_name == 'PUT':
            response = requests.put(url, json={'method': 'PUT'}, timeout=10)
        elif method_name == 'PATCH':
            response = requests.patch(url, json={'method': 'PATCH'}, timeout=10)
        elif method_name == 'DELETE':
            response = requests.delete(url, timeout=10)
            
        if response.status_code == 200:
            print(f'✅ {method_name}: PASS')
            methods_passed += 1
        else:
            print(f'❌ {method_name}: FAIL (Status: {response.status_code})')
    except Exception as e:
        print(f'❌ {method_name}: ERROR - {e}')

print(f'HTTP Methods: {methods_passed}/{methods_total} passed')
print('\n🎯 Quick test completed!') 