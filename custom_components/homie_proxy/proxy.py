"""Homie Proxy service for Home Assistant."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import socket
import ssl
import urllib.parse
from datetime import datetime
from typing import Any, Dict, List, Optional

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
            )
        )
    return _shared_session


async def _get_ssl_session(key: str, ctx: ssl.SSLContext) -> aiohttp.ClientSession:
    """Return a cached session that uses *ctx* for all connections."""
    if key not in _ssl_sessions or _ssl_sessions[key].closed:
        _ssl_sessions[key] = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=ctx)
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
        restrict_in: Optional[str] = None,  # legacy single-CIDR shim
    ) -> None:
        self.name = name
        self.tokens = set(tokens)
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

    async def is_target_allowed(self, target_url: str) -> bool:
        """Return True if the target URL passes outbound restrictions.

        DNS resolution uses the event loop's async getaddrinfo so the
        HA event loop is never blocked by a synchronous syscall.
        """
        try:
            hostname = urllib.parse.urlparse(target_url).hostname
            if not hostname:
                return False

            try:
                target_ip = ipaddress.ip_address(hostname)  # already an IP literal
            except ValueError:
                # Hostname — resolve without blocking the event loop.
                loop = asyncio.get_running_loop()
                try:
                    info = await loop.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
                    target_ip = ipaddress.ip_address(info[0][4][0])
                except (OSError, IndexError, ValueError):
                    _LOGGER.debug("DNS resolution failed for '%s'; denying", hostname)
                    return False

            if self.restrict_out == "custom":
                return any(target_ip in cidr for cidr in self.restrict_out_cidrs)
            if self.restrict_out == "external":
                return not any(target_ip in net for net in _PRIVATE_NETWORKS)
            if self.restrict_out == "internal":
                return any(target_ip in net for net in _PRIVATE_NETWORKS)
            return True  # "any"

        except Exception:
            return False

    def is_token_valid(self, token: Optional[str]) -> bool:
        return bool(token) and bool(self.tokens) and token in self.tokens


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
                _LOGGER.debug("Auth failed on '%s'", self.proxy_instance.name)
                return self._error(401, "Invalid or missing authentication token", qp)

            # ── Inbound IP check ──────────────────────────────────────────────
            if not self.proxy_instance.is_client_allowed(client_ip):
                _LOGGER.debug("Inbound IP denied: %s → '%s'", client_ip, self.proxy_instance.name)
                return self._error(403, "Access denied from your IP", qp)

            # ── Target URL ────────────────────────────────────────────────────
            target_url = (qp.get("url") or [""])[0]
            if not target_url:
                return self._error(400, "Target URL required", qp)

            if not await self.proxy_instance.is_target_allowed(target_url):
                _LOGGER.debug("Outbound URL denied: %s", target_url)
                return self._error(403, "Access denied to the target URL", qp)

            _LOGGER.debug("%s %s → %s", method, self.proxy_instance.name, target_url)

            # ── Build upstream headers ────────────────────────────────────────
            headers = dict(request.headers)
            host = urllib.parse.urlparse(target_url).hostname

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

            # ── Outbound request (retry once on stale keep-alive) ─────────────
            req_kwargs: Dict[str, Any] = {
                "method": method, "url": target_url,
                "headers": headers, "allow_redirects": follow, "timeout": timeout,
            }
            if body is not None:
                req_kwargs["data"] = body

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
                            async for chunk in resp.content.iter_chunked(8192):
                                if chunk:
                                    await stream_resp.write(chunk)
                                    total += len(chunk)
                            await stream_resp.write_eof()
                            _LOGGER.debug("Streamed %d bytes from %s", total, target_url)
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
        domain_data = self.hass.data.get(DOMAIN, {})
        instances = {
            data["service"].name: data["service"]
            for data in domain_data.values()
            if isinstance(data, dict) and "service" in data
        }

        info: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "instances": {
                name: {
                    "name": svc.name,
                    "tokens": list(svc.tokens),
                    "restrict_out": svc.restrict_out,
                    "restrict_out_cidrs": list(svc.restrict_out_cidrs),
                    "restrict_in_cidrs": list(svc.restrict_in_cidrs),
                    "timeout": svc.timeout,
                    "requires_auth": svc.requires_auth,
                    "endpoint_url": f"/api/homie_proxy/{svc.name}",
                    "status": "active" if svc.view else "inactive",
                }
                for name, svc in instances.items()
            },
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
            text=json.dumps(info, indent=2, ensure_ascii=False),
            content_type="application/json",
            headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-cache"},
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
        domain_data: Dict[str, Any] = self.hass.data.setdefault(DOMAIN, {})
        if not domain_data.get("debug_view_registered"):
            debug_view = HomieProxyDebugView(requires_auth=self.debug_requires_auth)
            self.hass.http.register_view(debug_view)
            domain_data["debug_view_registered"] = True
            _LOGGER.info("Registered debug endpoint at /api/homie_proxy/debug")

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
            self.proxy_instance.tokens = set(tokens)
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

        _LOGGER.info(
            "Updated proxy '%s': %d token(s), timeout=%ds, out=%s, in_cidrs=%d",
            self.name, len(tokens), timeout, restrict_out, len(in_list),
        )

    async def cleanup(self) -> None:
        """Remove service state. hass.data entry is cleaned up by __init__.py."""
        _LOGGER.info("Cleaning up Homie Proxy service: %s", self.name)
        # Global session pool is closed by async_unload_entry when this is
        # the last active instance.
