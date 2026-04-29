#!/usr/bin/env python3
"""
Homie Proxy Server
Minimal dependencies, configurable instances with authentication and restrictions.

This module can be used both as a standalone script and as an importable module.

Example usage as a module:
    from homie_proxy import HomieProxyServer, ProxyInstance
    
    # Create and configure server
    server = HomieProxyServer('my_config.json')
    
    # Run server
    server.run(host='localhost', port=8080)

Example programmatic configuration:
    from homie_proxy import HomieProxyServer, create_proxy_config
    
    # Create configuration programmatically
    config = create_proxy_config({
        'default': {
            'restrict_out': 'both',
            'tokens': ['my-token'],
            'restrict_in_cidrs': []
        }
    })
    
    # Create server with config
    server = HomieProxyServer()
    server.instances = config
    server.run()
"""

import hmac
import json
import ipaddress
import logging
import re
import ssl
import urllib.parse
import asyncio
import aiohttp
from aiohttp import web
from datetime import datetime
from typing import Dict, List, Optional
import socket
import os
import time

_LOGGER = logging.getLogger(__name__)


# ─── Security limits & defensive constants ───────────────────────────────────

# Mirror of custom_components/homie_proxy/const.py PRIVATE_CIDRS. Kept here so
# the standalone module has zero internal dependencies. If you change one,
# change the other (or extract a shared `homie_proxy_common` package).
PRIVATE_CIDRS = [
    "0.0.0.0/8",        # RFC 1122 "this network" — routes to localhost on Linux
    "10.0.0.0/8",       # RFC 1918
    "172.16.0.0/12",    # RFC 1918
    "192.168.0.0/16",   # RFC 1918
    "127.0.0.0/8",      # IPv4 loopback
    "169.254.0.0/16",   # IPv4 link-local — covers cloud metadata 169.254.169.254
    "100.64.0.0/10",    # CGNAT (RFC 6598)
    "::/128",           # IPv6 unspecified
    "::1/128",          # IPv6 loopback
    "fe80::/10",        # IPv6 link-local
    "fc00::/7",         # IPv6 ULA (RFC 4193)
]
_PRIVATE_NETWORKS = [ipaddress.ip_network(c) for c in PRIVATE_CIDRS]

_ALLOWED_SCHEMES = frozenset({"http", "https", "ws", "wss"})

MAX_REDIRECT_HOPS = 5

# Default stream chunk size.
#
#   0       → use ``resp.content.iter_any()`` — yields whatever arrived in
#             the socket buffer right now, no accumulation. THIS IS THE
#             RIGHT DEFAULT for live MJPEG / HLS / any latency-sensitive
#             stream: a fixed-size bucket coalesces multiple frames into
#             one write, which the downstream player then displays in
#             bursts → visibly choppy video.
#   N > 0   → use ``iter_chunked(N)``. Buffers up to N bytes before yielding.
#             Higher throughput / fewer event-loop wakeups, but introduces
#             latency proportional to N / bitrate. Useful for bulk transfers
#             but wrong for live streams.
#
# Per-instance default; can be overridden per-request via
# ``?stream_chunk_size=N`` query param.
DEFAULT_STREAM_CHUNK_SIZE = 0

# Legacy name kept for any external importers. NOT used internally.
STREAM_CHUNK_SIZE = 64 * 1024

# Per-process DNS cache for outbound-policy checks. See HA proxy.py for the
# detailed rationale; keep DNS_CACHE_TTL in sync between the two modules.
DNS_CACHE_TTL = 30.0
_DNS_CACHE: "Dict[str, tuple]" = {}

_REDACT_QS_RE = re.compile(
    r"(?i)(?P<key>token|password|secret|api[_-]?key)=[^&\s]*"
)


def _redact_url(url: str) -> str:
    if not url:
        return url
    return _REDACT_QS_RE.sub(r"\g<key>=***", url)


def _mask_token(token: str) -> str:
    if not token or len(token) <= 4:
        return "***"
    return f"{token[:4]}***"


async def _resolve_cached(hostname: str) -> Optional[List[str]]:
    """Resolve *hostname* to a list of IP-literal strings, with TTL caching.

    Returns None on resolution failure (caller fails closed). Negative
    results are NOT cached — a transient DNS failure shouldn't darken
    an endpoint for 30 seconds.
    """
    now = time.monotonic()
    entry = _DNS_CACHE.get(hostname)
    if entry is not None:
        ts, addrs = entry
        if now - ts < DNS_CACHE_TTL:
            return addrs

    loop = asyncio.get_running_loop()
    try:
        info = await loop.getaddrinfo(
            hostname, None, type=socket.SOCK_STREAM,
        )
    except OSError:
        return None
    if not info:
        return None

    addrs: List[str] = []
    for entry_t in info:
        try:
            addrs.append(entry_t[4][0])
        except (IndexError, TypeError):
            return None
    if not addrs:
        return None

    _DNS_CACHE[hostname] = (now, addrs)
    return addrs


def _dns_cache_clear() -> None:
    """Test hook — clear the DNS cache between tests."""
    _DNS_CACHE.clear()


def _disable_nagle(request: web.Request) -> None:
    """Set TCP_NODELAY on the inbound (client-facing) socket.

    Without this the kernel's Nagle algorithm coalesces small writes and
    delivery can stall up to ~40 ms (Nagle + delayed-ACK interaction). For
    live MJPEG / HLS that stacks on top of any upstream-side buffering and
    produces visibly choppy video.

    Best-effort: silently no-ops if the transport doesn't expose a real
    TCP socket (unix sockets, mock transports in tests, already closed)."""
    try:
        transport = request.transport
        if transport is None:
            return
        sock = transport.get_extra_info("socket")
        if sock is None:
            return
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    except (OSError, AttributeError):
        pass

# `websockets` is required for WebSocket proxying. We import it defensively so
# the rest of the proxy still loads if it's missing (HTTP-only mode); upgrade
# requests then fail with a clear 501.
try:
    import websockets
    from websockets.exceptions import WebSocketException
