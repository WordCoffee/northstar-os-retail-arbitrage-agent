"""Layers 5, 6, 7, 8, 12 - Provider waterfall router + warning gates + audit.

route_asin() tries the 6 RapidAPI pool apps in PRIORITY order for a single
ASIN, skipping apps already confirmed exhausted this run, and only falls back
to DataForSEO after the whole RapidAPI pool is exhausted for that ASIN.

Two blocking warning gates fire (at most once per run via a WarningGates
latch), each requiring explicit operator approval before the next spend:

  Gate #1 - fires when the RapidAPI pool is exhausted for an ASIN, before the
            first DataForSEO attempt. Proceeding requires enrichment approval.
  Gate #2 - fires when DataForSEO's free-credit allotment is exhausted and the
            next call would spend real USD. Proceeding requires enrichment
            approval.

Layer 12 - every attempt is logged: providers tried in order, the failure
reason per provider, and the final successful source (or null).
"""

import quota_tracker as qt
import provider_mappers as pm
import snapshot_builder as sb

PRIORITY = [
    "RAPIDAPI_BDC",
    "RAPIDAPI_REALTIME",
    "RAPIDAPI_AXESSO",
    "RAPIDAPI_PRICING",
    "RAPIDAPI_ONLINE",
    "RAPIDAPI_SCOUT",
    "DATAFORSEO",
]

RAPIDAPI_POOL = PRIORITY[:6]


class WarningGates:
    """Latched gate tracker: each named gate fires at most once per instance."""

    def __init__(self):
        self._state = {}

    def fire(self, name, approvals):
        if name in self._state:
            return self._state[name]["approved"]
        approved = bool(getattr(approvals, "enrichment", False))
        self._state[name] = {"fired": True, "approved": approved}
        return approved

    def fired_count(self, name):
        return 1 if name in self._state else 0

    def fired_names(self):
        return list(self._state.keys())


def _dfs_free_exhausted(quota_state):
    slot = quota_state["apps"]["DATAFORSEO"]["enrichment"]
    return slot.get("remaining") == 0


def route_asin(asin, fetch_fn, *, approvals, quota_state=None, gates=None,
               app_phase="enrichment"):
    gates = gates or WarningGates()
    quota_state = quota_state or qt.load_state()
    audit = {"asin": asin, "tried": [], "final_source": None,
             "gate_events": [], "validation": "not_run"}

    # --- RapidAPI pool first ---
    for app in RAPIDAPI_POOL:
        if qt.is_exhausted(app, app_phase, quota_state):
            audit["tried"].append({"app": app, "result": "skipped_exhausted"})
            continue
        status, raw = fetch_fn(app, asin)
        if status == 200 and raw:
            market = pm.map_provider(app, asin, raw)
            if market is None:
                audit["tried"].append({"app": app, "result": "mapper_none"})
                continue
            snap = sb.build_snapshot(asin, market, app)
            if snap.get("validation_errors"):
                audit["tried"].append({"app": app, "result": "validation_failed",
                                       "errors": snap["validation_errors"][:5]})
                continue
            qt.record_used(app, app_phase, 1)
            audit["final_source"] = app
            audit["validation"] = "passed"
            return snap, audit
        else:
            audit["tried"].append({"app": app, "result": "http_%s" % status})
            if status in (403, 429):
                qt.mark_exhausted(app, app_phase, "http_%s" % status)

    # --- All RapidAPI exhausted/failed -> Gate #1 before DataForSEO ---
    gate1 = gates.fire("gate1_rapidapi_exhausted", approvals)
    audit["gate_events"].append({"gate": "gate1_rapidapi_exhausted",
                                 "fired": True, "approved": gate1})
    if not gate1:
        audit["validation"] = "blocked_gate1"
        return None, audit

    # --- DataForSEO fallback ---
    dfs = "DATAFORSEO"
    if qt.is_exhausted(dfs, app_phase, quota_state):
        audit["tried"].append({"app": dfs, "result": "skipped_exhausted"})
        return None, audit
    if _dfs_free_exhausted(quota_state):
        gate2 = gates.fire("gate2_dataforseo_paid", approvals)
        audit["gate_events"].append({"gate": "gate2_dataforseo_paid",
                                     "fired": True, "approved": gate2})
        if not gate2:
            audit["validation"] = "blocked_gate2"
            return None, audit

    status, raw = fetch_fn(dfs, asin)
    if status == 200 and raw:
        market = pm.map_provider(dfs, asin, raw)
        if market is None:
            audit["tried"].append({"app": dfs, "result": "mapper_none"})
            return None, audit
        snap = sb.build_snapshot(asin, market, dfs)
        if snap.get("validation_errors"):
            audit["tried"].append({"app": dfs, "result": "validation_failed",
                                   "errors": snap["validation_errors"][:5]})
            return None, audit
        qt.record_used(dfs, app_phase, 1)
        audit["final_source"] = dfs
        audit["validation"] = "passed"
        return snap, audit
    audit["tried"].append({"app": dfs, "result": "http_%s" % status})
    return None, audit


def route_batch(asins, fetch_fn, *, approvals, quota_state=None, gates=None,
                app_phase="enrichment"):
    gates = gates or WarningGates()
    quota_state = quota_state or qt.load_state()
    snapshots = {}
    audits = {}
    for asin in asins:
        snap, audit = route_asin(asin, fetch_fn, approvals=approvals,
                                 quota_state=quota_state, gates=gates,
                                 app_phase=app_phase)
        audits[asin] = audit
        if snap is not None:
            snapshots[asin] = snap
    return snapshots, audits
