"""Package design module for Northstar OS (Packify-style, in-house).

Recreates the *shape* of Packify's packaging design surface without importing any
of Packify's code, assets or paid services:

- a small template library (box, bottle, pouch, can, label) with dimensions,
- a text-to-design-spec step that runs through the reasoning provider and the
  skills plane (product-marketing base skill first),
- a local credits ledger (no paid calls, no real money),
- a dieline-spec stub (geometry is cadquery's job, not this module's),
- integration with the decision layer's copy_audit for any text on the design.

Everything here is local, free, and offline-capable. Image generation (photoshoot)
and printing are deliberately out of scope: they are paid/external lanes already
covered by the provider suite (FLUX.2 Klein, ElevenLabs) and need operator
approval per the real-money guardrail.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(__file__))

TEMPLATES: Dict[str, Dict[str, Any]] = {
    "box": {"name": "Folding carton", "width_mm": 100, "height_mm": 150, "depth_mm": 50,
            "material": "SBS board 350gsm", "finish": "matte lamination"},
    "bottle": {"name": "Round bottle", "diameter_mm": 60, "height_mm": 180,
               "material": "PET", "finish": "glossy"},
    "pouch": {"name": "Stand-up pouch", "width_mm": 120, "height_mm": 200, "gusset_mm": 40,
              "material": "PET/AL/PE", "finish": "matte"},
    "can": {"name": "Aluminium can", "diameter_mm": 66, "height_mm": 120,
            "material": "aluminium", "finish": "printed"},
    "label": {"name": "Pressure-sensitive label", "width_mm": 80, "height_mm": 120,
              "material": "PP", "finish": "glossy"},
}


@dataclass
class PackageDesign:
    id: str
    name: str
    prompt: str
    template: str
    template_spec: Dict[str, Any]
    color_palette: List[str] = field(default_factory=list)
    typography: str = ""
    claims: List[str] = field(default_factory=list)
    dieline_spec: Dict[str, Any] = field(default_factory=dict)
    mockup_urls: List[str] = field(default_factory=list)
    credits_cost: int = 1
    status: str = "draft"          # draft | proposed | approved
    created_at: str = ""
    copy_audit: Optional[Dict[str, Any]] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _skills_block() -> str:
    try:
        import skills_plane
        return skills_plane.context_block(ids=["product-marketing", "ad-creative"])
    except Exception:  # noqa: BLE001 - prompt decoration must not break a design
        return ""


def design_from_prompt(prompt: str, provider=None, template: Optional[str] = None) -> PackageDesign:
    """Propose a package design from a free-text prompt.

    Uses the reasoning provider (MockReasoningProvider in tests) to turn the
    prompt into a structured spec. Falls back to a template-only stub when no
    provider is supplied, so the module is always usable offline.
    """
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("prompt must not be empty")
    if template is None or template not in TEMPLATES:
        low = prompt.lower()
        if "bottle" in low:
            template = "bottle"
        elif "pouch" in low or "bag" in low:
            template = "pouch"
        elif "can" in low:
            template = "can"
        elif "label" in low:
            template = "label"
        else:
            template = "box"
    spec = dict(TEMPLATES[template])

    design = PackageDesign(
        id=str(uuid.uuid4()),
        name=prompt[:60],
        prompt=prompt,
        template=template,
        template_spec=spec,
        created_at=_now(),
    )

    if provider is not None:
        system = ("You are a packaging designer for Northstar OS. Return ONLY JSON with keys: "
                  "name (string), color_palette (list of hex colors), typography (string), "
                  "claims (list of short claim strings), dieline_spec (object with width_mm, "
                  "height_mm, bleed_mm, safe_zone_mm). Use only the supplied facts; do not "
                  "invent certifications or prohibited claims.")
        skill_text = _skills_block()
        if skill_text:
            system = skill_text + "\n\n" + system
        try:
            from adapters.reasoning_provider import ReasoningRequest
            req = ReasoningRequest(
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": prompt}],
                model=getattr(provider, "model", None),
                task_type="package_design",
                session_id=f"pkg:{design.id}",
            )
            resp = provider.complete(req)
            data = getattr(resp, "data", None) or {}
            content = data.get("content", "") if isinstance(data, dict) else ""
            parsed = None
            try:
                parsed = json.loads(content)
            except Exception:  # noqa: BLE001
                parsed = None
            if isinstance(parsed, dict):
                design.name = str(parsed.get("name") or design.name)[:60]
                design.color_palette = list(parsed.get("color_palette") or [])
                design.typography = str(parsed.get("typography") or "")
                design.claims = [str(c) for c in (parsed.get("claims") or [])]
                if isinstance(parsed.get("dieline_spec"), dict):
                    design.dieline_spec = parsed["dieline_spec"]
        except Exception:  # noqa: BLE001
            pass
        # copy audit on the claims + name
        try:
            import decision_layer
            audit_text = " ".join([design.name] + design.claims)
            design.copy_audit = decision_layer.audit_copy(audit_text)
            if design.copy_audit.get("value") == "block":
                design.status = "draft"
        except Exception:  # noqa: BLE001
            design.copy_audit = None

    if not design.dieline_spec:
        design.dieline_spec = {"width_mm": spec.get("width_mm") or spec.get("diameter_mm"),
                              "height_mm": spec.get("height_mm"),
                              "bleed_mm": 3, "safe_zone_mm": 5}
    return design


# ---------------------------------------------------------------------------
# Local credits ledger (Packify-style, no money)
# ---------------------------------------------------------------------------

_CREDITS: Dict[str, int] = {}


def credits(account_id: str = "default") -> int:
    return _CREDITS.get(account_id, 49)   # Packify's starter grant, mirrored


def spend_credits(account_id: str, amount: int) -> Dict[str, Any]:
    if amount < 0:
        raise ValueError("amount must be non-negative")
    bal = credits(account_id)
    if amount > bal:
        return {"ok": False, "balance": bal, "spent": 0,
                "reason": "insufficient credits"}
    _CREDITS[account_id] = bal - amount
    return {"ok": True, "balance": _CREDITS[account_id], "spent": amount}


def grant_credits(account_id: str, amount: int) -> int:
    if amount < 0:
        raise ValueError("amount must be non-negative")
    _CREDITS[account_id] = credits(account_id) + amount
    return _CREDITS[account_id]


def reset_credits(account_id: str = "default") -> None:
    _CREDITS.pop(account_id, None)


def to_dict(design: PackageDesign) -> Dict[str, Any]:
    return asdict(design)


def _main(argv: List[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Northstar package design (offline)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p_new = sub.add_parser("new")
    p_new.add_argument("prompt")
    p_new.add_argument("--template", default=None)
    sub.add_parser("templates")
    p_cred = sub.add_parser("credits")
    p_cred.add_argument("--account", default="default")
    args = ap.parse_args(argv)

    if args.cmd == "templates":
        print(json.dumps(TEMPLATES, indent=2))
        return 0
    if args.cmd == "credits":
        print(json.dumps({"account": args.account, "balance": credits(args.account)}, indent=2))
        return 0
    if args.cmd == "new":
        d = design_from_prompt(args.prompt, template=args.template)
        print(json.dumps(to_dict(d), indent=2, default=str))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
