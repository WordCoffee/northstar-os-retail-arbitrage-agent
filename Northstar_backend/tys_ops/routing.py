"""Intent routing: visual work goes to Flux 3, code stays on the coding model.

The policy is a **routing decision with an audit trail**, not a prompt hint:

* a request about images, graphics, UI styling or rendering is **intercepted**
  and run on the ``graphics`` lane (FLUX 3), never on ``coding`` and never on
  the ComfyUI ``creative`` lane;
* a request about code is left on ``coding``;
* video/animation stays on ``creative`` because FLUX 3 Image Klein is an image
  model — pretending otherwise would silently produce the wrong artefact;
* everything ambiguous is left alone, and the decision plus its reasons is
  recorded so an operator can see why a task moved.

Matching is on word boundaries and graded: a *strong* code signal ("unit test",
"refactor", "endpoint") beats a weak visual word used as context ("the render
lane"), while a *strong* visual signal ("logo", "hero image", "ui styling")
beats code. When both are strong, visual wins — that is the operator's standing
instruction.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

GRAPHICS = "graphics"
CODING = "coding"
CREATIVE = "creative"

#: Unambiguous visual-output requests.
_STRONG_VISUAL = (
    "image", "images", "graphic", "graphics", "artwork", "illustration",
    "logo", "mockup", "mock-up", "banner", "thumbnail", "poster", "flyer",
    "photo", "photograph", "hero image", "product shot", "ui styling",
    "style guide", "visual design", "brand asset", "label design",
    "packaging design", "screenshot", "design concept", "concept art",
    "key art", "visual identity", "theme the ui", "icon set", "wallpaper",
    "colorway", "typography", "palette", "text-to-image", "generated image",
    "render a", "render the", "render an", "generate an image",
    "generate a image", "image generation", "design a", "design the",
)

#: Words that *can* mean visual work but are also ordinary engineering nouns.
_WEAK_VISUAL = (
    "render", "rendering", "visual", "visuals", "styling", "restyle",
    "layout", "wireframe", "texture", "design", "illustrate",
)

#: Motion work. FLUX 3 cannot do this; it stays on the existing creative lane.
_VIDEO_TERMS = (
    "video", "clip", "mp4", "animation", "animate", "animated", "timelapse",
    "time-lapse", "gif", "footage", "motion",
)

#: Unambiguous code work: these are never sent to an image model.
_STRONG_CODE = (
    "code", "coding", "refactor", "function", "class", "module", "endpoint",
    "api", "schema", "migration", "database", "sql", "query", "pytest",
    "unit test", "integration test", "bug", "stack trace", "traceback",
    "exception", "compile", "lint", "typescript", "javascript", "python",
    "react component", "dockerfile", "hotfix", "pull request", "regression",
    "syntax", "import error",
)


def _compile(terms: Iterable[str]) -> "re.Pattern[str]":
    ordered = sorted(set(terms), key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(re.escape(term) for term in ordered) + r")\b",
                      re.IGNORECASE)


_STRONG_VISUAL_RE = _compile(_STRONG_VISUAL)
_WEAK_VISUAL_RE = _compile(_WEAK_VISUAL)
_VIDEO_RE = _compile(_VIDEO_TERMS)
_STRONG_CODE_RE = _compile(_STRONG_CODE)


def _hits(pattern: "re.Pattern[str]", text: str) -> List[str]:
    return sorted({match.group(1).lower() for match in pattern.finditer(text or "")})


def classify(text: str) -> Dict[str, Any]:
    """Classify one objective. Returns lane ``None`` when nothing matches."""
    strong_visual = _hits(_STRONG_VISUAL_RE, text)
    weak_visual = _hits(_WEAK_VISUAL_RE, text)
    video = _hits(_VIDEO_RE, text)
    strong_code = _hits(_STRONG_CODE_RE, text)
    visual_signals = strong_visual + [t for t in weak_visual if t not in strong_visual]

    base = {"visual_terms": visual_signals, "code_terms": strong_code,
            "video_terms": video}

    # Motion is a different engine, and saying "video" also says "render".
    if video and not strong_visual:
        return {"lane": CREATIVE, "intent": "video", "signals": video,
                "reason": "motion media stays on the creative lane "
                          "(FLUX 3 is image-only)", **base}

    if strong_visual:
        # Strong visual output wins even next to code words: the operator asked
        # for the visual artefact, and Flux is the specialist for it.
        return {"lane": GRAPHICS, "intent": "image", "signals": strong_visual,
                "reason": "visual request intercepted before the coding model",
                **base}

    if strong_code:
        return {"lane": CODING, "intent": "code", "signals": strong_code,
                "reason": "code work stays on the coding model", **base}

    if visual_signals:
        return {"lane": GRAPHICS, "intent": "visual", "signals": visual_signals,
                "reason": "only visual signals present; routed to graphics", **base}

    return {"lane": None, "intent": "unknown", "signals": [],
            "reason": "no visual or code signal; lane left to the caller", **base}


def is_visual(text: str) -> bool:
    return classify(text)["lane"] == GRAPHICS


def is_media(text: str) -> bool:
    return classify(text)["lane"] in (GRAPHICS, CREATIVE)


def _step_text(step: Dict[str, Any]) -> str:
    parts = [str(step.get("objective") or "")]
    params = step.get("params") or {}
    for key in ("prompt", "instruction", "description", "style", "label"):
        if isinstance(params.get(key), str):
            parts.append(params[key])
    return " ".join(parts)


def apply_to_steps(steps: Iterable[Dict[str, Any]],
                   objective: str = "") -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Rewrite **visual** steps onto the graphics lane. Everything else is left.

    Routing is an interception, not a re-planner: an `inspect` step stays
    `inspect`, a `coding` step stays `coding`. Only the operating instruction —
    visual work goes to FLUX 3 — moves a step.
    """
    out: List[Dict[str, Any]] = []
    interceptions: List[Dict[str, Any]] = []
    for raw in steps:
        step = dict(raw)
        decision = classify(_step_text(step))
        previous = str(step.get("lane") or "").strip().lower()
        if decision["lane"] == GRAPHICS and previous != GRAPHICS:
            step["lane"] = GRAPHICS
            interceptions.append({
                "scope": "step",
                "objective": str(step.get("objective") or "")[:200],
                "from": previous,
                "to": GRAPHICS,
                "intent": decision["intent"],
                "signals": decision["signals"],
                "reason": decision["reason"],
            })
        out.append(step)
    return out, interceptions


