"""P5-T3 Golden Goose Top-5 selection tests."""
from __future__ import annotations

from Northstar_backend.foundation import golden_goose_top5 as t5
from Northstar_backend.foundation import golden_goose_decision as gg
from Northstar_backend.foundation.jobs_handlers import build_default_registry


def _c(item_id, score, *, state=gg.QUALIFIED_FOR_REVIEW, policy=0, econ=True, net=10.0):
    return {"item_id": item_id, "resale_score": score, "state": state,
            "policy_exclusion_flag": policy, "economics_complete": econ, "net_per_unit": net}


def _iso_from_now(seconds: int) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


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


def test_monthly_top5_operator_schedule_path(seeded_state):
    """Evidence-backed (no invented cadence/retention/snapshot payload).

    An operator explicitly creates a ``golden_goose.monthly_top5`` schedule via
    the scheduler API with its own cron/interval; tick enqueues exactly one
    occurrence and the handler, when run, is deterministic and provider-free.
    Nothing here presupposes a default cron cadence, a retention window, or a
    snapshot payload schema that is not already evidenced in the store/schema
    (decisions persist scorer_version + inputs_hash).
    """
    from Northstar_backend.foundation.jobs_scheduler import JobScheduler

    sched = JobScheduler(seeded_state.jobs_durable, seeded_state.repos,
                         scheduler_id="gg-sched")
    row = sched.create_schedule(
        organization_id=seeded_state.ids["org"],
        owner_user_id=seeded_state.ids["user"],
        job_template={"job_type": "golden_goose.monthly_top5",
                      "payload": {"candidates": [_c("A", 0.9), _c("B", 0.4, net=3.0)],
                                  "n": 5, "floor": 5.00}},
        interval_seconds=3600, enabled=False,  # operator opts in explicitly
        first_run_at=_iso_from_now(-5))  # due now, within misfire window
    # provider-backed schedules default disabled; operator must enable + satisfy
    # the due window. Enable and tick a due occurrence.
    sched.set_enabled(organization_id=seeded_state.ids["org"],
                      schedule_id=row["id"], enabled=True,
                      actor_user_id=seeded_state.ids["user"])
    result = sched.tick()
    assert result["enqueued"] == 1

    # The handler is deterministic and makes zero provider/network calls.
    reg = build_default_registry()
    h = reg.handler("golden_goose.monthly_top5")
    out = h({"candidates": [_c("A", 0.9), _c("B", 0.4, net=3.0)], "n": 5, "floor": 5.00}, {})
    assert out.ok and out.output["selected_count"] == 1
    assert out.output["selected"][0]["item_id"] == "A"
    assert out.output["padded"] is False