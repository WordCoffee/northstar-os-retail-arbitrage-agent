"""Routing tests: visual work to FLUX 3, code on the coding model.

The rule under test is an interception, so most assertions are about *where a
step ended up* and *what the audit trail says*, not about a prompt string.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tys_assistant as tys
from tys_ops import graphics, routing


@pytest.fixture()
def assistant(tmp_path):
    return tys.TysAssistant(store=tys.TysStore(str(tmp_path / "q.db")),
                            evidence_dir=str(tmp_path / "evidence"))


# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,lane,intent", [
    ("generate a hero image for the lion's mane pouch", routing.GRAPHICS, "image"),
    ("design a new label for the 6 oz jar", routing.GRAPHICS, "image"),
    ("restyle the dashboard with a warmer palette", routing.GRAPHICS, "image"),
    ("render the product shot at 1024x1024", routing.GRAPHICS, "image"),
    ("ui styling pass on the settings screen", routing.GRAPHICS, "image"),
    ("refactor the checkout endpoint", routing.CODING, "code"),
    ("fix the stack trace in the importer", routing.CODING, "code"),
    ("write a unit test for the render lane", routing.CODING, "code"),
    ("compose a 12s clip of the pouch rotating", routing.CREATIVE, "video"),
])
def test_classification_routes(text, lane, intent):
    decision = routing.classify(text)
    assert decision["lane"] == lane
    assert decision["intent"] == intent
    assert decision["reason"]


def test_unknown_text_is_left_alone():
    decision = routing.classify("summarise yesterday's queue")
    assert decision["lane"] is None
    assert routing.is_visual("summarise yesterday's queue") is False


def test_strong_code_beats_a_contextual_visual_word():
    # "render lane" is an engineering noun here, not a request for an image.
    assert routing.classify("add a regression test for the render lane")["lane"] == routing.CODING


def test_visual_wins_when_both_are_present():
    decision = routing.classify("build the logo and wire the endpoint")
    assert decision["lane"] == routing.GRAPHICS
    assert "endpoint" in decision["code_terms"]


# ---------------------------------------------------------------------------
# work-order rewriting
# ---------------------------------------------------------------------------

def test_work_order_rewrite_adds_graphics_and_records_why():
    order, hits = routing.route_work_order({
        "objective": "produce the pouch hero image",
        "scope": {"lanes": ["coding"]},
        "steps": [{"lane": "coding", "objective": "render the hero image",
                   "params": {"prompt": "lion's mane pouch on stone"}}],
    })
    assert order["steps"][0]["lane"] == routing.GRAPHICS
    assert routing.GRAPHICS in order["scope"]["lanes"]
    assert hits and any(hit["to"] == routing.GRAPHICS for hit in hits)
    step_hits = [hit for hit in hits if hit["scope"] == "step"]
    assert step_hits[0]["from"] == "coding"


def test_coding_step_is_not_moved_by_a_visual_objective():
    order, hits = routing.route_work_order({
        "objective": "generate the hero image and document it",
        "scope": {"lanes": ["coding", "graphics"]},
        "steps": [{"lane": "coding", "objective": "refactor the exporter module"}],
    })
    assert order["steps"][0]["lane"] == "coding"
    assert hits == []


def test_video_steps_stay_creative():
    order, _ = routing.route_work_order({
        "objective": "render a 12s product clip",
        "scope": {"lanes": ["creative"]},
        "steps": [{"lane": "creative", "objective": "animate the pouch turntable"}],
    })
    assert order["steps"][0]["lane"] == "creative"


# ---------------------------------------------------------------------------
# interception in the assistant
# ---------------------------------------------------------------------------

def test_submit_intercepts_visual_step_and_audits_it(assistant):
    task = assistant.submit({
        "objective": "create the pouch hero image",
        "scope": {"lanes": ["coding"]},
        "steps": [{"lane": "coding", "objective": "generate a hero image",
                   "params": {"prompt": "pouch on stone"}}],
    })
    assert task["steps"][0]["lane"] == "graphics"
    assert "graphics" in task["scope"]["lanes"]
    assert task.get("routing")
    events = [e["kind"] for e in assistant.store.events(task["id"])]
    assert "routing_intercepted" in events


class StubOrchestrator:
    MODEL = "stub-planner"

    def __init__(self, steps):
        self.steps = steps

    def available(self):
        return {"adapter": "orchestrator", "available": True, "model": self.MODEL}

    def plan(self, task):
        return ([dict(step) for step in self.steps], "{}")


def test_planner_cannot_route_visual_work_to_coding(assistant):
    calls = []

    def generator(prompt, width, height, steps, seed):
        calls.append(prompt)
        return {"artifacts": ["data/tys/graphics/hero.png"]}

    assistant.orchestrator = StubOrchestrator([
        {"lane": "coding", "objective": "render the pouch hero image",
         "params": {"prompt": "hero image"}},
    ])
    assistant.adapters["graphics"] = tys.GraphicsAdapter(generator=generator)
    task = assistant.submit({"objective": "create a hero image for the pouch",
                             "scope": {"lanes": ["coding"]},
                             "planning": "orchestrator"})
    finished = assistant.run(task["id"])
    assert finished["status"] == "done"
    assert finished["steps"][0]["lane"] == "graphics"
    assert calls == ["hero image"]
    events = [e["kind"] for e in assistant.store.events(task["id"])]
    assert "routing_intercepted" in events


def test_coding_lane_refuses_visual_step_even_if_it_slips_through(assistant):
    step = {"lane": "coding", "objective": "generate a logo",
            "params": {"prompt": "a logo"}}
    result = tys.CodingWorkerAdapter(runner=lambda p, c: "should not run").run_step(
        step, {"scope": {"lanes": ["coding"]}})
    assert result.blocked is True
    assert result.detail == "visual_requires_graphics_lane"


def test_creative_lane_refuses_image_work(assistant):
    step = {"lane": "creative", "objective": "render a hero image",
            "params": {"prompt": "hero"}}
    result = tys.CreativeWorkerAdapter(generator=lambda **kw: {"assets": []}).run_step(
        step, {"scope": {"lanes": ["creative"]}})
    assert result.blocked is True
    assert result.detail == "visual_requires_graphics_lane"


def test_creative_lane_still_accepts_video(assistant):
    step = {"lane": "creative", "objective": "animate a 12s product clip",
            "params": {"prompt": "turntable"}}
    result = tys.CreativeWorkerAdapter(generator=lambda **kw: {"assets": ["clip.mp4"]}).run_step(
        step, {"scope": {"lanes": ["creative"]}})
    assert result.ok is True


# ---------------------------------------------------------------------------
# graphics lane + FLUX 3 client
# ---------------------------------------------------------------------------

def test_graphics_adapter_returns_artifacts(assistant):
    adapter = tys.GraphicsAdapter(generator=lambda **kw: {"artifacts": ["hero.png"]})
    result = adapter.run_step({"lane": "graphics", "objective": "render a hero image",
                               "params": {"prompt": "hero"}}, {})
    assert result.ok is True
    assert result.artifacts == ["hero.png"]
    assert result.evidence["engine"] == "flux3"


def test_graphics_adapter_requires_a_prompt(assistant):
    result = tys.GraphicsAdapter().run_step(
        {"lane": "graphics", "objective": "", "params": {}}, {})
    assert result.ok is False
    assert result.blocked is True


def test_flux3_status_is_honest_when_weights_are_missing(monkeypatch):
    monkeypatch.setattr(graphics, "DEFAULT_UNET", "not-installed.safetensors")
    monkeypatch.setenv("FLUX3_SERVER_URL", "http://127.0.0.1:9")
    report = graphics.status()
    assert report["available"] is False
    assert report["weights"]["present"] is False
    assert "flux3_" in report["detail"]


def test_flux3_status_reports_the_installed_bundle():
    """On this host the FLUX 3 bundle is installed; the endpoint is separate."""
    report = graphics.status()
    assert report["weights"]["present"] is True
    assert report["model"].startswith("flux-3")


def test_generate_refuses_without_falling_back_to_comfy(monkeypatch):
    monkeypatch.setenv("FLUX3_SERVER_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("STUDIO_FLUX3_MODEL", "missing.safetensors")
    with pytest.raises(graphics.GraphicsError) as excinfo:
        graphics.generate("a hero image")
    assert excinfo.value.code == "flux3_unavailable"


def test_generate_requires_a_prompt(monkeypatch):
    with pytest.raises(graphics.GraphicsError) as excinfo:
        graphics.generate("   ")
    assert excinfo.value.code == "prompt_required"


# ---------------------------------------------------------------------------
# kernel lane awareness
# ---------------------------------------------------------------------------

def test_graphics_adapter_suspends_competing_engines_before_rendering(monkeypatch):
    order = []
    monkeypatch.setattr(graphics, "status",
                        lambda: {"available": True, "detail": "ok",
                                 "model": "flux-3-image-klein"})
    monkeypatch.setattr(graphics, "suspend_competing_engines",
                        lambda: (order.append("suspend"),
                                 {"ollama_unloaded": [], "coding_worker": "stopped"})[1])

    class Lock:
        def acquire(self, timeout=None):
            order.append("lock")
            return True

        def release(self):
            order.append("release")

    monkeypatch.setattr(graphics, "gpu_lock", lambda: Lock())

    def fake_generate(prompt, **kwargs):
        order.append("generate")
        return {"artifacts": ["hero.png"], "model": "flux-3-image-klein",
                "width": 1024, "height": 1024, "steps": 28, "seed": None}

    monkeypatch.setattr(graphics, "generate", fake_generate)
    result = tys.GraphicsAdapter().run_step(
        {"lane": "graphics", "objective": "render a hero image",
         "params": {"prompt": "hero"}}, {})
    assert result.ok is True
    assert order == ["suspend", "lock", "generate", "release"]


def test_graphics_adapter_does_not_suspend_when_flux_is_unavailable(monkeypatch):
    called = {"suspend": 0}
    monkeypatch.setattr(graphics, "status",
                        lambda: {"available": False,
                                 "detail": "flux3_weights_not_installed"})
    monkeypatch.setattr(graphics, "suspend_competing_engines",
                        lambda: called.__setitem__("suspend",
                                                   called["suspend"] + 1) or {})
    result = tys.GraphicsAdapter().run_step(
        {"lane": "graphics", "objective": "render a hero image",
         "params": {"prompt": "hero"}}, {})
    assert result.ok is False
    assert result.blocked is True
    assert called["suspend"] == 0


def test_kernel_accepts_the_graphics_lane():
    from agent_kernel.model import NODE_KINDS
    from agent_kernel.kernel import LANE_TOOL
    from agent_kernel.tys_adapter import VALID_LANES, work_order_to_plan

    assert "graphics" in NODE_KINDS
    assert LANE_TOOL["graphics"] == "graphics_generate"
    plan = work_order_to_plan({
        "objective": "render the hero image",
        "scope": {"lanes": ["graphics"]},
        "steps": [{"lane": "graphics", "objective": "render the hero image"}],
    })
    assert plan.nodes[0].lane == "graphics"
    assert "scope:graphics" in plan.constraints


def test_identity_declares_the_interception(assistant):
    identity = assistant.identity()
    assert identity["routing"]["graphics"].startswith("FLUX 3")
    assert identity["interception"]["visual"] == "graphics"
    assert "coding" in identity["interception"]["never_for_visual"]
