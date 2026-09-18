"""Tests for the monthly brand blacklist re-check task."""

import json

import pytest

from tasks.brand_blacklist_updater import (
    GATING_GATED,
    GATING_OPEN,
    GATING_UNKNOWN,
    RECHECK_GATE,
    BrandBlacklistUpdater,
    BrandGatingStatus,
    load_brand_policy,
    save_brand_policy,
)


@pytest.fixture()
def policy_file(tmp_path):
    path = tmp_path / "brand_policy.json"
    path.write_text(
        json.dumps({
            "schema_version": 1,
            "blacklist": ["Kirkland Signature"],
            "whitelist": [],
            "last_recheck": None,
        }),
        encoding="utf-8",
    )
    return path


def test_load_policy(policy_file):
    policy = load_brand_policy(policy_file)
    assert policy["blacklist"] == ["Kirkland Signature"]


def test_load_missing_policy_is_safe(tmp_path):
    policy = load_brand_policy(tmp_path / "nope.json")
    assert policy["blacklist"] == []


def test_load_corrupt_policy_is_safe(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{not json", encoding="utf-8")
    policy = load_brand_policy(p)
    assert policy["blacklist"] == []


def test_save_policy_atomic(policy_file):
    policy = load_brand_policy(policy_file)
    policy["whitelist"] = ["Acme"]
    assert save_brand_policy(policy, policy_file) is True
    assert load_brand_policy(policy_file)["whitelist"] == ["Acme"]


def test_offline_run_makes_no_live_call(policy_file, monkeypatch):
    monkeypatch.delenv(RECHECK_GATE, raising=False)
    calls = []

    def fake_check(brand):
        calls.append(brand)
        return BrandGatingStatus(brand=brand, status=GATING_UNKNOWN,
                                 evidence="offline stub")

    updater = BrandBlacklistUpdater(policy_path=policy_file, check_fn=fake_check)
    report = updater.run(live=False)
    assert report.live_armed is False
    assert [s.brand for s in report.per_brand] == ["Kirkland Signature"]
    assert report.still_blacklisted == ["Kirkland Signature"]


def test_offline_run_does_not_mutate_config(policy_file, monkeypatch):
    monkeypatch.delenv(RECHECK_GATE, raising=False)
    updater = BrandBlacklistUpdater(
        policy_path=policy_file,
        check_fn=lambda b: BrandGatingStatus(brand=b, status=GATING_GATED),
    )
    updater.run(live=False)
    assert load_brand_policy(policy_file)["last_recheck"] is None


def test_live_armed_requires_exact_gate(policy_file, monkeypatch):
    updater = BrandBlacklistUpdater(policy_path=policy_file)
    monkeypatch.setenv(RECHECK_GATE, "true")
    assert updater.live_armed() is False
    monkeypatch.setenv(RECHECK_GATE, "1")
    assert updater.live_armed() is True


def test_ungated_brand_surfaces_for_operator_review(policy_file, monkeypatch):
    monkeypatch.delenv(RECHECK_GATE, raising=False)

    def check(brand):
        return BrandGatingStatus(brand=brand, status=GATING_OPEN, changed=True,
                                 evidence="SP-API reports open")

    updater = BrandBlacklistUpdater(policy_path=policy_file, check_fn=check)
    report = updater.run(live=False)
    assert report.pending_operator_review
    assert report.pending_operator_review[0]["brand"] == "Kirkland Signature"
    # Never auto-removed from the blacklist.
    assert load_brand_policy(policy_file)["blacklist"] == ["Kirkland Signature"]


def test_live_run_persists_last_recheck(policy_file, monkeypatch):
    monkeypatch.setenv(RECHECK_GATE, "1")

    def check(brand):
        return BrandGatingStatus(brand=brand, status=GATING_GATED, evidence="still gated")

    updater = BrandBlacklistUpdater(policy_path=policy_file, check_fn=check)
    report = updater.run(live=True)
    assert report.live_armed is True
    saved = load_brand_policy(policy_file)
    assert saved["last_recheck"] is not None
    assert saved["last_recheck_run_id"] == report.run_id


def test_audit_trail_recorded(policy_file, monkeypatch):
    monkeypatch.delenv(RECHECK_GATE, raising=False)
    recorded = []
    updater = BrandBlacklistUpdater(
        policy_path=policy_file,
        check_fn=lambda b: BrandGatingStatus(brand=b, status=GATING_GATED),
        record_fn=recorded.append,
    )
    report = updater.run(live=False)
    assert len(report.audit_trail) == 1
    assert len(recorded) == 1
    assert recorded[0]["brand"] == "Kirkland Signature"


def test_report_as_dict(policy_file):
    updater = BrandBlacklistUpdater(
        policy_path=policy_file,
        check_fn=lambda b: BrandGatingStatus(brand=b, status=GATING_UNKNOWN),
    )
    d = updater.run(live=False).as_dict()
    assert d["live_armed"] is False
    assert "per_brand" in d and "audit_trail" in d
