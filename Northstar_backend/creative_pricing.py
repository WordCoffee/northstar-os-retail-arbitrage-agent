"""Creative job pricing — job-scaled credits, margin-safe by construction.

Extends the existing credit ledger (``credit_ledger.py``) and cost model
(``cost_model.py``) with the piece the operator asked for: **a price per creative
job that scales with the work**, in the in-house currency, so a portrait of a
person holding a product costs far less than a full package design.

Money model (all values are real, not invented)
-----------------------------------------------
* ``shared/usage-caps.json`` is the single source of truth for the credit rate
  ($0.0078/credit) and the model unit costs (image_v1 $0.015, image_v2 $0.03,
  image_v3 $0.08, Wan 15s $0.75).
* A job's real cost = model passes + a small orchestration allowance per pipeline
  step (planning, brief, dieline, prepress, QC) at the ``post`` unit cost.
* Credits are priced so the REAL cost sits at ``TARGET_MARGIN`` (68%) of the
  credit value charged — inside the repository's existing 60–80% band. Because a
  plan's monthly allotment is worth exactly its price in credits, a member who
  spends their whole allowance on one job class still leaves the tier at ≥60%
  margin. No tier can be drained into a loss by heavy creative use.

Honesty rules
-------------
* Unknown job classes or quality levels fail closed (raise ``ValueError``).
* Nothing here calls a model, reads a wallet or writes a ledger row. It is a
  quote: ``credits`` is what a caller *would* reserve.
* Tier access is explicit data (``TIER_ACCESS``), not a hidden conditional, and a
  test asserts every tier can afford a meaningful number of its allowed jobs.
"""
from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, Optional, Tuple

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CAPS_PATH = os.path.join(_REPO_ROOT, "shared", "usage-caps.json")

# Fallbacks mirror shared/usage-caps.json exactly; a test asserts they agree.
DEFAULT_CREDIT_RATE_USD = 0.0078
DEFAULT_UNIT_COSTS = {
    "image_v1": 0.015, "image_v2": 0.03, "image_v3": 0.08,
    "video_wan_15s": 0.75, "post": 0.002,
}

TARGET_MARGIN = 0.68            # inside the repo's 60-80% band (cost_model.py)
MARGIN_FLOOR = 0.60
MARGIN_CEILING = 0.80

QUALITIES = ("draft", "final")
MEDIA = ("image", "video")

# ── job catalogue ────────────────────────────────────────────────────────────
# `passes` = (model_key, count) per quality. `steps` = orchestration steps.
JOBS: Dict[str, Dict[str, Any]] = {
    "portrait_photo": {
        "label": "Ultra-realistic person holding the product",
        "media": "image",
        "passes": {"draft": (("image_v1", 1),), "final": (("image_v2", 1),)},
        "steps": {"draft": 3, "final": 5},
    },
    "product_shot": {
        "label": "Studio product photograph",
        "media": "image",
        "passes": {"draft": (("image_v1", 1),), "final": (("image_v2", 1),)},
        "steps": {"draft": 3, "final": 5},
    },
    "listing_image": {
        "label": "Marketplace listing image",
        "media": "image",
        "passes": {"draft": (("image_v1", 1),), "final": (("image_v2", 1),)},
        "steps": {"draft": 4, "final": 6},
    },
    "ad_creative": {
        "label": "Ad creative set",
        "media": "image",
        "passes": {"draft": (("image_v1", 2),), "final": (("image_v2", 2),)},
        "steps": {"draft": 5, "final": 8},
    },
    "label_design": {
        "label": "Product label (print-ready)",
        "media": "image",
        "passes": {"draft": (("image_v1", 1),), "final": (("image_v2", 1),)},
        # Prepress is the expensive part in real life: ICC/CMYK conversion, soft
        # proof, gamut dE, ink-limit and safe-area checks on top of the render.
        "steps": {"draft": 10, "final": 24},
    },
    "package_design": {
        "label": "Package / pouch / carton design (print-ready)",
        "media": "image",
        "passes": {"draft": (("image_v2", 1), ("image_v1", 2)),
                   "final": (("image_v3", 1), ("image_v2", 2))},
        "steps": {"draft": 12, "final": 18},
    },
    "video_short": {
        "label": "Short product video (15s)",
        "media": "video",
        "passes": {"draft": (("video_wan_15s", 1),), "final": (("video_wan_15s", 2),)},
        "steps": {"draft": 6, "final": 9},
    },
    "video_long": {
        "label": "Longer product video (60s)",
        "media": "video",
        "passes": {"draft": (("video_wan_15s", 4),), "final": (("video_wan_15s", 6),)},
        "steps": {"draft": 8, "final": 12},
    },
}

