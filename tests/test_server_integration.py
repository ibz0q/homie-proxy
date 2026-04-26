"""
Integration tests for the HomieProxy standalone server.

Uses aiohttp's TestServer/TestClient so no real ports are bound and no external
network is required. Each test class exercises one concern.

Run with:
    pytest tests/test_server_integration.py -v
"""
import asyncio
import json
import pytest
import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer, TestClient

# Load the standalone module by path to avoid shadowing the HA package that
# shares the same "homie_proxy" name.  See conftest.load_standalone().
from conftest import load_standalone as _load_standalone
_standalone = _load_standalone()
HomieProxyServer = _standalone.HomieProxyServer

# asyncio_mode = auto in pytest.ini handles async test discovery globally.


# â”€â”€â”€ Proxy factory â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def make_proxy(upstream_base: str = "", **instance_overrides) -> HomieProxyServer:
    """Return a HomieProxyServer with a single 'test' instance."""
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


async def proxy_client(aiohttp_client, upstream, **instance_overrides):
    """Convenience: return a TestClient wired to a proxy targeting *upstream*."""
    srv = make_proxy(**instance_overrides)
    return await aiohttp_client(srv.create_app())


# â”€â”€â”€ Authentication â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestAuthentication:
    async def test_valid_token_passes(self, upstream, aiohttp_client):
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.get("/test", params={
            "token": "good-token",
            "url": str(upstream.make_url("/echo")),
        })
        assert resp.status == 200

    async def test_wrong_token_is_401(self, upstream, aiohttp_client):
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.get("/test", params={
            "token": "wrong",
            "url": str(upstream.make_url("/echo")),
        })
        assert resp.status == 401

    async def test_missing_token_is_401(self, upstream, aiohttp_client):
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.get("/test", params={"url": str(upstream.make_url("/echo"))})
        assert resp.status == 401

    async def test_401_body_is_json(self, upstream, aiohttp_client):
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.get("/test", params={"url": str(upstream.make_url("/echo"))})
        data = await resp.json()
        assert "error" in data
        assert data["code"] == 401

    async def test_auth_evaluated_before_url_restriction(self, upstream, aiohttp_client):
        """An invalid token must get 401, not a 403 about the target URL.

        If the URL check ran first and the token check second, an unauthenticated
        caller could probe which URLs are blocked just by observing 403 vs 401.
        """
        # Create a proxy that only allows internal IPs â€” the upstream is 127.x.x.x
        # which *would* be blocked by external mode, but token check must come first.
        client = await aiohttp_client(
            make_proxy(restrict_out="external").create_app()
        )
        resp = await client.get("/test", params={
            "token": "wrong-token",           # bad auth
            "url": str(upstream.make_url("/echo")),  # 127.x.x.x â€” would fail outbound check
        })
        # Must be 401, not 403 â€” auth wins
        assert resp.status == 401

    async def test_multiple_tokens_any_accepted(self, upstream, aiohttp_client):
        srv = HomieProxyServer()
        srv.instances = {}
        srv.add_instance("test", {
            "restrict_out": "any",
            "tokens": ["token-a", "token-b", "token-c"],
            "restrict_in_cidrs": [],
            "timeout": 5,
        })
        client = await aiohttp_client(srv.create_app())
        for token in ("token-a", "token-b", "token-c"):
            resp = await client.get("/test", params={
                "token": token,
                "url": str(upstream.make_url("/echo")),
            })
            assert resp.status == 200, f"token '{token}' should be accepted"


# â”€â”€â”€ URL validation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestURLValidation:
    async def test_missing_url_is_400(self, upstream, aiohttp_client):
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.get("/test", params={"token": "good-token"})
        assert resp.status == 400

    async def test_400_body_is_json(self, upstream, aiohttp_client):
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.get("/test", params={"token": "good-token"})
        data = await resp.json()
        assert data["code"] == 400


