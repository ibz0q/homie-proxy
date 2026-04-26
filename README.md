# HomieProxy

A configurable HTTP reverse proxy for Home Assistant. Lets browser-based clients reach devices and APIs that would otherwise be blocked by CORS or network boundaries — with token authentication and per-instance access control.

```
/api/homie_proxy/<instance-name>?token=TOKEN&url=TARGET_URL
```

---

## Parameters

| Parameter | Required | Description |
|-----------|----------|-------------|
| `token` | ✓ | Authentication token configured on the instance |
| `url` | ✓ | Full target URL to proxy |
| `timeout` | | Override request timeout in seconds |
| `follow_redirects` | | Set to `true` to follow 3xx redirects (default: pass them back) |
| `skip_tls_checks` | | Comma-separated TLS checks to skip |
| `cors_preflight` | | Set to `1` to short-circuit an OPTIONS preflight with a 204 |
| `request_header[NAME]` | | Inject a header into the upstream request |
| `response_header[NAME]` | | Attach a header to the response returned to the caller |

**`skip_tls_checks` values:** `all` · `self_signed` · `expired_cert` · `hostname_mismatch` · `cert_authority`

> From a browser: URL-encode `[` → `%5B`, `]` → `%5D`, or use `URLSearchParams` to handle it automatically.

---

## Examples

### Basic GET

```bash
curl "http://localhost:8123/api/homie_proxy/my-route?token=abc-123&url=https://192.168.1.50/api/status"
```

### POST with JSON body

```bash
curl -X POST "http://localhost:8123/api/homie_proxy/my-route?token=abc-123&url=http://192.168.1.50/api/preset" \
     -H "Content-Type: application/json" \
     -d '{"preset": 1}'
```

### Inject headers into the upstream request

```bash
# Add an Authorization header the upstream requires
curl "http://localhost:8123/api/homie_proxy/my-route?token=abc-123&url=https://api.example.com/data\
&request_header%5BAuthorization%5D=Bearer%20upstream-secret"

# Override the Host header — required by many cameras and embedded devices
curl "http://localhost:8123/api/homie_proxy/my-route?token=abc-123&url=http://192.168.1.50/api\
&request_header%5BHost%5D=camera.local"
```

### Inject headers into the response

```bash
# Add CORS headers so a browser script can read the response
curl "http://localhost:8123/api/homie_proxy/my-route?token=abc-123&url=http://192.168.1.50/status\
&response_header%5BAccess-Control-Allow-Origin%5D=*"
```

Response headers are also applied to error responses from the proxy (4xx/5xx), so the browser always gets its CORS header and sees the real error message rather than a generic CORS failure.

### CORS preflight (OPTIONS short-circuit)

When a browser makes a cross-origin request it first sends an OPTIONS preflight. Short-circuit it without hitting the upstream:

```bash
curl -X OPTIONS "http://localhost:8123/api/homie_proxy/my-route?token=abc-123&url=http://192.168.1.50/api\
&cors_preflight=1\
&response_header%5BAccess-Control-Allow-Origin%5D=*\
&response_header%5BAccess-Control-Allow-Methods%5D=GET,%20POST,%20PUT\
&response_header%5BAccess-Control-Allow-Headers%5D=Content-Type"
# → 204 No Content with the requested headers
```

Without `cors_preflight=1`, OPTIONS is forwarded to the upstream normally.

### TLS bypass for self-signed / expired certificates

```bash
# Skip all checks (cameras, NVRs, old firmware)
curl "http://localhost:8123/api/homie_proxy/my-route?token=abc-123&url=https://192.168.1.50/api\
&skip_tls_checks=all"

# More targeted — skip only self-signed and expired
curl "http://localhost:8123/api/homie_proxy/my-route?token=abc-123&url=https://192.168.1.50/api\
&skip_tls_checks=self_signed,expired_cert"
```

### Redirects

```bash
# Default: 3xx is returned as-is to the caller
curl -D - "http://localhost:8123/api/homie_proxy/my-route?token=abc-123&url=https://example.com/moved"
# HTTP/1.1 302 Found

# Tell the proxy to follow redirects and return the final response
curl "http://localhost:8123/api/homie_proxy/my-route?token=abc-123\
&url=https://example.com/moved&follow_redirects=true"
```

### Per-request timeout

```bash
# Give a slow export endpoint extra time
curl "http://localhost:8123/api/homie_proxy/my-route?token=abc-123\
&url=https://slow.example.com/export.json&timeout=900"

# Liveness check — fail fast
curl "http://localhost:8123/api/homie_proxy/my-route?token=abc-123\
&url=https://api.example.com/ping&timeout=3"
# → 504 if upstream doesn't reply within 3 s
```

### Streaming and large files

No special parameter needed — the proxy streams chunks, never buffers the full response.