def route_work_order(work_order: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Intercept a work order before it is queued.

    Adds ``graphics`` to ``scope.lanes`` when a visual step is routed there, so
    the rewritten lane is inside the order's own scope rather than an escalation.
    """
    order = dict(work_order)
    scope = dict(order.get("scope") or {})
    lanes = list(scope.get("lanes") or [])

    interceptions: List[Dict[str, Any]] = []
    objective_decision = classify(str(order.get("objective") or ""))
    if objective_decision["lane"] == GRAPHICS and GRAPHICS not in lanes:
        lanes.append(GRAPHICS)
        interceptions.append({
            "scope": "scope",
            "objective": str(order.get("objective") or "")[:200],
            "from": "scope",
            "to": GRAPHICS,
            "intent": objective_decision["intent"],
            "signals": objective_decision["signals"],
            "reason": "added graphics lane for a visual objective",
        })

    steps, step_hits = apply_to_steps(order.get("steps") or [],
                                      str(order.get("objective") or ""))
    interceptions.extend(step_hits)
    if any(step.get("lane") == GRAPHICS for step in steps) and GRAPHICS not in lanes:
        lanes.append(GRAPHICS)

    if lanes:
        scope["lanes"] = lanes
    order["scope"] = scope
    order["steps"] = steps
    return order, interceptions


def policy_summary() -> Dict[str, Any]:
    """The routing table, for the state endpoint and the UI."""
    return {
        "graphics": {
            "executor": "FLUX 3 Image Klein (direct)",
            "intercepts": ["visual graphics", "UI styling", "image generation",
                           "rendering"],
            "never": ["coding model", "ComfyUI creative lane"],
        },
        "coding": {
            "executor": "Qwen3.8-27B llama.cpp worker",
            "scope": ["code", "tests", "refactors", "repository edits"],
        },
        "creative": {
            "executor": "existing studio/ComfyUI services",
            "scope": ["video", "animation", "motion"],
            "note": "FLUX 3 is image-only; motion media is not intercepted",
        },
        "precedence": "strong visual beats code; strong code beats weak visual; video wins over both",
        "audit": "every interception is recorded as a routing_intercepted event",
    }
