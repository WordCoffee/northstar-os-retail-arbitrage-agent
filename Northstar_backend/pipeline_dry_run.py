"""Layer 15 - Offline end-to-end dry-run orchestrator (zero network).

Ties every layer together using injected mock functions. Nothing here performs
a live call; search_fn (discovery) and fetch_fn (enrichment) are supplied by
the caller (tests or a manual dry run). Quota state is isolated to a dry-run
path so production state is never touched.
"""

import os
from datetime import datetime, timezone

import approval as ap
import benchmark_drift as bd
import kirkland_discovery as kd
import provider_waterfall_router as rf
import quota_tracker as qt
import snapshot_builder as sb
import unit_economics as ue


def dry_run(search_fn, fetch_fn, benchmark_canonical, cost_basis_lookup, approvals=None):
    approvals = approvals or ap.Approvals()

    # Isolate quota state so we don't mutate production counters.
    os.environ["QUOTA_TRACKER_PATH"] = "data/dryrun_quota.json"
    qt.save_state(qt._empty_state())

    trace = {"generated_at": datetime.now(timezone.utc).isoformat(), "steps": {}}

    # Layers 1-3: discovery + manifest
    seen, rejected = kd.discover(search_fn, max_pages=3)
    manifest, mpath = kd.build_manifest(seen, rejected)
    trace["steps"]["discovery"] = {
        "found": len(seen), "rejected": len(rejected),
        "manifest_path": mpath, "fingerprint": manifest["fingerprint"],
    }
    asins = list(seen.keys())

    # Layers 5-9: enrichment waterfall + schema-validated snapshots
    gates = rf.WarningGates()
    quota_state = qt.load_state()
    snapshots, audits = rf.route_batch(
        asins, fetch_fn, approvals=approvals, quota_state=quota_state, gates=gates)
    # Stamp titles from discovery into identity for benchmark comparison.
    for asin, rec in seen.items():
        if asin in snapshots:
            snapshots[asin]["facts"]["identity"]["name"] = rec.get("title")
            snapshots[asin]["facts"]["provenance"]["identity.name"] = "discovery_manifest"
    snap_path = sb.write_run_snapshots(snapshots)
    trace["steps"]["enrichment"] = {
        "enriched": len(snapshots), "audits": audits,
        "snapshots_path": snap_path,
    }

    # Layer 11: benchmark drift
    drift = bd.compare_batch(snapshots, benchmark_canonical)
    trace["steps"]["benchmark_drift"] = drift

    # Layer 13: economics
    econ = {asin: ue.compute_economics(snap, cost_basis_lookup)
            for asin, snap in snapshots.items()}
    trace["steps"]["economics"] = econ

    # Gate summary
    trace["gates_fired"] = gates.fired_names()
    return trace
