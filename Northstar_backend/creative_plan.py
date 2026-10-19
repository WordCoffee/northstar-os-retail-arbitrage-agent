"""Creative plan & confirmation contract (Bojo).

The flow the operator specified:

    request ──▶ plan (quick | detailed) ──▶ credits quote ──▶ operator chooses
                                                            ├── cancel
                                                            ├── edit the plan
                                                            ├── generate DRAFT   (cheaper)
                                                            └── generate FINAL   (most credits)

This module builds the plan, prices it, and validates the CHOICE. It never calls a
model and never moves credits: execution belongs to the existing creative tools, and
the charge belongs to ``credit_ledger.reserve/commit``.

Honesty contract
----------------
* Every step names a tool that is ACTUALLY registered. A step whose tool is not
  wired is marked ``available: False`` and listed as an unknown — the plan never
  promises a capability the repository does not have.
* ``unknowns`` lists what cannot be determined from the request (product facts,
  dimensions, brand assets) instead of inventing them.
* Inferred fields are labelled ``inferred`` and carry a confidence, never presented
  as if the operator stated them.
"""
from __future__ import annotations

import hashlib
import os
import sys
from typing import Any, Dict, List, Optional

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import creative_pricing as pricing  # noqa: E402

# ── job inference from the request ───────────────────────────────────────────
_RULES = (
    ("video_long", ("60s", "60 second", "long video", "minute video", "explainer")),
    ("video_short", ("video", "clip", "reel", "tiktok", "short-form", "15s", "motion")),
    ("package_design", ("package", "packaging", "pouch", "carton", "box", "dieline",
                        "stand-up", "sachet", "bottle label layout", "unboxing")),
    ("label_design", ("label", "sticker", "wrap", "print-ready", "print ready")),
    ("ad_creative", ("ad ", "ads", "advert", "campaign", "creative set", "facebook ad",
                     "meta ad", "promo")),
    ("listing_image", ("listing image", "main image", "white background", "amazon image",
                       "hero image", "product page")),
    ("portrait_photo", ("holding", "in hand", "person", "model", "lifestyle photo",
                        "someone using", "ugc")),
    ("product_shot", ("product photo", "product shot", "studio", "photograph", "render")),
)

# ── plan steps per job (tool, what it does) ─────────────────────────────────
_STEPS: Dict[str, List[Dict[str, str]]] = {
    "portrait_photo": [
        {"tool": "design_brief", "what": "shot direction: subject, pose, light, lens, background"},
        {"tool": "generate_image", "what": "render the portrait with the product in hand"},
    ],
    "product_shot": [
        {"tool": "design_brief", "what": "studio direction: surface, light, angle, palette"},
        {"tool": "generate_image", "what": "render the product photograph"},
    ],
    "listing_image": [
        {"tool": "design_brief", "what": "marketplace shot list and compliance notes"},
        {"tool": "generate_image", "what": "render the listing image on a clean background"},
    ],
    "ad_creative": [
        {"tool": "design_brief", "what": "angle, hook, copy blocks and visual direction"},
        {"tool": "generate_image", "what": "render the primary ad visual"},
        {"tool": "generate_image", "what": "render the variant visual"},
    ],
    "label_design": [
        {"tool": "list_templates", "what": "pick the label template and editable params"},
        {"tool": "design_brief", "what": "palette, type hierarchy, mandatory copy blocks"},
        {"tool": "create_dieline", "what": "build the dimension-true label artwork"},
        {"tool": "generate_image", "what": "render the label surface/hero"},
        {"tool": "_prepress", "what": "ICC/CMYK conversion, soft proof, ink-limit check"},
    ],
    "package_design": [
        {"tool": "list_templates", "what": "choose the pouch/carton template"},
        {"tool": "design_brief", "what": "structure brief: dieline, palette, copy blocks, negatives"},
        {"tool": "create_dieline", "what": "build the dimension-true dieline (print-ready SVG/PDF)"},
        {"tool": "generate_image", "what": "render the hero surface"},
        {"tool": "generate_image", "what": "render supporting angles"},
        {"tool": "_prepress", "what": "ICC/CMYK conversion, soft proof, gamut dE, ink limit"},
    ],
    "video_short": [
        {"tool": "design_brief", "what": "storyboard: 3 beats, motion notes, on-screen copy"},
        {"tool": "generate_image", "what": "render the keyframe"},
        {"tool": "_video", "what": "render the 15s motion clip"},
    ],
    "video_long": [
        {"tool": "design_brief", "what": "storyboard: 6-8 beats with timing"},
        {"tool": "generate_image", "what": "render keyframes"},
        {"tool": "_video", "what": "render the 60s motion clip"},
    ],
}

