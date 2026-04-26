"""
Unit tests for HomieProxy core logic.

Tests the HA component's ProxyInstance class and SSL helpers in isolation —
no server, no Home Assistant, no network required.
"""
import ipaddress
import ssl
import pytest

from homie_proxy.proxy import (
    ProxyInstance,
    _build_ssl_context,
    _get_ssl_context,
    _parse_skip_tls,
    _ssl_ctx_cache,
)

# asyncio_mode = auto in pytest.ini handles async test discovery globally.


# ─── Helpers ──────────────────────────────────────────────────────────────────

def instance(**kwargs) -> ProxyInstance:
    """Build a ProxyInstance with sensible test defaults."""
    defaults = dict(
        name="test",
        tokens=["good-token"],
        restrict_out="any",
        restrict_out_cidrs=None,
        restrict_in_cidrs=None,
        timeout=30,
    )
    defaults.update(kwargs)
    return ProxyInstance(**defaults)


# ─── Token validation ─────────────────────────────────────────────────────────

class TestTokenValidation:
    def test_correct_token_accepted(self):
        inst = instance(tokens=["abc", "def"])
        assert inst.is_token_valid("abc")
        assert inst.is_token_valid("def")

    def test_wrong_token_rejected(self):
        inst = instance(tokens=["abc"])
        assert not inst.is_token_valid("wrong")

    def test_empty_string_rejected(self):
        assert not instance().is_token_valid("")

    def test_none_rejected(self):
        assert not instance().is_token_valid(None)

    def test_no_tokens_configured_denies_everything(self):
        """Empty token list → deny all (secure by default)."""
        inst = instance(tokens=[])
        assert not inst.is_token_valid("anything")
        assert not inst.is_token_valid(None)

    def test_token_must_match_exactly(self):
        inst = instance(tokens=["secret"])
        assert not inst.is_token_valid("secret ")   # trailing space
        assert not inst.is_token_valid(" secret")   # leading space
        assert not inst.is_token_valid("SECRET")    # case differs


# ─── Inbound IP restriction ───────────────────────────────────────────────────

class TestClientAllowed:
    def test_no_restriction_allows_any_ip(self):
        inst = instance(restrict_in_cidrs=[])
        assert inst.is_client_allowed("1.2.3.4")
        assert inst.is_client_allowed("192.168.1.1")
        assert inst.is_client_allowed("127.0.0.1")

    def test_cidr_allows_matching_ip(self):
        inst = instance(restrict_in_cidrs=["192.168.1.0/24"])
        assert inst.is_client_allowed("192.168.1.1")
        assert inst.is_client_allowed("192.168.1.254")

    def test_cidr_blocks_non_matching_ip(self):
        inst = instance(restrict_in_cidrs=["192.168.1.0/24"])
        assert not inst.is_client_allowed("192.168.2.1")
        assert not inst.is_client_allowed("10.0.0.1")

    def test_multiple_cidrs_any_match_passes(self):
        inst = instance(restrict_in_cidrs=["10.0.0.0/8", "192.168.1.0/24"])
        assert inst.is_client_allowed("10.1.2.3")
        assert inst.is_client_allowed("192.168.1.50")
        assert not inst.is_client_allowed("172.16.0.1")

    def test_garbage_ip_denied(self):
        inst = instance(restrict_in_cidrs=["192.168.1.0/24"])
        assert not inst.is_client_allowed("not-an-ip")
        assert not inst.is_client_allowed("")


# ─── Outbound URL restriction ─────────────────────────────────────────────────

class TestTargetAllowed:
    async def test_any_mode_allows_all_ips(self):
        inst = instance(restrict_out="any")
        assert await inst.is_target_allowed("http://8.8.8.8/dns")
        assert await inst.is_target_allowed("http://192.168.1.1/api")
        assert await inst.is_target_allowed("http://10.0.0.1/api")

    async def test_external_blocks_rfc1918(self):
        inst = instance(restrict_out="external")
        assert not await inst.is_target_allowed("http://192.168.1.1/api")
        assert not await inst.is_target_allowed("http://10.0.0.1/api")
        assert not await inst.is_target_allowed("http://172.16.0.1/api")

    async def test_external_blocks_loopback(self):
        """127.0.0.1 must be blocked in external mode — proxying to HA's own API."""
        inst = instance(restrict_out="external")
        assert not await inst.is_target_allowed("http://127.0.0.1:8123/api/states")
        assert not await inst.is_target_allowed("http://127.0.0.1/")

    async def test_external_blocks_link_local(self):
        """169.254.169.254 is the AWS/GCP/Azure metadata endpoint — must be blocked."""
        inst = instance(restrict_out="external")
        assert not await inst.is_target_allowed("http://169.254.169.254/latest/meta-data/")

    async def test_external_allows_public_ips(self):
        inst = instance(restrict_out="external")
        assert await inst.is_target_allowed("http://8.8.8.8/dns")
        assert await inst.is_target_allowed("http://1.1.1.1/dns")

    async def test_internal_allows_private_ips(self):
        inst = instance(restrict_out="internal")
        assert await inst.is_target_allowed("http://192.168.1.1/api")
        assert await inst.is_target_allowed("http://10.0.0.1/api")

    async def test_internal_blocks_public_ips(self):
        inst = instance(restrict_out="internal")
        assert not await inst.is_target_allowed("http://8.8.8.8/dns")

    async def test_custom_cidr_allows_matching(self):
        inst = instance(
            restrict_out="custom",
            restrict_out_cidrs=["8.8.8.0/24", "1.1.1.0/24"],
        )
        assert await inst.is_target_allowed("http://8.8.8.8/dns")
        assert await inst.is_target_allowed("http://1.1.1.1/dns")

    async def test_custom_cidr_blocks_non_matching(self):
        inst = instance(
            restrict_out="custom",
            restrict_out_cidrs=["8.8.8.0/24"],
        )
        assert not await inst.is_target_allowed("http://9.9.9.9/dns")
        assert not await inst.is_target_allowed("http://192.168.1.1/api")

    async def test_empty_url_denied(self):
        inst = instance()
        assert not await inst.is_target_allowed("")

    async def test_url_without_hostname_denied(self):
        inst = instance()
        assert not await inst.is_target_allowed("http://")

    async def test_unresolvable_hostname_denied(self):
        """DNS failure → deny (safe default)."""
        inst = instance(restrict_out="external")
        assert not await inst.is_target_allowed("http://this-hostname-does-not-exist.invalid/")


