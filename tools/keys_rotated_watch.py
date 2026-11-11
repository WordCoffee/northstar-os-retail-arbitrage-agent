"""Wait for the owner to say the three keys are rotated — without spending a token.

The owner's action is one file: `state/security/keys_rotated.json`. Nothing else about the
rotation is guessable, so this process does the only thing that is: it watches for the file,
model-free, on a five-minute tick, and when it appears it runs the three steps that were
promised for that moment.

    1. `python tools/retire_chat_exports.py --retire`   remove the exports, allowlist the DEAD
                                                       fingerprints, rescan
    2. the gitleaks gate (`gitleaks dir . --config .gitleaks.toml --redact`) on the working tree
    3. `python tools/promote_closure.py --dry-run`      the promotion test for the green staging
                                                       candidate, in a throwaway worktree; it does
                                                       not touch `main`

It runs once per marker file (a sha256 of the marker is recorded, so re-writing the same file
does not re-run it), honours `STOP` and `state/vision/PAUSE`, and never makes a model call.

    python tools/keys_rotated_watch.py --once      # one tick, useful for the test
    python tools/keys_rotated_watch.py             # the 5-minute loop
    python tools/keys_rotated_watch.py --status
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = ROOT / "state" / "security" / "keys_rotated.json"
RESULT = ROOT / "state" / "security" / "keys_rotated_result.json"
LOG = ROOT / "reports" / "ty" / "keys_rotated_watch.log"
STOP = ROOT / "STOP"
PAUSE = ROOT / "state" / "vision" / "PAUSE"
INTERVAL_S = 300


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(message: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{now()} {message}\n")


def _marker_digest() -> str:
    try:
        return hashlib.sha256(MARKER.read_bytes()).hexdigest()
    except OSError:
        return ""


def _run(label: str, args: list[str], timeout: int = 1800) -> dict:
    started = time.time()
    log(f"{label}: running {' '.join(args)}")
    try:
        proc = subprocess.run(args, cwd=str(ROOT), capture_output=True, text=True,
                              timeout=timeout, encoding="utf-8", errors="replace")
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-6:]
        result = {"label": label, "returncode": proc.returncode,
                  "seconds": round(time.time() - started, 1), "tail": tail}
    except subprocess.TimeoutExpired:
        result = {"label": label, "returncode": None,
                  "seconds": round(time.time() - started, 1), "tail": ["timeout"]}
    except OSError as exc:
        result = {"label": label, "returncode": None, "seconds": 0,
                  "tail": [f"{type(exc).__name__}: {exc}"]}
    log(f"{label}: exit {result['returncode']} in {result['seconds']}s")
    return result


def steps() -> list[dict]:
    return [
        _run("retire", [sys.executable, "tools/retire_chat_exports.py", "--retire"]),
        _run("gitleaks", ["gitleaks", "dir", ".", "--config", ".gitleaks.toml",
                          "--no-banner", "--redact", "--exit-code", "0"]),
        _run("promotion-test", [sys.executable, "tools/promote_closure.py", "--dry-run"],
             timeout=3600),
    ]


def status() -> int:
    payload = {"at": now(), "marker_present": MARKER.exists(),
               "marker_digest": _marker_digest()[:16],
               "result": json.loads(RESULT.read_text(encoding="utf-8"))
               if RESULT.exists() else None,
               "stop": STOP.exists(), "pause": PAUSE.exists()}
    print(json.dumps(payload, indent=2))
    return 0


def tick() -> dict:
    if STOP.exists():
        return {"state": "stopped", "reason": "STOP file present"}
    if PAUSE.exists():
        return {"state": "paused", "reason": "PAUSE file present"}
    if not MARKER.exists():
        return {"state": "waiting", "reason": "no keys_rotated.json"}

    digest = _marker_digest()
    previous = {}
    if RESULT.exists():
        try:
            previous = json.loads(RESULT.read_text(encoding="utf-8"))
        except ValueError:
            previous = {}
    if previous.get("marker_digest") == digest and previous.get("steps"):
        return {"state": "done", "reason": "this marker has already been acted on",
                "steps": previous["steps"]}

    log(f"marker found (sha256 {digest[:16]}); running the three steps")
    ran = steps()
    payload = {"at": now(), "marker_digest": digest, "steps": ran,
               "note": ("retire + gitleaks + promotion dry-run. Promotion itself is not applied: "
                        "a merge to main needs the independent verifier and a rollback tag.")}
    RESULT.parent.mkdir(parents=True, exist_ok=True)
    RESULT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    log("three steps recorded in state/security/keys_rotated_result.json")
    return {"state": "acted", **payload}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Model-free watcher for the key rotation marker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--interval", type=int, default=INTERVAL_S)
    ns = parser.parse_args(argv)

    if ns.status:
        return status()
    if ns.once:
        print(json.dumps(tick(), indent=2))
        return 0

    log(f"watcher starting (interval {ns.interval}s)")
    while True:
        outcome = tick()
        if outcome.get("state") == "stopped":
            log("stopping: STOP file present")
            return 0
        time.sleep(ns.interval)


if __name__ == "__main__":
    raise SystemExit(main())
