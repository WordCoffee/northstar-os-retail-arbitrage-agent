"""B1 tests — two-gate authorization for a live Golden Goose scan.

Proves:
  - gate OFF (either/both missing) blocks the call;
  - gate ON (both set, fixture-only) permits the code path with a fake
    pipeline and ZERO network calls;
  - run_live_scan.py never self-arms (no in-process env mutation; source guard).

Run: python -m pytest agents/golden_goose_finder/tests/test_live_scan_gate.py -q
"""

from __future__ import annotations

import asyncio
import inspect
import os
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from agents.golden_goose_finder import run_live_scan as rls  # noqa: E402
from agents.golden_goose_finder import live_scan_gate as gate  # noqa: E402
from agents.golden_goose_finder.live_scan_gate import (  # noqa: E402
    LIVE_AUTH_PHRASE,
    LIVE_AUTH_PHRASE_ENV,
    LIVE_OPERATOR_ENV,
    check_live_scan_gates,
    gate_status,
)


_BOTH = {LIVE_OPERATOR_ENV: "1", LIVE_AUTH_PHRASE_ENV: LIVE_AUTH_PHRASE}


# =========================================================================
# check_live_scan_gates — default-off matrix
# =========================================================================

class TestGateMatrix:

    def test_both_absent_refused(self):
        ok, reason = check_live_scan_gates({})
        assert ok is False and "refused" in reason

    def test_operator_only_refused(self):
        ok, _ = check_live_scan_gates({LIVE_OPERATOR_ENV: "1"})
        assert ok is False

    def test_phrase_only_refused(self):
        ok, _ = check_live_scan_gates({LIVE_AUTH_PHRASE_ENV: LIVE_AUTH_PHRASE})
        assert ok is False

    def test_wrong_phrase_refused(self):
        ok, reason = check_live_scan_gates({LIVE_OPERATOR_ENV: "1", LIVE_AUTH_PHRASE_ENV: "nope"})
        assert ok is False
        assert "authorization phrase" in reason

    def test_operator_not_one_refused(self):
        ok, _ = check_live_scan_gates({LIVE_OPERATOR_ENV: "true", LIVE_AUTH_PHRASE_ENV: LIVE_AUTH_PHRASE})
        assert ok is False

    def test_phrase_is_whitespace_trimmed(self):
        ok, _ = check_live_scan_gates({LIVE_OPERATOR_ENV: "1", LIVE_AUTH_PHRASE_ENV: "  " + LIVE_AUTH_PHRASE + "  "})
        assert ok is True

    def test_both_correct_authorized(self):
        ok, reason = check_live_scan_gates(_BOTH)
        assert ok is True and reason == "authorized"

    def test_gate_status_view(self):
        st = gate_status(_BOTH)
        assert st == {"operator_approved": True, "auth_phrase_set": True}
        assert gate_status({}) == {"operator_approved": False, "auth_phrase_set": False}


# =========================================================================
# run() — refusals make ZERO pipeline calls
# =========================================================================

class TestRunRefusals:

    def _spy(self):
        calls = {"n": 0}

        async def fake_pipeline(**kwargs):
            calls["n"] += 1
            return {"summary": {}, "opportunities": [], "meta": {}}

        return fake_pipeline, calls

    def test_gates_off_raises_and_never_calls_pipeline(self, capsys):
        fake, calls = self._spy()
        with pytest.raises(rls.LiveScanRefused):
            asyncio.run(rls.run(pipeline=fake, env={}, save=False))
        assert calls["n"] == 0

    def test_operator_only_raises(self):
        fake, calls = self._spy()
        with pytest.raises(rls.LiveScanRefused):
            asyncio.run(rls.run(pipeline=fake, env={LIVE_OPERATOR_ENV: "1"}, save=False))
        assert calls["n"] == 0

    def test_wrong_phrase_raises(self):
        fake, calls = self._spy()
        with pytest.raises(rls.LiveScanRefused):
            asyncio.run(rls.run(pipeline=fake,
                                env={LIVE_OPERATOR_ENV: "1", LIVE_AUTH_PHRASE_ENV: "bad"}, save=False))
        assert calls["n"] == 0


# =========================================================================
# run() — authorized path with a fixture pipeline (no network)
# =========================================================================

class TestRunAuthorizedFixture:

    def test_both_gates_permit_path_no_network(self, capsys):
        calls = {"n": 0}

        async def fake_pipeline(**kwargs):
            calls["n"] += 1
            # Assert the live (non-mock) path was requested.
            assert kwargs.get("use_mock") is False
            return {
                "summary": {"total_opportunities": 2, "high_tier_count": 1},
                "opportunities": [
                    {"rank": 1, "brand": "Kirkland", "product_title": "Fixture A",
                     "net_profit_per_unit": 12.5, "roi_per_unit": 63.0, "composite_score": 88.0},
                ],
                "meta": {"elapsed_seconds": 0.01},
            }

        report = asyncio.run(rls.run(pipeline=fake_pipeline, env=_BOTH, save=False))
        assert calls["n"] == 1                      # authorized -> pipeline reaches the path
        assert report["summary"]["total_opportunities"] == 2
        out = capsys.readouterr().out
        assert "operator-authorized" in out

    def test_cli_main_refuses_when_gates_unset(self, monkeypatch, capsys):
        monkeypatch.delenv(LIVE_OPERATOR_ENV, raising=False)
        monkeypatch.delenv(LIVE_AUTH_PHRASE_ENV, raising=False)
        rc = rls.main()
        assert rc == 2
        out = capsys.readouterr().out
        assert "never arms itself" in out


# =========================================================================
# Never self-armed invariant
# =========================================================================

class TestNeverSelfArmed:

    def test_module_source_has_no_env_assignment(self):
        src = inspect.getsource(rls)
        # No `os.environ[...] = ...` anywhere in run_live_scan.py.
        assert "os.environ[" not in src, "run_live_scan.py must not mutate the environment"

    def test_import_does_not_set_gate_env(self, monkeypatch):
        monkeypatch.delenv(LIVE_OPERATOR_ENV, raising=False)
        monkeypatch.delenv(LIVE_AUTH_PHRASE_ENV, raising=False)
        import importlib
        importlib.reload(rls)
        assert os.environ.get(LIVE_OPERATOR_ENV) is None
        assert os.environ.get(LIVE_AUTH_PHRASE_ENV) is None

    def test_gate_module_is_read_only(self):
        src = inspect.getsource(gate)
        assert "os.environ[" not in src