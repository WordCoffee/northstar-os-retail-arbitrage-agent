"""Phase A / A0 — learning loop + cache hierarchy tests (offline)."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import master_brain_learning as mbl  # noqa: E402

NOW = datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc)


# --- canonicalization -------------------------------------------------------

def test_normalize_task():
    assert mbl.normalize_task("  Fix   the BUG!  ") == "fix the bug"
    assert mbl.normalize_task("") == ""
    assert mbl.normalize_task(None) == ""


def test_intent_signature_deterministic():
    a = mbl.intent_signature("Run the daily scout summary")
    b = mbl.intent_signature("run the daily SCOUT summary.")
    assert a == b and len(a) == 64


def test_intent_signature_partitions_by_account():
    a = mbl.intent_signature("Run the daily scout summary", account_id="acct_a")
    b = mbl.intent_signature("Run the daily scout summary", account_id="acct_b")
    assert a != b


def test_intent_signature_respects_task_class():
    a = mbl.intent_signature("do the thing", task_class="AUTOTHINK_CODE")
    b = mbl.intent_signature("do the thing", task_class="NORTHSTAR_OS_COMMERCE")
    assert a != b


# --- staleness / invalidation ----------------------------------------------

def test_state_hash_changes_with_state(tmp_path):
    s1 = tmp_path / "s1.json"
    s2 = tmp_path / "s2.json"
    base = {"git_baseline": {"commit_hash": "abc"},
            "engine": {"primary_id": "e1"},
            "known_issues": [{"id": "x", "status": "open"}],
            "test_baseline": {"updated_at": "t1"}}
    s1.write_text(json.dumps(base), encoding="utf-8")
    changed = dict(base)
    changed["git_baseline"] = {"commit_hash": "def"}
    s2.write_text(json.dumps(changed), encoding="utf-8")
    assert mbl.state_hash(str(s1)) != mbl.state_hash(str(s2))


def test_state_hash_stable_and_missing_file(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"git_baseline": {"commit_hash": "abc"}}), encoding="utf-8")
    assert mbl.state_hash(str(p)) == mbl.state_hash(str(p))
    # missing file -> still deterministic (empty subset)
    assert mbl.state_hash(str(tmp_path / "nope.json")) == mbl.state_hash(str(tmp_path / "nope.json"))


# --- signal capture ---------------------------------------------------------

def test_record_experience_appends(tmp_path):
    exp = tmp_path / "experience.jsonl"
    mbl.record_experience("outcome", "task a", path=str(exp), now=NOW)
    mbl.record_experience("outcome", "task b", path=str(exp), now=NOW)
    rows = mbl.read_experience(str(exp))
    assert len(rows) == 2
    assert rows[0]["kind"] == "outcome"


def test_all_four_signals(tmp_path):
    exp = str(tmp_path / "experience.jsonl")
    mbl.record_user_edit("t", "price", 10, 12, path=exp, now=NOW)
    mbl.record_outcome("t", "accepted", path=exp, now=NOW)
    mbl.record_model_choice("t", "T2", "deepseek-v4-flash-0731", path=exp, now=NOW)
    mbl.record_staleness("t", "state changed", path=exp, now=NOW)
    kinds = [r["kind"] for r in mbl.read_experience(exp)]
    assert kinds == ["user_edit", "outcome", "model_choice", "staleness"]


def test_record_invalid_kind_and_outcome(tmp_path):
    with pytest.raises(ValueError):
        mbl.record_experience("bogus", "t", path=str(tmp_path / "e.jsonl"))
    with pytest.raises(ValueError):
        mbl.record_outcome("t", "maybe", path=str(tmp_path / "e.jsonl"))


def test_user_edit_payload(tmp_path):
    exp = str(tmp_path / "e.jsonl")
    mbl.record_user_edit("t", "title", "old", "new", path=exp, now=NOW)
    r = mbl.read_experience(exp)[0]
    assert r["payload"] == {"field": "title", "from": "old", "to": "new"}


# --- confidence + distillation ---------------------------------------------

def test_confidence_prior_when_no_outcomes():
    assert mbl._confidence_for([]) == mbl.DEFAULT_PRIOR


def test_confidence_accepted_beats_rejected():
    acc = mbl._confidence_for([{"kind": "outcome", "payload": {"outcome": "accepted"}}] * 5)
    rej = mbl._confidence_for([{"kind": "outcome", "payload": {"outcome": "rejected"}}] * 5)
    assert acc > 0.8 and rej < 0.3


def test_distill_builds_playbook(tmp_path):
    exp = tmp_path / "e.jsonl"
    pb = tmp_path / "p.json"
    for _ in range(4):
        mbl.record_outcome("Run the daily scout summary", "accepted", path=str(exp), now=NOW)
    mbl.record_model_choice("Run the daily scout summary", "T2", "deepseek-v4-flash-0731",
                            latency_ms=900, cost_usd=0.001, path=str(exp), now=NOW)
    out = mbl.distill(path=str(exp), out_path=str(pb), now=NOW)
    assert len(out) == 1
    entry = next(iter(out.values()))
    assert entry["confidence"] > 0.8
    assert entry["strategy"]["model_choice"]["model"] == "deepseek-v4-flash-0731"
    assert entry["ttl_seconds"] == mbl.DEFAULT_TTL_SECONDS
    assert entry["observations"] == 5


def test_get_playbook_threshold(tmp_path):
    pb = tmp_path / "p.json"
    sig = "a" * 64
    mbl._atomic_write_json(str(pb), {
        sig: {"intent_signature": sig, "account_id": "default", "confidence": 0.9,
              "task": "t", "expires_at": mbl._iso(NOW + timedelta(days=1))}
    })
    assert mbl.get_playbook(sig, out_path=str(pb), now=NOW) is not None
    assert mbl.get_playbook(sig, min_confidence=0.95, out_path=str(pb), now=NOW) is None
    assert mbl.get_playbook(sig, account_id="other", out_path=str(pb), now=NOW) is None


def test_get_playbook_expired(tmp_path):
    pb = tmp_path / "p.json"
    sig = "b" * 64
    mbl._atomic_write_json(str(pb), {
        sig: {"intent_signature": sig, "account_id": "default", "confidence": 0.9,
              "expires_at": mbl._iso(NOW - timedelta(days=1))}
    })
    assert mbl.get_playbook(sig, out_path=str(pb), now=NOW) is None


# --- decay + unlearn --------------------------------------------------------

def test_decay_and_prune_drops_low(tmp_path):
    pb = tmp_path / "p.json"
    sig = "c" * 64
    mbl._atomic_write_json(str(pb), {
        sig: {"intent_signature": sig, "account_id": "default", "confidence": 0.61,
              "updated_at": mbl._iso(NOW - timedelta(days=30)),
              "expires_at": mbl._iso(NOW + timedelta(days=1))}
    })
    res = mbl.decay_and_prune(out_path=str(pb), now=NOW)
    assert sig in res["dropped"] and res["kept"] == 0


def test_unlearn_intent_and_topic(tmp_path):
    pb = tmp_path / "p.json"
    mbl._atomic_write_json(str(pb), {
        "s1": {"intent_signature": "s1", "account_id": "default", "confidence": 0.9,
               "task": "daily scout summary", "strategy": {}},
        "s2": {"intent_signature": "s2", "account_id": "default", "confidence": 0.9,
               "task": "write ad copy", "strategy": {}},
    })
    assert mbl.unlearn_intent("s1", out_path=str(pb)) is True
    removed = mbl.unlearn_topic("ad copy", out_path=str(pb))
    assert removed == ["s2"]
    assert mbl.load_playbooks(str(pb)) == {}


# --- L0 cache ---------------------------------------------------------------

def test_cache_put_get_and_ttl(tmp_path):
    l0 = tmp_path / "l0.json"
    mbl.cache_put("fp1", {"answer": 42}, path=str(l0), now=NOW)
    assert mbl.cache_get("fp1", path=str(l0), now=NOW) == {"answer": 42}
    later = NOW + timedelta(seconds=mbl.DEFAULT_TTL_SECONDS + 10)
    assert mbl.cache_get("fp1", path=str(l0), now=later) is None
    mbl.cache_put("fp2", "x", ttl_seconds=10, path=str(l0), now=NOW)
    assert mbl.cache_get("fp2", path=str(l0), now=NOW + timedelta(seconds=20)) is None


# --- routing ----------------------------------------------------------------

@pytest.fixture
def isolated_state(tmp_path):
    p = tmp_path / "00_STATE.json"
    p.write_text(json.dumps({"git_baseline": {"commit_hash": "abc"},
                             "engine": {"primary_id": "e1"}}), encoding="utf-8")
    return str(p)


def test_route_escalate_novel(tmp_path, isolated_state):
    d = mbl.route_request("summarize a brand new thing",
                          state_path=isolated_state,
                          l0_path=str(tmp_path / "l0.json"),
                          playbooks_path=str(tmp_path / "p.json"), now=NOW)
    assert d.tier == "L3" and d.action == "escalate" and not d.requires_approval


def test_route_l0_replay(tmp_path, isolated_state):
    l0 = tmp_path / "l0.json"
    pb = tmp_path / "p.json"
    task = "run the daily scout summary"
    fp = mbl.fingerprint(task, state_path=isolated_state)["fingerprint"]
    mbl.cache_put(fp, "cached-output", path=str(l0), now=NOW)
    d = mbl.route_request(task, state_path=isolated_state, l0_path=str(l0),
                          playbooks_path=str(pb), now=NOW)
    assert d.tier == "L0" and d.action == "replay" and not d.requires_approval


def test_route_l1_replay_plan(tmp_path, isolated_state):
    l0 = tmp_path / "l0.json"
    pb = tmp_path / "p.json"
    task = "run the daily scout summary"
    sig = mbl.intent_signature(task)
    mbl._atomic_write_json(str(pb), {
        sig: {"intent_signature": sig, "account_id": "default", "confidence": 0.9,
              "task": task, "strategy": {"model_choice": {"tier": "T2"}},
              "expires_at": mbl._iso(NOW + timedelta(days=1))}
    })
    d = mbl.route_request(task, state_path=isolated_state, l0_path=str(l0),
                          playbooks_path=str(pb), now=NOW)
    assert d.tier == "L1" and d.action == "replay_plan" and d.playbook is not None


def test_route_l2_fastpath(tmp_path, isolated_state):
    l0 = tmp_path / "l0.json"
    pb = tmp_path / "p.json"
    task = "run the daily scout summary"
    sig = mbl.intent_signature(task)
    mbl._atomic_write_json(str(pb), {
        sig: {"intent_signature": sig, "account_id": "default", "confidence": 0.2,
              "task": task, "strategy": {}, "expires_at": mbl._iso(NOW + timedelta(days=1))}
    })
    d = mbl.route_request(task, state_path=isolated_state, l0_path=str(l0),
                          playbooks_path=str(pb), now=NOW)
    assert d.tier == "L2" and d.action == "generate" and d.playbook is not None


def test_route_live_never_replays(tmp_path, isolated_state):
    l0 = tmp_path / "l0.json"
    task = "publish the listing live"
    fp = mbl.fingerprint(task, state_path=isolated_state)["fingerprint"]
    mbl.cache_put(fp, "should-not-be-used", path=str(l0), now=NOW)
    d = mbl.route_request(task, live=True, state_path=isolated_state, l0_path=str(l0),
                          playbooks_path=str(tmp_path / "p.json"), now=NOW)
    assert d.tier == "L3" and d.action == "approval_required" and d.requires_approval


def test_is_live_gated():
    assert mbl.is_live_gated("publish the post") is True
    assert mbl.is_live_gated("anything", live=True) is True
    assert mbl.is_live_gated("summarize the catalog") is False
