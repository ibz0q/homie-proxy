"""Shared pytest configuration and fixtures."""
import sys
import os
import asyncio
import json
import importlib.util

import pytest
import pytest_asyncio
from aiohttp import web

# ─── Path setup ───────────────────────────────────────────────────────────────
# The HA component lives at  custom_components/homie_proxy/  (a package).
# The standalone lives at    standalone_homie-proxy/homie_proxy.py  (a module).
# Both are named "homie_proxy", so only one can win the plain `import homie_proxy`
# race.  We put custom_components first so the HA *package* wins, and expose the
# standalone via a dedicated helper so integration tests can import it without
# ambiguity.

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_TESTS_DIR)               # homie-proxy/
_REPO_ROOT = os.path.dirname(_ROOT)               # repo root (contains custom_components/)
_HA_COMPONENTS = os.path.join(_REPO_ROOT, "custom_components")
_STANDALONE = os.path.join(_ROOT, "standalone_homie-proxy")
_STUBS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stubs")

# Path priority (index 0 wins):
#   1. HA custom_components — so "homie_proxy" resolves to the HA *package*
#   2. standalone_homie-proxy — available for explicit importlib loads
#   3. stubs — provides homeassistant / voluptuous shims for tests without HA
# Insert in reverse order so the first entry ends up at index 0.
for _p in (_STUBS, _STANDALONE, _HA_COMPONENTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def load_standalone():
    """Import the standalone homie_proxy module by file path.

    Returns the module object.  Use this instead of a plain
    ``import homie_proxy`` in integration tests so the standalone module is
    never confused with the HA package.
    """
    _mod_path = os.path.join(_STANDALONE, "homie_proxy.py")
    spec = importlib.util.spec_from_file_location("homie_proxy_standalone", _mod_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ─── Mock upstream app ────────────────────────────────────────────────────────

def make_upstream_app() -> web.Application:
    """Minimal aiohttp app that echoes request details back as JSON.

    Routes:
      ANY  /echo          — JSON echo of method, headers, body, query
      GET  /status/{N}    — Returns HTTP status N
      GET  /slow/{secs}   — Sleeps for {secs} seconds (for timeout tests)
      GET  /redirect      — 302 → /echo
    """
    app = web.Application()

    async def echo(req: web.Request) -> web.Response:
        body = await req.read()
        return web.Response(
            content_type="application/json",
            text=json.dumps({
                "method": req.method,
                "path": req.path,
                "headers": dict(req.headers),
                "body": body.decode("utf-8", errors="replace"),
                "query": dict(req.query),
            }),
        )

    async def status_n(req: web.Request) -> web.Response:
        code = int(req.match_info["code"])
        return web.Response(status=code, text=f"Status {code}")

    async def slow(req: web.Request) -> web.Response:
        secs = float(req.match_info["secs"])
        await asyncio.sleep(secs)
        return web.Response(text="ok")

    async def redirect(req: web.Request) -> web.Response:
        return web.HTTPFound(location="/echo")

    app.router.add_route("*", "/echo", echo)
    app.router.add_route("*", r"/echo/{tail:.*}", echo)
    app.router.add_get(r"/status/{code:\d+}", status_n)
    app.router.add_get(r"/slow/{secs}", slow)
    app.router.add_get("/redirect", redirect)
    return app


@pytest_asyncio.fixture
async def upstream(aiohttp_server):
    """A running mock upstream server."""
    return await aiohttp_server(make_upstream_app())
