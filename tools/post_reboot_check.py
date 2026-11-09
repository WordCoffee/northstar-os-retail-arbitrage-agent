"""Post-reboot proof: did the machine come back, and did the director resume itself?

A scheduled task that "should" fire at logon is a claim. This is the measurement: one
file of facts taken after a boot, kept in two places so it can be read by a human and
consumed by the launcher.

    python tools/post_reboot_check.py            # record the proof, print it
    python tools/post_reboot_check.py --quiet    # record it, print nothing
    python tools/post_reboot_check.py --json     # record it, print only the JSON

**Boot time source.** `Get-CimInstance Win32_OperatingSystem` `LastBootUpTime`, converted
to UTC. That is the machine's own answer and survives the reboot it describes. The
fallback is the `time.monotonic` offset (`time.time() - time.monotonic()`), which on
Windows is measured from boot; it is only used when CIM cannot be read, and the payload
records which one was used so a reader never has to guess.

Everything here is read-only except the two artefacts (`state/director/reboot_proof.json`
and an appended dated section in `reports/ty/reboot_proof.md`). The queue is read through
`tools/director_queue.py`, never by opening sqlite directly, so there is one definition of
"open job". Nothing here raises: a check that cannot complete still writes what it knows
and says what it could not read.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
CODE_ROOT = ROOT
STATE = ROOT / "state" / "director"
PROOF_JSON = STATE / "reboot_proof.json"
PROOF_MD = ROOT / "reports" / "ty" / "reboot_proof.md"
LOG = ROOT / "logs" / "ty_director.log"
HANDOFF = ROOT / "reports" / "ty" / "handoff.md"
PID_FILE = STATE / "director.pid"
QUEUE_DB: Optional[Path] = Path(STATE / "queue.sqlite")

TASK_NAME = os.environ.get("TY_TASK_NAME", "NorthstarTyDirector")
PS_TIMEOUT_S = 25

#: A scheduled task that has never run reports this sentinel (1999-11-30 local).
_NEVER = 2000

OPEN_STATUSES = ("queued", "claimed", "running", "ready", "blocked")
#: Reported in-flight first: a reader wants to see what is being worked on.
_OPEN_ORDER = ("running", "claimed", "ready", "queued", "blocked")


def configure(root: Optional[str]) -> None:
    """Point the *reads* at another checkout.

    A builder works in a git worktree, where `logs/` and `state/director/` are empty
    because they are runtime directories and never versioned. `--root` lets a run there
    cite the live log, pid and queue without writing a single byte into the live tree:
    the two artefacts stay with this code, so they can be committed with it.
    """
    global ROOT, QUEUE_DB, LOG, HANDOFF, PID_FILE
    ROOT = Path(root).resolve() if root else CODE_ROOT
    QUEUE_DB = ROOT / "state" / "director" / "queue.sqlite"
    LOG = ROOT / "logs" / "ty_director.log"
    HANDOFF = ROOT / "reports" / "ty" / "handoff.md"
    PID_FILE = ROOT / "state" / "director" / "director.pid"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: Optional[datetime]) -> Optional[str]:
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def _epoch(moment: Optional[datetime]) -> Optional[float]:
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return round(moment.timestamp(), 3)


def _parse(text: Any) -> Optional[datetime]:
    if not text:
        return None
    try:
        moment = datetime.fromisoformat(str(text).strip())
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


def _duration(seconds: Optional[float]) -> str:
    if seconds is None:
        return "unknown"
    seconds = max(0, int(seconds))
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


# ------------------------------------------------------------------ windows probe
def _powershell_json(script: str) -> Optional[Dict[str, Any]]:
    """Run one PowerShell script that prints one JSON object. Never raises."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=PS_TIMEOUT_S,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        text = (out.stdout or "").strip()
        if not text:
            return None
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _probe_script() -> str:
    name = TASK_NAME.replace("'", "''")
    return f"""
$ErrorActionPreference = 'SilentlyContinue'
$boot = $null
$os = Get-CimInstance -ClassName Win32_OperatingSystem | Select-Object -First 1
if ($os -and $os.LastBootUpTime) {{
  try {{ $boot = $os.LastBootUpTime.ToUniversalTime().ToString('o') }}
  catch {{ $boot = [string]$os.LastBootUpTime }}
}}
$task = $null
$info = Get-ScheduledTaskInfo -TaskName '{name}'
if ($info) {{
  $lastRun = $null
  if ($info.LastRunTime) {{
    try {{ $lastRun = $info.LastRunTime.ToUniversalTime().ToString('o') }}
    catch {{ $lastRun = [string]$info.LastRunTime }}
  }}
  $state = $null
  try {{ $state = (Get-ScheduledTask -TaskName '{name}').State }} catch {{}}
  $task = [pscustomobject]@{{
    name = '{name}'
    state = [string]$state
    last_run_time = $lastRun
    last_task_result = $info.LastTaskResult
    missed_runs = $info.NumberOfMissedRuns
  }}
}}
[pscustomobject]@{{ boot_utc = $boot; task = $task }} | ConvertTo-Json -Compress -Depth 5
"""


