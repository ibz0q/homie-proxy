"""Homie Proxy service for Home Assistant."""

from __future__ import annotations

import asyncio
import hmac
import ipaddress
import json
import logging
import re
import socket
import ssl
import time
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from aiohttp import web
from aiohttp.web_request import Request

from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PRIVATE_CIDRS

_LOGGER = logging.getLogger(__name__)

# Pre-parse private CIDRs once at module load for O(1) membership checks.
_PRIVATE_NETWORKS: List[ipaddress._BaseNetwork] = [
    ipaddress.ip_network(c) for c in PRIVATE_CIDRS
]

# Hop-by-hop headers that must not be forwarded.
_HOP_BY_HOP_RESPONSE = frozenset({"connection", "transfer-encoding", "content-encoding"})
_HOP_BY_HOP_WS = frozenset({
    "connection", "upgrade", "sec-websocket-key", "sec-websocket-version",
    "sec-websocket-protocol", "sec-websocket-extensions", "host",
})

# Max number of redirects to follow when `follow_redirects=true` is supplied.
# Each hop is re-validated against the outbound policy.
MAX_REDIRECT_HOPS = 5

# Streaming chunk size — 64 KB strikes a balance between throughput and
# memory. With 8 KB the event loop wakes up ~8× more often per Mbit/s of
# stream; for 5 Mbps MJPEG that's ~75 saved wakeups per second.
STREAM_CHUNK_SIZE = 64 * 1024

# Per-process DNS cache for outbound-policy checks. Entries expire after
# DNS_CACHE_TTL seconds; the bound is also the worst-case window during
# which a DNS-rebinding attacker could keep us pointed at a stale answer
# while the attacker's authoritative server flips records.
#
# IMPORTANT: this cache is for the POLICY check only. aiohttp's connector
# does its own DNS resolution at connect-time; if the two disagree,
# aiohttp's resolution wins for the actual TCP connect. That residual
# TOCTOU is documented in test_security.test_dns_rebinding_*.
DNS_CACHE_TTL = 30.0
_DNS_CACHE: Dict[str, Tuple[float, List[str]]] = {}


async def _resolve_cached(hostname: str) -> Optional[List[str]]:
    """Resolve *hostname* to a list of IP-literal strings, with TTL caching.

    Returns None on resolution failure (so the caller fails closed).
    Negative results are NOT cached — a transient DNS failure shouldn't
    keep an endpoint dark for 30 seconds.
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
    """Test hook — clear the DNS cache between tests so monkey-patched
    getaddrinfo isn't shadowed by stale entries from a previous test."""
    _DNS_CACHE.clear()


# ─── Helpers: log redaction & token masking ──────────────────────────────────

# Redact `token=...`, `password=...`, `secret=...` (case-insensitive) so
# logged URLs never leak credentials.
_REDACT_QS_RE = re.compile(
    r"(?i)(?P<key>token|password|secret|api[_-]?key)=[^&\s]*"
)


def _redact_url(url: str) -> str:
    """Strip well-known credential query parameters from a URL for logging."""
    if not url:
        return url
    return _REDACT_QS_RE.sub(r"\g<key>=***", url)


def _mask_token(token: str) -> str:
    """Return a partially-redacted token for /debug — first 4 chars + ***."""
    if not token:
        return "***"
    if len(token) <= 4:
        return "***"
    return f"{token[:4]}***"


# ─── Session pool ─────────────────────────────────────────────────────────────

_shared_session: Optional[aiohttp.ClientSession] = None
_ssl_sessions: Dict[str, aiohttp.ClientSession] = {}   # keyed by sorted skip_tls string
_ssl_ctx_cache: Dict[str, ssl.SSLContext] = {}


async def get_shared_session() -> aiohttp.ClientSession:
    """Return (or lazily create) the global keep-alive session pool."""
    global _shared_session
    if _shared_session is None or _shared_session.closed:
        _shared_session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                limit=64,
                limit_per_host=16,
                keepalive_timeout=60,
                enable_cleanup_closed=True,
                # aiohttp's own connect-time DNS cache. Complements our
                # policy-check cache in _resolve_cached(): we resolve once
                # for the policy, aiohttp resolves once for the connect,
                # both reuse their cache for the next request to the same
                # host. ttl_dns_cache matches DNS_CACHE_TTL so the two
                # caches expire on the same schedule.
                use_dns_cache=True,
                ttl_dns_cache=int(DNS_CACHE_TTL),
            )
        )
    return _shared_session


async def _get_ssl_session(key: str, ctx: ssl.SSLContext) -> aiohttp.ClientSession:
    """Return a cached session that uses *ctx* for all connections."""
    if key not in _ssl_sessions or _ssl_sessions[key].closed:
        _ssl_sessions[key] = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(
                ssl=ctx,
                use_dns_cache=True,
                ttl_dns_cache=int(DNS_CACHE_TTL),
            )
        )
    return _ssl_sessions[key]


