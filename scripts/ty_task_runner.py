#!/usr/bin/env python3
"""Run one authorized task through Ty's bounded coding pipeline.

Called by ``scripts/continuous_loop.py`` as a child process so the supervisor can
enforce a wall-clock timeout, kill the whole tree, and keep a heartbeat. The task
JSON is written by the supervisor from a validated contract; this runner does not
choose tasks or grant permissions.

Contract fields consumed here:
    objective, write_paths, read_paths, acceptance_commands, required_files,
    max_steps, max_repairs, required_artifact, model

The Workspace allowlist is the write scope; the run allowlist is exactly the
task's acceptance commands. A STOP file is checked before every model call.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Sequence

ROOT = Path(os.environ.get("NORTHSTAR_LOOP_ROOT")
            or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from agent_kernel.coding_runner import CodingTask, run_coding_task  # noqa: E402
from agent_kernel.coding_tools import Workspace  # noqa: E402
from agent_kernel.local_model import make_local_model  # noqa: E402
from agent_kernel.tys_adapter import make_workspace_acceptance  # noqa: E402


def _write_result(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task", required=True, help="validated task JSON")
    ap.add_argument("--result", required=True, help="result JSON path")
    ap.add_argument("--heartbeat", default="", help="heartbeat JSON path")
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args(argv)

    spec = json.loads(Path(args.task).read_text(encoding="utf-8"))
    root = Path(args.root).resolve()
    result_path = Path(args.result)
    heartbeat_path = Path(args.heartbeat) if args.heartbeat else None
    write_paths = [str(p) for p in (spec.get("write_paths") or [])]
    read_paths = [str(p) for p in (spec.get("read_paths") or [])] or write_paths
    commands = [[str(c) for c in cmd] for cmd in (spec.get("acceptance_commands") or [])]
    required = [str(p) for p in (spec.get("required_files") or [])]
    objective = str(spec.get("objective") or "").strip()
    if not objective or not write_paths:
        _write_result(result_path, {"ok": False, "error": "task needs objective and write_paths"})
        return 2

    def heartbeat(stage: str) -> None:
        if heartbeat_path is None:
            return
        heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        heartbeat_path.write_text(json.dumps({
            "pid": os.getpid(), "stage": stage,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }), encoding="utf-8")

    if (root / "STOP").is_file():
        _write_result(result_path, {"ok": False, "error": "STOP present before dispatch"})
        return 2

    workspace = Workspace(
        root,
        allow_paths=write_paths,
        read_paths=read_paths,
        run_allowlist=commands or None,
    )
    acceptance = make_workspace_acceptance(str(root), {
        "commands": commands,
        "required_files": required,
    }) if (commands or required) else None

    model_overrides = {}
    if spec.get("model"):
        model_overrides["model"] = spec["model"]
    if spec.get("provider"):
        model_overrides["provider"] = spec["provider"]
    model = make_local_model(**model_overrides)

    def guarded_model(prompt: str) -> str:
        if (root / "STOP").is_file():
            raise RuntimeError("STOP requested")
        heartbeat("model")
        return model(prompt)

    task = CodingTask(
        objective=objective,
        workspace=str(root),
        commands=commands,
        required_files=required,
        max_steps=int(spec.get("max_steps") or 10),
        max_repairs=int(spec.get("max_repairs") or 0),
        required_artifact=str(spec.get("required_artifact") or ""),
    )
    try:
        result = run_coding_task(task, model=guarded_model, acceptance=acceptance,
                                 workspace=workspace)
        payload = result.to_dict()
        payload["ok"] = bool(result.ok or result.acceptance_recovered)
        payload["acceptance_recovered"] = bool(result.acceptance_recovered)
        payload["task_id"] = spec.get("id")
        payload["heartbeat_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        _write_result(result_path, payload)
        return 0 if payload["ok"] else 1
    except Exception as exc:  # noqa: BLE001 - the supervisor records the failure
        _write_result(result_path, {
            "ok": False, "task_id": spec.get("id"),
            "error": f"{type(exc).__name__}: {exc}"[:1000],
            "heartbeat_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
