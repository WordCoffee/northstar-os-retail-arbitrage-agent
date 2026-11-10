"""P4-T4 freshness policy tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from Northstar_backend.foundation import freshness as fr


def _ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def test_fresh_is_observed_and_usable():
    r = fr.evaluate(_ago(1), "price")
    assert r["state"] == fr.OBSERVED and r["usable_for_gates"] is True
    assert fr.gate_state(_ago(1), "price") == fr.OBSERVED


def test_stale_is_cached_with_age_and_not_usable_for_gates():
    r = fr.evaluate(_ago(30), "price")  # price max age 7
    assert r["state"] == fr.CACHED
    assert r["label"] == fr.CACHED
    assert r["usable_for_gates"] is False
    assert r["age_days"] > 7 and r["max_age_days"] == 7
    assert fr.gate_state(_ago(30), "price") == fr.UNKNOWN


def test_missing_or_unparseable_is_unknown():
    for bad in (None, "", "not-a-date"):
        r = fr.evaluate(bad, "price")
        assert r["state"] == fr.UNKNOWN and r["usable_for_gates"] is False
        assert fr.gate_state(bad, "price") == fr.UNKNOWN


def test_per_field_max_age_differs():
    # 30 days old: stale for price (7) but fresh for pack (90)
    assert fr.evaluate(_ago(30), "price")["state"] == fr.CACHED
    assert fr.evaluate(_ago(30), "pack")["state"] == fr.OBSERVED
    assert fr.max_age_days("pack") == 90 and fr.max_age_days("price") == 7


def test_env_override(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_MAX_AGE_PRICE_DAYS", "60")
    assert fr.max_age_days("price") == 60
    assert fr.evaluate(_ago(30), "price")["state"] == fr.OBSERVED
    monkeypatch.setenv("NORTHSTAR_MAX_AGE_PRICE_DAYS", "notint")
    assert fr.max_age_days("price") == 7  # bad value falls back to default


def test_unknown_field_uses_default():
    assert fr.max_age_days("some_unlisted_field") == fr.DEFAULT_MAX_AGE_DAYS["default"]


def test_future_timestamp_is_unknown():
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    assert fr.evaluate(future, "price")["state"] == fr.UNKNOWN