async def close_shared_session() -> None:
    """Close all session pools (called when the last proxy instance is unloaded)."""
    global _shared_session
    if _shared_session is not None and not _shared_session.closed:
        await _shared_session.close()
    _shared_session = None
    for session in list(_ssl_sessions.values()):
        if not session.closed:
            await session.close()
    _ssl_sessions.clear()
    _ssl_ctx_cache.clear()


# ─── SSL helpers ──────────────────────────────────────────────────────────────

def _build_ssl_context(skip_checks: List[str]) -> Optional[ssl.SSLContext]:
    """Create an ssl.SSLContext that ignores the requested validation classes."""
    if not skip_checks:
        return None
    checks = [c.lower() for c in skip_checks]

    if "all" in checks:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        _LOGGER.info("TLS: all verification disabled")
        return ctx

    ctx = ssl.create_default_context()
    modified = False
    if any(c in checks for c in ("hostname_mismatch", "expired_cert", "self_signed")):
        ctx.check_hostname = False
        modified = True
    if any(c in checks for c in ("expired_cert", "self_signed", "cert_authority")):
        ctx.verify_mode = ssl.CERT_NONE
        modified = True
    if "weak_cipher" in checks:
        ctx.set_ciphers("ALL:@SECLEVEL=0")
        modified = True

    if modified:
        _LOGGER.info("TLS: ignoring %s", ", ".join(checks))
        return ctx
    return None


def _get_ssl_context(skip_checks: List[str]) -> Optional[ssl.SSLContext]:
    """Return a cached SSL context, building it on first use."""
    if not skip_checks:
        return None
    key = ",".join(sorted(c.lower() for c in skip_checks))
    if key not in _ssl_ctx_cache:
        ctx = _build_ssl_context(skip_checks)
        if ctx is not None:
            _ssl_ctx_cache[key] = ctx
    return _ssl_ctx_cache.get(key)


def _parse_skip_tls(qp: Dict[str, List[str]]) -> List[str]:
    """Extract and normalise the skip_tls_checks query parameter."""
    raw = (qp.get("skip_tls_checks") or [""])[0].lower()
    if not raw:
        return []
    if raw in ("true", "1", "yes"):
        return ["all"]
    return [s.strip() for s in raw.split(",") if s.strip()]


# ─── ProxyInstance ────────────────────────────────────────────────────────────

