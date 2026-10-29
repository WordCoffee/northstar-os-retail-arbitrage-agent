"""NS-PROJ-20 runner.

Modes:
  --executor dry   deterministic skeleton; validates plan/evidence/resume mechanics.
  --executor live  the local Qwen3.8-27B writes each node's content; the harness
                   persists it. This is a *live lane baseline*: it measures
                   completion and latency, not project quality.
  --executor tys   placeholder for a future Ty-as-is run (needs explicit wiring).

No mode touches the network except the local 27B on 127.0.0.1:8080.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import statistics
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from agent_kernel import (Acceptance, Budget, Kernel, Node, Policy,  # noqa: E402
                          grant, validate_plan)
from agent_kernel.artifacts import strip_markdown_fence  # noqa: E402
from agent_kernel.session import CheckpointStore, Journal  # noqa: E402

BRIEFS = ROOT / "eval/projects/ns_proj_20.json"
LLM_BASE = "http://127.0.0.1:8080"
LLM_MODEL = "northstaros-qwen3.8:27b"


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


class LiveExecutor:
    """One local 27B call per node; the harness persists the response."""

    def __init__(self, project_dir: Path, brief: Dict[str, Any]):
        self.project_dir = project_dir
        self.brief = brief
        self.calls: List[Dict[str, Any]] = []

    def __call__(self, node: Node, plan) -> Dict[str, Any]:
        rel = str((node.inputs or {}).get("write") or "").strip()
        if not rel:
            return {"ok": False, "detail": "no artifact declared"}
        prompt = self._prompt(node)
        started = time.time()
        try:
            out = self._post(prompt)
        except Exception as exc:  # noqa: BLE001 - a transport failure is a result
            self.calls.append({"node": node.node_id, "ok": False,
                               "seconds": round(time.time() - started, 2),
                               "error": str(exc)[:200]})
            return {"ok": False, "detail": f"model call failed: {str(exc)[:200]}"}
        seconds = round(time.time() - started, 2)
        choice = (out.get("choices") or [{}])[0] or {}
        text = str((choice.get("message") or {}).get("content") or "").strip()
        usage = out.get("usage") or {}
        self.calls.append({"node": node.node_id, "ok": bool(text),
                           "seconds": seconds, "chars": len(text),
                           "finish": choice.get("finish_reason"),
                           "completion_tokens": usage.get("completion_tokens")})
        if not text:
            return {"ok": False, "detail": "the model returned no content",
                    "data": {"finish": choice.get("finish_reason")}}
        clean, fenced = strip_markdown_fence(text)
        path = self.project_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(clean + ("\n" if clean and not clean.endswith("\n") else ""),
                        encoding="utf-8")
        self.calls[-1]["fence_stripped"] = fenced
        self.calls[-1]["chars"] = len(clean)
        return {"ok": True, "detail": clean[:300], "files": [str(path)],
                "data": {"seconds": seconds, "chars": len(clean),
                         "fence_stripped": fenced, "usage": usage}}

    def _prompt(self, node: Node) -> str:
        goal = str(self.brief.get("goal") or "")
        checks = "; ".join(self.brief.get("checks") or [])
        artifact = str(self.brief.get("artifact") or "")
        if node.node_id == "plan":
            return ("Produce a concise execution plan for this project. "
                    f"Goal: {goal}. Checks: {checks}. "
                    "Return markdown with 3-5 steps and no preamble.")
        if node.node_id == "verify":
            return ("Return a JSON array of 3-5 machine-checkable checks for this "
                    f"project. Goal: {goal}. Artifact: {artifact}. "
                    "Return JSON only.")
        return ("Produce the content of the artifact "
                f"`{artifact}` for this project. Goal: {goal}. Checks: {checks}. "
                "Return only the artifact content. If a patch is requested, return "
                "a unified diff. No commentary.")

    def _post(self, prompt: str) -> Dict[str, Any]:
        body = json.dumps({
            "model": LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 700,
            "temperature": 0.2,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }).encode("utf-8")
        req = urllib.request.Request(f"{LLM_BASE}/v1/chat/completions", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)


def _nodes_for(brief: Dict[str, Any], project: Path, *, live: bool) -> List[Node]:
    plan_doc = project / "plan.md"
    artifact = project / brief["artifact"]
    verify = project / "verification.json"
    checks = list(brief.get("checks") or [])

    def acc(path: Path, kind: str, terms=None, min_chars: int = 120) -> List[Acceptance]:
        if not live:
            return [Acceptance("artifact exists", "artifact_exists",
                               {"path": str(path)})]
        verifier = {"text": "text_valid", "json": "json_valid",
                    "patch": "patch_valid", "label": "label_valid",
                    "ad": "ad_valid", "social": "social_valid",
                    "aplus": "aplus_valid"}[kind]
        params: Dict[str, Any] = {"path": str(path)}
        if terms:
            params["terms"] = list(terms)
        if kind == "text":
            params["min_chars"] = min_chars
        return [Acceptance(f"{kind} content valid", verifier, params)]

    kind = str(brief.get("validator") or "text")
    terms = list(brief.get("terms") or [])
    return [
        Node("plan", "inspect", "write the plan", lane="inspect",
             inputs={"write": "plan.md",
                     "content": f"# {brief['title']}\n\nGoal: {brief['goal']}\n\n"
                                + "\n".join(f"- [ ] {c}" for c in checks)},
             acceptance=acc(plan_doc, "text", min_chars=80)),
        Node("build", "coding", "produce the artifact", lane="coding",
             depends_on=["plan"],
             inputs={"write": brief["artifact"],
                     "content": f"artifact for {brief['id']}: {brief['goal']}"},
             acceptance=acc(artifact, kind, terms,
                            int(brief.get("min_chars") or 120))),
        Node("verify", "inspect", "verify the artifact", lane="inspect",
             depends_on=["build"],
             inputs={"write": "verification.json",
                     "content": json.dumps({"brief": brief["id"],
                                            "checks": checks,
                                            "artifact": brief["artifact"]},
                                           indent=2)},
             acceptance=acc(verify, "json")),
    ]


def _kernel(project: Path, journal_path: Path, executor=None) -> Kernel:
    k = Kernel(policy=Policy(mode="auto"),
               journal=Journal(journal_path),
               checkpoints=CheckpointStore(project / ".checkpoints"))
    chosen = executor or DryExecutor(project)
    for lane in ("inspect", "coding", "browser", "creative"):
        k.executors[lane] = chosen
    return k


def run_one(brief: Dict[str, Any], root: Path, *, live: bool = False) -> Dict[str, Any]:
    project = root / brief["id"]
    project.mkdir(parents=True, exist_ok=True)
    started = time.time()
    executor = LiveExecutor(project, brief) if live else DryExecutor(project)
    k = _kernel(project, project / "journal.jsonl", executor)
    plan = k.create_plan(
        goal=brief["goal"], nodes=_nodes_for(brief, project, live=live),
        constraints=["live lane baseline" if live else "harness validation",
                     "no network beyond the local model" if live else "no model"],
        acceptance=[Acceptance("every node done with evidence", "plan_complete")],
        budget=Budget(max_steps=12, max_wall_s=1800 if live else 120))
    valid = validate_plan(plan) == []
    res = None
    if valid:
        k.submit(plan)
        k.approve(plan.plan_id, "bench")
        res = k.run(plan, grants=[grant("read", ""), grant("edit", "",
                                                           why="benchmark")])
    done = [n for n in plan.nodes if n.state == "done"]
    ev = sum(1 for n in plan.nodes if n.evidence_ids)
    calls = getattr(executor, "calls", [])
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
        "model_calls": calls,
        "model_seconds": [c["seconds"] for c in calls if c.get("seconds")],
        "model_chars": sum(int(c.get("chars") or 0) for c in calls),
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


def _port_open(host: str = "127.0.0.1", port: int = 8080) -> bool:
    with socket.socket() as s:
        s.settimeout(1.0)
        return s.connect_ex((host, port)) == 0


SERVER_BIN = Path.home() / ".config/northstar-llm/bin/llama-server.exe"
SERVER_MODEL = (Path.home() / "models/northstaros-qwen3.8/"
                "Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf")


def _server_pid() -> int | None:
    try:
        import psutil
    except Exception:  # noqa: BLE001
        return None
    for c in psutil.net_connections(kind="inet"):
        if c.laddr and c.laddr.port == 8080 and c.status == "LISTEN":
            return c.pid
    return None


def stop_server() -> None:
    pid = _server_pid()
    if not pid:
        return
    try:
        import psutil
        p = psutil.Process(pid)
        p.terminate()
        p.wait(timeout=20)
    except Exception:  # noqa: BLE001
        pass
    for _ in range(20):
        if not _port_open():
            return
        time.sleep(0.5)


def _healthy() -> bool:
    try:
        with urllib.request.urlopen(f"{LLM_BASE}/health", timeout=3) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def start_server(timeout_s: int = 180) -> bool:
    """Ensure the Ty worker is serving. A worker that is already up counts.

    The old version returned False whenever the port answered, so a harness run
    that followed a manual `scripts/start-northstar-llm.ps1` reported "could not
    start the local 27B" while the model was loaded and healthy one port away.
    """
    if _port_open():
        return _healthy()
    if not SERVER_BIN.is_file() or not SERVER_MODEL.is_file():
        return False
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    # Same profile as scripts/start-northstar-llm.ps1: 64K context on q4_0 KV with
    # MTP. The old 8192/q8_0 line measured a configuration that does not exist in
    # production. 65536 is a measured ceiling on this card, not a preference.
    subprocess.Popen(
        [str(SERVER_BIN), "-m", str(SERVER_MODEL),
         "--alias", "northstaros-qwen3.8:27b", "-ngl", "99",
         "-c", "65536", "-fa", "on", "-ctk", "q4_0", "-ctv", "q4_0",
         "-np", "1", "--jinja",
         "--spec-type", "draft-mtp", "--spec-draft-n-max", "4",
         "--host", "127.0.0.1", "--port", "8080",
         "--temp", "0.2"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=flags)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if _port_open() and _healthy():
            return True
        time.sleep(2)
    return False


def _pct(values: List[float], p: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    k = max(0, min(len(values) - 1, int(round((p / 100.0) * (len(values) - 1)))))
    return round(values[k], 2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--brief", default="")
    ap.add_argument("--executor", choices=["dry", "live", "tys"], default="dry")
    ap.add_argument("--restart-every", type=int, default=0,
                    help="restart the local 27B every N briefs (live mode)")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    if args.executor == "tys":
        print("Ty-as-is execution needs explicit step wiring; use dry or live.")
        return 2
    if args.executor == "live" and not _port_open() and not args.restart_every:
        print("The local 27B is not listening on 127.0.0.1:8080. Start it with "
              "scripts/start-northstar-llm.ps1, then rerun.")
        return 3

    data = json.loads(BRIEFS.read_text(encoding="utf-8"))
    briefs = data["briefs"]
    if args.brief:
        briefs = [b for b in briefs if b["id"] == args.brief]
    briefs = briefs[: max(1, args.limit)]

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix = "proj_bench_live" if args.executor == "live" else "proj_bench"
    root = Path(args.out or (ROOT / f"reports/rea_probe/{prefix}" / stamp))
    root.mkdir(parents=True, exist_ok=True)
    results = []
    server_restarts = 0
    if args.executor == "live" and args.restart_every and args.restart_every > 0:
        for i in range(0, len(briefs), args.restart_every):
            batch = briefs[i:i + args.restart_every]
            stop_server()
            if start_server():
                server_restarts += 1
            results.extend(run_one(b, root, live=True) for b in batch)
        stop_server()
    else:
        results = [run_one(b, root, live=args.executor == "live") for b in briefs]
    resume = resume_probe(root)

    secs = [s for r in results for s in r.get("model_seconds", [])]
    chars = sum(int(r.get("model_chars") or 0) for r in results)
    summary = {
        "programme": "NS-PROJ-20",
        "mode": "live-text-lane-baseline" if args.executor == "live" else "harness-validation",
        "label": ("live text-lane baseline — harness persists model text; content "
                  "quality unverified" if args.executor == "live"
                  else "harness validation — not a project result"),
        "project_result": False,
        "quality_claim": False,
        "run_at": stamp,
        "briefs": len(results),
        "complete": sum(1 for r in results if r["status"] == "complete"),
        "valid_plans": sum(1 for r in results if r["plan_valid"]),
        "mean_evidence_coverage": round(
            sum(r["evidence_coverage"] for r in results) / max(1, len(results)), 3),
        "total_interventions": sum(r["interventions"] for r in results),
        "model_calls": len(secs),
        "model_chars": chars,
        "server_restarts": server_restarts,
        "fence_stripped": sum(1 for r in results for c in r.get("model_calls", [])
                              if c.get("fence_stripped")),
        "node_seconds_p50": _pct(secs, 50),
        "node_seconds_p95": _pct(secs, 95),
        "resume_mechanics": resume,
        "results": [{k: v for k, v in r.items() if k != "plan"} for r in results],
        "note": ("Live text-lane baseline only: the local 27B produced text and "
                 "the harness persisted it. Artifact existence is checked; content "
                 "quality is not." if args.executor == "live"
                 else "Harness validation only. Not a claim about Ty's project ability."),
    }
    if args.executor == "live":
        summary["thresholds_from_this_run"] = {
            "completion_rate": round(summary["complete"] / max(1, len(results)), 3),
            "evidence_coverage": summary["mean_evidence_coverage"],
            "node_seconds_p50": summary["node_seconds_p50"],
            "node_seconds_p95": summary["node_seconds_p95"],
            "quality_thresholds": "not set — machine content validators are not implemented",
        }
    (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (root / "plans.json").write_text(json.dumps(
        {r["id"]: r["plan"] for r in results}, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in (
        "mode", "label", "briefs", "complete", "valid_plans",
        "mean_evidence_coverage", "total_interventions", "model_calls",
        "node_seconds_p50", "node_seconds_p95", "resume_mechanics")}, indent=2))
    return 0 if summary["complete"] == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
