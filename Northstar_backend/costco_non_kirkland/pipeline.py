"""Costco Non-Kirkland research pipeline orchestration.

OFFLINE-FIRST. Stages:

  A. Import: local Costco data -> normalize -> exclude Kirkland + disallowed
     product classes -> candidate pool.
  B. Match: offline Amazon match queue (UPC/MPN/title+pack, manual for title-only).
  C. Preliminary Golden Goose score (eligible + matched only).
  D. Optional authorized enrichment: manifest -> dry-run preflight -> explicit
     approval -> sign-in gate -> item cap -> spend cap -> provider export/API
     ingestion -> snapshot -> re-score -> human review queue.

Amazon-market information comes ONLY from approved SellerAmp snapshots or
approved exports. This pipeline NEVER opens Amazon product pages or
scrapes Amazon search/offer pages (see amazon_guard).

No provider action may occur in a GET route, UI load, search, view, or automatic job.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .enums import RecommendationStatus, PURCHASE_AUTHORIZATION_NOT_AUTHORIZED
from .kirkland_exclusion import audit_exclusion, evaluate_exclusion
from .disallowed import audit_disallowed, evaluate_disallowed
from .signin import require_signin, mark_signed_in
from .amazon_guard import assert_no_amazon_direct_scan
from .normalize import (
    apply_exclusion,
    load_csv_records,
    load_discovery_catalog,
    load_json_records,
    normalize_costco_record,
)
from .sources import discover_summary, discover_costco_sources
from .store import PipelineStore
from .matching import AmazonAttributes, build_match_candidate
from .economics import compute_economics
from .scoring import score_golden_goose
from .providers import provider_factory, ProviderRetired

OFFLINE_ONLY = True
ENRICHMENT_APPROVAL_ENV = "NORTHSTAR_ENRICHMENT_APPROVED"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ImportResult:
    run_id: str
    discovered: int = 0
    normalized: int = 0
    excluded_kirkland: int = 0
    excluded_disallowed: int = 0
    eligible: int = 0
    missing_brand: int = 0
    manual_review_required: int = 0
    by_reason_code: Dict[str, int] = field(default_factory=dict)
    by_disallowed_class: Dict[str, int] = field(default_factory=dict)
    dry_run: bool = False
    source_summary: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id, "discovered": self.discovered, "normalized": self.normalized,
            "excluded_kirkland": self.excluded_kirkland, "excluded_disallowed": self.excluded_disallowed,
            "eligible": self.eligible, "missing_brand": self.missing_brand,
            "manual_review_required": self.manual_review_required,
            "by_reason_code": dict(self.by_reason_code),
            "by_disallowed_class": dict(self.by_disallowed_class),
            "dry_run": self.dry_run, "source_summary": self.source_summary,
        }


def discover_sources(data_dir: Optional[str] = None, backend_dir: Optional[str] = None) -> Dict[str, Any]:
    """Discover local Costco sources (offline)."""
    return discover_summary(data_dir=data_dir, backend_dir=backend_dir)


def load_local_records(source_name: Optional[str] = None,
                       data_dir: Optional[str] = None,
                       backend_dir: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load raw local Costco records from the discovered sources."""
    sources = discover_costco_sources(data_dir=data_dir, backend_dir=backend_dir)
    raw: List[Dict[str, Any]] = []
    for s in sources:
        if not s.exists:
            continue
        if source_name and s.source_name != source_name:
            continue
        try:
            if s.kind == "csv":
                rows = load_csv_records(s.path)
            elif s.kind == "json-catalog":
                rows = load_discovery_catalog(s.path)
            else:
                rows = load_json_records(s.path)
            for r in rows:
                if isinstance(r, dict):
                    r["__source_file"] = s.path
                    r["__source_name"] = s.source_name
                    raw.append(r)
        except Exception:
            continue
    return raw


