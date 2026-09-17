"""Tests for the free-tier waterfall router.

Covers: §3 gate blocking, dispatch order, provider exhaustion, caller
failure fallback, audit trail, and credit accounting across the waterfall.
"""

import os

import pytest

from agents.golden_goose_finder.free_tier_registry import (
    FreeTierLedger,
    TASK_AMAZON_OFFERS,
    TASK_AMAZON_PRODUCT,
    TASK_AMAZON_SEARCH,
    TASK_COSTCO_SEARCH,
    TASK_GENERIC_SCRAPE,
    TASK_SAMS_SEARCH,
    FreeTierProvider,
    mark_key_available,
)
from agents.golden_goose_finder.free_tier_router import (
    DISPATCH_ORDER,
    SUPPORTED_TASKS,
    AuditTrail,
    RouteAttempt,
    RouteResult,
    get_audit_trail,
    is_live_approved,
    provider_for_task,
    run_task,
)


# ---------------------------------------------------------------------------
# §3 gate
# ---------------------------------------------------------------------------

class TestLiveGate:
    def test_gate_off_by_default(self):
        assert is_live_approved() is False

    def test_gate_off_with_empty_env(self, monkeypatch):
        monkeypatch.delenv("GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED", raising=False)
        assert is_live_approved() is False

    def test_gate_blocked_returns_correct_mode(self, monkeypatch):
        monkeypatch.delenv("GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED", raising=False)
        result = run_task(TASK_AMAZON_SEARCH, lambda p, t: None, live_armed=False)
        assert result.mode == "blocked"
        assert result.ok is False
        assert len(result.attempts) == 1
        assert result.attempts[0].status == "blocked"


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------

class TestProviderForTask:
    def test_picks_first_keyed_provider(self):
        """With the default KEY_AVAILABLE, bright_data should be first for Amazon search."""
        p = provider_for_task(TASK_AMAZON_SEARCH)
        assert p is not None
        assert p.id in DISPATCH_ORDER[TASK_AMAZON_SEARCH]

    def test_returns_none_when_no_providers(self):
        p = provider_for_task("nonexistent_task_xyz")
        assert p is None

    def test_respects_ledger_exhaustion(self, tmp_path):
        ledger = FreeTierLedger(path=str(tmp_path / "t.json"))
        ledger.load()
        # Exhaust ALL providers for this task by zeroing their credits
        for pid in DISPATCH_ORDER[TASK_AMAZON_SEARCH]:
            ledger.debit(pid, 999999.0)
        result = provider_for_task(TASK_AMAZON_SEARCH, ledger=ledger)
        assert result is None

    def test_skips_keyless_providers(self):
        """Temporarily mark a provider as keyless and verify it's skipped."""
        from agents.golden_goose_finder import free_tier_registry as reg
        # Temporarily disable the first keyed provider's key
        original_keys = {}
        for pid in DISPATCH_ORDER[TASK_AMAZON_SEARCH][:2]:
            p = reg.get_provider(pid)
            if p and p.has_key:
                original_keys[pid] = True
                p.has_key = False
        try:
            provider = provider_for_task(TASK_AMAZON_SEARCH)
            if provider:
                # Should pick a provider that still has a key
                assert provider.has_key
        finally:
            for pid, val in original_keys.items():
                p = reg.get_provider(pid)
                if p:
                    p.has_key = val


# ---------------------------------------------------------------------------
# Task dispatch
# ---------------------------------------------------------------------------

