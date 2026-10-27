"""Tests for Chrome Connect health, evidence, and alerts (Phase 5)."""

from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chromeconnect_health as health


# ---------------------------------------------------------------------------
# AdapterHealth tests
# ---------------------------------------------------------------------------

def test_adapter_health_initial_state():
    ah = health.AdapterHealth(name="test", origin="example.com")
    assert ah.state == health.HealthState.UNKNOWN
    assert ah.success_count == 0
    assert ah.failure_count == 0


def test_record_success():
    ah = health.AdapterHealth(name="test", origin="example.com")
    ah.record_success(1.5)
    assert ah.state == health.HealthState.GREEN
    assert ah.success_count == 1
    assert ah.consecutive_failures == 0
    assert ah.last_success is not None
    assert ah.avg_time_s == 1.5


def test_record_failure():
    ah = health.AdapterHealth(name="test", origin="example.com")
    ah.record_failure("selector miss")
    assert ah.state == health.HealthState.DEGRADED
    assert ah.failure_count == 1
    assert ah.consecutive_failures == 1
    assert ah.degraded_reason == "selector miss"


def test_three_failures_marks_red():
    ah = health.AdapterHealth(name="test", origin="example.com")
    for i in range(3):
        ah.record_failure(f"fail {i}")
    assert ah.state == health.HealthState.RED
    assert ah.consecutive_failures == 3


def test_success_resets_consecutive_failures():
    ah = health.AdapterHealth(name="test", origin="example.com")
    ah.record_failure("fail 1")
    ah.record_failure("fail 2")
    assert ah.consecutive_failures == 2
    ah.record_success(1.0)
    assert ah.consecutive_failures == 0
    assert ah.state == health.HealthState.GREEN


def test_record_degraded():
    ah = health.AdapterHealth(name="test", origin="example.com")
    ah.record_degraded("layout changed")
    assert ah.state == health.HealthState.DEGRADED
    assert ah.degraded_reason == "layout changed"


def test_to_dict():
    ah = health.AdapterHealth(name="test", origin="example.com")
    ah.record_success(2.0)
    d = ah.to_dict()
    assert d["name"] == "test"
    assert d["state"] == "green"
    assert d["success_count"] == 1


# ---------------------------------------------------------------------------
# EvidenceRecord tests
# ---------------------------------------------------------------------------

def test_make_evidence_ok():
    ev = health.make_evidence("title", "My Title", "https://example.com", confidence=0.9)
    assert ev.status == "OK"
    assert ev.value == "My Title"
    assert ev.confidence == 0.9
    assert ev.field_name == "title"


def test_make_evidence_unknown():
    ev = health.make_evidence("price", None, "https://example.com")
    assert ev.status == "UNKNOWN"
    assert ev.value is None


def test_evidence_to_dict():
    ev = health.make_evidence("title", "Test", "https://example.com")
    d = ev.to_dict()
    assert "field_name" in d
    assert "source_url" in d
    assert "observed_at" in d
    assert "selector_version" in d


# ---------------------------------------------------------------------------
# AlertManager tests
# ---------------------------------------------------------------------------

def test_alert_add():
    am = health.AlertManager()
    alert = am.add("warning", "adapter_degraded", "Adapter X degraded")
    assert alert.severity == "warning"
    assert alert.category == "adapter_degraded"
    assert not alert.acknowledged


def test_alert_unacknowledged():
    am = health.AlertManager()
    am.add("info", "test", "info msg")
    am.add("error", "test", "error msg")
    unacked = am.unacknowledged()
    assert len(unacked) == 2
    unacked_err = am.unacknowledged(min_severity="error")
    assert len(unacked_err) == 1


def test_alert_acknowledge():
    am = health.AlertManager()
    am.add("warning", "test", "msg")
    assert am.acknowledge(0) is True
    assert len(am.unacknowledged()) == 0
    assert am.acknowledge(99) is False


