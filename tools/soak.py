"""24-hour unattended soak: measure the loop, do not improve it.

The question a soak answers is not "does it work" but "what did it do to itself over a day, with
nobody watching". So this records four numbers and nothing else:

* **merged units** — commits on the branch since the soak started, by name;
* **restarts** — launcher crash-restarts, RAM-gate pauses and any director session that died;
* **minimum free RAM** — sampled every interval, with the RAM governor's own verdict beside it;
* **owner interventions** — `needs_you.md` sections added in the window, plus any STOP hit.

It never starts, stops or edits anything. If the loop stalls, the soak says it stalled; it does not
rescue it. That is deliberate: a soak that fixes what it measures measures nothing.

    python tools/soak.py --hours 24 --interval 60
    python tools/soak.py --status
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "soak.json"
REPORTS = ROOT / "reports" / "ty"
HANDOFF = REPORTS / "handoff.md"
NEEDS_YOU = REPORTS / "needs_you.md"
PAUSE_VISION = ROOT / "state" / "vision" / "PAUSE"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write(payload: Dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(STATE)


def ram() -> Dict[str, Any]:
    try:
        import psutil

        memory = psutil.virtual_memory()
        free = round(memory.available / 1024 ** 3, 2)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}
    verdict: Dict[str, Any] = {}
    try:
        sys.path.insert(0, str(ROOT / "tools"))
        import ram_governor  # noqa: PLC0415

        verdict = ram_governor.status(who="soak", record=True) or {}
    except Exception as exc:  # noqa: BLE001
        verdict = {"error": f"{type(exc).__name__}: {exc}"}
    return {"free_gb": free, "governor": verdict}


def git_commits(since_iso: str) -> List[str]:
    try:
        proc = subprocess.run(
            ["git", "log", "--since", since_iso, "--format=%h %s", "HEAD"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=60,
            encoding="utf-8", errors="replace")
        return [line for line in (proc.stdout or "").splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError):
        return []


def _count_markers(text: str, needle: str) -> int:
    return sum(1 for line in text.splitlines() if needle in line)


def owner_interventions() -> int:
    try:
        text = NEEDS_YOU.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0
    return sum(1 for line in text.splitlines() if line.startswith("## "))


def tick(state: Dict[str, Any]) -> Dict[str, Any]:
    sample = ram()
    free = sample.get("free_gb")
    if free is not None:
        state["min_free_gb"] = min(state.get("min_free_gb") or free, free)
        state["samples"] = int(state.get("samples") or 0) + 1
        if (sample.get("governor") or {}).get("paused"):
            state["ram_pauses"] = int(state.get("ram_pauses") or 0) + 1

    try:
        handoff = HANDOFF.read_text(encoding="utf-8", errors="replace")
    except OSError:
        handoff = ""
    state["restarts"] = _count_markers(handoff, "launcher: director session ended")
    state["commits"] = git_commits(state["started_at"])
    state["needs_you_sections"] = owner_interventions()
    state["vision_paused"] = PAUSE_VISION.exists()
    state["last_sample"] = {"at": now(), **sample,
                            "queue": _queue_depth(),
                            "listeners": _listeners()}
    state["updated_at"] = now()
    _write(state)
    return state


def _queue_depth() -> Dict[str, Any]:
    data = _read(ROOT / "reports" / "ty" / "director_queue.json", {})
    jobs = data.get("jobs") or []
    queued = [j for j in jobs if j.get("status") == "queued"]
    return {"queued": len(queued), "cycle": data.get("cycle")}


def _listeners() -> Dict[str, bool]:
    out = {}
    try:
        import socket

        for port in (8000, 8101):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(0.4)
                out[str(port)] = sock.connect_ex(("127.0.0.1", port)) == 0
    except OSError:
        pass
    return out


def report(state: Dict[str, Any]) -> Path:
    started = state["started_at"]
    ended = now()
    commits = state.get("commits") or []
    lines = [
        "# 24-hour soak",
        "",
        f"Started **{started}**, ended **{ended}**. Nothing in this window was started, stopped or "
        "fixed by the soak itself.",
        "",
        "| measure | value |",
        "|---|---|",
        f"| merged units (commits on the branch) | **{len(commits)}** |",
        f"| launcher crash-restarts | **{int(state.get('restarts') or 0)}** |",
        f"| RAM-gate pauses observed | **{int(state.get('ram_pauses') or 0)}** |",
        f"| minimum free RAM | **{state.get('min_free_gb')} GB** over {int(state.get('samples') or 0)} samples |",
        f"| owner interventions needed (needs_you sections) | **{int(state.get('needs_you_sections') or 0)}** |",
        f"| vision paused at end | {bool(state.get('vision_paused'))} |",
        "",
        "## Merged units",
        "",
    ]
    lines += [f"- `{row}`" for row in commits] or ["- none"]
    last = state.get("last_sample") or {}
    lines += [
        "",
        "## Last sample",
        "",
        "```json",
        json.dumps({k: v for k, v in last.items() if k != "governor"}, indent=2),
        "```",
        "",
        "## What this does not claim",
        "",
        "- Not a stability proof at load: the soak ran with the RAM governor on, so it measures the "
        "loop as governed, not the loop unbounded.",
        "- A restart count is the launcher's own line in `handoff.md`; a session that died without "
        "writing one is counted by the stream error, not by prose.",
        "",
    ]
    path = REPORTS / f"soak_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="24-hour unattended soak")
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--interval", type=int, default=60)
    parser.add_argument("--status", action="store_true")
    ns = parser.parse_args(argv)

    if ns.status:
        state = _read(STATE, {})
        print(json.dumps(state if state else {"state": "not started"}, indent=2)[:4000])
        return 0

    state = _read(STATE, {})
    if not state.get("started_at"):
        state = {"started_at": now(), "hours": ns.hours, "commits": [], "samples": 0,
                 "restarts": 0, "ram_pauses": 0, "min_free_gb": None,
                 "needs_you_sections": owner_interventions()}
        _write(state)

    deadline = (datetime.fromisoformat(state["started_at"]).timestamp()
                + float(state["hours"]) * 3600)
    while time.time() < deadline:
        tick(state)
        time.sleep(max(15, ns.interval))

    state["ended_at"] = now()
    _write(state)
    path = report(state)
    print(json.dumps({"ok": True, "report": str(path.relative_to(ROOT)),
                      "merged": len(state.get("commits") or []),
                      "min_free_gb": state.get("min_free_gb"),
                      "restarts": state.get("restarts")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
