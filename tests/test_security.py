"""
Security-focused tests for HomieProxy.

These tests are organised by attack class — SSRF, restriction-mode escapes,
header injection, scheme abuse, redirect-follow bypass, etc. — so a regression
in any single check is easy to spot.

Each `*_FIXED` test marks a property the code already enforces (these should
pass green). Each `*_VULNERABLE` test marks a known gap that has not yet been
fixed; they're decorated with `pytest.xfail` so the test suite stays green
overall and the gap shows up explicitly when running the suite.

Run with:
    pytest tests/test_security.py -v
"""
import ipaddress
import pytest

from homie_proxy.proxy import ProxyInstance
from homie_proxy.const import PRIVATE_CIDRS

# asyncio_mode = auto in pytest.ini handles async test discovery globally.


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make(restrict_out="any", **kw):
    """Build a ProxyInstance with sensible defaults for security tests."""
    cfg = dict(name="t", tokens=["good"], restrict_out=restrict_out, timeout=5)
    cfg.update(kw)
    return ProxyInstance(**cfg)


# ─── SSRF: classic private-range bypasses in `external` mode ──────────────────

class TestExternalModeSSRF:
    """`external` mode should refuse every well-known private/internal range."""

    @pytest.mark.parametrize("url", [
        # RFC 1918
        "http://10.0.0.1/",
        "http://10.255.255.254/",
        "http://172.16.0.1/",
        "http://172.31.255.254/",
        "http://192.168.0.1/",
        "http://192.168.255.254/",
        # Loopback
        "http://127.0.0.1/",
        "http://127.255.255.254/",
        "http://localhost/",
        # Link-local (AWS / GCP / Azure metadata: 169.254.169.254)
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.0.1/",
        # CGNAT (RFC 6598)
        "http://100.64.0.1/",
        "http://100.127.255.254/",
    ])
    async def test_external_blocks_all_private_v4(self, url):
        inst = make(restrict_out="external")
        assert not await inst.is_target_allowed(url), (
            f"SSRF: external mode let through {url!r}"
        )

    @pytest.mark.parametrize("url", [
        "http://[::1]/",                # IPv6 loopback
        "http://[fe80::1]/",            # IPv6 link-local
        "http://[fc00::1]/",            # IPv6 unique-local
        "http://[fd00::1]/",
    ])
    async def test_external_blocks_all_private_v6(self, url):
        inst = make(restrict_out="external")
        assert not await inst.is_target_allowed(url), (
            f"SSRF: external mode let through IPv6 private {url!r}"
        )


class TestExternalModeAdvancedSSRF:
    """SSRF vectors that have historically bypassed naive private-range filters."""

    @pytest.mark.parametrize("url", [
        # `0.0.0.0` resolves to loopback on Linux when used as a connect target.
        # MUST be blocked in external mode.
        "http://0.0.0.0/",
        "http://0.0.0.0:8123/api/states",
    ])
    async def test_external_blocks_zero_address(self, url):
        inst = make(restrict_out="external")
        assert not await inst.is_target_allowed(url), (
            f"SSRF: 0.0.0.0 not blocked — connects to localhost on Linux. "
            f"PRIVATE_CIDRS missing 0.0.0.0/8."
        )

    async def test_external_blocks_loopback_alias(self):
        """127.x.x.x is fully a loopback range; 127.0.0.2 must also be blocked."""
        inst = make(restrict_out="external")
        assert not await inst.is_target_allowed("http://127.0.0.2/")
        assert not await inst.is_target_allowed("http://127.1.2.3:8123/api")

    async def test_external_blocks_decimal_encoded_loopback(self):
        """127.0.0.1 = 2130706433 in decimal. Many parsers accept this form."""
        inst = make(restrict_out="external")
        # urllib.parse.urlparse may or may not accept this — both outcomes are
        # safe (rejection or "not in private CIDR" → blocked because the literal
        # "2130706433" isn't a valid IP literal so it's treated as a hostname
        # that fails to resolve → denied).
        result = await inst.is_target_allowed("http://2130706433/")
        # Whatever happens, it must NOT be allowed through to localhost.
        assert not result, (
            "decimal-encoded IP let through (or resolved to a public host). "
            "Verify this is the safe behaviour before relaxing the test."
        )


