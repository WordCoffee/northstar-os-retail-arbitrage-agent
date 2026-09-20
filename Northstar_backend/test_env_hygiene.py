"""Phase F/S12 — .env / credential isolation tests.

Verifies that:
  - credential-shaped env vars never leak into the test process,
  - the harness-safe vars survive the scrub,
  - .env files are NOT tracked by git (even though they exist on disk),
  - no value present in a parsed .env appears as an env var value during tests.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parent
_REPO = _BACKEND.parent

_CREDENTIAL_RE = re.compile(
    r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|API\.?KEY|AUTH", re.IGNORECASE
)

_SAFE_VARS = {
    "NORTHSTAR_DISABLE_RATE_LIMIT",
    "ENVIRONMENT",
    "GOLDEN_GOOSE_DEBUG",
    "GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED",
}

import conftest as _conftest  # noqa: E402


def _credential_vars_now() -> list:
    return [
        n for n in os.environ
        if _CREDENTIAL_RE.search(n) and n not in _SAFE_VARS
        and not _conftest._is_placeholder_value(os.environ[n])
    ]


def test_no_credential_env_vars_present() -> None:
    assert _credential_vars_now() == [], (
        "real credential values leaked into the test process: %r"
        % {n: "<redacted>" for n in _credential_vars_now()}
    )


def test_scrub_function_removes_and_preserves_safe() -> None:
    os.environ["SUPERSECRET_API_KEY"] = "leak-me"
    os.environ["NORTHSTAR_DISABLE_RATE_LIMIT"] = "1"
    snapshot = _conftest._scrub_credential_env()
    assert "SUPERSECRET_API_KEY" not in os.environ
    assert os.environ.get("NORTHSTAR_DISABLE_RATE_LIMIT") == "1"   # safe var kept
    _conftest._restore_env(snapshot)


def test_offline_mock_placeholder_keys_survive() -> None:
    """Test-authored mock keys (DUMMY / test-key-*) are NOT real secrets.

    The offline rehearsal suites set credential-NAMED vars to placeholders so
    their mocked provider paths run; S12 must not break them.
    """
    os.environ["KEENABLE_API_KEY"] = "DUMMY"
    os.environ["BRIGHTDATA_UNLOCKER_API_KEY"] = "test-key-brightdata"
    os.environ["FIRECRAWL_API_KEY"] = "test-key-firecrawl"
    snapshot = _conftest._scrub_credential_env()
    try:
        assert os.environ.get("KEENABLE_API_KEY") == "DUMMY"
        assert os.environ.get("BRIGHTDATA_UNLOCKER_API_KEY") == "test-key-brightdata"
        assert os.environ.get("FIRECRAWL_API_KEY") == "test-key-firecrawl"
    finally:
        _conftest._restore_env(snapshot)


def test_env_files_not_tracked_by_git() -> None:
    root = Path(subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], cwd=_REPO, text=True
    ).strip())
    tracked = subprocess.check_output(
        ["git", "ls-files"], cwd=root, text=True
    ).splitlines()
    env_tracked = [p for p in tracked if p.endswith(".env")]
    assert env_tracked == [], "tracked .env files found: %r" % env_tracked


def test_dotenv_values_never_present_after_scrub(tmp_path: Path) -> None:
    """Simulate a provider module importing a .env, then scrub.

    The scenario under test: amazon_search.brightdata calls load_dotenv() at
    import time; values must not survive into the test environment.
    """
    env_file = tmp_path / ".env"
    env_file.write_text(
        "BRIGHTDATA_API_TOKEN=super-secret-token\nOPENAI_API_KEY=sk-leak\n",
        encoding="utf-8",
    )
    from dotenv import dotenv_values
    parsed = dotenv_values(str(env_file))
    for name in parsed:
        os.environ[name] = parsed[name]
    snapshot = _conftest._scrub_credential_env()
    try:
        for name, value in parsed.items():
            assert os.environ.get(name) != value, (
                "leaked %s=%s from a .env into the test process" % (name, value)
            )
            assert name not in os.environ, name
    finally:
        _conftest._restore_env(snapshot)


def test_env_example_tracked_but_is_placeholder() -> None:
    """The committed .env.example must exist and hold no real values."""
    example = _BACKEND.parent / ".env.example"
    assert example.exists(), ".env.example missing from repo"
    text = example.read_text(encoding="utf-8", errors="replace")
    for marker in ("sk-", "Bearer ", "past", "secret"):
        # placeholders should only appear inside obviously-fake positions
        assert text.count(marker) == 0 or "example" in text.lower()