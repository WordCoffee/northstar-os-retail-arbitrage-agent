"""Guarded 20-ASIN validation extension for Northstar OS Retail Arbitrage Agent.

This module extends (never replaces) the existing proof-batch guarded-run
architecture. It is additive: it reuses GuardError/BindingError/RunAbort/
ProviderAdapter from proof_batch_contracts, _atomic_write_json + the
fingerprint idiom from proof_batch_run, env_flags.env_flag, live_gate,
and the existing JSON/JSONL persistence conventions.

Design goals (see task spec):
- Read-only reference to the canonical 20-ASIN source; never mutates it.
- New isolated run storage under data/validation-runs/<run-id>/.
- Fail-closed everywhere; no network at import, plan, authorize-check,
  preflight, report-plan, or report time.
- Live submission/retrieval commands verify every gate, then refuse
  before any request is created unless the transport is armed
  (DATAFORSEO_TRANSPORT_ENABLED exactly "true" + configured credentials)
  AND a client is wired in; the wired client is the only thing that ever
  creates a request.
- Manual-review ASINs (B01H40O42I, B08R2SRN88, B00N54AJZE) are never
  auto-approved; they stay manual_review_only / review-only.

No secrets are ever read, printed, logged, or stored. Credential access is
confined to the live transport methods only.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from env_flags import env_flag
from live_gate import live_enabled
import proof_batch_run as pbr
from proof_batch_contracts import (
    GuardError,
    BindingError,
    RunAbort,
    ProviderAdapter,
    DATAFORSEO_ACCEPTED_STATE,
    DATAFORSEO_REJECTION_STATES,
    DEFAULT_LANGUAGE_CODE,
    DEFAULT_LOCATION_CODE,
    evaluate_dataforseo_task_post,
    is_dataforseo_rejection_state,
    merchant_task_get_url,
    merchant_task_post_url,
)
try:
    from dataforseo_adapter import (
        AmbiguousTransportError,
        GuardError as DataForSeoGuardError,
        DataForSEOStandardTransport,
    )
except ImportError:
    # DataForSEO integration is out-of-scope for launch: provider contract
    # mismatch (40402 Invalid Path) unresolved; the adapter's core symbols are
    # absent from source and all backups as of 2026-08-28. Guard the symbols so
    # the rest of validation_run (Costco/other providers) imports cleanly.
    AmbiguousTransportError = None
    DataForSeoGuardError = None
    DataForSEOStandardTransport = None

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

STANDARD_QUEUE = "standard_queue"
PROVIDER_BRIGHTDATA = "BRIGHTDATA"
PROVIDER_DATAFORSEO = "DATAFORSEO"
EXPECTED_VALIDATION_PROVIDERS = [PROVIDER_BRIGHTDATA, PROVIDER_DATAFORSEO]
VALIDATION_TYPES = ("product", "seller_offer")

MANUAL_REVIEW_ASINS = ("B01H40O42I", "B08R2SRN88", "B00N54AJZE")

CONFIG_SCHEMA_VERSION = "dataforseo-config-1"
AUTH_SCHEMA_VERSION = "validation-auth-1"
MANIFEST_SCHEMA_VERSION = "validation-manifest-1"
LEDGER_SCHEMA_VERSION = "validation-ledger-1"
DATAFORSEO_SCHEMA_VERSION = "dataforseo-1"
BRIGHTDATA_SCHEMA_VERSION = "brightdata-1"

DEFAULT_HARD_CAP_CENTS = 100
MAX_ASINS = 20
MAX_TASKS_PER_ASIN = 2
DATAFORSEO_ESTIMATED_COST_CENTS = 5
DATAFORSEO_LOGIN_ENV = "DATAFORSEO_LOGIN"
DATAFORSEO_PASSWORD_ENV = "DATAFORSEO_PASSWORD"

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")

DATAFORSEO_TRANSPORT_ENV = "DATAFORSEO_TRANSPORT_ENABLED"


def _transport_enabled(environ: Optional[Dict[str, str]] = None) -> bool:
    """Strict runtime parse of the transport kill switch (mirrors
    dataforseo_adapter). ONLY the exact normalized value "true" enables;
    everything else (including "1"/"yes"/"false") is disabled. Default off.
    """
    env = environ if environ is not None else os.environ
    raw = (env.get(DATAFORSEO_TRANSPORT_ENV) or "").strip().lower()
    return raw == "true"

_LEDGER_LOCK = threading.RLock()


# ---------------------------------------------------------------------------
# Paths and atomic persistence
# ---------------------------------------------------------------------------

def validation_runs_root() -> str:
    return os.environ.get(
        "VALIDATION_RUNS_ROOT"
    ) or os.path.join(BACKEND_DIR, "data", "validation-runs")


def source_preflight_path() -> str:
    return os.environ.get(
        "VALIDATION_SOURCE_PREFLIGHT"
    ) or os.path.join(
        BACKEND_DIR, "data", "batch", "proof-batch-preflight-20260818T060549Z.json"
    )


def run_dir(run_id: str) -> str:
    return os.path.join(validation_runs_root(), run_id)


def _ensure_run_dirs(run_id: str) -> str:
    base = run_dir(run_id)
    for sub in (
        "",
        "raw/brightdata",
        "raw/dataforseo",
        "normalized/brightdata",
        "normalized/dataforseo",
        "comparisons",
        "reports",
        "logs",
    ):
        os.makedirs(os.path.join(base, sub), exist_ok=True)
    return base


def atomic_write_json(path: str, payload: Any) -> None:
    pbr._atomic_write_json(path, payload)


def read_json(path: str) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _atomic_write_jsonl(path: str, lines: List[str]) -> None:
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(line)
            if not line.endswith("\n"):
                fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_path, path)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# DataForSEO configuration boundary (Phase 1 / C)
# ---------------------------------------------------------------------------

def load_dataforseo_config(environ: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    env = environ if environ is not None else os.environ
    enabled = env_flag_value(env, "DATAFORSEO_ENABLED", default=False)
    mode = (env.get("DATAFORSEO_MODE") or STANDARD_QUEUE).strip().lower()
    cap_raw = env.get("DATAFORSEO_HARD_CAP_CENTS")
    cap = DEFAULT_HARD_CAP_CENTS
    if cap_raw:
        try:
            cap = int(cap_raw)
        except ValueError:
            raise GuardError("DATAFORSEO_HARD_CAP_CENTS must be an integer number of cents")
    cfg = {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "enabled": bool(enabled),
        "mode": mode,
        "hard_cap_cents": cap,
        "login_env": DATAFORSEO_LOGIN_ENV,
        "password_env": DATAFORSEO_PASSWORD_ENV,
    }
    return cfg


def env_flag_value(environ: Dict[str, str], name: str, default: bool = False) -> bool:
    raw = (environ.get(name) or "").strip().lower()
    if not raw:
        return bool(default)
    return raw in frozenset({"1", "true", "yes", "on"})


def validate_dataforseo_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    if not cfg.get("enabled"):
        return cfg
    if cfg.get("mode") != STANDARD_QUEUE:
        raise GuardError("DataForSEO mode must be exactly 'standard_queue'")
    cap = cfg.get("hard_cap_cents")
    if not isinstance(cap, int) or cap < 0:
        raise GuardError("DataForSEO hard cap must be a non-negative integer number of cents")
    return cfg


def dataforseo_credentials_available(environ: Optional[Dict[str, str]] = None) -> bool:
    env = environ if environ is not None else os.environ
    login = env.get(DATAFORSEO_LOGIN_ENV)
    password = env.get(DATAFORSEO_PASSWORD_ENV)
    return bool(login) and bool(password)


def get_dataforseo_credentials() -> Dict[str, str]:
    """Transport-only credential access. Never call outside a live transport."""
    return {
        "login": os.getenv(DATAFORSEO_LOGIN_ENV) or "",
        "password": os.getenv(DATAFORSEO_PASSWORD_ENV) or "",
    }


# ---------------------------------------------------------------------------
# Run manifest (Phase 1 / B)
# ---------------------------------------------------------------------------

def generate_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"data-validation-20asin-{stamp}"


def compute_manifest_fingerprint(manifest: Dict[str, Any]) -> str:
    asins = [a["asin"].upper() for a in manifest.get("asins", [])]
    subset = {
        "run_id": manifest.get("run_id"),
        "asins": sorted(asins),
        "max_asins": manifest.get("max_asins"),
        "max_tasks_per_asin": manifest.get("max_tasks_per_asin"),
        "hard_cap_cents": manifest.get("hard_cap_cents"),
        "mode": manifest.get("mode"),
        "providers": sorted(manifest.get("providers", [])),
    }
    return sha256_text(
        json.dumps(subset, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )


def create_validation_manifest(
    run_id: Optional[str] = None,
    source_path: Optional[str] = None,
    environ: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    run_id = run_id or generate_run_id()
    source_path = source_path or source_preflight_path()
    if not os.path.isfile(source_path):
        raise GuardError(f"source preflight not found: {source_path}")

    with open(source_path, encoding="utf-8") as fh:
        source = json.load(fh)

    try:
        asin_list = pbr.canonical_preflight_asins(source)
    except BindingError as exc:
        raise GuardError(f"source preflight ASIN binding invalid: {exc}")

    source_rows = {r.get("asin", "").upper(): r for r in source.get("selection", {}).get("asins", [])}
    if len(asin_list) != MAX_ASINS:
        raise GuardError(f"source must contain exactly {MAX_ASINS} ASINs; got {len(asin_list)}")

    source_fp = pbr.preflight_fingerprint(source)
    source_sha = sha256_file(source_path)
    cfg = load_dataforseo_config(environ)
    validate_dataforseo_config(cfg)

    asins_out = []
    for asin in asin_list:
        row = source_rows.get(asin, {})
        is_review = asin in MANUAL_REVIEW_ASINS
        asins_out.append({
            "asin": asin,
            "source_rank": row.get("source_rank"),
            "title": row.get("title"),
            "title_conflict": bool(row.get("title_conflict", False)),
            "manual_review_only": is_review,
            "expected_validation_plan": {
                "dataforseo": list(VALIDATION_TYPES),
                "brightdata": ["product"],
            },
            "max_reservation_cents": len(VALIDATION_TYPES) * DATAFORSEO_ESTIMATED_COST_CENTS,
        })

    manifest = {
        "kind": "validation-run-manifest",
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "planned",
        "mode": STANDARD_QUEUE,
        "providers": EXPECTED_VALIDATION_PROVIDERS,
        "max_asins": MAX_ASINS,
        "max_tasks_per_asin": MAX_TASKS_PER_ASIN,
        "hard_cap_cents": DEFAULT_HARD_CAP_CENTS,
        "source_reference": {
            "path": source_path,
            "sha256": source_sha,
            "preflight_fingerprint": source_fp,
            "selected_count": len(asin_list),
        },
        "asins": asins_out,
        "purchase_authorization": None,
        "notes": "References (does not mutate) the canonical 20-ASIN source. "
                 "Manual-review ASINs remain manual_review_only.",
    }
    _ensure_run_dirs(run_id)
    atomic_write_json(os.path.join(run_dir(run_id), "manifest.json"), manifest)
    return manifest


def load_manifest(run_id: str) -> Dict[str, Any]:
    path = os.path.join(run_dir(run_id), "manifest.json")
    if not os.path.isfile(path):
        raise GuardError(f"manifest not found for run_id {run_id}")
    return read_json(path)


# ---------------------------------------------------------------------------
# Authorization gate (Phase 1 / D)
# ---------------------------------------------------------------------------

def create_authorization(
    run_id: str,
    manifest: Dict[str, Any],
    operator_confirmation: str,
    environ: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    if operator_confirmation != run_id:
        raise GuardError("operator confirmation must equal the exact run_id")
    cfg = load_dataforseo_config(environ)
    validate_dataforseo_config(cfg)
    if manifest.get("mode") != STANDARD_QUEUE:
        raise GuardError("manifest mode must be 'standard_queue'")
    if manifest.get("max_asins") != MAX_ASINS:
        raise GuardError("manifest max_asins must be 20")
    if len(manifest.get("asins", [])) != MAX_ASINS:
        raise GuardError("manifest must contain exactly 20 ASINs")
    if set(manifest.get("providers", [])) != set(EXPECTED_VALIDATION_PROVIDERS):
        raise GuardError("manifest provider set mismatch")
    if manifest.get("hard_cap_cents", 0) > DEFAULT_HARD_CAP_CENTS:
        raise GuardError("manifest budget exceeds the $1.00 hard cap")

    mf = compute_manifest_fingerprint(manifest)
    pf = manifest.get("source_reference", {}).get("preflight_fingerprint")
    record = {
        "kind": "validation-authorization",
        "schema_version": AUTH_SCHEMA_VERSION,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "operator_intent": operator_confirmation,
        "providers": EXPECTED_VALIDATION_PROVIDERS,
        "selected_asin_count": len(manifest.get("asins", [])),
        "expected_max_paid_tasks": MAX_ASINS * MAX_TASKS_PER_ASIN,
        "reserved_max_cost_cents": manifest.get("hard_cap_cents"),
        "permitted_queue_mode": STANDARD_QUEUE,
        "run_status": "authorized",
        "manifest_fingerprint": mf,
        "preflight_fingerprint": pf,
        "config_schema_version": CONFIG_SCHEMA_VERSION,
    }
    atomic_write_json(os.path.join(run_dir(run_id), "authorization.json"), record)
    return record


def load_authorization(run_id: str) -> Optional[Dict[str, Any]]:
    path = os.path.join(run_dir(run_id), "authorization.json")
    if not os.path.isfile(path):
        return None
    return read_json(path)


def verify_authorization(
    run_id: str, manifest: Dict[str, Any], ledger: "Ledger"
) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    auth = load_authorization(run_id)
    if auth is None:
        reasons.append("no authorization record for run_id")
        return False, reasons
    if auth.get("run_id") != run_id:
        reasons.append("authorization run_id mismatch")
    mf = compute_manifest_fingerprint(manifest)
    if auth.get("manifest_fingerprint") != mf:
        reasons.append("manifest fingerprint mismatch")
    pf = manifest.get("source_reference", {}).get("preflight_fingerprint")
    if auth.get("preflight_fingerprint") != pf:
        reasons.append("preflight fingerprint mismatch")
    if set(auth.get("providers", [])) != set(EXPECTED_VALIDATION_PROVIDERS):
        reasons.append("provider approval mismatch")
    if auth.get("permitted_queue_mode") != STANDARD_QUEUE:
        reasons.append("queue mode mismatch")
    if auth.get("selected_asin_count") != len(manifest.get("asins", [])):
        reasons.append("asin count mismatch")
    if auth.get("reserved_max_cost_cents", 0) > DEFAULT_HARD_CAP_CENTS:
        reasons.append("budget exceeds cap")
    return (len(reasons) == 0), reasons


# ---------------------------------------------------------------------------
# Durable JSONL ledger with idempotency (Phase 1 / E)
# ---------------------------------------------------------------------------

class Ledger:
    def __init__(self, run_id: str):
        self.run_id = run_id
        self.path = os.path.join(run_dir(run_id), "budget-ledger.jsonl")

    @staticmethod
    def idempotency_key(
        provider: str,
        provider_schema_version: str,
        run_id: str,
        asin: str,
        validation_type: str,
        mode: str,
        payload_fingerprint: str,
    ) -> str:
        parts = "|".join([
            provider, provider_schema_version, run_id,
            asin.upper(), validation_type, mode, payload_fingerprint,
        ])
        return sha256_text(parts)

    def _read(self) -> List[Dict[str, Any]]:
        if not os.path.isfile(self.path):
            return []
        with open(self.path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def _write(self, records: List[Dict[str, Any]]) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        lines = [json.dumps(r, sort_keys=True, ensure_ascii=False) for r in records]
        with _LEDGER_LOCK:
            _atomic_write_jsonl(self.path, lines)

    def add(self, record: Dict[str, Any], dedupe_key: Optional[str] = None) -> Dict[str, Any]:
        key = dedupe_key or record.get("idempotency_key")
        with _LEDGER_LOCK:
            records = self._read()
            if key:
                for existing in records:
                    if existing.get("idempotency_key") == key:
                        return existing
            records.append(record)
            self._write(records)
            return record

    def update(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Replace the stored record carrying the same idempotency_key."""
        key = record.get("idempotency_key")
        if not key:
            raise GuardError("ledger update requires an idempotency_key")
        with _LEDGER_LOCK:
            records = self._read()
            for i, existing in enumerate(records):
                if existing.get("idempotency_key") == key:
                    records[i] = record
                    self._write(records)
                    return record
        raise GuardError(f"ledger record not found for update: {key}")

    def records(self, **filters: Any) -> List[Dict[str, Any]]:
        recs = self._read()
        out = []
        for r in recs:
            ok = True
            for k, v in filters.items():
                if r.get(k) != v:
                    ok = False
                    break
            if ok:
                out.append(r)
        return out

    def total_reserved(self) -> int:
        """Sum of reserved cents for in-flight states.

        Provider-rejected states release their reservation (excluded from the
        tuple), so a rejected task frees its previously reserved budget.
        """
        total = 0
        for r in self._read():
            if r.get("state") in ("planned", "reserved", "submitted", "pending"):
                total += int(r.get("reserved_cost_cents") or 0)
        return total

    def total_actual(self) -> int:
        total = 0
        for r in self._read():
            if r.get("actual_cost_cents") is not None:
                total += int(r.get("actual_cost_cents") or 0)
        return total

    def count_tasks(self, provider: str, asin: str) -> int:
        return len(self.records(provider=provider, asin=asin.upper()))

    def records_with_remote_task_id(self) -> List[Dict[str, Any]]:
        return [r for r in self._read() if r.get("remote_task_id")]