# ─── SSRF: classic public-range bypasses in `internal` mode ───────────────────

class TestInternalModeRestriction:
    """`internal` mode should refuse public IPs."""

    @pytest.mark.parametrize("url", [
        "http://8.8.8.8/",          # Google DNS
        "http://1.1.1.1/",          # Cloudflare
        "http://93.184.216.34/",    # example.com IPv4
        "http://[2606:2800:220:1:248:1893:25c8:1946]/",  # example.com IPv6
    ])
    async def test_internal_blocks_public(self, url):
        inst = make(restrict_out="internal")
        assert not await inst.is_target_allowed(url), (
            f"internal-only mode let through public IP {url!r}"
        )

    @pytest.mark.parametrize("url", [
        "http://192.168.1.1/",
        "http://10.0.0.1/",
        "http://127.0.0.1:8123/",
        "http://[::1]/",
    ])
    async def test_internal_allows_private(self, url):
        inst = make(restrict_out="internal")
        assert await inst.is_target_allowed(url), (
            f"internal-only mode rejected private IP {url!r}"
        )


# ─── Custom CIDR allowlist enforcement ────────────────────────────────────────

class TestCustomCIDR:
    async def test_only_listed_range_allowed(self):
        inst = make(restrict_out="custom", restrict_out_cidrs=["8.8.8.0/24"])
        assert     await inst.is_target_allowed("http://8.8.8.8/")
        assert     await inst.is_target_allowed("http://8.8.8.255/")
        assert not await inst.is_target_allowed("http://8.8.9.1/")
        assert not await inst.is_target_allowed("http://9.9.9.9/")

    async def test_empty_custom_list_blocks_everything(self):
        """custom mode with NO cidrs is a fail-closed: deny everything."""
        inst = make(restrict_out="custom", restrict_out_cidrs=[])
        assert not await inst.is_target_allowed("http://8.8.8.8/")
        assert not await inst.is_target_allowed("http://192.168.1.1/")
        assert not await inst.is_target_allowed("http://127.0.0.1/")

    async def test_loopback_only_allowlist_blocks_lan(self):
        """A custom allowlist of 127.0.0.0/8 must NOT leak the LAN."""
        inst = make(restrict_out="custom", restrict_out_cidrs=["127.0.0.0/8"])
        assert     await inst.is_target_allowed("http://127.0.0.1/")
        assert not await inst.is_target_allowed("http://192.168.1.1/")
        assert not await inst.is_target_allowed("http://10.0.0.1/")
        assert not await inst.is_target_allowed("http://8.8.8.8/")

    async def test_lan_allowlist_blocks_loopback(self):
        """A custom allowlist of just 192.168.0.0/16 must not allow loopback —
        i.e. a user who lists their LAN should not accidentally expose HA's
        own /api on 127.0.0.1:8123."""
        inst = make(restrict_out="custom", restrict_out_cidrs=["192.168.0.0/16"])
        assert     await inst.is_target_allowed("http://192.168.1.1/")
        assert not await inst.is_target_allowed("http://127.0.0.1:8123/")
        assert not await inst.is_target_allowed("http://10.0.0.1/")


# ─── DNS-based bypasses ───────────────────────────────────────────────────────

