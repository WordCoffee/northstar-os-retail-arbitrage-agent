"""Tests for the Tys Assistant operations layer (``tys_ops``).

These are behavioural tests against real files and real SQLite, not mocks: the
ledger, the queue, the index and the atomic writer are all exercised through
their public API. Anything a test asserts here is something the stress harness
also relies on.
"""

from __future__ import annotations

import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tys_ops import bridge, budgets, memory, selfheal, storage, ui, validators

GB = 1024 ** 3


# ---------------------------------------------------------------------------
# storage
# ---------------------------------------------------------------------------

def _ledger(tmp_path, **kwargs):
    return storage.StorageLedger(str(tmp_path / "ledger.json"),
                                 str(tmp_path / "media"))


def test_profile_cap_is_one_hundred(tmp_path):
    ledger = _ledger(tmp_path)
    for index in range(100):
        ledger.register_profile(f"p{index}", "free")
    with pytest.raises(storage.StorageError) as excinfo:
        ledger.register_profile("p101", "free")
    assert excinfo.value.code == "profile_cap_reached"


def test_free_tier_prunes_oldest_images_and_stays_under_cap(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.register_profile("p", "free")
    cap = ledger.profile("p")["image_quota_bytes"]
    statuses = []
    for index in range(100):
        result = ledger.store_media("p", "image", 20 * 1024 * 1024,
                                    name=f"{index}.png")
        statuses.append(result["status"])
    usage = ledger.usage("p")
    assert "pruned" in [m["state"] for m in ledger.media("p", state=None)]
    assert usage["total_bytes"] <= cap
    assert statuses.count("over_quota") == 0


def test_pruning_never_evicts_downloaded_media(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.register_profile("p", "free")
    first = ledger.store_media("p", "image", 700 * 1024 * 1024, name="keep.png")
    ledger.mark_downloaded("p", first["media"]["id"])
    second = ledger.store_media("p", "image", 700 * 1024 * 1024, name="more.png")
    assert second["status"] == "over_quota"
    assert second["code"] == "over_quota"
    assert second["deficit_bytes"] > 0
    assert [m["id"] for m in ledger.media("p")] == [first["media"]["id"]]


def test_free_tier_video_is_not_stored_and_prompts_download(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.register_profile("p", "free")
    result = ledger.store_media("p", "video", 10 * 1024 * 1024, name="clip.mp4")
    assert result["status"] == "not_stored"
    assert result["retention_seconds"] == 0
    assert result["must_download"] is True
    assert result["download_prompt"]["action"] == "download_now"


def test_session_end_purges_undownloaded_and_returns_prompts(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.register_profile("p", "free")
    ledger.store_media("p", "video", 1024, name="clip.mp4")
    stored = ledger.store_media("p", "image", 4096, name="shot.png",
                                data=b"x" * 4096)
    path = stored["media"]["path"]
    assert os.path.exists(path)
    ended = ledger.finalize_session("p")
    assert not os.path.exists(path)
    assert ended["purged"] and ended["download_prompts"]


def test_paid_tier_accepts_video_and_expires_it(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.register_profile("p", "paid_10gb")
    video = ledger.store_media("p", "video", 2 * GB, name="cut.mp4")
    assert video["status"] == "stored"
    assert video["media"]["expires_at"]
    later = time.time() + 31 * 86400
    swept = ledger.sweep_expired(now=later)
    assert swept["count"] == 1
    assert ledger.usage("p")["total_bytes"] == 0


def test_paid_tier_overflow_reports_deficit(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.register_profile("p", "paid_10gb")
    keep = ledger.store_media("p", "image", 9 * GB, name="plate.tif")
    ledger.mark_downloaded("p", keep["media"]["id"])
    result = ledger.store_media("p", "image", 2 * GB, name="overflow.tif")
    assert result["status"] == "over_quota"
    assert result["cap_bytes"] == 10 * GB


def test_paid_total_quota_counts_retained_video(tmp_path):
    """An image cannot use space already held by retained video."""
    ledger = _ledger(tmp_path)
    ledger.register_profile("p", "paid_10gb")
    ledger.store_media("p", "video", 3 * GB, name="cut.mp4")
    image = ledger.store_media("p", "image", 8 * GB, name="plate.tif")
    assert image["status"] == "over_quota"
    assert image["cap_bytes"] == 7 * GB


@pytest.mark.parametrize("kind,size,code", [
    ("audio", 10, "unknown_kind"),
    ("image", 0, "invalid_size"),
])
def test_invalid_media_input_is_refused(tmp_path, kind, size, code):
    ledger = _ledger(tmp_path)
    ledger.register_profile("p", "free")
    with pytest.raises(storage.StorageError) as excinfo:
        ledger.store_media("p", kind, size)
    assert excinfo.value.code == code


def test_unknown_profile_is_refused(tmp_path):
    ledger = _ledger(tmp_path)
    with pytest.raises(storage.StorageError) as excinfo:
        ledger.store_media("nobody", "image", 10)
    assert excinfo.value.code == "unknown_profile"


def test_ledger_survives_reload(tmp_path):
    path = str(tmp_path / "ledger.json")
    first = storage.StorageLedger(path, str(tmp_path / "media"))
    first.register_profile("p", "free")
    first.store_media("p", "image", 1024, name="a.png")
    second = storage.StorageLedger(path, str(tmp_path / "media"))
    assert second.usage("p")["total_bytes"] == 1024


def test_disk_guard_reports_action_when_low(tmp_path):
    report = storage.guard_disk(str(tmp_path), min_free_gb=10 ** 6)
    assert report["ok"] is False
    assert report["action"] == "pause_gpu_and_downloads"


def test_summary_counts_profiles_and_bytes(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.register_profile("a", "free")
    ledger.register_profile("b", "paid_10gb")
    ledger.store_media("a", "image", 2048)
    summary = ledger.summary()
    assert summary["profiles"] == 2
    assert summary["active_bytes"] == 2048
    assert summary["by_tier"] == {"free": 1, "paid_10gb": 1}


# ---------------------------------------------------------------------------
# bridge
# ---------------------------------------------------------------------------

SECRET = "unit-test-bridge-secret-0001"


def test_token_roundtrip_and_scope():
    authority = bridge.TokenAuthority(SECRET)
    token = bridge.issue_token(SECRET, "p1", scopes=["tasks:run"], ttl_s=60)
    payload = authority.verify(token, scope="tasks:run")
    assert payload["sub"] == "p1"
    with pytest.raises(bridge.BridgeError) as excinfo:
        authority.verify(token, scope="admin")
    assert excinfo.value.code == "token_scope_denied"


def test_token_expiry_uses_skew_window():
    authority = bridge.TokenAuthority(SECRET)
    token = bridge.issue_token(SECRET, "p1", ttl_s=60, now=1_000_000)
    assert authority.verify(token, now=1_000_000 + 30)
    with pytest.raises(bridge.BridgeError) as excinfo:
        authority.verify(token, now=1_000_000 + 200)
    assert excinfo.value.code == "token_expired"


def test_revoked_and_tampered_tokens_are_refused():
    authority = bridge.TokenAuthority(SECRET)
    token = bridge.issue_token(SECRET, "p1")
    authority.revoke(token)
    with pytest.raises(bridge.BridgeError) as excinfo:
        authority.verify(token)
    assert excinfo.value.code == "token_revoked"

    other = bridge.issue_token(SECRET, "p1")
    tampered = other[:-3] + "abc"
    with pytest.raises(bridge.BridgeError) as excinfo:
        authority.verify(tampered)
    assert excinfo.value.code == "token_bad_signature"


def test_weak_secret_refused():
    with pytest.raises(bridge.BridgeError) as excinfo:
        bridge.TokenAuthority("short")
    assert excinfo.value.code == "weak_secret"


def test_queue_dedupes_by_idempotency_key(tmp_path):
    queue = bridge.OfflineQueue(str(tmp_path / "q.json"))
    first = queue.enqueue("p", "run", {"n": 1}, idempotency_key="k")
    second = queue.enqueue("p", "run", {"n": 1}, idempotency_key="k")
    assert first["status"] == "queued"
    assert second["status"] == "duplicate"
    assert queue.stats("p")["pending"] == 1


def test_transport_failure_keeps_every_operation(tmp_path):
    queue = bridge.OfflineQueue(str(tmp_path / "q.json"), max_attempts=4)
    for index in range(6):
        queue.enqueue("p", "run", {"n": index}, idempotency_key=f"k{index}")

    def down(item):
        raise TimeoutError("uplink")

    first = queue.flush("p", down, now=time.time())
    assert len(first["sent"]) == 0
    assert first["pending_remaining"] == 6
    assert first["retry"][0]["attempts"] == 1

    sent = queue.flush("p", lambda item: {"ok": True}, now=time.time() + 60)
    assert len(sent["sent"]) == 6
    assert sent["pending_remaining"] == 0


def test_operations_become_dead_letters_not_silent_drops(tmp_path):
    queue = bridge.OfflineQueue(str(tmp_path / "q.json"), max_attempts=2)
    queue.enqueue("p", "run", {}, idempotency_key="k")

    def down(item):
        raise ConnectionError("down")

    for offset in (0, 10, 30):
        queue.flush("p", down, now=time.time() + offset)
    dead = queue.dead_letters("p")
    assert len(dead) == 1
    assert queue.stats("p")["dead"] == 1


def test_sync_envelope_replay_is_ignored():
    sync = bridge.SyncState()
    envelope = sync.envelope("p", [{"a": 1}])
    assert sync.apply_remote(envelope)["status"] == "applied"
    assert sync.apply_remote(envelope)["status"] == "replay_ignored"
    newer = sync.envelope("p", [{"a": 2}])
    advanced = sync.apply_remote(newer)
    assert advanced["status"] == "applied"
    assert advanced["cursor"] == 2


def test_gateway_refuses_plaintext_on_public_host():
    with pytest.raises(bridge.BridgeError) as excinfo:
        bridge.gateway_descriptor("seller.example.net", 8000, scheme="http")
    assert excinfo.value.code == "plaintext_exposure_refused"
    assert bridge.gateway_descriptor("127.0.0.1", 8000,
                                     scheme="http")["base_url"].startswith("http://")
    https = bridge.gateway_descriptor("seller.example.net", 443, scheme="https")
    assert https["routes"]["run"].startswith("POST")


# ---------------------------------------------------------------------------
# validators
# ---------------------------------------------------------------------------

def test_text_check_catches_every_structural_defect():
    result = validators.check_text(
        "TODO short.", required_headings=["Findings"], min_sentences=3,
        min_chars=120)
    assert result["valid"] is False
    assert "missing_heading" in result["codes"]
    assert "placeholder_todo" in result["codes"]
    assert "too_short" in result["codes"]
    assert "sentence_floor" in result["codes"]


def test_text_check_accepts_a_complete_deliverable():
    text = ("## Findings\n\nThe routing table names four lanes and each lane "
            "reports availability. The inspect lane stays inside scope. "
            "The coding lane starts on demand and stops afterwards.\n\n"
            "## Next\n\nQueue the follow-up inspection.")
    result = validators.check_text(text, required_headings=["Findings", "Next"],
                                   min_sentences=3, min_chars=120)
    assert result["valid"] is True


def test_unchanged_from_seed_is_flagged():
    seed = "## Findings\n\nThe draft is unchanged."
    result = validators.check_text(seed, seed=seed)
    assert result["codes"] == ["unchanged_from_seed"]


def test_json_required_keys():
    result = validators.check_json({"summary": "ok"}, required_keys=["summary", "steps"])
    assert result["valid"] is False
    assert result["codes"] == ["missing_key"]


GOOD_DIFF = """--- a/x.py
+++ b/x.py
@@ -1,2 +1,2 @@
 x = 1
-y = 2
+y = 3
"""

BAD_DIFF = """--- a/x.py
+++ b/x.py
@@ -1,7 +9,9 @@
 x = 1
-y = 2
+y = 3
"""


def test_patch_arithmetic_good_and_bad(tmp_path):
    good = tmp_path / "good.diff"
    good.write_text(GOOD_DIFF, encoding="utf-8", newline="\n")
    result = validators.check_patch(str(good))
    assert result["valid"] is True
    assert result["hunks"] == 1

    bad = tmp_path / "bad.diff"
    bad.write_text(BAD_DIFF, encoding="utf-8", newline="\n")
    result = validators.check_patch(str(bad))
    assert result["valid"] is False
    assert "hunk_arithmetic" in result["codes"]


def test_workspace_acceptance_outranks_self_report(tmp_path):
    (tmp_path / "ok.py").write_text("print('ok')\n", encoding="utf-8")
    failing = validators.workspace_acceptance(
        str(tmp_path),
        {"artifact_exists": ["missing.txt"],
         "command": [{"argv": [sys.executable, "-c", "raise SystemExit(4)"],
                      "expect_exit": 0}]},
        self_report={"status": "done"})
    assert failing["verdict"] == "fail"
    assert failing["self_report_outranked"] is True

    passing = validators.workspace_acceptance(
        str(tmp_path),
        {"artifact_exists": ["ok.py"],
         "command": [{"argv": [sys.executable, "ok.py"], "expect_exit": 0}]},
        self_report={"status": "failed"})
    assert passing["verdict"] == "pass"
    assert passing["self_report_outranked"] is True


def test_workspace_rejects_escaping_artifact_path(tmp_path):
    result = validators.workspace_acceptance(
        str(tmp_path), {"artifact_exists": ["../outside.txt"]})
    assert result["verdict"] == "fail"
    assert any("escapes" in problem for problem in result["problems"])


def test_suite_aggregates_and_never_raises():
    report = validators.run_suite([
        {"id": "a", "kind": "text", "text": "## Findings\n\nDone. Done. Done."},
        {"id": "b", "kind": "nonsense"},
    ])
    assert report["total"] == 2
    assert report["passed"] == 1
    assert report["rows"][1]["valid"] is False


# ---------------------------------------------------------------------------
# memory
# ---------------------------------------------------------------------------

def test_embedding_is_deterministic_and_normalised():
    first = memory.embed("the pouch hero render")
    second = memory.embed("the pouch hero render")
    assert first == second
    assert abs(sum(v * v for v in first) - 1.0) < 1e-6
    assert memory.embed("") == [0.0] * memory.DIM


def test_chunking_respects_token_budget():
    text = "\n\n".join(f"Sentence number {i} about the render lane." for i in range(40))
    chunks = memory.chunk_text(text, max_tokens=40)
    assert chunks
    assert all(memory.token_estimate(chunk) <= 60 for chunk in chunks)


def test_search_returns_the_relevant_chunk(tmp_path):
    index = memory.MemoryIndex(str(tmp_path / "m.db"))
    index.remember_text("p", "The free tier keeps no video and prompts a download.")
    index.remember_text("p", "The render lane takes the GPU lock before it starts.")
    hits = index.search("p", "video download", k=1)
    assert hits and "video" in hits[0]["text"].lower()


def test_compression_is_extractive_and_budgeted():
    text = ("The render lane takes the GPU lock. It releases the lock afterwards. "
            "The coding lane starts a worker on demand. It stops the worker. "
            "The inspect lane reads bounded files only.")
    packed = memory.compress(text, max_tokens=18, query="GPU lock")
    assert packed["tokens"] <= 18
    assert "GPU lock" in packed["text"]


def test_facts_supersede_and_report_contradiction(tmp_path):
    index = memory.MemoryIndex(str(tmp_path / "m.db"))
    first = index.assert_fact("p", "storage", "video", "retained")
    second = index.assert_fact("p", "storage", "video", "none", confidence=0.9)
    assert second["contradiction"]["previous"] == "retained"
    assert index.recall_fact("p", "storage", "video")["value"] == "none"
    assert len(index.conflicts("p")) == 1
    assert index.unlearn(second["id"])["status"] == "unlearned"
    assert index.facts("p") == []


def test_context_respects_budget(tmp_path):
    index = memory.MemoryIndex(str(tmp_path / "m.db"))
    for _ in range(5):
        index.remember_text("p", "The render lane takes the GPU lock and holds it. "
                                 "The coding lane waits for the lock.")
    context = index.context("p", "GPU lock", budget_tokens=25)
    assert context["used_tokens"] <= 25
    assert context["hits"] >= 1


# ---------------------------------------------------------------------------
# budgets
# ---------------------------------------------------------------------------

def test_token_bucket_refills_without_sleeping():
    bucket = budgets.TokenBucket(rate_per_s=1.0, burst=2)
    assert bucket.allow(2, now=0)["allowed"] is True
    assert bucket.allow(1, now=0)["allowed"] is False
    assert bucket.allow(1, now=2)["allowed"] is True


def test_budget_guard_refuses_over_task_cap(tmp_path):
    guard = budgets.BudgetGuard(str(tmp_path / "b.json"), task_cap=100,
                                daily_cap=1000)
    guard.start_task("p", "t1")
    guard.consume("p", 90)
    with pytest.raises(budgets.BudgetExceeded) as excinfo:
        guard.consume("p", 20)
    assert excinfo.value.code == "task_budget_exceeded"
    assert guard.status("p")["task_tokens"] == 90


def test_budget_guard_refuses_over_daily_cap(tmp_path):
    guard = budgets.BudgetGuard(str(tmp_path / "b.json"), task_cap=1000,
                                daily_cap=100)
    guard.start_task("p", "t1", cap=1000)
    with pytest.raises(budgets.BudgetExceeded) as excinfo:
        guard.consume("p", 150)
    assert excinfo.value.code == "daily_budget_exceeded"


def test_budget_rolls_over_on_a_new_day(tmp_path):
    guard = budgets.BudgetGuard(str(tmp_path / "b.json"), daily_cap=100)
    guard.start_task("p", "t1", cap=1000, now=0)
    guard.consume("p", 90, now=0)
    later = guard.status("p", now=86400 * 2)
    assert later["day_tokens"] == 0


def test_vram_refuses_rather_than_overcommits():
    card = budgets.VramBudget(1000)
    card.reserve("render", 900)
    with pytest.raises(budgets.BudgetExceeded) as excinfo:
        card.reserve("coding", 200)
    assert excinfo.value.code == "vram_busy"
    card.release("render")
    assert card.reserve("coding", 200)["used_mb"] == 200


def test_tuner_explores_then_exploits(tmp_path):
    tuner = budgets.Tuner(str(tmp_path / "t.json"))
    seen = set()
    for _ in range(20):
        choice = tuner.choose("low")
        seen.add(choice["params"]["id"])
        tuner.feedback("low", choice["params"]["id"], 0.9)
    assert len(seen) > 1
    report = tuner.report()["low"]
    assert report["trials"] == 20
    assert report["leader"]


def test_tuner_rejects_out_of_range_feedback(tmp_path):
    tuner = budgets.Tuner(str(tmp_path / "t.json"))
    with pytest.raises(ValueError):
        tuner.feedback("low", "l0", 1.5)


def test_feedback_router_reorders_lanes():
    router = budgets.FeedbackRouter(decay=1.0)
    for _ in range(5):
        router.record("browser", 0.9)
    for _ in range(2):
        router.record("inspect", 0.2)
    assert router.rank()[0] == "browser"


def test_complexity_classification():
    assert budgets.complexity("show state") == "low"
    assert budgets.complexity("refactor the routing table and migrate it") == "high"
    assert budgets.complexity("summarise the queue") == "medium"


# ---------------------------------------------------------------------------
# selfheal
# ---------------------------------------------------------------------------

def test_pid_alive_rejects_impossible_pids():
    assert selfheal.pid_alive(0) is False
    assert selfheal.pid_alive(999999) is False
    assert selfheal.pid_alive(os.getpid()) is True


def test_stale_lock_detection(tmp_path):
    lock = tmp_path / "profile.lock"
    lock.write_text(json.dumps({"pid": 999999}), encoding="utf-8")
    found = selfheal.stale_locks([str(lock)])
    assert found[0]["stale"] is True
    assert found[0]["reason"] == "dead_pid"


def test_repair_json_handles_trailing_commas_only():
    assert json.loads(selfheal.repair_json('{"a": 1,}')) == {"a": 1}
    assert selfheal.repair_json("{not json") is None


def test_repair_json_does_not_rewrite_smart_quotes_inside_strings():
    payload = '{"note": "the seller\u2019s \u201chero\u201d shot"}'
    repaired = selfheal.repair_json(payload)
    assert repaired is not None
    assert json.loads(repaired) == {"note": "the seller\u2019s \u201chero\u201d shot"}


def test_atomic_write_rolls_back_on_failed_verification(tmp_path):
    target = tmp_path / "state.json"
    target.write_text('{"ok": true}', encoding="utf-8")
    result = selfheal.atomic_write(str(target), "garbage",
                                   verify=lambda text: selfheal.repair_json(text)
                                   is not None and text.startswith("{"))
    assert result["status"] == "rolled_back"
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}


def test_atomic_write_succeeds_and_keeps_a_backup(tmp_path):
    target = tmp_path / "state.json"
    target.write_text('{"a": 1}', encoding="utf-8")
    result = selfheal.atomic_write(str(target), '{"a": 2}',
                                   verify=lambda text: json.loads(text) == {"a": 2})
    assert result["status"] == "written"
    assert os.path.isfile(result["backup"])
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 2}


def test_rollback_registry_restores_latest(tmp_path):
    target = tmp_path / "f.txt"
    target.write_text("one", encoding="utf-8")
    registry = selfheal.RollbackRegistry()
    registry.record(selfheal.snapshot(str(target)), reason="before edit")
    target.write_text("two", encoding="utf-8")
    registry.rollback()
    assert target.read_text(encoding="utf-8") == "one"


def test_diagnose_reports_findings(tmp_path):
    state = tmp_path / "00_STATE.json"
    state.write_text("{bad", encoding="utf-8")
    report = selfheal.diagnose(str(tmp_path), state_path=str(state),
                               db_path=str(tmp_path / "none.db"))
    ids = [finding["id"] for finding in report["findings"]]
    assert "state_corrupt" in ids
    assert report["worst"] in ("high", "critical")


# ---------------------------------------------------------------------------
# ui
# ---------------------------------------------------------------------------

def _state(index: int = 0):
    return {
        "queue": {"total": index, "next": "tys_1",
                  "by_status": {"done": index, "blocked": 0}},
        "lanes": {"inspect": {"available": True}, "coding": {"available": False,
                                                             "detail": "on demand"},
                  "browser": {"available": True}, "creative": {"available": True}},
        "tasks": [{"id": "tys_1", "status": "done", "title": "t", "cursor": 1}],
    }


def test_render_is_valid_and_deterministic():
    tree = ui.render("p", _state())
    assert ui.validate_tree(tree) == []
    assert tree["degraded"] is False
    again = ui.render("p", _state())
    assert tree["version"] == again["version"]


def test_render_degrades_to_a_complete_tree():
    tree = ui.render("p", {"queue": None, "lanes": "nope"})
    assert tree["degraded"] is True
    assert ui.validate_tree(tree) == []
    assert tree["regions"]["alerts"]["alerts"][0]["id"] == "render-degraded"


def test_personalisation_orders_navigation_by_usage():
    tree = ui.render("p", _state(),
                     {"lane_counts": {"browser": 10, "inspect": 1}})
    labels = [item["label"] for item in tree["regions"]["nav"]["items"]]
    assert labels[0] == "Browser"


def test_component_whitelist_is_enforced():
    with pytest.raises(ValueError):
        ui._component("script", cid="x")


def test_diff_reports_changed_regions():
    first = ui.render("p", _state(1))
    second = ui.render("p", _state(2))
    change = ui.diff(first, second)
    assert "status" in change["changed"]
    assert change["dropped"] == []


def test_storage_summary_surfaces_download_prompts():
    tree = ui.render("p", _state(), storage={"pending_download_prompts": 2,
                                             "active_bytes": 10, "profiles": 1})
    alerts = tree["regions"]["alerts"]["alerts"]
    assert any(alert["id"] == "download-prompts" for alert in alerts)


# ---------------------------------------------------------------------------
# agent state cache (concurrent mobile polling)
# ---------------------------------------------------------------------------

def test_cached_state_does_not_reprobe_within_ttl(tmp_path):
    import tys_assistant as tys

    assistant = tys.TysAssistant(store=tys.TysStore(str(tmp_path / "q.db")),
                                 evidence_dir=str(tmp_path / "evidence"))
    calls = {"n": 0}

    class Probe:
        def available(self):
            calls["n"] += 1
            return {"adapter": "probe", "available": True, "detail": ""}

    class Brain:
        MODEL = "test-brain"

        def available(self):
            return {"adapter": "brain", "available": True}

    assistant.adapters = {"inspect": Probe()}
    assistant.orchestrator = Brain()

    assistant.cached_state()
    assistant.cached_state()
    assert calls["n"] == 1
    assistant.cached_state(fresh=True)
    assert calls["n"] == 2
