"""Constants for the Homie Proxy integration."""

DOMAIN = "homie_proxy"

# Configuration keys
CONF_NAME = "name"
CONF_TOKENS = "tokens"  # Support for multiple tokens
CONF_RESTRICT_OUT = "restrict_out"
CONF_RESTRICT_OUT_CIDRS = "restrict_out_cidrs"
CONF_RESTRICT_IN_CIDRS = "restrict_in_cidrs"
CONF_REQUIRES_AUTH = "requires_auth"  # Home Assistant authentication requirement
CONF_TIMEOUT = "timeout"  # Request timeout per instance

# Defaults
DEFAULT_NAME = "external-api-route"
DEFAULT_RESTRICT_OUT = "any"
DEFAULT_REQUIRES_AUTH = True  # Secure by default
DEFAULT_TIMEOUT = 300  # 5 minutes default timeout

# Restriction options
RESTRICT_OPTIONS = [
    ("any", "Allow all networks"),
    ("external", "External networks only"),
    ("internal", "Internal networks only"),
    ("custom", "Custom cidr"),
]

# Private / reserved CIDR ranges used by restrict_out=external|internal.
# Keep this list complete — gaps are SSRF vectors.
PRIVATE_CIDRS = [
    # IPv4 "this network" (RFC 1122). On Linux a connect() to 0.0.0.0 is
    # routed to 127.0.0.1, so this MUST be blocked alongside 127/8.
    "0.0.0.0/8",
    # IPv4 RFC 1918
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    # IPv4 loopback — blocks proxying to 127.0.0.1 (i.e. HA itself)
    "127.0.0.0/8",
    # IPv4 link-local — blocks AWS/GCP/Azure metadata endpoints (169.254.169.254)
    "169.254.0.0/16",
    # IPv4 CGNAT (RFC 6598)
    "100.64.0.0/10",
    # IPv6 unspecified
    "::/128",
    # IPv6 loopback
    "::1/128",
    # IPv6 link-local
    "fe80::/10",
    # IPv6 Unique Local (RFC 4193)
    "fc00::/7",
]