# ── tier access (explicit, testable) ─────────────────────────────────────────
# Every tier gets a working creative experience. Higher tiers add final quality
# and video; nothing is silently hidden.
_IMAGE_CHEAP = ("portrait_photo", "product_shot", "listing_image")
_IMAGE_ALL = tuple(j for j, s in JOBS.items() if s["media"] == "image")

TIER_ACCESS: Dict[str, Dict[str, Tuple[str, ...]]] = {
    "foundation": {"draft": _IMAGE_ALL, "final": _IMAGE_CHEAP},
    "scout": {"draft": _IMAGE_ALL, "final": _IMAGE_CHEAP + ("ad_creative",)},
    "mover": {"draft": _IMAGE_ALL, "final": _IMAGE_ALL},
    "autothink": {"draft": _IMAGE_ALL + ("video_short", "video_long"),
                  "final": _IMAGE_ALL + ("video_short", "video_long")},
}

PLAN_ALLOTMENT = {
    "foundation": 5000, "scout": 11000, "mover": 19000, "autothink": 26000,
}


def _pricing() -> Dict[str, Any]:
    try:
        with open(_CAPS_PATH, "r", encoding="utf-8-sig") as fh:
            d = json.load(fh)
        rate = float(d["refund_policy"]["credit_rate_usd"])
        units = dict(DEFAULT_UNIT_COSTS)
        units.update({k: float(v) for k, v in (d.get("unit_costs_usd") or {}).items()})
        return {"credit_rate_usd": rate, "unit_costs": units, "source": _CAPS_PATH}
    except Exception:  # noqa: BLE001 - fall back to the pinned mirror, never invent
        return {"credit_rate_usd": DEFAULT_CREDIT_RATE_USD,
                "unit_costs": dict(DEFAULT_UNIT_COSTS), "source": "built-in fallback"}


def job_classes(media: Optional[str] = None) -> list:
    if media and media not in MEDIA:
        raise ValueError(f"unknown media {media!r}; expected one of {MEDIA}")
    return [jid for jid, spec in JOBS.items() if not media or spec["media"] == media]


