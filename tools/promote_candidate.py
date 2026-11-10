"""Test promoting the whole green candidate as one closure, instead of slice by slice.

Slice promotion failed because code slices import each other: main ended up with modules it could not
import. The candidate tree is already green as a whole, so the question is whether **main + the
candidate tree** is green — and that is a question a temp worktree can answer directly:

    worktree at main  ->  read-tree the candidate  ->  three gates

1. **gitleaks** on the staged result, exactly as the pre-commit hook runs it;
2. **collect-only** over the whole backend;
3. **the full suite**, because "collects" is not "passes".

Nothing is promoted. This reports whether a whole-tree promotion would be safe, and names what
fails if it would not.

    python tools/promote_candidate.py --ref staging-candidate/20261109-2142
    python tools/promote_candidate.py --ref staging --gate-only      # skip the suite
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "ty" / "candidate_closure.json"


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=str(cwd or ROOT), capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()[:300]}")
    return result.stdout


def gitleaks(worktree: Path) -> List[Dict[str, Any]]:
    report = worktree / "gitleaks.json"
    subprocess.run(["gitleaks", "git", "--pre-commit", "--staged", "--redact",
                    "--report-format", "json", "--report-path", str(report),
                    "-c", str(ROOT / ".gitleaks.toml")],
                   cwd=str(worktree), capture_output=True, text=True, check=False)
    if not report.exists():
        return []
    data = json.loads(report.read_text(encoding="utf-8") or "[]")
    return [{"file": item.get("File"), "line": item.get("StartLine"), "rule": item.get("RuleID")}
            for item in data]


def pytest_run(worktree: Path, *, collect_only: bool, timeout: int) -> Dict[str, Any]:
    args = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"]
    if collect_only:
        args += ["--collect-only"]
    started = time.time()
    result = subprocess.run(args, cwd=str(worktree / "Northstar_backend"),
                            capture_output=True, text=True, timeout=timeout)
    tail = (result.stdout or "").strip().splitlines()[-3:]
    errors = [line for line in (result.stdout or "").splitlines() if line.startswith("ERROR ")]
    return {"returncode": result.returncode, "seconds": round(time.time() - started, 1),
            "tail": tail, "errors": errors[:25]}


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gate a whole-candidate promotion in a temp worktree")
    parser.add_argument("--ref", default="staging-candidate/20261109-2142")
    parser.add_argument("--base", default="main")
    parser.add_argument("--gate-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    candidate = git("rev-parse", f"{ns.ref}^{{commit}}").strip()
    base = git("rev-parse", ns.base).strip()
    # Work under the repo, not %TEMP%: the temp-directory run spent 50 minutes on 196 s of CPU
    # (a stall, not work), while the same suite in state/worktrees finished in 19. A worktree on
    # the same volume as the repo is what the earlier full-suite runs used.
    worktree = ROOT / "state" / "worktrees" / "candidate-closure"
    if worktree.exists():
        subprocess.run(["git", "worktree", "remove", "--force", str(worktree)],
                       cwd=str(ROOT), capture_output=True, text=True)
        shutil.rmtree(worktree, ignore_errors=True)
    result: Dict[str, Any] = {"candidate": ns.ref, "candidate_sha": candidate[:12],
                              "base": ns.base, "base_sha": base[:12], "worktree": str(worktree)}
    try:
        subprocess.run(["git", "worktree", "add", str(worktree), ns.base],
                       cwd=str(ROOT), capture_output=True, text=True, check=False)
        # main + the candidate tree, without moving main
        git("read-tree", "-u", "--reset", candidate, cwd=worktree)
        git("add", "-A", cwd=worktree)
        result["gitleaks"] = gitleaks(worktree)
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        result["collect"] = pytest_run(worktree, collect_only=True, timeout=1800)
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        if not ns.gate_only:
            result["suite"] = pytest_run(worktree, collect_only=False, timeout=3600)
        ok = (not result["gitleaks"] and result["collect"]["returncode"] == 0
              and not result["collect"]["errors"]
              and (ns.gate_only or result.get("suite", {}).get("returncode") == 0))
        result["verdict"] = "SAFE-TO-PROMOTE" if ok else "REFUSED"
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(worktree)],
                       cwd=str(ROOT), capture_output=True, text=True)

    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if ns.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"candidate {result['candidate']} = {result['candidate_sha']} "
              f"onto {result['base']} = {result['base_sha']}")
        print(f"gitleaks findings: {len(result['gitleaks'])}")
        for finding in result["gitleaks"][:10]:
            print(f"   {finding['file']}:{finding['line']}  {finding['rule']}")
        print("collect-only:", result["collect"]["tail"])
        for error in result["collect"]["errors"][:8]:
            print("   ", error)
        if "suite" in result:
            print(f"full suite: {result['suite']['tail']} ({result['suite']['seconds']}s)")
        print(f"VERDICT: {result['verdict']}")
    return 0 if result["verdict"] == "SAFE-TO-PROMOTE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
