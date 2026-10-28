"""NS-PROJ-20 runner — the kernel's project-execution harness.

Two modes:
  --executor dry   (default) a deterministic project skeleton; validates plan,
                   evidence coverage, retry, gate release and resume. No model.
  --executor tys   run the same briefs through Ty's lanes. Needs the local
                   models/GPU; deliberately not the default.

The dry mode is a harness test, not a claim that Ty completes the projects. The
live baseline is recorded separately with the same metric names.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from agent_kernel import (Acceptance, Budget, Kernel, Node, Policy,  # noqa: E402
                          Policy as _Policy, grant, validate_plan)
from agent_kernel.session import CheckpointStore, Journal  # noqa: E402

BRIEFS = ROOT / "eval/projects/ns_proj_20.json"
OUT_DIR = ROOT / "reports"


class DryExecutor:
    """Writes the declared artifact. It does not pretend to be an agent."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir

    def __call__(self, node: Node, plan) -> Dict[str, Any]:
        rel = str((node.inputs or {}).get("write") or "").strip()
        if not rel:
            return {"ok": False, "detail": "no artifact declared"}
        content = str((node.inputs or {}).get("content") or "")
        path = self.project_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"ok": True, "detail": f"wrote {rel}", "files": [str(path)]}


def _nodes_for(brief: Dict[str, Any], project: Path) -> List[Node]:
    plan_doc = project / "plan.md"
    artifact = project / brief["artifact"]
    verify = project / "verification.json"
    checks = list(brief.get("checks") or [])
    return [
        Node("plan", "inspect", "write the plan", lane="inspect",
             inputs={"write": "plan.md",
                     "content": f"# {brief['title']}\n\nGoal: {brief['goal']}\n\n"
                                + "\n".join(f"- [ ] {c}" for c in checks)},
             acceptance=[Acceptance("plan file exists", "artifact_exists",
                                    {"path": str(plan_doc)})]),
        Node("build", "coding", "produce the artifact", lane="coding",
             depends_on=["plan"],
             inputs={"write": brief["artifact"],
                     "content": f"artifact for {brief['id']}: {brief['goal']}"},
             acceptance=[Acceptance("artifact exists", "artifact_exists",
                                    {"path": str(artifact)})]),
        Node("verify", "inspect", "verify the artifact", lane="inspect",
             depends_on=["build"],
             inputs={"write": "verification.json",
                     "content": json.dumps({"brief": brief["id"],
                                            "checks": checks,
                                            "artifact": brief["artifact"]},
                                           indent=2)},
             acceptance=[Acceptance("verification file exists", "artifact_exists",
                                    {"path": str(verify)})]),
    ]


def _kernel(project: Path, journal_path: Path) -> Kernel:
    k = Kernel(policy=Policy(mode="auto"),
               journal=Journal(journal_path),
               checkpoints=CheckpointStore(project / ".checkpoints"))
    dry = DryExecutor(project)
    for lane in ("inspect", "coding", "browser", "creative"):
        k.executors[lane] = dry
    return k


def run_one(brief: Dict[str, Any], root: Path) -> Dict[str, Any]:
    project = root / brief["id"]
    project.mkdir(parents=True, exist_ok=True)
    started = time.time()
    journal = project / "journal.jsonl"
    k = _kernel(project, journal)
    plan = k.create_plan(goal=brief["goal"], nodes=_nodes_for(brief, project),
                         constraints=["dry harness", "no model", "no network"],
                         acceptance=[Acceptance("every node done with evidence",
                                                "plan_complete")],
                         budget=Budget(max_steps=12, max_wall_s=120))
    valid = validate_plan(plan) == []
    res = None
    if valid:
        k.submit(plan)
        k.approve(plan.plan_id, "bench")
        res = k.run(plan, grants=[grant("read", ""), grant("edit", "",
                                                           why="dry harness")])
    done = [n for n in plan.nodes if n.state == "done"]
    ev = sum(1 for n in plan.nodes if n.evidence_ids)
    return {
        "id": brief["id"], "title": brief["title"],
        "plan_valid": valid,
        "status": (res.status if res else "invalid_plan"),
        "reason": (res.reason if res else "plan validation failed"),
        "nodes": len(plan.nodes),
        "nodes_done": len(done),
        "evidence_nodes": ev,
        "evidence_coverage": round(ev / max(1, len(plan.nodes)), 3),
        "interventions": len(res.interventions) if res else 0,
        "checkpoints": len(k.checkpoints.list(plan.session_id)),
        "events": len(k.journal.read(plan.session_id)),
        "duration_s": round(time.time() - started, 3),
        "plan": plan.to_dict(),
    }


