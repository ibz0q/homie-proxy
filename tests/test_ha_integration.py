"""
End-to-end HTTP tests for the HA component's request handlers.

These exist because the *standalone* version is exhaustively integration-tested
(test_server_integration.py / test_security_integration.py), but the Home
Assistant component's `HomieProxyView._handle()` and `HomieProxyDebugView.get()`
were previously only attribute-tested. That gap shipped a real bug
(`HomieProxyDebugView` referenced `self.hass` instead of `request.app["hass"]`)
which crashed 100 % of /debug requests in HA but passed every test.

We can't run HA's auth/middleware without HA itself, but we *can* mount the
view classes onto a plain aiohttp app and drive them with the test client —
this exercises the same code paths HA would and catches structural regressions
(missing attributes, wrong request-context access, exceptions in handlers).

Run with:
    pytest tests/test_ha_integration.py -v
"""
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

import json
import pytest
from aiohttp import web

# IMPORTANT: import order matters. conftest puts custom_components/ on sys.path
# first so `homie_proxy` resolves to the HA *package* (not the standalone).
from homie_proxy.proxy import (
    HomieProxyView,
    HomieProxyDebugView,
    ProxyInstance,
)
from homie_proxy.const import DOMAIN


# ─── Helpers ─────────────────────────────────────────────────────────────────

def make_proxy_instance(**overrides) -> ProxyInstance:
    cfg = dict(
        name="ha-test",
        tokens=["good-token"],
        restrict_out="any",
        restrict_out_cidrs=None,
        restrict_in_cidrs=None,
        timeout=5,
    )
    cfg.update(overrides)
    return ProxyInstance(**cfg)


