"""Stub for homeassistant.components.http."""
from typing import List


class HomeAssistantView:
    """Minimal stub matching the interface used by HomieProxyView."""

    url: str = ""
    name: str = ""
    requires_auth: bool = True
    cors_allowed: bool = True
    extra_urls: List[str] = []

    async def get(self, request):
        pass

    async def post(self, request):
        pass
