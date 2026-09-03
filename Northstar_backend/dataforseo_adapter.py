"""DataForSEO Amazon Merchant adapter (exclusive primary enrichment provider).

This module is the FULL CODE PATH for the DataForSEO live/paid merchant
cross-check. Per the Master Brain v2 operating doctrine, the entire feature is
built end-to-end (transport, budget ledger, approval gate, cache, contract
validation, shortlist gate, preflight, normalize/compare, orchestration),
but the LIVE transport is armed ONLY when BOTH:

  DATAFORSEO_ENABLED = "true"            (feature flag; explicit opt-in)
  DATAFORSEO_TRANSPORT_ENABLED = "true"  (runtime transport arm; strict parse)
  DATAFORSEO_LOGIN / DATAFORSEO_PASSWORD are set

Without the arm-flags AND credentials, every path fails closed (zero network,
LIVE_CALLS_MADE=0). Building/running the offline & mocked tests is safe; only
a fully-armed explicit live run spends provider budget, and that still requires
the operator's fresh, explicit, named approval to EXECUTE.

What DataForSEO actually returns (verified against the live Merchant API docs):
  * asin task  -> amazon_product_info: title, price_from/price_to (current
    listing price), rating {value, votes_count}, categories, and a
    `product_information` block whose "Item details" body contains a
    "Best Sellers Rank" TEXT string (e.g. "#1,291 in Video Games ...").
    It does NOT return a structured Buy Box winner/seller.
  * sellers task -> list of amazon_seller_item: seller_name, seller_url
    (carries `isAmazonFulfilled=0|1` and `seller=...`), price {current,
    regular, currency}, condition, rating.

Mapping (null-first; nothing invented):
  * buy_box_price      <- asin.price_from (current listing price proxy)
  * bsr                <- parsed from "Best Sellers Rank" text via intel_schema
  * title / rating / categories <- asin task
  * offers[]           <- sellers task; FBA/FBM derived from isAmazonFulfilled
  * buy_box_seller     <- sellers item flagged buybox_winner when present,
                            else null (DataForSEO does not reliably flag it)
  * cost_usd           <- sum of raw provider-reported task cost (fractional USD)
  * credits_used       <- None (DataForSEO does not report a separate credit
                            field; cost and credits must not be conflated)
"""

import os
import re
import json
import time
import hashlib
import tempfile
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import requests
from dotenv import load_dotenv

from proof_batch_contracts import (
    merchant_task_post_url,
    merchant_task_get_url,
    evaluate_dataforseo_task_post,
    evaluate_dataforseo_task_get,
    evaluate_dataforseo_labs_live,
    GuardError,
)


class AmbiguousTransportError(Exception):
    """Raised when a DataForSEO transport call returns an ambiguous outcome
    (e.g., a POST timeout) where success/failure cannot be determined, so the
    run must NOT be auto-retried or silently marked successful."""

    pass


# ---------------------------------------------------------------------------
# Runtime configuration (env-driven; values never logged/printed).
# ---------------------------------------------------------------------------
try:
    load_dotenv()
except Exception:
    pass

try:
    from intel_schema import normalize_bsr  # type: ignore
except Exception:
    normalize_bsr = None  # type: ignore

