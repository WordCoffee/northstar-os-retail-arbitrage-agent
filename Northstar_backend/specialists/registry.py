"""Agent registry — one source of truth for what exists and what each needs.

The registry is data, not code: the router, the agent cards in chat and the
acceptance suite all read it, so an agent cannot quietly drift out of the
required-input contract.
"""

from __future__ import annotations

from typing import Any, Dict, List

AGENTS: Dict[str, Dict[str, Any]] = {
    "package_designer": {
        "label": "Package Designer",
        "does": "full packaging: front, back and side panels, dieline and mockup",
        "inputs_required": ["title", "weight", "dims", "ingredients", "company",
                            "address", "country_of_origin"],
        "inputs_optional": ["subtitle", "claims", "icons", "suggested_use",
                            "warnings", "supplement_facts", "lot_code", "keywords"],
        "outputs": ["front panel", "back panel", "side panel", "panel sheet",
                    "dieline SVG", "dieline PDF", "mockup"],
        "needs_gpu": False,
        "validators": ["panels_present", "copy_present", "barcode_reserved",
                       "dims_consistent"],
        "keywords": ["pouch", "package", "packaging", "dieline", "label",
                     "stand-up", "doypack", "bag", "box", "carton", "net wt",
                     "6 oz", "front panel", "back panel"],
    },
    "listing_optimizer": {
        "label": "Listing Optimizer",
        "does": "audit, keyword coverage, rewrite and re-score an Amazon listing",
        "inputs_required": ["title", "bullets", "keywords"],
        "inputs_optional": ["description", "backend_terms", "competitors",
                            "brand_key", "image_count", "aplus"],
        "outputs": ["before/after scores", "issue list", "rewritten listing",
                    "backend search terms within the byte limit", "change log"],
        "needs_gpu": False,
        "validators": ["no_invented_keywords", "byte_limit", "scores_trace_to_engine"],
        "keywords": ["listing", "title", "bullets", "backend search terms",
                     "optimize listing", "seo", "keyword", "rewrite"],
    },
    "ppc_agent": {
        "label": "PPC Analyst",
        "does": "report-in, bulk-file-out: harvest, negatives, bids, budgets",
        "inputs_required": ["search_term_report"],
        "inputs_optional": ["targeting_report", "placement_report", "bulk_file"],
        "outputs": ["change log", "negatives", "bid moves", "validated bulk rows"],
        "needs_gpu": False,
        "validators": ["report_columns", "entity_operations_valid",
                       "row_traces_to_source", "bid_budget_limits"],
        "keywords": ["ppc", "acos", "tacos", "campaign", "search term report",
                     "negative", "bid", "bulk file", "ad spend"],
    },
    "image_aplus": {
        "label": "Amazon Image & A+",
        "does": "main image, lifestyle, infographics, A+ modules",
        "inputs_required": ["product", "shot_list"],
        "inputs_optional": ["brand_key", "keywords", "plate_asset_id"],
        "outputs": ["image brief", "renders", "A+ module plan"],
        "needs_gpu": True,
        "validators": ["amazon_image_rules", "no_invented_claims"],
        "keywords": ["main image", "lifestyle", "a+ content", "a+ modules",
                     "a+ module", "a+ page", "aplus", "a+ ", "infographic",
                     "size chart", "comparison chart", "shot list"],
    },
    "social_graphics": {
        "label": "Social & Ad Graphics",
        "does": "ads, social posts, banners and multi-aspect creative",
        "inputs_required": ["product", "content_type"],
        "inputs_optional": ["brand_key", "keywords", "aspects", "headline"],
        "outputs": ["layouts per aspect ratio", "copy variants"],
        "needs_gpu": True,
        "validators": ["brand_kit_applied"],
        "keywords": ["social", "ad creative", "banner", "instagram", "facebook",
                     "tiktok", "aspect ratio"],
    },
    "video_ugc": {
        "label": "Video & UGC",
        "does": "script, storyboard, local video render, voiceover, captions",
        "inputs_required": ["product", "duration_seconds"],
        "inputs_optional": ["script", "aspect", "voice_id", "claims"],
        "outputs": ["script", "storyboard", "clip", "captions"],
        "needs_gpu": True,
        "validators": ["duration_matches_spec", "claims_screened"],
        "keywords": ["video", "ugc", "reel", "tiktok video", "ad video",
                     "storyboard", "5 second", "15 second"],
    },
    "content": {
        "label": "Content Writer",
        "does": "ad copy, captions, brand story, email — keyword-tied",
        "inputs_required": ["product", "surface"],
        "inputs_optional": ["brand_key", "keywords", "tone"],
        "outputs": ["copy variants", "keyword coverage"],
        "needs_gpu": False,
        "validators": ["no_unverified_claims", "keyword_coverage"],
        "keywords": ["copy", "caption", "email", "brand story", "blog", "hook"],
    },
    "research": {
        "label": "Research",
        "does": "Golden Goose, market reads and economics validation",
        "inputs_required": ["query"],
        "inputs_optional": ["asin", "category", "budget"],
        "outputs": ["opportunity rows", "evidence packet"],
        "needs_gpu": False,
        "validators": ["approved_sources_only"],
        "keywords": ["product finder", "golden goose", "source", "arbitrage",
                     "competitor", "market", "supplier"],
    },
}


def get(name: str) -> Dict[str, Any] | None:
    return AGENTS.get(name)


def names() -> List[str]:
    return list(AGENTS)


def card(name: str) -> Dict[str, Any]:
    a = AGENTS.get(name) or {}
    return {
        "id": name,
        "label": a.get("label"),
        "does": a.get("does"),
        "needs": a.get("inputs_required") or [],
        "optional": a.get("inputs_optional") or [],
        "outputs": a.get("outputs") or [],
        "gpu": bool(a.get("needs_gpu")),
    }