except ImportError:
    print(
        "Warning: 'websockets' library not found. HTTP proxying will work; "
        "any WebSocket upgrade request will return HTTP 501. Install with "
        "`pip install websockets` to enable WebSocket proxying."
    )
    websockets = None

    class WebSocketException(Exception):  # noqa: N818 — match upstream name
        """Stand-in so handlers can `except WebSocketException` unconditionally."""

# Module exports for when used as an import
__all__ = [
    'HomieProxyServer',
    'ProxyInstance', 
    'HomieProxyRequestHandler',
    'create_proxy_config',
    'create_default_config'
]

def create_proxy_config(instances_dict: Dict) -> Dict[str, 'ProxyInstance']:
    """
    Create proxy instances from a configuration dictionary.
    
    Args:
        instances_dict: Dictionary mapping instance names to configuration dicts
        
    Returns:
        Dictionary mapping instance names to ProxyInstance objects
        
    Example:
        config = create_proxy_config({
            'api': {
                'restrict_out': 'external',
                'tokens': ['api-key-123'],
                'restrict_in_cidrs': ['192.168.1.0/24']
            },
            'internal': {
                'restrict_out': 'internal',
                'tokens': [],
                'restrict_in_cidrs': []
            }
        })
    """
    instances = {}
    for name, config in instances_dict.items():
        instances[name] = ProxyInstance(name, config)
    return instances

def create_default_config() -> Dict:
    """
    Create a default configuration dictionary.
    
    Returns:
        Default configuration dictionary
    """
    # NOTE: every instance MUST have at least one token. As of the security
    # hardening pass, an instance with an empty `tokens` list rejects every
    # request with 401 (was: allowed all requests). Replace the placeholders
    # below before exposing the proxy to anything.
    import uuid
    return {
        "instances": {
            "default": {
                "restrict_out": "both",
                "tokens": [str(uuid.uuid4())],
                "restrict_in_cidrs": [],
                "timeout": 300
            },
            "internal-only": {
                "restrict_out": "internal",
                "tokens": [str(uuid.uuid4())],
                "restrict_in_cidrs": [],
                "timeout": 300
            },
            "custom-networks": {
                "restrict_out": "both",
                "restrict_out_cidrs": ["8.8.8.0/24", "1.1.1.0/24"],
                "tokens": [str(uuid.uuid4())],
                "restrict_in_cidrs": [],
                "timeout": 300
            }
        }
    }

def create_ssl_context(skip_tls_checks: List[str]) -> Optional[ssl.SSLContext]:
    """Create SSL context based on TLS checks to skip"""
    if not skip_tls_checks:
        return None
    
    ssl_context = ssl.create_default_context()
    
    # Check for ALL option - disables all TLS verification
    if 'all' in [error.lower() for error in skip_tls_checks]:
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context
    
    # Handle specific TLS error types
    modified = False
    if any(check in skip_tls_checks for check in ['expired_cert', 'self_signed', 'cert_authority']):
        ssl_context.verify_mode = ssl.CERT_NONE
        modified = True
    
    if 'hostname_mismatch' in skip_tls_checks:
        ssl_context.check_hostname = False
        modified = True
    
    if 'weak_cipher' in skip_tls_checks:
        ssl_context.set_ciphers('ALL:@SECLEVEL=0')
        modified = True
    
    return ssl_context if modified else None


# ─── Shared HTTP session (keep-alive pool) ────────────────────────────────────
# Reusing one ClientSession across requests means TCP connections to the same
# upstream host are reused via HTTP keep-alive, which removes the handshake
# round-trip from every snapshot poll / PTZ command. ~10-30ms saved per call.
_shared_session: Optional[aiohttp.ClientSession] = None


async def get_shared_session() -> aiohttp.ClientSession:
    global _shared_session
    if _shared_session is None or _shared_session.closed:
        connector = aiohttp.TCPConnector(
            limit=64,
            limit_per_host=16,
            keepalive_timeout=60,
            enable_cleanup_closed=True,
            # aiohttp's connect-time DNS cache, complementing our policy-check
            # cache in _resolve_cached(). Both expire on the same TTL so they
            # converge on a refresh together.
            use_dns_cache=True,
            ttl_dns_cache=int(DNS_CACHE_TTL),
        )
        _shared_session = aiohttp.ClientSession(connector=connector)
    return _shared_session


_ssl_sessions: Dict[str, aiohttp.ClientSession] = {}   # keyed by sorted skip_tls string
_ssl_ctx_cache: Dict[str, Optional[ssl.SSLContext]] = {}


async def close_shared_session() -> None:
    global _shared_session
    if _shared_session is not None and not _shared_session.closed:
        await _shared_session.close()
    _shared_session = None
    for session in list(_ssl_sessions.values()):
        if not session.closed:
            await session.close()
    _ssl_sessions.clear()
    _ssl_ctx_cache.clear()


async def _get_ssl_session(key: str, ctx: ssl.SSLContext) -> aiohttp.ClientSession:
    """Return a cached aiohttp session that uses *ctx* for all connections."""
    if key not in _ssl_sessions or _ssl_sessions[key].closed:
        _ssl_sessions[key] = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                ssl=ctx,
                use_dns_cache=True,
                ttl_dns_cache=int(DNS_CACHE_TTL),
            )
        )
    return _ssl_sessions[key]


def _get_cached_ssl_context(skip_tls_checks: List[str]) -> Optional[ssl.SSLContext]:
    """Return a cached SSL context, building it on first use."""
    if not skip_tls_checks:
        return None
    key = ",".join(sorted(c.lower() for c in skip_tls_checks))
    if key not in _ssl_ctx_cache:
        _ssl_ctx_cache[key] = create_ssl_context(skip_tls_checks)
    return _ssl_ctx_cache[key]


