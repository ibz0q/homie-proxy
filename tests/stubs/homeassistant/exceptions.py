"""Stub for homeassistant.exceptions."""


class HomeAssistantError(Exception):
    pass


class ConfigEntryNotReady(HomeAssistantError):
    pass


class ServiceNotFound(HomeAssistantError):
    pass
