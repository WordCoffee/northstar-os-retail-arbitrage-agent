"""Provider-scoped tool suite — which tools the Master Brain may touch, per lane.

Two lanes, one answer: the LOCAL engine (this machine, free, private, never
resold) and the CLOUD engine (paid, customer-facing, commercially licensed).

``shared/model-suite.json`` answers *which model for this tier*.
``shared/provider-suite.json`` answers *which tools exist at all on this lane* —
and, more importantly, which tools are forbidden there for licence reasons.

The gate that matters: the local bench is allowed to run non-commercial
weights (FLUX.1 [dev], unverified LoRA weights) and copyleft agent runtimes
(OpenMontage under AGPL-3.0) because its output is never resold. The cloud
lane is a commercial product, so it is closed to both.

Pure and offline: no network call, no credential value read. Gate checks are
presence/flag-only. Unknown tools, providers, and licences fail closed.

CLI:
    python Northstar_backend/provider_suite.py                # active lane summary
    python Northstar_backend/provider_suite.py --provider cloud --json
    python Northstar_backend/provider_suite.py --check ultratex --provider cloud
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

PROVIDERS = ("local", "cloud")

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SUITE_PATH = os.path.join(_REPO_ROOT, "shared", "provider-suite.json")
_SERVICE_MAP_PATH = os.path.join(_REPO_ROOT, "shared", "service-model-map.json")

# Reason codes — stable strings the UI and callers may branch on.
R_OK = "ok"
R_UNKNOWN_TOOL = "unknown_tool"
R_UNKNOWN_PROVIDER = "unknown_provider"
R_NOT_IN_LANE = "not_in_lane"
R_LICENSE_NONCOMMERCIAL = "license_noncommercial"
R_WEIGHTS_UNVERIFIED = "weights_license_unverified"
R_GATE_NOT_ARMED = "gate_not_armed"
R_NOT_INSTALLED = "not_installed"

# Declared install states.
INSTALLED_STATES = ("installed", "ready", "absent")


# --- loading ----------------------------------------------------------------

def _load_json(path: str) -> Dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


SUITE: Dict = _load_json(_SUITE_PATH)
SERVICE_MAP: Dict = _load_json(_SERVICE_MAP_PATH)


def reload() -> Dict:
    """Re-read the suite file (tests, and operator edits without a restart)."""
    global SUITE, SERVICE_MAP
    SUITE = _load_json(_SUITE_PATH)
    SERVICE_MAP = _load_json(_SERVICE_MAP_PATH)
    return SUITE


def policy() -> Dict:
    return dict(SUITE.get("policy", {}) or {})


def tools() -> Dict[str, Dict]:
    """All declared tools, keyed by id. Empty dict when the file is missing."""
    raw = SUITE.get("tools", {}) or {}
    return {tid: cfg for tid, cfg in raw.items() if isinstance(cfg, dict)}


def tool_ids() -> List[str]:
    return sorted(tools())


# --- lane selection ---------------------------------------------------------

def active_provider(env: Optional[Dict[str, str]] = None) -> str:
    """The lane the operator is currently on.

    ``NORTHSTAR_PROVIDER`` wins; otherwise the operator default from
    ``shared/service-model-map.json`` (local), because this module describes
    the Master Brain's own bench, not the customer-facing default.
    """
    e = os.environ if env is None else env
    raw = str(e.get("NORTHSTAR_PROVIDER", "") or "").strip().lower()
    if raw in PROVIDERS:
        return raw
    defaults = SERVICE_MAP.get("default_provider", {}) or {}
    fallback = str(defaults.get("operator") or "local").strip().lower()
    return fallback if fallback in PROVIDERS else "local"


def lane_config(provider: str) -> Dict:
    return dict((SUITE.get("providers", {}) or {}).get(provider, {}) or {})


# --- gate checks ------------------------------------------------------------

def gate_armed(tool: Dict, env: Optional[Dict[str, str]] = None) -> Tuple[bool, Optional[str]]:
    """(armed, gate_name). Presence/flag only — no credential value is read."""
    e = os.environ if env is None else env
    gate = tool.get("gate")
    if not gate:
        return True, None
    mode = str(tool.get("gate_mode") or "armed").strip().lower()
    value = str(e.get(gate, "") or "").strip()
    if mode == "present":
        return bool(value), str(gate)
    return value == "1", str(gate)


# --- the verdict ------------------------------------------------------------

@dataclass(frozen=True)
class Verdict:
    id: str
    provider: str
    name: str
    kind: str
    allowed: bool          # lane + licence permit it here
    installed: bool        # present on this machine right now
    usable: bool           # allowed AND installed AND gate armed
    reason: str            # first blocking reason, or "ok"
    gate: Optional[str] = None
    license: Optional[str] = None
    cost: Optional[str] = None
    network: Optional[bool] = None
    unlocks: Optional[str] = None
    notes: Optional[str] = None


def _license_block(tool: Dict, provider: str) -> Optional[str]:
    """Return the reason this tool may not run on this lane, or None."""
    if provider != "cloud":
        return None
    pol = policy()
    # Explicit per-tool cloud block (e.g. AGPL network copyleft) wins.
    block = tool.get("cloud_block")
    if block and tool.get("cloud_ok") is False:
        return str(block)
    if tool.get("commercial_ok") is False and pol.get("cloud_requires_commercial_ok", True):
        if str(tool.get("weights_license", "")).strip().lower() in ("unverified", "unknown"):
            return R_WEIGHTS_UNVERIFIED
        return R_LICENSE_NONCOMMERCIAL
    if str(tool.get("weights_license", "")).strip().lower() in ("unverified", "unknown") and \
            pol.get("unknown_weights_license_blocks_cloud", True):
        return R_WEIGHTS_UNVERIFIED
    return None


def verify(tool_id: str, provider: Optional[str] = None,
           confirmed: Optional[Iterable[str]] = None,
           env: Optional[Dict[str, str]] = None) -> Verdict:
    """Resolve one tool on one lane. Never raises; unknown input fails closed.

    ``confirmed`` may add tool ids the caller has just proved present (the same
    pattern ``model_router.catalog(installed_local)`` uses for Ollama tags).
    """
    prov = (provider or active_provider(env)).strip().lower()
    tid = str(tool_id or "").strip()
    cfg = tools().get(tid)

    if prov not in PROVIDERS:
        return Verdict(tid, prov, "", "", False, False, False, R_UNKNOWN_PROVIDER)
    if not cfg:
        return Verdict(tid, prov, "", "", False, False, False, R_UNKNOWN_TOOL)

    base = dict(
        id=tid,
        provider=prov,
        name=str(cfg.get("name") or tid),
        kind=str(cfg.get("kind") or "unknown"),
        gate=cfg.get("gate"),
        license=cfg.get("license"),
        cost=cfg.get("cost"),
        network=cfg.get("network"),
        unlocks=cfg.get("unlocks"),
        notes=cfg.get("notes"),
    )

    lanes = [str(x).strip().lower() for x in (cfg.get("lanes") or [])]

    # Licence is checked BEFORE lane membership on purpose: if a non-commercial
    # tool ever gets listed on the cloud lane by mistake, the licence still
    # blocks it — and the reason says so instead of a vague "not_in_lane".
    block = _license_block(cfg, prov)
    if block:
        return Verdict(allowed=False, installed=False, usable=False,
                       reason=block, **base)

    if prov not in lanes:
        return Verdict(allowed=False, installed=False, usable=False,
                       reason=R_NOT_IN_LANE, **base)

    declared = str(cfg.get("installed") or "ready").strip().lower()
    confirmed_set = set(confirmed or ())
    installed = declared == "installed" or tid in confirmed_set

    armed, _ = gate_armed(cfg, env)
    if not installed:
        reason = R_NOT_INSTALLED
    elif not armed:
        reason = R_GATE_NOT_ARMED
    else:
        reason = R_OK

    return Verdict(allowed=True, installed=installed,
                   usable=installed and armed, reason=reason, **base)


def suite(provider: Optional[str] = None,
          confirmed: Optional[Iterable[str]] = None,
          env: Optional[Dict[str, str]] = None) -> Dict[str, object]:
    """The full lane view: what is usable, what is blocked, and why."""
    prov = (provider or active_provider(env)).strip().lower()
    if prov not in PROVIDERS:
        return {"provider": prov, "known": False, "reason": R_UNKNOWN_PROVIDER,
                "usable": [], "blocked": [], "counts": {}}

    confirmed_set = set(confirmed or ())
    usable: List[Dict] = []
    blocked: List[Dict] = []
    for tid in tool_ids():
        v = verify(tid, prov, confirmed=confirmed_set, env=env)
        card = {
            "id": v.id, "name": v.name, "kind": v.kind, "reason": v.reason,
            "license": v.license, "cost": v.cost, "gate": v.gate,
            "network": v.network, "unlocks": v.unlocks, "notes": v.notes,
        }
        if v.usable:
            usable.append(card)
        else:
            blocked.append(card)

    return {
        "provider": prov,
        "known": True,
        "display": lane_config(prov).get("display"),
        "commercial_use": lane_config(prov).get("commercial_use"),
        "usable": sorted(usable, key=lambda c: (c["kind"], c["id"])),
        "blocked": sorted(blocked, key=lambda c: (c["reason"], c["id"])),
        "counts": {
            "usable": len(usable),
            "blocked": len(blocked),
            "total": len(usable) + len(blocked),
        },
    }


def catalog(active: Optional[str] = None,
            confirmed: Optional[Iterable[str]] = None,
            env: Optional[Dict[str, str]] = None) -> Dict[str, object]:
    """Both lanes + the active one — the shape the UI reads."""
    act = (active or active_provider(env)).strip().lower()
    return {
        "schema": SUITE.get("$schema"),
        "active_provider": act,
        "providers": list(PROVIDERS),
        "policy": policy(),
        "lanes": {p: suite(p, confirmed=confirmed, env=env) for p in PROVIDERS},
    }


def explain(tool_id: str, provider: Optional[str] = None,
            confirmed: Optional[Iterable[str]] = None,
            env: Optional[Dict[str, str]] = None) -> str:
    """One-line human explanation — used by the CLI and the brain itself."""
    v = verify(tool_id, provider, confirmed=confirmed, env=env)
    if v.usable:
        return f"{v.name} · available on {v.provider} ({v.license}, {v.cost})"
    if v.reason == R_OK:
        return f"{v.name} · allowed on {v.provider} but not usable"
    return f"{v.name} · NOT available on {v.provider} — {v.reason}"


# --- CLI --------------------------------------------------------------------

def _render(payload: Dict) -> str:
    lines = [f"lane: {payload['active_provider']}"]
    for prov in PROVIDERS:
        lane = (payload.get("lanes", {}) or {}).get(prov, {})
        counts = lane.get("counts", {}) or {}
        lines.append(f"  {prov}: {counts.get('usable', 0)} usable / "
                     f"{counts.get('blocked', 0)} blocked")
        for card in lane.get("usable", []):
            lines.append(f"    + {card['id']} ({card['kind']})")
        for card in lane.get("blocked", []):
            lines.append(f"    - {card['id']} ({card['kind']}): {card['reason']}")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Provider-scoped tool suite")
    ap.add_argument("--provider", choices=list(PROVIDERS), default=None)
    ap.add_argument("--check", default=None, help="explain one tool id")
    ap.add_argument("--confirmed", default="", help="comma-separated ids proved present")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    confirmed = [x.strip() for x in args.confirmed.split(",") if x.strip()]
    if args.check:
        print(explain(args.check, args.provider, confirmed=confirmed))
        return 0

    payload = catalog(active=args.provider, confirmed=confirmed)
    print(json.dumps(payload, indent=2) if args.json else _render(payload))
    return 0


if __name__ == "__main__":
    sys.exit(main())
