"""Static configuration for the discovery lane (D11 / A18 i0).

The A18 design calls for an explicit source registry with honest quotas and one
closed query plan; A21 needs a service keyword profile per Northstar service.
Everything here is data.  Nothing here grants an action.

Quotas are recorded as **measured or unknown**, never guessed:

* GitHub search: 10 requests/minute unauthenticated (measured from
  ``X-RateLimit-Remaining``; also observed 429 live at
  ``reports/ty/research_20261105.md``).  Core: 60/hour.
* Everything else: ``None`` + ``source_of_truth: "unknown"``.  arXiv's ~3 s
  spacing is self-imposed politeness, not an asserted provider rule.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
SCOUT_DIR = Path(__file__).resolve().parent
FIXTURES = SCOUT_DIR / "fixtures"
SERVICES_PATH = ROOT / "ty" / "services.json"
SCORECARDS_PATH = ROOT / "ty" / "scorecards.json"
GAPS_PATH = ROOT / "ty" / "intel_gaps.json"          # tracked (state/ is gitignored)
MIRROR_PATH = ROOT / "state" / "intel" / "gaps.json"  # runtime mirror
REFUSALS_PATH = SCOUT_DIR / "refusals.jsonl"          # tracked, closed vocabulary
CACHE_DIR = ROOT / "state" / "intel" / "cache"

UA = "northstar-os-scout/1.0 (+local bench; no auth; no keys)"

SOURCES: Dict[str, Dict[str, Any]] = {
    "github": {
        "kind": "repository",
        "ecosystem": None,
        "api": "https://api.github.com/search/repositories",
        "auth": "none",
        "quota": {"limit": 10, "window": "1 minute", "source_of_truth": "measured"},
        "quota_note": "Unauthenticated search. X-RateLimit-Remaining read from every response.",
        "enabled": True,
    },
    "huggingface": {
        "kind": "model",
        "ecosystem": None,
        "api": "https://huggingface.co/api/models",
        "auth": "none",
        "quota": {"limit": None, "window": None, "source_of_truth": "unknown"},
        "quota_note": "Public model API; no documented anonymous search quota.",
        "enabled": True,
    },
    "pypi": {
        "kind": "package",
        "ecosystem": "PyPI",
        "api": "https://pypi.org/simple/ + https://pypi.org/pypi/<name>/json",
        "auth": "none",
        "quota": {"limit": None, "window": None, "source_of_truth": "unknown"},
        "quota_note": ("No keyless JSON search endpoint: pypi.org/search is a JS client challenge. "
                       "We filter the Simple index once (cached 24 h) then read per-project JSON."),
        "enabled": True,
    },
    "npm": {
        "kind": "package",
        "ecosystem": "npm",
        "api": "https://registry.npmjs.org/-/v1/search + /<name>/latest",
        "auth": "none",
        "quota": {"limit": None, "window": None, "source_of_truth": "unknown"},
        "quota_note": "Public registry; search result objects omit licence, so /latest is read per hit.",
        "enabled": True,
    },
    "arxiv": {
        "kind": "paper",
        "ecosystem": None,
        "api": "https://export.arxiv.org/api/query",
        "auth": "none",
        "quota": {"limit": None, "window": None, "source_of_truth": "unknown"},
        "quota_note": "3 s spacing is self-imposed politeness, not a published quota.",
        "enabled": True,
    },
}

#: One query per (source, theme).  ``service_hint`` is a prior, not an override:
#: the ranked service still comes from keyword evidence.
QUERY_PLAN: List[Dict[str, str]] = [
    {"source": "github", "query": "product photography", "service_hint": "design-studio"},
    {"source": "github", "query": "background removal", "service_hint": "design-studio"},
    {"source": "github", "query": "retail arbitrage", "service_hint": "prospector"},
    {"source": "github", "query": "listing optimization ecommerce", "service_hint": "listings"},
    {"source": "github", "query": "price tracker", "service_hint": "competitor-monitor"},
    {"source": "github", "query": "keyword research seo", "service_hint": "keywords"},
    {"source": "huggingface", "query": "background removal", "service_hint": "design-studio"},
    {"source": "huggingface", "query": "product photography", "service_hint": "design-studio"},
    {"source": "huggingface", "query": "product description", "service_hint": "listingforge"},
    {"source": "pypi", "query": "retail", "service_hint": "prospector"},
    {"source": "pypi", "query": "price parser", "service_hint": "competitor-monitor"},
    {"source": "pypi", "query": "keyword research", "service_hint": "keywords"},
    {"source": "npm", "query": "product photography", "service_hint": "design-studio"},
    {"source": "npm", "query": "price tracker", "service_hint": "competitor-monitor"},
    {"source": "npm", "query": "keyword research", "service_hint": "keywords"},
    {"source": "arxiv", "query": "retail pricing optimization", "service_hint": "offerchisel"},
    {"source": "arxiv", "query": "product image generation", "service_hint": "design-studio"},
    {"source": "arxiv", "query": "ecommerce recommendation", "service_hint": "prospector"},
]

#: Per-service keyword profiles.  Primary terms carry weight 1.0, secondary 0.5.
#: Services without a curated profile fall back to their label words.
SERVICE_KEYWORDS: Dict[str, Dict[str, List[str]]] = {
    "hub": {"primary": ["operations dashboard", "workspace"], "secondary": ["dashboard"]},
    "ledger": {"primary": ["bookkeeping", "accounting", "ledger"],
               "secondary": ["finance", "invoice", "expense"]},
    "prospector": {"primary": ["retail arbitrage", "product research", "product discovery",
                               "demand forecasting"],
                   "secondary": ["market research", "trend", "sourcing", "catalog"]},
    "goldengoose": {"primary": ["arbitrage", "deal finding", "resale"],
                    "secondary": ["supplier", "wholesale", "margin"]},
    "offerchisel": {"primary": ["offer", "procurement", "negotiation"],
                    "secondary": ["pricing strategy", "price optimization"]},
    "towncrier": {"primary": ["social media posting", "content calendar"],
                  "secondary": ["announcement", "marketing content"]},
    "auctioneer": {"primary": ["ppc", "advertising", "ad campaign"],
                   "secondary": ["bidding", "google ads", "ad spend"]},
    "autothink": {"primary": ["research agent", "llm agent", "agent framework",
                               "multi agent", "agentic"],
                  "secondary": ["reasoning", "rag", "retrieval augmented", "tool use",
                                "orchestration"]},
    "thewatch": {"primary": ["monitoring", "watch", "alerting"],
                 "secondary": ["notification", "webhook", "change detection"]},
    "rankledger": {"primary": ["rank tracking", "search ranking"],
                   "secondary": ["serp", "google ranking"]},
    "rivalboard": {"primary": ["competitor analysis", "competitor monitoring"],
                   "secondary": ["rival", "competitive intelligence"]},
    "account": {"primary": ["subscription billing"], "secondary": ["account", "billing"]},
    "foundation": {"primary": ["internal operations"], "secondary": ["admin"]},
    "jobs": {"primary": ["job scheduler", "task queue"],
             "secondary": ["cron", "workflow", "queue", "scheduler"]},
    "keywords": {"primary": ["keyword research", "seo"],
                 "secondary": ["search volume", "serp", "keyword difficulty"]},
    "beta": {"primary": ["onboarding"], "secondary": ["signup", "waitlist"]},
    "beta-support": {"primary": ["support desk"], "secondary": ["helpdesk", "ticketing"]},
    "beta-signup": {"primary": ["invite"], "secondary": ["referral"]},
    "beta-ops": {"primary": ["tester dashboard"], "secondary": ["feature flag"]},
    "design-studio": {"primary": ["image generation", "product photography", "background removal",
                                  "image editing", "comfyui"],
                      "secondary": ["diffusion", "inpainting", "segmentation", "upscaler",
                                    "virtual try-on", "3d to photo", "photo studio"]},
    "product-finder": {"primary": ["product finder", "product discovery", "product search",
                                   "ecommerce scraper", "e-commerce scraper"],
                       "secondary": ["catalog", "product data", "scraper"]},
    "golden-goose": {"primary": ["arbitrage", "deal finder", "profit margin"],
                     "secondary": ["resale", "inventory analytics"]},
    "listings": {"primary": ["listing optimization", "product listing", "title optimization"],
                 "secondary": ["bullet points", "listing quality", "ecommerce listing"]},
    "keyword-tracker": {"primary": ["keyword tracking", "keyword rank"],
                        "secondary": ["position tracking", "serp tracker"]},
    "competitor-monitor": {"primary": ["price tracker", "price monitoring", "competitor monitor"],
                           "secondary": ["price alert", "web scraping", "change detection"]},
    "listingforge": {"primary": ["product description", "copywriting", "listing generation"],
                      "secondary": ["content generation", "ai writing"]},
    "adpilot": {"primary": ["ad campaign", "ppc automation"],
                "secondary": ["advertising", "google ads", "bid management"]},
    "socialpulse": {"primary": ["social media scheduling", "social analytics"],
                    "secondary": ["engagement", "post scheduling"]},
    "profitability": {"primary": ["profit margin", "unit economics"],
                      "secondary": ["cost analysis", "profitability"]},
}

#: Ranking weights (sum 1.0).  Documented so a score can be explained.
#: ``lift`` is the gap-capped lift normalised to 0..1, so a service that already
#: meets its bar cannot be pushed to the top by popularity alone.
WEIGHTS = {
    "relevance": 0.35,
    "licence": 0.15,
    "popularity": 0.10,
    "vet": 0.10,
    "evidence": 0.10,
    "lift": 0.20,
}

#: Maximum raw lift before the scorecard gap caps it (see ``rank.estimated_lift``).
LIFT_CEILING = 14.0

#: Closed refusal vocabulary (A18 decision 1).  An unknown id is a schema bug.
REFUSAL_RULES = {
    "amazon_host_blocked": "Host is Amazon or a lookalike; standing gate, never fetched.",
    "not_absolute_url": "A relative or empty URL cannot be fetched.",
    "scheme_refused": "Only http/https may leave the machine.",
    "no_host": "URL has no host.",
    "source_disabled": "Source is disabled in the registry.",
    "source_unknown": "No connector is registered for that source.",
    "url_unverified": "HEAD/GET verification did not return a 2xx/3xx status.",
}

#: A hit is dropped when it is clearly from another domain and carries no
#: retail/commerce context.  "price tracker" legitimately describes a crypto
#: ticker and a Minecraft auction sniper; neither belongs in a retail gap list.
OFF_DOMAIN = (
    "minecraft", "roblox", "fortnite", "game server", "gaming", "poker",
    "casino", "betting", "sports betting", "crypto", "cryptocurrency",
    "bitcoin", "ethereum", "nft", "forex", "stock trading", "stock market",
    "donutsmp", "steam market", "csgo", "dota", "league of legends",
)

#: Always dropped, retail words or not: a clinical imaging paper is not a
#: retail tool just because it says "product" somewhere.
HARD_OFF_DOMAIN = (
    "clinical", "medical imaging", "fundus", "retinal", "healthcare",
    "electricity retailer", "energy retailer", "radiology", "pathology",
)

#: Evidence that a hit is in our domain.  An off-domain hit that also mentions
#: one of these is kept: "AI product photography for Shopify" is ours.
RETAIL_CONTEXT = (
    "ecommerce", "e-commerce", "retail", "shopify", "woocommerce", "etsy",
    "marketplace", "dropship", "arbitrage", "product", "listing", "sku",
    "inventory", "storefront", "merchant", "seller",
)

#: Minimum spacing between requests, seconds.  GitHub 10/min is the only
#: published quota; arXiv's 3 s is our own politeness, not a provider rule.
PACE = {"github": 2.5, "huggingface": 0.3, "pypi": 0.4, "npm": 0.2, "arxiv": 3.0}

#: Minimum relevance for a hit to become a finding at all.  A single weak
#: secondary keyword (0.5 raw -> 0.2) is not enough evidence to look at.
MIN_RELEVANCE = 0.25
#: Relevance below which even a clean licence is held for review.
ADOPT_MIN_RELEVANCE = 0.30


def load_services(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Read ``ty/services.json``.  Raises when absent — never invents services."""
    source = Path(path or SERVICES_PATH)
    data = json.loads(source.read_text(encoding="utf-8"))
    return list(data.get("services") or [])


def load_gaps(path: Optional[Path] = None) -> Dict[str, float]:
    """Remaining score gap per service from ``ty/scorecards.json``, when present.

    This grounds ``estimated_lift``: a finding cannot claim to lift a service
    more than the gap that exists.  Absent scorecards means no cap (``100.0``)
    and the basis says so.
    """
    source = Path(path or SCORECARDS_PATH)
    if not source.is_file():
        return {}
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
    gaps: Dict[str, float] = {}
    for row in data.get("services") or []:
        try:
            gaps[str(row["id"])] = float(row.get("gap", 100.0))
        except (KeyError, TypeError, ValueError):
            continue
    return gaps


def service_labels(services: List[Dict[str, Any]]) -> Dict[str, str]:
    return {str(s.get("id")): str(s.get("label") or s.get("id")) for s in services}
