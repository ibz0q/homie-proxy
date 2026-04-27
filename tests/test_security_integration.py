"""
End-to-end security tests against the standalone HomieProxy server.

These exercise the full request pipeline (token → inbound IP → URL policy
→ upstream → response) for properties that can only be observed across the
wire: redirect re-validation, debug-endpoint token masking, header
injection sanitisation, log redaction, and per-reject-path WARNING logs.

Pure-policy / no-server tests live in test_security.py.

Run with:
    pytest tests/test_security_integration.py -v
"""
import asyncio
import json
import logging
import pytest
import aiohttp
from aiohttp import web

from conftest import load_standalone as _load_standalone
_standalone = _load_standalone()
HomieProxyServer = _standalone.HomieProxyServer

# asyncio_mode = auto handles async test discovery.


# ─── Helper: spawn a proxy with a single instance ─────────────────────────────

def make_srv(**instance_overrides) -> HomieProxyServer:
    cfg = {
        "restrict_out": "any",
        "tokens": ["good-token"],
        "restrict_in_cidrs": [],
        "timeout": 5,
    }
    cfg.update(instance_overrides)
    srv = HomieProxyServer()
    srv.instances = {}
    srv.add_instance("test", cfg)
    return srv


# ─── Follow-redirects re-validation ──────────────────────────────────────────

@pytest.fixture
async def redirect_upstream(aiohttp_server):
    """Upstream that responds 302 to whatever URL the test passes via ?to=."""
    async def redirect(req):
        return web.HTTPFound(location=req.query.get("to", "/echo"))
    async def echo(req):
        return web.Response(text="ok")
    app = web.Application()
    app.router.add_get("/redir", redirect)
    app.router.add_get("/echo", echo)
    return await aiohttp_server(app)


class TestRedirectRevalidation:
    async def test_redirect_to_internal_blocked_in_external_mode(
        self, redirect_upstream, aiohttp_client,
    ):
        """A redirect chain that ends at an internal IP must be blocked when
        the instance is configured for external-only — even though the FIRST
        URL was external. Without the manual redirect follower, aiohttp would
        chase the Location header and connect to the internal address."""
        srv = HomieProxyServer()
        srv.instances = {}
        # Allow the upstream's own loopback so the FIRST hop succeeds, but
        # forbid 192.168.0.0/16 — the redirect target.
        srv.add_instance("test", {
            "restrict_out": "custom",
            "restrict_out_cidrs": ["127.0.0.0/8"],
            "tokens": ["good-token"],
            "restrict_in_cidrs": [],
            "timeout": 5,
        })
        client = await aiohttp_client(srv.create_app())
        # Upstream redirects to http://192.168.255.255/ which fails the policy.
        resp = await client.get("/test", params={
            "token": "good-token",
            "url": str(redirect_upstream.make_url("/redir?to=http://192.168.255.255/")),
            "follow_redirects": "true",
        }, allow_redirects=False)
        # Because the first hop succeeded, then the redirect target was
        # rejected, we expect a 403 — the proxy's policy engine, not the
        # upstream's response.
        assert resp.status == 403, (
            "Open-redirect → SSRF: the redirect target should have been "
            "re-validated against the outbound policy."
        )

    async def test_internal_redirect_in_any_mode_is_followed(
        self, redirect_upstream, aiohttp_client,
    ):
        """When restrict_out=any, redirects don't need re-validation —
        aiohttp's native follow is fine."""
        srv = make_srv(restrict_out="any")
        client = await aiohttp_client(srv.create_app())
        resp = await client.get("/test", params={
            "token": "good-token",
            "url": str(redirect_upstream.make_url(
                f"/redir?to={redirect_upstream.make_url('/echo')}"
            )),
            "follow_redirects": "true",
        })
        assert resp.status == 200
        assert (await resp.text()) == "ok"


# ─── Header injection ────────────────────────────────────────────────────────

