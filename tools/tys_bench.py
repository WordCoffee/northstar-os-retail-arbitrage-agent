"""Ty-as-is baseline: Ty's orchestrator + real coding lane, harness persists text.

This is deliberately not the kernel text lane. Ty's `run()` executes explicit
steps; the harness writes each step's returned text to the artifact path so the
content validators can inspect it. Label: ty-as-is (text persisted by harness).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))
sys.path.insert(0, str(ROOT / "tools"))
from agent_kernel import content as cv  # noqa: E402
from proj_bench import start_server, stop_server  # noqa: E402
from tys_assistant import CodingWorkerAdapter, TysAssistant, TysStore  # noqa: E402

BRIEFS = ROOT / "eval/projects/ns_proj_20.json"
LLM = "http://127.0.0.1:8080/v1/chat/completions"


def runner(prompt: str, _context) -> str:
    body = json.dumps({
        "model": "northstaros-qwen3.8:27b",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 700, "temperature": 0.2, "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode()
    req = urllib.request.Request(LLM, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.load(r)
    return str((out.get("choices") or [{}])[0].get("message", {}).get("content") or "")


def run_one(brief: dict, root: Path) -> dict:
    project = root / brief["id"]
    project.mkdir(parents=True, exist_ok=True)
    store = TysStore(str(project / "tys.db"))
    assistant = TysAssistant(
        store=store,
        adapters={"coding": CodingWorkerAdapter(runner=runner)},
        evidence_dir=str(project / "evidence"),
    )
    steps = [
        {"lane": "coding", "objective": f"Produce the content of plan.md for: {brief['goal']}. Return only the content.",
         "params": {"write": "plan.md"}},
        {"lane": "coding", "objective": f"Produce the content of {brief['artifact']} for: {brief['goal']}. Return only the content.",
         "params": {"write": brief["artifact"]}},
        {"lane": "coding", "objective": f"Produce a JSON list of checks for: {brief['goal']}. Return JSON only.",
         "params": {"write": "verification.json"}},
    ]
    task = assistant.submit({
        "objective": brief["goal"], "scope": {"lanes": ["coding"]},
        "steps": steps, "limits": {"max_steps": 5, "max_wall_s": 900},
    })
    started = time.time()
    run = assistant.run(task["id"], max_steps=5)
    elapsed = round(time.time() - started, 2)
    events = [e for e in store.events(task["id"]) if e["kind"] == "step_result"]
    written = []
    for ev in events:
        idx = int((ev.get("payload") or {}).get("index") or 0)
        if idx >= len(steps):
            continue
        write = steps[idx]["params"]["write"]
        text = str((ev.get("payload") or {}).get("detail") or "")
        path = project / write
        path.write_text(text + "\n", encoding="utf-8")
        written.append({"index": idx, "path": write, "bytes": len(text)})
    check = cv.validate_brief(project, brief) if (project / brief["artifact"]).is_file() else {
        "kind": brief.get("validator"), "valid": False, "detail": "artifact missing"}
    return {"id": brief["id"], "title": brief["title"], "ty_status": run.get("status"),
            "seconds": elapsed, "steps": len(events), "written": written,
            "content_valid": check["valid"], "content_detail": check.get("detail")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--brief", default="")
    ap.add_argument("--restart-every", type=int, default=5)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    briefs = json.loads(BRIEFS.read_text(encoding="utf-8"))["briefs"]
    if args.brief:
        briefs = [b for b in briefs if b["id"] == args.brief]
    briefs = briefs[: args.limit]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(args.out or (ROOT / "reports/rea_probe/proj_bench_tys" / stamp))
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    try:
        for i in range(0, len(briefs), max(1, args.restart_every)):
            stop_server()
            if not start_server():
                print("could not start the local 27B")
                return 3
            rows.extend(run_one(b, root) for b in briefs[i:i + max(1, args.restart_every)])
    finally:
        stop_server()
    valid = sum(1 for r in rows if r["content_valid"])
    out = {"mode": "ty-as-is-baseline",
           "label": "ty-as-is (text persisted by harness; not a quality claim)",
           "project_result": False, "briefs": len(rows),
           "content_valid": valid,
           "content_rate": round(valid / max(1, len(rows)), 3),
           "rows": rows}
    (root / "summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("briefs", "content_valid", "content_rate")},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
