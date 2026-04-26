"""Minimal voluptuous stub — enough to make HA component importable in tests."""


def Schema(schema, *args, **kwargs):
    return schema


class Required:
    def __init__(self, key, *args, **kwargs):
        self.key = key

    def __call__(self, v):
        return v


class Optional:
    def __init__(self, key, *args, **kwargs):
        self.key = key

    def __call__(self, v):
        return v


def All(*validators):
    return validators[0] if validators else (lambda x: x)


def Any(*validators):
    return validators[0] if validators else (lambda x: x)


def In(container):
    return lambda x: x


def Range(**kwargs):
    return lambda x: x


def Length(**kwargs):
    return lambda x: x


def Coerce(t):
    return t


class Invalid(Exception):
    pass


# Schema extra-key policies
ALLOW_EXTRA = "allow_extra"
PREVENT_EXTRA = "prevent_extra"
REMOVE_EXTRA = "remove_extra"
