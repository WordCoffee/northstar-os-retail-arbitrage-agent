"""Unattended author lane over the OpenCode Go subscription.

The supervisor keeps every control. This module only replaces the operator ferry:

    open   -> author_lane.open_task  (baseline + permitted scope)
    talk   -> `opencode run --model opencode-go/deepseek-v4.1-flash` (the Go
              subscription; NOT the OpenRouter key, no per-token billing)
    apply  -> one exact search/replace inside the declared write path
    close  -> author_lane.close_task (scope audit, probe, regression, commit)

The model never gets a shell, a path outside the contract, or the supervisor's
files. Every request is costed into `state/go_usage_ledger.jsonl` and the campaign
refuses to open a task when the conservative window share would be exceeded.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import author_lane as al          # noqa: E402
import continuous_loop as cl      # noqa: E402
import go_usage as usage          # noqa: E402

MODEL = "opencode-go/deepseek-v4.1-flash"
MAX_TURNS = 3                     # envelope repair turns, bounded
MAX_PROBE_REPAIRS = 1
TASK_DEADLINE_S = 600             # hard wall clock for one unattended task


def _opencode_command() -> List[str]:
    """Resolve the CLI shim to something CreateProcess can start.

    npm installs `opencode` (sh), `opencode.ps1` and `opencode.cmd`; `shutil.which`
    returns the .ps1 on this box, which subprocess cannot execute directly. The .cmd
    sibling is the Windows entry point.
    """
    import shutil
    found = shutil.which("opencode")
    if not found:
        return ["opencode"]
    path = Path(found)
    if path.suffix.lower() == ".ps1":
        cmd = path.with_suffix(".cmd")
        if cmd.is_file():
            return [str(cmd)]
    return [str(path)]


def _run(prompt: str, *, session: str, timeout: float = 300.0) -> Dict[str, Any]:
    """One model turn through the Go CLI. Returns text, usage and cost."""
    started = time.time()
    argv = _opencode_command() + ["run", "--model", MODEL, "--format", "json",
                                  "--title", f"ty-{session}"]
    # The prompt goes on stdin: a 16 KB contract file exceeds the Windows
    # command-line limit, and the CLI reads the message from stdin when none is
    # given. No credentials are involved on either side.
    try:
        proc = subprocess.run(argv, cwd=str(cl.ROOT), capture_output=True, text=True,
                              timeout=timeout, input=prompt)
    except subprocess.TimeoutExpired as exc:
        # A stalled CLI must become a failed turn, never a dead campaign process.
        return {"text": "", "tokens": {}, "cost_usd": 0.0, "session_id": "",
                "elapsed_s": round(time.time() - started, 2), "returncode": 124,
                "stderr": f"timeout after {timeout}s: {exc}"}
    text_parts: List[str] = []
    tokens: Dict[str, Any] = {}
    cost = 0.0
    session_id = ""
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        part = ev.get("part") or {}
        if ev.get("type") == "text":
            text_parts.append(str(part.get("text") or ""))
        elif ev.get("type") == "step_finish":
            tokens = part.get("tokens") or {}
            cost += float(part.get("cost") or 0.0)
            session_id = str(part.get("sessionID") or session_id)
    return {"text": "".join(text_parts).strip(), "tokens": tokens,
            "cost_usd": round(cost, 8), "session_id": session_id,
            "elapsed_s": round(time.time() - started, 2),
            "returncode": proc.returncode, "stderr": (proc.stderr or "")[-400:]}


def _log(task_id: str, turn: Dict[str, Any], *, prompt: str = "",
         reply: str = "") -> None:
    """Record one request. When the CLI reports no usage, estimate conservatively."""
    tok = turn.get("tokens") or {}
    cache = tok.get("cache") or {}
    cost = float(turn.get("cost_usd") or 0.0)
    source = "cli" if tok else "none"
    if not tok:
        est = usage.estimate_tokens(prompt, max(64, len(reply) // 4))
        tok = {"input": est["input_tokens"], "output": est["output_tokens"]}
        cost = est["cost_usd"]
        source = est["source"]
    usage.record({
        "task": task_id, "model": MODEL, "lane": "opencode-go-cli",
        "input_tokens": int(tok.get("input") or 0),
        "output_tokens": int(tok.get("output") or 0),
        "reasoning_tokens": int(tok.get("reasoning") or 0),
        "cache_read": int(cache.get("read") or 0),
        "cache_write": int(cache.get("write") or 0),
        "cost_usd": round(cost, 8),
        "tokens_source": source,
        "duration_s": turn.get("elapsed_s"),
    })


def _excerpt(path: Path, objective: str, *, cap: int = 6000) -> str:
    """The target function(s) named in the objective, not the whole module.

    A 24 KB module in the prompt makes the model emit a 24 KB replacement; the lane
    then spends minutes per turn. Sending only the symbol the objective names keeps
    the prompt small and the reply applicable. Falls back to the head of the file when
    no function is named.
    """
    import ast
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    if len(text) <= cap:
        return text
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text[:cap]
    names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    wanted = [n for n in names if n and n in objective]
    if not wanted:
        return text[:cap]
    pieces = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            seg = ast.get_source_segment(text, node) or ""
            if seg:
                pieces.append(seg)
    if not pieces:
        return text[:cap]
    body = "\n\n".join(pieces)
    return body[:cap] + f"\n\n# (the file is {len(text)} bytes; only the function(s) above may change)"


def _prompt(objective: str, path: str, content: str, error: str = "") -> str:
    body = (
        "You are the author for exactly one bounded fix. You cannot run tools, read "
        "other files, or change any path but the one named.\n\n"
        f"OBJECTIVE:\n{objective}\n\n"
        f"FILE: {path}\n```\n{content}\n```\n\n"
        "Reply with ONE JSON object and nothing else:\n"
        '{"path":"<the file above>","search":"<exact existing text>","replace":"<new text>"}\n'
        "Rules: search must be an exact substring of the file and occur once; replace "
        "must be the complete corrected text for that region; keep every line you are "
        "not fixing unchanged; double-quote keys and escape newlines as \\n.")
    if error:
        body += f"\n\nYOUR PREVIOUS REPLY WAS REJECTED: {error}\nFix that and reply again."
    return body


def _apply(path: str, search: str, replace: str, task: Dict[str, Any]) -> str:
    """Apply one exact replacement inside the declared scope. Returns an error string."""
    write_paths = [str(p) for p in (task.get("write_paths") or [])]
    if path not in write_paths:
        return f"path {path!r} is outside the contract's write scope {write_paths}"
    target = (cl.ROOT / path)
    if not target.is_file():
        return f"target {path} does not exist"
    text = target.read_text(encoding="utf-8")
    if not search:
        return "search block is empty"
    hits = text.count(search)
    if hits != 1:
        return f"search block occurs {hits} times (needs exactly 1)"
    target.write_text(text.replace(search, replace, 1), encoding="utf-8")
    return ""


def _extract(text: str) -> Dict[str, Any]:
    """The model's one JSON object, tolerating a fence and trailing prose."""
    body = text.strip()
    if body.startswith("```"):
        body = body.split("\n", 1)[1] if "\n" in body else body
        body = body.rsplit("```", 1)[0].strip()
    start = body.find("{")
    if start < 0:
        raise ValueError("no JSON object in the reply")
    obj, _ = json.JSONDecoder().raw_decode(body[start:])
    if not isinstance(obj, dict):
        raise ValueError("reply is not a JSON object")
    return obj


