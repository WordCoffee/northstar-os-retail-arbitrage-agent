"""Ty's eyes — the vision half of Tys Assistant.

What is under test is not "does a 4B model like this picture". It is the contract
around the model: an absence of evidence is never reported as success, the two
operator switches are dependent, and an off-goal verdict reaches the assistant as
guidance instead of vanishing into a log.

No GPU, no Ollama, no network: every model call is injected.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tys_assistant as tys
from agent_kernel import eye as eyemod
from agent_kernel import verify as verify_mod
from agent_kernel.model import Acceptance


PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def _caller(payload: str, seen: list | None = None):
    def _call(image: bytes, constraint: str) -> str:
        if seen is not None:
            seen.append({"constraint": constraint, "bytes": len(image)})
        return payload
    return _call


def _boom(image: bytes, constraint: str) -> str:
    raise RuntimeError("ollama is not running")


@pytest.fixture()
def assistant(tmp_path):
    return tys.TysAssistant(store=tys.TysStore(str(tmp_path / "q.db")),
                            evidence_dir=str(tmp_path / "evidence"))


@pytest.fixture()
def eye(tmp_path):
    return eyemod.TyEye(enabled=True, caller=_caller('{"pass": true, "reasons": []}'),
                        journal=str(tmp_path / "eyes.jsonl"))


# ---------------------------------------------------------------------------
# The eye's three statuses
# ---------------------------------------------------------------------------

def test_disabled_never_calls_the_model(tmp_path):
    seen: list = []
    disabled = eyemod.TyEye(enabled=False, caller=_caller("{}", seen),
                            journal=str(tmp_path / "e.jsonl"))
    out = disabled.look("build a pouch render", image=PNG,
                        constraint="a stand-up pouch is visible")
    assert out["status"] == eyemod.DISABLED
    assert seen == [], "a switched-off eye must not spend a model call"
    assert out["guidance"] == ""


def test_no_image_is_unverified_not_on_track(eye):
    out = eye.look("build a pouch render", image=None)
    assert out["status"] == eyemod.UNVERIFIED
    assert out["reason"] == "no_image"


def test_missing_file_is_unverified(tmp_path):
    e = eyemod.TyEye(enabled=True, caller=_caller('{"pass": true}'),
                     journal=str(tmp_path / "e.jsonl"))
    out = e.look("goal", image_path=str(tmp_path / "nope.png"))
    assert out["status"] == eyemod.UNVERIFIED
    assert out["reason"] == "image_missing"


def test_pass_is_on_track(eye):
    out = eye.look("build a pouch render", image=PNG,
                   constraint="a stand-up pouch is visible")
    assert out["status"] == eyemod.ON_TRACK
    assert out["guidance"] == ""
    assert out["image_sha256"]


def test_fail_is_off_track_with_the_models_own_reasons(tmp_path):
    e = eyemod.TyEye(
        enabled=True, journal=str(tmp_path / "e.jsonl"),
        caller=_caller('{"pass": false, "reasons": ["the label is blank", '
                       '"the pouch is cropped"], "confidence": 0.8}'))
    out = e.look("build a pouch render", image=PNG,
                 constraint="a labelled pouch, fully visible")
    assert out["status"] == eyemod.OFF_TRACK
    assert "the label is blank" in out["guidance"]
    assert "the pouch is cropped" in out["guidance"]
    assert out["reasons"] == ["the label is blank", "the pouch is cropped"]


def test_model_down_is_unverified_never_on_track(tmp_path):
    e = eyemod.TyEye(enabled=True, caller=_boom, journal=str(tmp_path / "e.jsonl"))
    out = e.look("goal", image=PNG, constraint="a pouch")
    assert out["status"] == eyemod.UNVERIFIED
    assert "RuntimeError" in out["reason"]


def test_prose_answer_is_unverified(tmp_path):
    e = eyemod.TyEye(enabled=True, caller=_caller("It looks fine to me."),
                     journal=str(tmp_path / "e.jsonl"))
    out = e.look("goal", image=PNG, constraint="a pouch")
    assert out["status"] == eyemod.UNVERIFIED


def test_missing_constraint_is_derived_and_labelled(tmp_path):
    seen: list = []
    e = eyemod.TyEye(enabled=True, caller=_caller('{"pass": true}', seen),
                     journal=str(tmp_path / "e.jsonl"))
    out = e.look("build a labelled pouch render", image=PNG)
    assert out["derived_constraint"] is True
    assert "build a labelled pouch render" in seen[0]["constraint"]


def test_every_look_is_journaled(tmp_path):
    journal = tmp_path / "eyes.jsonl"
    e = eyemod.TyEye(enabled=True, caller=_caller('{"pass": true}'), journal=str(journal))
    e.look("goal", image=PNG, constraint="a pouch")
    e.look("goal", image=PNG, constraint="a pouch")
    lines = [json.loads(x) for x in journal.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 2
    assert e.recent(1)[0]["status"] == eyemod.ON_TRACK


def test_artifacts_filters_to_images(tmp_path):
    e = eyemod.TyEye(enabled=False, journal=str(tmp_path / "e.jsonl"))
    assert e.artifacts(["a.png", "b.txt", "c.JPG", "d.mp4"]) == ["a.png", "c.JPG"]


def test_switch_can_be_a_callable(tmp_path):
    flag = {"on": False}
    e = eyemod.TyEye(enabled=lambda: flag["on"], caller=_caller('{"pass": true}'),
                     journal=str(tmp_path / "e.jsonl"))
    assert e.look("goal", image=PNG, constraint="x")["status"] == eyemod.DISABLED
    flag["on"] = True
    assert e.look("goal", image=PNG, constraint="x")["status"] == eyemod.ON_TRACK


# ---------------------------------------------------------------------------
# As an acceptance check
# ---------------------------------------------------------------------------

def _registry_run(tmp_path, payload: str, *, enabled: bool = True):
    path = tmp_path / "shot.png"
    path.write_bytes(PNG)
    reg = verify_mod.VerifierRegistry()
    acc = Acceptance("the render matches the goal", "vision", {
        "path": str(path), "constraint": "a labelled pouch is visible",
        "goal": "build a pouch render", "enabled": enabled,
        "caller": _caller(payload), "journal": str(tmp_path / "e.jsonl"),
    })
    return reg.verify(acc, verify_mod.VerifyContext("s1", "n1"))


def test_acceptance_pass(tmp_path):
    ev = _registry_run(tmp_path, '{"pass": true}')
    assert ev.result == "pass"
    assert ev.verifier == "vision"


def test_acceptance_fail_carries_guidance(tmp_path):
    ev = _registry_run(tmp_path, '{"pass": false, "reasons": ["blank label"]}')
    assert ev.result == "fail"
    assert "blank label" in ev.detail


def test_acceptance_disabled_is_unknown_not_pass(tmp_path):
    ev = _registry_run(tmp_path, '{"pass": true}', enabled=False)
    assert ev.result == "unknown"
    assert "disabled" in ev.detail


def test_acceptance_missing_image_fails(tmp_path):
    reg = verify_mod.VerifierRegistry()
    acc = Acceptance("x", "vision", {"path": str(tmp_path / "gone.png"),
                                     "constraint": "x", "enabled": True})
    assert reg.verify(acc, verify_mod.VerifyContext("s", "n")).result == "fail"


# ---------------------------------------------------------------------------
# The two switches
# ---------------------------------------------------------------------------

def test_defaults(assistant):
    assert assistant.assistant_enabled() is True
    assert assistant.vision_enabled() is False, "eyes are opt-in"


def test_vision_cannot_be_armed_while_the_assistant_is_off(assistant):
    assistant.set_switches(assistant=False)
    with pytest.raises(tys.TysError) as exc:
        assistant.set_switches(vision=True)
    assert exc.value.code == "vision_requires_assistant"
    assert assistant.vision_enabled() is False


def test_switching_the_assistant_off_disarms_vision(assistant):
    assistant.set_switches(vision=True)
    assert assistant.vision_enabled() is True
    assistant.set_switches(assistant=False)
    assert assistant.vision_enabled() is False
    assert assistant.switches()["vision_armed"] is False


def test_switches_round_trip_through_the_store(assistant):
    assistant.set_switches(vision=True)
    fresh = tys.TysAssistant(store=assistant.store, evidence_dir=assistant.evidence_dir)
    assert fresh.vision_enabled() is True


def test_eyes_status_reports_availability(assistant):
    status = assistant.eyes_status()
    assert status["available"] is True
    assert status["enabled"] is False
    assert status["model"]


def test_run_refuses_when_the_assistant_is_off(assistant):
    task = {"title": "t", "objective": "inspect the repo",
            "scope": {"lanes": ["inspect"], "paths": ["README.md"]}}
    saved = assistant.submit(task)
    assistant.set_switches(assistant=False)
    with pytest.raises(tys.TysError) as exc:
        assistant.run(saved["id"])
    assert exc.value.code == "assistant_disabled"


# ---------------------------------------------------------------------------
# Working together: the eye's verdict reaches the step
# ---------------------------------------------------------------------------

class _ImageAdapter(tys.Adapter):
    name = "graphics"

    def __init__(self, path):
        self.path = str(path)
        self.calls = 0

    def run_step(self, step, task):
        self.calls += 1
        return tys.StepResult(True, "rendered", artifacts=[self.path],
                              evidence={"render": "fake"})


def _task(tmp_path, **params):
    return {"id": "task_eye", "cursor": 0, "iteration": 0,
            "objective": "build a labelled pouch render for the lion's mane SKU",
            "scope": {"lanes": ["graphics"]},
            "steps": [{"lane": "graphics", "objective": "render the pouch",
                       "params": params}]}


def _wire(assistant, tmp_path, payload):
    shot = tmp_path / "render.png"
    shot.write_bytes(PNG)
    adapter = _ImageAdapter(shot)
    assistant.adapters["graphics"] = adapter
    assistant.eye = eyemod.TyEye(enabled=True, caller=_caller(payload),
                                 journal=str(tmp_path / "eyes.jsonl"))
    assistant.set_switches(vision=True)
    return adapter, shot


def test_step_records_the_eyes_verdict(assistant, tmp_path):
    adapter, _ = _wire(assistant, tmp_path, '{"pass": true}')
    task = _task(tmp_path)
    result = assistant._execute_step(task, task["steps"][0])
    assert result.ok is True
    assert adapter.calls == 1
    assert result.evidence["eyes"]["status"] == eyemod.ON_TRACK
    kinds = [e["kind"] for e in assistant.store.events(task["id"])]
    assert "eyes_look" in kinds


def test_off_track_guidance_travels_to_the_assistant(assistant, tmp_path):
    _wire(assistant, tmp_path, '{"pass": false, "reasons": ["the label is blank"]}')
    task = _task(tmp_path)
    result = assistant._execute_step(task, task["steps"][0])
    assert result.ok is True, "advisory by default: the step still stands"
    assert result.evidence["eyes"]["status"] == eyemod.OFF_TRACK
    assert "the label is blank" in result.evidence["guidance"]


def test_enforce_lets_the_eye_stop_a_step(assistant, tmp_path):
    _wire(assistant, tmp_path, '{"pass": false, "reasons": ["the pouch is cropped"]}')
    task = _task(tmp_path, eyes_enforce=True)
    result = assistant._execute_step(task, task["steps"][0])
    assert result.ok is False
    assert result.retriable is True
    assert "the pouch is cropped" in result.detail


def test_no_image_means_no_look_and_no_invented_verdict(assistant, tmp_path):
    class _TextAdapter(tys.Adapter):
        name = "coding"

        def run_step(self, step, task):
            return tys.StepResult(True, "wrote a file", artifacts=[str(tmp_path / "a.py")])

    assistant.adapters["coding"] = _TextAdapter()
    assistant.eye = eyemod.TyEye(enabled=True, caller=_boom,
                                 journal=str(tmp_path / "eyes.jsonl"))
    assistant.set_switches(vision=True)
    task = {"id": "task_text", "cursor": 0, "iteration": 0,
            "objective": "fix the importer", "scope": {"lanes": ["coding"]},
            "steps": [{"lane": "coding", "objective": "write the fix", "params": {}}]}
    result = assistant._execute_step(task, task["steps"][0])
    assert "eyes" not in result.evidence
    kinds = [e["kind"] for e in assistant.store.events(task["id"])]
    assert "eyes_look" not in kinds, "no image, no look, no verdict"


def test_disabled_eyes_do_not_look(assistant, tmp_path):
    adapter, _ = _wire(assistant, tmp_path, '{"pass": true}')
    assistant.set_switches(vision=False)
    task = _task(tmp_path)
    result = assistant._execute_step(task, task["steps"][0])
    assert "eyes" not in result.evidence
    assert adapter.calls == 1


# ---------------------------------------------------------------------------
# The admin surface the operator actually flips
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(assistant, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import tys_api

    monkeypatch.setattr(tys_api, "_assistant", lambda: assistant)
    app = FastAPI()
    app.include_router(tys_api.router)
    app.dependency_overrides[tys_api.require_tys_admin] = lambda: {"role": "operator"}
    return TestClient(app)


def test_api_reads_both_switches(client):
    body = client.get("/api/admin/tys/switches").json()
    assert body["switches"]["assistant"] is True
    assert body["switches"]["vision"] is False
    assert body["eyes"]["available"] is True


def test_api_turns_the_eyes_on_then_off(client):
    on = client.post("/api/admin/tys/switches", json={"vision": True})
    assert on.status_code == 200
    assert on.json()["switches"]["vision"] is True
    assert on.json()["eyes"]["enabled"] is True

    off = client.post("/api/admin/tys/switches", json={"vision": False})
    assert off.json()["switches"]["vision"] is False


def test_api_refuses_vision_without_the_assistant(client):
    res = client.post("/api/admin/tys/switches",
                      json={"assistant": False, "vision": True})
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "vision_requires_assistant"


def test_api_rejects_an_unknown_switch(client):
    res = client.post("/api/admin/tys/switches", json={"echo": True})
    assert res.status_code == 400
    assert res.json()["detail"]["code"] == "unknown_switch"


def test_api_voice_never_claims_a_look_that_did_not_happen(client):
    body = client.get("/api/admin/tys/voice").json()
    assert body["persona"].startswith("I am Tys Assistant")
    assert body["lines"] == []
    assert "corpus_learner.py" in body["learning"]["rea_breadth"]["tool"]


def test_persona_calls_the_vision_its_eyes(assistant):
    text = assistant.identity()["persona"]
    assert "My eyes are Ty's Vision" in text
    assert "unverified, never on track" in text

