"""Runtime configuration for the ledger service.

Defaults live in code and environment variables override them. There is no
feature-flag mechanism yet, so every setting below is unconditional.
"""
from __future__ import annotations

DEFAULTS = {
    "service_name": "ledger",
    "max_retries": 3,
    "timeout_seconds": 30,
    "read_only": True,
}

TRUTHY = ("1", "true", "yes", "on")
FALSY = ("0", "false", "no", "off")


def coerce(raw):
    """Turn an environment string into a bool, an int, or the raw text."""
    text = str(raw).strip()
    if text.lower() in TRUTHY:
        return True
    if text.lower() in FALSY:
        return False
    try:
        return int(text)
    except ValueError:
        return text


def get(name, default=None, environ=None):
    env = {} if environ is None else environ
    if name in env:
        return coerce(env[name])
    if name in DEFAULTS:
        return DEFAULTS[name]
    return default


def load(environ=None):
    env = {} if environ is None else environ
    settings = dict(DEFAULTS)
    names = list(DEFAULTS) + sorted(set(env) - set(DEFAULTS))
    for name in names:
        value = get(name, environ=env)
        if value is not None:
            settings[name] = value
    return settings
