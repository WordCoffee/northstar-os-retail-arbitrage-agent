"""Per-ASIN Easyparser market snapshot store for the Product Scout.

A separate, dedicated keyspace that NEVER mixes with the candidate cache
(``data/scanner-search-cache.json``) or the enrichment caches
(``data/enriched-offer-cache.json`` / ``data/seller-offer-cache.json``).

Store file (``data/amazon-market-snapshots.json`` by default, env
SCANNER_MARKET_SNAPSHOT_PATH project-root relative):

    {
      "schema_version": 1,
      "generated_at": <ISO>,
      "asins": {
        "<ASIN>": {
          "asin", "title", "source": "easyparser",
          "data_status": "available|partial|unavailable|failed",
          "observed_at", "fetched_at",
          "buy_box": {available, seller_name, seller_id, fulfillment,
                      price, shipping, landed_price, condition, prime, note},
          "offers": [ normalized Easyparser offer ],
          "offers_returned", "offers_complete",
          "seller_counts": {observed_total, claimed_total,
                            fba_observed, fbm_observed, amazon_observed,
                            counts_from_observed: true},
          "credits_used", "credits_remaining",   (only when Easyparser returns them)
          "missing_fields", "data_gaps",
          "stages": {detail, offers, sales},     (done|partial|failed|not_requested)
          "attempts", "last_error", "retry_eligible",
          "freshness": {offers_fresh_until, sales_fresh_until, identity_fresh_until}
        }
      }
    }

Run report (``data/enrichment-run-report.json`` by default, env
SCANNER_ENRICH_RUN_REPORT_PATH): one per run (dry-run / preflight / batch),
recording planned/attempted/succeeded/partial/failed/skipped counts,
credit usage when returned, caps in effect, and the stop reason.

Honesty rules:
- Only fields actually present in the provider response are stored; a
  field the provider did not return stays absent or null — never
  fabricated, never zero-filled.
- Observed seller counts (computed only from returned offers) are
  distinct from the claimed ``offer_count``. When
  offers_returned_count < offer_count the roster is partial and
  ``offers_complete`` is False.
- No credentials, API keys, or secret-bearing payloads are ever stored.
- Writes are per-ASIN atomic (temp file + os.replace) with post-write
  verification by re-read; a failed write leaves the prior store intact.
- A corrupt store is never overwritten or silently rebuilt: saves refuse
  until it is repaired or the file is moved away.
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

SCHEMA_VERSION = 1

OFFERS_FRESH_DAYS = 7
SALES_FRESH_DAYS = 30
IDENTITY_FRESH_DAYS = 90

MAX_ATTEMPTS = 3

ASIN_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

# Provider errors that make a retry pointless (bounded retry policy).
_PERMANENT_GAP_HINTS = (
    "Easyparser API key is not configured.",
    "Invalid ASIN.",
)

_ERROR_GAP_HINTS = (
    "timed out",
    "network level",
    "HTTP ",
    "not valid JSON",
    "unexpected structure",
    "success is false",
    "missing result data",
    "missing result.product",
    "missing result.offer.offer_results",
    "API key is not configured",
    "Invalid ASIN",
)

# Fields the pipeline needs but Easyparser OFFER does not supply today.
# A field moves out of missing_fields only when a parser actually reads it
# from a live response — never by assumption.
REQUIRED_FIELD_CATALOG = (
    "upc",
    "ean",
    "gtin",
    "item_weight_lbs",
    "package_weight_lbs",
    "package_dimensions_in",
    "brand",
    "browse_node_id",
    "amazon_category",
    "fba_fee",
    "monthly_sales_estimate",
    "sales_rank",
)

DATA_STATUS_AVAILABLE = "available"
DATA_STATUS_PARTIAL = "partial"
DATA_STATUS_UNAVAILABLE = "unavailable"
DATA_STATUS_FAILED = "failed"

_STAGE_DONE = "done"
_STAGE_PARTIAL = "partial"
_STAGE_FAILED = "failed"
_STAGE_UNAVAILABLE = "unavailable"
_STAGE_NOT_REQUESTED = "not_requested"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _store_path() -> str:
    raw = os.getenv("SCANNER_MARKET_SNAPSHOT_PATH")
    if raw:
        return raw if os.path.isabs(raw) else os.path.join(_BACKEND_DIR, raw)
    return os.path.join(_BACKEND_DIR, "data", "amazon-market-snapshots.json")


def _report_path() -> str:
    raw = os.getenv("SCANNER_ENRICH_RUN_REPORT_PATH")
    if raw:
        return raw if os.path.isabs(raw) else os.path.join(_BACKEND_DIR, raw)
    return os.path.join(_BACKEND_DIR, "data", "enrichment-run-report.json")


def _empty_store() -> Dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "generated_at": None, "asins": {}}


def _read_store() -> Optional[Dict[str, Any]]:
    """Raw store payload with distinct honest states. Zero network.

    None = missing, False = corrupt/unparseable, dict = valid.
    """
    path = _store_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(data, dict) or not isinstance(data.get("asins"), dict):
        return False
    return data


def load_snapshots() -> Dict[str, Any]:
    """All snapshots keyed by ASIN; {} when missing/corrupt. Zero network."""
    data = _read_store()
    if data is None or data is False:
        return {}
    return {k: v for k, v in data.get("asins", {}).items() if isinstance(v, dict)}


def get_snapshot(asin: Optional[str]) -> Optional[Dict[str, Any]]:
    if not asin or not ASIN_PATTERN.fullmatch(str(asin)):
        return None
    return load_snapshots().get(asin)


def _atomic_write_json(path: str, payload: Dict[str, Any]) -> bool:
    tmp_path = f"{path}.tmp"
    try:
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=str)
        os.replace(tmp_path, path)
        return True
    except OSError:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        return False


def save_snapshot(asin: Optional[str], snapshot: Optional[Dict[str, Any]]) -> tuple:
    """Persist one ASIN snapshot atomically; verify by re-read.

    Returns (ok, error). A corrupt existing store is never overwritten:
    saving refuses so the (possibly recoverable) prior file is preserved.
    The store file is created on first successful save.
    """
    if not asin or not ASIN_PATTERN.fullmatch(str(asin)):
        return False, "invalid ASIN"
    if not isinstance(snapshot, dict) or not snapshot:
        return False, "empty snapshot"
    snapshot = json.loads(json.dumps(snapshot, default=str))

    existing = _read_store()
    if existing is False:
        return False, "store corrupt; refusing to overwrite until repaired"

    store = existing if isinstance(existing, dict) else _empty_store()
    store["generated_at"] = _now_iso()
    store.setdefault("asins", {})
    store["asins"][asin] = snapshot

    if not _atomic_write_json(_store_path(), store):
        return False, "store write failed (prior file preserved)"

    verified = _read_store()
    if verified is False or verified is None:
        return False, "store unreadable after write (prior file preserved)"
    entry = verified.get("asins", {}).get(asin)
    if entry != snapshot:
        return False, "store write verification failed (prior file preserved)"
    return True, None


def read_run_report() -> Optional[Dict[str, Any]]:
    path = _report_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


def write_run_report(report: Optional[Dict[str, Any]]) -> tuple:
    """Persist a run report atomically; verify by re-read."""
    if not isinstance(report, dict):
        return False, "empty report"
    report = json.loads(json.dumps(report, default=str))
    report["schema_version"] = SCHEMA_VERSION
    if not _atomic_write_json(_report_path(), report):
        return False, "run report write failed (prior file preserved)"
    verified = read_run_report()
    if verified is None:
        return False, "run report unreadable after write (prior file preserved)"
    if verified.get("generated_at") != report.get("generated_at"):
        return False, "run report write verification failed (prior file preserved)"
    return True, None


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _fulfillment_label(is_fba, is_fbm, seller_name) -> str:
    if isinstance(seller_name, str) and seller_name.strip().lower() == "amazon.com":
        return "Amazon"
    if is_fba is True:
        return "FBA"
    if is_fbm is True:
        return "FBM"
    return "Unknown"


def is_error_gap(gap: str) -> bool:
    return any(hint in gap for hint in _ERROR_GAP_HINTS)


def permanent_gap(data_gaps) -> bool:
    for gap in data_gaps or []:
        if isinstance(gap, str) and any(hint in gap for hint in _PERMANENT_GAP_HINTS):
            return True
    return False


def _classify(result: Dict[str, Any]) -> tuple:
    """(data_status, offers_complete) from a normalized Easyparser result.

    A provider result that explicitly reports a complete zero-offer set
    (offer_count exactly 0 and offers_returned_count exactly 0, no
    error) is classified available+complete — that is the only case in
    which zero seller counts are real evidence. Every other empty
    result (claim absent, claim > 0, or error) stays unavailable/failed.
    """
    gaps = [g for g in (result.get("data_gaps") or []) if isinstance(g, str)]
    offers = [o for o in (result.get("offers") or []) if isinstance(o, dict)]
    error = any(is_error_gap(g) for g in gaps)
    if offers:
        claimed = result.get("offer_count")
        returned = result.get("offers_returned_count")
        complete = (
            isinstance(claimed, int)
            and isinstance(returned, int)
            and claimed > 0
            and returned >= claimed
        )
        return (DATA_STATUS_AVAILABLE if complete else DATA_STATUS_PARTIAL), complete
    claimed = result.get("offer_count")
    returned = result.get("offers_returned_count")
    if error:
        return DATA_STATUS_FAILED, False
    if (
        isinstance(claimed, int)
        and isinstance(returned, int)
        and claimed == 0
        and returned == 0
    ):
        return DATA_STATUS_AVAILABLE, True
    return DATA_STATUS_UNAVAILABLE, False


def build_snapshot(asin: str, result: Dict[str, Any], prior_attempts: int = 0) -> Dict[str, Any]:
    """Normalize one Easyparser OFFER response into a store snapshot.

    Stores only fields the response actually carries. Seller counts are
    observed (computed only from returned offers) and kept distinct from
    the claimed offer_count. Nothing is ever invented.
    """
    fetched_at = _now_iso()
    observed_at = result.get("observed_at")
    data_status, offers_complete = _classify(result)
    offers = [o for o in (result.get("offers") or []) if isinstance(o, dict)]
    gaps = [g for g in (result.get("data_gaps") or []) if isinstance(g, str)]

    attempts = prior_attempts + 1
    retry_eligible = (
        data_status in (DATA_STATUS_FAILED, DATA_STATUS_UNAVAILABLE)
        and attempts < MAX_ATTEMPTS
        and not permanent_gap(gaps)
    )

    buy_box_price = result.get("buy_box_price")
    buy_box_price = buy_box_price if _is_number(buy_box_price) else None
    buy_box_seller = result.get("buy_box_seller")
    buy_box = {
        "available": buy_box_price is not None or isinstance(buy_box_seller, str) and buy_box_seller.strip(),
        "seller_name": buy_box_seller,
        "seller_id": result.get("buy_box_seller_id"),
        "fulfillment": _fulfillment_label(
            result.get("buy_box_is_fba"), result.get("buy_box_is_fbm"), buy_box_seller
        ),
        "price": buy_box_price,
        "shipping": None,
        "landed_price": None,
        "condition": result.get("buy_box_condition"),
        "prime": result.get("buy_box_is_prime"),
        "note": None,
    }

    seller_counts = {
        "observed_total": result.get("offers_returned_count"),
        "claimed_total": result.get("offer_count"),
        "fba_observed": result.get("observed_fba_offer_count"),
        "fbm_observed": result.get("observed_fbm_offer_count"),
        "amazon_observed": result.get("observed_amazon_offer_count"),
        "counts_from_observed": True,
    }

    error = any(is_error_gap(g) for g in gaps)
    stages = {
        "detail": (
            _STAGE_DONE
            if result.get("title") or buy_box["available"]
            else (_STAGE_FAILED if error else _STAGE_UNAVAILABLE)
        ),
        "offers": (
            _STAGE_DONE
            if offers_complete
            else (_STAGE_PARTIAL if offers else (_STAGE_FAILED if error else _STAGE_UNAVAILABLE))
        ),
        "sales": _STAGE_NOT_REQUESTED,
    }

    fetched_dt = datetime.now(timezone.utc)
    snapshot = {
        "asin": asin,
        "title": result.get("title"),
        "source": "easyparser",
        "data_status": data_status,
        "observed_at": observed_at,
        "fetched_at": fetched_at,
        "buy_box": buy_box,
        "offers": offers,
        "offers_returned": result.get("offers_returned_count"),
        "offers_complete": offers_complete,
        "seller_counts": seller_counts,
        "credits_used": result.get("credits_used"),
        "credits_remaining": result.get("credits_remaining"),
        "missing_fields": [f for f in REQUIRED_FIELD_CATALOG if f not in result],
        "data_gaps": gaps,
        "stages": stages,
        "attempts": attempts,
        "last_error": None,
        "retry_eligible": retry_eligible,
        "freshness": {
            "offers_fresh_until": (fetched_dt + timedelta(days=OFFERS_FRESH_DAYS)).isoformat(),
            "sales_fresh_until": (fetched_dt + timedelta(days=SALES_FRESH_DAYS)).isoformat(),
            "identity_fresh_until": (fetched_dt + timedelta(days=IDENTITY_FRESH_DAYS)).isoformat(),
        },
    }
    error_gaps = [g for g in gaps if is_error_gap(g)]
    if error_gaps:
        snapshot["last_error"] = "; ".join(error_gaps)
    return snapshot


def snapshot_freshness_status(snapshot: Dict[str, Any], stage: str = "offers") -> str:
    """fresh | stale | unknown — from the per-stage freshness deadline."""
    key = {"offers": "offers_fresh_until", "sales": "sales_fresh_until", "identity": "identity_fresh_until"}.get(stage)
    raw = (snapshot.get("freshness") or {}).get(key) if isinstance(snapshot.get("freshness"), dict) else None
    if not isinstance(raw, str):
        return "unknown"
    try:
        due = datetime.fromisoformat(raw)
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
    except ValueError:
        return "unknown"
    return "stale" if datetime.now(timezone.utc) > due else "fresh"


def is_fresh_success(snapshot: Dict[str, Any]) -> bool:
    """True when the snapshot is a successful fetch and not yet stale."""
    if not isinstance(snapshot, dict):
        return False
    if snapshot.get("data_status") not in (DATA_STATUS_AVAILABLE, DATA_STATUS_PARTIAL):
        return False
    return snapshot_freshness_status(snapshot) == "fresh"


def is_retry_eligible(snapshot: Dict[str, Any]) -> bool:
    """Bounded retry policy: failed/unavailable, attempts not exhausted,
    and not a permanent error."""
    if not isinstance(snapshot, dict):
        return False
    if snapshot.get("data_status") not in (DATA_STATUS_FAILED, DATA_STATUS_UNAVAILABLE):
        return False
    if not isinstance(snapshot.get("attempts"), int) or snapshot["attempts"] >= MAX_ATTEMPTS:
        return False
    return not permanent_gap(snapshot.get("data_gaps"))
