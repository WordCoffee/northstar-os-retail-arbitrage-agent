"""Master Brain Subscriber Registry — plan catalog + entitlements resolution.

Offline, additive-only. No LLM calls, no network calls, no credentials.

Pairs with `master_brain_profiles.py`:

    1. resolve_active_profile()  -> WHO is asking?   (identity --> profile id)
    2. plan_for_profile(id)      -> WHICH plan covers the subscriber
    3. entitled_gates(plan_id)   -> WHICH live gates the plan would permit

HARD INVARIANT: a plan ENTITLES a gate — it never OPENS one. The 8 live gates
(orchestrated by the Analyst's Desk shell, window.NS.gates) always remain
`off: true` in beta. Executing any live action additionally requires a fresh,
named operator approval per action. The catalog carries `gates_always_off:
true` and every loader asserts it.

The canonical plan catalog lives in `master-brain/subscription-plans.json` and
the canonical subscriber index lives in `master-brain/profiles/manifest.json`.
Unknown plan ids and unknown profile ids fail closed (never fabricated).
"""

import json
import os
import sys
from typing import Dict, List, Optional

# Project-root canonical paths
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANS_PATH = os.path.join(REPO_ROOT, "master-brain", "subscription-plans.json")
MANIFEST_PATH = os.path.join(REPO_ROOT, "master-brain", "profiles", "manifest.json")

# Canonical live-gate registry, mirroring the Analyst's Desk shell (NS.gates).
# Single source of truth for what a plan may entitle. Every gate stays OFF in
# beta regardless of plan; execution needs separate named approval.
LIVE_GATES: Dict[str, str] = {
    "sourcescout_live_pull": "Costco live-pull (Bright Data / Firecrawl)",
    "sourcescout_enrich": "Enrichment (Easyparser / RapidAPI / DataForSEO)",
    "listingforge_copy": "Claude copy rewrite",
    "listingforge_media": "Image / video generation API",
    "adpilot_bulk_exec": "Amazon Bulk Operations upload",
    "adpilot_ads_read": "Amazon Ads API read",
    "socialpulse_publish": "Meta / TikTok / Instagram publish",
    "socialpulse_attrib": "Amazon Attribution generation",
}


def _read_catalog(path: str, label: str) -> Dict:
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ValueError("Cannot read %s at %s: %s" % (label, path, exc)) from exc
    return data


def load_plans(path: Optional[str] = None) -> Dict:
    """Load the plan catalog, fail-closed on missing/malformed/invariant breach."""
    catalog = _read_catalog(path or PLANS_PATH, "plan catalog")
    if catalog.get("gates_always_off") is not True:
        raise ValueError("Plan catalog invariant breach: gates_always_off must be true")
    plans = catalog.get("plans")
    if not isinstance(plans, list) or not plans:
        raise ValueError("Plan catalog holds no plans")
    return catalog


def list_plans() -> List[str]:
    """Plan ids in catalog order (Foundation -> Scout -> Mover -> AutothinK)."""
    return [p["id"] for p in load_plans()["plans"]]


def get_plan(plan_id: str) -> Dict:
    """Resolve a single plan. Unknown ids fail closed with KeyError."""
    for plan in load_plans()["plans"]:
        if plan["id"] == plan_id:
            return plan
    raise KeyError("Unknown subscription plan id: %r" % (plan_id,))


def entitled_gates(plan_id: str) -> List[str]:
    """Gates a plan would permit — a subset of LIVE_GATES, never opening them."""
    gates = get_plan(plan_id).get("entitled_gates", [])
    unknown = [g for g in gates if g not in LIVE_GATES]
    if unknown:
        raise ValueError("Plan %r entitles unknown gate(s): %s" % (plan_id, unknown))
    return list(gates)


def load_manifest() -> Dict:
    return _read_catalog(MANIFEST_PATH, "profiles manifest")


def default_profile() -> str:
    return load_manifest().get("default_profile") or ""


def plan_for_profile(profile_id: str) -> Dict:
    """Resolve the plan bound to a subscriber profile. Unknown profile ids or
    a missing/unknown plan binding fail closed with KeyError (never fabricated).
    """
    manifest = load_manifest()
    for entry in manifest.get("profiles", []):
        if entry.get("id") == profile_id:
            sub = entry.get("subscription") or {}
            plan_id = sub.get("plan")
            if not plan_id:
                raise KeyError("Profile %r has no subscription plan bound" % (profile_id,))
            return get_plan(plan_id)
    raise KeyError("Unknown subscriber profile id: %r" % (profile_id,))


