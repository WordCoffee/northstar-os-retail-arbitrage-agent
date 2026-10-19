"""Recursive self-evolution loop — steps 1-4, proposal-only (Thorn v5.0).

    1 collect   telemetry summary + purpose-command findings
    2 analyse   recurring failure kinds, hotspots, thin evidence
    3 propose   refinement proposals for prompts / sub-agents / structure
    4 verify    a DECLARED gate runner; recorded honestly, never assumed

Step 5 of the plan (local weight / adapter updating via LoRA) is **not
implemented**. It is owner decision D2, and `weight_updates()` reports it as
blocked rather than implying a training pipeline exists.

Hard rule: **there is no apply()**. A proposal is a record for a human to accept
or reject. Silent self-modification is precisely the failure mode this design
exists to prevent, so this module is constructed so it cannot perform one.

Effects are injected (`purpose_runner`, `gate_runner`), so the loop is fast and
deterministic under test and the CLI wires the real runners explicitly.
"""
from __future__ import annotations

import os
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence

# Sibling-module imports (lane_telemetry, purpose_commands) must resolve whether
# this file is imported as part of the package or run with `-m`.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

# The repository's own gates, declared once. verify() runs what it is given and
# records "not_run" when it is given nothing — it never assumes a green gate.
GATES: Sequence[Dict[str, str]] = (
    {"id": "purpose-architecture", "why": "import cycles and wide interfaces",
     "command": "python -m Northstar_backend.purpose_commands --command optimize-architecture"},
    {"id": "purpose-performance", "why": "hot loops, blocking calls in async, unbounded reads",
     "command": "python -m Northstar_backend.purpose_commands --command refactor-performance"},
    {"id": "purpose-vectors", "why": "modules with no test reference",
     "command": "python -m Northstar_backend.purpose_commands --command expand-vectors"},
    {"id": "python-tests", "why": "unit suites",
     "command": "python -m pytest Northstar_backend -q"},
    {"id": "ui-build", "why": "the served bundle compiles",
     "command": "npm --prefix northstar-os-ui run build"},
    {"id": "shell-gate", "why": "the V3 simple-shell contract",
     "command": "node northstar-os-ui/verify-shell-v3.cjs"},
)


def declared_gates() -> List[Dict[str, str]]:
    return [dict(g) for g in GATES]


def weight_updates() -> Dict[str, Any]:
    """Step 5 of the plan. Not implemented — and says exactly why."""
    return {
        "status": "blocked",
        "reason": ("Local LoRA/QLoRA weight updating is owner decision D2. No training "
                   "pipeline exists in this repository, so nothing is trained and no "
                   "adapter is written."),
        "blocked_on": "D2",
        "what_would_be_needed": [
            "explicit approval to spend hours on the shared 16 GB GPU",
            "a training toolchain installed and pinned (ai-toolkit or equivalent)",
            "a held-out evaluation set so an adapter can be rejected on evidence",
        ],
    }


# ── 1. collect ───────────────────────────────────────────────────────────────

def collect(db, *, account_id: Optional[str] = None,
            purpose_runner: Optional[Callable[[str], Dict[str, Any]]] = None,
            telemetry_window: int = 500) -> Dict[str, Any]:
    """Gather evidence. Nothing is executed unless a runner is supplied."""
    out: Dict[str, Any] = {"telemetry": None, "purpose": {}, "skipped": []}
    try:
        import lane_telemetry as lt
        out["telemetry"] = lt.summary(db, window=telemetry_window)
    except Exception as exc:  # noqa: BLE001 - reported, never hidden
        out["telemetry"] = {"error": f"{type(exc).__name__}: {exc}"[:200]}

    if purpose_runner is None:
        out["skipped"].append("purpose commands (no runner supplied; nothing was parsed)")
    else:
        for cmd in ("optimize-architecture", "refactor-performance", "expand-vectors"):
            try:
                rep = purpose_runner(cmd) or {}
                out["purpose"][cmd] = {
                    "ok": bool(rep.get("ok")),
                    "counts": rep.get("counts") or {},
                    "findings": (rep.get("findings") or [])[:20],
                    "error": rep.get("error"),
                }
            except Exception as exc:  # noqa: BLE001
                out["purpose"][cmd] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
    return out


# ── 2. analyse ───────────────────────────────────────────────────────────────

