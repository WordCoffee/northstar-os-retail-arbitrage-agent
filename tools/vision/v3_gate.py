"""V3 on the UIA backend, twice — and a refusal that is a named non-result.

The gate that has blocked Chrome Connect retirement since 2026-11-08 is V3: the same ten browser
tasks, run by Ty's Vision, twice, with the result recorded. The 9222 route (a CDP port) is
deliberately **not** used here: Chrome will not open a debugging port on a second launch while the
first instance is alive, and the owner has been clear that browser work stops when they say so.

So this runner does one thing, and refuses to do it when the eyes are not allowed to act:

* `state/vision/PAUSE` present → exit 3, nothing launched.
* desktop locked → exit 3, nothing launched.
* otherwise → run `parity --run --backend uia` **twice**, record both, write the evidence.

    python -m tools.vision.v3_gate             # run now if allowed
    python -m tools.vision.v3_gate --status    # would it run, and why not
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "reports" / "ty"
EXIT_BLOCKED = 3


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def blocked() -> str:
    try:
        from tools.director_vision import blocked_reason

        return blocked_reason() or ""
    except Exception as exc:  # noqa: BLE001 - an unreadable gate is a block, not a pass
        return f"gate unreadable: {type(exc).__name__}: {exc}"


def run_once(index: int, *, base: str, timeout: int = 1800) -> Dict[str, Any]:
    started = time.time()
    command = [sys.executable, "-m", "tools.vision.parity", "--run", "--backend", "uia",
               "--base", base]
    try:
        proc = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True,
                              timeout=timeout, encoding="utf-8", errors="replace")
        payload: Dict[str, Any] = {}
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    payload = json.loads(line)
                except ValueError:
                    continue
        return {
            "run": index,
            "at": _now(),
            "returncode": proc.returncode,
            "seconds": round(time.time() - started, 1),
            "ok": bool(payload.get("ok")),
            "passes": payload.get("passes"),
            "summary": payload,
            "tail": (proc.stdout or proc.stderr or "").strip().splitlines()[-6:],
        }
    except subprocess.TimeoutExpired:
        return {"run": index, "at": _now(), "returncode": None, "ok": False,
                "seconds": round(time.time() - started, 1), "tail": ["timeout"]}
    except OSError as exc:
        return {"run": index, "at": _now(), "returncode": None, "ok": False,
                "seconds": round(time.time() - started, 1),
                "tail": [f"{type(exc).__name__}: {exc}"]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="V3 on the UIA backend, twice")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--base", default="http://127.0.0.1:8101/ui/")
    parser.add_argument("--out", default="")
    ns = parser.parse_args(argv)

    reason = blocked()
    if ns.status:
        from tools.vision.profile6 import recorded  # noqa: PLC0415

        print(json.dumps({"at": _now(), "would_run": not reason, "blocked_reason": reason,
                          "profile6_window": recorded()}, indent=2))
        return 0 if not reason else EXIT_BLOCKED
    if reason:
        print(json.dumps({"at": _now(), "state": "refused", "reason": reason,
                          "note": "V3 was not run; a refusal is a result and is recorded as one"},
                         indent=2))
        return EXIT_BLOCKED

    # A dedicated window first, recorded by HWND: parity must not type into whatever Chrome window
    # happens to be focused (the 2026-11-11 Profiles 1/4 incident).
    from tools.vision import profile6  # noqa: PLC0415

    window = profile6.launch(ns.base)
    if not window.get("ok"):
        payload = {"at": _now(), "state": "refused", "reason": window.get("reason"),
                   "note": "no Profile 6 window could be recorded, so V3 did not start"}
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        out = OUT_DIR / f"v3_uia_{datetime.now().strftime('%Y%m%d')}.json"
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return EXIT_BLOCKED

    runs = [run_once(1, base=ns.base), run_once(2, base=ns.base)]
    ok = all(run.get("ok") for run in runs)
    payload = {
        "at": _now(),
        "backend": "uia",
        "cdp": "not used (9222 route skipped by instruction)",
        "base": ns.base,
        "runs": runs,
        "ok": ok,
        "verdict": ("PASSED twice" if ok else "FAILED: parity did not pass both runs"),
    }
    out = Path(ns.out) if ns.out else OUT_DIR / f"v3_uia_{datetime.now().strftime('%Y%m%d')}.json"
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k != "runs"}, indent=2))
    print("evidence:", out.relative_to(ROOT) if str(out).startswith(str(ROOT)) else out)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