def resume_probe(root: Path) -> Dict[str, Any]:
    """A gate blocks once; release resumes without repeating the first node."""
    project = root / "_resume"
    project.mkdir(parents=True, exist_ok=True)
    k = _kernel(project, project / "journal.jsonl")
    calls: List[str] = []

    def counting(node: Node, plan) -> Dict[str, Any]:
        calls.append(node.node_id)
        return DryExecutor(project)(node, plan)

    for lane in ("inspect", "coding"):
        k.executors[lane] = counting
    plan = k.create_plan(goal="resume probe", nodes=[
        Node("a", "inspect", "first", lane="inspect",
             inputs={"write": "a.txt", "content": "a"},
             acceptance=[Acceptance("a exists", "artifact_exists",
                                    {"path": str(project / "a.txt")})]),
        Node("b", "coding", "second", lane="coding", depends_on=["a"],
             inputs={"write": "b.txt", "content": "b"},
             acceptance=[Acceptance("b exists", "artifact_exists",
                                    {"path": str(project / "b.txt")})]),
    ], acceptance=[Acceptance("all done", "plan_complete")],
        gates=[{"node_id": "b", "gate": "operator_approval", "reason": "probe"}],
        budget=Budget(max_steps=10, max_wall_s=60))
    k.submit(plan); k.approve(plan.plan_id, "bench")
    first = k.run(plan, grants=[grant("read", ""), grant("edit", "")])
    k.release("b", resolution="approved")
    second = k.run(plan, grants=[grant("read", ""), grant("edit", "")])
    return {"first_status": first.status, "second_status": second.status,
            "calls": calls, "no_duplicate": calls.count("a") == 1,
            "resumed": second.status == "complete" and calls.count("a") == 1}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--brief", default="")
    ap.add_argument("--executor", choices=["dry", "tys"], default="dry")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    if args.executor == "tys":
        print("The live Ty baseline needs the local models/GPU and is run "
              "separately; use --executor dry for the harness.")
        return 2

    data = json.loads(BRIEFS.read_text(encoding="utf-8"))
    briefs = data["briefs"]
    if args.brief:
        briefs = [b for b in briefs if b["id"] == args.brief]
    briefs = briefs[: max(1, args.limit)]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(args.out or (ROOT / "reports/rea_probe/proj_bench" / stamp))
    root.mkdir(parents=True, exist_ok=True)
    results = [run_one(b, root) for b in briefs]
    resume = resume_probe(root)

    summary = {
        "programme": "NS-PROJ-20",
        "mode": "dry-harness",
        "run_at": stamp,
        "briefs": len(results),
        "complete": sum(1 for r in results if r["status"] == "complete"),
        "valid_plans": sum(1 for r in results if r["plan_valid"]),
        "mean_evidence_coverage": round(
            sum(r["evidence_coverage"] for r in results) / max(1, len(results)), 3),
        "total_interventions": sum(r["interventions"] for r in results),
        "resume": resume,
        "results": [{k: v for k, v in r.items() if k != "plan"} for r in results],
        "note": "Dry harness only. The live Ty baseline must be run separately; "
                "these numbers are not a claim about Ty's project ability.",
    }
    (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (root / "plans.json").write_text(json.dumps(
        {r["id"]: r["plan"] for r in results}, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in (
        "briefs", "complete", "valid_plans", "mean_evidence_coverage",
        "total_interventions", "resume")}, indent=2))
    return 0 if summary["complete"] == len(results) and resume["resumed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
