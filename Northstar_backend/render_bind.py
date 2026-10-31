"""Render initialisation binding (Phase 3, item 1).

Before a creative render runs, it should know what the product can AFFORD: the
margin decides whether the packaging material is kraft, foil or plain; the price
band decides the perceived tier; the keyword set decides what the imagery must
show. This module is that binding, as a pure function, so the render path cannot
silently invent a premium finish on a value-margin product.

Missing numbers do not become zero. A product with no cost or no price yields
`material_tier="unknown"` and a `pricing_unknown` blocker, and the caller decides
whether to proceed - the module never guesses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

PREMIUM_MARGIN = 0.55
STANDARD_MARGIN = 0.35
MAX_KEYWORDS = 20
KEYWORD_MAX_LEN = 60

#: material language per tier - these are the words that go into the render prompt
MATERIAL: Dict[str, Dict[str, str]] = {
    "premium": {
        "substrate": "matte kraft with soft-touch lamination",
        "finish": "embossed foil stamping, spot UV on the wordmark",
        "lighting": "soft studio lighting, 85mm lens, shallow depth of field",
    },
    "standard": {
        "substrate": "coated white board, satin varnish",
        "finish": "single-hit foil on the logo only",
        "lighting": "soft studio lighting, 85mm lens",
    },
    "value": {
        "substrate": "uncoated natural kraft",
        "finish": "one-colour flexo print",
        "lighting": "even softbox lighting, 50mm lens",
    },
    "unknown": {
        "substrate": "unspecified - pricing missing",
        "finish": "unspecified",
        "lighting": "soft studio lighting",
    },
}


@dataclass
class RenderBrief:
    product_id: str
    material_tier: str
    target_price: Optional[float]
    unit_cost: Optional[float]
    margin_pct: Optional[float]
    keywords: List[str] = field(default_factory=list)
    must_not: List[str] = field(default_factory=list)
    environment: str = "studio-white"
    blocked: List[str] = field(default_factory=list)
    materials: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_id": self.product_id,
            "material_tier": self.material_tier,
            "target_price": self.target_price,
            "unit_cost": self.unit_cost,
            "margin_pct": self.margin_pct,
            "keywords": list(self.keywords),
            "must_not": list(self.must_not),
            "environment": self.environment,
            "blocked": list(self.blocked),
            "materials": dict(self.materials),
            "ready": not self.blocked,
        }


def _num(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


def normalise_keywords(items: Optional[Iterable[Any]]) -> List[str]:
    """Lower-case, strip, collapse whitespace, de-duplicate, cap. Order is kept."""
    out: List[str] = []
    seen = set()
    for item in items or []:
        if not isinstance(item, str):
            continue
        word = " ".join(item.strip().lower().split())
        if not word or len(word) > KEYWORD_MAX_LEN:
            continue
        if word in seen:
            continue
        seen.add(word)
        out.append(word)
        if len(out) >= MAX_KEYWORDS:
            break
    return out


def tier_for(margin: Optional[float]) -> str:
    if margin is None:
        return "unknown"
    if margin >= PREMIUM_MARGIN:
        return "premium"
    if margin >= STANDARD_MARGIN:
        return "standard"
    return "value"


def environment_for(*, lifestyle: bool, buyer: Optional[Dict[str, Any]] = None) -> str:
    """Lifestyle scene from the buyer profile; studio white when there is none."""
    if not lifestyle:
        return "studio-white"
    buyer = buyer or {}
    room = str(buyer.get("room") or "").strip().lower()
    if room in {"kitchen", "office", "bathroom", "garage", "gym", "outdoor", "nursery"}:
        return f"lifestyle-{room}"
    demographic = str(buyer.get("segment") or "").strip().lower()
    if demographic:
        return f"lifestyle-{demographic.replace(' ', '-')[:24]}"
    return "lifestyle-generic"


def bind(
    product: Dict[str, Any],
    *,
    pricing: Optional[Dict[str, Any]] = None,
    keywords: Optional[Iterable[Any]] = None,
    buyer: Optional[Dict[str, Any]] = None,
    lifestyle: bool = False,
) -> RenderBrief:
    """Decide what this render is allowed to look like."""
    product = product or {}
    pricing = pricing or {}
    pid = str(product.get("id") or product.get("asin") or "").strip()

    price = _num(pricing.get("target_price", product.get("target_price")))
    cost = _num(pricing.get("unit_cost", product.get("unit_cost")))
    margin: Optional[float] = None
    if price and cost is not None and price > 0:
        margin = round((price - cost) / price, 4)

    tier = tier_for(margin)
    blocked: List[str] = []
    if not pid:
        blocked.append("product_id_missing")
    if margin is None:
        blocked.append("pricing_unknown")
    if tier == "value" and lifestyle:
        blocked.append("lifestyle_over_budget")   # a scene costs more than the margin supports

    must_not = [
        "text or lettering of any kind",
        "supplier watermarks",
        "added logos not supplied by the owner",
        "price, promotion or shipping claims",
    ]

    return RenderBrief(
        product_id=pid,
        material_tier=tier,
        target_price=price,
        unit_cost=cost,
        margin_pct=margin,
        keywords=normalise_keywords(keywords),
        must_not=must_not,
        environment=environment_for(lifestyle=lifestyle, buyer=buyer),
        blocked=blocked,
        materials=dict(MATERIAL[tier]),
    )


def prompt_suffix(brief: RenderBrief) -> str:
    """The material + lighting clause appended to every render prompt."""
    m = brief.materials
    return f"{m['substrate']}; {m['finish']}; {m['lighting']}"


__all__ = ["RenderBrief", "bind", "tier_for", "normalise_keywords", "environment_for",
           "prompt_suffix", "MATERIAL", "PREMIUM_MARGIN", "STANDARD_MARGIN"]
