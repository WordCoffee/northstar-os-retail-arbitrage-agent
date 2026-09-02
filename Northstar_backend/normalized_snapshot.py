"""Offline provider-neutral normalized live market snapshot (Phase 4).

Turns a raw provider response (any supported provider: Easyparser/Amazon OFFER,
Bright Data, Chocodata, Unwrangle, DataForSEO) into a normalized,
intel_schema-shaped per-ASIN market snapshot. PURE OFFLINE - imports no
provider clients, performs no network I/O. Reuses proof_batch_contracts for the
provider-rejection taxonomy.

Fail-closed: any of the following REFUSES normalization (raises
NormalizationError with an explicit status; never a fabricated snapshot):
  - wrong/missing ASIN vs the frozen manifest record;
  - title/brand/pack identity conflict with the benchmark;
  - provider rejection state (HTTP 200 is NOT acceptance);
  - missing required raw fields (ASIN + amazon_price);
  - schema parse failure;
  - secret-like strings detected in the raw payload (refuse, never exfiltrate).
"""

import copy
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asin_benchmark_store
import proof_batch_contracts as pbc
from intel_schema import SCHEMA_VERSION, ASIN_PATTERN, normalize_bsr, fixture_minimal

SUPPORTED_PROVIDERS = (
    "EASYPARSER", "BRIGHTDATA", "CHOCODATA", "UNWRANGLE", "DATAFORSEO",
)

_SECRET_PATTERNS = (
    re.compile(r"(?i)api[_-]?key\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)secret\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}"),
    re.compile(r"(?i)token\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{20,}"),
)


class NormalizationError(Exception):
    """Fail-closed refusal carrying a structured status + reason."""

    def __init__(self, status: str, reason: str, asin: Optional[str] = None):
        super().__init__(f"{status}: {reason}")
        self.status = status
        self.reason = reason
        self.asin = asin


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _detect_secret(raw: Any) -> Optional[str]:
    if not isinstance(raw, (str, dict, list)):
        return None
    text = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
    for pat in _SECRET_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(0)[:24]
    return None


def _dig(raw: Any, *keys: str, default: Any = None) -> Any:
    """Return the first present key at the top level (case-insensitive)."""
    if not isinstance(raw, dict):
        return default
    lowered = {k.lower(): k for k in raw.keys()}
    for key in keys:
        if key in raw and raw[key] is not None:
            return raw[key]
        lk = key.lower()
        if lk in lowered:
            found = raw[lowered[lk]]
            if found is not None:
                return found
    return default


def _extract_asin(raw: Any) -> Optional[str]:
    if not isinstance(raw, dict):
        return None
    val = _dig(raw, "asin", "ASIN", "product_asin", "item_asin")
    if val:
        return str(val).strip().upper()
    result = _dig(raw, "result")
    if isinstance(result, list) and result and isinstance(result[0], dict):
        nested = _dig(result[0], "asin", "ASIN")
        if nested:
            return str(nested).strip().upper()
    return None


def _extract_title(raw: Any) -> Optional[str]:
    return _dig(raw, "title", "name", "product_title", "product_name")