class TestDNSBypass:
    async def test_unresolvable_hostname_denied_in_external(self):
        """DNS failure must be a fail-closed (denied)."""
        inst = make(restrict_out="external")
        assert not await inst.is_target_allowed(
            "http://this-host-does-not-exist.invalid/"
        )

    async def test_unresolvable_hostname_denied_in_internal(self):
        inst = make(restrict_out="internal")
        assert not await inst.is_target_allowed(
            "http://this-host-does-not-exist.invalid/"
        )

    async def test_unresolvable_hostname_denied_in_custom(self):
        inst = make(restrict_out="custom", restrict_out_cidrs=["192.168.0.0/16"])
        assert not await inst.is_target_allowed(
            "http://this-host-does-not-exist.invalid/"
        )

    async def test_localhost_hostname_blocked_in_external(self):
        """`localhost` resolves to 127.0.0.1 — must be blocked in external mode.

        This catches the simplest DNS-based SSRF vector: an attacker who
        controls neither DNS nor /etc/hosts but knows that "localhost" exists
        on every machine.
        """
        inst = make(restrict_out="external")
        assert not await inst.is_target_allowed("http://localhost/")
        assert not await inst.is_target_allowed("http://localhost:8123/api/states")

    async def test_multiple_a_records_all_validated(self, monkeypatch):
        """If a hostname resolves to multiple IPs (some public, some private),
        EVERY address must satisfy the policy, not just the first one.

        We monkey-patch getaddrinfo to simulate the multi-A-record case so the
        test doesn't depend on real DNS.
        """
        import asyncio

        async def fake_getaddrinfo(hostname, port, type=None, **_):
            # Mixed result: public IP first, private IP second.
            return [
                (None, None, None, None, ("8.8.8.8", 0)),
                (None, None, None, None, ("127.0.0.1", 0)),
            ]

        loop = asyncio.get_running_loop()
        monkeypatch.setattr(loop, "getaddrinfo", fake_getaddrinfo)

        # External-only must reject the hostname because ONE of the resolved
        # addresses is private — even though the first one is public.
        inst = make(restrict_out="external")
        assert not await inst.is_target_allowed("http://multi-a-host.example/"), (
            "Multi-A-record SSRF: only the first address was validated, but "
            "aiohttp may connect to the second (private) address."
        )

    @pytest.mark.skip(
        reason=(
            "Documented residual risk — DNS TOCTOU between policy check and "
            "aiohttp's connect-time resolve. The check now validates EVERY "
            "address returned (multi-A-record case), but a racy/flapping "
            "resolver can still return different addresses on the second "
            "resolution. A full fix requires pinning the resolved IP onto "
            "the aiohttp request via an AsyncResolver / TCPConnector that "
            "uses our pre-resolved address. Tracked here as a skip-with-note "
            "rather than xfail so it shows up in `pytest -ra` output."
        ),
    )
    async def test_dns_rebinding_check_and_connect_atomic(self):
        pass  # see skip reason


# ─── URL parser oddities ──────────────────────────────────────────────────────

class TestURLParserAbuse:
    @pytest.mark.parametrize("url", [
        "",
        "http://",
        "http:///path",
        "://nohost",
        "not-a-url-at-all",
    ])
    async def test_malformed_url_denied(self, url):
        inst = make(restrict_out="external")
        assert not await inst.is_target_allowed(url)

    async def test_userinfo_in_url_does_not_confuse_hostname(self):
        """`http://attacker.com@127.0.0.1/` must be parsed as host=127.0.0.1
        (the userinfo is `attacker.com`). A naive split on '/' or '@' could
        treat attacker.com as the host and let it through."""
        inst = make(restrict_out="external")
        assert not await inst.is_target_allowed("http://attacker.com@127.0.0.1/")
        # …and the inverse: real public host with private-looking userinfo
        # must STILL be allowed (host wins over userinfo).
        # Skip the live-DNS half here; the urlparse contract is what we care about.
        from urllib.parse import urlparse
        assert urlparse("http://192.168.1.1@example.com/").hostname == "example.com"

    @pytest.mark.parametrize("scheme", [
        "file", "gopher", "ftp", "ldap", "dict", "data", "javascript",
    ])
    async def test_only_http_https_ws_wss_allowed(self, scheme):
        """Defence-in-depth: schemes other than http/https/ws/wss must be
        rejected up-front so file://, gopher://, etc. never reach upstream."""
        inst = make(restrict_out="any")
        result = await inst.is_target_allowed(f"{scheme}://example.com/payload")
        assert not result, f"scheme {scheme!r} should be rejected up-front"

    @pytest.mark.parametrize("scheme", ["http", "https", "ws", "wss"])
    async def test_supported_schemes_pass_scheme_check(self, scheme):
        """Same code path — the four supported schemes must NOT be rejected
        on scheme alone (host policy may still reject them)."""
        inst = make(restrict_out="any")
        # Use a public-IP literal so DNS isn't a factor.
        result = await inst.is_target_allowed(f"{scheme}://8.8.8.8/")
        assert result, f"supported scheme {scheme!r} was rejected"