# â”€â”€â”€ CORS preflight â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestCORSPreflight:
    async def test_preflight_returns_204_with_headers(self, upstream, aiohttp_client):
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.options("/test", params={
            "token": "good-token",
            "url": str(upstream.make_url("/echo")),
            "cors_preflight": "1",
            "response_header[Access-Control-Allow-Origin]": "*",
            "response_header[Access-Control-Allow-Methods]": "GET, POST, PUT",
        })
        assert resp.status == 204
        assert resp.headers["Access-Control-Allow-Origin"] == "*"
        assert resp.headers["Access-Control-Allow-Methods"] == "GET, POST, PUT"

    async def test_options_without_flag_forwarded_to_upstream(self, upstream, aiohttp_client):
        """OPTIONS without the flag must be proxied, not short-circuited."""
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.options("/test", params={
            "token": "good-token",
            "url": str(upstream.make_url("/echo")),
        })
        assert resp.status == 200
        data = await resp.json()
        assert data["method"] == "OPTIONS"


# â”€â”€â”€ Response header injection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestResponseHeaders:
    async def test_response_headers_injected(self, upstream, aiohttp_client):
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.get("/test", params={
            "token": "good-token",
            "url": str(upstream.make_url("/echo")),
            "response_header[Access-Control-Allow-Origin]": "*",
            "response_header[X-My-Header]": "custom-value",
        })
        assert resp.headers["Access-Control-Allow-Origin"] == "*"
        assert resp.headers["X-My-Header"] == "custom-value"

    async def test_error_responses_carry_cors_headers(self, upstream, aiohttp_client):
        """CORS headers must appear even on 4xx responses.

        Without this, a browser gets a CORS error instead of the real error,
        making debugging nearly impossible.
        """
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.get("/test", params={
            "token": "wrong-token",
            "url": str(upstream.make_url("/echo")),
            "response_header[Access-Control-Allow-Origin]": "*",
        })
        assert resp.status == 401
        assert resp.headers.get("Access-Control-Allow-Origin") == "*"


# â”€â”€â”€ Request header forwarding â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestRequestHeaders:
    async def test_custom_request_header_forwarded(self, upstream, aiohttp_client):
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.get("/test", params={
            "token": "good-token",
            "url": str(upstream.make_url("/echo")),
            "request_header[X-Forwarded-Auth]": "Bearer abc123",
        })
        data = await resp.json()
        assert data["headers"].get("X-Forwarded-Auth") == "Bearer abc123"

    async def test_host_header_override(self, upstream, aiohttp_client):
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.get("/test", params={
            "token": "good-token",
            "url": str(upstream.make_url("/echo")),
            "request_header[Host]": "camera.local",
        })
        data = await resp.json()
        host = data["headers"].get("Host") or data["headers"].get("host", "")
        assert host == "camera.local"

    async def test_multiple_custom_headers(self, upstream, aiohttp_client):
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.get("/test", params={
            "token": "good-token",
            "url": str(upstream.make_url("/echo")),
            "request_header[X-A]": "alpha",
            "request_header[X-B]": "beta",
        })
        data = await resp.json()
        assert data["headers"].get("X-A") == "alpha"
        assert data["headers"].get("X-B") == "beta"


# â”€â”€â”€ HTTP method forwarding â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestHTTPMethods:
    @pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE"])
    async def test_method_forwarded(self, upstream, aiohttp_client, method):
        client = await proxy_client(aiohttp_client, upstream)
        kwargs: dict = {"params": {"token": "good-token", "url": str(upstream.make_url("/echo"))}}
        if method in ("POST", "PUT", "PATCH"):
            kwargs["data"] = b"body"
        resp = await getattr(client, method.lower())("/test", **kwargs)
        assert resp.status == 200
        data = await resp.json()
        assert data["method"] == method

    async def test_head_returns_no_body(self, upstream, aiohttp_client):
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.head("/test", params={
            "token": "good-token",
            "url": str(upstream.make_url("/echo")),
        })
        assert resp.status in (200, 204)
        body = await resp.read()
        assert body == b""


# â”€â”€â”€ Body forwarding â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestBodyForwarding:
    async def test_post_json_body_forwarded(self, upstream, aiohttp_client):
        client = await proxy_client(aiohttp_client, upstream)
        payload = b'{"key": "value"}'
        resp = await client.post("/test", params={
            "token": "good-token",
            "url": str(upstream.make_url("/echo")),
            "request_header[Content-Type]": "application/json",
        }, data=payload)
        data = await resp.json()
        assert data["body"] == '{"key": "value"}'

    async def test_put_body_forwarded(self, upstream, aiohttp_client):
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.put("/test", params={
            "token": "good-token",
            "url": str(upstream.make_url("/echo")),
        }, data=b"<xml>update</xml>")
        data = await resp.json()
        assert data["body"] == "<xml>update</xml>"

    async def test_patch_body_forwarded(self, upstream, aiohttp_client):
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.patch("/test", params={
            "token": "good-token",
            "url": str(upstream.make_url("/echo")),
        }, data=b"patch-data")
        data = await resp.json()
        assert data["body"] == "patch-data"


