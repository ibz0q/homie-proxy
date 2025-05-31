"""Constants for the Homie Proxy integration."""

DOMAIN = "homie_proxy"

# Configuration keys
CONF_NAME = "name"
CONF_TOKEN = "token"
CONF_TOKENS = "tokens"  # New: Support for multiple tokens
CONF_RESTRICT_OUT = "restrict_out"
CONF_RESTRICT_IN = "restrict_in"

# Defaults
DEFAULT_NAME = "external-api-route"
DEFAULT_RESTRICT_OUT = "private"

# Restriction options
RESTRICT_OPTIONS = [
    ("any", "Allow all destinations"),
    ("private", "Private networks only (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)"),
    ("local", "Local network only (192.168.0.0/16)"),
    ("custom", "Custom CIDR range"),
]

# Default CIDR ranges
PRIVATE_CIDRS = ["10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
LOCAL_CIDRS = ["192.168.0.0/16"] 