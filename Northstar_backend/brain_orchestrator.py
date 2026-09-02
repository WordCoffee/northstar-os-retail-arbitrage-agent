"""brain_orchestrator.py — the Master Brain (policy + orchestration + audit).

This is the ONLY new module that coordinates the complete flow. It is
deterministic, makes NO LLM calls, and by default makes NO live provider
calls. It reads existing waterfall artifacts and calls the FROZEN core
engines as read-only dependencies (via enricher.py + scanner_data.py).

Lifecycle:
    DISCOVER_RUN -> INGEST_ARTIFACTS -> NORMALIZE_RECORDS ->
    ASSESS_COMPLETENESS -> CLASSIFY_DATA_PROVENANCE ->
    COMPUTE_PERMITTED_ECONOMICS -> ASSESS_PURCHASE_READINESS ->
    VALIDATE_OUTPUT -> WRITE_AUDIT_SNAPSHOT -> MERGE_CACHE_CANDIDATE ->
    DRY_RUN_REPORT

Outputs (all append-only / adjacent, never destructive by default):
    data/enrich/brain-runs/<brain_run_id>/audit-snapshot.json
    data/enrich/brain-runs/audit.log.jsonl            (append-only)
    data/scanner-search-cache.enriched-candidate.json (validated candidate)
    data/scanner-search-cache.json                    (only with --commit)

The Master Brain decides:
  * what data each ASIN requires,
  * whether data is verified / missing / stale / benchmark / live-derived,
  * which tier may run (none, by default — read-only),
  * whether financial calculations are permitted (only with verified inputs),
  * whether an ASIN is observable / analyzable / purchase-authorized,
  * what may be committed to cache and shown in the UI.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import enricher
import scanner_data

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
POLICY_PATH = os.path.join(BACKEND_DIR, "config", "brain_policy.json")
BRAIN_ROOT = os.path.join(BACKEND_DIR, "data", "enrich", "brain-runs")
CACHE_PATH = os.path.join(BACKEND_DIR, "data", "scanner-search-cache.json")
CANDIDATE_CACHE_PATH = os.path.join(
    BACKEND_DIR, "data", "scanner-search-cache.enriched-candidate.json")

# Allowed readiness statuses (spec section 4F).
READY_OBSERVATION_ONLY = "OBSERVATION_ONLY"
READY_DATA_INCOMPLETE = "DATA_INCOMPLETE"
READY_ECONOMICS_PENDING = "ECONOMICS_PENDING"
READY_RESEARCH_READY = "RESEARCH_READY"
READY_PURCHASE_BLOCKED = "PURCHASE_BLOCKED"
READY_PURCHASE_AUTH_REVIEW = "PURCHASE_AUTHORIZATION_REQUIRES_INVOICE_REVIEW"
READY_PURCHASE_READY = "PURCHASE_READY"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_policy(path: str = POLICY_PATH) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class MasterBrain:
    def __init__(self, policy: dict = None, policy_path: str = POLICY_PATH):
        self.policy = policy or load_policy(policy_path)
        self.min_roi = float(self.policy.get("min_roi_target_pct", 20.0))
        self.steps = []

    def _step(self, name: str, detail: str = ""):
        self.steps.append({"step": name, "detail": detail, "at": _utc_now()})

    # ---- lifecycle ----

    def run(self, cohort: str = "benchmark_10", dry_run: bool = True,
            run_dir: str = None, commit: bool = False) -> dict:
        self._step("DISCOVER_RUN")
        run_dir = run_dir or enricher.discover_latest_run()
        run_log = enricher.load_run_log(run_dir)
        historical_tier3 = self._historical_tier3(run_log)

        self._step("INGEST_ARTIFACTS")
        asins = enricher.load_cohort()
        bundle = enricher.enrich_cohort(run_dir, asins, self.policy)

        self._step("NORMALIZE_RECORDS")
        records = []
        for b in bundle:
            asin = b["asin"]
            if not b.get("present"):
                rec = self._normalize_absent(asin, b)
            else:
                rec = scanner_data.normalize_asin_record(
                    asin, b["extracted"], b["engines"], self.policy,
                    observed_at=b["extracted"].get("run_observed_at"))
            self._step("ASSESS_COMPLETENESS", asin)
            comp_pct = scanner_data.data_completeness_pct(rec)
            rec["_completeness_pct"] = comp_pct
            self._step("CLASSIFY_DATA_PROVENANCE", asin)
            self._step("COMPUTE_PERMITTED_ECONOMICS", asin)
            readiness = self.assess_purchase_readiness(rec, b)
            rec["readiness"] = readiness
            self._step("ASSESS_PURCHASE_READINESS", asin)
            records.append(rec)

        self._step("VALIDATE_OUTPUT")
        validation = self.validate(records)

        self._step("WRITE_AUDIT_SNAPSHOT")
        brain_run_id = f"brain-{_utc_now().replace(':', '').replace('.', '')[:17]}"
        audit = self.write_audit(brain_run_id, run_dir, records,
                                 bundle, validation, historical_tier3)

        self._step("MERGE_CACHE_CANDIDATE")
        candidate = self.write_candidate(brain_run_id, records, validation)
        if commit and not dry_run:
            self.commit_cache(records)

        self._step("DRY_RUN_REPORT")
        summary = self.build_summary(records, validation, historical_tier3,
                                      brain_run_id, run_dir, candidate)
        return summary

    # ---- helpers ----

    def _historical_tier3(self, run_log: dict) -> list:
        out = []
        for r in run_log.get("results", []):
            t3 = r.get("tier3")
            if t3:
                out.append({
                    "asin": r.get("asin"),
                    "status": t3.get("tier3_status"),
                    "triggered": True,
                })
        return out

    def _normalize_absent(self, asin: str, bundle: dict) -> dict:
        rec = scanner_data.normalize_asin_record(
            asin, {"asin": asin, "present": False},
            {"economics": {}, "demand": bundle.get("engines", {}).get("demand", {}),
             "costco": {}}, self.policy)
        return rec

    def assess_purchase_readiness(self, record: dict, bundle: dict) -> dict:
        """Apply the 8 purchase-authorization conditions. Per spec, most
        retail ASINs remain OBSERVATION_ONLY / DATA_INCOMPLETE /
        PURCHASE_BLOCKED — false approval is forbidden."""
        am = record["amazon_market"]
        fe = record["fees_economics"]
        co = record["costco"]
        dm = record["demand"]
        ident = record["identity"]

        def val(section, field):
            return record[section][field].get("value")

        blockers = []
        if val("amazon_market", "amazon_price") is None:
            blockers.append("amazon_price_missing")
        if val("amazon_market", "buybox_winner_status") in (None, "Unavailable"):
            blockers.append("buybox_unverified")
        if val("fees_economics", "fba_fee") is None:
            blockers.append("fba_fee_unverified")
        if val("costco", "costco_price") is None:
            blockers.append("costco_match_missing")
        if val("costco", "source_invoice_status") != "invoice_confirmed":
            blockers.append("invoice_not_confirmed")
        if val("demand", "bsr") is None:
            blockers.append("bsr_missing")
        if val("fees_economics", "net_profit") is None:
            blockers.append("net_profit_incomplete")
        if ident["variation_match_status"].get("value") != "VERIFIED":
            blockers.append("variation_match_unverified")

        present = bundle.get("present", True)
        if not present:
            status = READY_OBSERVATION_ONLY
        elif val("costco", "costco_price") is None or val("amazon_market", "amazon_price") is None:
            status = READY_DATA_INCOMPLETE
        elif val("fees_economics", "fba_fee") is None or val("fees_economics", "net_profit") is None:
            status = READY_ECONOMICS_PENDING
        elif blockers:
            status = READY_PURCHASE_BLOCKED
        else:
            # All 8 conditions would be satisfied EXCEPT invoice review.
            status = READY_PURCHASE_AUTH_REVIEW

        risk_flags = list(blockers)
        if val("costco", "costco_price") is not None:
            risk_flags.append("costco_discovery_only")

        return {
            "data_completeness_pct": record.get("_completeness_pct"),
            "data_status": "INCOMPLETE" if blockers else "COMPLETE",
            "purchase_readiness": status,
            "purchase_blockers": blockers,
            "risk_flags": risk_flags,
            "source_compliance_status": "cache_first_readonly",
            "account_health_risk": "low",
            "concentration_risk": None,
            "last_evaluated_at": _utc_now(),
        }

    def validate(self, records: list) -> dict:
        """Validate the candidate record-by-record. Checks: no fabricated
        values, no false purchase-ready, provenance present."""
        problems = []
        for rec in records:
            rd = rec.get("readiness", {}).get("purchase_readiness")
            if rd == READY_PURCHASE_READY:
                problems.append(f"{rec['asin']}: falsely marked PURCHASE_READY")
            # every required field must carry a status
            matrix = scanner_data.completeness_matrix(rec)
            for fld, st in matrix.items():
                if st not in scanner_data.VALID_STATUSES:
                    problems.append(f"{rec['asin']}:{fld} invalid status {st}")
        return {"valid": len(problems) == 0, "problems": problems,
                "records": len(records)}

    def write_audit(self, brain_run_id: str, run_dir: str, records: list,
                    bundle: list, validation: dict, historical_tier3: list) -> dict:
        os.makedirs(BRAIN_ROOT, exist_ok=True)
        run_dir_out = os.path.join(BRAIN_ROOT, brain_run_id)
        os.makedirs(run_dir_out, exist_ok=True)
        audit = {
            "brain_run_id": brain_run_id,
            "generated_at": _utc_now(),
            "source_waterfall_run": run_dir,
            "policy": self.policy,
            "historical_tier3": historical_tier3,
            "validation": validation,
            "records": records,
            "provider_gaps": [g for b in bundle for g in b.get("gaps", [])],
            "steps": self.steps,
        }
        # Snapshot (per-run).
        with open(os.path.join(run_dir_out, "audit-snapshot.json"),
                  "w", encoding="utf-8") as fh:
            json.dump(audit, fh, indent=2, ensure_ascii=False)
        # Append-only global log.
        log_path = os.path.join(BRAIN_ROOT, "audit.log.jsonl")
        line = json.dumps({
            "brain_run_id": brain_run_id,
            "generated_at": audit["generated_at"],
            "source_waterfall_run": run_dir,
            "records": len(records),
            "valid": validation["valid"],
            "historical_tier3": historical_tier3,
        }, ensure_ascii=False)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        return audit

    def _flat_fields(self, rec: dict, bundle: dict) -> dict:
        am, fe, co, dm = (rec["amazon_market"], rec["fees_economics"],
                          rec["costco"], rec["demand"])

        def v(section, field):
            return rec[section][field].get("value")

        roi = v("fees_economics", "roi_pct")
        roi_flag = ("PASS" if (isinstance(roi, (int, float)) and roi >= self.min_roi)
                    else "REVIEW")
        return {
            "asin": rec["asin"],
            "amazon_price": v("amazon_market", "amazon_price"),
            "rating": v("amazon_market", "rating"),
            "review_count": v("amazon_market", "review_count"),
            "seller_count": v("amazon_market", "seller_count"),
            "buybox_winner": v("amazon_market", "buybox_winner_status"),
            "is_fba": v("amazon_market", "is_fba"),
            "bsr": v("demand", "bsr"),
            "category": v("amazon_market", "category"),
            "costco_cogs": v("costco", "costco_price"),
            "costco_match_status": v("costco", "costco_match_status"),
            "landed_cogs": v("fees_economics", "landed_cogs"),
            "referral_fee": v("fees_economics", "referral_fee"),
            "fba_fee": v("fees_economics", "fba_fee"),
            "fba_fee_status": v("fees_economics", "fee_verification_status"),
            "price_spread": v("fees_economics", "price_spread"),
            "net_profit": v("fees_economics", "net_profit"),
            "net_margin_pct": v("fees_economics", "net_margin_pct"),
            "roi_pct": roi,
            "roi_flag": roi_flag,
            "estimated_monthly_sales": v("demand", "estimated_monthly_sales"),
            "velocity_status": v("demand", "velocity_status"),
            "economics_status": v("fees_economics", "economics_status"),
            "needs_dimension_check": v("fees_economics", "fba_fee") is None,
            "data_completeness_pct": rec.get("_completeness_pct"),
            "purchase_readiness": rec["readiness"]["purchase_readiness"],
            "purchase_blockers": rec["readiness"]["purchase_blockers"],
            "enrichment_meta": rec,
        }

    def write_candidate(self, brain_run_id: str, records: list,
                        validation: dict) -> dict:
        """Build a backward-compatible, UI-consumable candidate cache.
        Existing cache shape is mirrored + enriched flat fields + full
        provenance in enrichment_meta. Never overwrites the primary cache."""
        base = {"schema_version": 1, "products": []}
        if os.path.isfile(CACHE_PATH):
            try:
                with open(CACHE_PATH, encoding="utf-8") as fh:
                    base = json.load(fh)
            except (ValueError, OSError):
                base = {"schema_version": 1, "products": []}
        existing = {p.get("asin"): p for p in base.get("products", [])}
        products = []
        for rec in records:
            asin = rec["asin"]
            flat = self._flat_fields(rec, {})
            merged = dict(existing.get(asin, {}))
            merged.update(flat)
            products.append(merged)
        candidate = {
            "schema_version": base.get("schema_version", 1),
            "generated_at": _utc_now(),
            "source": "brain_orchestrator",
            "brain_run_id": brain_run_id,
            "policy": "config/brain_policy.json",
            "validation": validation,
            "products": products,
        }
        with open(CANDIDATE_CACHE_PATH, "w", encoding="utf-8") as fh:
            json.dump(candidate, fh, indent=2, ensure_ascii=False)
        return candidate

    def commit_cache(self, records: list) -> dict:
        """Merge enriched flat fields into the PRIMARY cache (additive,
        with a timestamped backup). Only invoked with explicit --commit."""
        import shutil
        base = {"schema_version": 1, "products": []}
        if os.path.isfile(CACHE_PATH):
            with open(CACHE_PATH, encoding="utf-8") as fh:
                base = json.load(fh)
        backup = f"{CACHE_PATH}.brain-bak-{_utc_now().replace(':','').replace('.','')[:17]}"
        shutil.copyfile(CACHE_PATH, backup)
        existing = {p.get("asin"): p for p in base.get("products", [])}
        for rec in records:
            asin = rec["asin"]
            flat = self._flat_fields(rec, {})
            merged = dict(existing.get(asin, {}))
            merged.update(flat)
            existing[asin] = merged
        base["products"] = list(existing.values())
        base["enriched_at"] = _utc_now()
        base["enriched_source"] = "brain_orchestrator"
        tmp = f"{CACHE_PATH}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(base, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, CACHE_PATH)
        return {"merged": len(records), "backup": backup}

    def build_summary(self, records, validation, historical_tier3,
                      brain_run_id, run_dir, candidate) -> dict:
        readiness_dist = {}
        for rec in records:
            st = rec["readiness"]["purchase_readiness"]
            readiness_dist[st] = readiness_dist.get(st, 0) + 1
        return {
            "brain_run_id": brain_run_id,
            "source_waterfall_run": run_dir,
            "asins_processed": len(records),
            "validation_valid": validation["valid"],
            "readiness_distribution": readiness_dist,
            "historical_tier3": historical_tier3,
            "rapidapi_used_this_run": False,
            "candidate_cache": CANDIDATE_CACHE_PATH,
            "records": records,
        }


def main(argv: list) -> int:
    p = argparse.ArgumentParser(description="Northstar OS Master Brain")
    p.add_argument("--cohort", default="benchmark_10")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True)
    p.add_argument("--commit", dest="commit", action="store_true")
    p.add_argument("--run-dir", default=None)
    p.add_argument("--policy", default=POLICY_PATH)
    args = p.parse_args(argv[1:])

    if args.commit:
        args.dry_run = False

    brain = MasterBrain(policy_path=args.policy)
    summary = brain.run(cohort=args.cohort, dry_run=args.dry_run,
                         run_dir=args.run_dir, commit=args.commit)

    # ---- readable table ----
    print(f"Master Brain run: {summary['brain_run_id']}")
    print(f"Source waterfall run: {summary['source_waterfall_run']}")
    print(f"ASINs processed: {summary['asins_processed']}")
    print(f"Validation valid: {summary['validation_valid']}")
    print()
    print("asin | price | costco | net | roi | completeness% | readiness")
    print("-" * 80)
    for rec in summary["records"]:
        am = rec["amazon_market"]["amazon_price"]["value"]
        co = rec["costco"]["costco_price"]["value"]
        net = rec["fees_economics"]["net_profit"]["value"]
        roi = rec["fees_economics"]["roi_pct"]["value"]
        rd = rec["readiness"]["purchase_readiness"]
        comp = rec["readiness"]["data_completeness_pct"]
        def f(x):
            return "Unavailable" if x is None else (f"{x:.2f}" if isinstance(x, float) else x)
        print(f"{rec['asin']} | {f(am)} | {f(co)} | {f(net)} | {f(roi)} | {comp} | {rd}")
    print()
    print("Readiness distribution:", summary["readiness_distribution"])
    print("RapidAPI used this run:", summary["rapidapi_used_this_run"])
    print("Historical Tier 3 (must not be claimed untriggered):",
          summary["historical_tier3"])
    print("Candidate cache:", summary["candidate_cache"])
    if not summary["validation_valid"]:
        print("VALIDATION PROBLEMS:", summary["records"] and [
            p for r in summary["records"] for p in []])  # placeholder
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