def import_costco_local(run_name: Optional[str] = None, *, source_name: Optional[str] = None,
                        data_dir: Optional[str] = None, backend_dir: Optional[str] = None,
                        dry_run: bool = False, store: Optional[PipelineStore] = None,
                        prompt_signin: bool = False) -> ImportResult:
    """A. Import: normalize + exclude Kirkland + disallowed classes -> candidate pool.

    Marks (never deletes) excluded records and stores them with an
    `exclusion_reason` (kirkland_signature_out_of_scope or disallowed_product_class).

    When `prompt_signin=True`, requires the Costco sign-in gate to be confirmed
    (this is a local-file import, so sign-in is informational; the import still
    proceeds because no live Costco access is used — the prompt is surfaced for
    the operator's awareness of the Costco source).
    """
    store = store or PipelineStore()
    if dry_run:
        # Fully read-only: no run record, no writes.
        run_id = "dry-run"
    else:
        run = store.create_run(run_name or "Costco Non-Kirkland Import", command="import_costco_local")
        run_id = run["run_id"]
    source_summary = discover_summary(data_dir=data_dir, backend_dir=backend_dir)

    signin_prompt = None
    if prompt_signin:
        signin_prompt = require_signin("costco", store=store).to_dict()

    raw_records = load_local_records(source_name=source_name, data_dir=data_dir, backend_dir=backend_dir)
    result = ImportResult(run_id=run_id, dry_run=dry_run, source_summary=source_summary)
    result.discovered = len(raw_records)

    normalized_list: List[Dict[str, Any]] = []
    for raw in raw_records:
        source_file = raw.pop("__source_file", None)
        src_name = raw.pop("__source_name", None)
        norm = normalize_costco_record(raw, source_file=source_file, evidence_class="cached_source_snapshot")
        # 1) Kirkland exclusion (primary reason; never overwritten)
        marked = apply_exclusion(norm)
        was_kirkland = marked.get("exclusion_reason") == "kirkland_signature_out_of_scope"
        # 2) Disallowed product-class exclusion (secondary; stored in
        #    disallowed_classes). Kirkland reason takes precedence.
        dis = evaluate_disallowed(marked)
        marked = dis.to_record(marked)
        if was_kirkland:
            # Kirkland is the out-of-scope reason of record; disallowed classes
            # remain captured in disallowed_classes but do not replace it.
            marked["exclusion_reason"] = "kirkland_signature_out_of_scope"
        elif dis.excluded:
            marked["exclusion_reason"] = "disallowed_product_class"
        result.normalized += 1
        if marked.get("manual_review_required"):
            result.manual_review_required += 1
        if was_kirkland:
            result.excluded_kirkland += 1
        elif marked.get("exclusion_reason") == "disallowed_product_class":
            result.excluded_disallowed += 1
        if marked.get("eligible_for_costco_non_kirkland_workflow"):
            result.eligible += 1
        if marked.get("brand_normalized") is None:
            result.missing_brand += 1
        if not dry_run:
            store.upsert_source_product(marked, run_id=run_id)

    audit = audit_exclusion([normalize_costco_record(r, source_file=None) for r in raw_records])
    result.by_reason_code = dict(audit.by_reason_code)
    dis_audit = audit_disallowed([normalize_costco_record(r, source_file=None) for r in raw_records])
    result.by_disallowed_class = dict(dis_audit.by_class)
    if signin_prompt:
        result.by_reason_code["signin_prompt"] = signin_prompt
    if not dry_run:
        store.update_run(run_id, status="completed",
                         counts_json=__import__("json").dumps(result.to_dict(), default=str))
    return result


def build_match_queue(run_id: Optional[str] = None, *, dry_run: bool = False,
                      store: Optional[PipelineStore] = None,
                      amazon_candidates: Optional[Dict[str, List[AmazonAttributes]]] = None) -> Dict[str, Any]:
    """B. Offline Amazon match queue.

    `amazon_candidates` maps costco_source_product_id -> list[AmazonAttributes].
    When None, only the existing ASIN ledger (`data/costco-amazon-mapping.json`)
    is used for costco->asin hints (offline). Provider lookups are never automatic.
    """
    store = store or PipelineStore()
    eligible = store.list_source_products(run_id=run_id, eligible_only=True)
    run = store.get_run(run_id) or store.create_run("Costco Non-Kirkland Match")
    rid = run["run_id"] if run_id is None else run_id

    ledger = _load_asin_ledger()
    created, by_status = 0, {}
    for csp in eligible:
        csp_id = csp["id"]
        candidates = list((amazon_candidates or {}).get(csp_id, []))
        # Offline ledger hint: ASIN -> Costco item title. Match by item title.
        if not candidates:
            for asin, item_title in ledger.items():
                if item_title and csp.get("title_normalized") and _title_matches(item_title, csp["title_normalized"]):
                    candidates.append(AmazonAttributes(asin=asin, title=item_title, brand=csp.get("brand_raw")))
        for amazon in candidates:
            cand = build_match_candidate(csp, amazon)
            by_status[cand["identity_status"]] = by_status.get(cand["identity_status"], 0) + 1
            created += 1
            if not dry_run:
                store.insert_match_candidate(cand, run_id=rid)
    return {"run_id": rid, "match_candidates_created": created,
            "by_identity_status": by_status, "dry_run": dry_run}


