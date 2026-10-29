"""Ty end-to-end pilot: p01 through run_kernel(coding_agent=True), no shim."""
from __future__ import annotations

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

BRIEF = next(b for b in json.loads(
    (ROOT / "eval/projects/ns_proj_20.json").read_text(encoding="utf-8")
)["briefs"] if b["id"] == "p01")


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


def main() -> int:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = ROOT / "reports/rea_probe/tys_kernel" / stamp
    project = root / "p01"
    project.mkdir(parents=True, exist_ok=True)
    seed(project, BRIEF)
    started = False
    if not start_server():
        # It may already be listening; start_server returns False in that case.
        import socket
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", 8080)) != 0:
                print("could not start the local 27B")
                return 3
    else:
        started = True
    try:
        assistant = TysAssistant(
            store=TysStore(str(project / "tys.db")),
            adapters={"coding": CodingWorkerAdapter(runner=model)},
            evidence_dir=str(project / "evidence"),
        )
        task = assistant.submit({
            "objective": "Fix the failing test, run pytest, write fix.patch",
            "scope": {"lanes": ["coding"], "workspace": str(project)},
            "steps": [{"lane": "coding", "objective": (
                "Read calc.py and test_calc.py, fix the bug, run "
                "`python -m pytest -q`, then write a unified diff to fix.patch. "
                "The artifact is fix.patch; it must contain ---, +++ and @@."),
                "params": {"acceptance": {
                    "commands": [["python", "-m", "pytest", "-q"]],
                    "required_files": ["fix.patch"]}}}],
            "limits": {"max_steps": 3, "max_wall_s": 600},
        })
        t0 = time.time()
        run = assistant.run_kernel(task["id"], coding_agent=True)
        seconds = round(time.time() - t0, 1)
        check = cv.validate_brief(project.parent, BRIEF)
        calc = (project / "calc.py").read_text(encoding="utf-8", errors="replace")
        test = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=project,
                              capture_output=True, text=True, timeout=180)
        out = {
            "mode": "ty-as-is + kernel coding tool loop (capability pilot)",
            "label": "ty-as-is + kernel coding tool loop (capability pilot)",
            "project_result": False,
            "ty_status": run.get("status"),
            "content_valid": check["valid"],
            "content_detail": check["detail"],
            "calc_fixed": "a + b" in calc,
            "pytest_exit": test.returncode,
            "artifact_written": (project / "fix.patch").is_file(),
            "seconds": seconds,
            "summary": run.get("reason") or "",
            "task_id": task["id"],
        }
        (root / "summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(json.dumps({k: out[k] for k in (
            "ty_status", "content_valid", "calc_fixed", "pytest_exit",
            "artifact_written", "seconds")}, indent=2))
        return 0 if (check["valid"] and "a + b" in calc and test.returncode == 0) else 1
    finally:
        if started:
            stop_server()


if __name__ == "__main__":
    raise SystemExit(main())
