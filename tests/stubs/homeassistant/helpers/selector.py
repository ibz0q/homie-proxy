"""Stub for homeassistant.helpers.selector.

config_flow.py constructs selectors at module-load time, so every class and
enum referenced there must exist here even though the stubs do nothing.
"""


class _NullSelector:
    """Generic stub: accepts any args and returns itself."""

    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return self


def selector(config):
    """Return the config dict unchanged."""
    return config


# ── Text ─────────────────────────────────────────────────────────────────────

class TextSelectorType:
    TEXT = "text"
    PASSWORD = "password"
    EMAIL = "email"
    URL = "url"


class TextSelectorConfig(_NullSelector):
    pass


class TextSelector(_NullSelector):
    pass


# ── Select ────────────────────────────────────────────────────────────────────

class SelectSelectorMode:
    DROPDOWN = "dropdown"
    LIST = "list"


class SelectOptionDict(_NullSelector):
    pass


class SelectSelectorConfig(_NullSelector):
    pass


class SelectSelector(_NullSelector):
    pass


# ── Number ────────────────────────────────────────────────────────────────────

class NumberSelectorMode:
    BOX = "box"
    SLIDER = "slider"


class NumberSelectorConfig(_NullSelector):
    pass


class NumberSelector(_NullSelector):
    pass


# ── Boolean ───────────────────────────────────────────────────────────────────

class BooleanSelector(_NullSelector):
    pass