_DETAILED_EXTRAS = (
    {"tool": "design_brief", "what": "prompt scaffold: subject, style, camera, lighting, negatives"},
    {"tool": "generate_image", "what": "render a second direction to compare"},
    {"tool": "_qc", "what": "check text, logo, proportions and claims before delivery"},
)


def _registered() -> set:
    try:
        import chat_tools
        return set(chat_tools.TOOLS)
    except Exception:  # noqa: BLE001 - a plan without the registry is still honest
        return set()


def infer_job(request: str, media: str = "image") -> Dict[str, Any]:
    """Best-guess job class, with the confidence and the evidence for it."""
    text = f" {(request or '').lower()} "
    for job, needles in _RULES:
        for needle in needles:
            if needle in text:
                if media == "video" and not job.startswith("video"):
                    continue                      # a video request stays in the video lane
                if media == "image" and job.startswith("video"):
                    continue
                return {"job": job, "confidence": 0.9, "matched": needle,
                        "reason": f"matched {needle!r} in the request"}
    fallback = "video_short" if media == "video" else "product_shot"
    return {"job": fallback, "confidence": 0.5, "matched": None,
            "reason": f"no job keyword matched; defaulted to {fallback} for {media}"}


def build_plan(request: str, *, media: str = "image", detail: str = "quick",
               count: int = 1, subscription: str = "foundation",
               pricing_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build the plan the operator confirms. Pure: no model call, no charge."""
    if media not in pricing.MEDIA:
        raise ValueError(f"unknown media {media!r}")
    if detail not in ("quick", "detailed"):
        raise ValueError("detail must be 'quick' or 'detailed'")

    guess = infer_job(request, media)
    job = guess["job"]
    registered = _registered()

    steps: List[Dict[str, Any]] = []
    unknowns: List[str] = []
    for spec in _STEPS[job]:
        tool = spec["tool"]
        available = (tool in registered) if not tool.startswith("_") else False
        steps.append({"tool": tool, "what": spec["what"], "available": available})
        if not available and tool.startswith("_"):
            unknowns.append(f"'{spec['what']}' runs in the creative pipeline, not as a chat tool")
        elif not available:
            unknowns.append(f"tool '{tool}' is not registered in this build")

    if detail == "detailed":
        for spec in _DETAILED_EXTRAS:
            available = spec["tool"] in registered if not spec["tool"].startswith("_") else False
            steps.append({"tool": spec["tool"], "what": spec["what"], "available": available})

    # What a plan cannot know from the request — named, never invented.
    low = (request or "").lower()
    if not any(k in low for k in ("oz", "g ", "ml", "mm", "cm", "inch", "count", "ct", "pack")):
        unknowns.append("finished size / fill weight is not stated")
    if "brand" not in low and "logo" not in low:
        unknowns.append("brand assets (logo, palette, fonts) are not referenced")
    if job in ("label_design", "package_design") and "ingredient" not in low:
        unknowns.append("mandatory label copy (ingredients, net qty) is not provided")

    options = {}
    for quality in pricing.QUALITIES:
        q = pricing.quote_for_plan(subscription, job, quality, count, pricing_data)
        options[quality] = {
            "quality": quality,
            "credits": q["credits"],
            "real_cost_usd": q["real_cost_usd"],
            "allowed": q["allowed"],
            "reason": q["reason"],
            "label": "First draft - quick look, great but not frontier"
                     if quality == "draft" else "Final - highest quality",
        }

    plan_id = "plan_" + hashlib.sha1(
        f"{request}|{job}|{media}|{detail}|{count}|{subscription}".encode("utf-8")
    ).hexdigest()[:16]

    return {
        "ok": True,
        "plan_id": plan_id,
        "request": request,
        "media": media,
        "detail": detail,
        "count": count,
        "subscription": subscription,
        "job": job,
        "job_label": pricing.JOBS[job]["label"],
        "inference": guess,
        "steps": steps,
        "unknowns": unknowns,
        "options": options,
        "summary": (f"{pricing.JOBS[job]['label']} ({media}, {detail} plan, {count}x) - "
                    f"draft {options['draft']['credits']} credits, "
                    f"final {options['final']['credits']} credits."),
    }


ACTIONS = ("cancel", "edit", "draft", "final")

# ── in-process plan registry ────────────────────────────────────────────────
# A plan is CONFIRMED in a later turn, so the card's action must find it again.
# Deliberately per-process: a restart forgets open plans (they are cheap to
# rebuild) instead of persisting a decision surface we would have to migrate.
_PLANS: Dict[str, Dict[str, Any]] = {}
MAX_OPEN_PLANS = 200


def remember(plan: Dict[str, Any]) -> str:
    if len(_PLANS) >= MAX_OPEN_PLANS:
        _PLANS.pop(next(iter(_PLANS)), None)      # drop the oldest
    _PLANS[plan["plan_id"]] = plan
    return plan["plan_id"]


def get(plan_id: str) -> Optional[Dict[str, Any]]:
    return _PLANS.get(plan_id)


def forget(plan_id: str) -> bool:
    return _PLANS.pop(plan_id, None) is not None


def open_plans() -> List[str]:
    return sorted(_PLANS)


def confirm(plan: Dict[str, Any], action: str) -> Dict[str, Any]:
    """Validate the operator's choice. Returns the decision, never executes it."""
    if action not in ACTIONS:
        raise ValueError(f"unknown action {action!r}; expected one of {ACTIONS}")
    if not plan or not plan.get("plan_id"):
        raise ValueError("a plan with a plan_id is required")
    if action == "cancel":
        return {"ok": True, "action": "cancel", "plan_id": plan["plan_id"],
                "credits": 0, "reserve": None,
                "message": "Cancelled. No credits were held."}
    if action == "edit":
        return {"ok": True, "action": "edit", "plan_id": plan["plan_id"],
                "credits": 0, "reserve": None,
                "message": "Send the edits; the plan will be rebuilt and re-quoted."}

    quality = "draft" if action == "draft" else "final"
    option = (plan.get("options") or {}).get(quality) or {}
    if not option.get("allowed"):
        return {"ok": False, "action": action, "plan_id": plan["plan_id"],
                "credits": 0, "reserve": None,
                "error": option.get("reason") or f"{quality} is not available on this tier"}
    return {
        "ok": True,
        "action": action,
        "plan_id": plan["plan_id"],
        "quality": quality,
        "job": plan.get("job"),
        "credits": option["credits"],
        "reserve": {"class": "creative", "amount": option["credits"],
                    "action": f"creative:{plan.get('job')}:{quality}",
                    "idempotency_key": f"{plan['plan_id']}:{quality}"},
        "instruction": {
            "job": plan.get("job"), "quality": quality, "count": plan.get("count", 1),
            "request": plan.get("request"),
        },
        "message": (f"{quality.title()} approved for {option['credits']} credits. "
                    "The ledger hold is the caller's to make."),
    }


def render_card(plan: Dict[str, Any]) -> Dict[str, Any]:
    """The chat card Bojo shows: plan, cost per option, and four actions."""
    opts = plan.get("options") or {}
    rows = [{"label": "Job", "value": plan.get("job_label", "")},
            {"label": "Media", "value": plan.get("media", "")},
            {"label": "Plan", "value": plan.get("detail", "")}]
    if plan.get("unknowns"):
        rows.append({"label": "Needs from you",
                     "value": "; ".join(plan["unknowns"][:3])})
    actions = []
    for action, quality in (("draft", "draft"), ("final", "final")):
        o = opts.get(quality) or {}
        actions.append({
            "id": action,
            "label": "Generate draft" if action == "draft" else "Generate final",
            "credits": o.get("credits"),
            "enabled": bool(o.get("allowed")),
            "note": o.get("label", "") if o.get("allowed") else (o.get("reason") or ""),
        })
    actions.append({"id": "edit", "label": "Edit plan", "credits": 0, "enabled": True})
    actions.append({"id": "cancel", "label": "Cancel", "credits": 0, "enabled": True})
    return {
        "kind": "generation_plan",
        "plan_id": plan.get("plan_id"),
        "job": plan.get("job"),
        "media": plan.get("media"),
        "title": f"Plan ready - {plan.get('job_label', 'creative job')}",
        "rows": rows,
        "options": actions,
        "steps": plan.get("steps", []),
        "action": {"label": "Generate draft", "message": "generate the draft"},
    }
