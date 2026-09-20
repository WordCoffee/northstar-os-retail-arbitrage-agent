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
    confirm_continue,
    diff_reports,
    generate_cli_docs,
    needs_lazy_enrichment,
    read_stream,
    resolve_profile,
    rollback_plan,
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