class ProxyInstance:
    """Access-control policy for one config entry."""

    def __init__(
        self,
        name: str,
        tokens: List[str],
        restrict_out: str,
        restrict_out_cidrs: Optional[List[str]] = None,
        restrict_in_cidrs: Optional[List[str]] = None,
        timeout: int = 300,
        restrict_in: Optional[str] = None,      # legacy single-CIDR shim
    ) -> None:
        self.name = name
        # `tokens` kept as list (constant-time compare); `_token_bytes` are the
        # bytes used by hmac.compare_digest. Stored separately so we don't
        # encode on every request.
        self.tokens = list(tokens)
        self._token_bytes = [t.encode("utf-8") for t in self.tokens]
        self.timeout = timeout

        if restrict_out not in ("any", "external", "internal", "custom"):
            try:
                ipaddress.ip_network(restrict_out, strict=False)
                restrict_out_cidrs = list(restrict_out_cidrs or []) + [restrict_out]
                restrict_out = "custom"
            except ValueError:
                _LOGGER.warning("Invalid restrict_out '%s', defaulting to 'any'", restrict_out)
                restrict_out = "any"

        self.restrict_out = restrict_out
        self.restrict_out_cidrs = self._parse_cidrs(restrict_out_cidrs or [])

        in_list = list(restrict_in_cidrs or [])
        if restrict_in:
            in_list.append(restrict_in)
        self.restrict_in_cidrs = self._parse_cidrs(in_list)

    @staticmethod
    def _parse_cidrs(items: List[str]) -> List[ipaddress._BaseNetwork]:
        out = []
        for it in items:
            if not it:
                continue
            try:
                out.append(ipaddress.ip_network(it, strict=False))
            except ValueError:
                _LOGGER.warning("Invalid CIDR '%s', ignoring", it)
        return out

    def is_client_allowed(self, client_ip: str) -> bool:
        """Return True if the client IP is permitted to reach this endpoint."""
        if not self.restrict_in_cidrs:
            return True
        try:
            addr = ipaddress.ip_address(client_ip)
            return any(addr in cidr for cidr in self.restrict_in_cidrs)
        except ValueError:
            return False

    # Defence-in-depth: only these URL schemes are forwarded. Anything else
    # (file://, gopher://, ftp://, ldap://, dict://, data:, javascript:, …)
    # is rejected up-front so it can never reach the upstream session.
    _ALLOWED_SCHEMES = frozenset({"http", "https", "ws", "wss"})

    def _check_ip(self, target_ip: ipaddress._BaseAddress) -> bool:
        """Apply the configured outbound policy to a single resolved address."""
        if self.restrict_out == "custom":
            return any(target_ip in cidr for cidr in self.restrict_out_cidrs)
        if self.restrict_out == "external":
            return not any(target_ip in net for net in _PRIVATE_NETWORKS)
        if self.restrict_out == "internal":
            return any(target_ip in net for net in _PRIVATE_NETWORKS)
        return True  # "any"

    async def is_target_allowed(
        self,
        target_url: str,
        *,
        _parsed: Optional[urllib.parse.ParseResult] = None,
    ) -> bool:
        """Return True if the target URL passes outbound restrictions.

        DNS resolution uses the event loop's async getaddrinfo so the HA
        event loop is never blocked by a synchronous syscall. When a hostname
        resolves to multiple addresses, EVERY address must satisfy the policy
        — otherwise a multi-A-record / DNS-rebinding attacker could pass the
        check (public IP) and then aiohttp would connect to a different
        resolved address (private IP).

        ``_parsed`` lets the caller (``HomieProxyView._handle``) avoid
        re-parsing the same URL twice per request — pass the
        ``urllib.parse.urlparse(target_url)`` result here and we skip the
        second parse. Public callers (and tests) use the simple
        ``is_target_allowed(url)`` form.

        DNS results are cached for ``DNS_CACHE_TTL`` seconds; see
        ``_resolve_cached``.
        """
        try:
            parsed = _parsed if _parsed is not None else urllib.parse.urlparse(target_url)
            scheme = (parsed.scheme or "").lower()
            if scheme not in self._ALLOWED_SCHEMES:
                _LOGGER.debug("Rejecting unsupported URL scheme: %r", scheme)
                return False

            hostname = parsed.hostname
            if not hostname:
                return False

            try:
                target_ip = ipaddress.ip_address(hostname)  # already an IP literal
                return self._check_ip(target_ip)
            except ValueError:
                pass  # not an IP literal — fall through to DNS

            # Hostname — resolve via the cached resolver. The cache is
            # process-wide and TTL-bounded so we don't re-syscall for every
            # request to the same upstream host.
            addrs = await _resolve_cached(hostname)
            if addrs is None:
                _LOGGER.debug("DNS resolution failed for '%s'; denying", hostname)
                return False

            for s in addrs:
                try:
                    addr = ipaddress.ip_address(s)
                except ValueError:
                    return False
                if not self._check_ip(addr):
                    _LOGGER.debug(
                        "Rejecting %s — resolved address %s fails policy",
                        hostname, addr,
                    )
                    return False
            return True

        except Exception:
            return False

    def is_token_valid(self, token: Optional[str]) -> bool:
        """Constant-time token check. `token in self.tokens` short-circuits on
        first byte mismatch and is theoretically vulnerable to timing attacks
        — `hmac.compare_digest` is constant-time for equal-length strings."""
        if not token or not self._token_bytes:
            return False
        try:
            given = token.encode("utf-8")
        except (UnicodeEncodeError, AttributeError):
            return False
        # Iterate ALL configured tokens (no short-circuit) so the time taken
        # to reject a wrong token is independent of which slot would match.
        result = False
        for tb in self._token_bytes:
            if hmac.compare_digest(given, tb):
                result = True
        return result


# ─── HTTP view ────────────────────────────────────────────────────────────────