def subscriber_snapshot(profile_id: Optional[str] = None) -> Dict:
    """Serializable snapshot a UI can mirror (kept honest, labeled demo there).

    Contains identity, plan, entitlements, gate state (all off), and the
    operative honesty statement.
    """
    manifest = load_manifest()
    pid = profile_id or default_profile()
    entry = next((p for p in manifest.get("profiles", []) if p.get("id") == pid), None)
    if entry is None:
        raise KeyError("Unknown subscriber profile id: %r" % (pid,))
    plan = plan_for_profile(pid)
    return {
        "profile_id": pid,
        "owner": entry.get("owner", ""),
        "principal": entry.get("principal", ""),
        "kind": entry.get("kind", ""),
        "plan_id": plan["id"],
        "plan_name": plan["name"],
        "plan_tier": plan.get("tier", 1),
        "price_usd_month": plan.get("price_usd_month", 0),
        "subscription_status": (entry.get("subscription") or {}).get("status", "unknown"),
        "entitlements": entitled_gates(plan["id"]),
        "gate_state": {g: "off" for g in LIVE_GATES},
        "gates_always_off": True,
        "honesty": "A plan marks which live gates it WOULD cover. Gates are never "
                   "flipped by a plan; executing live still requires a fresh, named "
                   "operator approval per action.",
    }


def run_cli(argv: Optional[List[str]] = None) -> (int, List[str]):
    """Offline diagnostics. Returns (exit_code, lines); caller prints."""
    argv = list(sys.argv[1:] if argv is None else argv)
    lines: List[str] = []

    if not argv or argv[0] in ("-h", "--help"):
        lines.append("usage: master_brain_subscribers.py (--plans | --plan ID |")
        lines.append("       --subscribers | --snapshot [PROFILE] | --check)")
        return 0 if argv else 1, lines

    if argv[0] == "--plans":
        for pid in list_plans():
            p = get_plan(pid)
            gates = len(p.get("entitled_gates", []))
            lines.append("%-12s %-10s $%-6s tier %s  gates=%d" % (
                pid, p["name"], p.get("price_usd_month", 0), p.get("tier", 1), gates))
        lines.append("gates_always_off=%s" % load_plans().get("gates_always_off"))
        return 0, lines

    if argv[0] == "--plan":
        pid = argv[1] if len(argv) > 1 else ""
        try:
            plan = get_plan(pid)
        except KeyError as exc:
            lines.append("ERROR: %s" % exc)
            return 1, lines
        lines.append("%s — %s / $%s/mo tier %s" % (
            plan["id"], plan["name"], plan.get("price_usd_month", 0), plan.get("tier", 1)))
        lines.append(plan.get("blurb", ""))
        lines.append("entitled_gates: %s" % ", ".join(entitled_gates(pid)))
        return 0, lines

    if argv[0] == "--subscribers":
        manifest = load_manifest()
        for entry in manifest.get("profiles", []):
            plan_id = (entry.get("subscription") or {}).get("plan", "")
            status = (entry.get("subscription") or {}).get("status", "unknown")
            lines.append("%-32s plan=%-10s status=%s" % (entry.get("id", "?"), plan_id, status))
        return 0, lines

    if argv[0] == "--snapshot":
        pid = argv[1] if len(argv) > 1 else default_profile()
        try:
            lines.append(json.dumps(subscriber_snapshot(pid), indent=2, sort_keys=True))
        except KeyError as exc:
            lines.append("ERROR: %s" % exc)
            return 1, lines
        return 0, lines

    if argv[0] == "--check":
        catalog = load_plans()
        lines.append("catalog: %s plans, gates_always_off=%s" % (
            len(catalog["plans"]), catalog.get("gates_always_off")))
        bad = []
        for pid in list_plans():
            entitled_gates(pid)  # raises on unknown gate
            for g in entitled_gates(pid):
                if g not in LIVE_GATES:
                    bad.append("%s -> %s" % (pid, g))
        if bad:
            lines.append("ERROR: non-canonical entitlements: %s" % ", ".join(bad))
            return 1, lines
        for entry in load_manifest().get("profiles", []):
            plan_for_profile(entry["id"])
            lines.append("profile %s -> ok" % entry["id"])
        lines.append("all checks green")
        return 0, lines

    lines.append("unknown flag: %s" % argv[0])
    return 2, lines


if __name__ == "__main__":
    code, out = run_cli()
    for line in out:
        print(line)
    sys.exit(code)