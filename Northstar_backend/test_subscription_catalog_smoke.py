"""A2 smoke test — the two plan-catalog loaders must never disagree.

Both backend loaders read `shared/subscription-plans.json` as the single
source of truth:
  - auth.py::PLAN_ENTITLEMENTS           (legacy dict shape: {id: {name, price, gates, description}})
  - master_brain_subscribers.load_plans() (catalog dict shape: {gates_always_off, plans: [...]})

If a future edit changes one consumer's view of plan ids, tier names, prices,
or gate arrays relative to the other, the smoke test below fails. This is the
guard against the two-source drift the Gate-0 audit flagged.

Run: python -m pytest Northstar_backend/test_subscription_catalog_smoke.py -q
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import auth  # noqa: E402
import master_brain_subscribers as subs  # noqa: E402

CATALOG = subs.load_plans()
PLANS_BY_ID = {p["id"]: p for p in CATALOG["plans"]}


def _disagreements():
    """Return a list of human-readable disagreements, empty when they agree."""
    auth_view = auth.PLAN_ENTITLEMENTS
    diffs = []
    if set(auth_view) != set(PLANS_BY_ID):
        diffs.append(
            "plan id sets differ: auth=%s vs subscribers=%s"
            % (sorted(auth_view), sorted(PLANS_BY_ID))
        )
        return diffs
    for pid, plan in PLANS_BY_ID.items():
        ae = auth_view[pid]
        checks = (
            ("name", plan["name"], ae["name"]),
            ("price", plan.get("price_usd_month"), ae["price"]),
            ("gates", list(plan.get("entitled_gates", [])), list(ae["gates"])),
            ("description", plan.get("description"), ae["description"]),
        )
        for field, got, want in checks:
            if got != want:
                diffs.append("%s.%s: %r != %r" % (pid, field, got, want))
    return diffs


def test_loaders_never_disagree_on_catalog():
    diffs = _disagreements()
    assert not diffs, "catalog drift between auth.py and master_brain_subscribers: %s" % " | ".join(diffs)


def test_loaders_read_the_same_single_source_file():
    # Both loaders must resolve to shared/subscription-plans.json (A2).
    assert subs.PLANS_PATH == auth._PLAN_CATALOG_PATH
    assert os.path.isfile(subs.PLANS_PATH)
    assert subs.PLANS_PATH.endswith(os.path.join("shared", "subscription-plans.json"))


def test_catalog_has_catalog_version():
    assert isinstance(CATALOG.get("catalog_version"), int)
    assert CATALOG["catalog_version"] >= 1


def test_gates_always_off_invariant_holds():
    assert CATALOG.get("gates_always_off") is True


def test_no_unlimited_language_in_catalog():
    def _scan(obj):
        if isinstance(obj, dict):
            return any(_scan(v) for v in obj.values())
        if isinstance(obj, list):
            return any(_scan(v) for v in obj)
        return isinstance(obj, str) and "unlimited" in obj.lower()

    assert not _scan(CATALOG), "catalog must not contain 'unlimited' language"


def test_gate_arrays_match_auth_view_exactly():
    # List-level (ordered) equality for gate arrays — order is content.
    for pid, plan in PLANS_BY_ID.items():
        assert list(plan.get("entitled_gates", [])) == auth.PLAN_ENTITLEMENTS[pid]["gates"], pid


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))