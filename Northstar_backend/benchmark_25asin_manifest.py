"""Offline-only frozen 25-ASIN benchmark comparison manifest builder.

Builds an audit-stable manifest of exactly the 25 frozen target ASINs for a
FUTURE (not-yet-approved) live benchmark comparison run. PURE OFFLINE — reads
the two user-provided benchmark CSVs via asin_benchmark_store, writes only to
data/benchmarks/manifests/ (never the raw/ or reference artifacts). The
scanner CSV contract and all live provider/cache files are untouched.

Fail-closed: an ASIN absent from BOTH benchmark CSVs has no benchmark anchor,
so its benchmark fields cannot be populated without fabrication — which is
forbidden. The builder therefore REFUSES to emit a manifest when any frozen
target ASIN is absent from both CSVs (raises ManifestBuildError listing the
missing ASINs). Every included record carries benchmark_evidence_class
'benchmark_reference' and a null captured_at (reference capture time unknown).
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import asin_benchmark_store

MANIFEST_SCHEMA_VERSION = 1

# Exactly 25 frozen target ASINs (audit-stable). Do not edit without a new
# frozen revision + fingerprint bump.
FROZEN_TARGET_ASINS = (
    "B00NXZ13GW", "B07F9YSRFB", "B07Q2HHLVN", "B0BMX67KY7", "B01NAE8NP9",
    "B07KT8CMR9", "B07N4FN1QY", "B07FKSPPNQ", "B0CQRTSLSV", "B00UP99X1I",
    "B0CHTNWWLJ", "B01H20NZUI", "B0B6VGVVQ1", "B0B7BZXKQ7", "B00F4MD808",
    "B07H3TXVR7", "B00JVOJF1S", "B0BRZSW9KF", "B000V49JAA", "B09C1P9WVX",
    "B006HIQBJS", "B0BMYPTV79", "B00RY4KZFW", "B0077SXI7A", "B097DMJDPM",
)

# Excluded due to title/mapping conflicts (Aller-Flo Fluticasone variants).
EXCLUDED_ASINS = (
    "B01H40O42I",
    "B08R2SRN88",
)

DEFAULT_MANIFEST_DIR = os.path.join("data", "benchmarks", "manifests")
DEFAULT_MANIFEST_PATH = os.path.join(DEFAULT_MANIFEST_DIR, "live-25asin-comparison-manifest.json")
DEFAULT_REVIEW_PATH = os.path.join(DEFAULT_MANIFEST_DIR, "live-25asin-comparison-manifest-review.md")

BENCHMARK_EVIDENCE_CLASS = "benchmark_reference"


class ManifestBuildError(Exception):
    """Fail-closed refusal: a frozen target ASIN lacks a benchmark anchor."""


def _env_path(name: str, default: str) -> str:
    return os.environ.get(name) or default


def manifest_path() -> str:
    return _env_path("BENCHMARK_25ASIN_MANIFEST_PATH", DEFAULT_MANIFEST_PATH)


def review_path() -> str:
    return _env_path("BENCHMARK_25ASIN_REVIEW_PATH", DEFAULT_REVIEW_PATH)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bsr_reference_status(canon: Dict[str, Any]) -> str:
    if canon.get("bsr_rank_number") is not None:
        return "verified"
    source_files = canon.get("source_files") or []
    if source_files:
        # Present in a CSV, but the BSR-bearing (Rank-BSR) file had none.
        return "missing_csv_reference"
    return "provider_not_supported"


def _derive_record(asin: str, canon: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "asin": asin,
        "benchmark_title": canon.get("title"),
        "benchmark_price": canon.get("price"),
        "benchmark_reviews": canon.get("reviews"),
        "benchmark_prime_fba": canon.get("prime_fba"),
        "benchmark_bsr_raw": canon.get("bsr_raw"),
        "benchmark_bsr_primary_rank": canon.get("bsr_rank_number"),
        "benchmark_bsr_primary_category": canon.get("bsr_category"),
        "benchmark_bsr_secondary_rank": canon.get("bsr_secondary_rank_number"),
        "benchmark_bsr_secondary_category": canon.get("bsr_secondary_category"),
        "bsr_reference_status": _bsr_reference_status(canon),
        "source_files": sorted(canon.get("source_files") or []),
        "benchmark_evidence_class": BENCHMARK_EVIDENCE_CLASS,
        "captured_at": None,
        "mapping_status": "conflict" if canon.get("title_conflict") else "verified",
        "inclusion_reason": "frozen_25asin_target",
        "future_live_run_eligible": True,
        "manual_review_required": bool(canon.get("title_conflict")),
        "excluded_from_live_run_reason": None,
    }


def build_manifest_dict(
    store: Optional[Dict[str, Any]] = None,
    raise_on_missing: bool = True,
) -> Dict[str, Any]:
    """Build the frozen 25-ASIN manifest dict (no writes).

    store: asin_benchmark_store.build_store() output (reads raw CSVs). If None,
    build_store() is called. With raise_on_missing=True, raises ManifestBuildError
    when any frozen target ASIN is absent from both CSVs. With False, missing
    ASINs are reported under 'validation.missing_target_asins' and excluded from
    records (so the structure can be inspected without fabrication).
    """
    if store is None:
        store = asin_benchmark_store.build_store()
    canonical = store.get("canonical") or {}

    present: Dict[str, Dict[str, Any]] = {}
    missing: List[str] = []
    for asin in FROZEN_TARGET_ASINS:
        canon = canonical.get(asin)
        if canon is None:
            missing.append(asin)
        else:
            present[asin] = canon

    dupes = [a for a in FROZEN_TARGET_ASINS if FROZEN_TARGET_ASINS.count(a) > 1]
    title_conflicts = [a for a, c in present.items() if c.get("title_conflict")]

    if raise_on_missing and missing:
        raise ManifestBuildError(
            f"{len(missing)} frozen target ASIN(s) absent from both benchmark CSVs: "
            f"{', '.join(missing)}"
        )
    if dupes:
        raise ManifestBuildError(f"duplicate ASINs in frozen target list: {dupes}")
    if title_conflicts and raise_on_missing:
        raise ManifestBuildError(
            f"title/mapping conflict among included targets: {title_conflicts}"
        )

    records = [r for a, r in (
        (a, _derive_record(a, present[a])) for a in FROZEN_TARGET_ASINS if a in present
    )]

    bsr_verified = sum(1 for r in records if r["bsr_reference_status"] == "verified")

    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "kind": "frozen-25asin-benchmark-manifest",
        "generated_at": _now_iso(),
        "frozen_target_count": len(FROZEN_TARGET_ASINS),
        "excluded_asins": list(EXCLUDED_ASINS),
        "target_asins": list(FROZEN_TARGET_ASINS),
        "benchmark_evidence_class": BENCHMARK_EVIDENCE_CLASS,
        "capture_time_note": "benchmark reference capture time unknown; reference only, not freshness proof",
        "records": records,
        "validation": {
            "included_count": len(records),
            "excluded_count": len(EXCLUDED_ASINS),
            "missing_target_asins": missing,
            "duplicate_target_asins": dupes,
            "title_conflict_targets": title_conflicts,
            "bsr_verified_count": bsr_verified,
            "bsr_missing_csv_reference_count": len(records) - bsr_verified,
        },
        "fingerprint": None,  # filled below
    }
    manifest["fingerprint"] = _fingerprint(manifest)
    return manifest


def _fingerprint(manifest: Dict[str, Any]) -> str:
    """SHA-256 over deterministic canonical manifest bytes (records only)."""
    payload = {
        "schema_version": manifest["schema_version"],
        "target_asins": manifest["target_asins"],
        "excluded_asins": manifest["excluded_asins"],
        "records": [
            {k: v for k, v in r.items() if k != "fingerprint"}
            for r in manifest["records"]
        ],
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def write_manifest(manifest: Dict[str, Any], path: Optional[str] = None) -> str:
    target = path or manifest_path()
    os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
    review = review_path()
    os.makedirs(os.path.dirname(review) or ".", exist_ok=True)
    with open(review, "w", encoding="utf-8") as fh:
        fh.write(_review_markdown(manifest))
    return target


def _review_markdown(manifest: Dict[str, Any]) -> str:
    v = manifest["validation"]
    lines = [
        "# Frozen 25-ASIN Benchmark Comparison Manifest — Review",
        "",
        f"- Generated: {manifest['generated_at']}",
        f"- Fingerprint (SHA-256): `{manifest['fingerprint']}`",
        f"- Frozen targets: {manifest['frozen_target_count']}",
        f"- Included: {v['included_count']}",
        f"- Excluded (title/mapping conflict): {v['excluded_count']} "
        f"({', '.join(manifest['excluded_asins'])})",
        f"- Missing from both CSVs: {len(v['missing_target_asins'])}",
        f"- BSR verified: {v['bsr_verified_count']}",
        f"- BSR missing_csv_reference: {v['bsr_missing_csv_reference_count']}",
        "",
        "## Benchmark-only disclaimer",
        "",
        "This manifest is a FROZEN REFERENCE for a future, not-yet-approved "
        "live benchmark comparison run. Benchmark values are user-provided "
        "reference observations; they are NOT a live market feed and NOT proof "
        "of current conditions. Capture time is unknown (reference only). No "
        "ASIN in this manifest is purchase-authorized.",
        "",
        "## Included ASINs",
        "",
        "| ASIN | Title | Price | Reviews | Prime/FBA | BSR ref | Mapping |",
        "|------|-------|-------|---------|-----------|---------|---------|",
    ]
    for r in manifest["records"]:
        title = (r["benchmark_title"] or "").replace("|", "/")
        lines.append(
            f"| {r['asin']} | {title} | {r['benchmark_price']} | "
            f"{r['benchmark_reviews']} | {r['benchmark_prime_fba']} | "
            f"{r['bsr_reference_status']} | {r['mapping_status']} |"
        )
    if v["missing_target_asins"]:
        lines += ["", "## Missing from both CSVs (no benchmark anchor)", ""]
        lines += [f"- {a}" for a in v["missing_target_asins"]]
    return "\n".join(lines) + "\n"


def _cli() -> None:
    import sys

    store = asin_benchmark_store.build_store()
    try:
        manifest = build_manifest_dict(store, raise_on_missing=True)
    except ManifestBuildError as exc:
        raise SystemExit(f"MANIFEST BUILD REFUSED (fail-closed): {exc}")
    path = write_manifest(manifest)
    print(f"manifest written: {path}")
    print(f"records={manifest['validation']['included_count']} "
          f"bsr_verified={manifest['validation']['bsr_verified_count']} "
          f"fingerprint={manifest['fingerprint']}")


if __name__ == "__main__":
    _cli()