def analyse(collected: Dict[str, Any]) -> Dict[str, Any]:
    """Turn evidence into named patterns. No pattern is asserted without evidence."""
    kinds: Dict[str, int] = {}
    hotspots: Dict[str, int] = {}
    for cmd, rep in (collected.get("purpose") or {}).items():
        for f in rep.get("findings") or []:
            k = f"{cmd}:{f.get('kind')}"
            kinds[k] = kinds.get(k, 0) + 1
            target = str(f.get("target") or "")
            if target:
                head = target.split(" <-> ")[0].split("::")[0]
                hotspots[head] = hotspots.get(head, 0) + 1

    lanes = ((collected.get("telemetry") or {}).get("lanes") or {})
    weak_lanes = [{"lane": n, "success_rate": s.get("success_rate"), "samples": s.get("samples")}
                  for n, s in lanes.items()
                  if s.get("success_rate") is not None and s["success_rate"] < 0.9]
    thin_lanes = [n for n, s in lanes.items() if not s.get("measured")]

    observations: List[str] = []
    if not lanes:
        observations.append("No lane telemetry recorded yet — routing stays unmeasured.")
    if weak_lanes:
        observations.append(f"{len(weak_lanes)} lane(s) below a 90% measured success rate.")
    if thin_lanes:
        observations.append(f"{len(thin_lanes)} lane(s) below the {((collected.get('telemetry') or {}).get('min_samples') or 'n')}-run evidence floor.")
    if not collected.get("purpose"):
        observations.append("No structural analysis was run, so no architectural pattern is claimed.")

    return {
        "finding_kinds": dict(sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0]))),
        "hotspots": [{"target": t, "findings": n}
                     for t, n in sorted(hotspots.items(), key=lambda kv: (-kv[1], kv[0]))[:10]],
        "weak_lanes": weak_lanes,
        "thin_lanes": thin_lanes,
        "observations": observations,
        "evidence_floor": ((collected.get("telemetry") or {}).get("min_samples")),
    }


# ── 3. propose ───────────────────────────────────────────────────────────────