# â”€â”€â”€ Upstream status passthrough â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestUpstreamStatus:
    @pytest.mark.parametrize("code", [400, 403, 404, 500, 503])
    async def test_upstream_status_forwarded(self, upstream, aiohttp_client, code):
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.get("/test", params={
            "token": "good-token",
            "url": str(upstream.make_url(f"/status/{code}")),
        })
        assert resp.status == code

    async def test_unreachable_upstream_returns_502(self, aiohttp_client):
        """Nothing listening on port 1 â†’ connection refused â†’ 502 Bad Gateway."""
        client = await proxy_client(aiohttp_client, None)
        resp = await client.get("/test", params={
            "token": "good-token",
            "url": "http://127.0.0.1:1/",
        })
        assert resp.status == 502

    async def test_502_body_is_json(self, aiohttp_client):
        client = await proxy_client(aiohttp_client, None)
        resp = await client.get("/test", params={
            "token": "good-token",
            "url": "http://127.0.0.1:1/",
        })
        data = await resp.json()
        assert data["code"] == 502


# â”€â”€â”€ Redirect handling â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestRedirects:
    async def test_redirects_not_followed_by_default(self, upstream, aiohttp_client):
        """The proxy must return the 302 as-is; the caller decides whether to follow.

        We disable redirect-following on the test-client request so the 302
        returned by the proxy isn't transparently chased.
        """
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.get("/test", params={
            "token": "good-token",
            "url": str(upstream.make_url("/redirect")),
        }, allow_redirects=False)
        assert resp.status == 302

    async def test_redirects_followed_when_requested(self, upstream, aiohttp_client):
        client = await proxy_client(aiohttp_client, upstream)
        resp = await client.get("/test", params={
            "token": "good-token",
            "url": str(upstream.make_url("/redirect")),
            "follow_redirects": "true",
        })
        assert resp.status == 200
        data = await resp.json()
        assert data["path"] == "/echo"


# â”€â”€â”€ Timeout override â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestTimeout:
    async def test_per_request_timeout_triggers_504(self, upstream, aiohttp_client):
        """?timeout=1 with a 3-second upstream â†’ 504 Gateway Timeout."""
        client = await proxy_client(aiohttp_client, upstream, timeout=30)
        resp = await client.get(
            "/test",
            params={
                "token": "good-token",
                "url": str(upstream.make_url("/slow/3")),
                "timeout": "1",
            },
            timeout=aiohttp.ClientTimeout(total=10),
        )
        assert resp.status == 504

    async def test_generous_timeout_succeeds(self, upstream, aiohttp_client):
        """?timeout=10 with a 1-second upstream â†’ success."""
        client = await proxy_client(aiohttp_client, upstream, timeout=30)
        resp = await client.get(
            "/test",
            params={
                "token": "good-token",
                "url": str(upstream.make_url("/slow/1")),
                "timeout": "10",
            },
            timeout=aiohttp.ClientTimeout(total=15),
        )
        assert resp.status == 200


# â”€â”€â”€ Inbound IP restriction â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestInboundIPRestriction:
    async def test_disallowed_client_ip_gets_403(self, upstream, aiohttp_client):
        """Restrict to 10.0.0.0/8; TestClient connects from 127.0.0.1 â†’ 403."""
        srv = HomieProxyServer()
        srv.instances = {}
        srv.add_instance("test", {
            "restrict_out": "any",
            "tokens": ["good-token"],
            "restrict_in_cidrs": ["10.0.0.0/8"],
            "timeout": 5,
        })
        client = await aiohttp_client(srv.create_app())
        resp = await client.get("/test", params={
            "token": "good-token",
            "url": str(upstream.make_url("/echo")),
        })
        assert resp.status == 403

    async def test_allowed_client_ip_passes(self, upstream, aiohttp_client):
        """Restrict to 127.0.0.0/8; TestClient connects from 127.0.0.1 â†’ allowed."""
        srv = HomieProxyServer()
        srv.instances = {}
        srv.add_instance("test", {
            "restrict_out": "any",
            "tokens": ["good-token"],
            "restrict_in_cidrs": ["127.0.0.0/8"],
            "timeout": 5,
        })
        client = await aiohttp_client(srv.create_app())
        resp = await client.get("/test", params={
            "token": "good-token",
            "url": str(upstream.make_url("/echo")),
        })
        assert resp.status == 200


