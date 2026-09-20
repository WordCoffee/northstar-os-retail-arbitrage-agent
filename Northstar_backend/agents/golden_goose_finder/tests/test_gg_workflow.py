"""Phase F/S11d — workflow toolkit tests (offline)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from agents.golden_goose_finder.gg_workflow import (  # noqa: E402
    PROFILE_DEFAULTS,
    AnnotationStore,
    SchedulerStub,
    TTLCache,
    compose_tier_alert,
    confirm_continue,
    cron_next_minute,
    diff_reports,
    generate_cli_docs,
    needs_lazy_enrichment,
    read_stream,
    resolve_profile,
    rollback_plan,
    tier_regressions,
    validate_cron,
    webhook_notify,
    write_rows_streaming,
)


def test_ttl_cache() -> None:
    cache = TTLCache(ttl_seconds=1.0)
    assert cache.get("k") is None
    cache.set("k", {"asin": "B0X"})
    assert cache.get("k")["asin"] == "B0X"
    # expired after ttl (time is frozen by monkeypatch below in next tests;
    # here we just force expiry by manipulating internal timestamp)
    from unittest import mock
    with mock.patch("agents.golden_goose_finder.gg_workflow.time.time") as t:
        t.return_value = 10.0
        cache2 = TTLCache(ttl_seconds=1.0)
        cache2.set("k", 1)
        t.return_value = 12.0   # +2s > ttl
        assert cache2.get("k") is None


# --- FIXES_50 #7 scan-timeout budget (Phase G) ---

def test_scan_budget_clock_injected_expiry():
    from agents.golden_goose_finder.gg_workflow import ScanBudget
    b = ScanBudget(timeout_seconds=300, started_at=1000.0)
    assert b.deadline == pytest.approx(1300.0)
    assert b.expired(now=1299.0) is False
    assert b.expired(now=1300.0) is True
    assert b.remaining(now=1250.0) == pytest.approx(50.0)
    assert b.remaining(now=1400.0) == pytest.approx(0.0)   # clamp at 0


def test_scan_budget_checkpoint():
    from agents.golden_goose_finder.gg_workflow import ScanBudget
    b = ScanBudget(timeout_seconds=60, started_at=1000.0)
    c = b.checkpoint(now=1010.0)
    assert c["complete"] is True and c["remaining_seconds"] == pytest.approx(50.0)
    assert b.checkpoint(now=1100.0)["complete"] is False


def test_lazy_enrichment_selector() -> None:
    assert needs_lazy_enrichment({"net_profit_per_unit": 12.5}) is True
    assert needs_lazy_enrichment({"net_profit_per_unit": -3}) is False
    assert needs_lazy_enrichment({"net_profit_per_unit": None}) is False
    assert needs_lazy_enrichment({}) is False


def test_streaming_writes_and_read(tmp_path) -> None:
    p = tmp_path / "report.jsonl"
    rows = [{"asin": "B0A", "tier": "HIGH"}, {"asin": "B0B", "tier": "LOW"}]
    assert write_rows_streaming(p, rows, chunk=1) == 2
    got = list(read_stream(p))
    assert got[0]["asin"] == "B0A" and got[1]["tier"] == "LOW"
    assert list(read_stream(tmp_path / "missing.jsonl")) == []


def test_diff_reports() -> None:
    prev = [{"amazon_asin": "B1", "tier": "HIGH"}, {"amazon_asin": "B2", "tier": "LOW"}]
    curr = [{"amazon_asin": "B2", "tier": "HIGH"}, {"amazon_asin": "B3", "tier": "MED"}]
    d = diff_reports(prev, curr)
    assert d["added"] == ["B3"]
    assert d["dropped"] == ["B1"]
    assert d["tier_changed"] == ["B2"]


# --- FIXES_50 #25 tier-regression alerts (Phase G) ---

def test_tier_regressions_detects_drops() -> None:
    prev = [{"asin": "B1", "tier": "HIGH"}, {"asin": "B2", "tier": "MEDIUM"}]
    curr = [{"asin": "B1", "tier": "LOW"}, {"asin": "B2", "tier": "REJECT"}]
    regs = tier_regressions(prev, curr)
    assert [(r["asin"], r["previous_tier"], r["current_tier"]) for r in regs] == [
        ("B1", "HIGH", "LOW"), ("B2", "MEDIUM", "REJECT"),
    ]


def test_tier_regressions_ignore_improvements_and_flat() -> None:
    prev = [{"asin": "B1", "tier": "LOW"}, {"asin": "B2", "tier": "HIGH"}, {"asin": "B3", "tier": "MEDIUM"}]
    curr = [{"asin": "B1", "tier": "HIGH"}, {"asin": "B2", "tier": "HIGH"}, {"asin": "B3", "tier": "MEDIUM"}]
    assert tier_regressions(prev, curr) == []


def test_tier_regressions_absent_not_counted() -> None:
    prev = [{"asin": "B1", "tier": "HIGH"}, {"asin": "B2", "tier": "LOW"}]
    curr = [{"asin": "B1", "tier": "LOW"}]           # B2 dropped out entirely
    assert [r["asin"] for r in tier_regressions(prev, curr)] == ["B1"]


def test_compose_tier_alert_no_send() -> None:
    regs = [{"asin": "B0X", "previous_tier": "HIGH", "current_tier": "LOW", "dropped": True}]
    a = compose_tier_alert(regs)
    assert a["code"] == "tier_regression" and a["severity"] == "warning"
    assert a["channel"] is None
    assert compose_tier_alert([])["code"] == "ok"


def test_resolve_profile() -> None:
    assert resolve_profile("conservative")["roi_floor"] == 30.0
    assert resolve_profile("aggressive")["min_monthly_sales"] == 400
    assert resolve_profile(None)["roi_floor"] == PROFILE_DEFAULTS["default"]["roi_floor"]
    assert resolve_profile("aggressive", roi_floor=20.0)["roi_floor"] == 20.0
    # unknown profile falls back to default
    assert resolve_profile("nope")["roi_floor"] == PROFILE_DEFAULTS["default"]["roi_floor"]


def test_confirm_continue_non_tty_default(monkeypatch) -> None:
    import sys
    class FakeStdin:
        def isatty(self) -> bool:
            return False
    monkeypatch.setattr(sys, "stdin", FakeStdin())
    assert confirm_continue("proceed?", default=True) is True
    assert confirm_continue("proceed?", default=False) is False


def test_scheduler_stub() -> None:
    s = SchedulerStub()
    s.schedule("weekly-scan", "0 6 * * 1")
    s.schedule("daily-enrich", "0 */2 * * *")
    assert len(s.jobs_list()) == 2 and s.jobs_list()[0]["cron"] == "0 6 * * 1"


# --- FIXES_50 #45 cron validator + next-fire dry-run (Phase G) ---

def test_validate_cron() -> None:
    assert validate_cron("0 6 * * 1") is True
    assert validate_cron("*/15 * * * *") is True
    assert validate_cron("30 6 * * 1-5") is True
    assert validate_cron("0 6 * * 7") is True          # 7 = Sunday alias
    assert validate_cron("0 6 * *") is False           # 4 fields
    assert validate_cron("61 * * * *") is False        # bad minute
    assert validate_cron("a * * * *") is False
    assert validate_cron("") is False


def test_cron_next_minute_step() -> None:
    from datetime import datetime, timezone
    base = int(datetime(2026, 9, 20, 10, 7, tzinfo=timezone.utc).timestamp())
    nxt = cron_next_minute("*/15 * * * *", base)
    expected = int(datetime(2026, 9, 20, 10, 15, tzinfo=timezone.utc).timestamp())
    assert nxt == expected


def test_cron_next_minute_weekly() -> None:
    from datetime import datetime, timezone
    sunday = int(datetime(2026, 9, 20, 18, 0, tzinfo=timezone.utc).timestamp())
    nxt = cron_next_minute("0 6 * * 1", sunday)        # Monday 06:00 UTC
    expected = int(datetime(2026, 9, 21, 6, 0, tzinfo=timezone.utc).timestamp())
    assert nxt == expected


def test_cron_next_minute_none_for_invalid() -> None:
    assert cron_next_minute("nope", 1000.0) is None


def test_scheduler_dry_run_validates_without_executing() -> None:
    from datetime import datetime, timezone
    s = SchedulerStub()
    s.schedule("weekly-scan", "0 6 * * 1")
    s.schedule("broken", "99 99 99 99 99")
    base = int(datetime(2026, 9, 20, 18, 0, tzinfo=timezone.utc).timestamp())
    out = s.dry_run(now=base)
    by_name = {r["name"]: r for r in out}
    assert by_name["weekly-scan"]["valid"] is True and by_name["weekly-scan"]["next_fire_epoch"] is not None
    assert by_name["broken"]["valid"] is False and "next_fire_epoch" not in by_name["broken"]


def test_webhook_stubbed_never_sends(caplog) -> None:
    import logging
    with caplog.at_level(logging.INFO, logger="northstar.webhook"):
        out = webhook_notify("https://example.invalid/hook", {"event": "scan_done"})
    assert out["status"] == "stubbed"
    assert "stubbed" in caplog.text


def test_annotation_store(tmp_path) -> None:
    store = AnnotationStore(tmp_path / "ann.json")
    store.tag("B0X", "suspect seller")
    store.tag("B0X", "confirmed")
    reloaded = AnnotationStore(tmp_path / "ann.json")
    assert len(reloaded.all()) == 2 and reloaded.all()[1]["note"] == "confirmed"


def test_rollback_plan() -> None:
    plan = rollback_plan(["run1", "run2", "run3"], "run1")
    assert plan["ok"] is True and plan["would_remove"] == ["run2", "run3"]
    assert rollback_plan(["run1"], "run1")["would_remove"] == []
    bad = rollback_plan(["run1", "run2"], "runX")
    assert bad["ok"] is False and bad["would_remove"] == []


def test_cli_docs_generation() -> None:
    doc = generate_cli_docs("golden-goose", [
        ("--dry-run", "Do not collect data"),
        ("--categories", "Costco categories | comma separated"),
    ])
    assert "# golden-goose — reference" in doc
    assert "| `--dry-run` | Do not collect data |" in doc
    assert "comma separated" in doc