```bash
# Download a large file
curl "http://localhost:8123/api/homie_proxy/my-route?token=abc-123&url=https://example.com/video.mp4" \
     -o video.mp4

# MJPEG camera stream
curl "http://localhost:8123/api/homie_proxy/my-route?token=abc-123&url=http://192.168.1.50/video.cgi" \
     --output -
```

### WebSocket

```bash
wscat -c "ws://localhost:8123/api/homie_proxy/my-route?token=abc-123&url=ws://192.168.1.50/ws"

# wss:// with a self-signed cert
wscat -c "ws://localhost:8123/api/homie_proxy/my-route?token=abc-123\
&url=wss://192.168.1.50/ws&skip_tls_checks=all"
```

### JavaScript fetch

`URLSearchParams` handles the bracket encoding automatically:

```javascript
const BASE = "http://localhost:8123/api/homie_proxy/my-route";

async function proxyFetch(targetUrl, options = {}) {
  const params = new URLSearchParams({
    token: "abc-123",
    url:   targetUrl,
    "response_header[Access-Control-Allow-Origin]": "*",
  });

  if (options.timeout)         params.set("timeout", options.timeout);
  if (options.followRedirects) params.set("follow_redirects", "true");
  if (options.skipTls)         params.set("skip_tls_checks", options.skipTls);

  for (const [k, v] of Object.entries(options.requestHeaders ?? {})) {
    params.set(`request_header[${k}]`, v);
  }

  return fetch(`${BASE}?${params}`, {
    method: options.method ?? "GET",
    body:   options.body,
  });
}

// GET
const status = await proxyFetch("http://192.168.1.50/api/status");

// POST JSON to a device with a self-signed cert
const result = await proxyFetch("https://192.168.1.50/api/preset", {
  method: "POST",
  body:   JSON.stringify({ preset: 1 }),
  requestHeaders: { "Content-Type": "application/json" },
  skipTls: "self_signed",
});
```

---

## Instance settings

Each entry added through the integration UI creates one proxy instance — one URL path segment.

| Setting | Values | Default | Description |
|---------|--------|---------|-------------|
| **Name** | string | `external-api-route` | Path: `/api/homie_proxy/<name>` |
| **Tokens** | list | auto-generated UUID | One or more tokens; any one is accepted |
| **Outbound access** | `any` / `external` / `internal` / `custom` | `any` | Which destinations are reachable |
| **Custom CIDRs** | CIDR list | — | Allowed destination ranges when mode is `custom` |
| **Inbound access** | CIDR list | — | Restrict which client IPs may call this instance (empty = any) |
| **Require HA auth** | bool | `true` | Also require a valid HA session |
| **Timeout** | 30–3600 s | 300 | Default upstream timeout (overridable per-request) |

### Outbound access modes

| Mode | Behaviour |
|------|-----------|
| `any` | No restriction |
| `external` | Public IPs only — blocks RFC 1918, loopback (`127.x`), link-local (`169.254.x`) |
| `internal` | Private/loopback only — blocks the public internet |
| `custom` | Only the CIDRs you list |

Token authentication always runs before access checks — an unauthenticated caller always gets 401, never a 403 that would reveal which destinations are blocked.

---

## Debug endpoint

Returns all configured instances and their settings. No token required (HA session auth still applies).

```
GET /api/homie_proxy/debug
```

---

## Error responses

All proxy errors return JSON:

```json
{ "error": "human-readable message", "code": 401 }
```

| Code | Cause |
|------|-------|
| `400` | `url` parameter missing or malformed |
| `401` | Token missing or wrong |
| `403` | Client IP blocked (inbound) or target URL blocked (outbound) |
| `502` | Upstream unreachable — connection refused or DNS failure |
| `504` | Upstream did not reply within the timeout |

---

## Installation

### HACS (recommended)

1. HACS → Integrations → ⋮ → **Custom repositories**
2. Add `https://github.com/ibz0q/homie-proxy`, category **Integration**
3. Install **HomieProxy**, restart Home Assistant
4. **Settings → Integrations → Add Integration → HomieProxy**

### Manual

Copy `custom_components/homie_proxy/` into your HA config's `custom_components/` directory, restart, then add the integration as above.

### Standalone server

```bash
cd homie-proxy/standalone_homie-proxy
pip install -r requirements.txt
python homie_proxy.py --config proxy_config.json --port 8080
```

Replace `http://localhost:8123/api/homie_proxy` with `http://localhost:8080` in all examples above.

---

## Development

```bash
cd homie-proxy
pip install pytest pytest-asyncio pytest-aiohttp aiohttp
pytest tests/ -v
```

Open in VS Code and reopen in the devcontainer for a pre-configured HA instance at `http://localhost:8123`.