class TestHeaderInjection:
    async def test_crlf_injection_in_request_header_does_not_smuggle(
        self, upstream, aiohttp_client,
    ):
        """A `request_header[X]=foo\\r\\nEvil-Header: bar` value must NOT
        result in `Evil-Header` being injected into the upstream request.

        Two acceptable outcomes:
          (a) aiohttp / the proxy reject the bad header (any 4xx/5xx, OR
              the client raises) — the injection never reaches upstream.
          (b) aiohttp accepts and strips the bad bytes, upstream sees no
              `X-Injected` header.

        Either way, the upstream MUST NOT see the injected header. We
        always assert the negative property — no early return."""
        client = await aiohttp_client(make_srv().create_app())
        injected_seen = None  # tri-state: None=request raised, False=safe, True=BAD
        try:
            resp = await client.get("/test", params={
                "token": "good-token",
                "url": str(upstream.make_url("/echo")),
                "request_header[X-Test]": "value\r\nX-Injected: pwned",
            })
        except (aiohttp.ClientError, ValueError):
            # Path (a): client refused. The bad header never went on the wire.
            # That's a pass — but we record it so the test can't silently
            # become a no-op.
            injected_seen = False
        else:
            if resp.status == 200:
                data = await resp.json()
                upstream_headers = {k.lower() for k in data["headers"]}
                injected_seen = "x-injected" in upstream_headers
            else:
                # Path (a) variant: proxy rejected it before sending.
                injected_seen = False

        assert injected_seen is False, (
            "CRLF header injection reached the upstream — request smuggling."
        )

    async def test_null_byte_in_header_rejected(self, upstream, aiohttp_client):
        """A null byte inside a header value must not propagate to upstream.
        Either the client rejects it or the proxy strips it; same property."""
        client = await aiohttp_client(make_srv().create_app())
        leaked = None
        try:
            resp = await client.get("/test", params={
                "token": "good-token",
                "url": str(upstream.make_url("/echo")),
                "request_header[X-Test]": "value\x00with-null",
            })
        except (aiohttp.ClientError, ValueError):
            leaked = False
        else:
            if resp.status == 200:
                data = await resp.json()
                # The full null-bearing value must not appear at upstream.
                leaked = any(
                    "\x00" in v for v in data["headers"].values()
                )
            else:
                leaked = False

        assert leaked is False, (
            "Null byte in header value reached the upstream untouched."
        )


# ─── Debug endpoint masks tokens ─────────────────────────────────────────────

class TestDebugTokenMasking:
    async def test_debug_does_not_leak_full_tokens(self, aiohttp_client):
        """The /debug endpoint must NEVER echo back the full token value —
        only the first 4 characters followed by ***. Otherwise sharing a
        debug bundle (logs, screenshots, bug report) would leak credentials."""
        srv = HomieProxyServer()
        srv.instances = {}
        srv.add_instance("test", {
            "restrict_out": "any",
            "tokens": ["super-secret-token-that-must-not-leak"],
            "restrict_in_cidrs": [],
        })
        client = await aiohttp_client(srv.create_app())
        resp = await client.get("/debug")
        assert resp.status == 200
        body = await resp.text()
        assert "super-secret-token-that-must-not-leak" not in body, (
            "Full token leaked in /debug output."
        )
        data = json.loads(body)
        masked = data["instances"]["test"]["tokens"][0]
        assert masked.startswith("supe"), f"Expected first-4-chars masking, got {masked!r}"
        assert masked.endswith("***"), f"Expected *** suffix, got {masked!r}"

    async def test_debug_short_tokens_fully_masked(self, aiohttp_client):
        """Tokens 4 chars or shorter must be fully masked (no prefix at all)."""
        srv = HomieProxyServer()
        srv.instances = {}
        srv.add_instance("test", {
            "restrict_out": "any",
            "tokens": ["abc"],
            "restrict_in_cidrs": [],
        })
        client = await aiohttp_client(srv.create_app())
        resp = await client.get("/debug")
        data = await resp.json()
        masked = data["instances"]["test"]["tokens"][0]
        assert "abc" not in masked, f"Short token leaked: {masked!r}"
        assert masked == "***"

    async def test_debug_reports_token_count(self, aiohttp_client):
        srv = HomieProxyServer()
        srv.instances = {}
        srv.add_instance("test", {
            "restrict_out": "any",
            "tokens": ["t1", "t2", "t3"],
            "restrict_in_cidrs": [],
        })
        client = await aiohttp_client(srv.create_app())
        data = await (await client.get("/debug")).json()
        assert data["instances"]["test"]["token_count"] == 3
        assert len(data["instances"]["test"]["tokens"]) == 3


# ─── Log redaction ───────────────────────────────────────────────────────────

class TestLogRedaction:
    """If a logged URL contains `?token=…` (or password/secret/api_key), the
    log message must not include the raw value. We assert this by capturing
    log records and scanning them."""

    async def test_outbound_reject_log_redacts_token(
        self, upstream, aiohttp_client, caplog,
    ):
        srv = HomieProxyServer()
        srv.instances = {}
        srv.add_instance("test", {
            "restrict_out": "external",  # will reject loopback upstream
            "tokens": ["good-token"],
            "restrict_in_cidrs": [],
        })
        client = await aiohttp_client(srv.create_app())
        with caplog.at_level(logging.WARNING):
            await client.get("/test", params={
                "token": "good-token",
                "url": "http://127.0.0.1:1/secret-path?token=upstream-creds",
            })
        for record in caplog.records:
            assert "upstream-creds" not in record.getMessage(), (
                f"token leaked in log message: {record.getMessage()!r}"
            )

    async def test_redact_url_helper(self):
        from importlib import import_module
        # Pull the helper out of the standalone module we already loaded.
        redact = _standalone._redact_url
        assert redact("http://x/?token=abc&foo=bar") == "http://x/?token=***&foo=bar"
        assert redact("http://x/?TOKEN=abc&foo=bar") == "http://x/?TOKEN=***&foo=bar"
        assert redact("http://x/?password=hunter2") == "http://x/?password=***"
        assert redact("http://x/?api_key=KKK&password=PPP") == "http://x/?api_key=***&password=***"
        assert redact("http://x/?api-key=KKK") == "http://x/?api-key=***"
        # Unrelated query params untouched.
        assert redact("http://x/?other=ok") == "http://x/?other=ok"


