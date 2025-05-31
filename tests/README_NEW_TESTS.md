# HomieProxy Comprehensive Test Suite

This directory contains comprehensive tests for the HomieProxy Home Assistant integration, including the new tests for WebSocket support, redirect following, HTTP methods, and performance scenarios.

## New Test Files

### 🚀 Core Test Suite

1. **`test_http_methods.py`** - Tests all supported HTTP methods
   - GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS
   - Form data, JSON data, raw data handling
   - Large request bodies
   - Custom headers preservation

2. **`test_follow_redirects.py`** - Comprehensive redirect testing
   - Basic redirect following (on/off)
   - Multiple redirects (2, 3, 5 hops)
   - Different redirect status codes (301, 302, 303, 307, 308)
   - Parameter variations ('true', '1', 'yes', etc.)
   - POST redirects
   - Header preservation through redirects
   - Redirect limits

3. **`test_websocket.py`** - WebSocket proxy functionality
   - Echo testing through proxy
   - Binary message handling
   - Authentication failures
   - TLS bypass for WebSocket connections
   - Custom headers
   - HTTP to WebSocket upgrade handling

4. **`test_streaming_performance.py`** - Streaming and performance tests
   - Streaming response handling
   - Large response processing
   - Concurrent request handling
   - Timeout scenarios
   - Binary content (images)
   - Response header preservation
   - Compression handling (gzip)

### 🏃‍♂️ Test Runner

**`run_all_tests.py`** - Master test runner
- Runs all comprehensive tests in sequence
- Provides summary and detailed results
- Handles timeouts and failures gracefully
- Includes optional existing tests

## Code Improvements

### ✨ Simplified View Methods

The repetitive HTTP method handlers in `HomieProxyView` have been simplified from:

```python
async def get(self, request: Request) -> web.Response:
    return await self.handler.handle_request(request, "GET")

async def post(self, request: Request) -> web.Response:
    return await self.handler.handle_request(request, "POST")
# ... and 4 more similar methods
```

**To:**

```python
async def _handle(self, request: Request, **kwargs) -> web.Response:
    """Handle all HTTP methods and WebSocket upgrades."""
    method = request.method.upper()
    return await self.handler.handle_request(request, method)
```

This eliminates ~25 lines of repetitive code while maintaining full functionality.

## Running the Tests

### Prerequisites

1. **Home Assistant** running at `localhost:8123`
2. **HomieProxy integration** installed and configured
3. **Default instance** configured with token `your-secret-token-here`
4. **Internet connection** for testing external services

### Run Individual Tests

```bash
# Test HTTP methods
python tests/test_http_methods.py

# Test redirect following
python tests/test_follow_redirects.py

# Test WebSocket functionality
python tests/test_websocket.py

# Test streaming and performance
python tests/test_streaming_performance.py
```

### Run All Tests

```bash
# Run the complete test suite
python tests/run_all_tests.py
```

## Test Coverage

### HTTP Methods ✅
- ✅ GET requests with custom headers
- ✅ POST with JSON, form data, and raw data
- ✅ PUT operations
- ✅ PATCH operations  
- ✅ DELETE requests
- ✅ HEAD requests (headers only)
- ✅ OPTIONS requests
- ✅ Large request bodies (1MB+)

### Redirect Following ✅
- ✅ Default behavior (no following)
- ✅ Basic redirect following
- ✅ Multiple redirects (2-5 hops)
- ✅ Different status codes (301-308)
- ✅ Parameter variations
- ✅ POST method redirects
- ✅ Header preservation
- ✅ Redirect limits

### WebSocket Support ✅
- ✅ Basic echo functionality
- ✅ Binary message handling
- ✅ Authentication validation
- ✅ TLS bypass options
- ✅ Custom headers
- ✅ Connection upgrade handling

### Performance & Streaming ✅
- ✅ Streaming responses
- ✅ Large responses
- ✅ Concurrent requests (5 threads)
- ✅ Timeout handling
- ✅ Binary content (images)
- ✅ Header preservation
- ✅ Compression (gzip)

### Error Handling ✅
- ✅ Authentication failures
- ✅ Network restrictions
- ✅ Timeout scenarios
- ✅ Invalid URLs
- ✅ TLS certificate issues

## Test Services Used

- **httpbin.org** - HTTP testing service
- **echo.websocket.org** - WebSocket echo service
- **Various endpoints** for specific functionality testing

## Expected Test Duration

- Individual tests: 30-120 seconds each
- Full test suite: 5-10 minutes
- Includes network-dependent operations

## Troubleshooting

### Common Issues

1. **Connection refused** - Check Home Assistant is running
2. **401 Unauthorized** - Verify token configuration
3. **Timeout errors** - Check internet connection
4. **WebSocket failures** - Ensure WebSocket support is enabled

### Debug Mode

Add verbose logging by modifying the proxy service logging level in Home Assistant's `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.homie_proxy: debug
```

## Integration with Existing Tests

The new tests complement the existing test files:
- `test_proxy.py` - Original comprehensive test
- `test_access_control.py` - Network access controls
- `test_tls_*.py` - TLS/SSL testing
- `test_*_headers.py` - Header handling tests

All tests can be run together using `run_all_tests.py` which automatically detects and includes existing tests. 