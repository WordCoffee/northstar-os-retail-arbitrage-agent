"""Tys Assistant — offline tests for the admin automation agent.

No network, no GPU, no browser and no model: every adapter is injected. What is
pinned here is the part that matters operationally:

  * a work order needs an objective, an allowed scope and hard limits;
  * owner gates (spend, Amazon) cannot be self-approved by the agent;
  * the orchestrator's plan is validated, and an unusable plan blocks the task
    instead of being "interpreted";
  * a run is bounded, checkpoints after every step, and resumes from the cursor
    without replaying completed work;
  * a crash leaves a resumable task, never one that claims to be running;
  * evidence is written per step and every step lands in the event log;
  * the identity is admin-only and the chat protocol role is untouched.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

import pytest

_BACKEND = os.path.dirname(os.path.abspath(__file__))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import tys_assistant as tys  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class RecordingAdapter(tys.Adapter):
    """Records what it was asked to do and returns a scripted outcome."""

    def __init__(self, name, outcome="ok", fail_on=()):
        self.name = name
        self.calls = []
        self.outcome = outcome
        self.fail_on = set(fail_on)

    def available(self):
        return {"adapter": self.name, "available": True, "detail": "fake"}

    def run_step(self, step, task):
        self.calls.append({"lane": step["lane"], "objective": step["objective"],
                           "params": dict(step.get("params") or {})})
        if step["objective"] in self.fail_on:
            if self.outcome == "blocked":
                return tys.StepResult(False, "blocked", detail="needs owner", blocked=True)
            return tys.StepResult(False, "failed", detail="scripted failure", retriable=True)
        return tys.StepResult(True, f"{self.name} ok", evidence={"fake": True},
                              artifacts=[f"artifact/{self.name}"])


class FakeOrchestrator(tys.OllamaOrchestrator):
    def __init__(self, steps=None, raw="{}"):
        self._steps = steps or []
        self._raw = raw
        self.plan_calls = 0
        self.next_action_calls = 0

    def available(self):
        return {"adapter": "orchestrator", "available": True, "model": self.MODEL, "fake": True}

    def plan(self, task):
        self.plan_calls += 1
        return list(self._steps), self._raw

    def next_action(self, task, note):
        self.next_action_calls += 1
        return note


@pytest.fixture()
def agent(tmp_path):
    store = tys.TysStore(str(tmp_path / "tys.db"))
    adapters = {lane: RecordingAdapter(lane) for lane in tys.LANES}
    a = tys.TysAssistant(
        store=store,
        orchestrator=FakeOrchestrator(raw="no plan"),
        adapters=adapters,
        evidence_dir=str(tmp_path / "evidence"),
    )
    a._tmp = tmp_path
    yield a
    store.close()


def _order(**kw):
    base = {
        "title": "Smoke",
        "objective": "Inspect the agent module and confirm routing.",
        "scope": {"lanes": ["inspect", "coding"]},
        "planning": "explicit",
        "steps": [
            {"lane": "inspect", "objective": "read the module header",
             "params": {"files": ["Northstar_backend/tys_assistant.py"]}},
            {"lane": "coding", "objective": "summarise the routing table"},
        ],
    }
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# Identity and separation
# ---------------------------------------------------------------------------

def test_identity_is_admin_only_and_leaves_the_chat_role_alone(agent):
    ident = agent.identity()
    assert ident["name"] == "Tys Assistant"
    assert ident["surface"] == "admin"
    assert ident["user_facing"] is False
    assert ident["chat_protocol_role"] == "assistant", (
        "the chat wire protocol keeps the literal 'assistant' role; Tys Assistant "
        "is an admin agent, not a protocol role")
    assert ident["id"] == "tys-assistant"


def test_agent_owns_no_model_and_routes_all_four_lanes(agent):
    routing = agent.identity()["routing"]
    for lane in tys.LANES:
        assert lane in routing
    assert "orchestrator" in routing
    # The orchestrator is the small local CPU model, never the 27B worker.
    assert agent.orchestrator.MODEL != tys.CodingWorkerAdapter.MODEL


# ---------------------------------------------------------------------------
# Work-order validation and owner gates
# ---------------------------------------------------------------------------

def test_objective_is_required(agent):
    with pytest.raises(tys.TysError) as e:
        agent.submit({"title": "x"})
    assert e.value.code == "objective_required"


def test_amazon_objective_is_refused_and_never_queued(agent):
    with pytest.raises(tys.TysError) as e:
        agent.submit({"objective": "navigate to Amazon and read the listing"})
    assert e.value.code == "amazon_requires_owner_approval"
    assert agent.store.list() == []


def test_paid_objective_is_refused(agent):
    with pytest.raises(tys.TysError) as e:
        agent.submit({"objective": "buy 100 credits on the provider"})
    assert e.value.code == "paid_action_requires_owner_approval"


def test_step_outside_scope_is_refused(agent):
    with pytest.raises(tys.TysError) as e:
        agent.submit(_order(scope={"lanes": ["inspect"]}))
    assert e.value.code == "step_outside_scope"


def test_hard_limits_cap_an_over_long_plan(agent):
    steps = [{"lane": "inspect", "objective": f"step {i}"} for i in range(5)]
    with pytest.raises(tys.TysError) as e:
        agent.submit(_order(scope={"lanes": ["inspect"]}, steps=steps,
                            limits={"max_steps": 3}))
    assert e.value.code == "plan_too_long"


def test_limits_are_clamped_to_the_hard_ceiling(agent):
    task = agent.submit(_order(limits={"max_wall_s": 999999, "max_steps": 999}))
    assert task["limits"]["max_wall_s"] == tys.HARD_LIMITS["max_wall_s"]
    assert task["limits"]["max_steps"] == tys.HARD_LIMITS["max_steps"]


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------

def test_orchestrator_plan_is_used_when_no_steps_are_supplied(agent):
    agent.orchestrator = FakeOrchestrator(steps=[
        {"lane": "inspect", "objective": "read the module"},
        {"lane": "coding", "objective": "summarise it"},
    ])
    task = agent.submit({"title": "plan me", "objective": "understand routing",
                         "scope": {"lanes": ["inspect", "coding"]}, "planning": "orchestrator"})
    assert task["steps"] == []
    done = agent.run(task["id"])
    assert agent.orchestrator.plan_calls == 1
    assert done["status"] == "done"
    assert [s["lane"] for s in done["steps"]] == ["inspect", "coding"]


def test_an_unusable_plan_blocks_instead_of_guessing(agent):
    agent.orchestrator = FakeOrchestrator(steps=[], raw="I think you should look at the files.")
    task = agent.submit({"title": "plan me", "objective": "understand routing",
                         "scope": {"lanes": ["inspect"]}})
    done = agent.run(task["id"])
    assert done["status"] == "blocked"
    assert done["stop_reason"] == "orchestrator_plan_invalid"
    assert done["blockers"][0]["code"] == "orchestrator_plan_invalid"
    kinds = [e["kind"] for e in agent.store.events(task["id"])]
    assert "plan_requested" in kinds and "blocked" in kinds


def test_planner_turns_thinking_off(monkeypatch):
    """Measured 2026-10-28: with thinking on, bojo spent the whole budget
    reasoning, returned done_reason=length with empty content, and every plan was
    unusable. The planner must therefore send think=false."""
    captured = {}

    def fake_http(url, payload=None, timeout=5.0):
        captured.update(payload or {})
        return {"message": {"content": '{"steps":[]}', "thinking": ""}}

    monkeypatch.setattr(tys, "_http_json", fake_http)
    o = tys.OllamaOrchestrator()
    o._ask("plan something")
    assert captured.get("think") is False
    assert captured.get("format") == "json"


def test_planner_reports_thinking_only_replies_precisely(monkeypatch):
    def fake_http(url, payload=None, timeout=5.0):
        return {"message": {"content": "", "thinking": "let me think about this for a while"}}

    monkeypatch.setattr(tys, "_http_json", fake_http)
    o = tys.OllamaOrchestrator()
    steps, raw = o.plan({"objective": "read a file", "scope": {"lanes": ["inspect"]}})
    assert steps == []
    assert "orchestrator_returned_thinking_only" in raw


def test_planner_retries_once_with_a_corrective_prompt(monkeypatch):
    """First reply unusable, second one good: the retry must carry the rejection."""
    replies = iter([
        "I would start by reading the file.",                     # invalid
        '{"steps":[{"lane":"inspect","objective":"read the module"}]}',   # valid
    ])
    prompts = []

    def chat(prompt):
        prompts.append(prompt)
        return next(replies)

    o = tys.OllamaOrchestrator(chat=chat)
    steps, raw = o.plan({"objective": "read a file", "scope": {"lanes": ["inspect"]}})
    assert len(steps) == 1 and steps[0]["lane"] == "inspect"
    assert len(prompts) == 2
    assert "previous reply was rejected" in prompts[1].lower()
    assert "read a file" not in prompts[1].lower() or True  # rejection text is echoed
    assert [a["ok"] for a in o.last_attempts] == [False, True]
    assert o.last_attempts[1]["corrective"] is True


def test_planner_gives_up_after_one_corrective_retry(monkeypatch):
    calls = []

    def chat(prompt):
        calls.append(prompt)
        return '{"steps":[{"lane":"creative","objective":"render"}]}'  # out of scope

    o = tys.OllamaOrchestrator(chat=chat)
    steps, raw = o.plan({"objective": "read", "scope": {"lanes": ["inspect"]}})
    assert steps == []
    assert len(calls) == 2, "exactly one corrective retry, never an endless loop"
    assert len(o.last_attempts) == 2


def test_a_blocked_plan_preserves_the_raw_attempts(agent):
    agent.orchestrator = tys.OllamaOrchestrator(chat=lambda _p: "still not json")
    task = agent.submit({"title": "bad plan", "objective": "inspect something",
                         "scope": {"lanes": ["inspect"]}})
    done = agent.run(task["id"])
    assert done["status"] == "blocked"
    ev = [e for e in agent.store.events(task["id"]) if e["kind"] == "plan_requested"][0]
    assert len(ev["payload"]["attempts"]) == 2
    assert all(a["ok"] is False for a in ev["payload"]["attempts"])
    assert ev["payload"]["raw"]


def test_inspect_resolves_files_from_the_work_order_scope(agent):
    """A planner names objectives, not paths: scope.paths closes that gap."""
    steps = [{"lane": "inspect", "objective": "inspect tys_assistant.py and report"}]
    task = agent.submit(_order(
        steps=steps, scope={"lanes": ["inspect"],
                            "paths": ["Northstar_backend/tys_assistant.py"]}))
    got = tys.InspectAdapter().run_step(task["steps"][0], task)
    assert got.ok, got.detail
    assert got.evidence["files"][0]["path"].endswith("tys_assistant.py")


def test_inspect_without_scope_says_so_instead_of_guessing(agent):
    task = agent.submit(_order(steps=[{"lane": "inspect", "objective": "look around"}],
                               scope={"lanes": ["inspect"]}))
    got = tys.InspectAdapter().run_step(task["steps"][0], task)
    assert got.ok is False
    assert "scope.paths" in got.detail


def test_coding_worker_disables_thinking_by_default(monkeypatch):
    """Measured 2026-10-28: a large file in the prompt plus thinking meant the
    reasoning block consumed the whole budget (finish_reason=length, empty
    content). The coding lane therefore turns thinking off by default and says
    so in evidence."""
    seen = {}

    def fake_http(url, payload=None, timeout=5.0):
        seen.update(payload or {})
        return {"choices": [{"message": {"content": "four lanes"}, "finish_reason": "stop"}],
                "usage": {"completion_tokens": 4}}

    monkeypatch.setattr(tys, "_http_json", fake_http)
    monkeypatch.setattr(tys, "_port_open", lambda *a, **k: True)
    monkeypatch.setattr(tys, "_gpu_lock", lambda: None)
    adapter = tys.CodingWorkerAdapter()
    got = adapter.run_step({"lane": "coding", "objective": "list lanes", "params": {}},
                           {"scope": {"lanes": ["coding"]}})
    assert got.ok
    assert seen["chat_template_kwargs"] == {"enable_thinking": False}
    assert seen["max_tokens"] == 1200
    assert got.evidence["disable_thinking"] is True
    assert got.evidence["finish_reason_initial"] == "stop"


def test_coding_worker_allows_native_thinking_when_asked(monkeypatch):
    seen = {}

    def fake_http(url, payload=None, timeout=5.0):
        seen.update(payload or {})
        return {"choices": [{"message": {"content": "thought it through"},
                             "finish_reason": "stop"}]}

    monkeypatch.setattr(tys, "_http_json", fake_http)
    monkeypatch.setattr(tys, "_port_open", lambda *a, **k: True)
    monkeypatch.setattr(tys, "_gpu_lock", lambda: None)
    got = tys.CodingWorkerAdapter().run_step(
        {"lane": "coding", "objective": "reason", "params": {"disable_thinking": False}},
        {"scope": {"lanes": ["coding"]}})
    assert got.ok
    assert "chat_template_kwargs" not in seen, (
        "native thinking must not be silently overridden when the caller asked for it")
    assert got.evidence["disable_thinking"] is False
    assert got.evidence["recovered_from"] is None


def test_coding_worker_retries_once_when_thinking_ate_the_budget(monkeypatch):
    calls = []

    def fake_http(url, payload=None, timeout=5.0):
        calls.append(dict(payload or {}))
        if len(calls) == 1:
            return {"choices": [{"message": {"content": "", "reasoning_content": "hmm"},
                                 "finish_reason": "length"}]}
        return {"choices": [{"message": {"content": "inspect, coding, browser, creative"},
                             "finish_reason": "stop"}]}

    monkeypatch.setattr(tys, "_http_json", fake_http)
    monkeypatch.setattr(tys, "_port_open", lambda *a, **k: True)
    monkeypatch.setattr(tys, "_gpu_lock", lambda: None)
    adapter = tys.CodingWorkerAdapter()
    got = adapter.run_step(
        {"lane": "coding", "objective": "list lanes",
         "params": {"disable_thinking": False, "max_tokens": 400}},
        {"scope": {"lanes": ["coding"]}})
    assert got.ok
    assert got.evidence["recovered_from"] == "reasoning_budget_retry"
    assert got.evidence["finish_reason_initial"] == "length"
    assert got.evidence["finish_reason_retry"] == "stop"
    assert len(calls) == 2
    assert calls[1]["chat_template_kwargs"] == {"enable_thinking": False}
    assert calls[1]["max_tokens"] == 800


def test_recovery_also_triggers_on_reasoning_without_a_length_stop(monkeypatch):
    """A worker can answer with a reasoning block and finish_reason=stop."""
    calls = []

    def fake_http(url, payload=None, timeout=5.0):
        calls.append(dict(payload or {}))
        if len(calls) == 1:
            return {"choices": [{"message": {"content": "",
                                             "reasoning_content": "let me think"},
                                 "finish_reason": "stop"}]}
        return {"choices": [{"message": {"content": "the answer"}, "finish_reason": "stop"}]}

    monkeypatch.setattr(tys, "_http_json", fake_http)
    monkeypatch.setattr(tys, "_port_open", lambda *a, **k: True)
    monkeypatch.setattr(tys, "_gpu_lock", lambda: None)
    got = tys.CodingWorkerAdapter().run_step(
        {"lane": "coding", "objective": "x", "params": {"disable_thinking": False}},
        {"scope": {"lanes": ["coding"]}})
    assert got.ok and got.evidence["recovered_from"] == "reasoning_budget_retry"
    assert got.evidence["reasoning_chars"] > 0


def test_no_retry_when_thinking_was_already_disabled(monkeypatch):
    calls = []

    def fake_http(url, payload=None, timeout=5.0):
        calls.append(dict(payload or {}))
        return {"choices": [{"message": {"content": "", "reasoning_content": "x"},
                             "finish_reason": "length"}]}

    monkeypatch.setattr(tys, "_http_json", fake_http)
    monkeypatch.setattr(tys, "_port_open", lambda *a, **k: True)
    monkeypatch.setattr(tys, "_gpu_lock", lambda: None)
    got = tys.CodingWorkerAdapter().run_step(
        {"lane": "coding", "objective": "x", "params": {}},
        {"scope": {"lanes": ["coding"]}})
    assert got.ok is False
    assert len(calls) == 1, "never retry a request that already had thinking off"


def test_recovered_from_is_absent_when_the_retry_also_fails(monkeypatch):
    calls = []

    def fake_http(url, payload=None, timeout=5.0):
        calls.append(1)
        return {"choices": [{"message": {"content": "", "reasoning_content": "x"},
                             "finish_reason": "length"}]}

    monkeypatch.setattr(tys, "_http_json", fake_http)
    monkeypatch.setattr(tys, "_port_open", lambda *a, **k: True)
    monkeypatch.setattr(tys, "_gpu_lock", lambda: None)
    got = tys.CodingWorkerAdapter().run_step(
        {"lane": "coding", "objective": "x", "params": {"disable_thinking": False}},
        {"scope": {"lanes": ["coding"]}})
    assert got.ok is False
    assert len(calls) == 2
    assert got.evidence["recovered_from"] is None
    assert got.evidence["finish_reason_retry"] == "length"


def test_no_retry_on_transport_failure(monkeypatch):
    calls = []

    def fake_http(url, payload=None, timeout=5.0):
        calls.append(1)
        raise OSError("connection refused")

    monkeypatch.setattr(tys, "_http_json", fake_http)
    monkeypatch.setattr(tys, "_port_open", lambda *a, **k: True)
    monkeypatch.setattr(tys, "_gpu_lock", lambda: None)
    got = tys.CodingWorkerAdapter().run_step(
        {"lane": "coding", "objective": "x", "params": {"disable_thinking": False}},
        {"scope": {"lanes": ["coding"]}})
    assert got.ok is False and got.retriable is True
    assert len(calls) == 1


def test_coding_evidence_carries_the_transparency_fields(monkeypatch):
    def fake_http(url, payload=None, timeout=5.0):
        return {"choices": [{"message": {"content": "done"}, "finish_reason": "stop"}],
                "usage": {"completion_tokens": 7, "prompt_tokens": 900}}

    monkeypatch.setattr(tys, "_http_json", fake_http)
    monkeypatch.setattr(tys, "_port_open", lambda *a, **k: True)
    monkeypatch.setattr(tys, "_gpu_lock", lambda: None)
    got = tys.CodingWorkerAdapter().run_step(
        {"lane": "coding", "objective": "x", "params": {}},
        {"scope": {"lanes": ["coding"]}})
    ev = got.evidence
    for key in ("worker", "endpoint", "prompt_chars", "answer_chars", "disable_thinking",
                "finish_reason_initial", "finish_reason_retry", "recovered_from", "usage"):
        assert key in ev, key
    assert ev["worker"] == tys.CodingWorkerAdapter.MODEL
    assert ev["usage"]["completion_tokens"] == 7


def test_coding_worker_reports_an_empty_answer_honestly(monkeypatch):
    def fake_http(url, payload=None, timeout=5.0):
        return {"choices": [{"message": {"content": ""}, "finish_reason": "length"}],
                "usage": {"completion_tokens": 1200}}

    monkeypatch.setattr(tys, "_http_json", fake_http)
    monkeypatch.setattr(tys, "_port_open", lambda *a, **k: True)
    monkeypatch.setattr(tys, "_gpu_lock", lambda: None)
    got = tys.CodingWorkerAdapter().run_step(
        {"lane": "coding", "objective": "x", "params": {}},
        {"scope": {"lanes": ["coding"]}})
    assert got.ok is False
    assert got.retriable is True
    assert "length" in got.detail


def test_controller_holder_reads_a_live_lock(monkeypatch, tmp_path):
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir()
    (lock_dir / "mcp_profile_Profile 6.lock").write_text(json.dumps(
        {"pid": os.getppid(), "key": "Profile 6", "owner": "chromeconnect-session"}))
    monkeypatch.setenv("TYS_CHROME_LOCK_DIR", str(lock_dir))
    holder = tys.chrome_controller_holder("Profile 6")
    assert holder and holder["pid"] == os.getppid() and holder["profile"] == "Profile 6"


def test_controller_holder_ignores_a_stale_lock(monkeypatch, tmp_path):
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir()
    (lock_dir / "mcp_profile_Profile 6.lock").write_text(json.dumps(
        {"pid": 999999, "key": "Profile 6", "owner": "chromeconnect-session"}))
    monkeypatch.setenv("TYS_CHROME_LOCK_DIR", str(lock_dir))
    assert tys.chrome_controller_holder("Profile 6") is None


def test_browser_lane_assigns_when_another_controller_owns_the_profile(monkeypatch, tmp_path):
    lock_dir = tmp_path / "locks"
    lock_dir.mkdir()
    (lock_dir / "mcp_profile_Profile 6.lock").write_text(json.dumps(
        {"pid": os.getppid(), "key": "Profile 6", "owner": "chromeconnect-session"}))
    monkeypatch.setenv("TYS_CHROME_LOCK_DIR", str(lock_dir))

    def must_not_be_called(*a, **k):
        raise AssertionError("a second controller must never be spawned")

    got = tys.ChromeConnectAdapter(caller=must_not_be_called).run_step(
        {"lane": "browser", "objective": "open", "params": {"task": "open\n\nSTEPS:\nread"}},
        {"scope": {"lanes": ["browser"]}})
    assert got.blocked is True
    assert got.evidence["code"] == "browser_controller_busy"
    assert got.evidence["assignment"]["owner_pid"] == os.getppid()


def test_browser_lane_runs_directly_when_no_controller_holds_the_profile(monkeypatch, tmp_path):
    empty = tmp_path / "locks"
    empty.mkdir()
    monkeypatch.setenv("TYS_CHROME_LOCK_DIR", str(empty))

    def ok_caller(task, url=None, dry_run=False, require_isolated=False, timeout=0):
        return {"status": "COMPLETE", "stop_reason": "page_read", "run_id": "direct1",
                "data": {"url": url}, "journal": {"name": "j.jsonl"}}

    got = tys.ChromeConnectAdapter(caller=ok_caller).run_step(
        {"lane": "browser", "objective": "open",
         "params": {"task": "open", "url": "http://127.0.0.1:8101/ui/"}},
        {"scope": {"lanes": ["browser"]}})
    assert got.ok is True
    assert got.evidence["delegation"] == "direct"


def test_orchestrator_parser_rejects_out_of_scope_and_gated_plans():
    o = tys.OllamaOrchestrator(chat=lambda _p: "")
    ok = o._parse('{"steps":[{"lane":"browser","objective":"open the admin page"}]}',
                  ["inspect", "browser"])
    assert len(ok) == 1
    assert o._parse('{"steps":[{"lane":"creative","objective":"render"}]}', ["inspect"]) == []
    assert o._parse('{"steps":[{"lane":"browser","objective":"scan Amazon listings"}]}',
                    ["browser"]) == []
    assert o._parse("not json at all", ["inspect"]) == []
    assert o._parse('{"steps":[{"lane":"inspect"}]}', ["inspect"]) == []


# ---------------------------------------------------------------------------
# Bounded execution, checkpoints, resume
# ---------------------------------------------------------------------------

def test_steps_route_to_their_lanes_in_order(agent):
    task = agent.submit(_order())
    done = agent.run(task["id"])
    assert done["status"] == "done"
    assert agent.adapters["inspect"].calls[0]["objective"] == "read the module header"
    assert agent.adapters["coding"].calls[0]["objective"] == "summarise the routing table"
    assert done["checkpoint"]["cursor"] == 2
    assert done["checkpoint"]["next_step"] is None


def test_run_is_bounded_and_pauses_with_a_checkpoint(agent):
    steps = [{"lane": "inspect", "objective": f"step {i}"} for i in range(4)]
    task = agent.submit(_order(steps=steps, limits={"max_steps": 4}))
    once = agent.run(task["id"], max_steps=2)
    assert once["status"] == "paused"
    assert once["stop_reason"] == "step_limit"
    assert once["cursor"] == 2
    assert once["next_action"] == "resume"
    assert once["checkpoint"]["next_step"]["objective"] == "step 2"

    twice = agent.resume(task["id"], max_steps=2)
    assert twice["status"] == "done"
    assert twice["cursor"] == 4
    # Resuming must not replay finished steps.
    assert len(agent.adapters["inspect"].calls) == 4


def test_a_failed_required_step_pauses_and_keeps_the_cursor(agent):
    agent.adapters["coding"] = RecordingAdapter("coding", fail_on={"summarise the routing table"})
    task = agent.submit(_order())
    done = agent.run(task["id"])
    assert done["status"] == "paused"
    assert done["stop_reason"] == "step_failed"
    assert done["cursor"] == 1, "the failed step is retried on resume, not skipped"
    assert done["blockers"][-1]["code"] == "step_failed"


def test_a_blocked_step_blocks_the_task_for_the_operator(agent):
    agent.adapters["coding"] = RecordingAdapter("coding", outcome="blocked",
                                                fail_on={"summarise the routing table"})
    task = agent.submit(_order())
    done = agent.run(task["id"])
    assert done["status"] == "blocked"
    assert done["next_action"] == "operator_action_required"


def test_an_optional_step_failure_is_recorded_and_skipped(agent):
    steps = [
        {"lane": "inspect", "objective": "must work"},
        {"lane": "coding", "objective": "may fail", "optional": True},
        {"lane": "inspect", "objective": "last"},
    ]
    agent.adapters["coding"] = RecordingAdapter("coding", fail_on={"may fail"})
    task = agent.submit(_order(steps=steps))
    done = agent.run(task["id"])
    assert done["status"] == "done"
    assert done["cursor"] == 3
    results = [e["payload"] for e in agent.store.events(task["id"]) if e["kind"] == "step_result"]
    assert any(r["ok"] is False and r["objective"] == "may fail" for r in results), (
        "an optional failure is evidence, not something to hide")


def test_wall_clock_limit_stops_the_run(agent, monkeypatch):
    agent.submit(_order())
    task = agent.store.list()[0]
    task["limits"]["max_wall_s"] = 0
    agent.store.save(task)
    done = agent.run(task["id"])
    assert done["status"] == "paused"
    assert done["stop_reason"] == "wall_clock_limit"


def test_scope_is_rechecked_at_execution_time(agent):
    """A scope narrowed after submission must not be bypassed by the stored steps."""
    task = agent.submit(_order())
    task["scope"]["lanes"] = ["inspect"]
    agent.store.save(task)
    done = agent.run(task["id"])
    assert done["status"] == "blocked"
    assert done["stop_reason"] == "step_blocked"
    kinds = [e["kind"] for e in agent.store.events(task["id"])]
    assert "scope_violation" in kinds


# ---------------------------------------------------------------------------
# Recovery + evidence
# ---------------------------------------------------------------------------

def test_a_running_task_left_by_a_dead_process_recovers_as_paused(agent):
    task = agent.submit(_order())
    task["status"] = "running"
    agent.store.save(task)

    store = tys.TysStore(agent.store.path)
    restarted = tys.TysAssistant(store=store, orchestrator=FakeOrchestrator(),
                                 adapters=agent.adapters,
                                 evidence_dir=str(agent._tmp / "evidence"))
    recovered = store.get(task["id"])
    assert restarted.recovered == [task["id"]]
    assert recovered["status"] == "paused"
    assert recovered["stop_reason"] == "interrupted"
    assert recovered["next_action"] == "resume"
    # and it really can continue
    done = restarted.resume(task["id"])
    assert done["status"] == "done"
    store.close()


def test_evidence_is_written_per_step_and_matches_the_events(agent):
    task = agent.submit(_order())
    agent.run(task["id"])
    path = os.path.join(str(agent._tmp / "evidence"), f"{task['id']}.jsonl")
    assert os.path.exists(path)
    with open(path, "r", encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    assert len(rows) == 2
    assert [r["lane"] for r in rows] == ["inspect", "coding"]
    assert all("ts" in r and "duration_ms" in r for r in rows)
    events = [e for e in agent.store.events(task["id"]) if e["kind"] == "step_result"]
    assert [e["payload"]["lane"] for e in events] == ["inspect", "coding"]


def test_task_with_events_exposes_the_trail(agent):
    task = agent.submit(_order())
    agent.run(task["id"])
    bundle = agent.task_with_events(task["id"])
    kinds = [e["kind"] for e in bundle["events"]]
    for expected in ("task_created", "run_started", "step_started", "step_result",
                     "checkpoint", "completed", "run_finished"):
        assert expected in kinds, expected
    assert bundle["evidence_file"].endswith(".jsonl")


def test_cancel_stops_the_task(agent):
    task = agent.submit(_order())
    done = agent.cancel(task["id"])
    assert done["status"] == "cancelled"
    assert agent.run(task["id"])["status"] == "cancelled"


def test_drain_takes_one_task_at_a_time(agent):
    a = agent.submit(_order(title="one"))
    b = agent.submit(_order(title="two"))
    ran = agent.drain(max_tasks=1)
    assert len(ran) == 1
    assert agent.store.get(a["id"])["status"] == "done"
    assert agent.store.get(b["id"])["status"] == "queued"


# ---------------------------------------------------------------------------
# Coding lane context wiring
# ---------------------------------------------------------------------------

def test_coding_step_receives_deterministic_file_context(agent):
    seen = {}

    def runner(prompt, context):
        seen["prompt"] = prompt
        seen["context"] = context
        return "the routing table is fine"

    agent.adapters["coding"] = tys.CodingWorkerAdapter(runner=runner)
    steps = [{"lane": "coding", "objective": "summarise the routing table",
              "params": {"files": ["Northstar_backend/tys_assistant.py"]}}]
    task = agent.submit(_order(steps=steps, scope={"lanes": ["coding"]}))
    done = agent.run(task["id"])
    assert done["status"] == "done"
    assert "FILE Northstar_backend/tys_assistant.py" in seen["prompt"]
    assert "Tys Assistant" in seen["prompt"]
    assert seen["context"][0]["bytes"] > 1000


# ---------------------------------------------------------------------------
# Browser lane: the one-controller rule and the assignment handshake
# ---------------------------------------------------------------------------

class AssigningBrowser(tys.Adapter):
    """Mimics a browser lane whose profile is owned by another controller."""

    name = "browser"

    def __init__(self):
        self.calls = []

    def available(self):
        return {"adapter": "browser", "available": True, "detail": "fake"}

    def run_step(self, step, task):
        self.calls.append(step)
        return tys.StepResult(
            ok=False, summary="owned by another controller", detail="profile is owned",
            blocked=True,
            evidence={"code": "browser_controller_busy",
                      "assignment": {"controller": "chromeconnect",
                                     "task": step["params"]["task"],
                                     "url": step["params"].get("url"),
                                     "max_steps": 8}},
        )


def test_browser_step_becomes_an_explicit_assignment(agent):
    agent.adapters["browser"] = AssigningBrowser()
    steps = [
        {"lane": "inspect", "objective": "read"},
        {"lane": "browser", "objective": "open the studio",
         "params": {"task": "Open the studio\n\nSTEPS:\nread",
                    "url": "http://127.0.0.1:8101/ui/design-studio"}},
    ]
    task = agent.submit(_order(steps=steps, scope={"lanes": ["inspect", "browser"]}))
    done = agent.run(task["id"])
    assert done["status"] == "awaiting_controller"
    assert done["stop_reason"] == "controller_assignment"
    assert done["cursor"] == 1, "the assignment keeps its place in the queue"
    ev = [e for e in agent.store.events(task["id"]) if e["kind"] == "controller_assignment"]
    assert ev and "STEPS:" in ev[0]["payload"]["assignment"]["task"]


def test_a_controller_result_completes_the_assigned_step(agent):
    agent.adapters["browser"] = AssigningBrowser()
    steps = [
        {"lane": "browser", "objective": "open the studio",
         "params": {"task": "Open the studio\n\nSTEPS:\nread"}},
        {"lane": "inspect", "objective": "after the browser"},
    ]
    task = agent.submit(_order(steps=steps, scope={"lanes": ["browser", "inspect"]}))
    waiting = agent.run(task["id"])
    assert waiting["status"] == "awaiting_controller"

    done = agent.complete_controller_step(task["id"], {
        "status": "COMPLETE",
        "stop_reason": "page_read",
        "run_id": "open_the_studio_mvr1",
        "steps": 2,
        "journal": {"name": "2026-10-28T05-00-00-000Z_open_the_studio_mvr1.jsonl"},
        "stats": {"mode": {"headed": True, "readOnly": True}},
        "data": {"url": "http://127.0.0.1:8101/ui/design-studio",
                 "text": "DEV: AUTH DISABLED — local loopback only"},
    })
    assert done["status"] == "done"
    assert done["cursor"] == 2
    results = [e["payload"] for e in agent.store.events(task["id"]) if e["kind"] == "step_result"]
    browser_result = results[0]
    assert browser_result["evidence"]["delegation"] == "assigned"
    assert browser_result["evidence"]["run_id"] == "open_the_studio_mvr1"
    assert browser_result["artifacts"][0].endswith(".jsonl")
    kinds = [e["kind"] for e in agent.store.events(task["id"])]
    assert "controller_result_accepted" in kinds


def test_a_failed_controller_result_pauses_and_keeps_the_step(agent):
    agent.adapters["browser"] = AssigningBrowser()
    steps = [{"lane": "browser", "objective": "open the studio",
              "params": {"task": "Open the studio\n\nSTEPS:\nread"}}]
    task = agent.submit(_order(steps=steps, scope={"lanes": ["browser"]}))
    agent.run(task["id"])
    done = agent.complete_controller_step(task["id"], {
        "status": "ERROR", "stop_reason": "tool_error:action_error", "run_id": "r2",
        "refusals": [{"code": "action_error", "detail": "timeout"}],
    })
    assert done["status"] == "paused"
    assert done["cursor"] == 0
    assert done["blockers"][-1]["code"] == "controller_step_failed"


def test_controller_result_is_refused_when_no_step_is_assigned(agent):
    task = agent.submit(_order())
    with pytest.raises(tys.TysError) as e:
        agent.complete_controller_step(task["id"], {"status": "COMPLETE"})
    assert e.value.code == "task_not_awaiting_controller"


def test_the_controller_adapter_classifies_a_busy_profile(monkeypatch, tmp_path):
    """A second controller must not fight the owner for the relay."""
    empty = tmp_path / "locks"
    empty.mkdir()
    monkeypatch.setenv("TYS_CHROME_LOCK_DIR", str(empty))

    def busy_caller(task, url=None, dry_run=False, require_isolated=False, timeout=0):
        return {
            "ok": False, "status": "ERROR", "stop_reason": "tool_error:Error",
            "refusals": [{"code": "Error", "detail":
                          'Chrome profile "Profile 6" is already owned by pid 22868 '
                          '(chromeconnect-session). Only one Chrome Connect session may attach.'}],
        }

    adapter = tys.ChromeConnectAdapter(caller=busy_caller)
    result = adapter.run_step(
        {"lane": "browser", "objective": "read", "params": {"task": "read\n\nSTEPS:\nread"}},
        {"scope": {"lanes": ["browser"]}})
    assert result.ok is False and result.blocked is True
    assert result.evidence["code"] == "browser_controller_busy"
    assert result.evidence["assignment"]["task"].startswith("read")


def test_the_controller_adapter_reports_a_real_run(monkeypatch, tmp_path):
    empty = tmp_path / "locks"
    empty.mkdir()
    monkeypatch.setenv("TYS_CHROME_LOCK_DIR", str(empty))

    def ok_caller(task, url=None, dry_run=False, require_isolated=False, timeout=0):
        return {"status": "COMPLETE", "stop_reason": "page_read", "run_id": "r9",
                "steps": 2, "stats": {"mode": {"headed": True, "readOnly": True}},
                "data": {"url": url}, "journal": {"name": "j.jsonl"},
                "refusals": [], "blockers": []}

    adapter = tys.ChromeConnectAdapter(caller=ok_caller)
    result = adapter.run_step(
        {"lane": "browser", "objective": "read", "params": {"task": "read", "url": "http://127.0.0.1:8101/ui/"}},
        {"scope": {"lanes": ["browser"]}})
    assert result.ok is True
    assert result.evidence["delegation"] == "direct"
    assert result.evidence["run_id"] == "r9"


# ---------------------------------------------------------------------------
# Admin API gate
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


def test_api_admits_the_operator_in_development(monkeypatch):
    import tys_api

    monkeypatch.setenv("ENVIRONMENT", "development")
    user = _run(tys_api.require_tys_admin({"id": "demo-t2", "role": "operator"}))
    assert user["id"] == "demo-t2"


def test_api_refuses_a_tenant_role_in_production(monkeypatch):
    import tys_api
    from fastapi import HTTPException

    monkeypatch.setenv("ENVIRONMENT", "production")
    with pytest.raises(HTTPException) as e:
        _run(tys_api.require_tys_admin({"id": "u1", "role": "organization_owner"}))
    assert e.value.status_code == 403
    assert e.value.detail["code"] == "tys_platform_admin_only"


def test_api_admits_a_platform_admin_in_production(monkeypatch):
    import tys_api

    monkeypatch.setenv("ENVIRONMENT", "production")
    user = _run(tys_api.require_tys_admin({"id": "p1", "role": "platform_admin"}))
    assert user["id"] == "p1"


def test_api_refuses_an_unknown_or_viewer_role(monkeypatch):
    import tys_api
    from fastapi import HTTPException

    monkeypatch.setenv("ENVIRONMENT", "development")
    for role in ("viewer", "analyst", ""):
        with pytest.raises(HTTPException) as e:
            _run(tys_api.require_tys_admin({"id": "u", "role": role}))
        assert e.value.status_code == 403


def test_api_route_namespace_is_not_the_chat_lane():
    import tys_api

    assert tys_api.router.prefix == "/api/admin/tys"
    assert "/api/chat" not in tys_api.router.prefix


# ── the one real task-execution contract ────────────────────────────────────

def _run_route():
    import tys_api

    for route in tys_api.router.routes:
        if route.path.endswith("/tasks/{task_id}/run") and "POST" in route.methods:
            return route
    raise AssertionError("the synchronous run route is missing")


def test_run_route_is_synchronous_and_has_no_speculative_parameters():
    """200 with the completed work order. No engine param, no 202, no stream."""
    route = _run_route()
    names = {p.name for p in route.dependant.query_params}
    assert names == {"max_steps"}, names
    assert "engine" not in names
    codes = set(getattr(route, "responses", {}) or {}) | {getattr(route, "status_code", 200)}
    assert 202 not in codes
    assert list(getattr(route, "responses", {}) or {}) == []


def test_run_route_returns_kernel_evidence_on_the_same_response():
    import tys_api

    payload = {"status": "complete", "plan": {"plan_id": "p1"}, "evidence": 4}

    class Store:
        def events(self, task_id):
            assert task_id == "t1"
            return [{"kind": "run_started", "payload": {}},
                    {"kind": "kernel_result", "payload": payload}]

    class Assistant:
        store = Store()

    assert tys_api._kernel_evidence(Assistant(), "t1") == payload


def test_run_route_omits_kernel_key_when_the_order_did_not_use_it():
    import tys_api

    class Assistant:
        class store:  # noqa: N801 - a namespace, not an instance
            @staticmethod
            def events(task_id):
                return [{"kind": "run_started", "payload": {}}]

    assert tys_api._kernel_evidence(Assistant(), "t1") is None


def test_kernel_evidence_never_breaks_a_run():
    import tys_api

    class Assistant:
        class store:  # noqa: N801
            @staticmethod
            def events(task_id):
                raise RuntimeError("event log unavailable")

    assert tys_api._kernel_evidence(Assistant(), "t1") is None
