"""Rescan `main` at ef9cad1d with the fixed config, and record the counts.

Two fixes changed what a scan can see: the config parses again (12 allowlists), and the gate no
longer lets gitleaks skip files over ~1 MB. A rescan with the old settings would report the old,
too-clean answer.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent")
REF = "ef9cad1d"
OUT = ROOT / "reports" / "ty" / "main_rescan_ef9cad1d.json"
WORK = ROOT / "state" / "worktrees" / "_rescan-main"


def main() -> int:
    if WORK.exists():
        subprocess.run(["git", "worktree", "remove", "--force", str(WORK)], cwd=str(ROOT),
                       capture_output=True, text=True)
        shutil.rmtree(WORK, ignore_errors=True)
    subprocess.run(["git", "worktree", "add", "--detach", str(WORK), REF], cwd=str(ROOT),
                   capture_output=True, text=True, check=True)
    report = WORK / "gitleaks.json"
    run = subprocess.run(["gitleaks", "dir", str(WORK), "--redact", "--max-target-megabytes", "100",
                          "--report-format", "json", "--report-path", str(report),
                          "-c", str(ROOT / ".gitleaks.toml"), "--exit-code", "0"],
                         capture_output=True, text=True)
    data = json.loads(report.read_text(encoding="utf-8") or "[]") if report.exists() else []
    findings = [{"file": str(item.get("File")).replace(str(WORK), "").lstrip("\\/"),
                 "line": item.get("StartLine"), "rule": item.get("RuleID")} for item in data]
    tracked = subprocess.run(["git", "ls-files"], cwd=str(WORK), capture_output=True, text=True)
    payload = {"ref": REF, "returncode": run.returncode,
               "stderr_tail": (run.stderr or "").strip().splitlines()[-2:],
               "tracked_files": len(tracked.stdout.splitlines()),
               "findings": len(findings), "by_file": {},
               "detail": findings[:20]}
    for finding in findings:
        payload["by_file"][finding["file"]] = payload["by_file"].get(finding["file"], 0) + 1
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    subprocess.run(["git", "worktree", "remove", "--force", str(WORK)], cwd=str(ROOT),
                   capture_output=True, text=True)
    print(json.dumps({k: payload[k] for k in ("ref", "tracked_files", "findings", "by_file")},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
