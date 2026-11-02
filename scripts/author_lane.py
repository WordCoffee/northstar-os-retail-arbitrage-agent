"""Two-phase external-author handoff.

The author (DeepSeek V4.1 Flash through the operator's Go connection) writes the fix;
the supervisor keeps every control: it takes the baseline, records the permitted scope,
audits the changed-path set, runs the independent probe and regression, commits only
task-owned bytes, and restores byte-for-byte on any failure.

`open_task` is deliberately dumb: it hands the author ONLY the task objective, the
write scope and the permitted read scope - never supervisor internals, policy files,
evaluators or the ledger.

    python scripts/continuous_loop.py --author-open  <task-id>
    python scripts/continuous_loop.py --author-close <task-id>
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import continuous_loop as cl

AUTHOR = {"provider": "opencode-go", "model": "deepseek-v4.1-flash",
          "transport": "operator session (no API call, no spend)"}
HANDOFF_DIR = cl.ROOT / "state" / "author_handoffs"


class AuthorError(RuntimeError):
    pass


def _task(tasks: Dict[str, Any], task_id: str) -> Dict[str, Any]:
    for task in tasks.get("tasks") or []:
        if str(task.get("id")) == task_id:
            return task
    raise AuthorError(f"unknown task {task_id!r}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def open_task(task_id: str, tasks: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Take the supervisor baseline and publish the author's permitted context."""
    task = _task(tasks, task_id)
    errors = cl.validate_task(task)
    if errors:
        raise AuthorError("invalid contract: " + "; ".join(errors))
    if cl.STOP_PATH.is_file():
        raise AuthorError("STOP present")
    run_id = f"{task_id}-author-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    baseline = cl.take_baseline(task, run_id)
    record = state["tasks"].setdefault(task_id, {})
    record.update({"status": "authoring", "run_id": run_id, "pid": 0,
                   "started_at": _now(), "reason": "", "lane": AUTHOR,
                   "baseline": baseline})
    cl._save_json(cl.STATE_PATH, state)
    handoff = {
        "task_id": task_id,
        "run_id": run_id,
        "author": AUTHOR,
        "objective": task.get("objective"),
        "write_paths": list(task.get("write_paths") or []),
        "read_paths": list(task.get("read_paths") or []),
        "acceptance": task.get("acceptance_commands") or [],
        "commit_paths": list(task.get("commit_paths") or []),
        "max_steps": task.get("max_steps"),
        "baseline_sha": baseline["sha"],
        "opened_at": _now(),
    }
    HANDOFF_DIR.mkdir(parents=True, exist_ok=True)
    (HANDOFF_DIR / f"{task_id}.json").write_text(json.dumps(handoff, indent=2),
                                                 encoding="utf-8")
    return handoff


def close_task(task_id: str, tasks: Dict[str, Any], state: Dict[str, Any],
               *, no_commit: bool = False) -> Dict[str, Any]:
    """Audit, verify and commit (or restore) whatever the author wrote."""
    task = _task(tasks, task_id)
    record = state["tasks"].get(task_id) or {}
    baseline = record.get("baseline")
    if not baseline:
        raise AuthorError(f"{task_id} has no open baseline - run --author-open first")
    started = time.time()
    changed = cl._changed_since(baseline["sha"], set(baseline["status"]))
    write_paths = set(baseline["write_paths"])
    detail: Dict[str, Any] = {"task_id": task_id, "changed": sorted(changed),
                              "write_paths": sorted(write_paths)}

    def fail(reason: str, *, outside: Optional[List[str]] = None) -> Dict[str, Any]:
        # Only task-owned bytes are restored. A file another process created during
        # the handoff window is NOT ours to delete - an earlier version removed one
        # and destroyed an unrelated improvement report.
        restoration = None
        try:
            restoration = cl.restore_baseline(baseline, paths=sorted(write_paths))
        except Exception as exc:  # noqa: BLE001
            reason += f"; RESTORATION FAILED: {exc}"
        record.update({"status": "failed", "finished_at": _now(),
                       "reason": reason[:1000], "lane": AUTHOR,
                       "restoration": "failed" if "RESTORATION FAILED" in reason else "ok",
                       "duration_s": round(time.time() - started, 3)})
        if outside:
            record["out_of_scope_left"] = sorted(outside)[:20]
        cl._save_json(cl.STATE_PATH, state)
        return {**detail, "status": "failed", "error": reason,
                "restoration": restoration,
                "out_of_scope_left": sorted(outside or [])[:20]}

    outside = changed - write_paths
    if outside:
        return fail("out-of-scope edits (left untouched): "
                    + ", ".join(sorted(outside)[:8]), outside=sorted(outside))

    checks = cl.run_checks(task)
    detail["checks"] = checks
    if not all(c["ok"] for c in checks):
        failed = next(c for c in checks if not c["ok"])
        return fail(f"acceptance failed: {failed['name']}: {failed.get('error')}")

    if no_commit:
        commit = {"ok": True, "committed": False, "reason": "no-commit"}
    else:
        commit = cl.commit_task(task, changed, baseline)
        if not commit.get("ok"):
            return fail("commit failed: " + str(commit.get("error")))
    record.update({"status": "completed", "finished_at": _now(), "reason": "",
                   "commit": commit.get("sha") or "", "lane": AUTHOR,
                   "duration_s": round(time.time() - started, 3)})
    cl._save_json(cl.STATE_PATH, state)
    (HANDOFF_DIR / f"{task_id}.json").unlink(missing_ok=True)
    return {**detail, "status": "completed", "commit": commit}