# ─── Token comparison ─────────────────────────────────────────────────────────

class TestTokenSafety:
    def test_tokens_are_compared_case_sensitively(self):
        inst = make(tokens=["MySecretTok"])
        assert     inst.is_token_valid("MySecretTok")
        assert not inst.is_token_valid("mysecrettok")

    def test_partial_match_rejected(self):
        inst = make(tokens=["aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"])
        assert not inst.is_token_valid("aaaaaaaa")
        assert not inst.is_token_valid("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeeeEXTRA")

    def test_whitespace_around_token_rejected(self):
        inst = make(tokens=["abc"])
        assert not inst.is_token_valid(" abc")
        assert not inst.is_token_valid("abc ")
        assert not inst.is_token_valid("abc\n")
        assert not inst.is_token_valid("abc\r\n")

    def test_empty_or_none_token_rejected(self):
        inst = make(tokens=["abc"])
        assert not inst.is_token_valid("")
        assert not inst.is_token_valid(None)


# ─── PRIVATE_CIDRS coverage audit ─────────────────────────────────────────────

class TestPrivateCIDRCoverage:
    """Verifies that the explicit PRIVATE_CIDRS list in const.py covers every
    range that should be blocked in `external` mode. Add a row here whenever
    a new private/reserved range is identified — IANA changes happen rarely
    but they do happen (e.g. 100.64.0.0/10 was added in 2012)."""

    @pytest.mark.parametrize("addr,name", [
        ("10.0.0.1",        "RFC 1918 — 10/8"),
        ("172.16.0.1",      "RFC 1918 — 172.16/12"),
        ("172.31.255.254",  "RFC 1918 — 172.16/12 upper"),
        ("192.168.0.1",     "RFC 1918 — 192.168/16"),
        ("127.0.0.1",       "loopback — 127/8"),
        ("169.254.169.254", "link-local / cloud metadata"),
        ("100.64.0.1",      "CGNAT (RFC 6598)"),
        ("::1",             "IPv6 loopback"),
        ("fe80::1",         "IPv6 link-local"),
        ("fc00::1",         "IPv6 ULA"),
        ("fd00::1",         "IPv6 ULA"),
    ])
    def test_address_in_private_cidrs(self, addr, name):
        ip = ipaddress.ip_address(addr)
        nets = [ipaddress.ip_network(c) for c in PRIVATE_CIDRS]
        assert any(ip in n for n in nets), (
            f"{name} ({addr}) is missing from PRIVATE_CIDRS — "
            f"this is an SSRF vector in `external` mode."
        )

    def test_zero_network_blocked(self):
        """0.0.0.0/8 is RFC 1122 reserved 'this network'. On Linux a connect
        to 0.0.0.0 routes to localhost, so it MUST be blocked alongside 127/8."""
        ip = ipaddress.ip_address("0.0.0.0")
        nets = [ipaddress.ip_network(c) for c in PRIVATE_CIDRS]
        assert any(ip in n for n in nets)

    def test_unspecified_v6_blocked(self):
        """The IPv6 equivalent of 0.0.0.0 is `::` — same risk class."""
        ip = ipaddress.ip_address("::")
        nets = [ipaddress.ip_network(c) for c in PRIVATE_CIDRS]
        assert any(ip in n for n in nets)


