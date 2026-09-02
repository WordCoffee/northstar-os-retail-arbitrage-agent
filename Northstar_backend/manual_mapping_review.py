"""Offline manual mapping-resolution record writer.

This module is NOT part of the guarded live validation run path. It only
writes a local-only review artifact for ASINs whose identity could not be
resolved by the strict mapping guard (e.g. a non-conflict title mismatch
that correctly hard-stopped a live run).

No provider / network calls are made. No protected artifacts are read or
written. The review record carries no purchase authorization and no
benchmark-mutation recommendation unless external/manual evidence later
justifies one.
"""

import json
import os
import tempfile

REVIEW_OUTPUT_ROOT = os.path.join("data", "batch", "manual-mapping-review")

ATTEMPT_2_FAILURE_DIR = (
    "data/batch/live-validation-runs/proof-batch-preflight-attempt-2-20260819T030931Z"
)
ATTEMPT_2_FAILURE_MANIFEST_SHA256 = (
    "42069974d7a86e2fb50093938c44f50e606726a94e0065bbf81572f10cd510d6"
)

B0CP6LXPLK_REVIEW_RECORD = {
    "asin": "B0CP6LXPLK",
    "status": "manual_resolution_required",
    "identity_status": "manual_resolution_required",
    "purchase_status": "blocked",
    "provider_validation_status": "unresolved_nonconflict_mapping_mismatch",
    "source_preflight_run_ids": [
        "proof-batch-preflight-20260818T060549Z",
        "proof-batch-preflight-attempt-2-20260819T030931Z",
    ],
    "failure_run_directory": ATTEMPT_2_FAILURE_DIR,
    "failure_manifest_sha256": ATTEMPT_2_FAILURE_MANIFEST_SHA256,
    "benchmark_title": "Minoxidil Extra Strength (6-mo)",
    "benchmark_title_variants": None,
    "title_conflict": False,
    "live_returned_title": None,
    "live_returned_title_note": (
        "Not retained: the live run hard-stopped on a scrubbed failure "
        "manifest with no result envelope, so no returned title is safely "
        "available in local evidence."
    ),
    "mapping_outcome": "unexpected_mapping_mismatch",
    "reason": (
        "Non-conflict ASIN returned an incompatible title; "
        "benchmark/provider/listing identity unresolved."
    ),
    "conclusion_about_correct_source": None,
    "purchase_authorization": None,
    "benchmark_mutation_recommendation": None,
    "next_required_evidence": [
        "Amazon listing title and product page identity from a manually reviewed source",
        "pack count/strength/volume comparison",
        "brand/manufacturer comparison",
        "UPC/EAN if available",
        "screenshot or documented human verification timestamp",
        "a future trusted paid-provider result, if acquired",
    ],
}


def build_review_record():
    """Return a fresh copy of the B0CP6LXPLK manual-resolution record."""
    return dict(B0CP6LXPLK_REVIEW_RECORD)


def write_review_record(record, out_path):
    """Atomically write a review record as pretty JSON.

    Uses a temp file + os.replace so a crash mid-write never leaves a
    partial record behind.
    """
    out_path = os.path.abspath(out_path)
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=parent or ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(record, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_path, out_path)
    except Exception:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise
    return out_path