class HomieProxyView(HomeAssistantView):
    """Proxies HTTP (and WebSocket) requests to upstream targets.

    Previously the logic lived in a separate HomieProxyRequestHandler class;
    it is now inlined here to remove a layer of indirection.
    """

    def __init__(self, proxy_instance: ProxyInstance, requires_auth: bool = True) -> None:
        self.proxy_instance = proxy_instance
        self.url = f"/api/homie_proxy/{proxy_instance.name}"
        self.name = f"api:homie_proxy:{proxy_instance.name}"
        self.requires_auth = requires_auth
        _LOGGER.info(
            "Proxy endpoint '%s' — HA auth %s",
            proxy_instance.name,
            "required" if requires_auth else "not required (token only)",
        )

    # ── HTTP method dispatch ──────────────────────────────────────────────────

    async def get(self, request: Request) -> web.Response:
        return await self._handle(request, "GET")

    async def post(self, request: Request) -> web.Response:
        return await self._handle(request, "POST")

    async def put(self, request: Request) -> web.Response:
        return await self._handle(request, "PUT")

    async def patch(self, request: Request) -> web.Response:
        return await self._handle(request, "PATCH")

    async def delete(self, request: Request) -> web.Response:
        return await self._handle(request, "DELETE")

    async def head(self, request: Request) -> web.Response:
        return await self._handle(request, "HEAD")

    async def options(self, request: Request, **_kwargs: Any) -> web.Response:
        return await self._handle(request, "OPTIONS")

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _client_ip(request: Request) -> str:
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
        return request.headers.get("X-Real-IP") or request.remote or "127.0.0.1"

    def _error(
        self,
        code: int,
        message: str,
        qp: Optional[Dict[str, List[str]]] = None,
    ) -> web.Response:
        """JSON error response; replays response_header[] params so CORS headers
        are present even on error responses (otherwise browsers mask the real error)."""
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if qp:
            for key, values in qp.items():
                if key.startswith("response_header[") and key.endswith("]"):
                    headers[key[16:-1]] = values[0]
        return web.Response(
            text=json.dumps(
                {
                    "error": message,
                    "code": code,
                    "timestamp": datetime.now().isoformat(),
                    "instance": self.proxy_instance.name,
                },
                indent=2,
            ),
            status=code,
            headers=headers,
        )

    @staticmethod
    def _is_ws_upgrade(request: Request) -> bool:
        return (
            "upgrade" in request.headers.get("Connection", "").lower()
            and request.headers.get("Upgrade", "").lower() == "websocket"
        )

    @staticmethod
    def _normalise_qp(raw: Dict[str, Any]) -> Dict[str, List[str]]:
        """Ensure all query-param values are lists (HA's aiohttp gives plain strings)."""
        return {k: ([v] if isinstance(v, str) else list(v)) for k, v in raw.items()}

    async def _pick_session(self, skip_tls: List[str]) -> aiohttp.ClientSession:
        """Return the right session for the given TLS configuration."""
        ctx = _get_ssl_context(skip_tls)
        if ctx is not None:
            key = ",".join(sorted(c.lower() for c in skip_tls))
            return await _get_ssl_session(key, ctx)
        return await get_shared_session()

    # ── Core handler ──────────────────────────────────────────────────────────

    async def _handle(self, request: Request, method: str) -> web.Response:
        qp: Optional[Dict[str, List[str]]] = None
        try:
            qp = self._normalise_qp(dict(request.query))
            client_ip = self._client_ip(request)
            inst_name = self.proxy_instance.name

            # ── CORS preflight short-circuit (opt-in via ?cors_preflight=1) ──
            if method == "OPTIONS":
                if (qp.get("cors_preflight") or ["0"])[0].lower() in ("1", "true", "yes"):
                    cors_h = {
                        k[16:-1]: v[0]
                        for k, v in qp.items()
                        if k.startswith("response_header[") and k.endswith("]")
                    }
                    return web.Response(status=204, headers=cors_h)

            # ── Token auth first — prevents leaking access-control info ──────
            token = (qp.get("token") or [""])[0]
            if not self.proxy_instance.is_token_valid(token):
                # WARNING: a 401 here is the canonical signal of a brute-force
                # attempt or a leaked token being probed. Log enough to triage.
                _LOGGER.warning(
                    "homie_proxy/%s: 401 auth failed (client_ip=%s, "
                    "token_prefix=%r, ua=%r) — possible brute force / leaked token",
                    inst_name, client_ip, _mask_token(token),
                    request.headers.get("User-Agent", "")[:64],
                )
                return self._error(401, "Invalid or missing authentication token", qp)

            # ── Inbound IP check ──────────────────────────────────────────────
            if not self.proxy_instance.is_client_allowed(client_ip):
                _LOGGER.warning(
                    "homie_proxy/%s: 403 inbound IP rejected (client_ip=%s) — "
                    "valid token used from non-allowlisted network",
                    inst_name, client_ip,
                )
                return self._error(403, "Access denied from your IP", qp)

            # ── Target URL ────────────────────────────────────────────────────
            target_url = (qp.get("url") or [""])[0]
            if not target_url:
                return self._error(400, "Target URL required", qp)

            # Parse once, share with the policy check and the Host-header
            # logic below. Avoids a redundant urlparse() on every request.
            parsed_target = urllib.parse.urlparse(target_url)

            if not await self.proxy_instance.is_target_allowed(
                target_url, _parsed=parsed_target,
            ):
                _LOGGER.warning(
                    "homie_proxy/%s: 403 outbound URL rejected (client_ip=%s, "
                    "url=%s, mode=%s) — possible SSRF attempt",
                    inst_name, client_ip, _redact_url(target_url),
                    self.proxy_instance.restrict_out,
                )
                return self._error(403, "Access denied to the target URL", qp)

            _LOGGER.debug("%s %s → %s", method, inst_name, _redact_url(target_url))

            # ── Build upstream headers ────────────────────────────────────────
            headers = dict(request.headers)
            host = parsed_target.hostname

            host_override: Optional[str] = None
            for key, values in qp.items():
                if key.startswith("request_header[") and key.endswith("]"):
                    hname = key[15:-1]
                    if hname.lower() == "host":
                        host_override = values[0]
                    else:
                        headers[hname] = values[0]

            if host_override:
                headers["Host"] = host_override
            elif host:
                try:
                    ipaddress.ip_address(host)
                    headers.pop("Host", None)   # bare IP — no Host header
                except ValueError:
                    headers["Host"] = host

            headers.setdefault("User-Agent", "")

            # ── WebSocket upgrade ─────────────────────────────────────────────
            if self._is_ws_upgrade(request):
                return await self._handle_websocket(request, target_url, headers, qp)

            # ── Request body ──────────────────────────────────────────────────
            body: Optional[bytes] = None
            if method in ("POST", "PUT", "PATCH"):
                try:
                    body = await request.read()
                except Exception as exc:
                    _LOGGER.error("Failed to read request body: %s", exc)
                    return self._error(400, "Failed to read request body", qp)

            # ── TLS / session / timeout ───────────────────────────────────────
            skip_tls = _parse_skip_tls(qp)
            session = await self._pick_session(skip_tls)

            follow = (qp.get("follow_redirects") or ["false"])[0].lower() in ("true", "1", "yes")

            timeout_raw = (qp.get("timeout") or [""])[0]
            timeout_secs = int(timeout_raw) if timeout_raw.isdigit() else self.proxy_instance.timeout
            is_streaming = (qp.get("stream") or [""])[0] == "1"
            timeout = (
                aiohttp.ClientTimeout(total=None, sock_read=timeout_secs)
                if is_streaming
                else aiohttp.ClientTimeout(total=timeout_secs)
            )

            # ── Redirect handling ────────────────────────────────────────────
            # When restrict_out is "any" we let aiohttp follow redirects
            # natively (no policy concerns). When the user has any tighter
            # mode, we MUST validate every redirect target — otherwise an
            # open redirector at a public URL can bounce us to internal IPs.
            #
            # See _follow_with_revalidation. Streaming + redirect-following
            # is rare; we don't combine them (caller can pre-resolve).
            need_manual_redirects = (
                follow
                and not is_streaming
                and self.proxy_instance.restrict_out != "any"
            )

            # ── Outbound request (retry once on stale keep-alive) ─────────────
            req_kwargs: Dict[str, Any] = {
                "method": method, "url": target_url,
                "headers": headers,
                "allow_redirects": (follow and not need_manual_redirects),
                "timeout": timeout,
            }
            if body is not None:
                req_kwargs["data"] = body

            if need_manual_redirects:
                return await self._follow_with_revalidation(
                    session, req_kwargs, qp, client_ip, inst_name,
                )

            attempts = 1 if is_streaming else 2
            last_err: Optional[Exception] = None

            for attempt in range(attempts):
                try:
                    async with session.request(**req_kwargs) as resp:
                        resp_headers: Dict[str, str] = {
                            k: v for k, v in resp.headers.items()
                            if k.lower() not in _HOP_BY_HOP_RESPONSE
                        }
                        for key, values in qp.items():
                            if key.startswith("response_header[") and key.endswith("]"):
                                resp_headers[key[16:-1]] = values[0]

                        if is_streaming:
                            stream_resp = web.StreamResponse(
                                status=resp.status, headers=resp_headers
                            )
                            await stream_resp.prepare(request)
                            total = 0
                            async for chunk in resp.content.iter_chunked(STREAM_CHUNK_SIZE):
                                if chunk:
                                    await stream_resp.write(chunk)
                                    total += len(chunk)
                            await stream_resp.write_eof()
                            _LOGGER.debug("Streamed %d bytes from %s", total, _redact_url(target_url))
                            return stream_resp

                        data = await resp.read()
                        _LOGGER.debug("Response HTTP %d, %d bytes", resp.status, len(data))
                        return web.Response(body=data, status=resp.status, headers=resp_headers)

                except (aiohttp.ServerDisconnectedError, aiohttp.ClientOSError) as exc:
                    last_err = exc
                    if attempt + 1 >= attempts:
                        raise
                    _LOGGER.debug("Retrying after stale-connection error: %s", exc)

            raise last_err or RuntimeError("request loop exited without a response")

        except aiohttp.ClientError as exc:
            return self._error(502, f"Bad Gateway: {exc}", qp)
        except asyncio.TimeoutError:
            return self._error(504, "Gateway Timeout", qp)
        except Exception as exc:
            _LOGGER.error("Proxy error: %s", exc)
            return self._error(500, "Internal server error", qp)

    # ── Manual redirect follower with policy re-validation ───────────────────

    async def _follow_with_revalidation(
        self,
        session: aiohttp.ClientSession,
        req_kwargs: Dict[str, Any],
        qp: Dict[str, List[str]],
        client_ip: str,
        inst_name: str,
    ) -> web.Response:
        """Follow up to MAX_REDIRECT_HOPS redirects, re-validating each new
        target against the outbound policy before issuing the next request.

        Without this, an attacker who can plant a 302 at a public URL could
        bounce the proxy to an internal IP (`restrict_out=external` would
        check the public URL once and then aiohttp's auto-follow would chase
        the redirect to the internal IP unchecked)."""
        seen: set = set()
        kwargs = dict(req_kwargs)
        kwargs["allow_redirects"] = False

        for hop in range(MAX_REDIRECT_HOPS + 1):
            current_url = kwargs["url"]
            if current_url in seen:
                _LOGGER.warning(
                    "homie_proxy/%s: redirect loop detected (client_ip=%s, "
                    "url=%s)",
                    inst_name, client_ip, _redact_url(current_url),
                )
                return self._error(508, "Redirect loop detected", qp)
            seen.add(current_url)

            async with session.request(**kwargs) as resp:
                resp_headers: Dict[str, str] = {
                    k: v for k, v in resp.headers.items()
                    if k.lower() not in _HOP_BY_HOP_RESPONSE
                }
                for key, values in qp.items():
                    if key.startswith("response_header[") and key.endswith("]"):
                        resp_headers[key[16:-1]] = values[0]

                # Not a redirect, or no Location header → return as-is.
                if not (300 <= resp.status < 400):
                    data = await resp.read()
                    return web.Response(
                        body=data, status=resp.status, headers=resp_headers,
                    )
                location = resp.headers.get("Location")
                if not location:
                    data = await resp.read()
                    return web.Response(
                        body=data, status=resp.status, headers=resp_headers,
                    )

                next_url = urllib.parse.urljoin(current_url, location)
                if not await self.proxy_instance.is_target_allowed(next_url):
                    _LOGGER.warning(
                        "homie_proxy/%s: 403 redirect target rejected "
                        "(client_ip=%s, from=%s, to=%s, mode=%s) — possible "
                        "SSRF via open-redirect",
                        inst_name, client_ip,
                        _redact_url(current_url), _redact_url(next_url),
                        self.proxy_instance.restrict_out,
                    )
                    return self._error(
                        403, "Redirect target blocked by access policy", qp,
                    )

                kwargs = dict(kwargs)
                kwargs["url"] = next_url
                # Per RFC 7231 §6.4.3: 303 changes method to GET; for 301/302
                # most user-agents also change POST→GET (we do the same).
                if resp.status in (301, 302, 303) and kwargs.get("method") in (
                    "POST", "PUT", "PATCH"
                ):
                    kwargs["method"] = "GET"
                    kwargs.pop("data", None)

        _LOGGER.warning(
            "homie_proxy/%s: 508 redirect chain exceeded MAX_REDIRECT_HOPS (%d) "
            "(client_ip=%s)",
            inst_name, MAX_REDIRECT_HOPS, client_ip,
        )
        return self._error(508, "Too many redirects", qp)

    # ── WebSocket relay ───────────────────────────────────────────────────────

    async def _handle_websocket(
        self,
        request: Request,
        target_url: str,
        headers: Dict[str, str],
        qp: Dict[str, List[str]],
    ) -> web.StreamResponse:
        """Relay a WebSocket connection bidirectionally using aiohttp's WS client.

        Replaces the previous websockets-library implementation; aiohttp already
        ships as an HA dependency so no extra package is needed.
        """
        if target_url.startswith("https://"):
            ws_url = "wss://" + target_url[8:]
        elif target_url.startswith("http://"):
            ws_url = "ws://" + target_url[7:]
        else:
            return self._error(400, "Invalid URL scheme for WebSocket", qp)

        ws_headers = {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP_WS}
        for key, values in qp.items():
            if key.startswith("request_header[") and key.endswith("]"):
                ws_headers[key[15:-1]] = values[0]

        skip_tls = _parse_skip_tls(qp)
        session = await self._pick_session(skip_tls)

        client_ws = web.WebSocketResponse()
        await client_ws.prepare(request)

        try:
            async with session.ws_connect(ws_url, headers=ws_headers) as target_ws:
                _LOGGER.debug("WebSocket relay open: %s", ws_url)

                async def fwd_c2t() -> None:
                    async for msg in client_ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await target_ws.send_str(msg.data)
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            await target_ws.send_bytes(msg.data)
                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSE,
                            aiohttp.WSMsgType.CLOSING,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            break

                async def fwd_t2c() -> None:
                    async for msg in target_ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            await client_ws.send_str(msg.data)
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            await client_ws.send_bytes(msg.data)
                        elif msg.type in (
                            aiohttp.WSMsgType.CLOSE,
                            aiohttp.WSMsgType.CLOSING,
                            aiohttp.WSMsgType.ERROR,
                        ):
                            break

                await asyncio.gather(fwd_c2t(), fwd_t2c(), return_exceptions=True)
                _LOGGER.debug("WebSocket relay closed: %s", ws_url)

        except aiohttp.ClientError as exc:
            _LOGGER.warning("WebSocket to %s failed: %s", ws_url, exc)
            if not client_ws.closed:
                await client_ws.close()

        return client_ws