# ─── Standalone PRIVATE_CIDRS coverage (mirror of the HA test above) ─────────
#
# The standalone module ships its own copy of PRIVATE_CIDRS (zero-deps design).
# A regression there is just as critical as in the HA component — and because
# the mirror is hand-maintained, drift between the two lists is a real risk.

class TestStandalonePrivateCIDRCoverage:
    """Verifies the standalone `PRIVATE_CIDRS` list covers the same risk
    classes as the HA component's. If you add a CIDR to one list, add it
    here too — these tests will fail if you forget."""

    @staticmethod
    def _standalone_cidrs():
        from conftest import load_standalone
        return load_standalone().PRIVATE_CIDRS

    @pytest.mark.parametrize("addr,name", [
        ("10.0.0.1",        "RFC 1918 — 10/8"),
        ("172.16.0.1",      "RFC 1918 — 172.16/12"),
        ("192.168.0.1",     "RFC 1918 — 192.168/16"),
        ("127.0.0.1",       "loopback — 127/8"),
        ("169.254.169.254", "link-local / cloud metadata"),
        ("100.64.0.1",      "CGNAT (RFC 6598)"),
        ("0.0.0.0",         "RFC 1122 'this network'"),
        ("::1",             "IPv6 loopback"),
        ("fe80::1",         "IPv6 link-local"),
        ("fc00::1",         "IPv6 ULA"),
        ("::",              "IPv6 unspecified"),
    ])
    def test_address_in_standalone_private_cidrs(self, addr, name):
        cidrs = self._standalone_cidrs()
        nets = [ipaddress.ip_network(c) for c in cidrs]
        ip = ipaddress.ip_address(addr)
        assert any(ip in n for n in nets), (
            f"Standalone PRIVATE_CIDRS missing {name} ({addr}). "
            f"This is an SSRF vector in `external` mode and a drift from the "
            f"HA component's list."
        )

    def test_standalone_and_ha_lists_agree(self):
        """If the two lists disagree, fix it here OR document why and update
        this test. Drift between them is a long-tail SSRF risk."""
        ha = set(PRIVATE_CIDRS)
        standalone = set(self._standalone_cidrs())
        diff_ha_only = ha - standalone
        diff_standalone_only = standalone - ha
        assert not diff_ha_only and not diff_standalone_only, (
            f"PRIVATE_CIDRS drift detected.\n"
            f"  Only in HA component: {diff_ha_only}\n"
            f"  Only in standalone:   {diff_standalone_only}"
        )


# ─── DNS cache (perf optimization) ───────────────────────────────────────────
#
# Tests the per-process getaddrinfo cache added in proxy.py / standalone:
# correctness (positive results cached, negatives NOT cached, TTL expiry
# works, multi-A-record still validates ALL addresses) and the test hook
# that lets the test suite isolate cache state between cases.

