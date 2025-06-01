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

# Default CIDR ranges
PRIVATE_CIDRS = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"] 