def test_alert_acknowledge_all():
    am = health.AlertManager()
    am.add("info", "test", "msg1")
    am.add("error", "test", "msg2")
    count = am.acknowledge_all()
    assert count == 2
    assert len(am.unacknowledged()) == 0


def test_alert_count_by_severity():
    am = health.AlertManager()
    am.add("info", "test", "msg1")
    am.add("error", "test", "msg2")
    am.add("error", "test", "msg3")
    counts = am.count_by_severity()
    assert counts["info"] == 1
    assert counts["error"] == 2
    assert counts["warning"] == 0


# ---------------------------------------------------------------------------
# HealthRegistry tests
# ---------------------------------------------------------------------------

def test_registry_register():
    reg = health.HealthRegistry()
    ah = reg.register("costco", "costco.com")
    assert ah.name == "costco"
    assert ah.state == health.HealthState.UNKNOWN
    assert reg.get("costco") is ah


def test_registry_record_success():
    reg = health.HealthRegistry()
    reg.register("costco", "costco.com")
    reg.record_success("costco", 2.0)
    ah = reg.get("costco")
    assert ah.state == health.HealthState.GREEN
    assert ah.success_count == 1


def test_registry_record_failure():
    reg = health.HealthRegistry()
    reg.register("costco", "costco.com")
    reg.record_failure("costco", "selector miss")
    ah = reg.get("costco")
    assert ah.state == health.HealthState.DEGRADED
    # Alert should be created
    assert len(reg.alerts.unacknowledged()) == 1


def test_registry_record_degraded():
    reg = health.HealthRegistry()
    reg.register("costco", "costco.com")
    reg.record_degraded("costco", "layout changed")
    ah = reg.get("costco")
    assert ah.state == health.HealthState.DEGRADED
    assert ah.degraded_reason == "layout changed"


def test_registry_degraded_adapters():
    reg = health.HealthRegistry()
    reg.register("a", "a.com")
    reg.register("b", "b.com")
    reg.record_success("a", 1.0)
    reg.record_failure("b", "fail")
    degraded = reg.degraded_adapters()
    assert "b" in degraded
    assert "a" not in degraded


def test_registry_summary():
    reg = health.HealthRegistry()
    reg.register("a", "a.com")
    reg.register("b", "b.com")
    reg.record_success("a", 1.0)
    reg.record_failure("b", "fail")
    s = reg.summary()
    assert s["total_adapters"] == 2
    assert s["green"] == 1
    assert s["degraded"] == 1


def test_registry_all_health():
    reg = health.HealthRegistry()
    reg.register("a", "a.com")
    reg.register("b", "b.com")
    health_list = reg.all_health()
    assert len(health_list) == 2
    assert all("name" in h and "state" in h for h in health_list)


# ---------------------------------------------------------------------------
# QA viewport tests
# ---------------------------------------------------------------------------

def test_qa_viewports():
    assert len(health.QA_VIEWPORTS) == 3
    labels = [v.label for v in health.QA_VIEWPORTS]
    assert "mobile" in labels
    assert "tablet" in labels
    assert "desktop" in labels


def test_run_qa_check():
    results = health.run_qa_check("https://example.com")
    assert len(results) == 3
    for r in results:
        assert r.url == "https://example.com"
        assert r.passed is True
        assert r.console_errors == []
        assert r.network_errors == []


def test_qa_result_to_dict():
    r = health.QAResult(url="https://example.com", viewport="mobile", width=390, height=844)
    d = r.to_dict()
    assert d["url"] == "https://example.com"
    assert d["width"] == 390


# ---------------------------------------------------------------------------
# Dashboard tests
# ---------------------------------------------------------------------------

def test_dashboard_data():
    reg = health.HealthRegistry()
    reg.register("costco", "costco.com")
    reg.record_success("costco", 2.0)
    data = health.dashboard_data(reg)
    assert "health" in data
    assert "adapters" in data
    assert "degraded" in data
    assert "alerts" in data
    assert "qa_viewports" in data
    assert len(data["qa_viewports"]) == 3