async def build_websocket_proxy_setup(proxy_instance: 'ProxyInstance', request_data: dict) -> dict:
    """Translate an HTTP-style request into the params needed to dial the
    upstream WebSocket: ws(s):// URL, headers (with hop-by-hop scrubbed and
    `request_header[X]` overrides applied), and an optional SSL context."""
    try:
        target_url = request_data['target_url']
        headers = request_data['headers']
        query_params = request_data['query_params']

        if target_url.startswith('https://'):
            ws_url = target_url.replace('https://', 'wss://', 1)
        elif target_url.startswith('http://'):
            ws_url = target_url.replace('http://', 'ws://', 1)
        elif target_url.startswith(('ws://', 'wss://')):
            ws_url = target_url
        else:
            return {'success': False, 'error': 'Invalid URL scheme for WebSocket', 'status': 400}

        # SSL config (mirrors the HTTP path)
        skip_tls_checks_param = query_params.get('skip_tls_checks', [''])
        ssl_context = None
        if skip_tls_checks_param[0]:
            v = skip_tls_checks_param[0].lower()
            if v in ['true', '1', 'yes']:
                checks = ['all']
            else:
                checks = [s.strip().lower() for s in v.split(',')]
            ssl_context = create_ssl_context(checks)

        # Strip hop-by-hop / WS-specific headers from the inbound request before
        # forwarding — the websockets client library injects its own.
        ws_headers = {}
        excluded = {
            'connection', 'upgrade', 'sec-websocket-key', 'sec-websocket-version',
            'sec-websocket-protocol', 'sec-websocket-extensions', 'host',
        }
        for h, v in headers.items():
            if h.lower() not in excluded:
                ws_headers[h] = v
        # Layer in custom request_header[] overrides
        for key, values in query_params.items():
            if key.startswith('request_header[') and key.endswith(']'):
                ws_headers[key[15:-1]] = values[0]

        return {'success': True, 'websocket_url': ws_url, 'headers': ws_headers, 'ssl_context': ssl_context}
    except Exception as e:
        print(f"WebSocket proxy setup error: {e}")
        return {'success': False, 'error': f"WebSocket setup error: {e}", 'status': 500}


async def handle_streaming_request(
    request: web.Request,
    target_url: str,
    req_headers: dict,
    query_params: dict,
    timeout_default: int,
    chunk_size_default: int = DEFAULT_STREAM_CHUNK_SIZE,
) -> web.StreamResponse:
    """Pipe an upstream response through to the client without buffering.
    Used for live MJPEG, HLS playlists, or any long-running stream that
    `async_proxy_request`'s `await response.read()` would deadlock on.

    Smoothness considerations (see HA proxy.py for full discussion):

      * Default ``chunk_size_default = 0`` → uses ``iter_any()`` which yields
        as bytes arrive, no accumulation. Critical for MJPEG: a fixed-size
        bucket coalesces frames and produces choppy playback.
      * ``TCP_NODELAY`` is set on the inbound socket so per-frame writes
        flush immediately (avoids ~40 ms Nagle/delayed-ACK stalls).
      * Per-request override via ``?stream_chunk_size=N`` query param.
    """
    timeout_param = query_params.get('timeout', [''])[0]
    timeout_seconds = int(timeout_param) if timeout_param and timeout_param.isdigit() else timeout_default
    # No total cap — streams run indefinitely. Time out only on idle reads.
    timeout = aiohttp.ClientTimeout(total=None, sock_read=timeout_seconds)

    # Resolve effective chunk size: query param wins, instance default falls back.
    raw_cs = query_params.get('stream_chunk_size', [''])[0]
    if raw_cs and raw_cs.lstrip('-').isdigit():
        chunk_size = max(0, int(raw_cs))
    else:
        chunk_size = max(0, int(chunk_size_default))

    # Custom response_header[] from query string (CORS, content-type override, etc.)
    resp_headers: Dict[str, str] = {}
    for key, values in query_params.items():
        if key.startswith('response_header[') and key.endswith(']'):
            resp_headers[key[16:-1]] = values[0]

    try:
        session = await get_shared_session()
        async with session.get(target_url, headers=req_headers, timeout=timeout) as upstream:
            for h, v in upstream.headers.items():
                if h.lower() not in {'connection', 'transfer-encoding', 'content-encoding'}:
                    resp_headers.setdefault(h, v)

            # Inbound TCP_NODELAY before prepare() so the very first frame
            # of the response also flushes immediately.
            _disable_nagle(request)

            stream_resp = web.StreamResponse(status=upstream.status, headers=resp_headers)
            await stream_resp.prepare(request)

            if chunk_size > 0:
                iterator = upstream.content.iter_chunked(chunk_size)
            else:
                # Low-latency mode — yields whatever the socket has right now.
                iterator = upstream.content.iter_any()

            async for chunk in iterator:
                if chunk:
                    await stream_resp.write(chunk)
            await stream_resp.write_eof()
            return stream_resp
    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
        return web.Response(status=502, text=f"Stream error: {e}")
    except Exception as e:  # pragma: no cover
        print(f"Streaming proxy error: {e}")
        return web.Response(status=500, text=f"Stream error: {e}")


async def _do_proxied_request(session, method, target_url, headers, body,
                              follow_redirects, timeout, query_params,
                              proxy_instance=None):
    """Execute a single buffered proxied request on the supplied session.

    Retries once on a stale keep-alive socket — Hikvision (and many other
    embedded HTTP servers) drop idle TCP connections without notifying us,
    so the first reuse from the pool fails with `ServerDisconnectedError`.
    `body` is bytes for our use cases (XML / form data / no body), so it is
    safe to resend.

    When `follow_redirects=True` AND the proxy instance has a tighter
    outbound policy than 'both/any', redirects are followed manually with
    re-validation on every hop. Otherwise an open redirector at a public
    URL could bounce the proxy to internal IPs.
    """
    needs_manual = (
        follow_redirects
        and proxy_instance is not None
        and getattr(proxy_instance, 'restrict_out', 'both') not in ('both', 'any')
    )

    if needs_manual:
        return await _do_proxied_request_with_revalidation(
            session, method, target_url, headers, body, timeout,
            query_params, proxy_instance,
        )

    request_kwargs = {
        'method': method,
        'url': target_url,
        'headers': headers,
        'allow_redirects': follow_redirects,
        'timeout': timeout,
    }
    if body is not None:
        request_kwargs['data'] = body

    last_err = None
    for attempt in range(2):
        try:
            async with session.request(**request_kwargs) as response:
                response_header = {}
                excluded_response_header = {'connection', 'transfer-encoding', 'content-encoding'}
                for header, value in response.headers.items():
                    if header.lower() not in excluded_response_header:
                        response_header[header] = value
                for key, values in query_params.items():
                    if key.startswith('response_header[') and key.endswith(']'):
                        header_name = key[16:-1]
                        response_header[header_name] = values[0]
                response_data = await response.read()
                return {
                    'success': True,
                    'status': response.status,
                    'headers': response_header,
                    'data': response_data,
                }
        except (aiohttp.ServerDisconnectedError, aiohttp.ClientOSError) as e:
            last_err = e
            _LOGGER.debug(f"Retrying after stale-connection error ({type(e).__name__}): {e}")
            continue
    raise last_err


