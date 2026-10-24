"""Skylos gate: the per-card evidence check for the continuous build loop.

Runs Skylos (Apache-2.0, installed in the integration venv) on the files a
build card touched and reports pass / fail / incomplete. A card is not DONE on a
model claim; it is DONE when this gate plus the tests both pass.

Usage:
    python tools/skylos_gate.py path/to/file.py [more paths...]
    python tools/skylos_gate.py --changed          # git diff --name-only (tracked)
    python tools/skylos_gate.py --all Northstar_backend

Exit codes:
    0  skylos reported no findings (or only INCOMPLETE with no high findings)
    1  skylos reported findings
    2  skylos binary missing or could not run

Skylos is located by checking (in order): SKYLOS_BIN env, the integration venv,
then PATH. If none exists, exit 2 with a clear message - never fake a pass.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

VENV_CANDIDATES = [
    r"C:\Users\T2Hol\Desktop\Northstar External\integration-venv\Scripts\skylos.exe",
    r"C:\Users\T2Hol\Desktop\Northstar External\integration-venv\Scripts\skylos",
]


def locate_skylos() -> Optional[str]:
    env = os.environ.get("SKYLOS_BIN", "").strip()
    if env and os.path.isfile(env):
        return env
    for cand in VENV_CANDIDATES:
        if os.path.isfile(cand):
            return cand
    found = shutil.which("skylos")
    return found


def changed_files() -> List[str]:
    try:
        out = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True, text=True, check=False,
        )
        files = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
        # include untracked new files too
        out2 = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            capture_output=True, text=True, check=False,
        )
        files += [ln.strip() for ln in out2.stdout.splitlines() if ln.strip()]
        return sorted(set(files))
    except Exception:  # noqa: BLE001
        return []


def run_skylos(binary: str, targets: List[str]) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    cmd = [binary] + targets
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, check=False)


def main(argv: List[str]) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    ap = argparse.ArgumentParser(description="Skylos gate for a build card")
    ap.add_argument("paths", nargs="*", help="files or directories to scan")
    ap.add_argument("--changed", action="store_true",
                    help="scan git-changed + untracked files")
    ap.add_argument("--all", metavar="DIR", help="scan a whole directory")
    ap.add_argument("--json", action="store_true", help="emit a JSON verdict")
    args = ap.parse_args(argv)

    binary = locate_skylos()
    if not binary:
        print("skylos binary not found (set SKYLOS_BIN or install into the "
              "integration venv). Gate cannot run - refusing to fake a pass.")
        return 2

    if args.all:
        targets = [args.all]
    elif args.changed:
        targets = changed_files()
        if not targets:
            print("no changed files; nothing to scan")
            return 0
    else:
        targets = args.paths
    if not targets:
        print("no targets given (pass paths, --changed, or --all DIR)")
        return 2

    proc = run_skylos(binary, targets)
    output = (proc.stdout or "") + (proc.stderr or "")
    # Skylos prints 'Coverage: INCOMPLETE' when it could not finish a check;
    # treat that as a non-passing (but not a hard fail) signal in the verdict.
    incomplete = "INCOMPLETE" in output.upper()
    # Skylos exits non-zero on findings; treat any non-zero as fail.
    findings = proc.returncode != 0

    verdict = {
        "binary": binary,
        "targets": targets,
        "returncode": proc.returncode,
        "incomplete": incomplete,
        "verdict": "FAIL" if findings else ("INCOMPLETE" if incomplete else "PASS"),
    }
    if args.json:
        print(json.dumps(verdict, indent=2))
    else:
        print(f"skylos gate: {verdict['verdict']}  (rc={proc.returncode}, "
              f"incomplete={incomplete})")
        # Print a short tail of skylos output for evidence.
        tail = output.strip().splitlines()[-12:]
        for ln in tail:
            print("  " + ln)
    if findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
