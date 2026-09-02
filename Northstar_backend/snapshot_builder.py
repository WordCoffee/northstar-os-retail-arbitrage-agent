"""Layer 9/10 - Snapshot builder + storage (null-first, schema-validated).

build_snapshot() wraps an intel_schema MarketSnapshot, stamps provenance, and
runs intel_schema.validate_snapshot. Storage helpers create data/snapshots and
data/catalog if missing (the prior crash was a missing data/snapshots dir).
"""

import json
import os
from datetime import datetime, timezone

from intel_schema import fixture_minimal, snapshot_from_fixture, validate_snapshot


def build_snapshot(asin, market, source, cost_basis=None, title=None):
    snap = snapshot_from_fixture(fixture_minimal())
    snap["asin"] = asin
    snap["facts"]["market"] = market
    snap["facts"]["identity"]["name"] = title
    snap["facts"]["provenance"]["market.amazon_price"] = source
    if title is not None:
        snap["facts"]["provenance"]["identity.name"] = source
    if cost_basis is not None:
        snap["facts"]["cost"] = cost_basis
    errs = validate_snapshot(snap)
    snap["validation_errors"] = errs if errs else None
    snap["validation_status"] = "valid" if not errs else "invalid"
    return snap


def ensure_dirs():
    os.makedirs("data/snapshots", exist_ok=True)
    os.makedirs("data/catalog", exist_ok=True)


def write_run_snapshots(snapshots, path=None):
    ensure_dirs()
    if path is None:
        path = "data/snapshots/dryrun_%s.json" % datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "offline_dry_run",
        "asins": snapshots,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    return path