def propose(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Refinement proposals, each traceable to the evidence that produced it."""
    proposals: List[Dict[str, Any]] = []

    for kind, count in (analysis.get("finding_kinds") or {}).items():
        if count >= 3:
            proposals.append({
                "id": f"refine-{kind.replace(':', '-')}",
                "area": "system-prompt / sub-agent",
                "change": (f"add an explicit guard to the focus prompt for '{kind.split(':')[1]}' "
                           f"and re-run the gate"),
                "rationale": f"the same finding kind appeared {count} times in one scan",
                "evidence": {"finding_kind": kind, "occurrences": count},
                "risk": "low",
                "risk_note": "a prompt addendum; no behaviour is changed by itself",
                "verification": ["python-tests", "shell-gate"],
            })

    for lane in analysis.get("weak_lanes") or []:
        proposals.append({
            "id": f"fallback-{lane['lane']}",
            "area": "routing",
            "change": (f"prefer a proven lane when '{lane['lane']}' is selected, and record "
                       f"the measured reason"),
            "rationale": (f"measured success rate {lane['success_rate']} over {lane['samples']} run(s)"),
            "evidence": lane,
            "risk": "medium",
            "risk_note": "routing changes user-visible behaviour; needs the operator",
            "verification": ["python-tests"],
        })

    for target in (analysis.get("hotspots") or [])[:3]:
        if target["findings"] >= 3:
            proposals.append({
                "id": f"split-{target['target'].replace('/', '-').replace('.', '-')}",
                "area": "architecture",
                "change": f"split or interface out '{target['target']}'",
                "rationale": f"{target['findings']} separate findings point at this module",
                "evidence": target,
                "risk": "medium",
                "risk_note": "a refactor touching shared imports",
                "verification": ["purpose-architecture", "python-tests"],
            })

    if analysis.get("thin_lanes"):
        proposals.append({
            "id": "record-more-lane-runs",
            "area": "measurement",
            "change": "keep recording lane telemetry; emit no routing policy yet",
            "rationale": ("routing needs measured runs before a policy is defensible: "
                          + ", ".join(analysis["thin_lanes"][:5])),
            "evidence": {"thin_lanes": analysis["thin_lanes"]},
            "risk": "none",
            "risk_note": "measurement only",
            "verification": [],
        })
    return proposals


# ── 4. verify ────────────────────────────────────────────────────────────────

def verify(proposals: Sequence[Dict[str, Any]],
           gate_runner: Optional[Callable[[Dict[str, str]], Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Run the gates a proposal names. Refuses to claim a verification it did not do."""
    needed = sorted({g for p in proposals for g in (p.get("verification") or [])})
    by_id = {g["id"]: g for g in GATES}
    if gate_runner is None:
        return {
            "status": "not_run",
            "reason": ("no gate runner was supplied — nothing was executed, so no gate is "
                       "claimed to have passed."),
            "gates": [{"id": g, **by_id.get(g, {})} for g in needed],
        }
    results = []
    for gid in needed:
        gate = by_id.get(gid) or {"id": gid, "why": "", "command": ""}
        try:
            res = gate_runner(gate) or {}
        except Exception as exc:  # noqa: BLE001
            res = {"status": "error", "detail": f"{type(exc).__name__}: {exc}"[:200]}
        results.append({"id": gid, "status": res.get("status", "unknown"),
                        "detail": res.get("detail", "")})
    failed = [r["id"] for r in results if r["status"] not in ("pass", "ok")]
    return {"status": "pass" if not failed else "fail", "gates": results, "failed": failed}


# ── the loop ─────────────────────────────────────────────────────────────────

def loop(db, *, account_id: Optional[str] = None,
         purpose_runner: Optional[Callable[[str], Dict[str, Any]]] = None,
         gate_runner: Optional[Callable[[Dict[str, str]], Dict[str, Any]]] = None) -> Dict[str, Any]:
    """One full evolution pass. Returns a RECORD — there is nothing to apply."""
    collected = collect(db, account_id=account_id, purpose_runner=purpose_runner)
    analysis = analyse(collected)
    proposals = propose(analysis)
    verification = verify(proposals, gate_runner=gate_runner)
    return {
        "steps": {"1_collect": collected.get("skipped") or "collected",
                  "2_analyse": analysis["observations"],
                  "3_propose": f"{len(proposals)} proposal(s)",
                  "4_verify": verification["status"]},
        "analysis": analysis,
        "proposals": proposals,
        "verification": verification,
        "weight_updates": weight_updates(),
        "applied": False,
        "note": ("Proposal-only: there is no apply(). A human accepts or rejects each "
                 "proposal; nothing in this run changed the system."),
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

def _purpose_runner(command: str) -> Dict[str, Any]:
    """Wire the real purpose commands in for CLI use."""
    import purpose_commands
    return purpose_commands.run_purpose_command(command)


def _subprocess_gate(gate: Dict[str, str]) -> Dict[str, Any]:
    """Execute one declared gate command. Only used when --run-gates is passed."""
    import os
    import subprocess
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        proc = subprocess.run(gate["command"], shell=True, capture_output=True,
                              text=True, timeout=1800, cwd=repo)
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "detail": f"{type(exc).__name__}: {exc}"[:200]}
    tail = ((proc.stdout or "")[-400:] + (proc.stderr or "")[-200:]).strip()
    return {"status": "pass" if proc.returncode == 0 else "fail",
            "detail": f"exit={proc.returncode} :: {tail[:300]}"}


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser(
        description="One self-evolution pass (proposal-only; nothing is applied).")
    ap.add_argument("--run-gates", action="store_true",
                    help="actually execute the declared gate commands (slow)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        import lane_telemetry
        db = lane_telemetry._db()
    except Exception as exc:  # noqa: BLE001
        print(f"telemetry store unavailable: {type(exc).__name__}: {exc}")
        return 1

    report = loop(db, purpose_runner=_purpose_runner,
                  gate_runner=_subprocess_gate if args.run_gates else None)

    if args.json:
        print(json.dumps(report, indent=2, default=str)[:20000])
        return 0

    print("SELF-EVOLUTION PASS - proposal only, nothing applied")
    for step, value in report["steps"].items():
        print(f"  {step}: {value}")
    for obs in report["analysis"].get("observations", []):
        print(f"  observation: {obs}")
    for p in report["proposals"]:
        print(f"  PROPOSAL [{p['risk']}] {p['id']}")
        print(f"    change:    {p['change']}")
        print(f"    rationale: {p['rationale']}")
        print(f"    evidence:  {p['evidence']}")
        print(f"    verify:    {p['verification'] or 'none'}")
    ver = report["verification"]
    print(f"  verification: {ver['status']}" + (f" - {ver.get('reason', '')}" if ver.get("reason") else ""))
    print(f"  weight updates: {report['weight_updates']['status']} "
          f"(blocked on {report['weight_updates']['blocked_on']})")
    print(f"  applied: {report['applied']} - {report['note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
