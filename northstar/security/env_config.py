"""Configuration loader for the control layer (Phase 1; env-file support added
per owner directive 2026-10-11).

Contract (enforced and tested):

- Secrets are read from the PROCESS ENVIRONMENT. Additionally, and ONLY when
  the operator sets the ``NORTHSTAR_ENV_FILE`` environment variable to a path,
  the loader may read values from that file. The path is never hardcoded here
  and never echoed; file contents are never logged or printed.
- Absence is reported by NAME only (``SET`` / ``MISSING``), so summaries are
  safe to paste into reports and logs.
- ``require_env_file()`` fails CLOSED with a clear error when
  ``NORTHSTAR_ENV_FILE`` is unset or the file is missing/unreadable — the
  message contains the variable NAME only, never a path or a value.
- A future Keychain / credential-store backend is an explicit plug-in slot
  (``BACKENDS``); it must never weaken the env-first contract, and no such
  backend is implemented today.
- This module never calls ``load_dotenv`` and never imports any dotenv library.

Usage::

    from northstar.security.env_config import get_secret, require_secret

    token = get_secret("BRIGHTDATA_API_KEY")        # None when missing
    token = require_secret("BRIGHTDATA_API_KEY")    # raises when missing
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, Iterable, Optional

_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Backends are tried in order. Only environment (+ the operator-designated
# env file) exists today; a Keychain backend is a future plug-in slot and must
# be reviewed before it is added.
BACKENDS = ("env",)

#: Environment variable holding the PATH of the operator-designated env file.
#: The path itself is never hardcoded in code, tests, docs, or reports.
ENV_FILE_VAR = "NORTHSTAR_ENV_FILE"


class MissingSecretError(RuntimeError):
    """Raised when a required secret is absent from the configured sources."""


class EnvFileError(RuntimeError):
    """Base error for the NORTHSTAR_ENV_FILE mechanism (never contains values)."""


class EnvFileNotConfiguredError(EnvFileError):
    """NORTHSTAR_ENV_FILE is not set."""


class EnvFileMissingError(EnvFileError):
    """NORTHSTAR_ENV_FILE is set but the file is missing or unreadable."""


def _validate_name(name: str) -> str:
    if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
        raise ValueError(f"invalid secret name: {name!r}")
    return name


def env_file_path() -> Optional[Path]:
    """The operator-designated env-file path, or None when not configured."""
    raw = os.environ.get(ENV_FILE_VAR)
    if not isinstance(raw, str) or not raw.strip():
        return None
    return Path(raw.strip()).expanduser()


def _parse_env_text(text: str) -> Dict[str, str]:
    """Minimal .env parser: KEY=VALUE lines, # comments, optional quotes.

    Later duplicate keys win. Never logs or returns anything but the mapping.
    """
    out: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if key:
            out[key] = value
    return out


def _file_values() -> Dict[str, str]:
    """Best-effort file source for lookups; empty when unavailable.

    The LOUD failure path for a missing/unset file is ``require_env_file()``.
    """
    path = env_file_path()
    if path is None:
        return {}
    try:
        return _parse_env_text(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return {}


def require_env_file() -> Dict[str, str]:
    """Load and return the operator-designated env file, failing closed.

    Raises ``EnvFileNotConfiguredError`` when NORTHSTAR_ENV_FILE is unset and
    ``EnvFileMissingError`` when the file is missing or unreadable. Error
    messages contain the variable NAME only — never a path or a value.
    """
    path = env_file_path()
    if path is None:
        raise EnvFileNotConfiguredError(
            f"{ENV_FILE_VAR} is not set — set it to the path of the environment file"
        )
    if not path.is_file():
        raise EnvFileMissingError(
            f"{ENV_FILE_VAR} points to a file that does not exist — "
            "update the variable or restore the file"
        )
    try:
        return _parse_env_text(path.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        raise EnvFileMissingError(
            f"{ENV_FILE_VAR} points to a file that could not be read"
        ) from exc


def get_secret(
    name: str, *, required: bool = False, default: Optional[str] = None
) -> Optional[str]:
    """Return the trimmed value for ``name`` (process env first, then the
    operator-designated env file).

    - missing OR blank OR non-string ⇒ ``default`` (or raises
      ``MissingSecretError`` when ``required=True``).
    - the value is returned as-is otherwise (never logged by this module).
    """
    name = _validate_name(name)
    raw = os.environ.get(name)
    value = raw.strip() if isinstance(raw, str) else ""
    if not value:
        file_value = _file_values().get(name, "")
        value = file_value.strip() if isinstance(file_value, str) else ""
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
    """``{name: is_set}`` — names and booleans only; safe to log.

    Considers BOTH the process environment and (when configured) the
    operator-designated env file. Never returns or logs values.
    """
    file_values = _file_values()
    out: Dict[str, bool] = {}
    for name in names:
        _validate_name(name)
        raw = os.environ.get(name)
        in_env = bool(isinstance(raw, str) and raw.strip())
        in_file = bool(str(file_values.get(name, "")).strip())
        out[name] = in_env or in_file
    return out


def redacted_summary(names: Iterable[str]) -> str:
    """``"NAME=SET, OTHER=MISSING"`` — never contains a value."""
    presence = secret_presence(names)
    return ", ".join(
        f"{name}={'SET' if is_set else 'MISSING'}"
        for name, is_set in presence.items()
    )
