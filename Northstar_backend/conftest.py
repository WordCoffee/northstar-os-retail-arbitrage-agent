"""Phase F/S12 — .env / credential isolation for the test process.

The app's provider modules call ``load_dotenv()`` at import time (amazon_search,
brightdata_*, etc.). If a local .env sits on the import path, those calls would
leak real credential values into os.environ for the whole pytest process.

This conftest scrubs credential-shaped env vars:
  - once at pytest_configure (before tests run),
  - and again before each test via an autouse fixture (defensive against any
    test that triggers load_dotenv() mid-run).

Non-credential harness vars (NORTHSTAR_DISABLE_RATE_LIMIT, ENVIRONMENT,
GOLDEN_GOOSE_DEBUG) are preserved. Never read or print credential values.
"""

from __future__ import annotations

import os
import re

import pytest

# Keep these harness variables; everything credential-shaped is scrubbed.
_SAFE_VARS = {
    "NORTHSTAR_DISABLE_RATE_LIMIT",
    "ENVIRONMENT",
    "GOLDEN_GOOSE_DEBUG",
    "GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED",
}

_CREDENTIAL_RE = re.compile(
    r"KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL|API\.?KEY|AUTH", re.IGNORECASE
)

_snapshot: dict = {}


def _scrub_credential_env() -> dict:
    """Remove credential-shaped vars from os.environ.

    Returns a snapshot {name: value} so tests can restore them afterward
    (restoration is only for consistency — nothing below reads values).
    """
    removed = {}
    for name in list(os.environ.keys()):
        if name in _SAFE_VARS:
            continue
        if _CREDENTIAL_RE.search(name):
            removed[name] = os.environ.pop(name)
    return removed


def _restore_env(snapshot: dict) -> None:
    for name, value in snapshot.items():
        os.environ[name] = value
    _snapshot.clear()


def pytest_configure(config):  # noqa: ANN001
    """Scrub once at startup — before any test module collection result runs."""
    _snapshot.update(_scrub_credential_env())


def pytest_unconfigure(config):  # noqa: ANN001
    """Defensive: restore at shutdown for any external tooling reusing the env."""
    _restore_env(_snapshot)


@pytest.fixture(autouse=True)
def _no_credential_env_leak():  # noqa: ANN201
    """Per-test scrub; restores AFTER the test (values never inspected)."""
    snapshot = _scrub_credential_env()
    yield
    for name, value in snapshot.items():
        os.environ[name] = value