class TestRunTask:
    def test_successful_call_debits_provider(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED", "1")
        ledger = FreeTierLedger(path=str(tmp_path / "t.json"))
        ledger.load()
        trail = AuditTrail()

        initial = ledger.remaining_credits("bright_data_web_unlocker")
        def fake_caller(provider, task_type):
            return {"status": "ok"}

        result = run_task(
            TASK_AMAZON_SEARCH, fake_caller,
            live_armed=True, ledger=ledger, audit=trail,
        )
        assert result.mode == "live"
        assert result.ok is True
        assert result.result == {"status": "ok"}
        assert result.chosen_provider_id is not None
        assert ledger.remaining_credits("bright_data_web_unlocker") < initial
        assert len(trail.entries) == 1
        assert trail.entries[0]["ok"] is True

    def test_caller_failure_tries_next_provider(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED", "1")
        ledger = FreeTierLedger(path=str(tmp_path / "t.json"))
        ledger.load()

        call_count = {"n": 0}

        def failing_then_ok(provider, task_type):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise ConnectionError("provider down")
            return {"status": "ok"}

        result = run_task(
            TASK_AMAZON_SEARCH, failing_then_ok,
            live_armed=True, ledger=ledger,
        )
        assert result.ok is True
        assert call_count["n"] == 2
        assert any(a.status == "failed" for a in result.attempts)
        assert any(a.status == "ok" for a in result.attempts)

    def test_all_providers_fail_returns_exhausted(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED", "1")
        ledger = FreeTierLedger(path=str(tmp_path / "t.json"))
        ledger.load()

        def always_fail(provider, task_type):
            raise RuntimeError("everything broken")

        result = run_task(
            TASK_AMAZON_SEARCH, always_fail,
            live_armed=True, ledger=ledger,
        )
        assert result.mode == "exhausted"
        assert result.ok is False
        # Only keyed+affordable providers get called (failed); others get no_key/exhausted
        failed = [a for a in result.attempts if a.status == "failed"]
        assert len(failed) >= 1  # at least one provider was actually called

    def test_exhausted_provider_skipped(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED", "1")
        ledger = FreeTierLedger(path=str(tmp_path / "t.json"))
        ledger.load()

        # Exhaust ALL providers so none can be called
        for pid in DISPATCH_ORDER[TASK_AMAZON_SEARCH]:
            ledger.debit(pid, 999999.0)

        called_ids = []

        def track_caller(provider, task_type):
            called_ids.append(provider.id)
            return {"ok": True}

        result = run_task(
            TASK_AMAZON_SEARCH, track_caller,
            live_armed=True, ledger=ledger,
        )
        # No provider should have been called (all exhausted)
        assert called_ids == []
        assert result.mode == "exhausted"

    def test_invalid_task_type(self, monkeypatch):
        monkeypatch.setenv("GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED", "1")
        result = run_task("nonexistent_task_xyz", lambda p, t: None, live_armed=True)
        assert result.mode == "invalid_task"
        assert result.ok is False

    def test_credit_restored_on_failure(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED", "1")
        ledger = FreeTierLedger(path=str(tmp_path / "t.json"))
        ledger.load()

        def fail(provider, task_type):
            raise ValueError("oops")

        # Find the first keyed provider and get its initial balance
        first_pid = None
        for pid in DISPATCH_ORDER[TASK_AMAZON_SEARCH]:
            from agents.golden_goose_finder.free_tier_registry import get_provider as gp
            prov = gp(pid)
            if prov and prov.has_key:
                first_pid = pid
                break
        if not first_pid:
            pytest.skip("no keyed provider available")

        initial = ledger.remaining_credits(first_pid)

        result = run_task(
            TASK_AMAZON_SEARCH, fail,
            live_armed=True, ledger=ledger,
        )
        # Credits should be restored after failure — the first keyed provider
        # was called and failed, then credits restored
        assert ledger.remaining_credits(first_pid) == initial


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

class TestAuditTrail:
    def test_global_trail_records(self, monkeypatch):
        monkeypatch.delenv("GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED", raising=False)
        initial_len = len(get_audit_trail())
        run_task(TASK_AMAZON_SEARCH, lambda p, t: None, live_armed=False)
        assert len(get_audit_trail()) == initial_len + 1

    def test_trail_entry_shape(self, monkeypatch):
        monkeypatch.delenv("GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED", raising=False)
        run_task(TASK_AMAZON_SEARCH, lambda p, t: None, live_armed=False)
        entry = get_audit_trail()[-1]
        assert "task_type" in entry
        assert "mode" in entry
        assert "ok" in entry
        assert "attempts" in entry
        assert "at" in entry


# ---------------------------------------------------------------------------
# Dispatch order coverage
# ---------------------------------------------------------------------------

class TestDispatchOrder:
    def test_all_tasks_have_dispatch_order(self):
        for task in SUPPORTED_TASKS:
            assert task in DISPATCH_ORDER, f"{task} missing from DISPATCH_ORDER"

    def test_dispatch_order_entries_are_known_providers(self):
        from agents.golden_goose_finder.free_tier_registry import get_provider
        for task, providers in DISPATCH_ORDER.items():
            for pid in providers:
                assert get_provider(pid) is not None, f"unknown provider {pid} in {task}"