def real_cost(job: str, quality: str = "draft", count: int = 1,
              pricing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Measured model + orchestration cost for one job. No credits involved."""
    spec = JOBS.get(job)
    if spec is None:
        raise ValueError(f"unknown job class {job!r}; known: {sorted(JOBS)}")
    if quality not in QUALITIES:
        raise ValueError(f"unknown quality {quality!r}; expected one of {QUALITIES}")
    if count < 1:
        raise ValueError("count must be >= 1")
    p = pricing or _pricing()
    units = p["unit_costs"]
    model_cost = sum(units[key] * n for key, n in spec["passes"][quality]) * count
    orch = units["post"] * spec["steps"][quality] * count
    return {
        "job": job, "quality": quality, "count": count,
        "model_passes": [{"model": k, "count": n * count} for k, n in spec["passes"][quality]],
        "model_cost_usd": round(model_cost, 6),
        "orchestration_cost_usd": round(orch, 6),
        "real_cost_usd": round(model_cost + orch, 6),
    }


def credits_for(cost_usd: float, pricing: Optional[Dict[str, Any]] = None,
                target_margin: float = TARGET_MARGIN) -> int:
    """Credits that put the real cost at `target_margin` of the credit value."""
    p = pricing or _pricing()
    rate = p["credit_rate_usd"]
    if cost_usd <= 0:
        return 1
    value_needed = cost_usd / max(1e-6, (1.0 - target_margin))
    return max(1, int(math.ceil(value_needed / rate)))


def quote(job: str, quality: str = "draft", count: int = 1,
          pricing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Full quote: real cost, credits, margin, and the tier-access map."""
    p = pricing or _pricing()
    base = real_cost(job, quality, count, p)
    credits = credits_for(base["real_cost_usd"], p)
    credit_value = round(credits * p["credit_rate_usd"], 6)
    margin = round(1.0 - (base["real_cost_usd"] / credit_value), 4) if credit_value else 0.0
    if not (MARGIN_FLOOR - 1e-9 <= margin <= MARGIN_CEILING + 1e-9):
        # Never silently ship a price outside the band the repo enforces.
        raise AssertionError(
            f"pricing outside the {MARGIN_FLOOR:.0%}-{MARGIN_CEILING:.0%} band: "
            f"{job}/{quality} margin={margin}")
    tiers = {plan: (job in TIER_ACCESS[plan][quality]) for plan in TIER_ACCESS}
    return {
        **base,
        "credits": credits,
        "credit_rate_usd": p["credit_rate_usd"],
        "credit_value_usd": credit_value,
        "margin": margin,
        "label": JOBS[job]["label"],
        "media": JOBS[job]["media"],
        "tiers": tiers,
        "pricing_source": p["source"],
    }


def quote_for_plan(plan: str, job: str, quality: str = "draft", count: int = 1,
                   pricing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Quote plus the tier gate. Denied tiers come back ``allowed: False`` with a reason."""
    if plan not in TIER_ACCESS:
        raise ValueError(f"unknown plan {plan!r}; known: {sorted(TIER_ACCESS)}")
    q = quote(job, quality, count, pricing)
    allowed = q["tiers"][plan]
    out = {**q, "plan": plan, "allowed": allowed, "reason": None}
    if not allowed:
        floor = min((p for p in TIER_ACCESS if job in TIER_ACCESS[p][quality]),
                    key=lambda p: PLAN_ALLOTMENT.get(p, 0), default=None)
        out["reason"] = (f"{quality} {job} needs the {floor} tier or above"
                         if floor else f"{job} is not available at {quality}")
    return out


def monthly_capacity(plan: str, job: str, quality: str = "draft",
                     pricing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """How many of this job a member can run on their whole monthly allowance."""
    q = quote_for_plan(plan, job, quality, 1, pricing)
    allotment = PLAN_ALLOTMENT.get(plan, 0)
    return {
        "plan": plan, "job": job, "quality": quality,
        "allowed": q["allowed"],
        "credits_each": q["credits"],
        "allotment": allotment,
        "jobs_per_month": allotment // q["credits"] if q["credits"] else 0,
        "cost_to_tier_usd": round((allotment // q["credits"] or 0) * q["real_cost_usd"], 4),
        "credit_value_usd": round(allotment * q["credit_rate_usd"], 2),
    }


def price_table(pricing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Every job × quality × tier, for the operator and the UI."""
    p = pricing or _pricing()
    rows = []
    for job in JOBS:
        for quality in QUALITIES:
            q = quote(job, quality, 1, p)
            rows.append({
                "job": job, "label": q["label"], "media": q["media"], "quality": quality,
                "credits": q["credits"], "real_cost_usd": q["real_cost_usd"],
                "margin": q["margin"], "tiers": q["tiers"],
            })
    return {
        "credit_rate_usd": p["credit_rate_usd"],
        "target_margin": TARGET_MARGIN,
        "band": {"floor": MARGIN_FLOOR, "ceiling": MARGIN_CEILING},
        "rows": rows,
        "plans": {plan: {"allotment": PLAN_ALLOTMENT.get(plan),
                         "credit_value_usd": round(PLAN_ALLOTMENT.get(plan, 0)
                                                   * p["credit_rate_usd"], 2)}
                  for plan in TIER_ACCESS},
        "source": p["source"],
    }
