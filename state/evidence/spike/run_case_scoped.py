"""POST-HOC arm B: the same lane, with the loop's own task-scoped toolset.

This is NOT part of the M0.5 matrix. It exists because every one of the 15
matrix candidates failed the same way: it called `list .` and never read the
target file. `allowed_tools` is a supported CodingAgent option that (a) removes
the actions the task cannot use and (b) switches the prompt to the task-scoped
branch, which drops the 60-entry repo-root tree that kept re-anchoring the model.

Same model, same cases, same gates. Only that one knob differs, so the comparison
attributes the matrix's zero to either the model or the lane's default surface.

    python state/evidence/spike/run_case_scoped.py --case S2 --candidate 1

What it does, in order:
  1. hard-reset the spike worktree to HEAD (so every candidate starts from the
     committed baseline, never from the previous candidate's work);
  2. copy the hidden gates into `<worktree>/.spike_acceptance/` - outside the
     task's write scope, so the candidate can neither edit nor game them;
  3. write the task contract (objective + scopes + acceptance commands);
  4. run `scripts/ty_task_runner.py` with the LOCAL Ollama model, under a hard
     wall-clock cap; a hung call is recorded as a failed candidate, never retried;
  5. judge INDEPENDENTLY of the agent's own claim: diff, gate exit, targeted test
     file exit, and whether the diff touches the module the problem lives in;
  6. write everything to state/evidence/spike/<slug>/cand<N>/.

The product tree is never touched: all writes land in the git worktree under
%TEMP%, and only evidence is written back into the repo.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SPIKE = ROOT / "state" / "evidence" / "spike"
HARNESS = SPIKE / "harness"
WORKTREE = Path(os.environ.get("TEMP", ".")) / "ns-spike-wt"
MODEL = os.environ.get("SPIKE_MODEL", "qwen3:8b")
CAP_S = int(os.environ.get("SPIKE_CAP_S", "600"))
MAX_STEPS = int(os.environ.get("SPIKE_MAX_STEPS", "12"))

sys.path.insert(0, str(HARNESS))
from cases import CASES  # noqa: E402

#: The task-scoped tool surface. `list` is deliberately absent: it was the
#: degenerate action in all 15 matrix candidates. `run` is kept so the model can
#: execute the acceptance command itself.
TOOLSETS = {
    "S1": ["read", "ast_edit", "ast_edit_batch", "apply_patch", "run", "finish"],
    "S2": ["read", "ast_edit", "ast_edit_batch", "apply_patch", "run", "finish"],
    "S3": ["read", "apply_patch", "run", "finish"],
    "S4": ["read", "ast_edit", "ast_edit_batch", "apply_patch", "run", "finish"],
    "S5": ["read", "ast_edit", "ast_edit_batch", "apply_patch", "run", "finish"],
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run(argv, cwd, *, timeout, env=None):
    """Run a command; on Windows kill the whole tree so a hung model cannot leak."""
    started = time.time()
    proc = subprocess.Popen([str(a) for a in argv], cwd=str(cwd),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, env=env)
    try:
        out, err = proc.communicate(timeout=timeout)
        timed_out = False
    except subprocess.TimeoutExpired:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True)
        try:
            out, err = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            out, err = "", ""
        timed_out = True
    return {"argv": [str(a) for a in argv], "exit": proc.returncode,
            "seconds": round(time.time() - started, 1), "timed_out": timed_out,
            "stdout": out or "", "stderr": err or ""}


def _git(*args, cwd=WORKTREE):
    p = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def reset_worktree() -> None:
    _git("reset", "--hard", "HEAD")
    _git("clean", "-fd")          # untracked, but keeps ignored evidence PNGs
    for folder in (".spike_acceptance", "spike_check"):
        dest = WORKTREE / folder
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
    gates = {"s1": "s1_accept.py", "s2": "s2_accept.py", "s3": "s3_accept.mjs",
             "s4": "s4_accept.py", "s5": "s5_accept.py"}
    for key, name in gates.items():
        target = "check.mjs" if name.endswith(".mjs") else "check.py"
        shutil.copy2(HARNESS / name, WORKTREE / ".spike_acceptance" / name)
        shutil.copy2(HARNESS / name, WORKTREE / "spike_check" / f"{key}_{target}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True, choices=sorted(CASES))
    ap.add_argument("--candidate", type=int, required=True)
    ap.add_argument("--keep", action="store_true", help="do not reset before running")
    ns = ap.parse_args()

    case = CASES[ns.case]
    out_dir = SPIKE / case["slug"] / f"cand{ns.candidate}b"
    out_dir.mkdir(parents=True, exist_ok=True)

    if not ns.keep:
        reset_worktree()
    (WORKTREE / ".spike_acceptance").mkdir(exist_ok=True)
    (WORKTREE / "spike_check").mkdir(exist_ok=True)
    gates = {"s1": "s1_accept.py", "s2": "s2_accept.py", "s3": "s3_accept.mjs",
             "s4": "s4_accept.py", "s5": "s5_accept.py"}
    for key, name in gates.items():
        target = "check.mjs" if name.endswith(".mjs") else "check.py"
        if not (WORKTREE / ".spike_acceptance" / name).is_file():
            shutil.copy2(HARNESS / name, WORKTREE / ".spike_acceptance" / name)
        if not (WORKTREE / "spike_check" / f"{key}_{target}").is_file():
            shutil.copy2(HARNESS / name, WORKTREE / "spike_check" / f"{key}_{target}")

    task = {
        "id": f"spike-{ns.case}-c{ns.candidate}",
        "title": f"{ns.case} {case['slug']}",
        "objective": case["objective"],
        "write_paths": case["write_paths"],
        "read_paths": case["read_paths"],
        "acceptance_commands": [list(c) for c in case["acceptance_cmds"]],
        "required_files": [],
        "max_steps": MAX_STEPS,
        "max_repairs": 2,
        "provider": "ollama",
        "model": MODEL,
        "num_ctx": 8192,
        "allowed_tools": list(TOOLSETS[ns.case]),
    }
    task_path = out_dir / "task.json"
    task_path.write_text(json.dumps(task, indent=2), encoding="utf-8")

    env = dict(os.environ)
    env.update({
        "NORTHSTAR_LOOP_ROOT": str(WORKTREE),
        "TYS_CODING_PROVIDER": "ollama",
        "TYS_CODING_MODEL": MODEL,
        "TYS_CODING_TIMEOUT_S": "120",
        "TYS_CODING_MAX_TOKENS": "2048",
        "PYTHONPATH": str(WORKTREE),
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    result_path = out_dir / "agent_result.json"
    started = time.time()
    agent = _run([sys.executable, str(ROOT / "scripts" / "ty_task_runner.py"),
                  "--task", str(task_path), "--result", str(result_path),
                  "--root", str(WORKTREE)],
                 cwd=WORKTREE, timeout=CAP_S, env=env)
    elapsed = round(time.time() - started, 1)

    # ---- the candidate's work, captured verbatim ---------------------------
    _, diff, _ = _git("diff", "--", ".")
    _, status, _ = _git("status", "--porcelain")
    untracked = [ln[3:].strip() for ln in status.splitlines() if ln.startswith("??")]
    new_files = {}
    for rel in untracked:
        p = WORKTREE / rel
        if p.is_file() and p.stat().st_size < 200_000:
            try:
                new_files[rel] = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
    (out_dir / "candidate.diff").write_text(diff, encoding="utf-8")
    (out_dir / "git_status.txt").write_text(status, encoding="utf-8")
    if new_files:
        (out_dir / "new_files.json").write_text(
            json.dumps(new_files, indent=1), encoding="utf-8")

    # ---- independent judgement (never the agent's own claim) --------------
    gate = _run(case["gate"], cwd=WORKTREE, timeout=case.get("gate_timeout_s", 300),
                env=env)
    (out_dir / "gate.txt").write_text(gate["stdout"] + "\n--- stderr ---\n"
                                     + gate["stderr"], encoding="utf-8")

    test_cmd = [sys.executable, "-m", "pytest", case["test_file"], "-x", "-q",
                "-p", "no:cacheprovider"]
    if case["test_file"].endswith(".mjs"):
        test_cmd = ["node", case["test_file"]]
    tests = _run(test_cmd, cwd=WORKTREE, timeout=600, env=env)
    (out_dir / "targeted_test.txt").write_text(
        tests["stdout"] + "\n--- stderr ---\n" + tests["stderr"], encoding="utf-8")

    touched = [m for m in case["module"] if m.replace("\\", "/") in diff]
    verdict = {
        "case": ns.case,
        "slug": case["slug"],
        "candidate": ns.candidate,
        "model": MODEL,
        "at": _now(),
        "agent_elapsed_s": elapsed,
        "agent_exit": agent["exit"],
        "agent_timed_out": agent["timed_out"],
        "agent_stdout_tail": agent["stdout"][-1500:],
        "agent_stderr_tail": agent["stderr"][-1500:],
        "diff_bytes": len(diff),
        "diff_nonempty": bool(diff.strip()),
        "diff_touches_target_module": touched,
        "new_files": sorted(new_files),
        "gate_exit": gate["exit"],
        "gate_timed_out": gate["timed_out"],
        "targeted_test_exit": tests["exit"],
        "targeted_test_timed_out": tests["timed_out"],
        "solved": bool(gate["exit"] == 0 and tests["exit"] == 0
                       and diff.strip() and touched),
        "claimed_ok": None,
    }
    if result_path.is_file():
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            verdict["claimed_ok"] = payload.get("ok")
            verdict["agent_steps"] = payload.get("steps")
            verdict["protocol_errors"] = payload.get("protocol_errors")
            verdict["scope_rejections"] = payload.get("scope_rejections")
            verdict["agent_summary"] = payload.get("summary")
            verdict["agent_error"] = payload.get("error")
        except ValueError:
            verdict["claimed_ok"] = "unreadable result json"

    (out_dir / "verdict.json").write_text(json.dumps(verdict, indent=2),
                                          encoding="utf-8")
    print(json.dumps({k: verdict[k] for k in
                      ("case", "candidate", "agent_exit", "agent_timed_out",
                       "diff_bytes", "diff_touches_target_module", "gate_exit",
                       "targeted_test_exit", "solved", "claimed_ok")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