# ─── Debug view ───────────────────────────────────────────────────────────────

class HomieProxyDebugView(HomeAssistantView):
    """Read-only debug endpoint listing all active proxy instances."""

    url = "/api/homie_proxy/debug"
    name = "api:homie_proxy:debug"

    def __init__(self, requires_auth: bool = True) -> None:
        super().__init__()
        self.requires_auth = requires_auth
        if requires_auth:
            _LOGGER.info("Debug endpoint requires HA authentication")
        else:
            _LOGGER.warning(
                "Debug endpoint accessible WITHOUT HA authentication — tokens visible in output"
            )

    async def get(self, request: Request) -> web.Response:
        # Wrap everything so we can return a JSON error rather than the bare
        # aiohttp 500 stub. Without this any malformed entry crashes the whole
        # debug view and makes it look broken.
        try:
            # HomeAssistantView does NOT auto-populate `self.hass`. The
            # canonical way to get hass from inside a view is via the request:
            # `request.app["hass"]` — works regardless of auth state.
            hass = request.app["hass"]
            domain_data = hass.data.get(DOMAIN, {})

            # Skip non-entry keys ("global_config", "debug_view_registered",
            # "debug_view_instance"). Only entries are dicts with "service".
            entry_dicts = [
                d for d in domain_data.values()
                if isinstance(d, dict) and "service" in d and d["service"] is not None
            ]
            instances = {d["service"].name: d["service"] for d in entry_dicts}

            instance_info: Dict[str, Any] = {}
            for name, svc in instances.items():
                try:
                    instance_info[name] = {
                        "name": svc.name,
                        # Tokens masked: first 4 chars + ***. Full tokens are
                        # never echoed back so this JSON is safe to share.
                        "tokens": [_mask_token(t) for t in (svc.tokens or [])],
                        "token_count": len(svc.tokens or []),
                        "restrict_out": svc.restrict_out,
                        # Coerce in case stale entries stored ip_network objects.
                        "restrict_out_cidrs": [str(c) for c in (svc.restrict_out_cidrs or [])],
                        "restrict_in_cidrs": [str(c) for c in (svc.restrict_in_cidrs or [])],
                        "timeout": int(svc.timeout) if svc.timeout is not None else None,
                        "requires_auth": bool(svc.requires_auth),
                        "debug_requires_auth": bool(getattr(svc, "debug_requires_auth", True)),
                        "endpoint_url": f"/api/homie_proxy/{svc.name}",
                        "status": "active" if svc.view else "inactive",
                    }
                except Exception as exc:
                    _LOGGER.exception("debug: failed to render instance %r", name)
                    instance_info[name] = {"error": f"render failed: {exc}"}

            info: Dict[str, Any] = {
                "timestamp": datetime.now().isoformat(),
                "instances": instance_info,
                "system": {
                    "private_cidrs": PRIVATE_CIDRS,
                    "available_restrictions": ["any", "external", "internal", "custom"],
                },
                "debug": {
                    "authentication_required": self.requires_auth,
                    "logging_level": logging.getLogger(
                        "custom_components.homie_proxy"
                    ).getEffectiveLevel(),
                },
            }

            return web.Response(
                text=json.dumps(info, indent=2, ensure_ascii=False, default=str),
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-cache"},
            )

        except Exception as exc:
            # Log the full traceback to HA logs so we can diagnose; return a
            # JSON error body instead of the aiohttp 500 stub.
            _LOGGER.exception("Debug view crashed: %s", exc)
            return web.Response(
                text=json.dumps({
                    "error": "debug view crashed",
                    "type": type(exc).__name__,
                    "message": str(exc),
                    "hint": "see Home Assistant logs (search 'homie_proxy') for full traceback",
                }, indent=2),
                status=500,
                content_type="application/json",
                headers={"Access-Control-Allow-Origin": "*"},
            )


