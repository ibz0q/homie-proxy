"""Constants for the Homie Proxy integration."""

DOMAIN = "homie_proxy"

# Configuration keys
CONF_NAME = "name"
CONF_TOKEN = "token"
CONF_TOKENS = "tokens"  # New: Support for multiple tokens
CONF_RESTRICT_OUT = "restrict_out"
CONF_RESTRICT_OUT_CIDRS = "restrict_out_cidrs"
CONF_RESTRICT_IN_CIDRS = "restrict_in_cidrs"

# Defaults
DEFAULT_NAME = "external-api-route"
DEFAULT_RESTRICT_OUT = "any"

# Restriction options
RESTRICT_OPTIONS = [
    ("any", "Allow all networks"),
    ("external", "External networks only"),
    ("internal", "Internal networks only"),
    ("custom", "Custom cidr"),
]

# Default CIDR ranges
PRIVATE_CIDRS = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
LOCAL_CIDRS = ["192.168.0.0/16"] 