"""Supplier discovery scraper — pre-account wholesale supplier intelligence.

Discovers wholesale suppliers for a product category before any account is
created: company name, website, public catalog URL, contact info, shipping /
logistics signals (liftgate requirement), and an account-friction estimate.

Live/paid outbound calls are STRICTLY gated:
  * ``SUPPLIER_DISCOVERY_LIVE_OPERATOR_APPROVED=1`` plus an injected transport
    are required for any real network call.
  * The default transport is the built-in OFFER/SEED catalog (a curated,
    offline supplier directory keyed by category) so the module works and is
    testable with zero network access.
  * Providers (Google CSE, ThomasNet, Alibaba, etc.) are wired through a
    pluggable ``fetch_fn`` — operators who have §3 approval provide their own
    fetcher; the module never embeds an un-gated live client.

A discovered supplier is returned as a ``SupplierProfile`` with fields that
map 1:1 onto the ``suppliers`` table columns (SuppliersDB.upsert accepts it
directly via ``as_dict()``).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Logistics signal keywords (mirrors config/supplier_intelligence.json)
# ---------------------------------------------------------------------------

LIFTGATE_KEYWORDS = [
    "liftgate", "tailgate", "ltl", "box truck", "box-truck",
    "pallet", "palletized", "dock required", "residential delivery",
    "mechanical liftgate", "truck delivery",
]

FRICTION_LOW = "low"
FRICTION_MEDIUM = "medium"
FRICTION_HIGH = "high"
FRICTION_LEVELS = (FRICTION_LOW, FRICTION_MEDIUM, FRICTION_HIGH)


@dataclass
class SupplierProfile:
    """One discovered supplier candidate."""

    name: str
    categories_supplied: List[str] = field(default_factory=list)
    public_catalog_url: Optional[str] = None
    website: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    requires_liftgate: bool = True
    liftgate_notes: Optional[str] = None
    logistics_notes: Optional[str] = None
    account_friction_level: str = FRICTION_MEDIUM
    friction_notes: Optional[str] = None
    confidence: float = 0.0
    source: str = "seed-catalog"
    discovery_keywords: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["id"] = _discovery_id(self.name)
        return d


def _discovery_id(name: str) -> str:
    import re
    s = str(name or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:80] or "supplier"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Built-in offline seed catalog (curated wholesale suppliers by category)
# ---------------------------------------------------------------------------

_SEED_CATALOG: List[Dict[str, Any]] = [
    {
        "name": "McKesson Medical-Surgical",
        "categories_supplied": ["otc_health", "personal_care", "vitamins_supplements"],
        "public_catalog_url": "https://mms.mckesson.com/catalog",
        "website": "https://mms.mckesson.com",
        "requires_liftgate": True,
        "liftgate_notes": "LTL palletized shipments; liftgate required for residential delivery.",
        "account_friction_level": "high",
        "friction_notes": "Tax ID + DEA/govt registration depending on category; 5-10 business day approval.",
        "confidence": 0.97,
        "source": "seed-catalog",
    },
    {
        "name": "Cardinal Health Distribution",
        "categories_supplied": ["otc_health", "vitamins_supplements", "personal_care"],
        "public_catalog_url": "https://cardinalhealth.com",
        "website": "https://www.cardinalhealth.com",
        "requires_liftgate": True,
        "liftgate_notes": "LTL standard; liftgate required on residential addresses.",
        "account_friction_level": "high",
        "friction_notes": "Wholesale license / resale certificate required.",
        "confidence": 0.95,
        "source": "seed-catalog",
    },
    {
        "name": "UNFI (United Natural Foods)",
        "categories_supplied": ["snacks_bars", "vitamins_supplements", "household_cleaning"],
        "public_catalog_url": "https://www.unfi.com",
        "website": "https://www.unfi.com",
        "requires_liftgate": True,
        "liftgate_notes": "Full-truckload and LTL; liftgate needed for residential drop.",
        "account_friction_level": "medium",
        "friction_notes": "Retailer/wholesaler application, 3-5 day approval.",
        "confidence": 0.9,
        "source": "seed-catalog",
    },
    {
        "name": "KEHE Distributors",
        "categories_supplied": ["snacks_bars", "household_cleaning", "baby_child", "personal_care"],
        "public_catalog_url": "https://www.kehe.com",
        "website": "https://www.kehe.com",
        "requires_liftgate": True,
        "liftgate_notes": "LTL deliveries; residential liftgate service available on request.",
        "account_friction_level": "medium",
        "friction_notes": "Independent retailer application; net terms after history.",
        "confidence": 0.88,
        "source": "seed-catalog",
    },
    {
        "name": "National Distributors Inc.",
        "categories_supplied": ["household_cleaning", "personal_care", "pet"],
        "public_catalog_url": "https://nationaldistributors.com",
        "website": "https://nationaldistributors.com",
        "requires_liftgate": False,
        "liftgate_notes": "Parcel + LTL options; small orders ship parcel (no liftgate).",
        "account_friction_level": "low",
        "friction_notes": "Quick online signup, tax-id only.",
        "confidence": 0.72,
        "source": "seed-catalog",
    },
    {
        "name": "Topline Brands",
        "categories_supplied": ["household_cleaning", "personal_care", "vitamins_supplements"],
        "public_catalog_url": "https://toplinebrands.com",
        "website": "https://toplinebrands.com",
        "requires_liftgate": True,
        "liftgate_notes": "LTL; mechanical liftgate required at residential detached garages.",
        "account_friction_level": "medium",
        "friction_notes": "Application + resale certificate.",
        "confidence": 0.8,
        "source": "seed-catalog",
    },
    {
        "name": "Sun Wholesale Supply",
        "categories_supplied": ["pet", "snacks_bars", "baby_child"],
        "public_catalog_url": "https://sunwholesale.example.com/catalog",
        "website": "https://sunwholesale.example.com",
        "requires_liftgate": False,
        "liftgate_notes": "Parcel-friendly; small-case shipping standard.",
        "account_friction_level": "low",
        "friction_notes": "Public catalog, no account needed for pricing.",
        "confidence": 0.66,
        "source": "seed-catalog",
    },
]


def _seed_liftgate_notes_for(categories: List[str]) -> str:
    return (
        "LTL only, liftgate required: delivery constraint — Residential detached "
        "garage—mechanical liftgate required."
    )


class SupplierDiscoveryScraper:
    """Discover wholesale suppliers for a category.

    ``mode``:
      - "offline" (default): built-in curated seed catalog only. Zero network.
      - "live": uses the injected ``fetch_fn`` transport. Only runs when the
        operator gate env var is exactly "1"; otherwise returns an empty list
        with ``last_error`` set (never auto-live).
    """

    def __init__(
        self,
        fetch_fn: Optional[Callable[[str, List[str]], List[Dict[str, Any]]]] = None,
        gate_env: str = "SUPPLIER_DISCOVERY_LIVE_OPERATOR_APPROVED",
        min_confidence: float = 0.6,
    ) -> None:
        self.fetch_fn = fetch_fn
        self.gate_env = gate_env
        self.min_confidence = min_confidence
        self.last_error: Optional[str] = None
        self._load_config()

    def _load_config(self) -> None:
        cfg = Path(__file__).resolve().parent.parent / "config" / "supplier_intelligence.json"
        try:
            with open(cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.min_confidence = float(
                data.get("discovery", {}).get("min_confidence_threshold", self.min_confidence)
            )
            self.max_results = int(
                data.get("discovery", {}).get("max_results_per_category", 50)
            )
        except (OSError, ValueError, TypeError, AttributeError):
            self.max_results = 50

    # -- gate ---------------------------------------------------------------

    def live_armed(self) -> bool:
        return os.environ.get(self.gate_env, "").strip() == "1"

    # -- offline seed -------------------------------------------------------

    def _seed_search(self, category_slug: str, keywords: List[str]) -> List[SupplierProfile]:
        out: List[SupplierProfile] = []
        wanted = set(keywords) | {category_slug}
        for row in _SEED_CATALOG:
            cats = row.get("categories_supplied", [])
            if wanted & {str(c).lower() for c in cats} or not category_slug:
                prof = SupplierProfile(**row)
                prof.discovery_keywords = ", ".join(keywords) if keywords else category_slug
                if prof.requires_liftgate and not prof.liftgate_notes:
                    prof.liftgate_notes = _seed_liftgate_notes_for(cats)
                out.append(prof)
        return out

    def discover(
        self,
        category_slug: str,
        keywords: Optional[List[str]] = None,
        mode: str = "offline",
    ) -> List[SupplierProfile]:
        """Discover suppliers. Returns [] (never raises) when unavailable."""
        self.last_error = None
        keywords = [k for k in (keywords or []) if k]

        if mode == "offline":
            return self._seed_search(category_slug, keywords)

        if mode == "live":
            if not self.live_armed():
                self.last_error = (
                    f"Live discovery gated: set {self.gate_env}=1 with an injected "
                    "fetch_fn and operator approval."
                )
                return []
            if not self.fetch_fn:
                self.last_error = "Live discovery requires an injected fetch_fn transport."
                return []

        try:
            raw = self.fetch_fn(category_slug, keywords)  # type: ignore[misc]
            return [self._normalize(row, category_slug, keywords) for row in (raw or [])]
        except Exception as exc:  # operator transport failures are surfaced, not fatal
            self.last_error = f"Discovery transport error: {exc}"
            return []

    def _normalize(
        self,
        row: Dict[str, Any],
        category_slug: str,
        keywords: List[str],
    ) -> SupplierProfile:
        prof = SupplierProfile(
            name=str(row.get("name") or "Unknown Supplier"),
            categories_supplied=[
                str(c) for c in row.get("categories_supplied", [])
            ] or [category_slug],
            public_catalog_url=row.get("public_catalog_url"),
            website=row.get("website"),
            contact_email=row.get("contact_email"),
            contact_phone=row.get("contact_phone"),
            account_friction_level=str(row.get("account_friction_level") or FRICTION_MEDIUM),
            friction_notes=row.get("friction_notes"),
            confidence=float(row.get("confidence") or 0.0),
            source=str(row.get("source") or "live"),
            discovery_keywords=", ".join(keywords) if keywords else category_slug,
        )
        # Logistics: default requires_liftgate True (config default) unless the
        # row explicitly says otherwise; liftgate text is mined from any notes.
        raw_liftgate = row.get("requires_liftgate")
        prof.requires_liftgate = True if raw_liftgate is None else bool(raw_liftgate)
        notes = " ".join(
            str(row.get(k) or "") for k in ("liftgate_notes", "logistics_notes", "shipping_terms")
        )
        if any(kw in notes.lower() for kw in LIFTGATE_KEYWORDS):
            prof.requires_liftgate = True
            prof.liftgate_notes = row.get("liftgate_notes") or notes.strip() or None
        prof.logistics_notes = row.get("logistics_notes")
        if prof.requires_liftgate and not prof.liftgate_notes:
            prof.liftgate_notes = _seed_liftgate_notes_for(prof.categories_supplied)
        return prof


def discover_suppliers(
    category_slug: str,
    keywords: Optional[List[str]] = None,
    mode: str = "offline",
    **kwargs: Any,
) -> List[SupplierProfile]:
    """Module-level convenience: discover suppliers for a category."""
    return SupplierDiscoveryScraper(**kwargs).discover(category_slug, keywords, mode)