def _planned_payload_fingerprint(asin: str, validation_type: str, mode: str) -> str:
    return sha256_text(f"{asin.upper()}|{validation_type}|{mode}")


def ledger_add_planned(
    run_id: str,
    provider: str,
    asin: str,
    validation_type: str,
    reserved_cost_cents: int,
    schema_version: str,
) -> Dict[str, Any]:
    if validation_type not in VALIDATION_TYPES:
        raise GuardError(f"unsupported validation_type: {validation_type}")
    ledger = Ledger(run_id)
    asin = asin.upper()
    if ledger.count_tasks(provider, asin) >= MAX_TASKS_PER_ASIN:
        raise RunAbort("max_tasks_per_asin", f"plan({asin})", asin,
                       "max two tasks per ASIN")
    if ledger.total_reserved() + reserved_cost_cents > DEFAULT_HARD_CAP_CENTS:
        rec = {
            "local_request_id": f"{run_id}:{provider}:{asin}:{validation_type}:budget_rejected",
            "run_id": run_id,
            "provider": provider,
            "asin": asin,
            "validation_type": validation_type,
            "mode": STANDARD_QUEUE,
            "idempotency_key": Ledger.idempotency_key(
                provider, schema_version, run_id, asin, validation_type,
                STANDARD_QUEUE, "budget_rejected"),
            "payload_fingerprint": "budget_rejected",
            "state": "budget_rejected",
            "reserved_cost_cents": 0,
            "actual_cost_cents": None,
            "remote_task_id": None,
            "error_classification": "budget_overage",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        ledger.add(rec)
        raise RunAbort("budget_cap", f"plan({asin})", asin,
                       "hard $1.00 cap exceeded before submission")
    fp = _planned_payload_fingerprint(asin, validation_type, STANDARD_QUEUE)
    rec = {
        "local_request_id": f"{run_id}:{provider}:{asin}:{validation_type}:{fp[:8]}",
        "run_id": run_id,
        "provider": provider,
        "asin": asin,
        "validation_type": validation_type,
        "mode": STANDARD_QUEUE,
        "idempotency_key": Ledger.idempotency_key(
            provider, schema_version, run_id, asin, validation_type,
            STANDARD_QUEUE, fp),
        "payload_fingerprint": fp,
        "state": "planned",
        "reserved_cost_cents": reserved_cost_cents,
        "actual_cost_cents": None,
        "remote_task_id": None,
        "retrieval_attempt_count": 0,
        "raw_response_reference": None,
        "normalized_response_reference": None,
        "comparison_reference": None,
        "error_classification": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    return ledger.add(rec)


# ---------------------------------------------------------------------------
# Offline planner (Phase 2 / F)
# ---------------------------------------------------------------------------

def plan_run(
    run_id: str,
    manifest: Dict[str, Any],
    cache_lookup: Optional[Any] = None,
) -> Dict[str, Any]:
    ledger = Ledger(run_id)
    per_asin = []
    totals = {
        "asin_count": 0,
        "manual_review_only": 0,
        "cache_hit": 0,
        "retrieve_existing_task": 0,
        "eligible_to_submit": 0,
        "blocked": 0,
        "total_reserved_cents": 0,
    }
    for entry in manifest.get("asins", []):
        asin = entry["asin"].upper()
        totals["asin_count"] += 1
        if asin in MANUAL_REVIEW_ASINS or entry.get("manual_review_only"):
            ledger.add({
                "local_request_id": f"{run_id}:{PROVIDER_DATAFORSEO}:{asin}:review:manual",
                "run_id": run_id,
                "provider": PROVIDER_DATAFORSEO,
                "asin": asin,
                "validation_type": "manual_review",
                "mode": STANDARD_QUEUE,
                "idempotency_key": Ledger.idempotency_key(
                    PROVIDER_DATAFORSEO, DATAFORSEO_SCHEMA_VERSION, run_id, asin,
                    "manual_review", STANDARD_QUEUE, "manual_review"),
                "payload_fingerprint": "manual_review",
                "state": "manual_review_required",
                "reserved_cost_cents": 0,
                "actual_cost_cents": None,
                "remote_task_id": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            totals["manual_review_only"] += 1
            per_asin.append({"asin": asin, "classification": "manual_review_only"})
            continue

        existing = ledger.records(provider=PROVIDER_DATAFORSEO, asin=asin)
        has_remote = any(r.get("remote_task_id") for r in existing)
        if has_remote:
            totals["retrieve_existing_task"] += 1
            per_asin.append({"asin": asin, "classification": "retrieve_existing_task"})
            continue
        if existing:
            totals["eligible_to_submit"] += 1
            totals["total_reserved_cents"] += sum(
                int(r.get("reserved_cost_cents") or 0) for r in existing
            )
            per_asin.append({"asin": asin, "classification": "eligible_to_submit"})
            continue
        if cache_lookup is not None and cache_lookup(asin):
            totals["cache_hit"] += 1
            per_asin.append({"asin": asin, "classification": "cache_hit"})
            continue
        try:
            for vt in VALIDATION_TYPES:
                ledger_add_planned(
                    run_id, PROVIDER_DATAFORSEO, asin, vt,
                    DATAFORSEO_ESTIMATED_COST_CENTS, DATAFORSEO_SCHEMA_VERSION)
            totals["eligible_to_submit"] += 1
            totals["total_reserved_cents"] += 2 * DATAFORSEO_ESTIMATED_COST_CENTS
            per_asin.append({"asin": asin, "classification": "eligible_to_submit"})
        except RunAbort:
            totals["blocked"] += 1
            per_asin.append({"asin": asin, "classification": "blocked"})

    plan = {
        "kind": "validation-preflight-plan",
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": STANDARD_QUEUE,
        "hard_cap_cents": manifest.get("hard_cap_cents"),
        "reserved_max_cost_cents": totals["total_reserved_cents"],
        "within_budget": totals["total_reserved_cents"] <= manifest.get("hard_cap_cents", 0),
        "totals": totals,
        "per_asin": per_asin,
    }
    atomic_write_json(os.path.join(run_dir(run_id), "preflight-plan.json"), plan)
    _write_redacted_plan_report(run_id, plan)
    return plan


def _write_redacted_plan_report(run_id: str, plan: Dict[str, Any]) -> None:
    path = os.path.join(run_dir(run_id), "reports", "plan-report.md")
    lines = [
        "# Validation Preflight Plan",
        "",
        f"run_id: {run_id}",
        f"mode: {plan.get('mode')}",
        f"hard_cap_cents: {plan.get('hard_cap_cents')}",
        f"reserved_max_cost_cents: {plan.get('reserved_max_cost_cents')}",
        f"within_budget: {plan.get('within_budget')}",
        "",
        "## Totals",
        "",
    ]
    totals = plan.get("totals", {})
    for k, v in totals.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Per-ASIN (redacted; no provider data)")
    lines.append("")
    for row in plan.get("per_asin", []):
        lines.append(f"- {row['asin']}: {row['classification']}")
    lines.append("")
    atomic_write_json  # keep linter calm; write markdown via tmp
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    os.replace(tmp, path)


def load_plan(run_id: str) -> Dict[str, Any]:
    path = os.path.join(run_dir(run_id), "preflight-plan.json")
    if not os.path.isfile(path):
        raise GuardError(f"plan not found for run_id {run_id}")
    return read_json(path)


# ---------------------------------------------------------------------------
# Raw / normalized evidence + comparison (Phase 3 / G)
# ---------------------------------------------------------------------------

def store_raw(run_id: str, provider: str, asin: str, payload: Dict[str, Any]) -> str:
    asin = asin.upper()
    sub = "dataforseo" if provider == PROVIDER_DATAFORSEO else "brightdata"
    base = os.path.join(run_dir(run_id), "raw", sub)
    os.makedirs(base, exist_ok=True)
    name = f"{asin}.json"
    path = os.path.join(base, name)
    if os.path.isfile(path):
        return path
    payload_hash = sha256_text(json.dumps(payload, sort_keys=True, ensure_ascii=False))
    wrapped = {
        "provider": provider,
        "asin": asin,
        "stored_at": datetime.now(timezone.utc).isoformat(),
        "payload_hash": payload_hash,
        "payload": payload,
    }
    atomic_write_json(path, wrapped)
    return path


def normalize_provider_record(
    provider: str,
    raw: Dict[str, Any],
    retrieval_ts: Optional[str] = None,
    schema_version: Optional[str] = None,
    raw_reference: Optional[str] = None,
) -> Dict[str, Any]:
    expected = ["asin", "title", "brand", "product_count", "pack_count",
                "size", "variation", "observed_price", "seller_signals"]
    norm: Dict[str, Any] = {k: raw.get(k) for k in expected}
    norm["provider"] = provider
    norm["retrieval_timestamp"] = retrieval_ts
    norm["schema_version"] = schema_version or (
        DATAFORSEO_SCHEMA_VERSION if provider == PROVIDER_DATAFORSEO
        else BRIGHTDATA_SCHEMA_VERSION)
    norm["raw_reference"] = raw_reference
    norm["coverage"] = [k for k in expected if raw.get(k) is not None]
    norm["data_gaps"] = [k for k in expected if raw.get(k) is None]
    return norm


def store_normalized(run_id: str, provider: str, asin: str, record: Dict[str, Any]) -> str:
    asin = asin.upper()
    sub = "dataforseo" if provider == PROVIDER_DATAFORSEO else "brightdata"
    base = os.path.join(run_dir(run_id), "normalized", sub)
    os.makedirs(base, exist_ok=True)
    name = f"{asin}.json"
    path = os.path.join(base, name)
    if os.path.isfile(path):
        return path
    atomic_write_json(path, record)
    return path


def compare_providers(
    brightdata_norm: Dict[str, Any],
    dataforseo_norm: Dict[str, Any],
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    asin = dataforseo_norm.get("asin") or brightdata_norm.get("asin") or ""
    asin = asin.upper()
    if asin in MANUAL_REVIEW_ASINS:
        classification = "manual_review_required"
    elif not brightdata_norm or not dataforseo_norm:
        classification = "insufficient_source_coverage"
    elif brightdata_norm.get("asin") != dataforseo_norm.get("asin"):
        classification = "identity_conflict"
    else:
        bd_title = (brightdata_norm.get("title") or "").strip().lower()
        df_title = (dataforseo_norm.get("title") or "").strip().lower()
        bd_pack = brightdata_norm.get("pack_count")
        df_pack = dataforseo_norm.get("pack_count")
        title_match = bool(bd_title) and bool(df_title) and bd_title == df_title
        pack_conflict = (
            bd_pack is not None and df_pack is not None and bd_pack != df_pack)
        if pack_conflict:
            classification = "identity_conflict"
        elif not bd_title or not df_title:
            classification = "identity_possible_but_incomplete"
        elif title_match:
            classification = "identity_match"
        else:
            classification = "identity_conflict"

    result = {
        "kind": "validation-comparison",
        "asin": asin,
        "classification": classification,
        "brightdata_reference": brightdata_norm.get("raw_reference"),
        "dataforseo_reference": dataforseo_norm.get("raw_reference"),
        "purchase_recommendation": None,
        "operational_clearance": None,
    }
    if run_id:
        base = os.path.join(run_dir(run_id), "comparisons")
        os.makedirs(base, exist_ok=True)
        atomic_write_json(os.path.join(base, f"{asin}.json"), result)
    return result


# ---------------------------------------------------------------------------
# Live-ready transport interfaces (Phase 4) -- fail-closed until armed
# ---------------------------------------------------------------------------

class DataForSEOTransport(ProviderAdapter):
    """Narrow, dependency-injected transport. Construction makes zero calls.

    Credentials are accessed only inside submit/retrieve, and only when
    this process arms the transport: allow_live=True AND
    DATAFORSEO_TRANSPORT_ENABLED exactly "true" AND configured credentials
    AND a wired client. The wired client is the ONLY thing that can create
    a request; without it this class always refuses pre-network.
    """

    def __init__(self, client=None, allow_live: bool = False):
        self._client = client
        self._allow_live = bool(allow_live)

    def _credentials(self) -> Dict[str, str]:
        return get_dataforseo_credentials()

    def _armed_client(self) -> Any:
        if not self._allow_live or not _transport_enabled():
            raise GuardError("DataForSEO live transport is not enabled; no request created")
        creds = self._credentials()
        if not creds.get("login") or not creds.get("password"):
            raise GuardError("DataForSEO credentials are not configured; no request created")
        client = self._client
        if client is None or not callable(getattr(client, "submit", None)) \
                or not callable(getattr(client, "retrieve", None)):
            raise GuardError("DataForSEO live transport has no client wired; no request created")
        return client

    def submit(self, asin: str, validation_type: str, mode: str,
               keyword: Optional[str] = None) -> Dict[str, Any]:
        return self._armed_client().submit(asin, validation_type, mode, keyword=keyword)

    def retrieve(self, remote_task_id: str,
                 validation_type: str = "product") -> Dict[str, Any]:
        return self._armed_client().retrieve(remote_task_id, validation_type)

    def fetch(self, asin: str, request_index: int) -> dict:
        raise NotImplementedError


class BrightDataValidationInterface:
    """Thin dependency-injected wrapper around existing bright_data_client.

    Importing/wiring this class makes zero calls. It only delegates to the
    wired client when an explicit, authorized transport call is made;
    without a wired client it always refuses pre-network.
    """

    def __init__(self, client=None, allow_live: bool = False):
        self._client = client
        self._allow_live = bool(allow_live)

    def submit(self, asin: str, validation_type: str, mode: str) -> Dict[str, Any]:
        if not self._allow_live:
            raise GuardError("Bright Data validation transport is not enabled; no request created")
        client = self._client
        if client is None or not callable(getattr(client, "submit", None)):
            raise GuardError("Bright Data validation transport has no client wired; no request created")
        return client.submit(asin, validation_type, mode)

    def fetch(self, asin: str, request_index: int) -> dict:
        raise NotImplementedError


def _dataforseo_standard_client() -> Any:
    """Lazily-resolved real client (pattern mirrors
    proof_batch_easyparser_adapter.real_easyparser_client). Wraps the armed
    DataForSEOStandardTransport; construction makes zero calls and the
    transport itself stays fail-closed until armed.

    Only the Merchant products family is exercised by this run (keyword-
    driven listings evidence). The keyword is sourced offline from the
    candidate's benchmark title and passed in at submit time; it is never
    a marketplace search and never fabricated.
    """
    if DataForSEOStandardTransport is None:
        raise RuntimeError(
            "DataForSEO integration disabled (out-of-scope for launch); "
            "provider contract mismatch (40402 Invalid Path) unresolved.")
    class _StandardClient:
        DATAFORSEO_API_BASE = "https://api.dataforseo.com"

        def __init__(self):
            self._tr = DataForSEOStandardTransport(allow_live=True)

        def submit(self, asin: str, validation_type: str, mode: str,
                   keyword: Optional[str] = None) -> Dict[str, Any]:
            if validation_type not in ("product", "asin", "sellers"):
                raise GuardError(
                    f"validation_type not supported by the DataForSEO transport: "
                    f"{validation_type}")
            if validation_type == "product":
                family = "products"
            else:
                family = validation_type  # "asin" | "sellers"
            url = merchant_task_post_url(family)
            if family == "products":
                if not keyword or not str(keyword).strip():
                    raise GuardError(
                        "product task requires a keyword sourced from the candidate's "
                        "benchmark title; none provided")
                payload = [{
                    "keyword": str(keyword).strip()[:80],
                    "language_code": DEFAULT_LANGUAGE_CODE,
                    "location_code": DEFAULT_LOCATION_CODE,
                }]
            else:
                payload = [{
                    "asin": str(asin).strip().upper(),
                    "language_code": DEFAULT_LANGUAGE_CODE,
                    "location_code": DEFAULT_LOCATION_CODE,
                }]
            return self._tr.submit(url, payload)

        def retrieve(self, remote_task_id: str,
                     validation_type: str = "product") -> Dict[str, Any]:
            if validation_type not in ("product", "asin", "sellers"):
                raise GuardError(
                    f"validation_type not supported by the DataForSEO transport: "
                    f"{validation_type}")
            family = "products" if validation_type == "product" else validation_type
            url = merchant_task_get_url(family, remote_task_id)
            return self._tr.retrieve(url)

    return _StandardClient()


def _first_result_item(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """First result item of a task_get response (Standard queue)."""
    tasks = payload.get("tasks") if isinstance(payload, dict) else None
    if not isinstance(tasks, list) or not tasks:
        return None
    first = tasks[0]
    if not isinstance(first, dict):
        return None
    if first.get("status_code") not in (None, 20000):
        return None
    result = first.get("result")
    if not isinstance(result, list) or not result:
        return None
    item = result[0]
    return item if isinstance(item, dict) else None


def _observed_from_dataforseo(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map one DataForSEO result item to the validation-run observed
    vocabulary. Only explicitly-returned fields are mapped; unknown fields
    stay None and are never inferred."""
    if not isinstance(raw, dict):
        return {}
    price = raw.get("price")
    price_value = None
    if isinstance(price, dict):
        candidate = price.get("value")
        if isinstance(candidate, (int, float)) and not isinstance(candidate, bool):
            price_value = float(candidate)
    elif isinstance(price, (int, float)) and not isinstance(price, bool):
        price_value = float(price)
    return {
        "asin": raw.get("asin"),
        "title": raw.get("title"),
        "brand": raw.get("brand"),
        "product_count": raw.get("product_count"),
        "pack_count": raw.get("pack_count"),
        "size": raw.get("size"),
        "variation": raw.get("variation"),
        "observed_price": price_value,
        "seller_signals": raw.get("seller_offer_count"),
    }


# ---------------------------------------------------------------------------
# CLI (Phase 2 / 4)
# ---------------------------------------------------------------------------

def _arg(argv: List[str], name: str) -> Optional[str]:
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def _require_run_id(argv: List[str]) -> str:
    run_id = _arg(argv, "--run")
    if not run_id:
        raise GuardError("missing required --run <run_id>")
    return run_id


def _require_confirm(argv: List[str], run_id: str) -> str:
    confirm = _arg(argv, "--confirm")
    if confirm is None:
        raise GuardError("missing required --confirm <run_id>")
    if confirm != run_id:
        raise GuardError("confirm value must equal the exact run_id")
    return confirm


def cmd_preflight(argv: List[str]) -> int:
    run_id = _require_run_id(argv)
    source = _arg(argv, "--source") or source_preflight_path()
    try:
        manifest = load_manifest(run_id)
        if manifest.get("run_id") != run_id:
            raise GuardError("run_id mismatch in existing manifest")
    except GuardError:
        manifest = create_validation_manifest(run_id=run_id, source_path=source)
    plan = plan_run(run_id, manifest)
    print(f"preflight complete: {run_id}")
    print(f"  asins: {plan['totals']['asin_count']}")
    print(f"  manual_review_only: {plan['totals']['manual_review_only']}")
    print(f"  eligible_to_submit: {plan['totals']['eligible_to_submit']}")
    print(f"  retrieve_existing_task: {plan['totals']['retrieve_existing_task']}")
    print(f"  cache_hit: {plan['totals']['cache_hit']}")
    print(f"  blocked: {plan['totals']['blocked']}")
    print(f"  reserved_max_cost_cents: {plan['reserved_max_cost_cents']}")
    print(f"  within_budget: {plan['within_budget']}")
    return 0


def cmd_report_plan(argv: List[str]) -> int:
    run_id = _require_run_id(argv)
    plan = load_plan(run_id)
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


def cmd_authorize_check(argv: List[str]) -> int:
    run_id = _require_run_id(argv)
    confirm = _arg(argv, "--confirm")
    manifest = load_manifest(run_id)
    if confirm is not None:
        if confirm != run_id:
            raise GuardError("confirm value must equal the exact run_id")
        try:
            create_authorization(run_id, manifest, confirm)
        except GuardError as exc:
            print(f"authorization NOT created: {exc}")
            return 2
        print("authorization record created")
        return 0
    ledger = Ledger(run_id)
    ok, reasons = verify_authorization(run_id, manifest, ledger)
    if ok:
        print("authorization valid")
    else:
        print("authorization invalid. reasons:")
        for r in reasons:
            print(f"  - {r}")
    return 0


def cmd_execute_dataforseo(argv: List[str]) -> int:
    if DataForSEOStandardTransport is None or DataForSeoGuardError is None:
        raise RuntimeError(
            "DataForSEO integration disabled (out-of-scope for launch); "
            "provider contract mismatch (40402 Invalid Path) unresolved.")
    run_id = _require_run_id(argv)
    _require_confirm(argv, run_id)
    manifest = load_manifest(run_id)
    ledger = Ledger(run_id)
    ok, reasons = verify_authorization(run_id, manifest, ledger)
    if not ok:
        raise GuardError("authorization invalid: " + "; ".join(reasons))
    if not live_enabled():
        raise GuardError("live providers are disabled")

    # Asin -> benchmark title (sourced offline) for the keyword-driven
    # products task. Never a marketplace search; never fabricated.
    titles_by_asin = {str(r.get("asin", "")).upper(): r.get("title")
                      for r in manifest.get("asins", [])}

    transport = DataForSEOTransport(
        client=_dataforseo_standard_client(), allow_live=True)
    planned = ledger.records(provider=PROVIDER_DATAFORSEO, state="planned")
    submitted = 0
    skipped = 0
    for rec in planned:
        asin = str(rec.get("asin", "")).upper()
        validation_type = rec.get("validation_type") or "product"
        if rec.get("remote_task_id"):
            skipped += 1
            continue
        keyword = titles_by_asin.get(asin)
        try:
            response = transport.submit(asin, validation_type, STANDARD_QUEUE,
                                        keyword=keyword)
        except (GuardError, DataForSeoGuardError) as exc:
            if validation_type == "seller_offer":
                # Not provisioned on the DataForSEO transport; recorded as
                # unsupported, never submitted.
                rec = _mark_ledger_state(ledger, rec, "mapping_incompatible",
                                         str(exc))
                print(f"  {asin} {validation_type}: not provisioned ({exc})")
                skipped += 1
                continue
            print(f"  {asin} {validation_type}: refused ({exc})")
            skipped += 1
            continue
        except AmbiguousTransportError as exc:
            print(f"  {asin} {validation_type}: ambiguous, manual reconciliation required ({exc})")
            skipped += 1
            continue
        raw_ref = store_raw(run_id, PROVIDER_DATAFORSEO, asin, response)
        rec = dict(rec)
        family = "products" if validation_type == "product" else validation_type
        verdict = evaluate_dataforseo_task_post(response, endpoint_family=family)
        if not verdict["accepted"]:
            rec["state"] = verdict["classification"]
            rec["remote_task_id"] = None
            rec["actual_cost_cents"] = verdict["provider_cost_cents"]
            rec["error_classification"] = verdict["reason"]
            rec["raw_response_reference"] = raw_ref
            rec["updated_at"] = datetime.now(timezone.utc).isoformat()
            ledger.update(rec)
            print(
                f"  {asin} {validation_type}: provider rejected "
                f"({verdict['classification']}: {verdict['reason']})")
            skipped += 1
            continue
        rec["state"] = DATAFORSEO_ACCEPTED_STATE
        rec["remote_task_id"] = verdict["task_id"]
        rec["actual_cost_cents"] = verdict["provider_cost_cents"]
        rec["error_classification"] = None
        rec["raw_response_reference"] = raw_ref
        rec["updated_at"] = datetime.now(timezone.utc).isoformat()
        ledger.update(rec)
        submitted += 1
    print(f"execute complete: {run_id}")
    print(f"  submitted: {submitted}")
    print(f"  skipped/unsupported: {skipped}")
    print(f"  pending_planned: {len(ledger.records(provider=PROVIDER_DATAFORSEO, state='planned'))}")
    return 0


def _mark_ledger_state(ledger, rec, state, failure_reason=None) -> Dict[str, Any]:
    rec = dict(rec)
    rec["state"] = state
    if failure_reason is not None:
        rec["error_classification"] = failure_reason
    rec["updated_at"] = datetime.now(timezone.utc).isoformat()
    ledger.update(rec)
    return rec


def cmd_retrieve_dataforseo(argv: List[str]) -> int:
    if DataForSEOStandardTransport is None or DataForSeoGuardError is None:
        raise RuntimeError(
            "DataForSEO integration disabled (out-of-scope for launch); "
            "provider contract mismatch (40402 Invalid Path) unresolved.")
    run_id = _require_run_id(argv)
    manifest = load_manifest(run_id)
    ledger = Ledger(run_id)
    ok, reasons = verify_authorization(run_id, manifest, ledger)
    if not ok:
        raise GuardError("authorization invalid: " + "; ".join(reasons))
    if not live_enabled():
        raise GuardError("live providers are disabled")
    transport = DataForSEOTransport(client=_dataforseo_standard_client(), allow_live=True)
    tasks = ledger.records(provider=PROVIDER_DATAFORSEO, state="submitted")
    if not tasks:
        print("no submitted tasks; nothing to retrieve")
        return 0
    retrieved = 0
    failed = 0
    for rec in tasks:
        remote_task_id = rec.get("remote_task_id")
        asin = str(rec.get("asin", "")).upper()
        if not remote_task_id:
            failed += 1
            continue
        try:
            response = transport.retrieve(remote_task_id)
        except (GuardError, DataForSeoGuardError) as exc:
            print(f"  {asin}: retrieval refused ({exc})")
            failed += 1
            continue
        except AmbiguousTransportError as exc:
            print(f"  {asin}: ambiguous, manual reconciliation required ({exc})")
            failed += 1
            continue
        raw_ref = store_raw(run_id, PROVIDER_DATAFORSEO, asin, response)
        norm = normalize_provider_record(
            PROVIDER_DATAFORSEO,
            _observed_from_dataforseo(_first_result_item(response) or {}),
            retrieval_ts=datetime.now(timezone.utc).isoformat(),
            raw_reference=raw_ref)
        norm_ref = store_normalized(run_id, PROVIDER_DATAFORSEO, asin, norm)
        rec = dict(rec)
        rec["state"] = "retrieved"
        rec["raw_response_reference"] = raw_ref
        rec["normalized_response_reference"] = norm_ref
        rec["updated_at"] = datetime.now(timezone.utc).isoformat()
        ledger.update(rec)
        retrieved += 1
    print(f"retrieve complete: {run_id}")
    print(f"  retrieved: {retrieved}")
    print(f"  failed: {failed}")
    return 0


def cmd_repair_dataforseo(argv: List[str]) -> int:
    """OFFLINE repair of false-submitted DataForSEO rows (zero provider calls).

    Reclassifies ledger rows currently in state=submitted by re-evaluating
    their stored raw envelopes under the strict task-post acceptance
    predicate. Rejected rows: state set to the rejection classification,
    remote_task_id cleared, actual_cost_cents set from the provider-reported
    cost (0 here), error_classification set, reservation released. Raw
    evidence artifacts are preserved; only the ledger rows change.
    Writes a before/after repair manifest under reports/.
    """
    run_id = _require_run_id(argv)
    if not os.path.isdir(run_dir(run_id)):
        raise GuardError(f"run directory not found: {run_id}")
    ledger = Ledger(run_id)
    submitted = ledger.records(provider=PROVIDER_DATAFORSEO, state="submitted")
    before = _ledger_state_counts(ledger)
    reserved_before = ledger.total_reserved()
    actual_before = _actual_cost_sum(ledger)
    processed = 0
    repaired = 0
    unchanged = 0
    missing_envelope = 0
    for rec in submitted:
        asin = str(rec.get("asin", "")).upper()
        envelope_path = os.path.join(run_dir(run_id), "raw", "dataforseo", f"{asin}.json")
        processed += 1
        if not os.path.isfile(envelope_path):
            missing_envelope += 1
            continue
        envelope = read_json(envelope_path)
        verdict = evaluate_dataforseo_task_post(envelope.get("payload"))
        if verdict["accepted"]:
            unchanged += 1
            continue
        rec = dict(rec)
        rec["state"] = verdict["classification"]
        rec["remote_task_id"] = None
        rec["actual_cost_cents"] = verdict["provider_cost_cents"]
        rec["error_classification"] = verdict["reason"]
        rec["raw_response_reference"] = envelope_path
        rec["updated_at"] = datetime.now(timezone.utc).isoformat()
        ledger.update(rec)
        repaired += 1
    after = _ledger_state_counts(ledger)
    manifest = {
        "kind": "dataforseo-submission-repair",
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "offline_only": True,
        "provider_calls_made": 0,
        "rows_processed": processed,
        "rows_repaired": repaired,
        "rows_unchanged": unchanged,
        "rows_missing_envelope": missing_envelope,
        "before": before,
        "after": after,
        "reserved_cents_before": reserved_before,
        "reserved_cents_after": ledger.total_reserved(),
        "actual_cost_cents_before": actual_before,
        "actual_cost_cents_after": _actual_cost_sum(ledger),
    }
    reports_dir = os.path.join(run_dir(run_id), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    manifest_path = os.path.join(reports_dir, f"repair-manifest-{ts}.json")
    atomic_write_json(manifest_path, manifest)
    print(f"repair complete: {run_id}")
    print(f"  processed: {processed}")
    print(f"  repaired: {repaired}")
    print(f"  unchanged: {unchanged}")
    print(f"  missing_envelope: {missing_envelope}")
    print(f"  manifest: {manifest_path}")
    return 0


def _ledger_state_counts(ledger: "Ledger") -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for r in ledger.records():
        state = r.get("state") or "unknown"
        counts[state] = counts.get(state, 0) + 1
    return counts


def _reserved_cents(ledger: "Ledger") -> int:
    total = 0
    for r in ledger.records():
        if r.get("state") in ("planned", "reserved", "submitted", "pending"):
            total += int(r.get("reserved_cost_cents") or 0)
    return total


def _actual_cost_sum(ledger: "Ledger") -> int:
    total = 0
    for r in ledger.records():
        if r.get("actual_cost_cents") is not None:
            total += int(r.get("actual_cost_cents") or 0)
    return total


def cmd_report(argv: List[str]) -> int:
    run_id = _require_run_id(argv)
    manifest = load_manifest(run_id)
    ledger = Ledger(run_id)
    auth = load_authorization(run_id)
    plan = None
    try:
        plan = load_plan(run_id)
    except GuardError:
        plan = None
    print(f"run_id: {run_id}")
    print(f"status: {manifest.get('status')}")
    print(f"asin_count: {len(manifest.get('asins', []))}")
    print(f"authorization_present: {auth is not None}")
    print(f"ledger_entries: {len(ledger.records())}")
    print(f"ledger_reserved_cents: {ledger.total_reserved()}")
    if plan:
        print(f"plan_eligible_to_submit: {plan['totals']['eligible_to_submit']}")
        print(f"plan_manual_review_only: {plan['totals']['manual_review_only']}")
        print(f"plan_within_budget: {plan['within_budget']}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(argv) if argv is not None else list(sys.argv[1:])
    if not argv:
        print("usage:")
        print("  python validation_run.py preflight --run <id> [--source <path>]")
        print("  python validation_run.py report-plan --run <id>")
        print("  python validation_run.py authorize-check --run <id> [--confirm <id>]")
        print("  python validation_run.py execute-dataforseo --run <id> --confirm <id>")
        print("  python validation_run.py retrieve-dataforseo --run <id> [--confirm <id>]")
        print("  python validation_run.py repair-dataforseo --run <id>")
        print("  python validation_run.py report --run <id>")
        return 2
    cmd = argv[0]
    try:
        if cmd == "preflight":
            return cmd_preflight(argv[1:])
        if cmd == "report-plan":
            return cmd_report_plan(argv[1:])
        if cmd == "authorize-check":
            return cmd_authorize_check(argv[1:])
        if cmd == "execute-dataforseo":
            return cmd_execute_dataforseo(argv[1:])
        if cmd == "retrieve-dataforseo":
            return cmd_retrieve_dataforseo(argv[1:])
        if cmd == "repair-dataforseo":
            return cmd_repair_dataforseo(argv[1:])
        if cmd == "report":
            return cmd_report(argv[1:])
        print(f"unknown command: {cmd}")
        return 2
    except GuardError as exc:
        print(f"error: {exc}")
        return 2
    except BindingError as exc:
        print(f"error: {exc}")
        return 2
    except RunAbort as exc:
        print(f"abort: {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
