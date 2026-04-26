"""Stub for homeassistant.core."""
from typing import Any, Dict


class HomeAssistant:
    """Minimal stub — only the attributes used by proxy.py at runtime."""

    def __init__(self):
        self.data: Dict[str, Any] = {}


def callback(func):
    """No-op decorator stub."""
    return func
