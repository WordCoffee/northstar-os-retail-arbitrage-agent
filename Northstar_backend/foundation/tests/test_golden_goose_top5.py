"""P5-T3 Golden Goose Top-5 selection tests."""
from __future__ import annotations

from Northstar_backend.foundation import golden_goose_top5 as t5
from Northstar_backend.foundation import golden_goose_decision as gg
from Northstar_backend.foundation.jobs_handlers import build_default_registry


def _c(item_id, score, *, state=gg.QUALIFIED_FOR_REVIEW, policy=0, econ=True, net=10.0):
    return {"item_id": item_id, "resale_score": score, "state": state,
            "policy_exclusion_flag": policy, "economics_complete": econ, "net_per_unit": net}


def test_fewer_than_five_never_padded():
    out = t5.select_top5([_c("A", 0.9), _c("B", 0.8)])
    assert out["selected_count"] == 2 and out["padded"] is False
    assert out["note"] == "fewer than n qualified; nothing padded"


def test_deterministic_and_tie_break_by_item_id():
    cands = [_c("B", 0.5), _c("A", 0.5), _c("C", 0.9)]
    a = t5.select_top5(cands)
    b = t5.select_top5(list(reversed(cands)))
    assert [c["item_id"] for c in a["selected"]] == ["C", "A", "B"]
    assert a["inputs_hash"] == b["inputs_hash"]


def test_blocking_gates_reported():
    cands = [
        _c("policy", 1.0, policy=1),
        _c("state", 1.0, state="UNKNOWN"),
        _c("econ", 1.0, econ=False),
        _c("floor", 1.0, net=3.0),
        _c("netunknown", 1.0, net=None),
        _c("ok", 0.5),
    ]
    out = t5.select_top5(cands)
    assert [c["item_id"] for c in out["selected"]] == ["ok"]
    reasons = {b["item_id"]: b["blocking_gate"] for b in out["blocked"]}
    assert reasons == {"policy": "policy_exclusion", "state": "below_qualified_for_review",
                       "econ": "economics_incomplete", "floor": "below_net_floor",
                       "netunknown": "net_unknown"}


def test_never_padded_caps_at_n():
    cands = [_c(f"i{i}", 0.1 * i) for i in range(7)]
    out = t5.select_top5(cands, n=5)
    assert out["selected_count"] == 5 and out["qualifying_count"] == 7
    assert out["padded"] is False


def test_handler_registered_and_validates():
    reg = build_default_registry()
    assert reg.has("golden_goose.monthly_top5") is True
    h = reg.handler("golden_goose.monthly_top5")
    ok = h({"candidates": [_c("A", 0.9)]}, {})
    assert ok.ok and ok.output["selected_count"] == 1
    bad = h({}, {})
    assert bad.ok is False and bad.error_code == "candidates_required"