def _title_matches(item_title: str, normalized_costco_title: str) -> bool:
    from difflib import SequenceMatcher
    import re
    a = " ".join(re.sub(r"[^a-z0-9 ]", " ", item_title.lower()).split())
    return SequenceMatcher(None, a, normalized_costco_title).ratio() >= 0.6


def _load_asin_ledger(data_dir: Optional[str] = None) -> Dict[str, str]:
    import json
    base = data_dir or (__file__ and os.path.join(os.path.dirname(__file__), "..", "..", "data"))
    p = os.path.join(base, "costco-amazon-mapping.json")
    if not os.path.exists(p):
        return {}
    try:
        with open(p, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def score_run(run_id: str, *, score_version: Optional[str] = None,
              dry_run: bool = False, store: Optional[PipelineStore] = None) -> Dict[str, Any]:
    """C. Preliminary Golden Goose score for eligible + matched candidates."""
    store = store or PipelineStore()
    candidates = store.list_match_candidates(run_id=run_id)
    scored, blocked = 0, 0
    rows = []
    for cand in candidates:
        if cand["identity_status"] in ("identity_conflict", "pack_mismatch", "size_mismatch"):
            blocked += 1
            continue
        csp = store.get_run(run_id) and _find_csp(store, cand["costco_source_product_id"])
        econ = compute_economics(
            cost_basis=csp.get("costco_price") if csp else None,
            cost_basis_source="costco_discovery" if csp else None,
            cost_basis_status="discovery_only" if csp else None,
            sale_price=None,  # no Amazon price without enrichment
            identity_status=cand["identity_status"],
            pack_verified=(cand["pack_match_status"] == "exact"),
        )
        gg = score_golden_goose(
            eligible=True, identity_status=cand["identity_status"],
            pack_verified=(cand["pack_match_status"] == "exact"),
            economics_completeness=econ.economics_completeness,
            economics=econ.to_dict(),
        )
        scored += 1
        if not dry_run:
            store.insert_gg_score(run_id, cand["costco_source_product_id"], cand.get("id"), gg.to_dict())
        rows.append({"candidate_id": cand.get("id"), "csp_id": cand["costco_source_product_id"],
                     "asin": cand.get("asin"), "score": gg.score,
                     "recommendation_status": gg.recommendation_status,
                     "purchase_authorization_status": gg.purchase_authorization_status})
    return {"run_id": run_id, "scored": scored, "blocked": blocked, "rows": rows, "dry_run": dry_run}


def _find_csp(store: PipelineStore, csp_id: str) -> Optional[Dict[str, Any]]:
    for r in store.list_source_products(limit=100000):
        if r["id"] == csp_id:
            return r
    return None


# ---------------------------------------------------------------------------
# D. Enrichment (approval-gated)
# ---------------------------------------------------------------------------

def plan_enrichment(run_id: str, *, provider: str, max_items: int,
                    spend_cap: Optional[float] = None, dry_run: bool = False,
                    store: Optional[PipelineStore] = None) -> Dict[str, Any]:
    """Generate an enrichment manifest. Dry-run by default; NEVER executes."""
    store = store or PipelineStore()
    provider = provider.lower()
    try:
        provider_factory(provider)
    except ProviderRetired as e:
        return {"error": f"Provider {provider!r} is retired.", "reason": "retired_provider",
                "detail": e.reason, "allowed": ("selleramp",)}
    except KeyError:
        return {"error": f"Unknown provider {provider!r}", "allowed": ("selleramp",)}

    candidates = store.list_match_candidates(run_id=run_id)
    # Only identity-clear, non-blocked candidates are eligible for enrichment.
    pick = [c for c in candidates
            if c["identity_status"] not in ("identity_conflict", "pack_mismatch", "size_mismatch")]
    pick = pick[:max_items]
    items = [{"candidate_id": c.get("id"), "asin": c.get("asin"),
              "csp_id": c.get("costco_source_product_id")} for c in pick]

    preflight = {
        "kind": "costco-nonkirkland-enrichment-preflight",
        "dry_run": dry_run, "provider": provider, "max_items": max_items,
        "spend_cap": spend_cap, "selected_items": len(items),
        "note": "Preflight manifest; NO provider action taken until explicit approval.",
        "no_live_calls": True,
        "signin_prompt": require_signin(provider, store=store).to_dict(),
    }
    if dry_run:
        return preflight

    manifest = store.create_manifest(run_id, provider, [i["asin"] for i in items],
                                     max_items=max_items, spend_cap=spend_cap)
    store.update_manifest(manifest["manifest_id"], preflight_json=_json(preflight))
    manifest["items_detail"] = items
    return manifest


def _json(x: Any) -> str:
    import json
    return json.dumps(x, default=str)


def enrich(manifest_id: str, *, approved: bool = False, max_items: int = 0,
           spend_cap: Optional[float] = None, mock: bool = False,
           store: Optional[PipelineStore] = None) -> Dict[str, Any]:
    """Execute an enrichment manifest ONLY after explicit operator approval.

    Fail-closed: without `approved=True` (and an approval token), nothing runs.
    Also requires the provider sign-in gate to be confirmed before any action.
    """
    store = store or PipelineStore()
    manifest = store.get_manifest(manifest_id)
    if not manifest:
        return {"error": "manifest not found", "manifest_id": manifest_id}

    approved_by_token = (os.getenv(ENRICHMENT_APPROVAL_ENV) or "").strip().lower() in ("1", "true", "yes", "on")
    if not (approved and approved_by_token):
        return {
            "error": "NOT APPROVED — no provider action executed.",
            "manifest_id": manifest_id, "status": "requires_explicit_approval",
            "no_live_calls": True,
            "how_to_approve": f"Set {ENRICHMENT_APPROVAL_ENV}=1 and pass --approved.",
        }

    provider = manifest["provider"]

    # Sign-in gate: prompt the operator to sign in to the provider's research
    # browser before any sanctioned enrichment executes.
    signin = require_signin(provider, store=store)
    if signin.required:
        return {
            "error": "SIGN-IN REQUIRED — no provider action executed.",
            "manifest_id": manifest_id, "status": "requires_sign_in",
            "no_live_calls": True, "signin_prompt": signin.to_dict(),
        }

    try:
        adapter = provider_factory(provider)
    except ProviderRetired as e:
        return {"error": f"Provider {provider!r} is retired: {e.reason}"}
    except KeyError:
        return {"error": f"Unknown provider {provider!r}"}

    status = adapter.is_configured()
    items = manifest.get("items") or []
    if max_items:
        items = items[:max_items]

    results = []
    for asin in items:
        # No direct Amazon page is ever opened; only approved provider snapshots.
        assert_no_amazon_direct_scan(asin=asin)
        results.append(adapter.fetch(asin, mock=mock))

    store.update_manifest(manifest_id, status="completed", approved=1,
                          approval_token=os.getenv(ENRICHMENT_APPROVAL_ENV, "env-approval"),
                          approved_at=_now())
    return {
        "manifest_id": manifest_id, "provider": provider, "approved": True,
        "items": len(items), "results": results, "provider_configured": status.configured,
        "provider_reason": status.reason,
        "purchase_authorization_status": PURCHASE_AUTHORIZATION_NOT_AUTHORIZED,
    }


def export_review(run_id: str, *, fmt: str = "csv", store: Optional[PipelineStore] = None) -> str:
    """Export the non-Kirkland review queue (default: excludes unverified/low-confidence)."""
    store = store or PipelineStore()
    rows = store.list_gg_scores(run_id=run_id)
    filtered = [r for r in rows if r.get("purchase_authorization_status") == PURCHASE_AUTHORIZATION_NOT_AUTHORIZED]
    # Only surface candidates that are at least watchlist / candidate-level.
    visible = [r for r in filtered if r.get("recommendation_status") in (
        RecommendationStatus.CANDIDATE.value, RecommendationStatus.WATCHLIST.value,
        RecommendationStatus.HIGH_PRIORITY_REVIEW.value)]
    if fmt == "json":
        return json_dumps(visible)
    if fmt == "csv":
        import csv
        import io
        buf = io.StringIO()
        cols = ("id", "costco_source_product_id", "amazon_match_candidate_id", "score",
                "confidence_level", "recommendation_status", "purchase_authorization_status",
                "manual_review_required", "scored_at")
        w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in visible:
            w.writerow(r)
        return buf.getvalue()
    lines = []
    for r in visible:
        lines.append(
            f"{r.get('id')}\t{r.get('costco_source_product_id')}\t{r.get('amazon_match_candidate_id')}\t"
            f"score={r.get('score')}\t{r.get('recommendation_status')}\t"
            f"{r.get('purchase_authorization_status')}")
    return "\n".join(lines)


def json_dumps(x: Any) -> str:
    import json
    return json.dumps(x, indent=2, default=str)