def boot_time(probe: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Boot time, CIM first, monotonic offset as the fallback.

    ``probe`` is the parsed PowerShell payload; when it is omitted it is fetched here
    so a caller can share one process with the task query.
    """
    if probe is None:
        probe = _powershell_json(_probe_script()) or {}
    moment = _parse(probe.get("boot_utc"))
    if moment is not None:
        return {"source": "Get-CimInstance Win32_OperatingSystem LastBootUpTime",
                "utc": _iso(moment), "epoch": _epoch(moment)}
    try:
        # On Windows time.monotonic() is measured from boot, so this offset is the
        # boot instant without needing a previous record.
        epoch = round(time.time() - time.monotonic(), 3)
        return {"source": "time.monotonic offset (CIM unreadable)",
                "utc": _iso(datetime.fromtimestamp(epoch, timezone.utc)),
                "epoch": epoch}
    except (OSError, ValueError):
        return {"source": "unknown", "utc": None, "epoch": None}


def task_state(probe: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """LastRunTime / LastTaskResult / NumberOfMissedRuns / State, as the scheduler has them."""
    if probe is None:
        probe = _powershell_json(_probe_script()) or {}
    row = probe.get("task")
    if not isinstance(row, dict):
        return {"ok": False, "name": TASK_NAME,
                "error": "Get-ScheduledTaskInfo returned nothing"}
    moment = _parse(row.get("last_run_time"))
    never = moment is None or moment.year < _NEVER
    try:
        result = int(row.get("last_task_result"))
    except (TypeError, ValueError):
        result = None
    try:
        missed = int(row.get("missed_runs"))
    except (TypeError, ValueError):
        missed = None
    return {
        "ok": True, "name": row.get("name") or TASK_NAME,
        "state": row.get("state") or None,
        "last_run_time": None if never else _iso(moment),
        "last_run_epoch": None if never else _epoch(moment),
        "never_run": bool(never),
        "last_task_result": result,
        "missed_runs": missed,
    }


# ---------------------------------------------------------------------- director
def _pid_alive(pid: int) -> bool:
    if not pid:
        return False
    try:
        import ctypes

        handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, int(pid))
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    except Exception:  # noqa: BLE001 - unknown means "do not claim alive"
        return False


def director_state() -> Dict[str, Any]:
    """The pid the launcher last wrote down, and whether it is still there."""
    record: Any = {}
    try:
        record = json.loads(PID_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        record = {}
    if not isinstance(record, dict):
        record = {}
    try:
        pid = int(record.get("pid") or 0)
    except (TypeError, ValueError):
        pid = 0
    return {"pid": pid or None, "alive": _pid_alive(pid),
            "started_at": record.get("started_at"),
            "recorded_cmd": record.get("cmd"), "pid_file": str(PID_FILE)}


# ------------------------------------------------------------------------- queue
def _queue_module() -> Any:
    tools = str(ROOT / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import director_queue  # noqa: PLC0415 - local tool, imported on demand

    return director_queue


def queue_state(queue_module: Any = None, db: Optional[Path] = None) -> Dict[str, Any]:
    """Open jobs by status, through `tools/director_queue.py` only."""
    try:
        module = queue_module or _queue_module()
    except Exception as exc:  # noqa: BLE001 - the check must still report
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    path = Path(db or QUEUE_DB or getattr(module, "DB"))
    if not path.exists():
        return {"ok": True, "db": str(path), "total": 0, "open": 0,
                "by_status": {}, "note": "no queue database yet"}
    try:
        rows = module.jobs(db=path)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "db": str(path), "error": f"{type(exc).__name__}: {exc}"}
    by_status: Dict[str, int] = {}
    open_rows: List[Dict[str, Any]] = []
    for row in rows:
        status = str(row.get("status") or "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        if status in OPEN_STATUSES:
            open_rows.append({"id": row.get("id"), "unit": row.get("unit"),
                              "status": status, "owner": row.get("owner") or ""})
    open_rows.sort(key=lambda row: (_OPEN_ORDER.index(row["status"]),
                                    str(row.get("id") or "")))
    return {"ok": True, "db": str(path), "total": len(rows),
            "open": len(open_rows), "by_status": dict(sorted(by_status.items())),
            "open_jobs": open_rows}


# ------------------------------------------------------------------------- log
def read_log_starts(log_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Every `started director pid=` line, oldest first, with its timestamp."""
    path = Path(log_path or LOG)
    starts: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return starts
    for line in lines:
        marker = " started director pid="
        if marker not in line:
            continue
        stamp, _, tail = line.partition(marker)
        try:
            pid = int(tail.split()[0])
        except (ValueError, IndexError):
            continue
        moment = _parse(stamp.strip())
        starts.append({"line": line.strip(), "pid": pid,
                       "at": _iso(moment), "epoch": _epoch(moment)})
    return starts


def resume_evidence(starts: List[Dict[str, Any]],
                    boot_epoch: Optional[float]) -> Dict[str, Any]:
    """The newest start line, and whether any start happened after this boot."""
    if not starts:
        return {"found": False, "after_boot": False, "pid": None,
                "at": None, "line": None}
    newest = max(starts, key=lambda row: row.get("epoch") or 0)
    after = [row for row in starts
             if boot_epoch is not None and (row.get("epoch") or 0) >= boot_epoch]
    resumed = max(after, key=lambda row: row.get("epoch") or 0) if after else None
    return {"found": True, "after_boot": bool(resumed),
            "pid": (resumed or newest).get("pid"),
            "at": (resumed or newest).get("at"),
            "line": (resumed or newest).get("line"),
            "newest_pid": newest.get("pid"), "newest_at": newest.get("at"),
            "starts_total": len(starts)}


def handoff_state(path: Optional[Path] = None,
                  boot_epoch: Optional[float] = None) -> Dict[str, Any]:
    """The handoff's mtime: proof the session actually continued writing."""
    target = Path(path or HANDOFF)
    try:
        stat = target.stat()
    except OSError:
        return {"path": str(target), "exists": False, "mtime": None,
                "mtime_epoch": None, "after_boot": False}
    moment = datetime.fromtimestamp(stat.st_mtime, timezone.utc)
    return {"path": str(target), "exists": True, "bytes": stat.st_size,
            "mtime": _iso(moment), "mtime_epoch": round(stat.st_mtime, 3),
            "after_boot": bool(boot_epoch is not None and stat.st_mtime >= boot_epoch)}


# ------------------------------------------------------------------------ render
def build_payload(probe: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One dict of facts. Every part is gathered defensively."""
    if probe is None:
        probe = _powershell_json(_probe_script())
    boot = boot_time(probe)
    boot_epoch = boot.get("epoch")
    task = task_state(probe)
    director = director_state()
    queue = queue_state()
    starts = read_log_starts()
    resume = resume_evidence(starts, boot_epoch)
    handoff = handoff_state(boot_epoch=boot_epoch)
    now = _now()
    return {
        "checked_at": _iso(now),
        "checked_epoch": round(now.timestamp(), 3),
        "boot": boot,
        "uptime_seconds": None if boot_epoch is None
        else round(time.time() - boot_epoch, 1),
        "task": task,
        "director": director,
        "queue": queue,
        "resume": resume,
        "handoff": handoff,
        "verdict": {
            "boot_known": boot_epoch is not None,
            "task_ran_this_boot": bool(
                boot_epoch is not None and task.get("last_run_epoch")
                and task["last_run_epoch"] >= boot_epoch),
            "director_alive": bool(director.get("alive")),
            "director_resumed_after_boot": bool(resume.get("after_boot")),
            "handoff_continued_after_boot": bool(handoff.get("after_boot")),
        },
    }


def _yes(value: Any) -> str:
    return "yes" if value else "**no**"


def _result_text(task: Dict[str, Any]) -> str:
    if not task.get("ok"):
        return f"unreadable ({task.get('error')})"
    if task.get("never_run"):
        return "never run"
    code = task.get("last_task_result")
    meaning = {0: "0 (success)", 267011: "267011 (never run)",
               267009: "267009 (running)"}.get(code)
    return meaning or str(code)


def render_markdown(payload: Dict[str, Any]) -> str:
    """One dated section. Appended, never rewritten."""
    boot = payload.get("boot") or {}
    task = payload.get("task") or {}
    director = payload.get("director") or {}
    queue = payload.get("queue") or {}
    resume = payload.get("resume") or {}
    handoff = payload.get("handoff") or {}
    verdict = payload.get("verdict") or {}

    stamp = payload.get("checked_at") or _iso(_now())
    lines = [
        f"## {stamp} — reboot proof",
        "",
        f"boot **{boot.get('utc')}** via {boot.get('source')}; "
        f"uptime {_duration(payload.get('uptime_seconds'))}",
        "",
        f"- task `{task.get('name') or TASK_NAME}`: state {task.get('state') or 'unknown'}, "
        f"last run {task.get('last_run_time') or 'never'}, "
        f"result {_result_text(task)}, "
        f"missed runs {task.get('missed_runs')}",
        f"- director pid {director.get('pid') or '—'}: "
        f"{'alive' if director.get('alive') else '**not alive**'} "
        f"(pid file written {director.get('started_at') or 'never'})",
        f"- queue: {queue.get('open', '?')} open / {queue.get('total', '?')} jobs "
        f"— {json.dumps(queue.get('by_status') or {}, sort_keys=True)}",
        f"- resumed after boot: {_yes(resume.get('after_boot'))} — "
        f"{resume.get('line') or 'no `started director pid=` line in the log'}",
        f"- handoff `{handoff.get('path')}` mtime {handoff.get('mtime') or 'missing'} "
        f"(continued after boot: {_yes(handoff.get('after_boot'))})",
        "",
        f"verdict: task ran this boot {_yes(verdict.get('task_ran_this_boot'))}; "
        f"director alive {_yes(verdict.get('director_alive'))}; "
        f"resumed after boot {_yes(verdict.get('director_resumed_after_boot'))}; "
        f"handoff continued {_yes(verdict.get('handoff_continued_after_boot'))}",
        "",
    ]
    return "\n".join(lines)


def write_json(payload: Dict[str, Any], path: Optional[Path] = None) -> Path:
    target = Path(path or PROOF_JSON)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    tmp.replace(target)
    return target


def append_markdown(section: str, path: Optional[Path] = None) -> Path:
    """Append a dated section; create the file with a header the first time."""
    target = Path(path or PROOF_MD)
    target.parent.mkdir(parents=True, exist_ok=True)
    header = ("# Reboot proof\n\n"
              "One dated section per `python tools/post_reboot_check.py` run. "
              "Old sections are never rewritten.\n\n")
    existing = ""
    if target.exists():
        try:
            existing = target.read_text(encoding="utf-8")
        except OSError:
            existing = ""
    with target.open("a" if existing else "w", encoding="utf-8") as handle:
        if not existing:
            handle.write(header)
        handle.write(section if section.endswith("\n\n") else section.rstrip() + "\n\n")
    return target


def run(probe: Optional[Dict[str, Any]] = None,
        json_path: Optional[Path] = None,
        md_path: Optional[Path] = None) -> Dict[str, Any]:
    """Record the proof. Never raises: a failure is reported, not thrown."""
    try:
        payload = build_payload(probe)
    except Exception as exc:  # noqa: BLE001 - the launcher must survive this
        payload = {"checked_at": _iso(_now()), "checked_epoch": round(time.time(), 3),
                   "error": f"{type(exc).__name__}: {exc}",
                   "verdict": {"boot_known": False, "task_ran_this_boot": False,
                               "director_alive": False,
                               "director_resumed_after_boot": False,
                               "handoff_continued_after_boot": False}}
    try:
        write_json(payload, json_path)
    except OSError as exc:
        payload.setdefault("write_errors", []).append(f"json: {exc}")
    try:
        append_markdown(render_markdown(payload), md_path)
    except OSError as exc:
        payload.setdefault("write_errors", []).append(f"markdown: {exc}")
    return payload


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Post-reboot proof")
    parser.add_argument("--quiet", action="store_true", help="write only, print nothing")
    parser.add_argument("--json", action="store_true", help="print the payload only")
    parser.add_argument("--root", default="",
                        help="checkout to read the log, pid and queue from")
    ns = parser.parse_args(argv)

    configure(ns.root)
    payload = run()
    if ns.quiet:
        return 0
    if ns.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"\nwrote {PROOF_JSON} and appended {PROOF_MD}")
    # Exit 0 either way: a proof that says "no" is evidence, not a crash. The
    # verdict is in the payload, where a reader can act on it.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
