"""Golden Goose Finder — free-tier data-provider registry and credit ledger.

Registry of every ZERO-COST data provider the Golden Goose Finder can route
through, with per-task credit costs, monthly/one-time quota models, and a
JSON-persisted credit ledger so scans stay inside the free envelope
(~750 credits per scan → 10-15 scans/mo across all providers).

Honesty rules:
  - ``key_env`` only names the env var holding each key — this module NEVER
    reads, prints, or writes any credential value (§3 hard stop).
  - ``has_key`` is OPERATOR-MAINTAINED metadata (a non-secret flag). It is
    set when the operator confirms the key exists in the profile env; the
    router skips providers without an available key instead of guessing.
  - Credits are conservative: when a provider documents a cost range, the
    registry records the UPPER bound so the ledger never over-promises.
  - This module performs no network calls of any kind.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Task types the router can dispatch (kept in sync with free_tier_router).
TASK_COSTCO_SEARCH = "costco_search"
TASK_SAMS_SEARCH = "sams_club_search"
TASK_AMAZON_SEARCH = "amazon_search"
TASK_AMAZON_PRODUCT = "amazon_product"
TASK_AMAZON_OFFERS = "amazon_offers"
TASK_GENERIC_SCRAPE = "generic_scrape"

ALL_TASKS = frozenset({
    TASK_COSTCO_SEARCH,
    TASK_SAMS_SEARCH,
    TASK_AMAZON_SEARCH,
    TASK_AMAZON_PRODUCT,
    TASK_AMAZON_OFFERS,
    TASK_GENERIC_SCRAPE,
})

# Operator-maintained key-availability metadata (non-secret flags).
# True = the operator confirmed a working key exists for this provider in the
# profile environment. New signups default False until the operator adds them.
KEY_AVAILABLE: Dict[str, bool] = {
    # Proven keys already in the profile env (confirmed in earlier sessions).
    "openwebninja_free": True,
    "bright_data_web_unlocker": True,
    "firecrawl": True,
    "scrape_do": True,
    "chocodata": True,
    "scavio": True,
    "easyparser": True,
    "rapidapi_pool": True,
    "canopy": True,
    # Free signups — keys provided 2026-09-16; user must add to .env.
    "scrapingdog": True,
    "scrapingbee": True,
    "scrapebadger": True,
    "amazonscraperapi": True,
    "apiclaw": True,
    "apify_sams": True,
    # Not yet obtained — waiting on user signup.
    "flybyapis": False,
    "outscraper": False,
}


@dataclass
class FreeTierProvider:
    """One zero-cost data provider with its quota model and per-task costs."""

    id: str
    name: str
    key_env: str  # env var name holding the key — NEVER read as a value here
    monthly_quota: Optional[int]  # credits granted every month (None = n/a)
    one_time_credits: Optional[int]  # credits granted once at signup (None = n/a)
    task_costs: Dict[str, float]  # task_type -> credits per call (upper bound)
    tasks: frozenset  # task types this provider can serve
    rate_note: str = ""
    has_key: bool = False  # operator-maintained metadata flag (set via mark_key_available)

    @property
    def start_credits(self) -> int:
        """Starting credit pool: monthly quota, else one-time credits."""
        if self.monthly_quota is not None:
            return self.monthly_quota
        return self.one_time_credits or 0

    @property
    def quota_model(self) -> str:
        if self.monthly_quota is not None:
            return "monthly"
        if self.one_time_credits is not None:
            return "one_time"
        return "unknown"

    def cost_for(self, task_type: str) -> Optional[float]:
        return self.task_costs.get(task_type)


def _p(
    provider_id: str,
    name: str,
    key_env: str,
    monthly: Optional[int],
    one_time: Optional[int],
    task_costs: Dict[str, float],
    tasks: List[str],
    rate_note: str = "",
) -> FreeTierProvider:
    return FreeTierProvider(
        id=provider_id,
        name=name,
        key_env=key_env,
        monthly_quota=monthly,
        one_time_credits=one_time,
        task_costs=task_costs,
        tasks=frozenset(tasks),
        rate_note=rate_note,
        has_key=KEY_AVAILABLE.get(provider_id, False),
    )


FREE_PROVIDERS: List[FreeTierProvider] = [
    # --- Warehouse-club catalog paths ---
    _p(
        "openwebninja_free", "OpenWebNinja (free)", "OPENWEBNINJA_API_KEY",
        100, None, {TASK_COSTCO_SEARCH: 1.0}, [TASK_COSTCO_SEARCH],
        "100 requests/mo free; Costco search is its strongest surface.",
    ),
    _p(
        "apify_sams", "Apify Sam's Club scraper (free credit)", "APIFY_API_TOKEN",
        5, None, {TASK_SAMS_SEARCH: 1.0}, [TASK_SAMS_SEARCH],
        "Actor: stealth_mode/samsclub-product-search-scraper ($10/1K results); ~$5 free credit/mo.",
    ),
    _p(
        "outscraper", "Outscraper Sam's Club (free)", "OUTSCRAPER_API_KEY",
        None, 500, {TASK_SAMS_SEARCH: 1.0}, [TASK_SAMS_SEARCH],
        "500 free Sam's Club product pulls at signup.",
    ),
    _p(
        "bright_data_web_unlocker", "Bright Data Web Unlocker (free)", "BRIGHTDATA_API_TOKEN",
        5000, None, {
            TASK_COSTCO_SEARCH: 1.0,
            TASK_SAMS_SEARCH: 1.0,
            TASK_AMAZON_SEARCH: 1.0,
            TASK_AMAZON_PRODUCT: 1.0,
            TASK_AMAZON_OFFERS: 1.0,
            TASK_GENERIC_SCRAPE: 1.0,
        },
        [
            TASK_COSTCO_SEARCH, TASK_SAMS_SEARCH, TASK_AMAZON_SEARCH,
            TASK_AMAZON_PRODUCT, TASK_AMAZON_OFFERS, TASK_GENERIC_SCRAPE,
        ],
        "5,000 requests/mo free; the workhorse of the Amazon/catalog paths.",
    ),
    _p(
        "firecrawl", "Firecrawl (free)", "FIRECRAWL_API_KEY",
        1000, None, {
            TASK_GENERIC_SCRAPE: 1.0,
            TASK_AMAZON_PRODUCT: 2.0,
            TASK_COSTCO_SEARCH: 1.0,
        },
        [TASK_GENERIC_SCRAPE, TASK_AMAZON_PRODUCT, TASK_COSTCO_SEARCH],
        "1,000 pages/mo free; generic scrape fallback.",
    ),
    _p(
        "scrape_do", "Scrape.do (free)", "SCRAPEDO_API_KEY",
        1000, None, {
            TASK_GENERIC_SCRAPE: 1.0,
            TASK_AMAZON_PRODUCT: 1.0,
            TASK_COSTCO_SEARCH: 1.0,
        },
        [TASK_GENERIC_SCRAPE, TASK_AMAZON_PRODUCT, TASK_COSTCO_SEARCH],
        "1,000 free requests/mo; scrape fallback.",
    ),
    # --- Amazon search / product / offers ---
    _p(
        "chocodata", "Chocodata Amazon Search (free)", "CHOCODATA_API_KEY",
        None, 1000, {TASK_AMAZON_SEARCH: 5.0}, [TASK_AMAZON_SEARCH],
        "1,000 free credits; search costs ~5 → ~200 searches.",
    ),
    _p(
        "scavio", "Scavio Amazon (free)", "SCAVIO_API_KEY",
        None, 500, {TASK_AMAZON_SEARCH: 2.0, TASK_AMAZON_PRODUCT: 2.0},
        [TASK_AMAZON_SEARCH, TASK_AMAZON_PRODUCT],
        "Free tier quota varies; treat as one-time ~500.",
    ),
    _p(
        "scrapingdog", "Scrapingdog (free 200)", "SCRAPINGDOG_API_KEY",
        None, 200, {
            TASK_AMAZON_SEARCH: 1.0,
            TASK_AMAZON_PRODUCT: 1.0,
            TASK_AMAZON_OFFERS: 2.0,
        },
        [TASK_AMAZON_SEARCH, TASK_AMAZON_PRODUCT, TASK_AMAZON_OFFERS],
        "200 free credits at signup; NOT yet obtained.",
    ),
    _p(
        "scrapingbee", "ScrapingBee (free 1K)", "SCRAPINGBEE_API_KEY",
        None, 1000, {TASK_AMAZON_SEARCH: 1.0, TASK_AMAZON_PRODUCT: 1.0},
        [TASK_AMAZON_SEARCH, TASK_AMAZON_PRODUCT],
        "1,000 free calls at signup; NOT yet obtained.",
    ),
    _p(
        "scrapebadger", "ScrapeBadger (free 1K)", "SCRAPEBADGER_API_KEY",
        None, 1000, {
            TASK_AMAZON_PRODUCT: 10.0,
            TASK_AMAZON_SEARCH: 5.0,
            TASK_AMAZON_OFFERS: 8.0,
        },
        [TASK_AMAZON_PRODUCT, TASK_AMAZON_SEARCH, TASK_AMAZON_OFFERS],
        "1,000 free credits at signup; NOT yet obtained.",
    ),
    _p(
        "flybyapis", "FlyByAPIs Amazon (free 100/mo)", "FLYBYAPIS_API_KEY",
        100, None, {TASK_AMAZON_PRODUCT: 1.0}, [TASK_AMAZON_PRODUCT],
        "100 free requests/mo; NOT yet obtained.",
    ),
    _p(
        "amazonscraperapi", "AmazonScraperApi (free 1K)", "AMAZONSCRAPERAPI_API_KEY",
        None, 1000, {TASK_AMAZON_SEARCH: 1.0, TASK_AMAZON_PRODUCT: 1.0},
        [TASK_AMAZON_SEARCH, TASK_AMAZON_PRODUCT],
        "1,000 free requests at signup; NOT yet obtained.",
    ),
    _p(
        "apiclaw", "APIclaw (free 1K)", "APICLAW_API_KEY",
        None, 1000, {
            TASK_AMAZON_SEARCH: 2.0,
            TASK_AMAZON_PRODUCT: 2.0,
            TASK_AMAZON_OFFERS: 2.0,
        },
        [TASK_AMAZON_SEARCH, TASK_AMAZON_PRODUCT, TASK_AMAZON_OFFERS],
        "1,000 free credits at signup; NOT yet obtained.",
    ),
    _p(
        "rapidapi_pool", "RapidAPI Amazon hosts (free pool)", "RAPIDAPI_API_KEY",
        600, None, {TASK_AMAZON_PRODUCT: 1.0}, [TASK_AMAZON_PRODUCT],
        "6 hosts x ~100 free/mo pooled ~600/mo; product detail lookups.",
    ),
    _p(
        "canopy", "Canopy Amazon (free)", "CANOPY_API_KEY",
        None, 500, {TASK_AMAZON_PRODUCT: 1.0}, [TASK_AMAZON_PRODUCT],
        "Free trial credits; product enrichment.",
    ),
    _p(
        "easyparser", "EasyParser Amazon Offers (free credits)", "EASYPARSER_API_KEY",
        None, 41, {TASK_AMAZON_OFFERS: 1.0}, [TASK_AMAZON_OFFERS],
        "41 credits remaining; only for offer/seller-identity snapshots.",
    ),
]

FREE_PROVIDER_BY_ID: Dict[str, FreeTierProvider] = {p.id: p for p in FREE_PROVIDERS}


def get_provider(provider_id: str) -> Optional[FreeTierProvider]:
    return FREE_PROVIDER_BY_ID.get(provider_id)


def providers_for_task(task_type: str) -> List[FreeTierProvider]:
    """All providers able to serve a task type, in registry order."""
    return [p for p in FREE_PROVIDERS if task_type in p.tasks]


def mark_key_available(provider_id: str, available: bool = True) -> None:
    """Operator-facing metadata toggle (never touches any credential value)."""
    provider = get_provider(provider_id)
    if provider is not None:
        provider.has_key = available
        KEY_AVAILABLE[provider_id] = available


# ---------------------------------------------------------------------------
# Credit ledger (JSON-persisted so monthly budgets survive restarts).
# ---------------------------------------------------------------------------

_DEFAULT_LEDGER_PATH = Path(__file__).resolve().parents[2] / "data" / "free_tier_ledger.json"


class FreeTierLedger:
    """Tracks remaining credits per provider with monthly quota resets."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = Path(path) if path else _DEFAULT_LEDGER_PATH
        self.remaining: Dict[str, float] = {}
        self.used_this_month: Dict[str, float] = {}
        self.month: str = ""
        self._loaded = False

    # -- month handling ----------------------------------------------------

    @staticmethod
    def current_month() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def _reset_for_new_month(self) -> None:
        """Refresh monthly-quota pools; keep one-time pools untouched."""
        self.used_this_month = {}
        for provider in FREE_PROVIDERS:
            if provider.monthly_quota is not None:
                self.remaining[provider.id] = float(provider.monthly_quota)

    # -- persistence -------------------------------------------------------

    def load(self) -> "FreeTierLedger":
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.remaining = {
                    k: float(v) for k, v in (data.get("remaining") or {}).items()
                }
                self.used_this_month = {
                    k: float(v) for k, v in (data.get("used_this_month") or {}).items()
                }
                self.month = str(data.get("month") or "")
        except (OSError, ValueError, TypeError):  # pragma: no cover - IO guard
            self.remaining, self.used_this_month, self.month = {}, {}, ""
        self._init_pools()
        if self.month != self.current_month():
            self.month = self.current_month()
            self._reset_for_new_month()
            self.save()
        self._loaded = True
        return self

    def _init_pools(self) -> None:
        """Seed any provider missing from the ledger with its start credits."""
        for provider in FREE_PROVIDERS:
            if provider.id not in self.remaining:
                self.remaining[provider.id] = float(provider.start_credits)

    def save(self) -> str:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "month": self.month or self.current_month(),
                "remaining": self.remaining,
                "used_this_month": self.used_this_month,
            }
            self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:  # pragma: no cover - unwritable path → keep in-memory only
            pass
        return str(self.path)

    # -- accounting --------------------------------------------------------

    def remaining_credits(self, provider_id: str) -> float:
        self._init_pools()
        return self.remaining.get(provider_id, 0.0)

    def can_debit(self, provider_id: str, amount: float) -> bool:
        return self.remaining_credits(provider_id) >= amount

    def debit(self, provider_id: str, amount: float) -> float:
        """Consume credits; returns the new remaining balance."""
        self._init_pools()
        current = self.remaining.get(provider_id, 0.0)
        new_remaining = max(0.0, current - float(amount))
        self.remaining[provider_id] = new_remaining
        self.used_this_month[provider_id] = (
            self.used_this_month.get(provider_id, 0.0) + float(amount)
        )
        return new_remaining

    def restore(self, provider_id: str, amount: float) -> None:
        """Refund credits after a failed call (best-effort accounting)."""
        self._init_pools()
        self.remaining[provider_id] = (
            self.remaining.get(provider_id, 0.0) + float(amount)
        )

    def summary(self) -> Dict[str, Any]:
        self._init_pools()
        return {
            "month": self.month or self.current_month(),
            "remaining": dict(self.remaining),
            "used_this_month": dict(self.used_this_month),
            "providers": len(FREE_PROVIDERS),
        }


def load_default_ledger() -> FreeTierLedger:
    """Load (or create) the shared repo ledger."""
    ledger = FreeTierLedger()
    if not ledger._loaded:  # noqa: SLF001 - internal guard
        ledger.load()
    return ledger