async def _do_proxied_request_with_revalidation(
    session, method, target_url, headers, body, timeout,
    query_params, proxy_instance,
):
    """Manually follow up to MAX_REDIRECT_HOPS redirects, re-validating each
    new target against the outbound policy. Used when the caller asked for
    redirect-following AND the instance has tighter-than-'both' restrictions
    — protects against open-redirector → SSRF pivots."""
    seen: set = set()
    current_url = target_url
    current_method = method
    current_body = body
    excluded_response_header = {'connection', 'transfer-encoding', 'content-encoding'}

    for _hop in range(MAX_REDIRECT_HOPS + 1):
        if current_url in seen:
            _LOGGER.warning(
                "homie_proxy/%s: redirect loop detected (url=%s)",
                proxy_instance.name, _redact_url(current_url),
            )
            return {'success': False, 'status': 508, 'error': 'Redirect loop detected'}
        seen.add(current_url)

        request_kwargs = {
            'method': current_method, 'url': current_url,
            'headers': headers, 'allow_redirects': False, 'timeout': timeout,
        }
        if current_body is not None:
            request_kwargs['data'] = current_body

        async with session.request(**request_kwargs) as response:
            if not (300 <= response.status < 400):
                response_header = {
                    h: v for h, v in response.headers.items()
                    if h.lower() not in excluded_response_header
                }
                for key, values in query_params.items():
                    if key.startswith('response_header[') and key.endswith(']'):
                        response_header[key[16:-1]] = values[0]
                return {
                    'success': True,
                    'status': response.status,
                    'headers': response_header,
                    'data': await response.read(),
                }

            location = response.headers.get('Location')
            if not location:
                response_header = {
                    h: v for h, v in response.headers.items()
                    if h.lower() not in excluded_response_header
                }
                return {
                    'success': True,
                    'status': response.status,
                    'headers': response_header,
                    'data': await response.read(),
                }

            next_url = urllib.parse.urljoin(current_url, location)
            if not await proxy_instance.is_target_url_allowed(next_url):
                _LOGGER.warning(
                    "homie_proxy/%s: 403 redirect target rejected "
                    "(from=%s, to=%s, mode=%s) — open-redirect SSRF blocked",
                    proxy_instance.name,
                    _redact_url(current_url), _redact_url(next_url),
                    proxy_instance.restrict_out,
                )
                return {'success': False, 'status': 403,
                        'error': 'Redirect target blocked by access policy'}

            current_url = next_url
            if response.status in (301, 302, 303) and current_method in ('POST', 'PUT', 'PATCH'):
                current_method = 'GET'
                current_body = None

    _LOGGER.warning(
        "homie_proxy/%s: 508 too many redirects",
        proxy_instance.name,
    )
    return {'success': False, 'status': 508, 'error': 'Too many redirects'}


async def async_proxy_request(proxy_instance: 'ProxyInstance', request_data: dict) -> dict:
    """Async proxy request function using aiohttp"""
    try:
        client_ip = request_data['client_ip']
        method = request_data['method']
        query_params = request_data['query_params']
        headers = request_data['headers']
        body = request_data['body']
        target_url = request_data['target_url']

        # Configure TLS/SSL settings (contexts are cached by configuration key).
        skip_tls_checks_param = query_params.get('skip_tls_checks', [''])
        skip_tls_checks: List[str] = []
        ssl_context = None
        if skip_tls_checks_param[0]:
            skip_tls_value = skip_tls_checks_param[0].lower()
            if skip_tls_value in ['true', '1', 'yes']:
                skip_tls_checks = ['all']
            else:
                skip_tls_checks = [s.strip().lower() for s in skip_tls_value.split(',')]
            ssl_context = _get_cached_ssl_context(skip_tls_checks)

        # Configure redirect following
        follow_redirects_param = query_params.get('follow_redirects', ['false'])
        follow_redirects = follow_redirects_param[0].lower() in ['true', '1', 'yes']

        # Per-request timeout (overrides instance default if supplied as ?timeout=N)
        timeout_param = query_params.get('timeout', [''])
        if timeout_param[0] and timeout_param[0].isdigit():
            timeout_seconds = int(timeout_param[0])
        else:
            timeout_seconds = proxy_instance.timeout

        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        print(f"Using timeout: {timeout_seconds}s for request")

        # SSL-skip requests use a cached per-config session so TCP connections
        # are pooled across requests (not created and torn down every time).
        if ssl_context is not None:
            ssl_key = ",".join(sorted(skip_tls_checks))
            session = await _get_ssl_session(ssl_key, ssl_context)
        else:
            session = await get_shared_session()

        return await _do_proxied_request(
            session, method, target_url, headers, body,
            follow_redirects, timeout, query_params,
            proxy_instance=proxy_instance,
        )

    except aiohttp.ClientError as e:
        return {'success': False, 'error': f"Bad Gateway: {str(e)}", 'status': 502}

    except asyncio.TimeoutError:
        return {'success': False, 'error': "Gateway Timeout", 'status': 504}

    except Exception as e:
        print(f"Async proxy request error: {e}")
        return {'success': False, 'error': "Internal server error", 'status': 500}


