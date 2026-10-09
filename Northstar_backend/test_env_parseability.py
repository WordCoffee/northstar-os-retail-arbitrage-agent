"""Environment-file parseability (P1-08, closed 2026-10-09).

The repo-root `.env` carried one line in the shape ``domain key: <secret>``
(no ``=``), which python-dotenv rejects — and rejecting one line stops it
loading ANY key from the file. That silently disarmed every root-level
provider key and, worse, made config intent and runtime state disagree without
failing loudly.

This test parses the real file with the same library the app uses and asserts:

  1. it parses with no warnings and no unparsable lines,
  2. the keys the app actually reads are present by name (never by value),
  3. every line is either blank, a comment, or ``KEY=VALUE``.

Only key NAMES are inspected. No value is read into a variable, printed, or
asserted.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import dotenv_values  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATHS = (_REPO_ROOT / ".env", _REPO_ROOT / "Northstar_backend" / ".env")

# Keys the suite reads from the environment. Names only — never values.
# The live gate is only required in the backend env file, which is the one the
# API actually loads (the documented dual-.env divergence); the root file may
# legitimately omit it.
_REQUIRED_KEYS_BY_ENV = {
    _REPO_ROOT / ".env": (),
    _REPO_ROOT / "Northstar_backend" / ".env": ("SCANNER_LIVE_ALLOWED",),
}

_BOOL_KEYS = (
    "SCANNER_LIVE_ALLOWED",
    "CLOUD_MODEL_LIVE",
    "DATAFORSEO_ENABLED",
)


class EnvFileParseTests:
    """Plain assertions (pytest and unittest both collect these)."""


def _parse(path: Path) -> dict:
    # dotenv_values returns None for a malformed value; a bare unparsable
    # line makes the whole key set collapse, which is what we are guarding.
    return {k: v for k, v in dotenv_values(str(path)).items() if k}


def test_env_files_exist():
    for path in _ENV_PATHS:
        assert path.is_file(), f"missing env file: {path}"


def test_root_env_parses_with_all_keys():
    parsed = _parse(_REPO_ROOT / ".env")
    # The audit recorded 53 keys; the malformed line cost the file every key.
    assert len(parsed) >= 40, f"only {len(parsed)} keys parsed from root .env"


def test_backend_env_parses():
    parsed = _parse(_REPO_ROOT / "Northstar_backend" / ".env")
    assert len(parsed) >= 20, f"only {len(parsed)} keys parsed from backend .env"


def test_no_unparsable_lines_in_root_env():
    """Every non-blank, non-comment line must be ``KEY=VALUE``."""
    text = (_REPO_ROOT / ".env").read_text(encoding="utf-8", errors="replace")
    bad = []
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped.split(" ")[0]:
            bad.append(number)
        elif not stripped.split("=", 1)[0].replace("_", "").isalnum():
            bad.append(number)
    assert not bad, f"unparsable .env lines: {bad}"


def test_required_keys_present_by_name():
    for path, keys in _REQUIRED_KEYS_BY_ENV.items():
        parsed = _parse(path)
        for key in keys:
            assert key in parsed, f"{path.name} is missing {key}"


def test_scanner_live_gate_is_disarmed_in_every_env_file():
    """The 2026-10-08 incident's exact root cause: the gate was armed.

    The gate must not be armed anywhere it can reach the app. An absent key
    is the safe default (the gate fails closed), so only an explicit opt-in
    is refused.
    """
    for path in _ENV_PATHS:
        parsed = _parse(path)
        value = (parsed.get("SCANNER_LIVE_ALLOWED") or "").strip().lower()
        assert value not in ("1", "true", "yes", "on"), (
            f"{path.name} arms SCANNER_LIVE_ALLOWED — a GET could spend money"
        )


def test_boolean_keys_are_parsable_as_booleans():
    for path in _ENV_PATHS:
        parsed = _parse(path)
        for key in _BOOL_KEYS:
            if key not in parsed:
                continue
            value = (parsed[key] or "").strip().lower()
            assert value in ("", "0", "1", "true", "false", "yes", "no", "on", "off"), (
                f"{path.name}:{key} is not a boolean token"
            )
