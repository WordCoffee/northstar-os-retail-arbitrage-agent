"""Ty multi-brief pilot: p01-p05 through run_kernel(coding_agent=True)."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))
sys.path.insert(0, str(ROOT / "tools"))
from agent_kernel import content as cv  # noqa: E402
from coding_seed import seed  # noqa: E402
from proj_bench import start_server, stop_server  # noqa: E402
from tys_assistant import CodingWorkerAdapter, TysAssistant, TysStore  # noqa: E402

BRIEFS = {b["id"]: b for b in json.loads(
    (ROOT / "eval/projects/ns_proj_20.json").read_text(encoding="utf-8"))["briefs"]}
IDS = ("p01", "p02", "p03", "p04", "p05")
SPEC = {
    "p01": {"commands": [["python", "-m", "pytest", "-q"]],
            "required_files": ["fix.patch"]},
    "p02": {"required_files": ["endpoint.md"]},
    "p03": {"commands": [["python", "-m", "pytest", "-q"]],
            "required_files": ["refactor.md"]},
    "p04": {"commands": [["python", "-m", "pytest", "-q"]],
            "required_files": ["flag.md"]},
    "p05": {"commands": [["python", "-m", "py_compile", "broken.py"]],
            "required_files": ["build.log"], "min_bytes": {"build.log": 120}},
}


def model(prompt: str) -> str:
    body = json.dumps({
        "model": "northstaros-qwen3.8:27b",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 700, "temperature": 0.2, "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode()
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
                                 data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.load(r)
    return str((out.get("choices") or [{}])[0].get("message", {}).get("content") or "")


def run_one(bid: str, root: Path) -> dict:
    brief = BRIEFS[bid]
    project = root / bid
    project.mkdir(parents=True, exist_ok=True)
    seed(project, brief)
    assistant = TysAssistant(
        store=TysStore(str(project / "tys.db")),
        adapters={"coding": CodingWorkerAdapter(runner=model)},
        evidence_dir=str(project / "evidence"),
    )
    if bid == "p03":
        objective = ("Write refactor.md FIRST with the split plan, then split "
                     "report_builder.py into two modules without changing "
                     "behaviour; tests must stay green.")
    elif bid == "p05":
        objective = ("Fix the syntax error in broken.py, then rewrite build.log "
                     "with the successful build output (at least 120 characters).")
    else:
        objective = (f"{brief['goal']}. Produce `{brief['artifact']}`. "
                     f"Checks: {'; '.join(brief.get('checks') or [])}.")
    task = assistant.submit({
        "objective": objective,
        "scope": {"lanes": ["coding"], "workspace": str(project)},
        "steps": [{"lane": "coding", "objective": objective,
                   "params": {"acceptance": SPEC[bid]}}],
        "limits": {"max_steps": 3, "max_wall_s": 900},
    })
    t0 = time.time()
    run = assistant.run_kernel(task["id"], coding_agent=True)
    check = cv.validate_brief(root, brief)
    return {"id": bid, "ty_status": run.get("status"),
            "content_valid": check["valid"], "detail": check["detail"],
            "seconds": round(time.time() - t0, 1),
            "reason": run.get("reason") or ""}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default=",".join(IDS))
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    ids = [i.strip() for i in args.ids.split(",") if i.strip()]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(args.out or (ROOT / "reports/rea_probe/tys_kernel_multi" / stamp))
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(0, len(ids), 2):
        stop_server()
        if not start_server():
            print("could not start the local 27B")
            return 3
        rows.extend(run_one(bid, root) for bid in ids[i:i + 2])
    stop_server()
    out = {"mode": "ty-as-is + kernel coding tool loop (multi-brief pilot)",
           "label": "ty-as-is + kernel coding tool loop (multi-brief pilot)",
           "project_result": False, "briefs": len(rows),
           "ok": sum(1 for r in rows if r["content_valid"]), "rows": rows}
    (root / "summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"briefs": out["briefs"], "ok": out["ok"],
                      "rows": [{k: r[k] for k in ("id", "ty_status",
                                                   "content_valid", "seconds")}
                               for r in rows]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
