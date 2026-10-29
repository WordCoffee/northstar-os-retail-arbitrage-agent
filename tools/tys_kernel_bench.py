"""Twenty-brief kernel benchmark: every brief through run_kernel(coding_agent=True).

One brief, one work order, one kernel run, one JSONL evidence record. The lane is
real — a coding node is executed by the bounded tool loop against the brief's own
seeded workspace, and the artifact is then validated by the semantic validators,
not just by keyword presence.

    python tools/tys_kernel_bench.py --all
    python tools/tys_kernel_bench.py --ids p06,p07,p08
    python tools/tys_kernel_bench.py --all --jsonl reports/rea_probe/run.jsonl

Three briefs cannot be solved by a text model and are recorded as such:

    p11  label.png      produced by `pouch_label` (composited text, never generated)
    p13  canvases.json  produced by `tools/social_canvases.mjs`
    p14  ad.mp4         produced by the FFmpeg probe

They still run through the kernel, with a deterministic tool executor in the
coding lane, and their JSONL row says `lane: "tool"`. Calling that a model pass
would be a fabrication.

Exit code: 0 only when every selected brief passes. The counts are always printed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))
sys.path.insert(0, str(ROOT / "tools"))
from agent_kernel import content as cv  # noqa: E402
from coding_seed import seed  # noqa: E402
from proj_bench import start_server, stop_server  # noqa: E402
from tys_assistant import CodingWorkerAdapter, TysAssistant, TysStore  # noqa: E402

BRIEFS = {b["id"]: b for b in json.loads(
    (ROOT / "eval/projects/ns_proj_20.json").read_text(encoding="utf-8"))["briefs"]}
ALL_IDS = tuple("p%02d" % n for n in range(1, 21))
TOOL_IDS = ("p11", "p13", "p14")
MAX_CODING_STEPS = 15

# Domain semantics, per brief. These are NOT in eval/projects/ns_proj_20.json on
# purpose: the benchmark definition stays untouched, and the quality bar this
# runner applies is visible in one table. `content.py` consumes the same shape.
SEMANTICS: Dict[str, Dict[str, Any]] = {
    "p02": {"min_sentences": 3},
    "p03": {"min_sentences": 4},
    "p04": {"min_sentences": 3},
    "p05": {"min_sentences": 2},
    "p06": {"required_keys": ["setting_key", "observed_value"]},
    "p07": {"min_sentences": 4, "required_headings": ["Host", "Grant"]},
    "p08": {"required_keys": ["run_id", "status", "checkpoint"]},
    "p09": {"required_keys": ["assertion"]},
    "p10": {"min_sentences": 4},
    "p12": {"min_sentences": 3},
    "p16": {"min_sentences": 4, "required_headings": ["Gate", "Lane"]},
    "p17": {"required_keys": ["goal", "nodes"]},
    "p18": {"min_sentences": 4, "required_headings": ["Evidence", "Next step"]},
    "p20": {"required_keys": ["evidence"]},
}

# Per-brief execution spec: what the kernel node must prove.
# The patch bar is inside acceptance on purpose: a loop that cannot see a
# malformed hunk cannot repair it (that was the original p01 defect).
DIFF_CHECK = str(ROOT / "tools" / "diff_check.py")

SPEC: Dict[str, Dict[str, Any]] = {
    "p01": {"commands": [["python", "-m", "pytest", "-q"],
                         ["python", DIFF_CHECK, "fix.patch"]],
            "required_files": ["fix.patch"]},
    "p03": {"commands": [["python", "-m", "pytest", "-q"]],
            "required_files": ["refactor.md"]},
    "p04": {"commands": [["python", "-m", "pytest", "-q"]],
            "required_files": ["flag.md"]},
    "p05": {"commands": [["python", "-m", "py_compile", "broken.py"]],
            "required_files": ["build.log"]},
    "p19": {"commands": [["python", "-c",
                          "import pathlib,sys;c=pathlib.Path('config.txt')"
                          ".read_text();n=pathlib.Path('notes.txt').read_text();"
                          "sys.exit(0 if 'retries = 3' in c and "
                          "'restarted Tuesday' in n else 1)"],
                          ["python", DIFF_CHECK, "applied.diff"]],
            "required_files": ["applied.diff"]},
    "p20": {"commands": [["python", "run.py"]],
            "required_files": ["project.json"]},
}

OBJECTIVE: Dict[str, str] = {
    "p01": "Fix the bug in calc.py so that `python -m pytest -q` passes. Do not edit "
           "test_calc.py: the assertion is correct and the source is wrong. Then "
           "write fix.patch containing the unified diff you applied. Writing the "
           "patch is not the fix — the file itself must be corrected. In the hunk "
           "header `@@ -a,b +c,d @@`, b must equal the number of context and "
           "removed lines in the body and d the number of context and added lines; "
           "count them before you write, or the patch is rejected.",
    "p02": "Add one GET route returning the ledger period, with a test, and write "
           "endpoint.md describing method, path and response shape.",
    "p03": "Write refactor.md with the split plan FIRST, then split "
           "report_builder.py into two modules without changing behaviour. "
           "pytest must stay green.",
    "p04": "Add a feature flag that defaults OFF, cover it with a test, then write "
           "flag.md explaining the default and the override.",
    "p05": "Fix the syntax error in broken.py, then rewrite build.log with the "
           "successful build output.",
    "p06": "Audit the admin setting in admin_setting.json against "
           "settings_capture.txt and write audit.json with the setting key, the "
           "observed value and a verdict. Do not claim a change was submitted.",
    "p07": "Finish the browser runbook: name the single host from hosts.txt, set "
           "the capability and an expiry at most 24 hours out, and remove every "
           "TODO. Read-only; never sign in.",
    "p08": "Write resume.json that resumes run-2026-10-27-a from ckpt-0003 "
           "without repeating completed steps, naming the blocking gate.",
    "p09": "Assert the external change in state_check.json and write state.json "
           "with a verdict. An unread value is unknown, never pass.",
    "p10": "Write digest.md summarising the two weeks in evidence/, naming the "
           "missing renders_completed figure instead of inventing it.",
    "p12": "Correct the single legal-copy defect on the package back panel and "
           "write back.md with the corrected text. Do not touch the front panel.",
    "p15": "Score listing.txt against rubric.md and write listing_audit.json. "
           "Name the dimensions that cannot be measured as unmeasured.",
    "p16": "Finish the two-lane campaign: replace every TODO, keep the gate a "
           "stop, and name one host with a read-only grant and an expiry.",
    "p17": "The plan in plan_v1.json failed verification. Write replan.json that "
           "fixes the cause (the timeline is too long) instead of retrying it.",
    "p18": "Complete the handoff so a fresh session can resume: goal, decisions, "
           "evidence paths and the next step, with no unresolved TODO.",
    "p19": "Apply both hunks in changes.diff: use the write tool to update config.txt "
           "(retries = 3) and notes.txt (render worker restarted Tuesday 09:00). "
           "Confirm the files changed, then write applied.diff containing the diff "
           "you actually applied. A diff that was never applied is not the answer.",
    "p20": "Close out the three-node project: run it, keep the run log, and write "
           "project.json with the evidence path and the node results.",
}


def model(prompt: str) -> str:
    body = json.dumps({
        "model": "northstaros-qwen3.8:27b",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1200, "temperature": 0.2, "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode()
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions",
                                 data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        out = json.load(r)
    return str((out.get("choices") or [{}])[0].get("message", {})
               .get("content") or "")


def brief_with_semantics(bid: str) -> Dict[str, Any]:
    brief = dict(BRIEFS[bid])
    if bid in SEMANTICS:
        brief["semantics"] = dict(SEMANTICS[bid])
    return brief


def _objective(bid: str) -> str:
    brief = BRIEFS[bid]
    base = OBJECTIVE.get(bid) or (
        f"{brief['goal']}. Produce `{brief['artifact']}`. "
        f"Checks: {'; '.join(brief.get('checks') or [])}.")
    sem = SEMANTICS.get(bid) or {}
    terms = list(brief.get("terms") or [])
    wants: List[str] = []
    if terms:
        wants.append("the words " + ", ".join(f"`{t}`" for t in terms))
    if sem.get("required_keys"):
        wants.append("top-level JSON keys: " + ", ".join(sem["required_keys"]))
    if sem.get("required_headings"):
        wants.append("markdown sections: " + ", ".join(sem["required_headings"]))
    if sem.get("min_sentences"):
        wants.append(f"at least {sem['min_sentences']} full sentences")
    want = (" The artifact must carry " + "; ".join(wants) + ".") if wants else ""
    return (base + want +
            f" The artifact is `{brief['artifact']}`; write it before you finish, "
            "and run the checks rather than describing them. Do not leave TODO, "
            "TBD or FIXME markers in the finished file.")


def tool_node(bid: str, project: Path) -> Dict[str, Any]:
    """The deterministic producers for the three non-text briefs."""
    if bid == "p11":
        import pouch_label as pl
        out = pl.compose(PLATE, title="ORGANIC LION'S MANE",
                         subtitle="MUSHROOM POWDER", weight="6 oz (170 g)",
                         logo_path=LOGO, icons=["organic_sprout", "non_gmo"])
        (project / "label.png").write_bytes(out["bytes"])
        return {"ok": True, "detail": "pouch_label composed", "files": ["label.png"]}
    if bid == "p13":
        r = subprocess.run(["node", "tools/social_canvases.mjs"], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=60)
        (project / "canvases.json").write_text(r.stdout, encoding="utf-8")
        return {"ok": r.returncode == 0, "detail": f"node exit {r.returncode}",
                "files": ["canvases.json"]}
    if bid == "p14":
        import shutil
        shutil.copy2(VIDEO, project / "ad.mp4")
        return {"ok": True, "detail": "clip copied from the FFmpeg probe",
                "files": ["ad.mp4"]}
    return {"ok": False, "detail": f"no tool producer for {bid}"}


PLATE = ROOT / "Northstar_backend/data/studio_generated/2e4a7ab96e9941479b068792f592864d.png"
LOGO = ROOT / "Northstar_backend/assets/brand/mogra_logo.png"
VIDEO = ROOT / "reports/rea_probe/video/ad_15s_1080x1920.mp4"


def _tool_factory(bid: str, project: Path):
    """A factory returning an executor: the kernel calls `coding_factory(node)(node, plan)`."""
    def executor(node, plan):  # noqa: ARG001 - kernel executor signature
        return tool_node(bid, project)

    def factory(node):  # noqa: ARG001 - the kernel passes the node it is about to run
        return executor
    return factory


def _run_command(project: Path, cmd: List[str]) -> Dict[str, Any]:
    try:
        r = subprocess.run([sys.executable if c == "python" else c for c in cmd],
                           cwd=project, capture_output=True, text=True, timeout=300)
        return {"cmd": cmd, "exit": r.returncode,
                "stdout": (r.stdout or "")[-2000:], "stderr": (r.stderr or "")[-1000:]}
    except Exception as exc:  # noqa: BLE001
        return {"cmd": cmd, "exit": None, "error": str(exc)[:300]}


def _provenance(project: Path, artifact: str) -> Dict[str, Any]:
    """What was actually written: hashes of the artifact and of the tree."""
    path = project / artifact
    files = {}
    for p in sorted(project.rglob("*")):
        if not p.is_file() or "__pycache__" in p.parts or p.suffix in (".db", ".pyc"):
            continue
        rel = p.relative_to(project).as_posix()
        if rel.startswith("evidence/") or rel.startswith(".pytest_cache"):
            continue
        files[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return {"artifact": artifact,
            "artifact_sha256": (hashlib.sha256(path.read_bytes()).hexdigest()
                                if path.is_file() else None),
            "artifact_bytes": path.stat().st_size if path.is_file() else 0,
            "files": files}


def _default_command(brief: Dict[str, Any]) -> List[List[str]]:
    """A real execution record for briefs that have no test suite.

    The evidence requirement is "test execution output", so a brief with nothing
    to run gets a command that actually opens and re-checks its artifact, not an
    empty field. Always a list of command lists, one shape only.
    """
    artifact = brief["artifact"]
    kind = str(brief.get("validator") or "text")
    if kind == "json":
        return [["python", "-c",
                 "import json,sys;p=sys.argv[1];d=json.load(open(p,encoding='utf-8'));"
                 "print('json ok type=%s keys=%d' % (type(d).__name__, len(d)))",
                 artifact]]
    if kind == "patch":
        return [["python", "-c",
                 "import sys,re;p=sys.argv[1];t=open(p,encoding='utf-8').read();"
                 "h=len(re.findall(r'^@@', t, re.M));"
                 "print('hunks=%d' % h);sys.exit(0 if h else 1)", artifact]]
    if kind == "text":
        return [["python", "-c",
                 "import sys,pathlib;p=pathlib.Path(sys.argv[1]);t=p.read_text("
                 "encoding='utf-8',errors='replace');"
                 "print('chars=%d lines=%d' % (len(t), t.count(chr(10))+1));"
                 "sys.exit(0 if len(t) >= 120 else 1)", artifact]]
    return []


def run_one(bid: str, root: Path, seed_root: Path) -> Dict[str, Any]:
    brief = brief_with_semantics(bid)
    project = root / bid
    project.mkdir(parents=True, exist_ok=True)
    seed(project, brief)
    lane = "tool" if bid in TOOL_IDS else "coding"

    assistant = TysAssistant(
        store=TysStore(str(project / "tys.db")),
        adapters={"coding": CodingWorkerAdapter(runner=model)},
        evidence_dir=str(project / "evidence"),
    )
    step = {"lane": "coding", "objective": _objective(bid),
            "params": {"acceptance": SPEC.get(bid, {
                "required_files": [brief["artifact"]]})}}
    task = assistant.submit({
        "objective": _objective(bid),
        "scope": {"lanes": ["coding"], "workspace": str(project)},
        "steps": [step],
        "limits": {"max_steps": 4, "max_wall_s": 900},
    })
    started = time.time()
    coding_factory = _tool_factory(bid, project) if bid in TOOL_IDS else None
    outcome: Dict[str, Any] = {}
    try:
        outcome = assistant.run_kernel(
            task["id"], coding_agent=bid not in TOOL_IDS,
            coding_max_steps=MAX_CODING_STEPS) if coding_factory is None else (
            _run_via_kernel_with_tools(assistant, task, coding_factory))
    except Exception as exc:  # noqa: BLE001 - a lane crash is a recorded result
        outcome = {"status": "error", "reason": f"{type(exc).__name__}: {exc}"[:300]}
    seconds = round(time.time() - started, 1)

    check = cv.validate_brief(root, brief, seed_dir=seed_root)
    planned = (SPEC.get(bid, {}).get("commands") or []) or _default_command(brief)
    commands = [_run_command(project, c) for c in planned]
    row = {
        "id": bid,
        "title": brief.get("title", ""),
        "lane": lane,
        "artifact": brief["artifact"],
        "kernel_status": outcome.get("status"),
        "kernel_reason": str(outcome.get("reason") or "")[:300],
        "content_valid": bool(check["valid"]),
        "validator": {"kind": check["kind"], "detail": check["detail"],
                      "checks": check.get("checks") or {}},
        "semantics": (brief.get("semantics") or {}),
        "commands": commands,
        "provenance": _provenance(project, brief["artifact"]),
        "seconds": seconds,
        "task_id": task["id"],
    }
    row["passed"] = bool(row["content_valid"] and all(
        c.get("exit") == 0 for c in commands))
    return row


def _run_via_kernel_with_tools(assistant, task: Dict[str, Any], factory) -> Dict[str, Any]:
    """Run a work order through the kernel with a deterministic tool executor.

    `run_kernel` always builds a coding agent; the three non-text briefs need the
    kernel's plan/evidence/checkpointing without a model in the loop, so the tool
    factory is passed straight through to `run_order`.
    """
    from agent_kernel.policy import grant
    from agent_kernel.tys_adapter import run_order

    order = {"id": task["id"], "title": task.get("title") or "",
             "objective": task["objective"], "scope": task.get("scope") or {},
             "steps": task.get("steps") or [], "limits": task.get("limits") or {}}
    grants = [grant("edit", minutes=240, why="benchmark tool lane"),
              grant("creative_generate", minutes=240, why="benchmark tool lane")]
    res = run_order(assistant, order, approve_by="operator", grants=grants,
                    task=task, coding_factory=factory)
    return res.to_dict()


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="run every brief p01-p20")
    ap.add_argument("--ids", default="", help="comma-separated brief ids")
    ap.add_argument("--out", default="", help="run directory")
    ap.add_argument("--jsonl", default="", help="evidence log path")
    ap.add_argument("--restart-every", type=int, default=1,
                    help="restart the local 27B every N briefs (default 1: a fresh "
                         "worker per brief, because a long brief leaves the single "
                         "llama.cpp slot holding its context and the next brief "
                         "degrades — measured 2026-10-29)")
    ap.add_argument("--no-server", action="store_true",
                    help="use a worker that is already running")
    args = ap.parse_args(argv)

    if args.all:
        ids = list(ALL_IDS)
    elif args.ids:
        ids = [i.strip() for i in args.ids.split(",") if i.strip()]
    else:
        ap.print_help()
        return 2
    unknown = [i for i in ids if i not in BRIEFS]
    if unknown:
        print(f"unknown brief ids: {', '.join(unknown)}")
        return 2

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = Path(args.out or (ROOT / "reports/rea_probe/tys_kernel_bench" / stamp))
    root.mkdir(parents=True, exist_ok=True)
    jsonl = Path(args.jsonl or (root / "evidence.jsonl"))
    jsonl.parent.mkdir(parents=True, exist_ok=True)

    seed_root = Path(tempfile.mkdtemp(prefix="ns_seed_ref_"))
    for bid in ids:  # the untouched reference tree, for the unchanged-from-seed check
        seed(seed_root / bid, BRIEFS[bid])

    rows: List[Dict[str, Any]] = []
    batch = max(1, args.restart_every)
    for i in range(0, len(ids), batch):
        if not args.no_server:
            stop_server()
            if not start_server():
                print("could not start the local 27B")
                return 3
        for bid in ids[i:i + batch]:
            row = run_one(bid, root, seed_root)
            rows.append(row)
            with jsonl.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, sort_keys=True) + "\n")
            print(f"  {bid}: {'PASS' if row['passed'] else 'FAIL'} "
                  f"({row['kernel_status']}, {row['seconds']}s, "
                  f"{row['validator']['detail']})", flush=True)
    if not args.no_server:
        stop_server()

    passed = sum(1 for r in rows if r["passed"])
    summary = {
        "mode": "kernel benchmark (run_kernel + semantic validators)",
        "briefs": len(rows), "passed": passed, "failed": len(rows) - passed,
        "rate": round(passed / max(1, len(rows)), 3),
        "model_lane": sum(1 for r in rows if r["lane"] == "coding"),
        "tool_lane": sum(1 for r in rows if r["lane"] == "tool"),
        "jsonl": str(jsonl),
        "failed_ids": [r["id"] for r in rows if not r["passed"]],
        "rows": [{k: r[k] for k in ("id", "lane", "kernel_status", "content_valid",
                                    "passed", "seconds")} for r in rows],
    }
    (root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in (
        "briefs", "passed", "failed", "rate", "model_lane", "tool_lane",
        "failed_ids", "jsonl")}, indent=2))
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
