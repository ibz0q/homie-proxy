# HomieProxy

A configurable HTTP reverse proxy for Home Assistant. Lets browser-based clients (or anything that can make HTTP requests) reach targets that would otherwise be blocked by CORS or network topology — with token authentication and per-instance access control.

## Installation

### HACS (recommended)

1. Open HACS → **Integrations** → ⋮ menu → **Custom repositories**
2. Add this repository URL, category **Integration**
3. Search for **HomieProxy** and install
4. Restart Home Assistant
5. **Settings → Integrations → Add Integration → HomieProxy**

### Manual

Copy `custom_components/homie_proxy/` into your HA config's `custom_components/` directory, restart, then add the integration as above.

---

## Quick start

```
http://localhost:8123/api/homie_proxy/<instance-name>?token=TOKEN&url=TARGET_URL
```

Example:
```bash
curl "http://localhost:8123/api/homie_proxy/my-route?token=abc-123&url=https://192.168.1.50/api/status"
```

---

## Query parameters

### Required

| Parameter | Description |
|-----------|-------------|
| `token` | Authentication token configured on the instance |
| `url` | Full target URL to proxy to |

### Optional

| Parameter | Default | Description |
|-----------|---------|-------------|
| `timeout` | instance default | Override request timeout in seconds |
| `follow_redirects` | `false` | Set to `true` to follow 3xx redirects |
| `skip_tls_checks` | — | Comma-separated TLS checks to skip (see below) |
| `cors_preflight` | — | Set to `1` to short-circuit an OPTIONS preflight (returns 204) |

### Header injection

**Outbound request headers** — forwarded to the target:
```
request_header[Host]=camera.local
request_header[Authorization]=Bearer abc123
request_header[X-Custom]=value
```

**Response headers** — added to the response returned to the caller:
```
response_header[Access-Control-Allow-Origin]=*
response_header[X-My-Header]=custom-value
```

> When making requests from a browser, URL-encode `[` as `%5B` and `]` as `%5D`.

### TLS skip options

Pass one or more values, comma-separated, in `skip_tls_checks`:

| Value | Effect |
|-------|--------|
| `all` | Disable all TLS verification |
| `hostname_mismatch` | Skip hostname verification |
| `expired_cert` | Skip expiry check |
| `self_signed` | Skip self-signed check |
| `cert_authority` | Skip CA validation |

Example: `skip_tls_checks=self_signed,expired_cert`

---

## Instance configuration

Each integration entry represents one proxy instance (one URL path segment).

| Setting | Values | Default | Description |
|---------|--------|---------|-------------|
| **Name** | string | `external-api-route` | URL path segment: `/api/homie_proxy/<name>` |
| **Tokens** | list | auto-generated UUID | One or more bearer tokens |
| **Outbound access** | `any` / `external` / `internal` / `custom` | `any` | Which destinations are reachable |
| **Custom CIDRs** | CIDR list | — | Allowed destination ranges when mode is `custom` |
| **Inbound access** | CIDR list | — | Restrict which client IPs may call this instance (empty = any) |
| **Require HA auth** | bool | `true` | Also require a valid HA session cookie / token |
| **Timeout** | 30–3600 s | 300 | Per-request upstream timeout |

### Outbound access modes

| Mode | Allows |
|------|--------|
| `any` | Everything |
| `external` | Public IPs only (blocks RFC 1918, loopback, link-local) |
| `internal` | Private/loopback IPs only (blocks public internet) |
| `custom` | Only the CIDR ranges you specify |

---

## Debug endpoint

Lists all configured instances and their settings (no token required, but HA session auth applies):

```
GET /api/homie_proxy/debug
```

---

## Development

The repo also contains a **standalone server** (`homie-proxy/standalone_homie-proxy/`) for running outside Home Assistant, and a full pytest suite.

### Run tests

```bash
cd homie-proxy
pip install pytest pytest-asyncio pytest-aiohttp aiohttp
pytest tests/ -v
```

Tests run entirely in-process — no live server or internet connection required.

### DevContainer

Open the `homie-proxy/` folder in VS Code and reopen in the devcontainer. Home Assistant starts automatically at `http://localhost:8123`.