def _extract_price(raw: Any) -> Optional[float]:
    val = _dig(raw, "price", "amazon_price", "buybox_price", "buy_box_price")
    if val is None:
        bb = _dig(raw, "buy_box")
        if isinstance(bb, dict):
            val = bb.get("price")
    if val is None:
        return None
    try:
        return float(str(val).replace("$", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _extract_reviews(raw: Any) -> Optional[int]:
    val = _dig(raw, "reviews", "review_count", "reviews_count", "ratings_total")
    if val is None:
        return None
    try:
        return int(str(val).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _extract_prime_fba(raw: Any) -> Optional[str]:
    val = _dig(raw, "prime_fba", "fulfillment")
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("fba", "amazon"):
            return "yes"
        if v == "fbm":
            return "no"
        return v
    bb = _dig(raw, "buy_box")
    if isinstance(bb, dict) and isinstance(bb.get("fulfillment"), str):
        f = bb["fulfillment"].lower()
        return "yes" if f in ("fba", "amazon") else ("no" if f == "fbm" else None)
    return None


def _extract_bsr_raw(raw: Any) -> Optional[str]:
    return _dig(raw, "bsr", "best_sellers_rank", "best_seller_rank")


def _extract_offers(raw: Any) -> List[Dict[str, Any]]:
    offers = _dig(raw, "offers", "offer_list", "sellers")
    if isinstance(offers, list):
        return [o for o in offers if isinstance(o, dict)]
    return []


def _extract_buy_box(raw: Any) -> Dict[str, Any]:
    bb = _dig(raw, "buy_box")
    if isinstance(bb, dict):
        return bb
    return {}


def _provider_rejected(raw: Any, provider: str) -> Optional[str]:
    """Return a rejection status from proof_batch_contracts, else None."""
    if not isinstance(raw, dict):
        return "provider_rejected_unknown"
    if provider == "DATAFORSEO":
        if raw.get("tasks_error") not in (None, 0):
            tasks = raw.get("tasks")
            if isinstance(tasks, list) and tasks and isinstance(tasks[0], dict):
                return pbc.classify_dataforseo_rejection(
                    tasks[0].get("status_code"), tasks[0].get("status_message"))
            return "provider_rejected_unknown"
        if raw.get("status_code") not in (None, 20000):
            return pbc.classify_dataforseo_rejection(
                raw.get("status_code"), raw.get("status_message"))
    status = raw.get("status")
    if isinstance(status, str) and status.lower() in ("error", "rejected", "fail"):
        return "provider_rejected_unknown"
    if raw.get("error") or raw.get("errors"):
        return "provider_rejected_unknown"
    return None


def _pack_match(bench_title: Any, live_title: Any) -> str:
    bt = asin_benchmark_store.pack_tokens(bench_title)
    lt = asin_benchmark_store.pack_tokens(live_title)
    if not bt and not lt:
        return "unavailable"
    if bt == lt and bt:
        return "match"
    if bt and lt and (bt & lt):
        return "conflict" if not (bt <= lt or lt <= bt) else "match"
    if bt and lt:
        return "conflict"
    return "unavailable"


def normalize_live_snapshot(
    raw: Any,
    manifest_record: Dict[str, Any],
    provider: str = "EASYPARSER",
) -> Dict[str, Any]:
    """Normalize a raw provider response into an intel_schema-shaped snapshot.

    manifest_record: a record from benchmark_25asin_manifest (carries the
    frozen benchmark identity + asin). Raises NormalizationError on any
    fail-closed condition. Never fabricates missing values.
    """
    provider = (provider or "EASYPARSER").upper()
    if provider not in SUPPORTED_PROVIDERS:
        raise NormalizationError("provider_not_supported",
                                 f"unsupported provider: {provider}")

    if raw is None or not isinstance(raw, dict):
        raise NormalizationError("provider_rejected_unknown",
                                 "raw payload is not a dict")

    secret = _detect_secret(raw)
    if secret:
        raise NormalizationError("secret_detected",
                                 f"refusing: secret-like string in raw payload ({secret}...)")

    rejection = _provider_rejected(raw, provider)
    if rejection:
        raise NormalizationError(rejection,
                                 f"provider rejection state: {rejection}")

    asin = _extract_asin(raw)
    if not asin or not ASIN_PATTERN.fullmatch(asin):
        raise NormalizationError("missing_asin",
                                 "no valid ASIN in raw payload")
    bench_asin = (manifest_record or {}).get("asin")
    if bench_asin and asin != str(bench_asin).upper():
        raise NormalizationError("identity_conflict",
                                 f"returned ASIN {asin} != manifest ASIN {bench_asin}",
                                 asin=asin)

    price = _extract_price(raw)
    if price is None:
        raise NormalizationError("missing_market_price",
                                 "no amazon_price in raw payload", asin=asin)

    title = _extract_title(raw)
    bench_title = (manifest_record or {}).get("benchmark_title")
    pack_status = "unavailable"
    if title is not None and bench_title is not None:
        pack_status = _pack_match(bench_title, title)
        norm_live = asin_benchmark_store.normalize_title(title)
        norm_bench = asin_benchmark_store.normalize_title(bench_title)
        identity_conflict = (
            norm_bench is not None
            and norm_live is not None
            and norm_bench != norm_live
            and pack_status == "conflict"
        )
        if identity_conflict:
            raise NormalizationError(
                "identity_conflict",
                f"title/brand/pack conflict vs benchmark for {asin}", asin=asin)

    bsr_raw = _extract_bsr_raw(raw)
    bsr_fact = normalize_bsr(bsr_raw, source=provider)
    if bsr_raw is not None and bsr_fact["bsr_capture_status"] == "parse_error":
        raise NormalizationError("parse_error",
                                 f"BSR present but unparseable for {asin}", asin=asin)

    snap = fixture_minimal()
    snap["schema_version"] = SCHEMA_VERSION
    snap["asin"] = asin
    snap["ingested_at"] = _now_iso()
    snap["sources"] = {provider: raw}
    facts = snap["facts"]
    facts["identity"]["name"] = title
    facts["identity"]["pack_match"] = pack_status
    facts["market"]["amazon_price"] = price
    facts["market"]["bsr"] = bsr_fact
    facts["demand"]["bsr"] = bsr_fact.get("bsr_primary_rank")
    facts["demand"]["bsr_category"] = bsr_fact.get("bsr_primary_category")

    prime = _extract_prime_fba(raw)
    facts["market"]["prime_fba"] = prime

    offers = _extract_offers(raw)
    facts["market"]["offers"] = offers
    fba = sum(1 for o in offers if str(o.get("fulfillment", "")).upper() == "FBA")
    fbm = sum(1 for o in offers if str(o.get("fulfillment", "")).upper() == "FBM")
    total = len(offers)
    facts["market"]["seller_counts"] = {
        "total_observed": total or None,
        "fba_observed": fba or None,
        "fbm_observed": fbm or None,
        "amazon_observed": None,
        "claimed_total": None,
    }
    facts["market"]["coverage"] = {
        "offer_list_available": bool(offers),
        "offers_complete_status": "full" if offers else "unknown",
        "coverage_reason": None if offers else "no offer roster in payload",
    }
    bb = _extract_buy_box(raw)
    if isinstance(bb, dict) and bb.get("price") is not None:
        facts["market"]["buy_box"] = {
            "available": True,
            "price": bb.get("price"),
            "seller_name": bb.get("seller_name") or bb.get("seller"),
            "seller_id": bb.get("seller_id"),
            "fulfillment": bb.get("fulfillment"),
            "source": provider,
            "observed_at": _now_iso(),
        }
    facts["provenance"] = {
        "market.amazon_price": {"source": provider, "fetched_at": _now_iso()},
        "market.bsr": {"source": provider, "fetched_at": _now_iso()},
    }
    return snap


def try_normalize(
    raw: Any,
    manifest_record: Dict[str, Any],
    provider: str = "EASYPARSER",
) -> Dict[str, Any]:
    """Non-raising variant: returns {accepted, snapshot|status, reason, asin}."""
    try:
        snap = normalize_live_snapshot(raw, manifest_record, provider)
        return {"accepted": True, "snapshot": snap, "asin": snap.get("asin")}
    except NormalizationError as exc:
        return {
            "accepted": False,
            "status": exc.status,
            "reason": exc.reason,
            "asin": exc.asin,
        }
