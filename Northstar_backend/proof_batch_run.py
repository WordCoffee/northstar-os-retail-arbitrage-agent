"""Dedicated guarded runner for the fixed 20-ASIN provider-data validation run
(design: docs/proof-batch-guarded-execution-design.md).

OFFLINE-FIRST: this module imports NO provider client at module level. The
only adapter in this build is the synthetic FixtureAdapter. A real-data-
ready Easyparser adapter (proof_batch_easyparser_adapter.py) is wired into
`run` behind the full guard stack: after every runner guard passes, the
guarded path arms it (allow_live=True + injected client), but the adapter's
second external arm gate PROOF_BATCH_LIVE_ARMED=1 is absent by default, so the
`run` command refuses with a clear message at the adapter gate. Enabling a
real pull is a separate, human-approved runtime step (docs/proof-batch-adapter-arming-plan.md).

Isolation decisions (audit §1):
  - ASIN source is ONLY the named preflight JSON (fixed 20, fingerprint
    bound). No scanner cache, no candidate discovery, no arbitrary ASIN
    arguments, no fallback.
  - Outputs go ONLY to data/batch/live-validation-runs/<run_id>/. Protected
    artifacts (scanner caches, benchmark files, snapshot store, run report,
    costco files) are never read-modify-written by this module.
  - The market snapshot store's pure normalizer (build_snapshot) is reused
    for offer normalization; its protected store file is never touched.

Guard stack (all required, no fallback):
  1. explicit --live flag (CLI) / live=True (API)
  2. live_gate.live_enabled()  (SCANNER_LIVE_ALLOWED strict opt-in)
  3. valid fixed preflight binding (20 unique ASINs, Easyparser-only,
     market_offers sole requested field contract)
  4. explicit finite --max-requests (>= 1)
  5. explicit finite --max-credits (>= 1)
  6. caps consistent with the preflight plan (allowed = min(runtime,
     preflight plan, hard 20); preflight plan must itself be 20)
  7. protected-artifact integrity drift check: not enforced in this build
     (no persistent baseline store exists; task-level Phase 3 verification
     covers it). Documented as a future optional guard.

Commands:
  python proof_batch_run.py dry-run --preflight <p> --max-requests N --max-credits N
  python proof_batch_run.py fixture-run --preflight <p> --max-requests N --max-credits N --out-dir <dir>
  python proof_batch_run.py run --live --preflight <p> --max-requests N --max-credits N
  python proof_batch_run.py report --run-dir <dir>
dry-run and report are zero network. fixture-run uses the synthetic adapter
only and writes to an explicit out dir. `run` additionally requires the live
gate AND a live-enabled adapter; the easyparser-live adapter exists but is
NOT enabled in this build (allow_live=False) — it always refuses until a
separately human-approved build enables it. All live commands are
documentation only; nothing was executed.
"""

import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import intel_schema
import benchmark_validation as bv
import live_gate
import market_snapshot_store as snapshot_store
import proof_batch as pb
from proof_batch_contracts import (
    BindingError,
    GuardError,
    ProviderAdapter,
    RunAbort,
    ESTIMATED_CREDITS_PER_REQUEST,
)

ASIN_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")

HARD_PROOF_BATCH_LIMIT = 20

RUN_OUTPUT_ROOT = "data/batch/live-validation-runs"

EXPECTED_PURPOSE = "provider_data_contract_validation"
EXPECTED_PROVIDER = "EASYPARSER"
EXPECTED_REQUESTED_FIELDS = ("market_offers",)

# Mapping comparison states (design §6).
STATE_MATCH = "match"
STATE_EXPECTED_REVIEW = "expected_mapping_review"
STATE_UNEXPECTED_MISMATCH = "unexpected_mapping_mismatch"
STATE_UNAVAILABLE = "unavailable"
STATE_DRIFT = "possible_market_drift"
STATE_PARSE_ERROR = "parse_error"
STATE_PROVIDER_ERROR = "provider_error"

# Abort (failure-manifest) reasons.
STOP_GUARD_REFUSED = "guard_refused"
STOP_BINDING_INVALID = "binding_invalid"
STOP_MAX_REQUESTS = "budget_max_requests"
STOP_MAX_CREDITS = "budget_max_credits"
STOP_WRONG_ASIN = "wrong_asin"
STOP_MAPPING_MISMATCH = "mapping_incompatible"
STOP_PROVIDER_ERROR = "provider_error"
STOP_PARSE_ERROR = "parse_error"
STOP_SCHEMA = "schema_validation"
STOP_SECRET = "secret_like_output"
STOP_PERSISTENCE = "persistence_failure"
STOP_ADAPTER = "adapter_internal_error"

HARD_STOP_CONDITIONS = (
    (STOP_GUARD_REFUSED, "a required live guard (--live, SCANNER_LIVE_ALLOWED, caps, binding) is missing or inconsistent"),
    (STOP_BINDING_INVALID, "preflight binding invalid or fingerprint tampered"),
    (STOP_MAX_REQUESTS, "request budget exhausted before the next request"),
    (STOP_MAX_CREDITS, "credit budget exhausted before the next request"),
    (STOP_WRONG_ASIN, "provider returned a wrong/missing product ASIN (requested/returned relationship unprovable)"),
    (STOP_MAPPING_MISMATCH, "returned product/title/pack incompatible with the benchmark row"),
    (STOP_PROVIDER_ERROR, "provider reported a request failure"),
    (STOP_PARSE_ERROR, "provider response malformed/unparseable"),
    (STOP_SCHEMA, "normalized snapshot fails intel_schema validation"),
    (STOP_SECRET, "secret-like key detected in result, snapshot, or adapter meta"),
    (STOP_PERSISTENCE, "atomic persistence failure (never a partial finalized artifact)"),
    (STOP_ADAPTER, "adapter internal error or crash"),
)

PURCHASE_AUTHORIZATION_STATEMENT = "Passing provider-data validation does not authorize a purchase."


# ---------------------------------------------------------------------------
# Preflight binding
# ---------------------------------------------------------------------------