# ─── CIDR parsing ─────────────────────────────────────────────────────────────

class TestCIDRParsing:
    def test_valid_cidrs_parsed(self):
        nets = ProxyInstance._parse_cidrs(["10.0.0.0/8", "192.168.0.0/16"])
        assert len(nets) == 2
        assert ipaddress.ip_network("10.0.0.0/8") in nets

    def test_invalid_cidr_silently_skipped(self):
        nets = ProxyInstance._parse_cidrs(["10.0.0.0/8", "not-a-cidr", "192.168.0.0/16"])
        assert len(nets) == 2

    def test_empty_list(self):
        assert ProxyInstance._parse_cidrs([]) == []

    def test_empty_strings_skipped(self):
        nets = ProxyInstance._parse_cidrs(["", "10.0.0.0/8", ""])
        assert len(nets) == 1

    def test_host_bits_normalised(self):
        """192.168.1.5/24 should parse (strict=False normalises it to 192.168.1.0/24)."""
        nets = ProxyInstance._parse_cidrs(["192.168.1.5/24"])
        assert len(nets) == 1
        assert nets[0] == ipaddress.ip_network("192.168.1.0/24")


# ─── Legacy migration ─────────────────────────────────────────────────────────

class TestLegacyCompat:
    def test_restrict_out_cidr_string_becomes_custom(self):
        """Old configs stored a bare CIDR string in restrict_out."""
        inst = ProxyInstance(name="legacy", tokens=["t"], restrict_out="10.0.0.0/8")
        assert inst.restrict_out == "custom"
        assert len(inst.restrict_out_cidrs) == 1

    def test_invalid_restrict_out_defaults_to_any(self):
        inst = ProxyInstance(name="legacy", tokens=["t"], restrict_out="garbage")
        assert inst.restrict_out == "any"

    def test_restrict_in_legacy_shim_merged(self):
        """The old single-CIDR `restrict_in` param is merged into restrict_in_cidrs."""
        inst = ProxyInstance(
            name="legacy", tokens=["t"], restrict_out="any",
            restrict_in="192.168.1.0/24",
        )
        assert len(inst.restrict_in_cidrs) == 1


# ─── SSL context helpers ──────────────────────────────────────────────────────

class TestSSLContext:
    def setup_method(self):
        _ssl_ctx_cache.clear()

    def test_empty_list_returns_none(self):
        assert _build_ssl_context([]) is None
        assert _get_ssl_context([]) is None

    def test_all_disables_full_verification(self):
        ctx = _get_ssl_context(["all"])
        assert ctx is not None
        assert ctx.check_hostname is False
        assert ctx.verify_mode == ssl.CERT_NONE

    def test_true_string_equivalent_to_all(self):
        checks = _parse_skip_tls({"skip_tls_checks": ["true"]})
        assert checks == ["all"]

    def test_comma_separated_checks_split(self):
        checks = _parse_skip_tls({"skip_tls_checks": ["self_signed,expired_cert"]})
        assert "self_signed" in checks
        assert "expired_cert" in checks

    def test_missing_key_returns_empty(self):
        assert _parse_skip_tls({}) == []

    def test_same_config_returns_cached_object(self):
        """SSL context must be cached — not rebuilt on every request."""
        ctx1 = _get_ssl_context(["all"])
        ctx2 = _get_ssl_context(["all"])
        assert ctx1 is ctx2

    def test_unknown_checks_alone_return_none(self):
        """Unrecognised check names alone must not create a modified context."""
        ctx = _build_ssl_context(["unknown_thing"])
        assert ctx is None

    def test_hostname_mismatch_disables_check_hostname(self):
        ctx = _build_ssl_context(["hostname_mismatch"])
        assert ctx is not None
        assert ctx.check_hostname is False
