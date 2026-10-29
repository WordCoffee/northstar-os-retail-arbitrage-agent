"""First coding-agent increment: p01, p02, p05 against the local 27B."""
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
from agent_kernel.coding_agent import CodingAgent  # noqa: E402
from proj_bench import start_server, stop_server  # noqa: E402

BRIEFS = {b["id"]: b for b in json.loads(
    (ROOT / "eval/projects/ns_proj_20.json").read_text(encoding="utf-8"))["briefs"]}
IDS = ("p01", "p02", "p05")


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


def seed(project: Path, bid: str) -> None:
    project.mkdir(parents=True, exist_ok=True)
    if bid == "p01":
        (project / "calc.py").write_text(
            "def add(a, b):\n    return a - b\n", encoding="utf-8")
        (project / "test_calc.py").write_text(
            "from calc import add\n\n\ndef test_add():\n"
            "    assert add(2, 3) == 5\n", encoding="utf-8")
    elif bid == "p05":
        (project / "broken.py").write_text("def f(:\n    return 1\n", encoding="utf-8")
    else:
        (project / "README.md").write_text(
            "# Demo service\n\nThe service has no endpoint yet.\n", encoding="utf-8")


def task_for(brief: dict) -> str:
    bid = brief["id"]
    if bid == "p01":
        return ("A failing test exists in test_calc.py. Read calc.py, fix the bug, run "
                "`python -m pytest -q`, then write a unified diff to `fix.patch`. "
                "The artifact is fix.patch and it must contain ---, +++ and @@ lines.")
    if bid == "p05":
        return ("broken.py fails `python -m py_compile broken.py`. Read it, fix the "
                "syntax error, prove the build with py_compile, then write the build "
                "output/evidence to `build.log` (at least 120 characters).")
    return ("Add a read-only endpoint design to `endpoint.md`: name the route, the GET "
            "method and the JSON response shape. The artifact is endpoint.md.")


def acceptance_for(project: Path, brief: dict):
    def check():
        # project is <folder>/<id>; validate_brief expects <folder>/<id>/<artifact>
        r = cv.validate_brief(project.parent, brief)
        return r["valid"], r["detail"]
    return check


def run_one(bid: str, root: Path) -> dict:
    brief = BRIEFS[bid]
    folder = root
    project = root / bid
    seed(project, bid)
    started = time.time()
    result = CodingAgent(project, model, max_steps=12, max_repairs=1,
                         acceptance=acceptance_for(project, brief),
                         required_artifact=brief["artifact"]).run(task_for(brief))
    check = cv.validate_brief(folder, brief)
    extra = True
    detail = check["detail"]
    if bid == "p01":
        calc = (project / "calc.py").read_text(encoding="utf-8", errors="replace")
        test = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=project,
                              capture_output=True, text=True, timeout=120)
        extra = ("a + b" in calc and test.returncode == 0)
        detail = f"{detail}; calc_fixed={'a + b' in calc}; pytest={test.returncode}"
    elif bid == "p05":
        comp = subprocess.run([sys.executable, "-m", "py_compile", "broken.py"],
                              cwd=project, capture_output=True, text=True, timeout=60)
        extra = comp.returncode == 0
        detail = f"{detail}; py_compile={comp.returncode}"
    return {"id": bid, "ok": bool(result.ok and check["valid"] and extra),
            "agent_ok": result.ok, "content_valid": check["valid"],
            "extra": extra, "steps": result.steps, "seconds": round(time.time() - started, 1),
            "summary": result.summary, "detail": detail,
            "files": result.files, "error": result.error}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(args.out or (ROOT / "reports/rea_probe/coding_bench" / stamp))
    root.mkdir(parents=True, exist_ok=True)
    if not start_server():
        print("could not start the local 27B")
        return 3
    try:
        rows = [run_one(bid, root) for bid in IDS]
    finally:
        stop_server()
    out = {"mode": "coding-agent-pilot", "briefs": len(rows),
           "ok": sum(1 for r in rows if r["ok"]), "rows": rows}
    (root / "summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"briefs": out["briefs"], "ok": out["ok"],
                      "rows": [{k: r[k] for k in ("id", "ok", "agent_ok",
                                                   "content_valid", "extra", "steps",
                                                   "seconds", "error")} for r in rows]},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