def load_preflight(path: str) -> Dict[str, Any]:
    """Read the named preflight JSON. Never accepts any other ASIN source."""
    if not os.path.isfile(path):
        raise BindingError(f"preflight file not found: {path}")
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except (json.JSONDecodeError, ValueError) as exc:
        raise BindingError(f"preflight file is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise BindingError("preflight payload must be a JSON object")
    if pb.contains_secret_like(payload):
        raise BindingError("preflight contains secret-like keys; rejected")
    return payload


def canonical_preflight_asins(preflight: Dict[str, Any]) -> List[str]:
    """Uppercased, deduped ASIN list in preflight order. Raises BindingError
    on duplicates, non-ASIN strings, or count != 20."""
    rows = (preflight.get("selection") or {}).get("asins")
    if not isinstance(rows, list):
        raise BindingError("preflight selection.asins missing or not a list")
    asins: List[str] = []
    seen = set()
    for row in rows:
        asin = (row.get("asin") if isinstance(row, dict) else None)
        if not isinstance(asin, str) or not ASIN_PATTERN.fullmatch(asin.strip()):
            raise BindingError("preflight contains an invalid ASIN entry")
        asin = asin.strip().upper()
        if asin in seen:
            raise BindingError(f"duplicate ASIN in preflight: {asin}")
        seen.add(asin)
        asins.append(asin)
    if len(asins) != HARD_PROOF_BATCH_LIMIT:
        raise BindingError(
            f"preflight ASIN count must be exactly {HARD_PROOF_BATCH_LIMIT}; got {len(asins)}"
        )
    return asins


def preflight_fingerprint(preflight: Dict[str, Any]) -> str:
    """Deterministic sha256 over a stable binding subset of the preflight
    (design §3). Runtime caps (max_credits) are NOT part of the fingerprint —
    they are entered per run by the human."""
    canonical = canonical_preflight_asins(preflight)
    plan = preflight.get("provider_plan") or {}
    providers = [
        {
            "provider": (p or {}).get("provider"),
            "status": (p or {}).get("status"),
            "fields_owned": (p or {}).get("fields_owned"),
            "requests_per_asin": (p or {}).get("requests_per_asin"),
            "credit_estimate_per_asin": (p or {}).get("credit_estimate_per_asin"),
        }
        for p in (plan.get("providers") if isinstance(plan.get("providers"), list) else [])
        if isinstance(p, dict)
    ]
    hard_caps = preflight.get("hard_caps") or {}
    subset = {
        "purpose": preflight.get("purpose"),
        "run_id": preflight.get("run_id"),
        "asins": sorted(canonical),
        "providers": providers,
        "requested_fields_per_asin": plan.get("requested_fields_per_asin"),
        "request_count_per_asin": plan.get("request_count_per_asin"),
        "request_count_total": plan.get("request_count_total"),
        "max_asins": hard_caps.get("max_asins"),
        "max_requests_plan": hard_caps.get("max_requests"),
    }
    canonical_bytes = json.dumps(subset, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(canonical_bytes).hexdigest()


def validate_preflight_binding(preflight: Dict[str, Any]) -> List[str]:
    """Binding errors (empty = valid). No fallback when any error exists."""
    errors: List[str] = []
    if preflight.get("kind") != "proof-batch-preflight":
        errors.append("kind is not proof-batch-preflight")
    if preflight.get("purpose") != EXPECTED_PURPOSE:
        errors.append(f"purpose must be {EXPECTED_PURPOSE}")
    if not isinstance(preflight.get("run_id"), str) or not preflight["run_id"]:
        errors.append("run_id missing")
    try:
        canonical_preflight_asins(preflight)
    except BindingError as exc:
        errors.append(str(exc))
    if preflight.get("human_confirmation") != pb.HUMAN_CONFIRMATION_LINE:
        errors.append("human_confirmation line missing or altered")
    plan = preflight.get("provider_plan")
    if not isinstance(plan, dict):
        errors.append("provider_plan missing")
        return errors
    providers = plan.get("providers")
    if not isinstance(providers, list):
        errors.append("provider_plan.providers missing")
        return errors
    easyparser = None
    for p in providers:
        if not isinstance(p, dict):
            continue
        name = (p.get("provider") or "").upper()
        status = p.get("status")
        if name == EXPECTED_PROVIDER:
            easyparser = p
            if status != "planned":
                errors.append("EASYPARSER must be status 'planned'")
            if p.get("requests_per_asin") != 1:
                errors.append("EASYPARSER requests_per_asin must be 1")
            if p.get("credit_estimate_per_asin") != 5:
                errors.append("EASYPARSER credit_estimate_per_asin must be the documented 5")
        elif status in ("planned", "approved", "enabled"):
            errors.append(f"unexpected planned provider: {name}")
    if easyparser is None:
        errors.append("EASYPARSER provider entry missing from the plan")
    fields = plan.get("requested_fields_per_asin")
    if fields != list(EXPECTED_REQUESTED_FIELDS):
        errors.append(f"requested_fields_per_asin must be {list(EXPECTED_REQUESTED_FIELDS)}")
    if plan.get("request_count_per_asin") != 1:
        errors.append("request_count_per_asin must be 1")
    if plan.get("request_count_total") != HARD_PROOF_BATCH_LIMIT:
        errors.append(f"request_count_total must be {HARD_PROOF_BATCH_LIMIT}")
    caps = preflight.get("hard_caps") or {}
    if caps.get("max_asins") != HARD_PROOF_BATCH_LIMIT:
        errors.append(f"hard_caps.max_asins must be {HARD_PROOF_BATCH_LIMIT}")
    if caps.get("max_requests") != HARD_PROOF_BATCH_LIMIT:
        errors.append(f"hard_caps.max_requests (plan) must be {HARD_PROOF_BATCH_LIMIT}")
    return errors


# ---------------------------------------------------------------------------
# Budget
# ---------------------------------------------------------------------------

class BudgetTracker:
    """Request/credit accounting. Stop-before semantics: can_request() is
    checked BEFORE each fetch. Retries (default 0) count toward both caps."""

    def __init__(self, max_requests: int, max_credits: int,
                 estimated_credits_per_request: float = ESTIMATED_CREDITS_PER_REQUEST):
        if not isinstance(max_requests, int) or max_requests < 1:
            raise GuardError("max_requests must be a finite integer >= 1")
        if not isinstance(max_credits, int) or max_credits < 1:
            raise GuardError("max_credits must be a finite integer >= 1")
        if max_requests > HARD_PROOF_BATCH_LIMIT:
            raise GuardError(f"max_requests exceeds the hard proof-batch limit of {HARD_PROOF_BATCH_LIMIT}")
        if (not isinstance(estimated_credits_per_request, (int, float))
                or isinstance(estimated_credits_per_request, bool)
                or estimated_credits_per_request <= 0):
            raise GuardError(
                "estimated_credits_per_request must be a positive finite number; "
                "an unknown/unbounded per-request cost cannot be budgeted (fail closed)"
            )
        self.allowed_requests = max_requests
        self.max_credits = max_credits
        self.est_per_request = estimated_credits_per_request
        self.requests_used = 0
        self.retries_used = 0
        self.credits_estimated_used = 0.0
        self.credits_reported_used = 0

    def can_request(self) -> bool:
        """Stop-before: false when either cap would be exceeded by the next request."""
        if self.requests_used >= self.allowed_requests:
            return False
        if self.credits_estimated_used + self.est_per_request > self.max_credits:
            return False
        return True

    def stop_reason(self) -> Optional[str]:
        if self.requests_used >= self.allowed_requests:
            return STOP_MAX_REQUESTS
        if self.credits_estimated_used + self.est_per_request > self.max_credits:
            return STOP_MAX_CREDITS
        return None

    def record_request(self, credits_reported: Optional[int]) -> None:
        self.requests_used += 1
        if isinstance(credits_reported, int) and not isinstance(credits_reported, bool) and credits_reported > 0:
            self.credits_reported_used += credits_reported
            self.credits_estimated_used += float(credits_reported)
        else:
            self.credits_estimated_used += self.est_per_request

    def snapshot_state(self) -> Dict[str, Any]:
        return {
            "allowed_requests": self.allowed_requests,
            "requests_used": self.requests_used,
            "retries_used": self.retries_used,
            "credits_estimated_used": round(self.credits_estimated_used, 2),
            "credits_reported_used": self.credits_reported_used,
            "credits_actual_status": (
                "reported_by_provider"
                if self.credits_reported_used > 0
                else "unavailable_estimated_only"
            ),
            "max_credits": self.max_credits,
        }


# ---------------------------------------------------------------------------
# Mapping classification
# ---------------------------------------------------------------------------

def classify_mapping(
    requested_asin: str,
    returned_asin: Optional[str],
    returned_title: Optional[str],
    benchmark_row: Optional[Dict[str, Any]],
) -> tuple:
    """(mapping_state, reason). Hard-failure states raise nothing here; the
    runner aborts on unexpected_mapping_mismatch (design §6)."""
    if returned_asin is None:
        return STATE_UNAVAILABLE, "provider returned no ASIN; no mapping conclusion"
    if str(returned_asin).upper() != requested_asin.upper():
        return (
            STATE_UNEXPECTED_MISMATCH,
            f"returned ASIN {returned_asin} != requested ASIN {requested_asin} — hard mapping failure",
        )
    if benchmark_row is None:
        return STATE_UNAVAILABLE, "no benchmark reference row for requested ASIN"
    if returned_title is None:
        return STATE_UNAVAILABLE, "provider returned no title; mapping review required"
    identity = bv.compare_identity(
        benchmark_row.get("title"), returned_title,
        bench_pack=bv.pack_tokens_signal(benchmark_row.get("title")),
        live_pack=bv.pack_tokens_signal(returned_title),
    )
    if identity.get("pack_mismatch_block"):
        # Strong pack-size conflict: hard stop for ALL ASINs, including the
        # known title-conflict set. A pack mismatch is independent product
        # evidence beyond title text, so it must never be downgraded to review.
        return (
            STATE_UNEXPECTED_MISMATCH,
            f"pack-size signal conflict — {identity.get('note')}",
        )
    if benchmark_row.get("title_conflict"):
        # Pre-registered historical benchmark title conflict. The returned ASIN
        # already equals the requested ASIN (checked above), which establishes
        # product identity, so a differing returned title is the expected
        # cross-file disagreement — route to human review, do NOT hard-stop, and
        # preserve the title mismatch flag for the report. No benchmark title is
        # silently overwritten or resolved.
        return (
            STATE_EXPECTED_REVIEW,
            "Known benchmark title conflict — returned title requires human mapping review.",
        )
    if identity.get("title_status") == "mismatch":
        return (
            STATE_UNEXPECTED_MISMATCH,
            f"returned title incompatible with benchmark — {identity.get('note')}",
        )
    return STATE_MATCH, "ASIN exact match and title/pack compatible"


# ---------------------------------------------------------------------------
# Snapshot mapping (provider result -> intel_schema facts)
# ---------------------------------------------------------------------------

def _intel_offer(offer: Dict[str, Any]) -> Dict[str, Any]:
    """Map one normalized snapshot offer to the intel_schema offer shape.
    Only fields present in the source are emitted; unknown stays absent
    (null on render), never 0."""
    mapped: Dict[str, Any] = {}
    price = offer.get("price")
    price_value = None
    if isinstance(price, dict):
        raw = price.get("value")
        if isinstance(raw, bool):
            price_value = None
        elif isinstance(raw, (int, float)):
            price_value = float(raw)
        elif isinstance(raw, str):
            try:
                price_value = float(raw)
            except (TypeError, ValueError):
                price_value = None
    elif isinstance(price, (int, float)) and not isinstance(price, bool):
        price_value = float(price)
    if price_value is not None:
        mapped["price"] = round(price_value, 2)
    is_fba = offer.get("is_fba")
    is_fbm = offer.get("is_fbm")
    fulfilled_by_amazon = offer.get("fulfilled_by_amazon")
    if is_fba is True or fulfilled_by_amazon is True:
        mapped["fulfillment"] = "FBA"
    elif is_fbm is True:
        mapped["fulfillment"] = "FBM"
    elif offer.get("buybox_winner") is True and offer.get("seller_name") == "Amazon.com":
        mapped["fulfillment"] = "AMAZON"
    if offer.get("buybox_winner") is True:
        mapped["is_buy_box_winner"] = True
    for key in ("seller_name", "seller_id", "condition"):
        value = offer.get(key)
        if value is not None:
            mapped[key] = value
    return mapped


def build_envelope_snapshot(asin: str, result: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize one adapter result into an intel_schema-shaped snapshot.
    Uses market_snapshot_store.build_snapshot for offer normalization (pure,
    offline) and maps only fields the result actually carries."""
    snap = snapshot_store.build_snapshot(asin, result)
    observed_at = result.get("observed_at") or snap.get("observed_at")
    coverage_status = "full" if snap.get("offers_complete") is True else (
        "partial" if snap.get("offers_returned") else "unknown"
    )
    provenance: Dict[str, Any] = {
        "market.seller_counts": {"source": "easyparser", "fetched_at": observed_at},
        "market.offers": {"source": "easyparser", "fetched_at": observed_at},
        "market.coverage": {"source": "easyparser", "fetched_at": observed_at},
    }
    if snap.get("title"):
        provenance["identity.name"] = {"source": "easyparser", "fetched_at": observed_at}
    offers = [_intel_offer(o) for o in (snap.get("offers") or []) if isinstance(o, dict)]
    buy_box = snap.get("buy_box") or {}
    seller_counts = snap.get("seller_counts") or {}
    gaps = [g for g in (result.get("data_gaps") or []) if isinstance(g, str)]
    return {
        "schema_version": intel_schema.SCHEMA_VERSION,
        "asin": asin,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "sources": {"easyparser": {"kind": "normalized_provider_result"}},
        "facts": {
            "identity": {
                "name": snap.get("title"),
                "pack_match": None,
                "upc_or_ean": None,
                "net_weight_lbs": None,
            },
            "cost": {"costco_cost": None, "cost_status": "unavailable", "source": None},
            "fees": {
                "fba_fee": None,
                "fba_fee_status": "unavailable",
                "referral_fee": None,
                "fee_provenance": None,
            },
            "demand": {
                "estimated_monthly_sales": None,
                "sales_estimation_method": "unknown",
                "sales_estimation_confidence": "unknown",
                "bsr": None,
                "bsr_category": None,
            },
            "market": {
                "amazon_price": None,
                "buy_box": {
                    "available": bool(buy_box.get("available")),
                    "price": buy_box.get("price"),
                    "seller_name": buy_box.get("seller_name"),
                    "seller_id": buy_box.get("seller_id"),
                    "fulfillment": buy_box.get("fulfillment"),
                    "condition": buy_box.get("condition"),
                    "source": "easyparser",
                    "observed_at": observed_at,
                },
                "seller_counts": {
                    "total_observed": seller_counts.get("observed_total"),
                    "claimed_total": seller_counts.get("claimed_total"),
                    "fba_observed": seller_counts.get("fba_observed"),
                    "fbm_observed": seller_counts.get("fbm_observed"),
                    "amazon_observed": seller_counts.get("amazon_observed"),
                },
                "coverage": {
                    "offer_list_available": snap.get("offers_returned") is not None,
                    "offers_complete_status": coverage_status,
                    "coverage_reason": "; ".join(gaps) if gaps else (
                        None if coverage_status == "full" else "provider did not return a complete offer roster"
                    ),
                },
                "offers": offers,
            },
            "economics": {
                "net_profit": None,
                "roi_pct": None,
                "economics_confidence": "unavailable",
                "economics_status": "model_based_values_not_merged_into_provider_data",
            },
            "provenance": provenance,
        },
    }


def result_status_for(snap: Dict[str, Any]) -> str:
    status = snap.get("data_status")
    if status == snapshot_store.DATA_STATUS_AVAILABLE:
        return "available"
    if status == snapshot_store.DATA_STATUS_PARTIAL:
        return "partial"
    if status == snapshot_store.DATA_STATUS_FAILED:
        return "provider_error"
    return "unavailable"


# ---------------------------------------------------------------------------
# Adapter boundary (fixture only in this build)
# ---------------------------------------------------------------------------

# ProviderAdapter (and GuardError/BindingError/RunAbort) are imported from
# proof_batch_contracts so the runner and the live adapter share one class
# identity. FixtureAdapter subclasses the shared contract base.

class FixtureAdapter(ProviderAdapter):
    """Deterministic synthetic adapter (test/CLI fixture use only, labeled
    synthetic everywhere it appears). Zero network by construction."""

    NAME = "fixture"

    def __init__(self, benchmark_store: Dict[str, Any]):
        self.canonical = benchmark_store.get("canonical") or {}
        self.requests_made: List[str] = []

    def fetch(self, asin: str, request_index: int) -> Dict[str, Any]:
        self.requests_made.append(asin)
        row = self.canonical.get(asin) or {}
        base = row.get("price")
        base = base if isinstance(base, (int, float)) and not isinstance(base, bool) else 12.0
        drift = base * (1.01 + (request_index % 3) * 0.01)
        offers = []
        for i in range(3):
            price = round(drift * (1.0 + i * 0.02), 2)
            offers.append({
                "position": i + 1,
                "buybox_winner": i == 0,
                "price": {"value": price, "currency": "USD"},
                "condition": "New",
                "seller_id": f"SELLER-{request_index}-{i}",
                "seller_name": "Amazon.com" if i == 0 else f"Fixture Seller {i}",
                "is_prime": i == 0,
                "is_fba": True,
                "is_fbm": False,
                "ships_from": "USA",
                "shipping_text": "FREE Shipping" if i == 0 else None,
            })
        return {
            "source": "fixture",
            "asin": asin,
            "title": row.get("title"),
            "offer_count": 3,
            "offers_returned_count": 3,
            "buy_box_price": drift,
            "buy_box_price_raw": None,
            "buy_box_seller": "Amazon.com",
            "buy_box_seller_id": f"SELLER-{request_index}-0",
            "buy_box_is_fba": True,
            "buy_box_is_fbm": False,
            "buy_box_is_prime": True,
            "buy_box_condition": "New",
            "observed_fba_offer_count": 3,
            "observed_fbm_offer_count": 0,
            "observed_amazon_offer_count": 1,
            "offers": offers,
            "request_zip_code": "75201",
            "observed_at": "2026-08-18T12:00:00+00:00",
            "credits_used": 5,
            "credits_remaining": None,
            "data_gaps": ["SYNTHETIC FIXTURE — not live provider data"],
            "request_index": request_index,
        }


# ---------------------------------------------------------------------------
# Atomic persistence
# ---------------------------------------------------------------------------

def _atomic_write_json(path: str, payload: Dict[str, Any]) -> None:
    """Temp write + flush + fsync -> atomic os.replace. Raises OSError on
    failure; a leftover .tmp is cleaned up."""
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_path, path)
    if os.path.exists(tmp_path):
        try:
            os.remove(tmp_path)
        except OSError:
            pass


def _read_back(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object on read-back")
    return payload


# ---------------------------------------------------------------------------
# Guarded run
# ---------------------------------------------------------------------------

def run_guarded(
    preflight: Dict[str, Any],
    adapter: ProviderAdapter,
    max_requests: int,
    max_credits: int,
    live: bool,
    live_enabled: bool,
    out_dir: str,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """The guarded execution function. Requires every guard; refuses with
    GuardError (nothing written) when any is missing. Aborts (scrubbed
    failure manifest only) on binding failure, budget stop, wrong ASIN,
    incompatible mapping, schema failure, secret-like output, adapter crash,
    or persistence failure. Finalizes validated-result-envelopes.json ONLY
    when all 20 ASINs hold a final non-aborting status.

    `live_enabled` is passed in so tests can exercise the gate without
    setting SCANNER_LIVE_ALLOWED; the CLI always passes
    live_gate.live_enabled()."""
    if not live:
        raise GuardError("live flag required; refused without explicit --live")
    if not live_enabled:
        raise GuardError(
            f"live gate disabled ({live_gate.GATE_ENV} not an explicit opt-in); refused"
        )
    binding_errors = validate_preflight_binding(preflight)
    if binding_errors:
        raise GuardError("preflight binding invalid: " + "; ".join(binding_errors))
    if not isinstance(adapter, ProviderAdapter):
        raise GuardError("a provider adapter is required")
    if adapter.NAME == "fixture" and not isinstance(adapter, FixtureAdapter):
        raise GuardError("invalid fixture adapter")

    fingerprint = preflight_fingerprint(preflight)
    asins = canonical_preflight_asins(preflight)
    plan_total = (preflight.get("provider_plan") or {}).get("request_count_total")
    if plan_total != HARD_PROOF_BATCH_LIMIT:
        raise GuardError("preflight plan request count is not 20; binding rejected")
    allowed = min(max_requests, plan_total, HARD_PROOF_BATCH_LIMIT)
    if allowed < 1:
        raise GuardError("effective request allowance is zero; refused")
    if max_requests > HARD_PROOF_BATCH_LIMIT:
        raise GuardError(f"max_requests exceeds the hard proof-batch limit of {HARD_PROOF_BATCH_LIMIT}")

    run_id = run_id or preflight.get("run_id") or f"proof-batch-run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    canonical = (preflight.get("selection") or {}).get("asins") or []
    benchmark_lookup = {}
    for row in canonical:
        if isinstance(row, dict) and row.get("asin"):
            benchmark_lookup[row["asin"].upper()] = row

    budget = BudgetTracker(max_requests=allowed, max_credits=max_credits)
    envelopes: List[Dict[str, Any]] = []
    stop_reason = "completed"

    try:
        for request_index, asin in enumerate(asins, start=1):
            if not budget.can_request():
                stop_reason = budget.stop_reason() or STOP_MAX_REQUESTS
                break
            refresh = getattr(adapter, "refresh_guard_state", None)
            if callable(refresh):
                refresh(budget.allowed_requests - budget.requests_used,
                        max(0, budget.max_credits - budget.credits_estimated_used))
            try:
                result = adapter.fetch(asin, request_index)
            except Exception as exc:  # adapter contract says never raise; treat as abort
                raise RunAbort(STOP_ADAPTER, f"fetch({asin})", asin, str(exc)) from exc

            meta = result.get("adapter_request_meta") if isinstance(result, dict) else None
            meta = meta if isinstance(meta, dict) else None
            if meta is not None and meta.get("credit_accounting_status") == "provider_reported":
                budget.record_request(credits_reported=meta.get("actual_credits_used"))
            else:
                budget.record_request(credits_reported=result.get("credits_used"))

            if pb.contains_secret_like(result):
                raise RunAbort(STOP_SECRET, f"normalize({asin})", asin, "secret-like key in provider result")

            # Provider-reported failure or malformed/parse failure is a hard
            # abort (design §8): never finalize with unusable provider data.
            if meta is not None and meta.get("provider_status") == "provider_error":
                raise RunAbort(
                    STOP_PROVIDER_ERROR, f"provider({asin})", asin,
                    "provider reported a request failure; hard abort",
                )
            if meta is not None and meta.get("provider_status") == "parse_error":
                raise RunAbort(
                    STOP_PARSE_ERROR, f"provider({asin})", asin,
                    "provider response was malformed; hard abort",
                )

            snap = build_envelope_snapshot(asin, result)
            if pb.contains_secret_like(snap):
                raise RunAbort(STOP_SECRET, f"normalize({asin})", asin, "secret-like key in normalized snapshot")

            normalized = snapshot_store.build_snapshot(asin, result)
            provider_status = "success" if normalized.get("data_status") in (
                snapshot_store.DATA_STATUS_AVAILABLE, snapshot_store.DATA_STATUS_PARTIAL
            ) else ("error" if normalized.get("data_status") == snapshot_store.DATA_STATUS_FAILED else "partial")
            result_status = result_status_for(normalized)

            # Returned-ASIN evidence: prefer the provider's explicit product
            # ASIN when supplied; when the provider could not return one the
            # requested/returned relationship cannot be established — a hard
            # abort (design §8), never a silent pass-through.
            if isinstance(result, dict) and "provider_asin" in result:
                mapping_asin = result.get("provider_asin")
                if mapping_asin is None:
                    raise RunAbort(
                        STOP_WRONG_ASIN, f"map({asin})", asin,
                        "provider returned no product ASIN; requested/returned ASIN relationship cannot be established",
                    )
            else:
                mapping_asin = result.get("asin")

            mapping_state, mapping_reason = classify_mapping(
                asin,
                mapping_asin,
                snap.get("facts", {}).get("identity", {}).get("name"),
                benchmark_lookup.get(asin),
            )
            if mapping_state == STATE_UNEXPECTED_MISMATCH:
                raise RunAbort(
                    STOP_WRONG_ASIN if mapping_asin and str(mapping_asin).upper() != asin.upper()
                    else STOP_MAPPING_MISMATCH,
                    f"map({asin})", asin, mapping_reason,
                )

            captured_at = result.get("observed_at") or datetime.now(timezone.utc).isoformat()
            env = pb.build_envelope(
                run_id=run_id,
                asin=asin,
                provider=EXPECTED_PROVIDER,
                requested_fields=list(EXPECTED_REQUESTED_FIELDS),
                snapshot=snap,
                provider_status=provider_status,
                result_status=result_status,
                captured_at=captured_at,
                provenance={
                    "coverage": snap["facts"]["market"]["coverage"]["offers_complete_status"],
                    "provider_request_id": (meta or {}).get("request_id"),
                    "credit_accounting_status": (meta or {}).get("credit_accounting_status"),
                    "adapter": adapter.NAME,
                },
                error={"code": "provider_gap", "message": "; ".join(
                    g for g in (result.get("data_gaps") or []) if isinstance(g, str)
                )} if result_status in ("provider_error", "unavailable") else None,
                preflight_fingerprint=fingerprint,
                requested_asin=asin,
                request_index=request_index,
                mapping_state=mapping_state,
                mapping_reason=mapping_reason,
                credits_used_reported=budget.credits_reported_used,
                credits_used_estimated=budget.credits_estimated_used,
            )
            schema_errors = pb.validate_envelope(env)
            if schema_errors:
                raise RunAbort(STOP_SCHEMA, f"validate({asin})", asin, "; ".join(schema_errors))
            envelopes.append(env)
    except RunAbort as exc:
        # Scrubbed failure manifest (never secrets/raw bodies), then abort.
        _write_failure_manifest(out_dir, run_id, fingerprint, exc.reason, exc.stage, exc.asin, budget)
        raise

    if stop_reason != "completed":
        _write_failure_manifest(out_dir, run_id, fingerprint, stop_reason, "request_loop", None, budget)
        return {"status": "aborted", "stop_reason": stop_reason, "run_id": run_id}

    if len(envelopes) != HARD_PROOF_BATCH_LIMIT:
        _write_failure_manifest(out_dir, run_id, fingerprint, STOP_MAX_REQUESTS, "finalize", None, budget)
        return {"status": "aborted", "stop_reason": STOP_MAX_REQUESTS, "run_id": run_id}

    try:
        _finalize_success(out_dir, run_id, fingerprint, preflight, envelopes, budget, adapter)
    except RunAbort as exc:
        if exc.reason == STOP_PERSISTENCE:
            _write_failure_manifest(out_dir, run_id, fingerprint, STOP_PERSISTENCE, "finalize", None, budget)
        raise
    except OSError as exc:
        _write_failure_manifest(out_dir, run_id, fingerprint, STOP_PERSISTENCE, "finalize", None, budget)
        raise RunAbort(STOP_PERSISTENCE, "finalize", None, str(exc)) from exc
    return {"status": "completed", "stop_reason": "completed", "run_id": run_id}


def _write_failure_manifest(out_dir: str, run_id: str, fingerprint: str,
                            reason: str, stage: str, asin: Optional[str],
                            budget: BudgetTracker) -> None:
    os.makedirs(out_dir, exist_ok=True)
    manifest = {
        "kind": "proof-batch-failure-manifest",
        "schema_version": 1,
        "run_id": run_id,
        "preflight_fingerprint": fingerprint,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "stop_reason": reason,
        "asin": asin,
        "budget": budget.snapshot_state() if budget else None,
        "note": "scrubbed failure record — no secrets, no raw response bodies, no normalized results",
    }
    _atomic_write_json(os.path.join(out_dir, "failure-manifest.json"), manifest)


def _is_synthetic_adapter(adapter: ProviderAdapter) -> bool:
    """True when the adapter's data is synthetic (fixture adapter, or a live
    adapter explicitly run with a mock/force-synthetic label)."""
    return isinstance(adapter, FixtureAdapter) or bool(getattr(adapter, "force_synthetic_label", False))


def _finalize_success(out_dir: str, run_id: str, fingerprint: str,
                      preflight: Dict[str, Any], envelopes: List[Dict[str, Any]],
                      budget: BudgetTracker, adapter: ProviderAdapter) -> None:
    os.makedirs(out_dir, exist_ok=True)
    results_path = os.path.join(out_dir, "validated-result-envelopes.json")
    payload = {
        "kind": "proof-batch-validated-results",
        "schema_version": 1,
        "run_id": run_id,
        "preflight_fingerprint": fingerprint,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "adapter": adapter.NAME,
        "synthetic_fixture": _is_synthetic_adapter(adapter),
        "envelope_count": len(envelopes),
        "envelopes": envelopes,
    }
    # Temp write -> read-back validation (every envelope + fingerprint) ->
    # atomic rename. No finalized artifact before validation passes.
    tmp_path = f"{results_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    read_back = _read_back(tmp_path)
    if read_back.get("preflight_fingerprint") != fingerprint:
        raise RunAbort(STOP_PERSISTENCE, "finalize", None, "fingerprint mismatch on read-back")
    for env in read_back.get("envelopes") or []:
        if env.get("preflight_fingerprint") != fingerprint:
            raise RunAbort(STOP_PERSISTENCE, "finalize", None, "envelope fingerprint mismatch on read-back")
        if pb.validate_envelope(env):
            raise RunAbort(STOP_PERSISTENCE, "finalize", None, "envelope invalid on read-back")
    try:
        os.replace(tmp_path, results_path)
    except OSError:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise

    manifest = {
        "kind": "proof-batch-run-manifest",
        "schema_version": 1,
        "run_id": run_id,
        "preflight_fingerprint": fingerprint,
        "preflight_path": "data/batch/proof-batch-preflight-20260818T060549Z.json",
        "preflight_run_id": preflight.get("run_id"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": EXPECTED_PROVIDER,
        "requested_fields": list(EXPECTED_REQUESTED_FIELDS),
        "adapter": adapter.NAME,
        "synthetic_fixture": _is_synthetic_adapter(adapter),
        "asins": [e["asin"] for e in envelopes],
        "counts": {
            "selected": len(envelopes),
            "available": sum(1 for e in envelopes if e["result_status"] == "available"),
            "partial": sum(1 for e in envelopes if e["result_status"] == "partial"),
            "provider_error": sum(1 for e in envelopes if e["result_status"] == "provider_error"),
            "unavailable": sum(1 for e in envelopes if e["result_status"] == "unavailable"),
            "expected_mapping_review": sum(1 for e in envelopes if e.get("mapping_state") == STATE_EXPECTED_REVIEW),
            "match": sum(1 for e in envelopes if e.get("mapping_state") == STATE_MATCH),
        },
        "budget": budget.snapshot_state(),
        "stop_reason": "completed",
        "persistence": {
            "results_file": "validated-result-envelopes.json",
            "atomic_replace": True,
            "read_back_validated": True,
        },
        "honesty": {
            "actual_credit_total": (
                budget.credits_reported_used
                if budget.credits_reported_used > 0
                else None
            ),
            "actual_credit_note": (
                "reported by provider" if budget.credits_reported_used > 0
                else "provider did not report credit usage; estimated only — never claimed as actual"
            ),
        },
    }
    _atomic_write_json(os.path.join(out_dir, "run-manifest.json"), manifest)


# ---------------------------------------------------------------------------
# Report (post-run comparator; zero network)
# ---------------------------------------------------------------------------

def load_benchmark_reference() -> Dict[str, Any]:
    path = "data/benchmarks/asin_benchmark_reference.json"
    if not os.path.isfile(path):
        return {"canonical": {}, "conflicts": []}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _outcome_status(report_row: Dict[str, Any]) -> str:
    """Per-ASIN outcome vocabulary (Phase F): match |
    expected_mapping_review | unexpected_mapping_mismatch | unavailable |
    possible_market_drift | provider_error. parse_error is a hard abort and
    can never appear in a finalized report (documented in the report)."""
    mapping = report_row.get("mapping_state")
    result = report_row.get("result_status")
    if result == "provider_error":
        return STATE_PROVIDER_ERROR
    if result == "unavailable":
        return STATE_UNAVAILABLE
    if mapping == STATE_UNEXPECTED_MISMATCH:
        return STATE_UNEXPECTED_MISMATCH
    if mapping == STATE_EXPECTED_REVIEW:
        return STATE_EXPECTED_REVIEW
    if mapping == STATE_MATCH:
        price_cls = (report_row.get("price") or {}).get("classification")
        if price_cls in ("moderate_drift", "material_drift"):
            return STATE_DRIFT
        return STATE_MATCH
    return STATE_UNAVAILABLE


def build_run_report(run_dir: str, reference: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compare a finalized validated-result-envelopes artifact against the
    benchmark reference. Refuses (raises) on missing/invalid artifacts or a
    broken results↔run-manifest↔preflight fingerprint linkage."""
    results_path = os.path.join(run_dir, "validated-result-envelopes.json")
    if not os.path.isfile(results_path):
        raise GuardError(f"finalized results artifact not found: {results_path}")
    payload = _read_back(results_path)
    if payload.get("kind") != "proof-batch-validated-results":
        raise GuardError("artifact is not a proof-batch validated-results file")
    envelopes = payload.get("envelopes")
    if not isinstance(envelopes, list) or not envelopes:
        raise GuardError("validated-results artifact contains no envelopes")

    manifest_path = os.path.join(run_dir, "run-manifest.json")
    if not os.path.isfile(manifest_path):
        raise GuardError("run-manifest.json not found; fingerprint linkage cannot be verified")
    manifest = _read_back(manifest_path)
    if manifest.get("kind") != "proof-batch-run-manifest":
        raise GuardError("run-manifest.json is not a proof-batch run manifest")
    if manifest.get("preflight_fingerprint") != payload.get("preflight_fingerprint"):
        raise GuardError(
            "fingerprint linkage broken: run-manifest fingerprint != validated-results fingerprint; "
            "refusing to report"
        )

    reference = reference if reference is not None else load_benchmark_reference()
    reports = []
    for env in envelopes:
        report = pb.compare_envelope(reference, env)
        report["requested_asin"] = env.get("requested_asin") or env.get("asin")
        report["returned_asin"] = (env.get("snapshot") or {}).get("asin")
        report["request_index"] = env.get("request_index")
        report["mapping_state"] = env.get("mapping_state")
        report["mapping_reason"] = env.get("mapping_reason")
        report["result_status"] = env.get("result_status")
        report["provider_status"] = env.get("provider_status")
        report["preflight_fingerprint"] = env.get("preflight_fingerprint")
        report["captured_at"] = env.get("captured_at")
        report["coverage"] = (env.get("provenance") or {}).get("coverage")
        report["provider_request_id"] = (env.get("provenance") or {}).get("provider_request_id")
        report["credit_accounting_status"] = (env.get("provenance") or {}).get("credit_accounting_status")
        report["outcome_status"] = _outcome_status(report)
        reports.append(report)

    metrics = bv.summarize_batch(reports)
    mapping_counts: Dict[str, int] = {}
    for state in (STATE_MATCH, STATE_EXPECTED_REVIEW, STATE_UNEXPECTED_MISMATCH, STATE_UNAVAILABLE):
        mapping_counts[state] = sum(1 for r in reports if r.get("mapping_state") == state)
    outcome_counts: Dict[str, int] = {}
    for state in (STATE_MATCH, STATE_EXPECTED_REVIEW, STATE_UNEXPECTED_MISMATCH,
                  STATE_UNAVAILABLE, STATE_DRIFT, STATE_PROVIDER_ERROR):
        outcome_counts[state] = sum(1 for r in reports if r.get("outcome_status") == state)
    expected_review_asins = sorted(
        r["asin"] for r in reports if r.get("mapping_state") == STATE_EXPECTED_REVIEW
    )
    unexpected_mismatch_asins = sorted(
        r["asin"] for r in reports if r.get("mapping_state") == STATE_UNEXPECTED_MISMATCH
    )
    price_classes: Dict[str, int] = {}
    for r in reports:
        cls = (r.get("price") or {}).get("classification") or "unavailable"
        price_classes[cls] = price_classes.get(cls, 0) + 1

    return {
        "kind": "proof-batch-benchmark-comparison-report",
        "schema_version": 1,
        "run_id": payload.get("run_id"),
        "preflight_fingerprint": payload.get("preflight_fingerprint"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_artifact": "validated-result-envelopes.json",
        "fingerprint_linkage": {
            "results_artifact": payload.get("preflight_fingerprint"),
            "run_manifest": manifest.get("preflight_fingerprint"),
            "linked": True,
        },
        "per_asin": reports,
        "metrics": metrics,
        "mapping_summary": {
            "match_count": mapping_counts.get(STATE_MATCH, 0),
            "expected_mapping_review_count": mapping_counts.get(STATE_EXPECTED_REVIEW, 0),
            "expected_mapping_review_asins": expected_review_asins,
            "unexpected_mapping_mismatch_count": mapping_counts.get(STATE_UNEXPECTED_MISMATCH, 0),
            "unexpected_mapping_mismatch_asins": unexpected_mismatch_asins,
            "unavailable_count": mapping_counts.get(STATE_UNAVAILABLE, 0),
        },
        "outcome_summary": outcome_counts,
        "outcome_vocabulary": {
            "match": STATE_MATCH,
            "expected_mapping_review": STATE_EXPECTED_REVIEW,
            "unexpected_mapping_mismatch": STATE_UNEXPECTED_MISMATCH,
            "unavailable": STATE_UNAVAILABLE,
            "possible_market_drift": STATE_DRIFT,
            "provider_error": STATE_PROVIDER_ERROR,
            "parse_error": STATE_PARSE_ERROR,
            "parse_error_note": "parse_error is a hard abort (scrubbed failure manifest); it can never appear in a finalized report",
        },
        "price_drift_summary": price_classes,
        "drift_policy": {
            "capture_time_unknown": True,
            "note": "benchmark capture time unknown — price/BSR/review differences are possible market drift, never provider failure by themselves",
        },
        "internally_validated": {
            "label": bv.INTERNAL_ONLY_LABEL,
            "economics_demand": "model-based/internal unless independently sourced",
        },
        "no_universal_accuracy_percentage": True,
        "purchase_authorization_statement": PURCHASE_AUTHORIZATION_STATEMENT,
        "limitations": {
            "offer_roster": "coverage full/partial/unknown per envelope; no benchmark seller roster exists",
            "economics_demand_not_benchmarked": True,
            "raw_responses_never_persisted": True,
            "capture_time_unknown": True,
        },
    }


def write_report_files(run_dir: str, report: Dict[str, Any]) -> List[str]:
    """Write benchmark-comparison-report.json/.csv + human-review-summary.md
    into the run dir (atomic per file)."""
    import csv as _csv

    json_path = os.path.join(run_dir, "benchmark-comparison-report.json")
    _atomic_write_json(json_path, report)

    csv_path = os.path.join(run_dir, "benchmark-comparison-report.csv")
    tmp_path = f"{csv_path}.tmp"
    rows = [
        "request_index",
        "requested_asin",
        "returned_asin",
        "outcome_status",
        "mapping_state",
        "title_status",
        "pack_mismatch_block",
        "price_classification",
        "price_absolute_variance",
        "review_trend",
        "bsr_comparable",
        "result_status",
        "provider_status",
        "offer_coverage",
        "buy_box_present",
        "internally_consistent",
    ]
    with open(tmp_path, "w", encoding="utf-8", newline="") as fh:
        writer = _csv.writer(fh)
        writer.writerow(rows)
        for r in report["per_asin"]:
            price = r.get("price") or {}
            reviews = r.get("reviews") or {}
            bsr = r.get("bsr") or {}
            offer_section = r.get("offer_section") or {}
            consistency = (offer_section.get("internal_consistency") or {}).get("status")
            writer.writerow([
                r.get("request_index"),
                r.get("requested_asin"),
                r.get("returned_asin"),
                r.get("outcome_status"),
                r.get("mapping_state"),
                (r.get("identity") or {}).get("title_status"),
                (r.get("identity") or {}).get("pack_mismatch_block"),
                price.get("classification"),
                price.get("absolute_variance"),
                reviews.get("trend"),
                bsr.get("comparable"),
                r.get("result_status"),
                r.get("provider_status"),
                offer_section.get("coverage"),
                offer_section.get("buy_box_present"),
                consistency,
            ])
    os.replace(tmp_path, csv_path)

    md_path = os.path.join(run_dir, "human-review-summary.md")
    lines = [
        "# Proof-Batch Validation Run — Human Review Summary",
        "",
        f"- run_id: `{report.get('run_id')}`",
        f"- preflight fingerprint: `{report.get('preflight_fingerprint')}`",
        f"- generated_at: {report.get('generated_at')}",
        "",
        "## Mapping summary",
        f"- match: {report['mapping_summary']['match_count']}",
        f"- expected_mapping_review: {report['mapping_summary']['expected_mapping_review_count']} "
        f"({', '.join(report['mapping_summary']['expected_mapping_review_asins']) or 'none'})",
        f"- unexpected_mapping_mismatch: {report['mapping_summary']['unexpected_mapping_mismatch_count']} "
        f"({', '.join(report['mapping_summary']['unexpected_mapping_mismatch_asins']) or 'none'})",
        f"- unavailable: {report['mapping_summary']['unavailable_count']}",
        "",
        "## Outcome summary (per-ASIN vocabulary)",
        f"- {report['outcome_summary']}",
        f"- parse_error note: {report['outcome_vocabulary']['parse_error_note']}",
        "",
        "## Price drift (vs unknown-timestamp benchmark)",
        f"- {report['price_drift_summary']}",
        "- Drift is possible market drift, not provider failure; capture time unknown.",
        "",
        "## Batch metrics",
        f"- benchmark matched ASINs: {report['metrics'].get('benchmark_matched_asin_count')}",
        f"- unmatched: {report['metrics'].get('unmatched_asin_count')}",
        f"- pack mismatch blocks: {report['metrics'].get('pack_mismatch_block_count')}",
        "",
        "## Limits",
        f"- economics/demand: {report['internally_validated']['label']} — never a purchase decision.",
        f"- No universal accuracy percentage: {report['no_universal_accuracy_percentage']}.",
        f"- {report.get('purchase_authorization_statement') or PURCHASE_AUTHORIZATION_STATEMENT}",
        "- Invoice legitimacy, selling eligibility, correct pack, fee confirmation, and supply-chain",
        "  review remain required.",
        "",
    ]
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return [json_path, csv_path, md_path]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _arg(opts: Dict[str, str], name: str) -> Optional[str]:
    for i, arg in enumerate(opts.get("argv", [])):
        if arg == name and i + 1 < len(opts.get("argv", [])):
            return opts["argv"][i + 1]
    return None


def _require_caps(argv: List[str]) -> tuple:
    max_requests = None
    max_credits = None
    for i, arg in enumerate(argv):
        if arg == "--max-requests" and i + 1 < len(argv):
            try:
                max_requests = int(argv[i + 1])
            except (TypeError, ValueError):
                max_requests = None
        if arg == "--max-credits" and i + 1 < len(argv):
            try:
                max_credits = int(argv[i + 1])
            except (TypeError, ValueError):
                max_credits = None
    missing = []
    if max_requests is None or max_requests < 1:
        missing.append("--max-requests N (>= 1)")
    if max_credits is None or max_credits < 1:
        missing.append("--max-credits N (>= 1)")
    if missing:
        raise GuardError("every finite cap is required. Missing: " + ", ".join(missing))
    return max_requests, max_credits


def _preflight_arg(argv: List[str]) -> str:
    for i, arg in enumerate(argv):
        if arg == "--preflight" and i + 1 < len(argv):
            return argv[i + 1]
    raise GuardError("--preflight <path> is required")


def _run_dry_run(argv: List[str]) -> int:
    max_requests, max_credits = _require_caps(argv)
    preflight = load_preflight(_preflight_arg(argv))
    errors = validate_preflight_binding(preflight)
    if errors:
        print("binding invalid:")
        for e in errors:
            print("  - " + e)
        return 2
    fingerprint = preflight_fingerprint(preflight)
    asins = canonical_preflight_asins(preflight)
    allowed = min(max_requests, HARD_PROOF_BATCH_LIMIT, HARD_PROOF_BATCH_LIMIT)
    output_dir = os.path.join(RUN_OUTPUT_ROOT, preflight.get("run_id") or "run")
    expected_review = sorted(
        (row.get("asin") or "").upper()
        for row in (preflight.get("selection") or {}).get("asins") or []
        if isinstance(row, dict) and row.get("title_conflict")
    )
    print("mode:                  dry-run (zero network calls)")
    print("preflight:             %s" % _preflight_arg(argv))
    print("preflight run_id:      %s" % preflight.get("run_id"))
    print("preflight fingerprint: %s" % fingerprint)
    print("asins:                 %d / %d (fixed set)" % (len(asins), HARD_PROOF_BATCH_LIMIT))
    for asin in asins:
        print("  - %s" % asin)
    print("provider:              EASYPARSER (offer/seller/price/shipping/fulfillment/Buy Box)")
    print("requested fields:      %s" % ", ".join(EXPECTED_REQUESTED_FIELDS))
    print("max_requests:          %d (effective %d)" % (max_requests, allowed))
    print("max_credits:           %d" % max_credits)
    print("estimated credits:     ~%.0f (%d requests x %.0f/request, documented estimate)" % (
        allowed * ESTIMATED_CREDITS_PER_REQUEST, allowed, ESTIMATED_CREDITS_PER_REQUEST))
    print("credit accounting:     estimated_only (provider not contacted; actual_credits_used = null)")
    print("retries:               0 (default; no hidden retries)")
    print("output dir:            %s (exact future write location)" % output_dir)
    print("expected_mapping_review ASINs: %s" % (
        ", ".join(expected_review) if expected_review else "none flagged in this preflight"))
    print("hard stop conditions (any of these aborts the run with a scrubbed failure manifest):")
    for reason, description in HARD_STOP_CONDITIONS:
        print("  - %s: %s" % (reason, description))
    print(pb.HUMAN_CONFIRMATION_LINE)
    print("DRY RUN ONLY — NO PROVIDER CALLS, NO CREDITS USED, NO LIVE SNAPSHOT WRITTEN")
    return 0


def _run_fixture_run(argv: List[str]) -> int:
    max_requests, max_credits = _require_caps(argv)
    preflight = load_preflight(_preflight_arg(argv))
    out_dir = None
    for i, arg in enumerate(argv):
        if arg == "--out-dir" and i + 1 < len(argv):
            out_dir = argv[i + 1]
    if not out_dir:
        raise GuardError("fixture-run requires --out-dir <path> (explicit destination)")
    binding_errors = validate_preflight_binding(preflight)
    if binding_errors:
        raise GuardError("preflight binding invalid: " + "; ".join(binding_errors))
    reference = load_benchmark_reference()
    adapter = FixtureAdapter(reference)
    outcome = run_guarded(
        preflight=preflight,
        adapter=adapter,
        max_requests=max_requests,
        max_credits=max_credits,
        live=True,
        live_enabled=True,
        out_dir=out_dir,
    )
    print("fixture-run:           %s" % outcome["status"])
    print("run_id:                %s" % outcome["run_id"])
    print("requests made:         %d" % len(adapter.requests_made))
    print("note:                  SYNTHETIC FIXTURE — no provider calls, zero network")
    return 0


# ---------------------------------------------------------------------------
# Adapter arming (guarded path only)
# ---------------------------------------------------------------------------

# Test-only client injection hook. NEVER set by production code. When set,
# _arm_live_adapter uses its result as the injected client so offline tests
# exercise the FULL arming path with a fake; production resolves the real
# client via adapter_mod.real_easyparser_client() (lazily, only after every
# guard passes).
LIVE_CLIENT_FACTORY = None


def _arm_live_adapter(preflight: Dict[str, Any], allowed: int, max_credits: int) -> ProviderAdapter:
    """Arm the easyparser-live adapter. MUST be called only from the guarded
    `run` path, and only AFTER every runner guard has passed (--live,
    SCANNER_LIVE_ALLOWED, binding/fingerprint, finite caps, plan
    consistency, arbitrary-ASIN-option rejection). allow_live is hardcoded
    True here — it can never be set by CLI input. The second external arm
    gate (PROOF_BATCH_LIVE_ARMED=1, read-only in the adapter) is absent by
    default, so this function fails closed BEFORE any client interaction (no
    factory call, no client import) and no provider call is possible while
    the arm gate is unset."""
    import proof_batch_easyparser_adapter as adapter_mod
    if not adapter_mod.proof_batch_armed():
        raise GuardError(
            "easyparser-live adapter is not armed (set %s=1 in the runtime "
            "environment to authorize the guarded live path); adapter remains "
            "disabled by default. No live execution is possible until the arm "
            "gate is explicitly set; no provider call was made."
            % adapter_mod.PROOF_BATCH_LIVE_ARMED_ENV
        )
    if LIVE_CLIENT_FACTORY is not None:
        client = LIVE_CLIENT_FACTORY()
    else:
        client = adapter_mod.real_easyparser_client()
    if not callable(client):
        raise GuardError("armed client must be callable")
    return adapter_mod.EasyparserLiveAdapter(adapter_config={
        "run_id": preflight.get("run_id"),
        "preflight_fingerprint": preflight_fingerprint(preflight),
        "request_budget_remaining": allowed,
        "credit_budget_remaining": max_credits,
        "allow_live": True,
        "client": client,
    })


def _run_run(argv: List[str]) -> int:
    """Live run. Refuses unless every guard passes AND the second external arm
    gate (PROOF_BATCH_LIVE_ARMED=1) is set. Both external gates and the full
    runner guard chain are required; this command always refuses after the
    outer guards when the arm gate is absent."""
    max_requests, max_credits = _require_caps(argv)
    preflight = load_preflight(_preflight_arg(argv))
    errors = validate_preflight_binding(preflight)
    if errors:
        print("binding invalid:")
        for e in errors:
            print("  - " + e)
        return 2
    if "--live" not in argv:
        print("error: refused without explicit --live")
        return 2
    if not live_gate.live_enabled():
        print("error: %s" % live_gate.live_disabled_note())
        return 2
    for opt in ("--asin", "--asins", "--input-file", "--discover"):
        if opt in argv:
            print("error: %s is not supported — the proof batch uses the fixed 20-ASIN preflight binding only" % opt)
            return 2

    allowed = min(max_requests, HARD_PROOF_BATCH_LIMIT, HARD_PROOF_BATCH_LIMIT)
    try:
        adapter = _arm_live_adapter(preflight, allowed, max_credits)
    except GuardError as exc:
        print("error: %s" % exc)
        print("the guarded live run is documented (docs/proof-batch-easyparser-live-adapter-plan.md")
        print("section 11) but NOT EXECUTED in this build.")
        return 2

    outcome = run_guarded(
        preflight=preflight,
        adapter=adapter,
        max_requests=max_requests,
        max_credits=max_credits,
        live=True,
        live_enabled=live_gate.live_enabled(),
        out_dir=os.path.join(RUN_OUTPUT_ROOT, preflight.get("run_id") or "run"),
    )
    print("run: %s" % outcome["status"])
    print("run_id: %s" % outcome["run_id"])
    return 0


def _run_report(argv: List[str]) -> int:
    run_dir = None
    for i, arg in enumerate(argv):
        if arg == "--run-dir" and i + 1 < len(argv):
            run_dir = argv[i + 1]
    if not run_dir:
        raise GuardError("report requires --run-dir <path>")
    report = build_run_report(run_dir)
    written = write_report_files(run_dir, report)
    print("report written:")
    for path in written:
        print("  - %s" % path)
    print("mapping summary:       %s" % json.dumps(report["mapping_summary"]))
    print("outcome summary:       %s" % json.dumps(report["outcome_summary"]))
    print("price drift:           %s" % json.dumps(report["price_drift_summary"]))
    print("purchase statement:    %s" % report.get("purchase_authorization_statement") or PURCHASE_AUTHORIZATION_STATEMENT)
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(argv) if argv is not None else list(sys.argv[1:])
    if not argv:
        print("usage:")
        print("  python proof_batch_run.py dry-run --preflight <p> --max-requests N --max-credits N")
        print("  python proof_batch_run.py fixture-run --preflight <p> --max-requests N --max-credits N --out-dir <dir>")
        print("  python proof_batch_run.py run --live --preflight <p> --max-requests N --max-credits N")
        print("  python proof_batch_run.py report --run-dir <dir>")
        return 2
    command = argv[0]
    try:
        if command == "dry-run":
            return _run_dry_run(argv[1:])
        if command == "fixture-run":
            return _run_fixture_run(argv[1:])
        if command == "run":
            return _run_run(argv[1:])
        if command == "report":
            return _run_report(argv[1:])
        print("unknown command: %s" % command)
        return 2
    except GuardError as exc:
        print("error: %s" % exc)
        return 2
    except BindingError as exc:
        print("error: %s" % exc)
        return 2
    except RunAbort as exc:
        print("abort: %s" % exc)
        return 2
    except OSError as exc:
        print("error: persistence failure: %s" % exc)
        return 3


if __name__ == "__main__":
    # Belt-and-suspenders: running as a script makes this module `__main__`;
    # register it under its real name so any legacy `import proof_batch_run`
    # still resolves to this object. The strict class identity (ProviderAdapter
    # / GuardError / BindingError / RunAbort) now lives in proof_batch_contracts
    # and is shared by both modules regardless of how they are imported, so this
    # alias is no longer the sole identity solution.
    sys.modules.setdefault("proof_batch_run", sys.modules["__main__"])
    sys.exit(main())