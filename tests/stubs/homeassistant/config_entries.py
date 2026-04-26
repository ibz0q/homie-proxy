"""Stub for homeassistant.config_entries."""
from typing import Any, Dict, Optional


class ConfigEntry:
    entry_id: str = ""
    data: Dict[str, Any] = {}
    options: Dict[str, Any] = {}
    title: str = ""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class ConfigFlow:
    VERSION = 1

    def __init_subclass__(cls, domain=None, **kwargs):
        """Accept the `domain=` keyword used by HA config flows."""
        super().__init_subclass__(**kwargs)

    async def async_step_user(self, user_input=None):
        pass


class OptionsFlow:
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)


SOURCE_USER = "user"
