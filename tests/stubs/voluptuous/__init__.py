"""Voluptuous stub that mirrors the bits real voluptuous does that affect
config-flow correctness — in particular, **default substitution for
missing keys**. The previous bare stub returned the schema verbatim from
`Schema(...)` and never executed it, which meant a class of config-flow
bugs (the empty-CIDRs-not-clearing one) sailed through CI undetected.

What this stub now models:
  * `Schema(d)(data)` walks the dict-of-marker-to-validator declaration
    and produces a validated dict, just like real voluptuous.
  * `Required(key, default=X)` and `Optional(key, default=X)` both
    inject `X` when the key is missing from `data` — **identical to
    real voluptuous**. This is the behaviour that caused the bug.
  * `Optional(key, description={"suggested_value": X})` does **not**
    inject — `suggested_value` is form-rendering metadata only.

Validators themselves are passed through (no type coercion, no
constraint enforcement) — full voluptuous semantics aren't needed for
config-flow tests, just the marker-default behaviour.
"""

_SENTINEL = object()


class _Schema:
    def __init__(self, schema):
        self._schema = schema

    def __call__(self, data):
        # If schema isn't a dict (e.g. someone wrapped a scalar), pass through.
        if not isinstance(self._schema, dict):
            return data
        out = dict(data) if data is not None else {}
        for marker, _validator in self._schema.items():
            # Plain-string keys: no marker semantics.
            if not isinstance(marker, _Marker):
                continue
            if marker.key in out:
                continue
            if marker.default is not _SENTINEL:
                # Real voluptuous: callable defaults are invoked.
                out[marker.key] = (
                    marker.default() if callable(marker.default) else marker.default
                )
            # else: missing + no default → leave absent (matches real voluptuous
            # for Optional; Required would raise, but tests don't currently
            # construct Required without a default).
        return out


def Schema(schema, *args, **kwargs):
    return _Schema(schema)


class _Marker:
    def __init__(self, key, default=_SENTINEL, description=None, **kwargs):
        self.key = key
        self.default = default
        self.description = description

    # Markers in a dict literal are used as keys — must be hashable.
    def __hash__(self):
        return hash((type(self).__name__, self.key))

    def __eq__(self, other):
        return isinstance(other, _Marker) and self.key == other.key and type(self) is type(other)


class Required(_Marker):
    def __call__(self, v):
        return v


class Optional(_Marker):
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