class ProxyInstance:
    """Configuration for a proxy instance"""

    def __init__(self, name: str, config: Dict):
        self.name = name
        self.restrict_out = config.get('restrict_out', 'both')  # external, internal, both, custom
        self.restrict_out_cidrs = [ipaddress.ip_network(cidr) for cidr in config.get('restrict_out_cidrs', [])]
        # Tokens stored as a list (not set) so iteration order is stable for
        # constant-time comparison. The bytes form is cached so we don't
        # re-encode on every request.
        self.tokens = list(config.get('tokens', []))
        self._token_bytes = [t.encode('utf-8') for t in self.tokens]
        self.restrict_in_cidrs = [ipaddress.ip_network(cidr) for cidr in config.get('restrict_in_cidrs', [])]
        self.timeout = config.get('timeout', 300)
        # 0 → iter_any() (low-latency, recommended for live streams).
        # >0 → iter_chunked(N) — trades latency for fewer event-loop wakeups.
        self.stream_chunk_size = max(0, int(config.get('stream_chunk_size', DEFAULT_STREAM_CHUNK_SIZE)))

        # Backward compatibility - support old parameter names
        if 'access_mode' in config:
            self.restrict_out = config['access_mode']
        if 'allowed_networks_out' in config:
            self.restrict_out = config['allowed_networks_out']
        if 'allowed_cidrs' in config:
            self.restrict_in_cidrs = [ipaddress.ip_network(cidr) for cidr in config['allowed_cidrs']]
        if 'restrict_access_to_cidrs' in config:
            self.restrict_in_cidrs = [ipaddress.ip_network(cidr) for cidr in config['restrict_access_to_cidrs']]
        if 'allowed_networks_cidrs' in config:
            self.restrict_out_cidrs = [ipaddress.ip_network(cidr) for cidr in config['allowed_networks_cidrs']]
        if 'allowed_networks_out_cidrs' in config:
            self.restrict_out_cidrs = [ipaddress.ip_network(cidr) for cidr in config['allowed_networks_out_cidrs']]

    def is_client_access_allowed(self, client_ip: str) -> bool:
        """Check if client IP is allowed to access this proxy instance."""
        try:
            ip = ipaddress.ip_address(client_ip)
            if self.restrict_in_cidrs:
                return any(ip in cidr for cidr in self.restrict_in_cidrs)
            return True
        except ValueError:
            return False

    def _check_ip(self, target_ip: ipaddress._BaseAddress) -> bool:
        """Apply the configured outbound policy to a single resolved address."""
        # Custom CIDR list takes precedence over mode keyword.
        if self.restrict_out_cidrs:
            return any(target_ip in cidr for cidr in self.restrict_out_cidrs)
        if self.restrict_out == 'external':
            return not any(target_ip in net for net in _PRIVATE_NETWORKS)
        if self.restrict_out == 'internal':
            return any(target_ip in net for net in _PRIVATE_NETWORKS)
        # 'both' / 'any' / anything else
        return True

    async def is_target_url_allowed(
        self,
        target_url: str,
        *,
        _parsed: Optional[urllib.parse.ParseResult] = None,
    ) -> bool:
        """Check if the target URL is allowed by the outbound policy.

        Hardening notes:
          * Scheme allowlist (http/https/ws/wss) — file://, gopher://, etc.
            are rejected up-front.
          * Multi-IP validation — when a hostname resolves to several
            addresses, EVERY address must satisfy the policy. This blocks
            the multi-A-record / DNS-rebinding SSRF where an attacker
            returns [public-ip, private-ip] and aiohttp later connects to
            the private one.
          * Uses an explicit PRIVATE_CIDRS list rather than Python's
            `is_private` (whose coverage varies by Python version — 100.64/10
            was only added in 3.11).

        ``_parsed`` lets the request handler avoid re-parsing the same URL
        twice per request (it parses once for hostname extraction, once for
        the policy check). Public callers / tests use the simple
        ``is_target_url_allowed(url)`` form.

        DNS results are cached for ``DNS_CACHE_TTL`` seconds; see
        ``_resolve_cached``.
        """
        try:
            parsed = _parsed if _parsed is not None else urllib.parse.urlparse(target_url)
            scheme = (parsed.scheme or '').lower()
            if scheme not in _ALLOWED_SCHEMES:
                return False

            hostname = parsed.hostname
            if not hostname:
                return False

            try:
                target_ip = ipaddress.ip_address(hostname)
                return self._check_ip(target_ip)
            except ValueError:
                pass  # not an IP literal — DNS-resolve below

            addrs = await _resolve_cached(hostname)
            if addrs is None:
                return False
            for s in addrs:
                try:
                    addr = ipaddress.ip_address(s)
                except ValueError:
                    return False
                if not self._check_ip(addr):
                    return False
            return True

        except Exception:
            return False

    def is_token_valid(self, token: Optional[str]) -> bool:
        """Constant-time token check.

        Behavioural change from the previous version: when NO tokens are
        configured, the instance now denies every request (was: allowed
        every request). Allowing all when no tokens are set is the wrong
        default for a security-sensitive component — secure-by-default.
        """
        if not token or not self._token_bytes:
            return False
        try:
            given = token.encode('utf-8')
        except (UnicodeEncodeError, AttributeError):
            return False
        result = False
        # Iterate ALL configured tokens (no short-circuit).
        for tb in self._token_bytes:
            if hmac.compare_digest(given, tb):
                result = True
        return result