class TestDNSCacheHA:
    """Cache behaviour for the HA component's `_resolve_cached`."""

    @pytest.fixture(autouse=True)
    def _isolate(self):
        from homie_proxy.proxy import _dns_cache_clear
        _dns_cache_clear()
        yield
        _dns_cache_clear()

    async def test_positive_result_is_cached(self, monkeypatch):
        """Two consecutive lookups of the same hostname must hit the OS
        resolver only once. This is the whole point of the cache."""
        from homie_proxy import proxy as ha
        import asyncio

        calls = []

        async def fake_getaddrinfo(host, port, **kw):
            calls.append(host)
            return [(None, None, None, None, ("203.0.113.5", 0))]

        loop = asyncio.get_running_loop()
        monkeypatch.setattr(loop, "getaddrinfo", fake_getaddrinfo)

        a = await ha._resolve_cached("cached-host.example")
        b = await ha._resolve_cached("cached-host.example")

        assert a == ["203.0.113.5"]
        assert b == ["203.0.113.5"]
        assert len(calls) == 1, (
            f"DNS cache miss — expected 1 getaddrinfo call, got {len(calls)}: "
            f"{calls!r}. The cache isn't actually caching."
        )

    async def test_ttl_expiry_triggers_re_resolve(self, monkeypatch):
        """When TTL is exceeded the next lookup MUST re-syscall."""
        from homie_proxy import proxy as ha
        import asyncio

        # Clamp TTL down to "already expired" by the time we ask again.
        monkeypatch.setattr(ha, "DNS_CACHE_TTL", 0.0)

        calls = []
        async def fake_getaddrinfo(host, port, **kw):
            calls.append(host)
            return [(None, None, None, None, ("203.0.113.5", 0))]
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(loop, "getaddrinfo", fake_getaddrinfo)

        await ha._resolve_cached("ttl-host.example")
        await ha._resolve_cached("ttl-host.example")
        assert len(calls) == 2, "TTL=0 should force re-resolution"

    async def test_negative_result_not_cached(self, monkeypatch):
        """Failures (NXDOMAIN, network error) must NOT be cached — a transient
        DNS hiccup shouldn't darken an endpoint for the whole TTL window."""
        from homie_proxy import proxy as ha
        import asyncio

        calls = []
        async def failing_then_succeeding(host, port, **kw):
            calls.append(host)
            if len(calls) == 1:
                raise OSError("DNS unavailable")
            return [(None, None, None, None, ("203.0.113.5", 0))]
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(loop, "getaddrinfo", failing_then_succeeding)

        first = await ha._resolve_cached("flaky-host.example")
        second = await ha._resolve_cached("flaky-host.example")

        assert first is None
        assert second == ["203.0.113.5"], (
            "Negative DNS result was cached — a brief failure now blocks "
            "the endpoint for the full TTL."
        )
        assert len(calls) == 2

    async def test_cache_does_not_break_multi_a_validation(self, monkeypatch):
        """The multi-A-record SSRF defence (every address must pass policy)
        must still work with the cache — i.e. the cache stores ALL addresses,
        not just the first one."""
        from homie_proxy.proxy import ProxyInstance, _resolve_cached
        import asyncio

        async def fake_getaddrinfo(host, port, **kw):
            # Public AND private — must reject the WHOLE hostname in external mode.
            return [
                (None, None, None, None, ("8.8.8.8", 0)),
                (None, None, None, None, ("127.0.0.1", 0)),
            ]
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(loop, "getaddrinfo", fake_getaddrinfo)

        # Confirm the cache returns BOTH addresses.
        addrs = await _resolve_cached("multi-a-cached.example")
        assert addrs == ["8.8.8.8", "127.0.0.1"]

        # And confirm the policy still rejects (every address must satisfy).
        inst = ProxyInstance(
            name="t", tokens=["x"], restrict_out="external", timeout=5,
        )
        assert not await inst.is_target_allowed(
            "http://multi-a-cached.example/"
        )

    async def test_dns_cache_clear_test_hook(self, monkeypatch):
        """The `_dns_cache_clear` test hook MUST actually empty the cache —
        the autouse fixture in conftest depends on this, otherwise tests
        bleed cache state into each other."""
        from homie_proxy import proxy as ha
        import asyncio

        calls = []
        async def fake_getaddrinfo(host, port, **kw):
            calls.append(host)
            return [(None, None, None, None, ("203.0.113.5", 0))]
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(loop, "getaddrinfo", fake_getaddrinfo)

        await ha._resolve_cached("clear-host.example")
        ha._dns_cache_clear()
        await ha._resolve_cached("clear-host.example")

        assert len(calls) == 2, "_dns_cache_clear didn't actually clear the cache"


