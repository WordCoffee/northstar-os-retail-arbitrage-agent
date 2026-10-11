"""Environment-only configuration loader for the control layer (Phase 1).

Contract (enforced and tested):

- Secrets are read from the PROCESS ENVIRONMENT only. This module never reads
  ``.env`` files, never calls ``load_dotenv``, and never prints or logs values.
- Absence is reported by NAME only (``SET`` / ``MISSING``), so summaries are
  safe to paste into reports and logs.
- A future Keychain / credential-store backend is an explicit plug-in slot
  (``BACKENDS``); it must never weaken the env-first contract, and no such
  backend is implemented today.

Usage::

    from northstar.security.env_config import get_secret, require_secret

    token = get_secret("BRIGHTDATA_API_KEY")        # None when missing
    token = require_secret("BRIGHTDATA_API_KEY")    # raises when missing
"""
from __future__ import annotations

import os
import re
from typing import Dict, Iterable, Optional

_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Backends are tried in order. Only "env" exists today; a Keychain backend is
# a future plug-in slot and must be reviewed before it is added.
BACKENDS = ("env",)


class MissingSecretError(RuntimeError):
    """Raised when a required secret is absent from the environment."""


def _validate_name(name: str) -> str:
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        raise ValueError(f"invalid secret name: {name!r}")
    return name


def get_secret(
    name: str, *, required: bool = False, default: Optional[str] = None
) -> Optional[str]:
    """Return the trimmed env value for ``name``.

    - missing OR blank (empty/whitespace) OR not a string ⇒ ``default``
      (or raises ``MissingSecretError`` when ``required=True``)
    - the value is returned as-is otherwise (never logged by this module).
    """
    name = _validate_name(name)
    raw = os.environ.get(name)
    value = raw.strip() if isinstance(raw, str) else ""
    if not value:
        if required:
            raise MissingSecretError(
                f"required environment secret is missing: {name}"
            )
        return default
    return value


def require_secret(name: str) -> str:
    """Return the env value or raise ``MissingSecretError``."""
    value = get_secret(name, required=True)
    assert value is not None  # required=True guarantees a value
    return value


def secret_presence(names: Iterable[str]) -> Dict[str, bool]:
    """``{name: is_set}`` — names and booleans only; safe to log."""
    out: Dict[str, bool] = {}
    for name in names:
        _validate_name(name)
        raw = os.environ.get(name)
        out[name] = bool(isinstance(raw, str) and raw.strip())
    return out


def redacted_summary(names: Iterable[str]) -> str:
    """``"NAME=SET, OTHER=MISSING"`` — never contains a value."""
    presence = secret_presence(names)
    return ", ".join(
        f"{name}={'SET' if is_set else 'MISSING'}"
        for name, is_set in presence.items()
    )