def author_task(task_id: str, tasks: Dict[str, Any], state: Dict[str, Any],
                *, dry_run: bool = False) -> Dict[str, Any]:
    task = next((t for t in tasks.get("tasks") or [] if t.get("id") == task_id), None)
    if task is None:
        return {"status": "failed", "error": f"unknown task {task_id}"}
    window = usage.preflight(0.01)
    if not window["ok"]:
        return {"status": "quota", "error": window["reason"],
                "windows": window["windows"]}
    if dry_run:
        return {"status": "dry_run", "task": task_id, "windows": window["windows"]}

    handoff = al.open_task(task_id, tasks, state)
    path = handoff["write_paths"][0]
    objective = str(task.get("objective") or "")
    turns: List[Dict[str, Any]] = []
    error = ""
    started = time.time()

    for _ in range(MAX_TURNS):
        if time.time() - started > TASK_DEADLINE_S:
            error = f"task deadline {TASK_DEADLINE_S}s exceeded before a usable edit"
            break
        target = cl.ROOT / path
        content = _excerpt(target, objective)
        prompt_text = _prompt(objective, path, content, error)
        turn = _run(prompt_text, session=task_id)
        _log(task_id, turn, prompt=prompt_text, reply=turn.get("text") or "")
        turns.append({k: turn[k] for k in ("cost_usd", "elapsed_s", "tokens")})
        if turn["returncode"] != 0 and not turn["text"]:
            error = f"the model call failed ({turn['returncode']}): {turn['stderr']}"
            continue
        try:
            obj = _extract(turn["text"])
            err = _apply(str(obj.get("path") or ""), str(obj.get("search") or ""),
                         str(obj.get("replace") or ""), task)
        except (ValueError, json.JSONDecodeError) as exc:
            error = f"reply was not one usable JSON object: {exc}"
            continue
        if err:
            error = err
            continue
        error = ""
        break

    if error:
        return {"status": "failed", "error": error, "turns": turns,
                "restoration": al.close_task(task_id, tasks, state, no_commit=True)}

    out = al.close_task(task_id, tasks, state)
    if out.get("status") != "completed" and MAX_PROBE_REPAIRS:
        probe = next((c for c in (task.get("checks") or [])), {})
        first = (out.get("checks") or [{}])[0]
        repair_prompt = _prompt(
            objective, path, _excerpt(cl.ROOT / path, objective),
            f"the independent probe failed:\n{str(first.get('output') or '')[-600:]}")
        turn = _run(repair_prompt, session=task_id)
        _log(task_id, turn, prompt=repair_prompt, reply=turn.get("text") or "")
        turns.append({k: turn[k] for k in ("cost_usd", "elapsed_s", "tokens")})
        try:
            obj = _extract(turn["text"])
            _apply(str(obj.get("path") or ""), str(obj.get("search") or ""),
                   str(obj.get("replace") or ""), task)
            out = al.close_task(task_id, tasks, state)
        except (ValueError, json.JSONDecodeError) as exc:
            out = {"status": "failed", "error": f"repair reply unusable: {exc}"}
    out["turns"] = turns
    out["elapsed_s"] = round(time.time() - started, 1)
    out["estimated_cost_usd"] = round(sum(t["cost_usd"] for t in turns), 6)
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task", default="", help="one task id")
    ap.add_argument("--max-tasks", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    tasks = cl.load_tasks()
    state = cl.load_state()
    ids = ([args.task] if args.task else
           [t["id"] for t in tasks.get("tasks") or []
            if t.get("authorized") is True and t.get("execution") == "ty"
            and not cl.blocked_reason(t, state)])
    results = []
    failures = 0
    for tid in ids[: max(0, args.max_tasks)]:
        res = author_task(tid, tasks, state, dry_run=args.dry_run)
        results.append({"task": tid, **{k: res.get(k) for k in
                                        ("status", "error", "commit", "turns",
                                         "elapsed_s", "estimated_cost_usd")}})
        if res.get("status") == "quota":
            break
        failures = failures + 1 if res.get("status") == "failed" else 0
        if failures >= 2:
            break
    print(json.dumps({"results": results, "windows": usage.totals()}, indent=2))
    return 0 if all(r.get("status") in ("completed", "dry_run") for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
