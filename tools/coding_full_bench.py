"""Hybrid 20-brief run: coding agent for text/code, tools for label/social/ad."""
from __future__ import annotations

import argparse
import json
import shutil
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

try:
    from coding_seed import seed  # type: ignore
except Exception:  # noqa: BLE001 - the seed agent may not have landed yet
    from coding_bench import seed  # type: ignore

BRIEFS = json.loads((ROOT / "eval/projects/ns_proj_20.json").read_text(
    encoding="utf-8"))["briefs"]
TOOL = {"p11", "p13", "p14"}
PLATE = ROOT / "Northstar_backend/data/studio_generated/2e4a7ab96e9941479b068792f592864d.png"
LOGO = ROOT / "Northstar_backend/assets/brand/mogra_logo.png"
VIDEO = ROOT / "reports/rea_probe/video/ad_15s_1080x1920.mp4"


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


def task_for(brief: dict) -> str:
    if brief["id"] == "p03":
        return ("Write `refactor.md` FIRST with the split plan, then split "
                "report_builder.py into two modules without changing behaviour. "
                "Tests must stay green: `python -m pytest -q`.")
    if brief["id"] == "p04":
        return ("Write `flag.md` FIRST describing the default-off flag, then add "
                "the flag to config.py and cover both states in test_config.py. "
                "Run `python -m pytest -q`.")
    if brief["id"] == "p20":
        return ("Write `project.json` FIRST with the three nodes and their "
                "evidence, then run `python run.py` and include the result.")
    return (f"{brief['goal']} Produce the artifact `{brief['artifact']}` in the "
            f"workspace. Checks: {'; '.join(brief.get('checks') or [])}. "
            "Use the tools. Run tests if they exist. When the artifact and checks "
            "pass, call finish.")


def acceptance_for(project: Path, brief: dict):
    def check():
        r = cv.validate_brief(project.parent, brief)
        ok = r["valid"]
        detail = r["detail"]
        if brief["id"] in ("p01", "p03", "p04"):
            test = subprocess.run([sys.executable, "-m", "pytest", "-q"],
                                  cwd=project, capture_output=True, text=True,
                                  timeout=180)
            ok = ok and test.returncode == 0
            detail += f"; pytest={test.returncode}"
        if brief["id"] == "p05":
            comp = subprocess.run([sys.executable, "-m", "py_compile", "broken.py"],
                                  cwd=project, capture_output=True, text=True,
                                  timeout=60)
            ok = ok and comp.returncode == 0
            detail += f"; py_compile={comp.returncode}"
        return ok, detail
    return check


def tool_node(brief: dict, project: Path) -> None:
    if brief["id"] == "p11":
        import pouch_label as pl
        out = pl.compose(PLATE, title="ORGANIC LION'S MANE",
                         subtitle="MUSHROOM POWDER", weight="6 oz (170 g)",
                         logo_path=LOGO, icons=["organic_sprout", "non_gmo"])
        (project / "label.png").write_bytes(out["bytes"])
    elif brief["id"] == "p13":
        r = subprocess.run(["node", "tools/social_canvases.mjs"], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=60)
        (project / "canvases.json").write_text(r.stdout, encoding="utf-8")
    elif brief["id"] == "p14":
        shutil.copy2(VIDEO, project / "ad.mp4")


def run_one(brief: dict, root: Path) -> dict:
    project = root / brief["id"]
    project.mkdir(parents=True, exist_ok=True)
    seed(project, brief)
    started = time.time()
    if brief["id"] in TOOL:
        tool_node(brief, project)
        result = None
        steps = 1
    else:
        result = CodingAgent(project, model, max_steps=12, max_repairs=1,
                             acceptance=acceptance_for(project, brief)).run(
                                 task_for(brief))
        steps = result.steps
    check = cv.validate_brief(root, brief)
    return {"id": brief["id"], "ok": check["valid"],
            "content_valid": check["valid"], "detail": check["detail"],
            "steps": steps, "seconds": round(time.time() - started, 1),
            "agent_ok": (result.ok if result else True),
            "error": (result.error if result else "")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--restart-every", type=int, default=4)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(args.out or (ROOT / "reports/rea_probe/coding_full" / stamp))
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(0, len(BRIEFS), max(1, args.restart_every)):
        batch = BRIEFS[i:i + max(1, args.restart_every)]
        if any(b["id"] not in TOOL for b in batch):
            stop_server()
            if not start_server():
                print("could not start the local 27B")
                return 3
        rows.extend(run_one(b, root) for b in batch)
    stop_server()
    ok = sum(1 for r in rows if r["ok"])
    out = {"mode": "hybrid-coding-tool-pilot", "briefs": len(rows),
           "ok": ok, "rate": round(ok / max(1, len(rows)), 3), "rows": rows,
           "note": "Coding agent for text/code, tools for p11/p13/p14."}
    (root / "summary.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"briefs": out["briefs"], "ok": out["ok"],
                      "rate": out["rate"],
                      "failed": [r["id"] for r in rows if not r["ok"]]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