# ─── Security WARNING events fire on every reject path ──────────────────────

class TestSecurityLogging:
    async def test_auth_fail_logs_warning(self, upstream, aiohttp_client, caplog):
        srv = make_srv()
        client = await aiohttp_client(srv.create_app())
        with caplog.at_level(logging.WARNING):
            await client.get("/test", params={
                "token": "wrong-token",
                "url": str(upstream.make_url("/echo")),
            })
        msgs = " ".join(r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING)
        assert "401" in msgs and "auth failed" in msgs

    async def test_outbound_reject_logs_warning(self, aiohttp_client, caplog):
        srv = HomieProxyServer()
        srv.instances = {}
        srv.add_instance("test", {
            "restrict_out": "external",
            "tokens": ["good-token"],
            "restrict_in_cidrs": [],
        })
        client = await aiohttp_client(srv.create_app())
        with caplog.at_level(logging.WARNING):
            await client.get("/test", params={
                "token": "good-token",
                "url": "http://192.168.1.1/api",
            })
        msgs = " ".join(r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING)
        assert "403" in msgs and "SSRF" in msgs

    async def test_inbound_reject_logs_warning(self, upstream, aiohttp_client, caplog):
        srv = HomieProxyServer()
        srv.instances = {}
        srv.add_instance("test", {
            "restrict_out": "any",
            "tokens": ["good-token"],
            "restrict_in_cidrs": ["10.0.0.0/8"],   # test client comes from 127.x
        })
        client = await aiohttp_client(srv.create_app())
        with caplog.at_level(logging.WARNING):
            await client.get("/test", params={
                "token": "good-token",
                "url": str(upstream.make_url("/echo")),
            })
        msgs = " ".join(r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING)
        assert "403" in msgs and "inbound IP" in msgs


# ─── Debug endpoint accessibility (standalone has no auth gate) ──────────────

class TestStandaloneDebugAccess:
    """Standalone /debug has no auth gate by design — it's a development /
    troubleshooting aid. The HA component sets `requires_auth=True` by
    default and lets HA's own auth middleware handle it (covered separately
    below). This class pins the standalone behaviour."""

    async def test_debug_accessible_without_token(self, aiohttp_client):
        srv = HomieProxyServer()
        srv.instances = {}
        srv.add_instance("test", {"restrict_out": "any", "tokens": ["t"], "restrict_in_cidrs": []})
        client = await aiohttp_client(srv.create_app())
        resp = await client.get("/debug")
        assert resp.status == 200
        data = await resp.json()
        assert "test" in data["instances"]


# ─── HA debug endpoint: requires_auth attribute is honoured ──────────────────

class TestHADebugViewAuthFlag:
    """The HomieProxyDebugView reads `requires_auth` from its constructor
    arg. HA's auth middleware then enforces or skips authentication based
    on that attribute. We can't run HA's middleware here without a real
    HA instance, but we CAN verify the attribute is correctly plumbed."""

    def test_requires_auth_default_true(self):
        from homie_proxy.proxy import HomieProxyDebugView
        view = HomieProxyDebugView()
        assert view.requires_auth is True, (
            "Default must be auth-required — secure by default."
        )

    def test_requires_auth_false_when_disabled(self):
        from homie_proxy.proxy import HomieProxyDebugView
        view = HomieProxyDebugView(requires_auth=False)
        assert view.requires_auth is False, (
            "When debug_requires_auth: false is set, the flag must be "
            "passed through so HA's auth middleware lets unauthenticated "
            "requests through."
        )

    def test_requires_auth_attribute_is_instance_level(self):
        """HA's auth middleware reads `view.requires_auth`. Setting it on
        the instance (not the class) is the correct pattern — but if it's
        accidentally only a CLASS attribute, multiple instances would
        share the same flag and one user's `false` would affect every
        other user. Pin instance-level isolation here."""
        from homie_proxy.proxy import HomieProxyDebugView
        v1 = HomieProxyDebugView(requires_auth=False)
        v2 = HomieProxyDebugView(requires_auth=True)
        assert v1.requires_auth is False
        assert v2.requires_auth is True

    def test_url_and_name_are_class_attributes(self):
        """url/name must be class attributes (not per-instance) — HA's
        view registry uses `type(view).url` to look them up."""
        from homie_proxy.proxy import HomieProxyDebugView
        assert HomieProxyDebugView.url == "/api/homie_proxy/debug"
        assert HomieProxyDebugView.name == "api:homie_proxy:debug"
