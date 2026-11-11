"""One place that turns Ollama's env vars into an HTTP client URL.

Ollama's own ``OLLAMA_HOST`` is a **bind** address (``0.0.0.0:11434`` on this
box), not a URL. Used raw it produces ``httpx.UnsupportedProtocol: Request URL
is missing an 'http://' or 'https://' protocol`` — and because every caller
swallows that exception, the catalogue reported ``installed: []`` while the
engine was up with 14 tags. The UI then said "no models detected" and the
AutothinK page looked dead next to a live Ollama.

``local_vision``, ``local_screen`` and ``tools/gpu_budget.py`` each grew their
own fix after hitting the same trap. This module is the shared copy so the rest
of the backend stops rediscovering it.

Rules:
* a bare ``host:port`` gains ``http://``;
* ``0.0.0.0`` / ``::`` (bind addresses) become loopback, because you cannot
  connect to a bind address;
* ``localhost`` is left alone (it is already a destination);
* an empty/unset value means the default local engine.
"""

from __future__ import annotations

import os
from typing import Optional
import urllib.parse

DEFAULT_BASE_URL = "http://127.0.0.1:11434"

#: Bind addresses that are not connectable destinations.
_BIND_HOSTS = {"0.0.0.0", "::", "[::]"}
#: Env vars that may name the engine, in precedence order.
_ENV_NAMES = ("OLLAMA_BASE_URL", "TY_OLLAMA_URL", "OLLAMA_HOST")


def normalise_host(value: Optional[str]) -> str:
    """Return a client-usable base URL for an Ollama-style host string."""
    raw = (value or "").strip().rstrip("/")
    if not raw:
        return DEFAULT_BASE_URL
    if "://" not in raw:
        raw = "http://" + raw
    parsed = urllib.parse.urlsplit(raw)
    host = parsed.hostname or "127.0.0.1"
    if host in _BIND_HOSTS:
        host = "127.0.0.1"
    port = parsed.port or 11434
    return f"{parsed.scheme or 'http'}://{host}:{port}"


def ollama_base_url(environ: Optional[dict] = None) -> str:
    """First configured engine host, normalised. Falls back to loopback."""
    env = os.environ if environ is None else environ
    for name in _ENV_NAMES:
        value = env.get(name)
        if value and value.strip():
            return normalise_host(value)
    return DEFAULT_BASE_URL


__all__ = ["DEFAULT_BASE_URL", "normalise_host", "ollama_base_url"]