class HomieProxyRequestHandler:
    """Async request handler that processes proxy requests"""
    
    def __init__(self, proxy_instance: ProxyInstance):
        self.proxy_instance = proxy_instance
    
    def log_message(self, format_str, *args):
        """Log a message with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {format_str % args}")
    
    def get_client_ip(self, request: web.Request) -> str:
        """Get the real client IP address"""
        # Check for forwarded headers first
        forwarded_for = request.headers.get('X-Forwarded-For')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        
        real_ip = request.headers.get('X-Real-IP')
        if real_ip:
            return real_ip
        
        return request.remote or '127.0.0.1'
    
    def is_websocket_request(self, request: web.Request) -> bool:
        """True when the incoming request looks like a WS upgrade handshake."""
        connection = request.headers.get('Connection', '').lower()
        upgrade = request.headers.get('Upgrade', '').lower()
        return 'upgrade' in connection and upgrade == 'websocket'

    async def handle_websocket_request(
        self, request: web.Request, target_url: str, headers: dict, query_params: dict,
    ) -> web.WebSocketResponse:
        """Bridge an inbound aiohttp WS to an outbound `websockets` client and
        relay messages bidirectionally until either side closes."""
        if websockets is None:
            return self.send_error_response(
                501, "WebSocket support unavailable — install the 'websockets' package", query_params,
            )

        request_data = {'target_url': target_url, 'headers': headers, 'query_params': query_params}
        setup = await build_websocket_proxy_setup(self.proxy_instance, request_data)
        if not setup['success']:
            return self.send_error_response(setup.get('status', 500), setup['error'], query_params)

        ws_url = setup['websocket_url']
        ws_headers = setup['headers']
        ssl_context = setup['ssl_context']

        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.log_message(f"WebSocket upgrade: connecting to {ws_url}")

        try:
            connect_kwargs = {'extra_headers': ws_headers}
            if ssl_context is not None:
                connect_kwargs['ssl'] = ssl_context

            async with websockets.connect(ws_url, **connect_kwargs) as target_ws:
                self.log_message(f"WebSocket connected: {ws_url}")

                async def relay_client_to_target():
                    try:
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                await target_ws.send(msg.data)
                            elif msg.type == aiohttp.WSMsgType.BINARY:
                                await target_ws.send(msg.data)
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                break
                    except Exception as e:
                        self.log_message(f"WS relay client→target error: {e}")

                async def relay_target_to_client():
                    try:
                        async for msg in target_ws:
                            if isinstance(msg, str):
                                await ws.send_str(msg)
                            elif isinstance(msg, bytes):
                                await ws.send_bytes(msg)
                    except Exception as e:
                        self.log_message(f"WS relay target→client error: {e}")

                await asyncio.gather(
                    relay_client_to_target(),
                    relay_target_to_client(),
                    return_exceptions=True,
                )
                self.log_message("WebSocket connection closed")
        except WebSocketException as e:
            self.log_message(f"WebSocket connection failed: {e}")
            if not ws.closed:
                await ws.close(message=f"Target connection failed: {e}".encode())
        except Exception as e:
            self.log_message(f"WebSocket error: {e}")
            if not ws.closed:
                await ws.close(message=f"Connection error: {e}".encode())

        return ws

    def send_error_response(self, code: int, message: str, query_params: Optional[dict] = None) -> web.Response:
        """Send an error response. Replays any `response_header[X]=Y` query params
        the client supplied so error responses (e.g. 502 from a stale keep-alive)
        still carry the right CORS headers — otherwise the browser blocks the
        response and the user just sees a confusing 'CORS missing' message
        instead of the real upstream error."""
        error_response = {
            'error': message,
            'code': code,
            'timestamp': datetime.now().isoformat(),
            'instance': self.proxy_instance.name
        }
        headers = {'Content-Type': 'application/json'}
        if query_params:
            for key, values in query_params.items():
                if key.startswith('response_header[') and key.endswith(']'):
                    headers[key[16:-1]] = values[0]
        return web.Response(
            text=json.dumps(error_response, indent=2),
            status=code,
            headers=headers,
        )
    
    async def handle_request(self, request: web.Request) -> web.Response:
        """Main request handler for all HTTP methods"""
        inst_name = self.proxy_instance.name
        try:
            method = request.method
            client_ip = self.get_client_ip(request)

            # Parse query parameters
            query_params = dict(request.query)
            # Convert single values to lists for consistency with old code
            for key, value in query_params.items():
                if not isinstance(value, list):
                    query_params[key] = [value]

            # Optional CORS preflight short-circuit (opt-in via ?cors_preflight=1).
            if method == 'OPTIONS':
                cors_preflight_param = query_params.get('cors_preflight', ['0'])[0].lower()
                if cors_preflight_param in ('1', 'true', 'yes'):
                    cors_headers: Dict[str, str] = {}
                    for key, values in query_params.items():
                        if key.startswith('response_header[') and key.endswith(']'):
                            cors_headers[key[16:-1]] = values[0]
                    return web.Response(status=204, headers=cors_headers)

            # ── Token auth first — prevents leaking access-control details ──
            tokens = query_params.get('token', [])
            token = tokens[0] if tokens else None
            if not self.proxy_instance.is_token_valid(token):
                _LOGGER.warning(
                    "homie_proxy/%s: 401 auth failed (client_ip=%s, "
                    "token_prefix=%s) — possible brute force / leaked token",
                    inst_name, client_ip, _mask_token(token or ""),
                )
                return self.send_error_response(401, "Invalid or missing token", query_params)

            # Check inbound IP
            if not self.proxy_instance.is_client_access_allowed(client_ip):
                _LOGGER.warning(
                    "homie_proxy/%s: 403 inbound IP rejected (client_ip=%s) — "
                    "valid token used from non-allowlisted network",
                    inst_name, client_ip,
                )
                return self.send_error_response(403, "Access denied from your IP", query_params)

            target_urls = query_params.get('url', [])
            if not target_urls:
                return self.send_error_response(400, "Target URL required", query_params)
            target_url = target_urls[0]

            # Parse once and share with the policy check below — saves a
            # second urllib.parse.urlparse() call per request.
            parsed_target = urllib.parse.urlparse(target_url)
            original_hostname = parsed_target.hostname

            # Check outbound URL (now async — DNS resolved without blocking,
            # and cached in _resolve_cached for repeat requests).
            if not await self.proxy_instance.is_target_url_allowed(
                target_url, _parsed=parsed_target,
            ):
                _LOGGER.warning(
                    "homie_proxy/%s: 403 outbound URL rejected "
                    "(client_ip=%s, url=%s, mode=%s) — possible SSRF",
                    inst_name, client_ip,
                    _redact_url(target_url), self.proxy_instance.restrict_out,
                )
                return self.send_error_response(403, "Access denied to the target URL", query_params)

            self.log_message(f"Target URL allowed: {_redact_url(target_url)}")

            # Get request body
            body = None
            if request.can_read_body:
                body = await request.read()
            
            # Prepare headers - start with original headers from client
            headers = dict(request.headers)
            
            # Remove aiohttp-specific headers that shouldn't be forwarded
            excluded_headers = {
                'host'  # Will be set properly below
            }
            for header in excluded_headers:
                headers.pop(header, None)
            
            # Check if Host header was provided via request_header[Host] parameter
            host_header_override = None
            for key, values in query_params.items():
                if key.startswith('request_header[') and key.endswith(']'):
                    header_name = key[15:-1]  # Remove 'request_header[' and ']'
                    if header_name.lower() == 'host':
                        host_header_override = values[0]
                    else:
                        headers[header_name] = values[0]
            
            # Handle Host header logic AFTER custom headers so override takes precedence
            if host_header_override:
                # Use explicit override
                headers['Host'] = host_header_override
                self.log_message(f"Host header override set to: {host_header_override}")
            elif original_hostname:
                # Check if the hostname is an IP address
                try:
                    ipaddress.ip_address(original_hostname)
                    # It's an IP address - don't set Host header
                    headers.pop('Host', None)
                    self.log_message(f"Target is IP address ({original_hostname}) - no Host header set")
                except ValueError:
                    # It's a hostname - set Host header to hostname only (no port)
                    headers['Host'] = original_hostname
                    self.log_message(f"Set Host header to hostname: {headers['Host']}")
            
            # Always ensure User-Agent is explicitly set (use blank if none provided)
            user_agent_set = False
            for header_name in headers.keys():
                if header_name.lower() == 'user-agent':
                    user_agent_set = True
                    break
            
            if not user_agent_set:
                headers['User-Agent'] = ''
                self.log_message("Setting blank User-Agent (no User-Agent provided)")
            else:
                self.log_message(f"User-Agent already provided: {headers.get('User-Agent', headers.get('user-agent', 'NOT FOUND'))}")
            
            # Prepare request data for async proxy
            request_data = {
                'client_ip': client_ip,
                'method': method,
                'query_params': query_params,
                'headers': headers,
                'body': body,
                'target_url': target_url
            }
            
            # Log the request
            self.log_message(f"REQUEST to {target_url}")
            self.log_message(f"Request method: {method}")
            if headers:
                self.log_message("Request headers being sent to target:")
                for header_name, header_value in headers.items():
                    # Truncate very long header values for readability
                    if len(str(header_value)) > 100:
                        display_value = str(header_value)[:97] + "..."
                    else:
                        display_value = header_value
                    self.log_message(f"  {header_name}: {display_value}")
            else:
                self.log_message("No custom headers being sent to target")
            
            if body:
                body_size = len(body)
                if body_size > 1024:
                    self.log_message(f"Request body: {body_size} bytes")
                else:
                    self.log_message(f"Request body: {body_size} bytes - {body[:100]}{b'...' if len(body) > 100 else b''}")
            
            # WebSocket upgrade — handshake on the inbound connection and
            # bidirectionally relay frames to/from the upstream WS server.
            if self.is_websocket_request(request):
                self.log_message(f"WebSocket upgrade request detected for {target_url}")
                return await self.handle_websocket_request(
                    request, target_url, headers, query_params,
                )

            # Streaming mode (?stream=1): pipe upstream response chunks straight
            # to the client without buffering. Required for live MJPEG, HLS
            # playlists, and anything else where waiting for `await response.read()`
            # would never return.
            if method == 'GET' and query_params.get('stream', [''])[0] == '1':
                self.log_message(f"Streaming mode for {target_url}")
                return await handle_streaming_request(
                    request, target_url, headers, query_params,
                    self.proxy_instance.timeout,
                    self.proxy_instance.stream_chunk_size,
                )

            # Make the async proxy request
            response_data = await async_proxy_request(self.proxy_instance, request_data)
            
            if not response_data['success']:
                return self.send_error_response(
                    response_data.get('status', 500),
                    response_data['error'],
                    query_params,
                )
            
            # Log the response
            self.log_message(f"RESPONSE from {target_url}")
            self.log_message(f"Response status: {response_data['status']}")
            if response_data['headers']:
                self.log_message("Response headers received from target:")
                for header_name, header_value in response_data['headers'].items():
                    # Truncate very long header values for readability
                    if len(str(header_value)) > 100:
                        display_value = str(header_value)[:97] + "..."
                    else:
                        display_value = header_value
                    self.log_message(f"  {header_name}: {display_value}")
            else:
                self.log_message("No response headers received from target")
            
            # Create and return response
            response = web.Response(
                body=response_data['data'],
                status=response_data['status'],
                headers=response_data['headers']
            )
            
            data_size = len(response_data['data'])
            self.log_message(f"Returned response: {data_size} bytes")
            
            return response
            
        except Exception as e:
            self.log_message(f"Proxy error: {e}")
            # `query_params` may or may not have been parsed before the exception;
            # pass whatever we have so error responses still carry CORS headers.
            qp = locals().get('query_params')
            return self.send_error_response(500, "Internal server error", qp)


class HomieProxyServer:
    """
    Main homie proxy server using aiohttp.
    
    Can be used with file-based configuration or programmatic configuration.
    
    Example file-based usage:
        server = HomieProxyServer('my_config.json')
        server.run()
    
    Example programmatic usage:
        server = HomieProxyServer()
        server.add_instance('api', {
            'restrict_out': 'external',
            'tokens': ['secret-key'],
            'restrict_in_cidrs': []
        })
        server.run(host='localhost', port=8080)
    """
    
    def __init__(self, config_file: Optional[str] = None, instances: Optional[Dict[str, ProxyInstance]] = None):
        """
        Initialize the proxy server.
        
        Args:
            config_file: Path to JSON configuration file (optional)
            instances: Dictionary of ProxyInstance objects (optional)
            
        If neither config_file nor instances is provided, creates default configuration.
        If both are provided, instances takes precedence.
        """
        self.config_file = config_file
        self.instances: Dict[str, ProxyInstance] = {}
        self.app = None
        
        if instances:
            self.instances = instances
            print(f"Loaded {len(self.instances)} proxy instances from provided configuration")
        elif config_file:
            self.load_config()
        else:
            # Neither provided, create default instances
            self.instances = create_proxy_config(create_default_config()['instances'])
            print(f"Created {len(self.instances)} default proxy instances")
    
    def add_instance(self, name: str, config: Dict) -> None:
        """
        Add a proxy instance programmatically.
        
        Args:
            name: Instance name
            config: Instance configuration dictionary
            
        Example:
            server.add_instance('api', {
                'restrict_out': 'external',
                'tokens': ['api-key-123'],
                'restrict_in_cidrs': ['192.168.1.0/24']
            })
        """
        self.instances[name] = ProxyInstance(name, config)
        print(f"Added proxy instance: {name}")
    
    def remove_instance(self, name: str) -> bool:
        """
        Remove a proxy instance.
        
        Args:
            name: Instance name to remove
            
        Returns:
            True if instance was removed, False if it didn't exist
        """
        if name in self.instances:
            del self.instances[name]
            print(f"Removed proxy instance: {name}")
            return True
        return False
    
    def list_instances(self) -> List[str]:
        """
        Get list of configured instance names.
        
        Returns:
            List of instance names
        """
        return list(self.instances.keys())
    
    def get_instance_config(self, name: str) -> Optional[Dict]:
        """
        Get configuration for a specific instance.
        
        Args:
            name: Instance name
            
        Returns:
            Instance configuration dictionary or None if not found
        """
        if name in self.instances:
            instance = self.instances[name]
            return {
                'restrict_out': instance.restrict_out,
                'restrict_out_cidrs': [str(cidr) for cidr in instance.restrict_out_cidrs],
                'restrict_in_cidrs': [str(cidr) for cidr in instance.restrict_in_cidrs],
                'tokens': list(instance.tokens),
                'timeout': instance.timeout,
                'stream_chunk_size': instance.stream_chunk_size,
            }
        return None
    
    def load_config(self):
        """Load configuration from file"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            self.instances = {}
            for name, instance_config in config.get('instances', {}).items():
                self.instances[name] = ProxyInstance(name, instance_config)
            
            print(f"Loaded {len(self.instances)} proxy instances")
            
        except FileNotFoundError:
            print(f"Config file {self.config_file} not found. Creating default config.")
            self.create_default_config()
        except json.JSONDecodeError as e:
            print(f"Error parsing config file: {e}")
            exit(1)
    
    def create_default_config(self):
        """Create a default configuration file"""
        default_config = create_default_config()
        
        with open(self.config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        print(f"Created default config file: {self.config_file}")
        self.load_config()
    
    def create_app(self) -> web.Application:
        """Create the aiohttp application with routes"""
        app = web.Application()
        
        # Add route for each instance
        for instance_name, instance in self.instances.items():
            handler = HomieProxyRequestHandler(instance)
            
            # Create route pattern
            route_path = f'/{instance_name}'
            
            # Add route for all HTTP methods
            app.router.add_route('*', route_path, handler.handle_request)
        
        # Add debug route to show all instances
        async def debug_handler(request):
            debug_info = {
                'timestamp': datetime.now().isoformat(),
                'instances': {}
            }
            
            for name, instance in self.instances.items():
                debug_info['instances'][name] = {
                    'restrict_out': instance.restrict_out,
                    'restrict_out_cidrs': [str(cidr) for cidr in instance.restrict_out_cidrs],
                    'restrict_in_cidrs': [str(cidr) for cidr in instance.restrict_in_cidrs],
                    # Tokens MASKED — never echo full credentials, even on
                    # the debug endpoint. First 4 chars + ***.
                    'tokens': [_mask_token(t) for t in instance.tokens],
                    'token_count': len(instance.tokens),
                    'timeout': instance.timeout,
                    'stream_chunk_size': instance.stream_chunk_size,
                }
            
            return web.Response(
                text=json.dumps(debug_info, indent=2),
                headers={'Content-Type': 'application/json'}
            )
        
        app.router.add_get('/debug', debug_handler)

        # Close the shared keep-alive HTTP session cleanly on shutdown
        async def _on_cleanup(_app):
            await close_shared_session()
        app.on_cleanup.append(_on_cleanup)

        return app
    
    async def init_server(self, host: str = '0.0.0.0', port: int = 8080):
        """Initialize the aiohttp server"""
        # Check if port is in use
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(1)
            result = test_socket.connect_ex((host if host != '0.0.0.0' else 'localhost', port))
            test_socket.close()
            
            if result == 0:
                print(f"ERROR: Port {port} is already in use!")
                print(f"   Another service is already running on {host}:{port}")
                print(f"   Please stop the other service or use a different port with --port")
                exit(1)
        except Exception:
            pass  # If connection test fails, port is likely free
        
        # Create the app
        self.app = self.create_app()
        
        print(f"Homie Proxy Server starting on {host}:{port}")
        print(f"Available instances: {list(self.instances.keys())}")
        print("Async server - supports concurrent requests")
        print("Server ready! Press Ctrl+C to stop")
        
        return self.app
    
    def run(self, host: str = '0.0.0.0', port: int = 8080):
        """Run the proxy server"""
        async def start_server():
            app = await self.init_server(host, port)
            runner = web.AppRunner(app)
            await runner.setup()
            
            site = web.TCPSite(runner, host, port)
            await site.start()
            
            print("Server running. Press Ctrl+C to stop...")
            
            # Keep the server running
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down server...")
                await runner.cleanup()
                print("Server stopped successfully")
        
        # Run the async server
        try:
            asyncio.run(start_server())
        except KeyboardInterrupt:
            print("\nServer interrupted")


def main():
    """Main entry point for console script"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Homie Proxy Server')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to (default: 8080)')
    parser.add_argument('--config', default='proxy_config.json', help='Configuration file (default: proxy_config.json)')
    
    args = parser.parse_args()
    
    server = HomieProxyServer(args.config)
    server.run(args.host, args.port)


if __name__ == '__main__':
    main() 