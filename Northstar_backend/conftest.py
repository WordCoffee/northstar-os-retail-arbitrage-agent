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

import glob
import os
import re

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))

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

# Test suites intentionally set credential-NAMED vars to placeholder values so
# their OFFLINE rehearsals run (provider_seller_probe uses "DUMMY"; the
# full-pull rehearsal uses "test-key-*"). Only non-placeholder values are
# treated as real secrets and scrubbed.
def _is_placeholder_value(value: str) -> bool:
    if not value:
        return True
    if value == "DUMMY":
        return True
    if value.startswith("test-key-") or value.startswith("test-"):
        return True
    return False


def _is_credential(name: str, value: str) -> bool:
    return name not in _SAFE_VARS and bool(_CREDENTIAL_RE.search(name)) and not _is_placeholder_value(value)


_snapshot: dict = {}


def _scrub_credential_env() -> dict:
    """Remove real credential values from os.environ.

    Returns a snapshot {name: value} so tests can restore them afterward
    (restoration is only for consistency — nothing below reads values).
    """
    removed = {}
    for name in list(os.environ.keys()):
        if _is_credential(name, os.environ[name]):
            removed[name] = os.environ.pop(name)
    return removed


def _restore_env(snapshot: dict) -> None:
    for name, value in snapshot.items():
        os.environ[name] = value
    _snapshot.clear()


def pytest_configure(config):  # noqa: ANN001
    """Scrub once at startup — before any test module collection result runs."""
    # Match the official runner (scripts/run_all_tests.ps1): one pytest session
    # shares a single client identity across hundreds of TestClient requests,
    # so the anonymous token bucket (30 req/min) would 429 later tests and make
    # the suite order-dependent. Limiter tests exercise the middleware directly,
    # so no coverage is lost. Never honored in prod-like environments.
    os.environ.setdefault("NORTHSTAR_DISABLE_RATE_LIMIT", "1")
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


# --- generated-artifact isolation (F remediation) ---------------------------
# The scanner cache is a GENERATED artifact. Some offline tests legitimately
# regenerate it (and some CLI mains mutate SCANNER_SEARCH_CACHE_PATH globally),
# which left the committed file dirty and made the byte-identity guard in
# test_proof_batch_run.py order-dependent. Snapshot the committed bytes at
# session start and restore after every test so the guard is deterministic.
# Source-file guards (finance.py, fee_engine.py, …) remain strict — only the
# generated scanner-cache set is restored.
_GENERATED_ARTIFACT_GLOBS = [
    os.path.join(_HERE, "data", "scanner-search-cache*.json"),
]
_generated_snapshot: dict = {}


def pytest_sessionstart(session):  # noqa: ANN001
    for pattern in _GENERATED_ARTIFACT_GLOBS:
        for path in glob.glob(pattern):
            try:
                with open(path, "rb") as fh:
                    _generated_snapshot[path] = fh.read()
            except OSError:
                continue


def _restore_generated() -> None:
    for path, data in _generated_snapshot.items():
        try:
            current = None
            if os.path.exists(path):
                with open(path, "rb") as fh:
                    current = fh.read()
            if current != data:
                with open(path, "wb") as fh:
                    fh.write(data)
        except OSError:
            continue


def pytest_collection_finish(session):  # noqa: ANN001
    """After collection: scrub credentials AND restore generated artifacts.

    This hook used to be defined twice - once for the credential scrub and once
    for the generated-cache restore - so the second definition silently replaced
    the first and the post-collection credential scrub never ran. One hook, both
    jobs, in the order that leaves no secret in the environment for a test body.
    """
    _snapshot.update(_scrub_credential_env())
    _restore_generated()


@pytest.fixture(autouse=True)
def _restore_generated_artifacts():  # noqa: ANN201
    """Restore the generated scanner cache to its committed bytes after each test."""
    yield
    _restore_generated()