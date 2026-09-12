"""Tests for the Master Brain Subscriber Registry (plan catalog + entitlements).

Offline unit tests. No network, no credentials, no paid calls.
Run: python -m pytest Northstar_backend/test_master_brain_subscribers.py -q
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import master_brain_subscribers as subs  # noqa: E402

CATALOG = subs.load_plans()
PLAN_IDS = {p["id"] for p in CATALOG["plans"]}
ALL_GATES = set(subs.LIVE_GATES)


# ---------- catalog ----------

def test_catalog_loads_four_plans():
    assert len(CATALOG["plans"]) == 4


def test_gates_always_off_invariant_asserted_by_loader():
    # A catalog that drops the invariant flag must fail closed.
    import tempfile

    bad = dict(CATALOG)
    bad["gates_always_off"] = False
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(bad, fh)
        tmp = fh.name
    try:
        with pytest.raises(ValueError):
            subs.load_plans(tmp)
    finally:
        os.unlink(tmp)


def test_list_plans_catalog_order():
    assert subs.list_plans() == ["foundation", "scout", "mover", "autothink"]


def test_get_plan_foundation_is_free_with_no_gates():
    plan = subs.get_plan("foundation")
    assert plan["price_usd_month"] == 0
    assert plan["tier"] == 1
    assert plan["entitled_gates"] == []


def test_get_plan_autothink_is_tier2_premium():
    plan = subs.get_plan("autothink")
    assert plan["tier"] == 2
    assert plan["price_usd_month"] == 149
    assert "autothink" in plan["services"]


def test_get_plan_unknown_fails_closed():
    with pytest.raises(KeyError):
        subs.get_plan("nope_plan")


# ---------- entitlements ----------

def test_entitled_gates_are_subset_of_canonical_gates():
    for pid in PLAN_IDS:
        assert set(subs.entitled_gates(pid)) <= ALL_GATES


def test_entitled_gates_progression():
    # scout < mover < autothink, strictly
    scout = set(subs.entitled_gates("scout"))
    mover = set(subs.entitled_gates("mover"))
    autothink = set(subs.entitled_gates("autothink"))
    assert scout < mover < autothink
    assert autothink == ALL_GATES


def test_entitled_gates_unknown_plan_fails_closed():
    with pytest.raises(KeyError):
        subs.entitled_gates("nope_plan")


# ---------- profile binding ----------

def test_plan_for_profile_t2_resolves_autothink():
    plan = subs.plan_for_profile("t2-holdings-tyrone-johnson")
    assert plan["id"] == "autothink"
    assert plan["name"] == "AutothinK"


def test_plan_for_profile_unknown_profile_fails_closed():
    with pytest.raises(KeyError):
        subs.plan_for_profile("nobody-real")


# ---------- snapshot ----------

def test_snapshot_shape_default_profile():
    snap = subs.subscriber_snapshot()
    assert snap["profile_id"] == subs.default_profile() == "t2-holdings-tyrone-johnson"
    assert snap["plan_id"] == "autothink"
    assert snap["gates_always_off"] is True
    assert snap["subscription_status"] == "active"
    assert set(snap["gate_state"]) == ALL_GATES
    assert all(v == "off" for v in snap["gate_state"].values())
    assert "approval" in snap["honesty"]


def test_snapshot_unknown_profile_fails_closed():
    with pytest.raises(KeyError):
        subs.subscriber_snapshot("nobody-real")


# ---------- CLI ----------

def test_cli_plans():
    code, lines = subs.run_cli(["--plans"])
    assert code == 0
    joined = "\n".join(lines)
    assert "foundation" in joined and "autothink" in joined
    assert "gates_always_off=True" in joined


def test_cli_plan_detail():
    code, lines = subs.run_cli(["--plan", "scout"])
    assert code == 0
    assert "Scout" in lines[0] and "$29" in lines[0]


def test_cli_plan_unknown_fails_closed():
    code, lines = subs.run_cli(["--plan", "nope_plan"])
    assert code == 1
    assert "Unknown subscription plan id" in lines[0]


def test_cli_subscribers():
    code, lines = subs.run_cli(["--subscribers"])
    assert code == 0
    assert "t2-holdings-tyrone-johnson" in "\n".join(lines)


def test_cli_check_green():
    code, lines = subs.run_cli(["--check"])
    assert code == 0
    assert "all checks green" in "\n".join(lines)


def test_cli_snapshot():
    code, lines = subs.run_cli(["--snapshot"])
    assert code == 0
    snap = json.loads("\n".join(lines))
    assert snap["plan_id"] == "autothink"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))