# â”€â”€â”€ Outbound URL restriction â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestOutboundRestriction:
    async def test_external_mode_blocks_private_upstream(self, aiohttp_client):
        """external mode must reject requests to RFC 1918 addresses."""
        srv = HomieProxyServer()
        srv.instances = {}
        srv.add_instance("test", {
            "restrict_out": "external",
            "tokens": ["good-token"],
            "restrict_in_cidrs": [],
            "timeout": 5,
        })
        client = await aiohttp_client(srv.create_app())
        resp = await client.get("/test", params={
            "token": "good-token",
            "url": "http://192.168.1.1/api",
        })
        assert resp.status == 403

    async def test_internal_mode_allows_private_upstream(self, upstream, aiohttp_client):
        """internal mode must allow RFC 1918 / loopback addresses."""
        srv = HomieProxyServer()
        srv.instances = {}
        srv.add_instance("test", {
            "restrict_out": "internal",
            "tokens": ["good-token"],
            "restrict_in_cidrs": [],
            "timeout": 5,
        })
        client = await aiohttp_client(srv.create_app())
        # upstream binds to 127.0.0.1 (loopback) â€” allowed in internal mode
        resp = await client.get("/test", params={
            "token": "good-token",
            "url": str(upstream.make_url("/echo")),
        })
        assert resp.status == 200

    async def test_custom_cidr_allows_specific_range(self, upstream, aiohttp_client):
        """custom mode should only allow the specified CIDRs."""
        srv = HomieProxyServer()
        srv.instances = {}
        srv.add_instance("test", {
            "restrict_out": "custom",
            "restrict_out_cidrs": ["127.0.0.0/8"],  # allow loopback only
            "tokens": ["good-token"],
            "restrict_in_cidrs": [],
            "timeout": 5,
        })
        client = await aiohttp_client(srv.create_app())
        resp = await client.get("/test", params={
            "token": "good-token",
            "url": str(upstream.make_url("/echo")),  # 127.x.x.x â€” allowed
        })
        assert resp.status == 200

    async def test_custom_cidr_blocks_outside_range(self, aiohttp_client):
        srv = HomieProxyServer()
        srv.instances = {}
        srv.add_instance("test", {
            "restrict_out": "custom",
            "restrict_out_cidrs": ["8.8.8.0/24"],   # only Google DNS
            "tokens": ["good-token"],
            "restrict_in_cidrs": [],
            "timeout": 5,
        })
        client = await aiohttp_client(srv.create_app())
        resp = await client.get("/test", params={
            "token": "good-token",
            "url": "http://192.168.1.1/api",   # outside range
        })
        assert resp.status == 403


# â”€â”€â”€ Debug endpoint â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TestDebugEndpoint:
    async def test_debug_shows_instance_names(self, aiohttp_client):
        srv = HomieProxyServer()
        srv.instances = {}
        srv.add_instance("alpha", {"restrict_out": "any", "tokens": ["t"], "restrict_in_cidrs": []})
        srv.add_instance("beta",  {"restrict_out": "any", "tokens": ["t"], "restrict_in_cidrs": []})
        client = await aiohttp_client(srv.create_app())
        resp = await client.get("/debug")
        assert resp.status == 200
        data = await resp.json()
        assert "alpha" in data["instances"]
        assert "beta" in data["instances"]

    async def test_debug_response_is_json(self, aiohttp_client):
        srv = HomieProxyServer()
        srv.instances = {}
        srv.add_instance("test", {"restrict_out": "any", "tokens": ["t"], "restrict_in_cidrs": []})
        client = await aiohttp_client(srv.create_app())
        resp = await client.get("/debug")
        assert resp.content_type == "application/json"