class TestDNSCacheStandalone:
    """Mirror of the HA-component DNS cache tests for the standalone module.
    The same semantics MUST hold — drift between the two would be a perf
    or security inconsistency."""

    @pytest.fixture(autouse=True)
    def _isolate(self):
        from conftest import load_standalone
        load_standalone()._dns_cache_clear()
        yield
        load_standalone()._dns_cache_clear()

    async def test_positive_result_is_cached(self, monkeypatch):
        from conftest import load_standalone
        sa = load_standalone()
        import asyncio

        calls = []
        async def fake_getaddrinfo(host, port, **kw):
            calls.append(host)
            return [(None, None, None, None, ("203.0.113.5", 0))]
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(loop, "getaddrinfo", fake_getaddrinfo)

        await sa._resolve_cached("sa-cached.example")
        await sa._resolve_cached("sa-cached.example")
        assert len(calls) == 1

    async def test_negative_result_not_cached(self, monkeypatch):
        from conftest import load_standalone
        sa = load_standalone()
        import asyncio

        calls = []
        async def failing(host, port, **kw):
            calls.append(host)
            raise OSError("DNS unavailable")
        loop = asyncio.get_running_loop()
        monkeypatch.setattr(loop, "getaddrinfo", failing)

        assert await sa._resolve_cached("sa-fail.example") is None
        assert await sa._resolve_cached("sa-fail.example") is None
        assert len(calls) == 2

    def test_cache_constants_match_ha(self):
        """If TTL drifts between the modules, the two caches expire on
        different schedules and behaviour gets confusing."""
        from homie_proxy.proxy import DNS_CACHE_TTL as ha_ttl
        from conftest import load_standalone
        sa = load_standalone()
        assert ha_ttl == sa.DNS_CACHE_TTL, (
            f"DNS_CACHE_TTL drift: HA={ha_ttl}, standalone={sa.DNS_CACHE_TTL}"
        )


# ─── Inbound IP filter cases ──────────────────────────────────────────────────

class TestInboundFilter:
    def test_overlapping_cidrs(self):
        """If a tighter CIDR allows it, broader-deny doesn't apply (we OR
        across the list, no precedence)."""
        inst = make(restrict_in_cidrs=["10.0.0.0/8", "192.168.1.0/24"])
        assert     inst.is_client_allowed("10.5.5.5")
        assert     inst.is_client_allowed("192.168.1.50")
        assert not inst.is_client_allowed("172.16.0.1")

    def test_ipv6_inbound(self):
        inst = make(restrict_in_cidrs=["::1/128"])
        assert     inst.is_client_allowed("::1")
        assert not inst.is_client_allowed("fe80::1")
        assert not inst.is_client_allowed("127.0.0.1")

    def test_garbage_ip_value_denied(self):
        inst = make(restrict_in_cidrs=["10.0.0.0/8"])
        assert not inst.is_client_allowed("not-an-ip")
        assert not inst.is_client_allowed("")
        assert not inst.is_client_allowed("10.0.0.1; rm -rf /")


# ─── Token-then-restriction ordering ──────────────────────────────────────────

class TestCheckOrdering:
    """Both `is_token_valid` (sync) and `is_target_allowed` (async) are
    independent; the actual ordering happens in HomieProxyView._handle.
    This is asserted in the integration tests (test_server_integration) but
    we keep a unit-level invariant: a wrong token NEVER gives the attacker
    information about the URL policy."""

    async def test_wrong_token_does_not_evaluate_url(self):
        """We can't directly check which check ran first without a
        side-effect, but we can assert that an instance with NO tokens
        configured rejects the token check independent of the URL policy."""
        inst = make(tokens=[], restrict_out="external")
        assert not inst.is_token_valid("anything")
        # A separate URL check would still pass for a public IP — but the
        # token check is the gate, so the URL never gets evaluated. The
        # behavioural assertion lives in TestAuthentication
        # .test_auth_evaluated_before_url_restriction.