DATAFORSEO_LOGIN = os.getenv("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.getenv("DATAFORSEO_PASSWORD")
DATAFORSEO_ENABLED = (os.getenv("DATAFORSEO_ENABLED") or "").strip().lower() == "true"
DATAFORSEO_TRANSPORT_ENABLED = (os.getenv("DATAFORSEO_TRANSPORT_ENABLED") or "").strip().lower() == "true"

REQUEST_TIMEOUT_SECONDS = 60
ASIN_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")
MAX_POLL_SECONDS = 120
POLL_INTERVAL_SECONDS = 5

# Default budgets (cents). First-ever approved run is a 1-cent canary; every
# later run gets the full default ceiling.
DATAFORSEO_FIRST_RUN_BUDGET_CENTS = 1
DATAFORSEO_BUDGET_CENTS = 100
MAX_TASKS_PER_ASIN = 2

# Task-type -> Merchant family endpoint mapping.
TASK_TYPE_FAMILY = {
    "product": "products",
    "asin": "asin",
    "sellers": "sellers",
    "bulk_search_volume": "bulk_search_volume",
    "related_keywords": "related_keywords",
}
# Merchant task types that are submit-able in standard queue.
MERCHANT_TASK_TYPES = ("product", "asin", "sellers")
# Labs task types (read-only inspection; auto-submission requires env gate).
LABS_TASK_TYPES = (
    "product_rank_overview",
    "ranked_keywords",
    "bulk_search_volume",
    "related_keywords",
    "product_competitors",
    "keyword_intersection",
)


def _norm_true(value: Any) -> bool:
    return isinstance(value, str) and value.strip().lower() == "true"


def _feature_truthy(value: Any) -> bool:
    """Lenient feature-flag truthiness for DATAFORSEO_ENABLED.

    Distinct from the strict transport arm (``_transport_enabled``, which
    ONLY 'true' enables). An explicit opt-in of '1'/'true'/'yes'/'on' all
    enable the feature; everything else (absent, '0', 'false', 'off') leaves
    it disabled by default.
    """
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return False
    return value.strip().lower() in ("1", "true", "yes", "on")


def _feature_enabled_from_env(env: Optional[Dict[str, Any]] = None) -> bool:
    src = env if isinstance(env, dict) else os.environ
    return _feature_truthy(src.get("DATAFORSEO_ENABLED"))


def _transport_enabled() -> bool:
    """Strict runtime transport kill-switch. ONLY an exact 'true' (any case)
    enables; every other value (including '1', 'yes', 'on', '0') disables."""
    raw = os.getenv("DATAFORSEO_TRANSPORT_ENABLED")
    if not isinstance(raw, str):
        return False
    return raw.strip().lower() == "true"


# ---- Paths (override via env so tests stay hermetic) ----------------------
def _env_path(key: str) -> str:
    return os.path.expanduser(os.path.expandvars(os.getenv(key, "")))


def ledger_path() -> str:
    return _env_path("DATAFORSEO_LEDGER_PATH") or os.path.join(_adapter_root(), "ledger.jsonl")


def cache_dir() -> str:
    return _env_path("DATAFORSEO_CACHE_DIR") or os.path.join(_adapter_root(), "cache")


def raw_dir() -> str:
    return _env_path("DATAFORSEO_RAW_DIR") or os.path.join(_adapter_root(), "raw")


def approval_state_path() -> str:
    return _env_path("DATAFORSEO_APPROVAL_STATE_PATH") or os.path.join(_adapter_root(), "approval.json")


def _adapter_root() -> str:
    return _env_path("DATAFORSEO_ADAPTER_ROOT") or tempfile.gettempdir()


def _clear_runtime_env() -> None:
    """Recompute runtime feature/transport after tests mutate os.environ.

    Kept as a no-op hook (the strict parsing reads os.environ lazily, so no
    module-level caching is used)."""


# ---------------------------------------------------------------------------
# Feature flag + config.
# ---------------------------------------------------------------------------
def feature_enabled(env: Optional[Dict[str, Any]] = None) -> bool:
    """DATAFORSEO_ENABLED is an explicit opt-in; false by default."""
    return _feature_enabled_from_env(env)


def load_config(env: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Merged feature/config snapshot (fail-closed defaults)."""
    src = env if isinstance(env, dict) else os.environ
    enabled = _feature_truthy(src.get("DATAFORSEO_ENABLED"))
    mode = str(src.get("DATAFORSEO_MODE") or "standard_queue").strip() or "standard_queue"
    transport = _norm_true(src.get("DATAFORSEO_TRANSPORT_ENABLED"))

    est_cost_raw = src.get("DATAFORSEO_ESTIMATED_COST_CENTS")
    if est_cost_raw is not None:
        try:
            est_cost = int(str(est_cost_raw).strip())
        except (TypeError, ValueError):
            raise GuardError("DATAFORSEO_ESTIMATED_COST_CENTS must be an integer")
    else:
        est_cost = None

    cfg = {
        "enabled": enabled,
        "mode": mode,
        "transport_armed": transport and bool(src.get("DATAFORSEO_LOGIN")
                                              and src.get("DATAFORSEO_PASSWORD")),
        "has_credentials": bool(src.get("DATAFORSEO_LOGIN")
                                and src.get("DATAFORSEO_PASSWORD")),
        "transport_enabled": transport,
        "estimated_cost_cents": est_cost,
        "budget_cents": _int_env(src, "DATAFORSEO_BUDGET_CENTS", DATAFORSEO_BUDGET_CENTS),
        "first_run_budget_cents": _int_env(
            src, "DATAFORSEO_FIRST_RUN_BUDGET_CENTS", DATAFORSEO_FIRST_RUN_BUDGET_CENTS),
        "cache_ttl_hours": _int_env(src, "DATAFORSEO_CACHE_TTL_HOURS", 24),
    }
    if est_cost is not None and est_cost < 0:
        raise GuardError("DATAFORSEO_ESTIMATED_COST_CENTS must be non-negative")
    validate_config(cfg)
    return cfg


def _int_env(src: Dict[str, Any], key: str, default: int) -> int:
    raw = src.get(key)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def validate_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Only the standard queue is permitted for merchant submission."""
    if cfg.get("mode") != "standard_queue":
        raise GuardError("only DataForSEO Standard queue is supported (mode must be standard_queue)")
    return cfg


# ---------------------------------------------------------------------------
# Endpoint allowlist (offline-authoritative, matching Merchant/Labs docs).
# ---------------------------------------------------------------------------
def classify_endpoint(url: str, method: str = "GET") -> str:
    """Classify an absolute DataForSEO URL into an allowed class.

    Allowed (Merchant Standard async):
      .../v3/merchant/amazon/{products|asin|sellers}/task_post        POST
      .../v3/merchant/amazon/{products|asin|sellers}/task_get/advanced/{id}  GET
    Allowed (Labs live, read-only inspection):
      .../v3/dataforseo_labs/amazon/{family}/live                     POST/GET
    Everything else (live endpoints, product_info, seller_info, search,
    reviews, tasks_ready, task_get without an id) is REFUSED with GuardError.
    """
    if not isinstance(url, str) or not url.strip():
        raise GuardError("empty DataForSEO endpoint URL")
    parsed = urlparse(url.strip())
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 4 and parts[0] == "v3" and parts[1] == "dataforseo_labs":
        if parts[2] == "amazon" and len(parts) == 5 and parts[4] == "live":
            return "labs_live"
        raise GuardError("dataforseo labs endpoint refused")
    if len(parts) < 5 or parts[:2] != ["v3", "merchant"] or parts[2] != "amazon":
        raise GuardError("dataforseo endpoint refused (not v3/merchant/amazon)")
    family = parts[3]
    if family not in ("products", "asin", "sellers"):
        raise GuardError("dataforseo endpoint refused (unsupported merchant family)")
    op = parts[4]
    if op == "task_post" and method.upper() == "POST" and len(parts) == 5:
        return "task_post"
    if op == "task_get":
        # task_get requires an explicit task id. Both forms are accepted:
        #   .../task_get/{id}            (6 parts)
        #   .../task_get/advanced/{id}   (7 parts)
        if method.upper() == "GET":
            valid6 = (len(parts) == 6 and parts[5] and "/" not in parts[5])
            valid7 = (len(parts) == 7 and parts[5] == "advanced"
                      and parts[6] and "/" not in parts[6])
            if valid6 or valid7:
                return "task_get"
        raise GuardError("dataforseo task_get requires an explicit task id")
    raise GuardError("dataforseo endpoint refused")


def _merchant_task_post_url(family: str) -> str:
    return merchant_task_post_url(family)


def verify_endpoint_allowlist() -> Dict[str, Any]:
    """Self-check: the allowlist must permit the documented Merchant Standard
    families and refuse every disallowed route. Used by tests + preflight."""
    base = "https://api.dataforseo.com"
    result = {
        "all_pass": True,
        "products_task_post_allowed": True,
        "products_task_get_allowed": True,
        "asin_task_post_allowed": True,
        "sellers_task_post_allowed": True,
        "product_info_rejected": True,
        "seller_info_rejected": True,
        "search_rejected": True,
        "reviews_rejected": True,
        "tasks_ready_rejected": True,
    }

    def _check(expect, fn):
        try:
            out = fn()
            return out if expect else False
        except GuardError:
            return not expect

    result["products_task_post_allowed"] = _check(
        True, lambda: classify_endpoint(f"{base}/v3/merchant/amazon/products/task_post", "POST"))
    result["products_task_get_allowed"] = _check(
        True, lambda: classify_endpoint(
            f"{base}/v3/merchant/amazon/products/task_get/advanced/t-1", "GET"))
    result["asin_task_post_allowed"] = _check(
        True, lambda: classify_endpoint(f"{base}/v3/merchant/amazon/asin/task_post", "POST"))
    result["sellers_task_post_allowed"] = _check(
        True, lambda: classify_endpoint(f"{base}/v3/merchant/amazon/sellers/task_post", "POST"))
    result["product_info_rejected"] = _check(
        False, lambda: classify_endpoint(f"{base}/v3/merchant/amazon/product_info/task_post", "POST"))
    result["seller_info_rejected"] = _check(
        False, lambda: classify_endpoint(f"{base}/v3/merchant/amazon/seller_info/task_post", "POST"))
    result["search_rejected"] = _check(
        False, lambda: classify_endpoint(f"{base}/v3/merchant/amazon/search/task_post", "POST"))
    result["reviews_rejected"] = _check(
        False, lambda: classify_endpoint(f"{base}/v3/merchant/amazon/reviews/task_post", "POST"))
    result["tasks_ready_rejected"] = _check(
        False, lambda: classify_endpoint(f"{base}/v3/merchant/amazon/products/tasks_ready", "GET"))

    result["all_pass"] = all(result[k] for k in result if k != "all_pass")
    return result


# ---------------------------------------------------------------------------
# Contract validation (single-ASIN, bounded task types).
# ---------------------------------------------------------------------------
def validate_contract(body: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a single-ASIN validation contract.

    Produces the normalized contract dict used downstream. Rejects batch/list/
    wildcard ASINs, keyword-only searches, unknown task types, and Labs task
    types unless DATAFORSEO_LABS_AUTO_SUBMIT is an explicit opt-in.
    """
    asin = body.get("asin")
    if isinstance(asin, list):
        raise GuardError("a single ASIN is required (got a list)")
    if not isinstance(asin, str) or not asin.strip():
        raise GuardError("a nonblank single ASIN is required")
    asin = asin.strip()
    if not ASIN_PATTERN.fullmatch(asin):
        raise GuardError("invalid ASIN; expected exactly 10 alphanumeric characters")
    marketplace = body.get("marketplace") or "amazon.com"
    bd_snapshot_ref = body.get("bd_snapshot_ref")
    approval_run_id = body.get("approval_run_id") or ""

    if body.get("keyword"):
        raise GuardError("keyword-only searches are not part of the validation contract")

    task_types = body.get("task_types")
    if task_types is None:
        task_types = ["product"]
    if not isinstance(task_types, list):
        raise GuardError("task_types must be a list")
    task_types = [str(t).strip() for t in task_types if str(t).strip()]
    if len(task_types) > 2:
        raise GuardError("at most two task types are supported per validation")
    allowed = set(MERCHANT_TASK_TYPES)
    labs_allowed = _norm_true(os.getenv("DATAFORSEO_LABS_AUTO_SUBMIT"))
    for t in task_types:
        if t not in allowed and t not in LABS_TASK_TYPES:
            raise GuardError(f"unsupported task type: {t}")
        if t in LABS_TASK_TYPES and not labs_allowed:
            raise GuardError(
                "labs task types require DATAFORSEO_LABS_AUTO_SUBMIT opt-in")

    return {
        "asin": asin,
        "marketplace": marketplace,
        "bd_snapshot_ref": bd_snapshot_ref,
        "approval_run_id": approval_run_id,
        "task_types": task_types,
        "valid": True,
    }


# ---------------------------------------------------------------------------
# Shortlist gate (internal product-analysis evidence).
# ---------------------------------------------------------------------------
def candidate_passed_shortlist(asin: str, bd_snapshot_ref: Optional[str] = None):
    """Default shortlist lookup. Only ASINs that the offline product-analysis
    pipeline already marked Pass (economics_tier present) proceed.

    Returns (passed: bool, evidence: dict). Never makes a network call.
    """
    try:
        from proof_batch import cached_shortlist_lookup  # type: ignore
    except Exception:
        cached_shortlist_lookup = None
    if cached_shortlist_lookup is not None:
        try:
            ev = cached_shortlist_lookup(asin, bd_snapshot_ref)
            return (ev.get("verdict") == "Pass", ev or {})
        except Exception:
            return (False, {})
    return (False, {"reason": "shortlist lookup unavailable"})


# ---------------------------------------------------------------------------
# Approval gate.
# ---------------------------------------------------------------------------
def _approval_records() -> List[Dict[str, Any]]:
    path = approval_state_path()
    if not os.path.isfile(path):
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (json.JSONDecodeError, OSError, ValueError):
        return []
    if isinstance(data, list):
        return data
    return []


def _write_approval_records(records: List[Dict[str, Any]]) -> None:
    path = approval_state_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(records, fh)


def create_approval(run_id: str, token: str) -> Dict[str, Any]:
    """Record an explicit one-run approval. The operator token MUST equal the
    run_id exactly (fail-closed). Nothing is executed by this alone."""
    if not isinstance(run_id, str) or not run_id.strip():
        raise GuardError("approval run_id is required")
    if not isinstance(token, str) or not token.strip() or token.strip() != run_id.strip():
        raise GuardError("approval token must equal the approval run_id exactly")
    run_id = run_id.strip()
    rec = {"run_id": run_id, "run_status": "authorized",
           "created_at": time.time()}
    records = [r for r in _approval_records() if r.get("run_id") != run_id]
    records.append(rec)
    _write_approval_records(records)
    return rec


def _approved_run_ids() -> List[str]:
    return [r.get("run_id") for r in _approval_records()
            if r.get("run_status") == "authorized"]


def _require_approval(run_id: str, token: str) -> None:
    if not isinstance(token, str) or not token.strip() or token.strip() != run_id.strip():
        raise GuardError("missing or mismatched operator approval token")
    if run_id.strip() not in _approved_run_ids():
        raise GuardError(f"no authorization record for run_id {run_id!r}")


def is_first_approved_run(run_id: str) -> bool:
    """True if this run_id is the earliest authorized run (the 1-cent canary)."""
    ids = sorted(_approved_run_ids())
    if not ids:
        return False
    return run_id.strip() == ids[0]


def effective_budget_cents(run_id: str) -> int:
    """First-ever approved run gets a 1-cent canary; all later runs the default."""
    if is_first_approved_run(run_id):
        return DATAFORSEO_FIRST_RUN_BUDGET_CENTS
    return DATAFORSEO_BUDGET_CENTS


# ---------------------------------------------------------------------------
# Idempotency + budget ledger.
# ---------------------------------------------------------------------------
def idempotency_key(run_id: str, asin: str, marketplace: str,
                    task_type: str, bd_snapshot_ref: Optional[str]) -> str:
    raw = f"{run_id}|{marketplace}|{asin}|{task_type}|{bd_snapshot_ref}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class Ledger:
    """Append-only JSONL ledger of per-task planning/result records.

    Fail-closed and idempotent: a repeated plan for the same idempotency key
    does not double-count. Budget and per-ASIN caps are enforced on planning.
    """

    def __init__(self, path: Optional[str] = None):
        self.path = path or ledger_path()
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)

    def _read(self) -> List[Dict[str, Any]]:
        if not os.path.isfile(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except (json.JSONDecodeError, ValueError):
                    continue
        return out

    def _append(self, rec: Dict[str, Any]) -> None:
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")

    def _rewrite(self, records: List[Dict[str, Any]]) -> None:
        with open(self.path, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec) + "\n")

    def records(self, request_state: Optional[str] = None) -> List[Dict[str, Any]]:
        recs = self._read()
        if request_state is None:
            return recs
        return [r for r in recs if r.get("request_state") == request_state]

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        for r in self._read():
            if r.get("idempotency_key") == key:
                return r
        return None

    def count_tasks(self, asin: str) -> int:
        return sum(1 for r in self._read() if r.get("asin") == asin)

    def reserved_plus_completed(self) -> int:
        total = 0
        for r in self._read():
            total += int(r.get("est_cost_cents") or r.get("actual_cost_cents") or 0)
        return total


def ledger_plan_task(
    ledger: Ledger,
    run_id: str,
    asin: str,
    marketplace: str,
    task_type: str,
    endpoint_family: str,
    bd_snapshot_ref: Optional[str],
    est_cost_cents: int,
    budget_cents: int,
) -> Dict[str, Any]:
    """Plan one task in the ledger with budget + per-ASIN caps enforced.

    Returns the planned record (request_state='planned'). Raises GuardError on
    the per-ASIN cap or budget exhaustion. Idempotent: the same key replans to
    the same record without a second row.
    """
    key = idempotency_key(run_id, asin, marketplace, task_type, bd_snapshot_ref)
    records = ledger.records()

    # Per-ASIN cap is enforced BEFORE the idempotency dedup, so a second
    # identical plan for the same ASIN above the cap is still refused (the
    # idempotency return only short-circuits when within budget+cap limits).
    asin_count = sum(1 for r in records if r.get("asin") == asin)
    if asin_count >= MAX_TASKS_PER_ASIN:
        raise GuardError(f"max {MAX_TASKS_PER_ASIN} tasks per ASIN reached for {asin}")

    existing = ledger.get(key)
    if existing is not None:
        return existing

    reserved = sum(int(r.get("est_cost_cents") or 0) for r in records)
    if reserved + int(est_cost_cents or 0) > int(budget_cents or 0):
        rec = {
            "idempotency_key": key,
            "run_id": run_id,
            "asin": asin,
            "marketplace": marketplace,
            "task_type": task_type,
            "endpoint_family": endpoint_family,
            "bd_snapshot_ref": bd_snapshot_ref,
            "est_cost_cents": 0,  # a rejected plan reserves nothing
            "request_state": "budget_rejected",
            "ts": time.time(),
        }
        ledger._append(rec)
        raise GuardError("budget ceiling exceeded for this run")

    rec = {
        "idempotency_key": key,
        "run_id": run_id,
        "asin": asin,
        "marketplace": marketplace,
        "task_type": task_type,
        "endpoint_family": endpoint_family,
        "bd_snapshot_ref": bd_snapshot_ref,
        "est_cost_cents": int(est_cost_cents or 0),
        "budget_cents": int(budget_cents or 0),
        "request_state": "planned",
        "ts": time.time(),
    }
    ledger._append(rec)
    return rec


def _update_ledger(ledger: Ledger, key: str, updates: Dict[str, Any]) -> None:
    records = ledger._read()
    for i, r in enumerate(records):
        if r.get("idempotency_key") == key:
            records[i] = {**r, **updates}
    ledger._rewrite(records)


# ---------------------------------------------------------------------------
# Cache / raw persistence (cache-first; raw preserved separately).
# ---------------------------------------------------------------------------
def _cache_key(asin: str, marketplace: str, task_type: str) -> str:
    return hashlib.sha256(f"{asin}|{marketplace}|{task_type}".encode("utf-8")).hexdigest()


def _cache_file(asin: str, marketplace: str, task_type: str) -> str:
    return os.path.join(cache_dir(), _cache_key(asin, marketplace, task_type) + ".json")


def _raw_file(run_id: str, asin: str, task_type: str) -> str:
    return os.path.join(raw_dir(), f"{run_id}-{asin}-{task_type}.json")


def cache_put(asin: str, marketplace: str, task_type: str,
              norm: Dict[str, Any]) -> str:
    d = cache_dir()
    os.makedirs(d, exist_ok=True)
    path = _cache_file(asin, marketplace, task_type)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(norm, fh)
    return path


def cache_get(asin: str, marketplace: str, task_type: str) -> Optional[Dict[str, Any]]:
    path = _cache_file(asin, marketplace, task_type)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError, ValueError):
        return None


def raw_put(run_id: str, asin: str, task_type: str, raw: Dict[str, Any]) -> str:
    d = raw_dir()
    os.makedirs(d, exist_ok=True)
    path = _raw_file(run_id, asin, task_type)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(raw, fh)
    return path


# ---------------------------------------------------------------------------
# Normalization (null-first / allowlist of supported fields only).
# ---------------------------------------------------------------------------
def normalize_provider_record(
    raw: Dict[str, Any],
    asin: str,
    marketplace: str,
    task_type: str,
) -> Dict[str, Any]:
    """Normalize one raw DataForSEO task result item to the validation shape.

    Only allowlisted fields are carried; any other key (e.g. secret_field) is
    dropped. Unobserved economic fields are None, never invented. purchase
    authorization is always False here (that lives in a later gate).
    """
    endpoint_family = _endpoint_family_for(task_type)
    price = raw.get("price")
    observed_price = None
    if isinstance(price, dict):
        observed_price = price.get("value")
    elif isinstance(price, (int, float)) and not isinstance(price, bool):
        observed_price = float(price)
    if observed_price is None:
        observed_price = raw.get("observed_price")

    seller_offer_count = None
    sellers = raw.get("sellers")
    if isinstance(sellers, dict):
        seller_offer_count = sellers.get("offer_count")
    if seller_offer_count is None and endpoint_family == "sellers":
        # Sellers family may surface offer count at the top level too.
        seller_offer_count = raw.get("seller_offer_count")

    record = {
        "source": "dataforseo",
        "asin": raw.get("asin") or asin,
        "title": raw.get("title"),
        "brand": raw.get("brand"),
        "observed_price": _to_float(observed_price),
        "condition": raw.get("condition"),
        "fulfillment_signal": raw.get("fulfillment_signal"),
        "seller_offer_count": seller_offer_count,
        "sales_estimate": None,
        "buy_box_owner": None,
        "fba_fee": None,
        "purchase_authorized": False,
        "endpoint_family": endpoint_family,
        "task_type": task_type,
        "product_url": raw.get("product_url"),
        "request_state": raw.get("request_state"),
    }
    return record


def _endpoint_family_for(task_type: str) -> str:
    if task_type in ("product", "asin", "sellers"):
        return TASK_TYPE_FAMILY[task_type]
    return task_type


def _to_float(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def compare_with_bright_data(bd: Dict[str, Any], df_norm: Dict[str, Any]) -> Dict[str, Any]:
    """Compare a Bright Data record vs the DataForSEO-normalized record.

    Never mutates either input. Returns classification matched | mismatch |
    incomplete | provider_error plus review_flags and preserved values. Does
    NOT authorize purchase (purchase_authorized=False always here).
    """
    bd_frozen = json.loads(json.dumps(bd))

    if df_norm.get("request_state") == "provider_error":
        return {
            "classification": "provider_error",
            "review_flags": ["dataforseo_provider_error"],
            "bright_data_observed_value": bd_frozen,
            "dataforseo_observed_value": df_norm,
            "purchase_authorized": False,
        }

    bd_title = bd.get("title")
    df_title = df_norm.get("title")
    bd_price = bd.get("observed_price")
    df_price = df_norm.get("observed_price")
    bd_brand = bd.get("brand")
    df_brand = df_norm.get("brand")

    if df_title is None and df_price is None and df_brand is None:
        return {
            "classification": "incomplete",
            "review_flags": ["dataforseo_incomplete"],
            "bright_data_observed_value": bd_frozen,
            "dataforseo_observed_value": df_norm,
            "purchase_authorized": False,
        }

    flags: List[str] = []
    if bd_title != df_title:
        flags.append("mismatch_title")
    if _to_float(bd_price) != _to_float(df_price):
        flags.append("mismatch_observed_price")

    if flags:
        return {
            "classification": "mismatch",
            "review_flags": flags,
            "bright_data_observed_value": bd_frozen,
            "dataforseo_observed_value": df_norm,
            "purchase_authorized": False,
        }

    return {
        "classification": "matched",
        "review_flags": [],
        "bright_data_observed_value": bd_frozen,
        "dataforseo_observed_value": df_norm,
        "purchase_authorized": False,
    }


# ---------------------------------------------------------------------------
# Preflight (no execution; reports what WOULD happen).
# ---------------------------------------------------------------------------
def preflight(
    asin: str,
    marketplace: str,
    bd_snapshot_ref: Optional[str],
    approval_run_id: Optional[str] = None,
    lookup=None,
    task_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Report a planned validation without making any provider call.

    LIVE_CALLS_MADE is always 0. Surfaces the feature flag, the explicit
    live-approval requirement, the endpoint allowlist, the effective budget
    ceiling, generated idempotency keys, and the candidate shortlist/contract
    verdicts.
    """
    lookup = lookup or candidate_passed_shortlist
    lookup_result = lookup(asin, bd_snapshot_ref)
    if isinstance(lookup_result, dict):
        passed = lookup_result.get("verdict") == "Pass"
        evidence = lookup_result
    else:
        passed, evidence = lookup_result
    cfg = load_config()

    contract_valid = True
    if task_types:
        contract_body = {
            "asin": asin, "marketplace": marketplace,
            "bd_snapshot_ref": bd_snapshot_ref,
            "approval_run_id": approval_run_id, "task_types": task_types,
        }
        try:
            validate_contract(contract_body)
        except GuardError:
            contract_valid = False

    task_types = task_types or ["product"]
    keys = []
    for tt in task_types:
        keys.append({
            "key_prefix": idempotency_key(
                approval_run_id or "", asin, marketplace, tt, bd_snapshot_ref)[:12],
            "task_type": tt,
        })

    return {
        "LIVE_CALLS_MADE": 0,
        "feature_flag": {"enabled": cfg["enabled"]},
        "explicit_live_approval_required": True,
        "allowed_endpoint_classes": ["task_post", "task_get"],
        "budget": {
            "effective_ceiling_cents": effective_budget_cents(approval_run_id or ""),
            "first_run_budget_cents": cfg["first_run_budget_cents"],
        },
        "candidate": {
            "shortlist_passed": bool(passed),
            "shortlist_evidence": evidence,
            "contract_valid": contract_valid,
        },
        "idempotency_keys": keys,
    }


# ---------------------------------------------------------------------------
# Standard transport (armed only with explicit flags + credentials).
# ---------------------------------------------------------------------------
class DataForSEOStandardTransport:
    """Standard DataForSEO transport. Construction makes zero network calls.

    A real call only occurs when ``allow_live`` is True AND the runtime arm
    (``DATAFORSEO_TRANSPORT_ENABLED`` strictly 'true') and credentials are
    present. Otherwise ``submit``/``retrieve`` fail closed with GuardError.
    On an ambiguous timeout it raises AmbiguousTransportError so the caller
    reconciles manually instead of retrying blindly.
    """

    def __init__(self, allow_live: bool = False):
        self.allow_live = bool(allow_live)

    def _credentials(self) -> Optional[Tuple[str, str]]:
        if self.allow_live and _transport_enabled():
            login = os.getenv("DATAFORSEO_LOGIN")
            password = os.getenv("DATAFORSEO_PASSWORD")
            if login and password:
                return (login, password)
        return None

    def submit(self, url: str, payload: Any) -> Dict[str, Any]:
        classify_endpoint(url, "POST")
        creds = _require_creds(self)
        try:
            resp = requests.post(
                url, json=payload, timeout=REQUEST_TIMEOUT_SECONDS, auth=creds)
        except requests.exceptions.Timeout:
            raise AmbiguousTransportError("POST timeout, outcome unknown")
        except requests.exceptions.RequestException as exc:
            raise GuardError("dataforseo transport error: %s" % exc)
        if resp.status_code != 200:
            raise GuardError("dataforseo transport HTTP %d" % resp.status_code)
        try:
            return resp.json()
        except (json.JSONDecodeError, ValueError):
            raise GuardError("dataforseo response was not valid JSON")

    def retrieve(self, url: str) -> Dict[str, Any]:
        classify_endpoint(url, "GET")
        creds = _require_creds(self)
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS, auth=creds)
        except requests.exceptions.Timeout:
            raise AmbiguousTransportError("GET timeout, outcome unknown")
        except requests.exceptions.RequestException as exc:
            raise GuardError("dataforseo transport error: %s" % exc)
        if resp.status_code != 200:
            raise GuardError("dataforseo transport HTTP %d" % resp.status_code)
        try:
            return resp.json()
        except (json.JSONDecodeError, ValueError):
            raise GuardError("dataforseo response was not valid JSON")


def _require_creds(transport: "DataForSEOStandardTransport") -> Tuple[str, str]:
    """Return armed credentials or raise GuardError WITHOUT any credential
    access or network call.

    The runtime transport arm is checked BEFORE touching ``_credentials()``
    (so a disabled transport never even reads credentials, satisfying the
    'creds.assert_not_called' contract). Credentials must be a non-empty
    2-tuple of login/password; anything else (empty creds, wrong shape) is a
    clean refusal with no network call."""
    if not _transport_enabled():
        raise GuardError("DataForSEO transport not armed; no network call made")
    creds = transport._credentials()
    if not isinstance(creds, (tuple, list)) or len(creds) != 2:
        raise GuardError("DataForSEO transport not armed; no network call made")
    login, password = creds
    if not login or not password:
        raise GuardError("DataForSEO transport not armed; no network call made")
    return (login, password)


# ---------------------------------------------------------------------------
# Orchestration: execute_validation + retrieve_validation.
# ---------------------------------------------------------------------------
def execute_validation(
    body: Dict[str, Any],
    operator_token: str = "",
    lookup=None,
    transport: Optional[DataForSEOStandardTransport] = None,
) -> Dict[str, Any]:
    """Guard a single-ASIN standard-queue validation run end-to-end.

    Gates (in order, all fail-closed):
      1. Approval token must exactly equal the run_id and an authorization
         record must exist.
      2. Contract must validate (single bounded ASIN, allowed task types).
      3. Shortlist gate: the candidate must have passed.
      4. Cache-first: a cached normalized record short-circuits with
         LIVE_CALLS_MADE=0.
      5. Transport arming: if the transport is not armed, every task reports
         source 'transport_refused' with zero live calls; if armed, the
         submitted task is ledged and any ambiguous outcome is marked
         'needs_manual_reconciliation' (never auto-retried).
    """
    run_id = (body or {}).get("approval_run_id") or ""
    _require_approval(run_id, operator_token)

    contract = validate_contract(body)
    asin = contract["asin"]
    marketplace = contract["marketplace"]
    bd_ref = contract["bd_snapshot_ref"]

    lookup = lookup or candidate_passed_shortlist
    lookup_result = lookup(asin, bd_ref)
    if isinstance(lookup_result, dict):
        # Contract: lookup returns a dict with a 'verdict' key ("Pass" for pass).
        passed = lookup_result.get("verdict") == "Pass"
        evidence = lookup_result
    else:
        passed, evidence = lookup_result
    if not passed:
        raise GuardError(f"candidate {asin} did not pass the internal shortlist gate")

    transport = transport or DataForSEOStandardTransport(allow_live=True)
    live_calls = 0
    results = []
    ledger = Ledger()
    budget_cents = effective_budget_cents(run_id)

    for task_type in contract["task_types"]:
        endpoint_family = _endpoint_family_for(task_type)
        key = idempotency_key(run_id, asin, marketplace, task_type, bd_ref)
        est_cost_cents = _estimate_cost_cents(task_type)

        # Cache-first.
        cached = cache_get(asin, marketplace, task_type)
        if cached is not None:
            results.append({
                "task_type": task_type,
                "endpoint_family": endpoint_family,
                "asin": asin,
                "source": "cache",
                "live_calls_made": 0,
                "idempotency_key": key,
                "normalized": cached,
            })
            continue

        try:
            ledger_plan_task(ledger, run_id, asin, marketplace, task_type,
                             endpoint_family, bd_ref, est_cost_cents, budget_cents)
        except GuardError as exc:
            results.append({
                "task_type": task_type, "endpoint_family": endpoint_family,
                "asin": asin, "source": "budget_rejected",
                "live_calls_made": 0, "idempotency_key": key, "error": str(exc),
            })
            continue

        # Attempt submission. The call counts as live once the transport is
        # invoked with valid arming; an ambiguous timeout DID reach the
        # provider (count=1) while a refused transport made no network call
        # (count=0).
        try:
            post_url = merchant_task_post_url(endpoint_family)
            payload = _task_post_payload(task_type, asin, marketplace)
            verdict = transport.submit(post_url, payload)
            live_calls += 1
        except AmbiguousTransportError:
            live_calls += 1
            _update_ledger(ledger, key, {"request_state": "needs_manual_reconciliation"})
            results.append({
                "task_type": task_type, "endpoint_family": endpoint_family,
                "asin": asin, "source": "needs_manual_reconciliation",
                "live_calls_made": 1, "idempotency_key": key,
                "error": "provider POST outcome unknown; manual reconciliation required",
            })
            continue
        except GuardError as exc:
            results.append({
                "task_type": task_type, "endpoint_family": endpoint_family,
                "asin": asin, "source": "transport_refused",
                "live_calls_made": 0, "idempotency_key": key, "error": str(exc),
            })
            continue

        accepted = evaluate_dataforseo_task_post(verdict, endpoint_family)
        if not accepted["accepted"]:
            rec_state = accepted["request_state"]
            _update_ledger(ledger, key, {
                "request_state": rec_state,
                "provider_task_id": None,
                "actual_cost_cents": _usd_to_cents(accepted.get("provider_cost_cents")),
                "failure_reason": accepted.get("reason"),
            })
            results.append({
                "task_type": task_type, "endpoint_family": endpoint_family,
                "asin": asin, "source": "provider_rejected",
                "classification": accepted["classification"],
                "provider_cost_cents": accepted.get("provider_cost_cents"),
                "reason": accepted.get("reason"),
                "live_calls_made": 1, "idempotency_key": key,
            })
            continue

        task_id = accepted["task_id"]
        actual_cost_cents = _usd_to_cents(accepted.get("provider_cost_cents"))
        _update_ledger(ledger, key, {
            "request_state": "submitted",
            "provider_task_id": task_id,
            "actual_cost_cents": actual_cost_cents,
        })
        results.append({
            "task_type": task_type, "endpoint_family": endpoint_family,
            "asin": asin, "source": "live",
            "provider_task_id": task_id,
            "provider_cost_cents": accepted.get("provider_cost_cents"),
            "actual_cost_cents": actual_cost_cents,
            "live_calls_made": 1, "idempotency_key": key,
        })

    return {
        "LIVE_CALLS_MADE": live_calls,
        "results": results,
        "feature_flag_enabled": feature_enabled(),
        "explicit_live_approval_required": True,
    }


def retrieve_validation(
    run_id: str,
    asin: str,
    task_type: str,
    task_id: str,
    marketplace: str = "amazon.com",
    bd_snapshot_ref: Optional[str] = None,
    transport: Optional[DataForSEOStandardTransport] = None,
) -> Dict[str, Any]:
    """Poll a queued Merchant task to completion via transport.retrieve and
    normalize + cache the result. Fail-closed; ambiguous outcomes require
    manual reconciliation (never auto-retried)."""
    endpoint_family = _endpoint_family_for(task_type)
    transport = transport or DataForSEOStandardTransport(allow_live=True)
    get_url = merchant_task_get_url(endpoint_family, task_id)
    try:
        body = transport.retrieve(get_url)
    except AmbiguousTransportError:
        return {"LIVE_CALLS_MADE": 1, "status": "needs_manual_reconciliation",
                "error": "retrieve outcome unknown; manual reconciliation required"}
    except GuardError as exc:
        return {"LIVE_CALLS_MADE": 0, "status": "refused", "error": str(exc)}

    verdict = evaluate_dataforseo_task_get(body, endpoint_family, task_id)
    if not verdict["accepted"]:
        if verdict.get("pending"):
            return {"LIVE_CALLS_MADE": 1, "status": "in_progress",
                    "pending": True, "reason": verdict.get("reason")}
        if verdict.get("classification") == "provider_error":
            return {"LIVE_CALLS_MADE": 1, "status": "provider_error",
                    "reason": verdict.get("reason")}
        return {"LIVE_CALLS_MADE": 1, "status": "provider_rejected",
                "classification": verdict.get("classification"),
                "reason": verdict.get("reason")}

    item = verdict["result_item"]
    norm = normalize_provider_record(item, asin, marketplace, task_type)
    cache_put(asin, marketplace, task_type, norm)
    return {
        "LIVE_CALLS_MADE": 1,
        "status": "retrieved",
        "normalized": norm,
        "idempotency_key": idempotency_key(run_id, asin, marketplace, task_type, bd_snapshot_ref),
    }


def _estimate_cost_cents(task_type: str) -> int:
    if task_type in LABS_TASK_TYPES:
        return 5
    return 5


def _task_post_payload(task_type: str, asin: str, marketplace: str) -> List[Dict[str, Any]]:
    loc = 2840
    lang = "en_US"
    if task_type == "product":
        return [{"keyword": "kirkland", "location_code": loc, "language_code": lang}]
    return [{"asin": asin, "location_code": loc, "language_code": lang}]


def _usd_to_cents(usd: Any) -> int:
    try:
        return int(round(float(usd) * 100))
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Local dotenv loader (non-destructive; used by route/test seeding).
# ---------------------------------------------------------------------------
def load_local_env() -> bool:
    """Load a local .env (path from NORTHSTAR_ENV_PATH) WITHOUT overriding
    vars already present in os.environ. Fail-closed (never raises)."""
    path = os.getenv("NORTHSTAR_ENV_PATH")
    if not path or not os.path.isfile(path):
        return False
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip()
                if k and k not in os.environ:
                    os.environ[k] = v
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Provider-shape functions preserved from the original adapter.
# ---------------------------------------------------------------------------
def _empty_result(asin: Optional[str]) -> Dict[str, Any]:
    return {
        "source": "dataforseo",
        "asin": asin,
        "provider_asin": None,
        "request_id": None,
        "title": None,
        "offer_count": None,
        "offers_returned_count": 0,
        "buy_box_price": None,
        "buy_box_price_raw": None,
        "buy_box_seller": None,
        "buy_box_seller_id": None,
        "buy_box_is_fba": None,
        "buy_box_is_fbm": None,
        "buy_box_is_prime": None,
        "buy_box_condition": None,
        "observed_fba_offer_count": 0,
        "observed_fbm_offer_count": 0,
        "observed_amazon_offer_count": 0,
        "offers": [],
        "request_zip_code": None,
        "observed_at": None,
        "credits_used": None,
        "credits_remaining": None,
        "cost_usd": None,
        "categories": None,
        "data_gaps": [],
        "provider_endpoint": None,
    }


def _auth() -> Optional[Tuple[str, str]]:
    if not (DATAFORSEO_LOGIN and DATAFORSEO_PASSWORD):
        return None
    return (DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD)


def _extract_items(result_item: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(result_item, dict):
        return []
    items = result_item.get("items")
    if isinstance(items, list):
        return items
    return []


def _parse_bsr_from_product_info(item: Dict[str, Any], gaps: List[str]) -> Dict[str, Any]:
    raw = None
    for section in item.get("product_information") or []:
        if not isinstance(section, dict):
            continue
        body = section.get("body")
        if isinstance(body, dict) and body.get("Best Sellers Rank"):
            raw = body.get("Best Sellers Rank")
            break
    if raw is None:
        gaps.append("BSR not present in DataForSEO product_information")
        if normalize_bsr is None:
            return {"bsr_raw": None, "bsr_primary_rank": None,
                    "bsr_primary_category": None, "bsr_capture_status": "unavailable",
                    "bsr_source": "dataforseo", "bsr_captured_at": None}
        return normalize_bsr(None, source="dataforseo")
    if normalize_bsr is not None:
        return normalize_bsr(raw, source="dataforseo")
    return {"bsr_raw": raw, "bsr_primary_rank": None, "bsr_primary_category": None,
            "bsr_capture_status": "unavailable", "bsr_source": "dataforseo",
            "bsr_captured_at": None}


def _seller_fulfillment(seller_url: Optional[str]):
    if not isinstance(seller_url, str) or "isAmazonFulfilled=" not in seller_url:
        return (None, None)
    try:
        qs = parse_qs(urlparse(seller_url).query)
        flag = qs.get("isAmazonFulfilled", [None])[0]
    except Exception:
        return (None, None)
    if flag == "1":
        return (True, False)
    if flag == "0":
        return (False, True)
    return (None, None)


def _seller_id_from_url(seller_url: Optional[str]) -> Optional[str]:
    if not isinstance(seller_url, str) or "seller=" not in seller_url:
        return None
    try:
        qs = parse_qs(urlparse(seller_url).query)
        return qs.get("seller", [None])[0]
    except Exception:
        return None


def _normalize_asin(asin: str, item: Dict[str, Any], gaps: List[str]) -> Dict[str, Any]:
    result = _empty_result(asin)
    result["title"] = item.get("title") or item.get("name") or None
    result["provider_asin"] = item.get("data_asin") or item.get("asin") or asin
    result["categories"] = [c.get("category") for c in (item.get("categories") or [])
                            if isinstance(c, dict) and c.get("category")]
    price = item.get("price_from")
    if isinstance(price, (int, float)) and not isinstance(price, bool):
        result["buy_box_price"] = float(price)
        result["buy_box_price_raw"] = float(price)
    else:
        gaps.append("DataForSEO asin task missing current price (price_from)")
    rating = item.get("rating")
    if isinstance(rating, dict):
        result["rating_value"] = rating.get("value")
        result["rating_votes"] = rating.get("votes_count")
    result["bsr"] = _parse_bsr_from_product_info(item, gaps)
    return result


def _normalize_sellers(result: Dict[str, Any], items: List[Dict[str, Any]],
                       gaps: List[str]) -> None:
    offers = []
    fba = fbm = amazon = 0
    buy_box_seller = None
    for s in items:
        if not isinstance(s, dict):
            continue
        price = s.get("price")
        if isinstance(price, dict):
            price_val = price.get("current")
        else:
            price_val = price if isinstance(price, (int, float)) and not isinstance(price, bool) else None
        seller_url = s.get("seller_url")
        if s.get("seller_name") is None and seller_url is None and price is None:
            continue
        is_fba, is_fbm = _seller_fulfillment(seller_url)
        seller_name = s.get("seller_name")
        if seller_name == "Amazon":
            is_fba, is_fbm = True, False
        if is_fba:
            fba += 1
        elif is_fbm:
            fbm += 1
        if seller_name == "Amazon":
            amazon += 1
        if s.get("buybox_winner") is True and buy_box_seller is None:
            buy_box_seller = seller_name
        offers.append({
            "position": s.get("rank_group") or s.get("position"),
            "buybox_winner": bool(s.get("buybox_winner")),
            "price": float(price_val) if isinstance(price_val, (int, float)) else None,
            "condition": s.get("condition"),
            "seller_id": _seller_id_from_url(seller_url),
            "seller_name": seller_name,
            "is_prime": None,
            "is_fba": is_fba,
            "is_fbm": is_fbm,
            "fulfillment": "FBA" if is_fba else ("FBM" if is_fbm else "Unknown"),
            "ships_from": s.get("ships_from"),
        })
    result["offers"] = offers
    result["offers_returned_count"] = len(offers)
    result["offer_count"] = len(offers) or None
    result["observed_fba_offer_count"] = fba
    result["observed_fbm_offer_count"] = fbm
    result["observed_amazon_offer_count"] = amazon
    if buy_box_seller is not None:
        result["buy_box_seller"] = buy_box_seller
    else:
        gaps.append("DataForSEO sellers task does not flag a Buy Box winner")


def get_dataforseo_offers(asin: str) -> Dict[str, Any]:
    """Merchant asin + sellers tasks -> shared normalized offer shape."""
    gaps: List[str] = []
    result = _empty_result(asin)
    result["provider_endpoint"] = "/v3/merchant/amazon/asin|sellers/task_post"
    if not DATAFORSEO_ENABLED:
        gaps.append("DataForSEO adapter not enabled (DATAFORSEO_ENABLED not true)")
        result["data_gaps"] = gaps
        return result
    if not DATAFORSEO_TRANSPORT_ENABLED or not _auth():
        gaps.append("DataForSEO transport not armed (DATAFORSEO_TRANSPORT_ENABLED/"
                    "credentials missing); no network call made")
        result["data_gaps"] = gaps
        return result
    if not asin or not ASIN_PATTERN.fullmatch(asin):
        gaps.append("Invalid ASIN. Expected exactly 10 alphanumeric characters.")
        result["data_gaps"] = gaps
        return result

    cost_usd = 0.0
    try:
        asin_post = _post_task("asin", [{"asin": asin, "location_code": 2840,
                                         "language_code": "en_US"}])
        cost_usd += float(asin_post.get("provider_cost_cents") or 0.0)
        if not asin_post.get("accepted"):
            gaps.append("DataForSEO asin task rejected: %s" % asin_post.get("reason"))
            result["data_gaps"] = gaps
            result["credits_used"] = None
            result["cost_usd"] = cost_usd
            return result
        asin_get = _get_task("asin", asin_post["task_id"])
        asin_items = _extract_items(asin_get.get("result_item"))
        result = _normalize_asin(asin, asin_items[0] if asin_items else {}, gaps)

        sellers_post = _post_task("sellers", [{"asin": asin, "location_code": 2840,
                                               "language_code": "en_US"}])
        cost_usd += float(sellers_post.get("provider_cost_cents") or 0.0)
        if sellers_post.get("accepted"):
            sellers_get = _get_task("sellers", sellers_post["task_id"])
            sellers_items = _extract_items(sellers_get.get("result_item"))
            _normalize_sellers(result, sellers_items, gaps)
        else:
            gaps.append("DataForSEO sellers task rejected: %s" % sellers_post.get("reason"))
    except GuardError as exc:
        gaps.append("DataForSEO guard error: %s" % exc)

    result["credits_used"] = None
    result["cost_usd"] = cost_usd
    result["data_gaps"] = gaps
    return result


def _post_task(family: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = merchant_task_post_url(family)
    try:
        resp = requests.post(
            url, json=payload, auth=_auth(), timeout=REQUEST_TIMEOUT_SECONDS
        )
    except requests.exceptions.RequestException as exc:
        raise GuardError("dataforseo transport error: %s" % exc)
    try:
        body = resp.json()
    except (json.JSONDecodeError, ValueError):
        raise GuardError("dataforseo response was not valid JSON")
    return evaluate_dataforseo_task_post(body, family)


def _get_task(family: str, task_id: str) -> Dict[str, Any]:
    url = merchant_task_get_url(family, task_id)
    deadline = time.monotonic() + MAX_POLL_SECONDS
    last = None
    while time.monotonic() < deadline:
        try:
            resp = requests.get(url, auth=_auth(), timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.exceptions.RequestException as exc:
            raise GuardError("dataforseo transport error: %s" % exc)
        try:
            body = resp.json()
        except (json.JSONDecodeError, ValueError):
            raise GuardError("dataforseo response was not valid JSON")
        verdict = evaluate_dataforseo_task_get(body, family, task_id)
        last = verdict
        if verdict.get("accepted"):
            return verdict
        if not verdict.get("pending"):
            return verdict
        time.sleep(POLL_INTERVAL_SECONDS)
    return last or {"accepted": False, "classification": "provider_rejected_unknown",
                    "reason": "poll timeout"}


# ---------------------------------------------------------------------------
# Route-facing validation entry (used by main.py /api/dataforseo/validate)
# ---------------------------------------------------------------------------
def execute_validation_route(body: Dict[str, Any], operator_token: str = "") -> Dict[str, Any]:
    """Guarded single-ASIN DataForSEO Standard-queue cross-check (route entry)."""
    cfg = load_config()
    if not cfg.get("enabled"):
        raise GuardError("DataForSEO adapter not available (DATAFORSEO_ENABLED not set)")
    if not cfg.get("transport_armed"):
        raise GuardError("DataForSEO transport not armed; no network call made")
    asin = (body or {}).get("asin")
    if not asin or not ASIN_PATTERN.fullmatch(asin):
        raise GuardError("invalid asin")
    return get_dataforseo_offers(asin)

