"""Golden Goose Runtime Agent — helper sub-agent orchestration.

The Golden Goose Finder is an AI agent that controls FIVE helper sub-agents
which scan web pages, documents, and websites to feed the pipeline:

  1. COSTCO_CATALOG_SCANNER — scans costco.com for multi-pack products
  2. SAMS_CLUB_CATALOG_SCANNER — scans samsclub.com for multi-pack products
  3. AMAZON_PRODUCT_FINDER — finds individual/small-pack ASINs on Amazon
  4. AMAZON_SELLER_ANALYZER — gathers seller counts / FBA depth / Buy Box data
  5. PRICE_BSR_HISTORY_TRACKER — price + BSR historical signals per ASIN

Each helper is a sub-agent with a structured prompt contrat: it receives a
target list, scans its assigned web surface, and returns STRICT JSON that this
module validates and converts into pipeline data classes (WholesaleProduct,
AmazonMatch). Live scanning is HARD STOPPED (§3): helpers never fire live
outbound calls unless the run is explicitly armed with operator approval.

Usage (brain / orchestrator):
    from agents.golden_goose_finder.runtime_agent import (
        HELPER_ROLES, build_helper_payloads, collect_helper_results,
        MockHelperDispatcher,
    )
    payloads = build_helper_payloads(categories=["nicotine_cessation"])
    # brain: spawn 5 sub-agents with payloads[i]["prompt"], collect outputs
    results = collect_helper_results(raw_outputs, validate=True)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable

try:
    from .wholesale_scanner import WholesaleProduct, extract_brand_from_title, extract_pack_count
except ImportError:  # pragma: no cover
    try:
        from wholesale_scanner import WholesaleProduct, extract_brand_from_title, extract_pack_count  # type: ignore
    except ImportError:

        @dataclass
        class WholesaleProduct:  # type: ignore[no-redef]
            source_store: str
            product_title: str
            brand: str
            category_slug: str
            pack_count: int | None
            wholesale_price: float
            item_url: str | None = None
            item_number: str | None = None
            weight_lbs: float | None = None
            dimensions_in: list[float] | None = None
            image_url: str | None = None
            in_stock: bool = True

        def extract_brand_from_title(title: str) -> str | None:  # type: ignore[misc]
            return None

        def extract_pack_count(title: str, category_slug: str | None = None) -> int | None:  # type: ignore[misc]
            return None

try:
    from .amazon_matcher import AmazonMatch
except ImportError:  # pragma: no cover
    try:
        from amazon_matcher import AmazonMatch  # type: ignore
    except ImportError:

        @dataclass
        class AmazonMatch:  # type: ignore[no-redef]
            asin: str
            title: str
            brand: str
            amazon_price: float
            amazon_category: str | None = None
            browse_node: int | None = None
            bsr: int | None = None
            review_rating: float | None = None
            review_count: int | None = None
            fba_sellers: int | None = None
            is_prime: bool = False
            weight_oz: float | None = None
            dimensions_in: list[float] | None = None
            listing_fba_fee: float | None = None
            url: str | None = None
            image_url: str | None = None
            monthly_sales_estimate: int | None = None


# ---------------------------------------------------------------------------
# Helper sub-agent role definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HelperRole:
    """Definition of one helper sub-agent controlled by the Golden Goose Finder."""

    id: str
    name: str
    mission: str
    web_surface: str
    inputs: list[str]
    outputs: list[str]
    prompt_template: str
    mock_data_key: str


HELPER_ROLES: list[HelperRole] = [
    HelperRole(
        id="costco_catalog_scanner",
        name="Costco Catalog Scanner",
        mission=(
            "Scan costco.com search results pages for multi-pack products in the target "
            "categories. Capture product title, brand, pack count, price, item number, "
            "and URL. Focus on national brands (Nicorette, Advil, Nature Made, Tide, etc.) "
            "and EXCLUDE store brands (Kirkland Signature, Member's Mark, Equate)."
        ),
        web_surface="https://www.costco.com search + category listing pages",
        inputs=["category", "brand allowlist", "max results"],
        outputs=["product_title", "brand", "pack_count", "wholesale_price", "item_number", "item_url"],
        prompt_template=(
            "You are the COSTCO CATALOG SCANNER helper for the Golden Goose Finder.\n"
            "Scan Costco search results for category: {category}.\n"
            "Brand allowlist: {brand_allowlist}\n"
            "Return STRICT JSON: {{\"products\": [{{\"product_title\": str, \"brand\": str, "
            "\"pack_count\": int|null, \"wholesale_price\": float, \"item_number\": str|null, "
            "\"item_url\": str|null}}]}}. "
            "Exclude Kirkland Signature / Member's Mark / store brands. "
            "Max {max_results} products. Ensure pack_count is the NUMBER OF UNITS in the pack."
        ),
        mock_data_key="costco_products",
    ),
    HelperRole(
        id="sams_club_catalog_scanner",
        name="Sam's Club Catalog Scanner",
        mission=(
            "Scan samsclub.com search results pages for multi-pack products in the target "
            "categories. Capture product title, brand, pack count, price, item number, URL. "
            "Exclude Member's Mark store brands; prefer national brands."
        ),
        web_surface="https://www.samsclub.com search + category listing pages",
        inputs=["category", "brand allowlist", "max results"],
        outputs=["product_title", "brand", "pack_count", "wholesale_price", "item_number", "item_url"],
        prompt_template=(
            "You are the SAM'S CLUB CATALOG SCANNER helper for the Golden Goose Finder.\n"
            "Scan Sam's Club search results for category: {category}.\n"
            "Brand allowlist: {brand_allowlist}\n"
            "Return STRICT JSON: {{\"products\": [{{\"product_title\": str, \"brand\": str, "
            "\"pack_count\": int|null, \"wholesale_price\": float, \"item_number\": str|null, "
            "\"item_url\": str|null}}]}}. "
            "Exclude Member's Mark / store brands. Max {max_results} products."
        ),
        mock_data_key="sams_products",
    ),
    HelperRole(
        id="amazon_product_finder",
        name="Amazon Product Finder",
        mission=(
            "For each wholesale multi-pack product, find the INDIVIDUAL or small-pack "
            "version sold on Amazon (e.g. 20-count vs 200-count). Capture ASIN, title, "
            "price, BSR, rating, review count. Do NOT return another multi-pack; find the "
            "smaller per-unit listing."
        ),
        web_surface="amazon.com search results for {wholesale_title}",
        inputs=["wholesale_title", "brand", "unit hint (pack_count)"],
        outputs=["asin", "title", "amazon_price", "bsr", "review_rating", "review_count", "url"],
        prompt_template=(
            "You are the AMAZON PRODUCT FINDER helper for the Golden Goose Finder.\n"
            "Wholesale product to match: {wholesale_title}\n"
            "Brand: {brand} — pack count: {pack_count}\n"
            "Find the INDIVIDUAL / SMALL-PACK Amazon listing (much smaller count, lower price).\n"
            "Return STRICT JSON: {{\"matches\": [{{\"asin\": str, \"title\": str, "
            "\"amazon_price\": float, \"bsr\": int|null, \"review_rating\": float|null, "
            "\"review_count\": int|null, \"url\": str|null}}]}}. Max {max_results} matches. "
            "Do NOT return large multi-packs — the individual-unit listing only."
        ),
        mock_data_key="amazon_matches",
    ),
    HelperRole(
        id="amazon_seller_analyzer",
        name="Amazon Seller/Competition Analyzer",
        mission=(
            "For each candidate ASIN, determine the competitive depth: active seller count "
            "split FBA vs FBM, Buy Box owner and price, FBA offer count. This drives the "
            "competition score (0-1 FBA = golden, >5 = crowded)."
        ),
        web_surface="amazon.com offer listing page per ASIN",
        inputs=["asin", "candidate title"],
        outputs=["fba_sellers", "fbm_sellers", "buy_box_price", "is_prime", "total_offers"],
        prompt_template=(
            "You are the AMAZON SELLER ANALYZER helper for the Golden Goose Finder.\n"
            "ASIN: {asin} — title: {title}\n"
            "Scan the offer listing and report competitive depth.\n"
            "Return STRICT JSON: {{\"seller_data\": {{\"asin\": str, \"fba_sellers\": int, "
            "\"fbm_sellers\": int, \"buy_box_price\": float|null, \"is_prime\": bool, "
            "\"total_offers\": int}}}}. Count ACTIVE offers only."
        ),
        mock_data_key="seller_data",
    ),
    HelperRole(
        id="price_bsr_history_tracker",
        name="Price/BSR History Tracker",
        mission=(
            "For each candidate ASIN, assemble price + Best Seller Rank history signals: "
            "current BSR, BSR 30 days ago, Buy Box price 30 days ago, estimated monthly "
            "sales. Sources may include Keepa-style data, provider snapshots, or cached "
            "reports. If history is unavailable, mark each field null — never fabricate."
        ),
        web_surface="Keepa-style history / cached market snapshots / provider enrichment",
        inputs=["asin", "bsr_category"],
        outputs=["bsr", "bsr_30d_ago", "buy_box_price_30d_ago", "monthly_sales_estimate", "history_available"],
        prompt_template=(
            "You are the PRICE/BSR HISTORY TRACKER helper for the Golden Goose Finder.\n"
            "ASIN: {asin} — BSR category: {bsr_category}\n"
            "Assemble price/rank history from available data (Keepa, snapshots, enrichment).\n"
            "Return STRICT JSON: {{\"history\": {{\"asin\": str, \"bsr\": int|null, "
            "\"bsr_30d_ago\": int|null, \"buy_box_price\": float|null, "
            "\"buy_box_price_30d_ago\": float|null, \"monthly_sales_estimate\": int|null, "
            "\"history_available\": bool}}}}. NEVER fabricate values — null when unknown."
        ),
        mock_data_key="price_history",
    ),
]

HELPER_ROLE_BY_ID: dict[str, HelperRole] = {r.id: r for r in HELPER_ROLES}


# ---------------------------------------------------------------------------
# Helper dispatch — build payloads for the brain to spawn sub-agents
# ---------------------------------------------------------------------------

def build_helper_payloads(
    categories: list[str] | None = None,
    brand_allowlist: list[str] | None = None,
    wholesale_products: list[WholesaleProduct] | None = None,
    amazon_candidates: list[AmazonMatch] | None = None,
    max_results: int = 20,
    live_armed: bool = False,
) -> list[dict[str, Any]]:
    """Build the dispatch payload for each of the five helper sub-agents.

    Returns a list of dicts (one per helper role) shaped as:
        {
            "helper_id": str,
            "helper_name": str,
            "mission": str,
            "live_armed": bool,          # §3 gate — True only with operator approval
            "prompt": str,               # ready-to-paste sub-agent prompt
            "input_refs": [...],         # what the helper should scan
            "output_contract": [...],    # fields the helper must produce
        }

    The brain (OpenCode agent) spawns one sub-agent per payload using the
    ``prompt`` field verbatim, then feeds the returned JSON into
    ``collect_helper_results``.
    """
    cats = categories or ["nicotine_cessation", "otc_health", "vitamins_supplements", "household_cleaning", "personal_care", "pet"]
    brands = brand_allowlist or [
        "Nicorette", "NicoDerm", "Advil", "Zyrtec", "Claritin", "Tylenol", "Mucinex",
        "Nature Made", "Emergen-C", "Centrum", "Nature's Bounty", "Tide", "Cascade",
        "Lysol", "Clorox", "Dove", "Colgate", "Crest", "Royal Canin", "Blue Buffalo",
        "Greenies", "Temptations", "Olly", "Airborne",
    ]

    payloads: list[dict[str, Any]] = []
    for role in HELPER_ROLES:
        prompt_vars: dict[str, Any] = {
            "category": ", ".join(cats),
            "brand_allowlist": ", ".join(brands),
            "max_results": max_results,
            "wholesale_title": "",
            "brand": "",
            "pack_count": None,
            "asin": "",
            "title": "",
            "bsr_category": "",
        }
        input_refs: list[str] = []
        if role.id in ("costco_catalog_scanner", "sams_club_catalog_scanner"):
            prompt_vars["category"] = ", ".join(cats)
            input_refs = [f"category={c}" for c in cats]
        elif role.id == "amazon_product_finder":
            if wholesale_products:
                wp = wholesale_products[0]  # batch templating: first product as sample
                prompt_vars["wholesale_title"] = wp.product_title
                prompt_vars["brand"] = wp.brand
                prompt_vars["pack_count"] = wp.pack_count
                input_refs = [
                    f"{p.product_title} (brand={p.brand}, pack={p.pack_count})"
                    for p in wholesale_products[:max_results]
                ]
        elif role.id == "amazon_seller_analyzer":
            if amazon_candidates:
                prompt_vars["asin"] = amazon_candidates[0].asin
                prompt_vars["title"] = amazon_candidates[0].title
                input_refs = [f"{c.asin} — {c.title}" for c in amazon_candidates[:max_results]]
        elif role.id == "price_bsr_history_tracker":
            if amazon_candidates:
                prompt_vars["asin"] = amazon_candidates[0].asin
                prompt_vars["bsr_category"] = amazon_candidates[0].amazon_category or "unknown"
                input_refs = [
                    f"{c.asin} (cat={c.amazon_category or 'unknown'})"
                    for c in amazon_candidates[:max_results]
                ]

        prompt = role.prompt_template.format(**prompt_vars)
        payloads.append(
            {
                "helper_id": role.id,
                "helper_name": role.name,
                "mission": role.mission,
                "web_surface": role.web_surface,
                "live_armed": bool(live_armed),
                "prompt": prompt,
                "input_refs": input_refs,
                "output_contract": role.outputs,
            }
        )
    return payloads


# ---------------------------------------------------------------------------
# Result collection — parse + validate helper JSON output
# ---------------------------------------------------------------------------

def _extract_json_block(text: str) -> Any:
    """Extract the first JSON object/array from a sub-agent's free-text reply."""
    if not text:
        return None
    text = text.strip()
    # Smallest-first fenced blocks, then bare objects/arrays.
    for pattern in (
        r"```(?:json)?\s*(\{.*?\})\s*```",
        r"```(?:json)?\s*(\[.*?\])\s*```",
        r"(\{.*\})",
        r"(\[.*\])",
    ):
        m = re.search(pattern, text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
    return None


def _as_list(value: Any) -> list[dict[str, Any]]:
    """Normalize a helper's JSON into a list of dicts."""
    if value is None:
        return []
    if isinstance(value, list):
        return [v for v in value if isinstance(v, dict)]
    if isinstance(value, dict):
        # Common wrappers: {"products": [...]}, {"matches": [...]},
        # {"seller_data": {...}}, {"history": {...}}
        for key in ("products", "matches", "seller_data", "history", "results", "data", "opportunities"):
            if key in value and isinstance(value[key], list):
                return [v for v in value[key] if isinstance(v, dict)]
            if key in value and isinstance(value[key], dict):
                return [value[key]]
        return [value]
    return []


@dataclass
class HelperResult:
    """Validated result from one helper sub-agent."""

    helper_id: str
    ok: bool
    items: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    received_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def collect_helper_results(
    raw_outputs: dict[str, str],
    validate: bool = True,
) -> dict[str, HelperResult]:
    """Parse each helper's raw text output into validated HelperResults.

    Args:
        raw_outputs: mapping of helper_id → sub-agent final text (JSON).
        validate: if True, basic structural checks are applied; malformed
            helpers return ok=False with the parsing error.

    Returns:
        dict of helper_id → HelperResult.
    """
    results: dict[str, HelperResult] = {}
    for helper_id, text in raw_outputs.items():
        role = HELPER_ROLE_BY_ID.get(helper_id)
        if role is None:
            results[helper_id] = HelperResult(helper_id=helper_id, ok=False, error=f"unknown helper_id: {helper_id}")
            continue
        try:
            parsed = _extract_json_block(text)
            items = _as_list(parsed)
            if validate and not items:
                results[helper_id] = HelperResult(helper_id=helper_id, ok=False, error="no JSON items found")
                continue
            # Structural validation: required fields per role
            required: dict[str, set[str]] = {
                "costco_catalog_scanner": {"product_title"},
                "sams_club_catalog_scanner": {"product_title"},
                "amazon_product_finder": {"asin"},
                "amazon_seller_analyzer": {"asin", "fba_sellers"},
                "price_bsr_history_tracker": {"asin"},
            }
            missing = required.get(helper_id, set()) - set(items[0].keys())
            if validate and missing:
                results[helper_id] = HelperResult(helper_id=helper_id, ok=False, error=f"missing fields: {sorted(missing)}")
                continue
            results[helper_id] = HelperResult(helper_id=helper_id, ok=True, items=items)
        except Exception as exc:  # noqa: BLE001
            results[helper_id] = HelperResult(helper_id=helper_id, ok=False, error=str(exc))
    return results


# ---------------------------------------------------------------------------
# Helper output → pipeline data classes
# ---------------------------------------------------------------------------

def wholesale_products_from_helper_result(
    result: HelperResult,
    source_store: str,
    default_category: str = "otc_health",
) -> list[WholesaleProduct]:
    """Convert a catalog-scanner helper result into WholesaleProduct objects."""
    products: list[WholesaleProduct] = []
    if not result.ok:
        return products
    for item in result.items:
        title = str(item.get("product_title") or "")
        if not title:
            continue
        brand = str(item.get("brand") or "") or extract_brand_from_title(title) or "Unknown"
        pack_count = item.get("pack_count")
        if pack_count is None:
            pack_count = extract_pack_count(title)
        products.append(
            WholesaleProduct(
                source_store=source_store,
                product_title=title,
                brand=brand,
                category_slug=str(item.get("category_slug") or default_category),
                pack_count=int(pack_count) if pack_count else None,
                wholesale_price=float(item.get("wholesale_price") or 0.0),
                item_url=str(item.get("item_url") or "").strip() or None,
                item_number=str(item.get("item_number") or "").strip() or None,
                image_url=str(item.get("image_url") or "").strip() or None,
                in_stock=bool(item.get("in_stock", True)),
            )
        )
    return products


def amazon_matches_from_helper_results(
    finder_result: HelperResult,
    seller_result: HelperResult | None = None,
    history_result: HelperResult | None = None,
) -> list[AmazonMatch]:
    """Merge product-finder + seller-analyzer + history-tracker results into AmazonMatch objects.

    The seller analyzer and history tracker are keyed by ASIN; this function
    attaches their data to the base ASIN list from the product finder.
    """
    by_asin_seller: dict[str, dict[str, Any]] = {}
    if seller_result and seller_result.ok:
        for item in seller_result.items:
            by_asin_seller[str(item.get("asin") or "")] = item

    by_asin_history: dict[str, dict[str, Any]] = {}
    if history_result and history_result.ok:
        for item in history_result.items:
            by_asin_history[str(item.get("asin") or "")] = item

    matches: list[AmazonMatch] = []
    if not finder_result.ok:
        return matches
    for item in finder_result.items:
        asin = str(item.get("asin") or "")
        if not asin:
            continue
        seller = by_asin_seller.get(asin, {})
        hist = by_asin_history.get(asin, {})
        matches.append(
            AmazonMatch(
                asin=asin,
                title=str(item.get("title") or "Unknown"),
                brand=str(item.get("brand") or ""),
                amazon_price=float(item.get("amazon_price") or 0.0),
                amazon_category=str(item.get("amazon_category") or "").strip() or None,
                browse_node=_int_or_none(item.get("browse_node")),
                bsr=_int_or_none(hist.get("bsr") or item.get("bsr")),
                review_rating=_float_or_none(item.get("review_rating")),
                review_count=_int_or_none(item.get("review_count")),
                fba_sellers=_int_or_none(seller.get("fba_sellers") or item.get("fba_sellers")),
                is_prime=bool(seller.get("is_prime", item.get("is_prime", False))),
                weight_oz=_float_or_none(item.get("weight_oz")),
                dimensions_in=item.get("dimensions_in"),
                listing_fba_fee=_float_or_none(item.get("listing_fba_fee")),
                url=str(item.get("url") or "").strip() or None,
                image_url=str(item.get("image_url") or "").strip() or None,
                monthly_sales_estimate=_int_or_none(hist.get("monthly_sales_estimate") or item.get("monthly_sales_estimate")),
            )
        )
    return matches


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Mock dispatcher — deterministic helper outputs for offline end-to-end tests
# ---------------------------------------------------------------------------

class MockHelperDispatcher:
    """Spawns no real sub-agents — returns canned deterministic JSON per helper.

    Mirrors the contract the real brain uses (payload → spawn → JSON) so the
    entire pipeline can be exercised offline without any live calls.
    """

    def __init__(self, categories: list[str] | None = None, seed: int = 42) -> None:
        self.categories = categories or ["otc_health"]
        self.seed = seed

    def dispatch(self, payloads: list[dict[str, Any]]) -> dict[str, str]:
        """Return mock raw outputs keyed by helper_id (simulating sub-agent replies)."""
        outputs: dict[str, str] = {}
        for payload in payloads:
            helper_id = payload["helper_id"]
            if helper_id == "costco_catalog_scanner":
                outputs[helper_id] = json.dumps({"products": self._mock_costco()})
            elif helper_id == "sams_club_catalog_scanner":
                outputs[helper_id] = json.dumps({"products": self._mock_sams()})
            elif helper_id == "amazon_product_finder":
                outputs[helper_id] = json.dumps({"matches": self._mock_finder()})
            elif helper_id == "amazon_seller_analyzer":
                outputs[helper_id] = json.dumps({"seller_data": self._mock_sellers()})
            elif helper_id == "price_bsr_history_tracker":
                outputs[helper_id] = json.dumps({"history": self._mock_history()})
            else:
                outputs[helper_id] = "{}"
        return outputs

    # --- mock fixtures (deterministic, realistic) ---

    def _mock_costco(self) -> list[dict[str, Any]]:
        return [
            {
                "product_title": "Nicorette Nicotine Lozenge 2mg Mint (200 Count)",
                "brand": "Nicorette",
                "pack_count": 200,
                "wholesale_price": 39.99,
                "item_number": "1678912",
                "item_url": "https://www.costco.com/nicorette-lozenge-2mg.html",
            },
            {
                "product_title": "Advil Pain Reliever 200mg Liqui-Gels (500 Count)",
                "brand": "Advil",
                "pack_count": 500,
                "wholesale_price": 24.99,
                "item_number": "1122334",
                "item_url": "https://www.costco.com/advil-500ct.html",
            },
            {
                "product_title": "Nature Made Vitamin D3 2000 IU (250 Softgels)",
                "brand": "Nature Made",
                "pack_count": 250,
                "wholesale_price": 12.99,
                "item_number": "9988776",
                "item_url": "https://www.costco.com/nature-made-d3.html",
            },
        ]

    def _mock_sams(self) -> list[dict[str, Any]]:
        return [
            {
                "product_title": "Zyrtec Allergy Relief 24hr Tablets (pack of 4 bottles, 70ct each)",
                "brand": "Zyrtec",
                "pack_count": 280,
                "wholesale_price": 44.98,
                "item_number": "SAM-887766",
                "item_url": "https://www.samsclub.com/zyrtec-4pk.html",
            },
            {
                "product_title": "Tide PODS Laundry Detergent (152 Count)",
                "brand": "Tide",
                "pack_count": 152,
                "wholesale_price": 29.99,
                "item_number": "SAM-556677",
                "item_url": "https://www.samsclub.com/tide-pods.html",
            },
        ]

    def _mock_finder(self) -> list[dict[str, Any]]:
        return [
            {
                "asin": "B00N2Y1THA",
                "title": "Nicorette Nicotine Lozenge 2mg Mint (20 Count)",
                "brand": "Nicorette",
                "amazon_price": 11.99,
                "bsr": 4200,
                "review_rating": 4.7,
                "review_count": 8900,
                "url": "https://www.amazon.com/dp/B00N2Y1THA",
            },
            {
                "asin": "B00GOHEWCU",
                "title": "Advil Liqui-Gels 200mg (100 Count)",
                "brand": "Advil",
                "amazon_price": 8.99,
                "bsr": 2100,
                "review_rating": 4.8,
                "review_count": 14800,
                "url": "https://www.amazon.com/dp/B00GOHEWCU",
            },
            {
                "asin": "B005DK1FOI",
                "title": "Nature Made Vitamin D3 2000 IU (60 Softgels)",
                "brand": "Nature Made",
                "amazon_price": 7.99,
                "bsr": 1100,
                "review_rating": 4.8,
                "review_count": 42100,
                "url": "https://www.amazon.com/dp/B005DK1FOI",
            },
            {
                "asin": "B00EN7UEH2",
                "title": "Zyrtec Allergy Relief 24hr (70 Count)",
                "brand": "Zyrtec",
                "amazon_price": 22.99,
                "bsr": 980,
                "review_rating": 4.8,
                "review_count": 67200,
                "url": "https://www.amazon.com/dp/B00EN7UEH2",
            },
            {
                "asin": "B01ETY8ZIA",
                "title": "Tide PODS Original Scent (42 Count)",
                "brand": "Tide",
                "amazon_price": 14.99,
                "bsr": 1850,
                "review_rating": 4.7,
                "review_count": 31900,
                "url": "https://www.amazon.com/dp/B01ETY8ZIA",
            },
        ]

    def _mock_sellers(self) -> list[dict[str, Any]]:
        return [
            {"asin": "B00N2Y1THA", "fba_sellers": 1, "fbm_sellers": 3, "buy_box_price": 11.99, "is_prime": True, "total_offers": 8},
            {"asin": "B00GOHEWCU", "fba_sellers": 0, "fbm_sellers": 2, "buy_box_price": 8.99, "is_prime": True, "total_offers": 5},
            {"asin": "B005DK1FOI", "fba_sellers": 2, "fbm_sellers": 4, "buy_box_price": 7.99, "is_prime": True, "total_offers": 12},
            {"asin": "B00EN7UEH2", "fba_sellers": 1, "fbm_sellers": 3, "buy_box_price": 22.99, "is_prime": True, "total_offers": 9},
            {"asin": "B01ETY8ZIA", "fba_sellers": 3, "fbm_sellers": 4, "buy_box_price": 14.99, "is_prime": True, "total_offers": 14},
        ]

    def _mock_history(self) -> list[dict[str, Any]]:
        return [
            {"asin": "B00N2Y1THA", "bsr": 4200, "bsr_30d_ago": 5100, "buy_box_price": 11.99, "buy_box_price_30d_ago": 12.49, "monthly_sales_estimate": 1800, "history_available": True},
            {"asin": "B00GOHEWCU", "bsr": 2100, "bsr_30d_ago": 2400, "buy_box_price": 8.99, "buy_box_price_30d_ago": 9.49, "monthly_sales_estimate": 3200, "history_available": True},
            {"asin": "B005DK1FOI", "bsr": 1100, "bsr_30d_ago": 1300, "buy_box_price": 7.99, "buy_box_price_30d_ago": 8.49, "monthly_sales_estimate": 5800, "history_available": True},
            {"asin": "B00EN7UEH2", "bsr": 980, "bsr_30d_ago": 1100, "buy_box_price": 22.99, "buy_box_price_30d_ago": 23.99, "monthly_sales_estimate": 4500, "history_available": True},
            {"asin": "B01ETY8ZIA", "bsr": 1850, "bsr_30d_ago": 2000, "buy_box_price": 14.99, "buy_box_price_30d_ago": 15.99, "monthly_sales_estimate": 3900, "history_available": True},
        ]


# ---------------------------------------------------------------------------
# Convenience: run the full mock-harness pipeline (offline, end-to-end)
# ---------------------------------------------------------------------------

async def run_mock_harness(
    categories: list[str] | None = None,
    roi_floor: float = 10.0,
    min_monthly_sales: int = 500,
    max_results: int = 100,
) -> dict[str, Any]:
    """Run the full Golden Goose pipeline using the mock helper dispatcher.

    This exercises the EXACT path the runtime agent takes (dispatch five
    helpers → collect → convert to WholesaleProduct/AmazonMatch → economics →
    scoring → report) but with deterministic offline data. No live calls.
    """
    dispatcher = MockHelperDispatcher(categories=categories)
    payloads = build_helper_payloads(categories=categories, max_results=max_results)
    raw = dispatcher.dispatch(payloads)
    results = collect_helper_results(raw, validate=True)

    wholesale: list[WholesaleProduct] = []
    wholesale += wholesale_products_from_helper_result(
        results["costco_catalog_scanner"], source_store="Costco", default_category="otc_health"
    )
    wholesale += wholesale_products_from_helper_result(
        results["sams_club_catalog_scanner"], source_store="Sam's Club", default_category="otc_health"
    )

    matches = amazon_matches_from_helper_results(
        finder_result=results["amazon_product_finder"],
        seller_result=results["amazon_seller_analyzer"],
        history_result=results["price_bsr_history_tracker"],
    )

    # Import pipeline pieces lazily to keep this module importable standalone.
    from .breakdown_economics import WholesalePack, IndividualListing, calculate_breakdown_economics
    from .opportunity_scorer import score_batch
    from .goose_report import generate_json_report, save_report

    economics = []
    disposed: list[dict[str, Any]] = []
    for wp in wholesale:
        # naive pack-to-match pairing is a stand-in: production pairing uses
        # amazon_matcher.find_individual_listing; the harness pairs by brand.
        match = next((m for m in matches if m.brand.lower() == wp.brand.lower()), None)
        if match is None:
            disposed.append({"title": wp.product_title, "reason": "no amazon match found", "details": "brand-miss"})
            continue
        pack = WholesalePack(
            source_store=wp.source_store,
            product_title=wp.product_title,
            brand=wp.brand,
            category_slug=wp.category_slug,
            pack_count=wp.pack_count or 1,
            wholesale_price=wp.wholesale_price,
        )
        listing = IndividualListing(
            asin=match.asin,
            title=match.title,
            brand=match.brand,
            category_slug=wp.category_slug,
            amazon_price=match.amazon_price,
            bsr=match.bsr,
            review_rating=match.review_rating,
            review_count=match.review_count,
            fba_sellers=match.fba_sellers,
            is_prime=match.is_prime,
            monthly_sales_estimate=match.monthly_sales_estimate,
        )
        eco = calculate_breakdown_economics(pack, listing, roi_floor=roi_floor)
        if eco is not None:
            economics.append(eco)
        else:
            disposed.append({"asin": match.asin, "title": match.title, "reason": "economics unavailable", "details": ""})

    scored = score_batch(economics, roi_floor=roi_floor, min_monthly_sales=min_monthly_sales)
    scored = [s for s in scored if s.tier != "REJECT"][:max_results]

    report = generate_json_report(
        scored,
        run_metadata={
            "mode": "mock-harness",
            "helpers_dispatched": len(payloads),
            "wholesale_found": len(wholesale),
            "amazon_matches": len(matches),
            "economics_evaluated": len(economics),
            "disposed": disposed,
        },
    )
    report_path = save_report(report)
    return {
        "status": "ok",
        "helpers_dispatched": len(payloads),
        "wholesale_found": len(wholesale),
        "amazon_matches": len(matches),
        "economics_evaluated": len(economics),
        "opportunities_scored": len(scored),
        "tiers": {
            "HIGH": sum(1 for s in scored if s.tier == "HIGH"),
            "MEDIUM": sum(1 for s in scored if s.tier == "MEDIUM"),
            "LOW": sum(1 for s in scored if s.tier == "LOW"),
        },
        "report_path": report_path,
    }


# ---------------------------------------------------------------------------
# Playbook text — what the brain pastes into the conversation as operating docs
# ---------------------------------------------------------------------------

class LiveArmedError(RuntimeError):
    """Raised when a live helper is dispatched without operator approval."""


def require_live_approval(live_armed: bool, helper_id: str) -> None:
    """§3 gate: raise unless the helper run is explicitly armed by the operator."""
    if not live_armed:
        raise LiveArmedError(
            f"Helper '{helper_id}' requires §3 operator approval for live outbound calls. "
            "Run in mock mode or obtain fresh named approval."
        )