# ─── Service ──────────────────────────────────────────────────────────────────

class HomieProxyService:
    """Manages one config-entry's proxy lifecycle."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        tokens: List[str],
        restrict_out: str,
        restrict_out_cidrs: Optional[List[str]] = None,
        restrict_in_cidrs: Optional[List[str]] = None,
        timeout: int = 300,
        requires_auth: bool = True,
        debug_requires_auth: bool = True,
        restrict_in: Optional[str] = None,  # legacy shim
    ) -> None:
        self.hass = hass
        self.name = name
        self.tokens = tokens
        self.restrict_out = restrict_out
        self.restrict_out_cidrs = list(restrict_out_cidrs or [])
        self.restrict_in_cidrs = list(restrict_in_cidrs or ([restrict_in] if restrict_in else []))
        self.timeout = timeout
        self.requires_auth = requires_auth
        self.debug_requires_auth = debug_requires_auth
        self.view: Optional[HomieProxyView] = None
        self.proxy_instance: Optional[ProxyInstance] = None

    async def setup(self) -> None:
        """Create the ProxyInstance and register HTTP views."""
        _LOGGER.info("Setting up Homie Proxy service: %s", self.name)

        self.proxy_instance = ProxyInstance(
            name=self.name,
            tokens=self.tokens,
            restrict_out=self.restrict_out,
            restrict_out_cidrs=self.restrict_out_cidrs,
            restrict_in_cidrs=self.restrict_in_cidrs,
            timeout=self.timeout,
        )

        # Register the debug view once per HA run, tracked via hass.data so it
        # survives entry remove → re-add without attempting to re-register the URL.
        # Note: aiohttp's router doesn't support unregistering a view, hence
        # the once-per-run pattern.
        domain_data: Dict[str, Any] = self.hass.data.setdefault(DOMAIN, {})
        if not domain_data.get("debug_view_registered"):
            debug_view = HomieProxyDebugView(requires_auth=self.debug_requires_auth)
            self.hass.http.register_view(debug_view)
            domain_data["debug_view_registered"] = True
            # Keep a reference so auth can be toggled live without re-registration.
            domain_data["debug_view_instance"] = debug_view
            _LOGGER.info("Registered debug endpoint at /api/homie_proxy/debug")
        else:
            # View already registered (re-setup after entry reload). Apply
            # THIS entry's debug_requires_auth to the live view so the saved
            # value takes effect immediately — without this, a reload would
            # reuse whatever value was set the first time HA started.
            existing_view = domain_data.get("debug_view_instance")
            if existing_view is not None and existing_view.requires_auth != self.debug_requires_auth:
                existing_view.requires_auth = self.debug_requires_auth
                _LOGGER.info(
                    "Debug endpoint auth applied from entry '%s': requires_auth=%s",
                    self.name, self.debug_requires_auth,
                )

        self.view = HomieProxyView(
            proxy_instance=self.proxy_instance,
            requires_auth=self.requires_auth,
        )
        try:
            self.hass.http.register_view(self.view)
        except Exception as exc:
            if "already has OPTIONS handler" in str(exc):
                _LOGGER.warning("OPTIONS handler conflict for '%s' (harmless)", self.name)
            else:
                _LOGGER.error("Failed to register view for '%s': %s", self.name, exc)
                raise

        _LOGGER.info(
            "Homie Proxy '%s' ready at /api/homie_proxy/%s — %d token(s), timeout=%ds",
            self.name, self.name, len(self.tokens), self.timeout,
        )

    async def update(
        self,
        tokens: List[str],
        restrict_out: str,
        restrict_out_cidrs: Optional[List[str]] = None,
        restrict_in_cidrs: Optional[List[str]] = None,
        timeout: int = 300,
        requires_auth: bool = True,
        debug_requires_auth: bool = True,
        restrict_in: Optional[str] = None,  # legacy shim
    ) -> None:
        """Update proxy policy in-place — no HTTP re-registration needed.

        All settings take effect immediately on the next request; a reload is
        no longer required for token, CIDR, timeout, or auth changes.
        """
        self.tokens = tokens
        self.restrict_out = restrict_out
        self.restrict_out_cidrs = list(restrict_out_cidrs or [])
        in_list = list(restrict_in_cidrs or [])
        if restrict_in:
            in_list.append(restrict_in)
        self.restrict_in_cidrs = in_list
        self.timeout = timeout
        self.requires_auth = requires_auth
        self.debug_requires_auth = debug_requires_auth

        if self.proxy_instance is not None:
            self.proxy_instance.tokens = list(tokens)
            self.proxy_instance._token_bytes = [t.encode("utf-8") for t in tokens]
            self.proxy_instance.restrict_out = (
                restrict_out if restrict_out in ("any", "external", "internal", "custom") else "any"
            )
            self.proxy_instance.restrict_out_cidrs = ProxyInstance._parse_cidrs(self.restrict_out_cidrs)
            self.proxy_instance.restrict_in_cidrs = ProxyInstance._parse_cidrs(in_list)
            self.proxy_instance.timeout = timeout

        # Propagate HA-auth flag to the live view immediately so the middleware
        # picks it up on the next request without a full entry reload.
        if self.view is not None:
            self.view.requires_auth = requires_auth

        # Propagate debug-auth change to the shared debug view if it exists.
        domain_data = self.hass.data.get(DOMAIN, {})
        debug_view = domain_data.get("debug_view_instance")
        if debug_view is not None and debug_view.requires_auth != debug_requires_auth:
            debug_view.requires_auth = debug_requires_auth
            _LOGGER.info(
                "Debug endpoint auth updated: requires_auth=%s (changed by entry '%s')",
                debug_requires_auth, self.name,
            )

        _LOGGER.info(
            "Updated proxy '%s': %d token(s), timeout=%ds, out=%s, in_cidrs=%d",
            self.name, len(tokens), timeout, restrict_out, len(in_list),
        )

    async def cleanup(self) -> None:
        """Remove service state. hass.data entry is cleaned up by __init__.py."""
        _LOGGER.info("Cleaning up Homie Proxy service: %s", self.name)
        # Global session pool is closed by async_unload_entry when this is
        # the last active instance.