def fake_service(proxy_instance: ProxyInstance, **kw) -> SimpleNamespace:
    """Duck-type a HomieProxyService for the debug view to read.

    The debug view only reads attributes (.name, .tokens, .restrict_out,
    .restrict_out_cidrs, .restrict_in_cidrs, .timeout, .requires_auth,
    .debug_requires_auth, .view). A SimpleNamespace gives us those without
    pulling in HomieProxyService.setup() which wants a real hass.http.
    """
    defaults = dict(
        name=proxy_instance.name,
        tokens=list(proxy_instance.tokens),
        restrict_out=proxy_instance.restrict_out,
        restrict_out_cidrs=[str(c) for c in proxy_instance.restrict_out_cidrs],
        restrict_in_cidrs=[str(c) for c in proxy_instance.restrict_in_cidrs],
        timeout=proxy_instance.timeout,
        requires_auth=True,
        debug_requires_auth=True,
        view=object(),  # truthy → debug view reports status="active"
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def make_app(
    proxy_instance: ProxyInstance,
    *,
    debug_view: Optional[HomieProxyDebugView] = None,
    services: Optional[List[SimpleNamespace]] = None,
    extra_domain_data: Optional[Dict[str, Any]] = None,
) -> web.Application:
    """Mount the HA views onto a real aiohttp app, mirroring HA's wiring."""
    app = web.Application()

    # HA stores the hass instance on the app under the "hass" key. The debug
    # view reads it via `request.app["hass"]` — this is the canonical pattern.
    fake_hass = SimpleNamespace(data={})

    # Populate hass.data the way `HomieProxyService.setup()` would: one
    # synthetic entry per service, plus debug-view bookkeeping keys.
    domain_data: Dict[str, Any] = {}
    for i, svc in enumerate(services or []):
        domain_data[f"entry_{i}"] = {"service": svc, "config": {}}
    if extra_domain_data:
        domain_data.update(extra_domain_data)
    fake_hass.data[DOMAIN] = domain_data
    app["hass"] = fake_hass

    # Mount the proxy view's HTTP-method handlers manually. HA's register_view
    # does the same dispatch, but we don't have a real HA here.
    view = HomieProxyView(proxy_instance, requires_auth=False)
    base = f"/api/homie_proxy/{proxy_instance.name}"
    for method in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"):
        app.router.add_route(method, base, getattr(view, method.lower()))

    if debug_view is not None:
        app.router.add_get("/api/homie_proxy/debug", debug_view.get)

    return app


# ─── HomieProxyDebugView via real HTTP ───────────────────────────────────────

class TestHADebugViewOverHTTP:
    """The bug we just fixed (`self.hass` → `request.app["hass"]`) was a 100 %
    crash on every /debug call but slipped past every existing test. These
    tests would have caught it."""

    async def test_debug_returns_200_and_json(self, aiohttp_client):
        inst = make_proxy_instance()
        debug = HomieProxyDebugView(requires_auth=False)
        app = make_app(inst, debug_view=debug, services=[fake_service(inst)])
        client = await aiohttp_client(app)

        resp = await client.get("/api/homie_proxy/debug")
        assert resp.status == 200, (
            f"debug view crashed (most likely cause: handler tried to read "
            f"self.hass instead of request.app['hass']). status={resp.status}, "
            f"body={await resp.text()!r}"
        )
        assert resp.content_type == "application/json"
        data = await resp.json()
        # Structural assertions — the shape MUST remain stable for any UI / CLI
        # that consumes /debug.
        assert "instances" in data
        assert "system" in data
        assert "debug" in data
        assert "timestamp" in data

    async def test_debug_lists_each_instance(self, aiohttp_client):
        a = make_proxy_instance(name="alpha")
        b = make_proxy_instance(name="beta")
        debug = HomieProxyDebugView(requires_auth=False)
        # Single ProxyInstance for the proxy route — but we register two
        # services in domain_data so the debug view sees two instances.
        app = make_app(
            a, debug_view=debug,
            services=[fake_service(a), fake_service(b)],
        )
        client = await aiohttp_client(app)
        data = await (await client.get("/api/homie_proxy/debug")).json()
        assert "alpha" in data["instances"]
        assert "beta" in data["instances"]

    async def test_debug_masks_full_tokens(self, aiohttp_client):
        inst = make_proxy_instance(tokens=["super-secret-please-do-not-leak"])
        svc = fake_service(inst)
        debug = HomieProxyDebugView(requires_auth=False)
        app = make_app(inst, debug_view=debug, services=[svc])
        client = await aiohttp_client(app)
        body = await (await client.get("/api/homie_proxy/debug")).text()
        assert "super-secret-please-do-not-leak" not in body, (
            "Full token leaked in HA /debug output."
        )
        data = json.loads(body)
        masked = data["instances"]["ha-test"]["tokens"][0]
        assert masked.startswith("supe") and masked.endswith("***")

    async def test_debug_skips_non_entry_keys(self, aiohttp_client):
        """hass.data[DOMAIN] also contains 'global_config', 'debug_view_*'.
        These must not be treated as instances or the view crashes."""
        inst = make_proxy_instance()
        debug = HomieProxyDebugView(requires_auth=False)
        app = make_app(
            inst, debug_view=debug,
            services=[fake_service(inst)],
            extra_domain_data={
                "global_config": {"debug_requires_auth": True},
                "debug_view_registered": True,
                "debug_view_instance": debug,
            },
        )
        client = await aiohttp_client(app)
        resp = await client.get("/api/homie_proxy/debug")
        assert resp.status == 200
        data = await resp.json()
        # Only the real entry should appear; sibling keys are filtered out.
        assert set(data["instances"].keys()) == {"ha-test"}

    async def test_debug_reports_instance_fields(self, aiohttp_client):
        """Sanity-check the JSON shape so the UI / docs don't drift."""
        inst = make_proxy_instance(restrict_out="external", timeout=42)
        svc = fake_service(inst, requires_auth=False, debug_requires_auth=False)
        app = make_app(inst, debug_view=HomieProxyDebugView(requires_auth=False),
                       services=[svc])
        client = await aiohttp_client(app)
        data = (await (await client.get("/api/homie_proxy/debug")).json()
                )["instances"]["ha-test"]
        assert data["restrict_out"] == "external"
        assert data["timeout"] == 42
        assert data["requires_auth"] is False
        assert data["debug_requires_auth"] is False
        assert data["endpoint_url"] == "/api/homie_proxy/ha-test"

    async def test_debug_returns_json_error_on_handler_crash(self, aiohttp_client):
        """The defensive try/except must turn a malformed entry into a JSON
        error body (status 500) rather than letting the bare aiohttp 500
        stub through. Verify by injecting a service object that raises on
        attribute access."""
        inst = make_proxy_instance()

        class Exploding:
            @property
            def name(self): return "boom"
            tokens = ["t"]
            @property
            def restrict_out(self): raise RuntimeError("kaboom")

        debug = HomieProxyDebugView(requires_auth=False)
        # Wrap the exploding object to look like a service entry.
        app = make_app(inst, debug_view=debug, services=[])
        # Inject an entry whose service raises on attribute access — bypassing
        # fake_service so we can target the inner per-instance try/except.
        app["hass"].data[DOMAIN]["entry_boom"] = {"service": Exploding()}
        client = await aiohttp_client(app)
        resp = await client.get("/api/homie_proxy/debug")
        assert resp.status == 200, "outer try/except should keep the request alive"
        data = await resp.json()
        # The exploding instance is rendered as an error, the others succeed.
        assert "boom" in data["instances"]
        assert "error" in data["instances"]["boom"]


# ─── HomieProxyView (the proxy itself) via real HTTP ─────────────────────────

class TestHAProxyViewOverHTTP:
    """End-to-end behaviour of the HA component's proxy handler. Mirrors the
    standalone server's TestAuthentication / TestURLValidation but exercises
    the HA `HomieProxyView._handle()` code path."""

    async def test_proxy_returns_401_on_wrong_token(self, aiohttp_client):
        inst = make_proxy_instance(tokens=["good"])
        client = await aiohttp_client(make_app(inst))
        resp = await client.get(
            "/api/homie_proxy/ha-test",
            params={"token": "wrong", "url": "http://example.invalid/"},
        )
        assert resp.status == 401, (
            f"HA proxy view did not return 401 on wrong token; got {resp.status}"
        )
        data = await resp.json()
        assert data["code"] == 401

    async def test_proxy_returns_400_when_url_missing(self, aiohttp_client):
        inst = make_proxy_instance()
        client = await aiohttp_client(make_app(inst))
        resp = await client.get(
            "/api/homie_proxy/ha-test", params={"token": "good-token"},
        )
        assert resp.status == 400
        assert (await resp.json())["code"] == 400

    async def test_proxy_blocks_private_target_in_external_mode(self, aiohttp_client):
        inst = make_proxy_instance(restrict_out="external")
        client = await aiohttp_client(make_app(inst))
        resp = await client.get(
            "/api/homie_proxy/ha-test",
            params={"token": "good-token", "url": "http://192.168.1.1/api"},
        )
        assert resp.status == 403, "external mode let through RFC 1918 — SSRF."

    async def test_proxy_inbound_ip_filter_via_xff(self, aiohttp_client):
        """`X-Forwarded-For` is honoured by `_client_ip()`. Spoof it to a
        non-allowlisted address and confirm 403."""
        inst = make_proxy_instance(restrict_in_cidrs=["10.0.0.0/8"])
        client = await aiohttp_client(make_app(inst))
        resp = await client.get(
            "/api/homie_proxy/ha-test",
            params={"token": "good-token", "url": "http://example.com/"},
            headers={"X-Forwarded-For": "8.8.8.8"},   # outside 10/8
        )
        assert resp.status == 403

    async def test_proxy_passes_valid_request_to_upstream(self, aiohttp_client, upstream):
        """The full happy path through the HA handler: token OK → URL OK →
        upstream call → response. Catches plumbing regressions in `_handle`."""
        inst = make_proxy_instance(restrict_out="any")
        client = await aiohttp_client(make_app(inst))
        resp = await client.get(
            "/api/homie_proxy/ha-test",
            params={
                "token": "good-token",
                "url": str(upstream.make_url("/echo")),
            },
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["method"] == "GET"
        assert data["path"] == "/echo"

    async def test_proxy_cors_preflight_short_circuits(self, aiohttp_client):
        inst = make_proxy_instance()
        client = await aiohttp_client(make_app(inst))
        resp = await client.options(
            "/api/homie_proxy/ha-test",
            params={
                "token": "good-token",
                "url": "http://example.com/",
                "cors_preflight": "1",
                "response_header[Access-Control-Allow-Origin]": "*",
            },
        )
        assert resp.status == 204
        assert resp.headers["Access-Control-Allow-Origin"] == "*"

    async def test_proxy_response_headers_injected_on_error(self, aiohttp_client):
        """CORS-on-error: even a 401 must carry the configured response headers
        so the browser can read the real status."""
        inst = make_proxy_instance(tokens=["good"])
        client = await aiohttp_client(make_app(inst))
        resp = await client.get(
            "/api/homie_proxy/ha-test",
            params={
                "token": "wrong",
                "url": "http://example.com/",
                "response_header[Access-Control-Allow-Origin]": "*",
            },
        )
        assert resp.status == 401
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"
