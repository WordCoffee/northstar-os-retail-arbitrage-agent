"""tys_launcher - the process that keeps working when the session does not.

`tys_runner.py` knows how to reserve a cycle, validate evidence and rotate a
session. It does not *call* anything, so on its own it is a set of rules with no
engine. This is the engine: it loops ``next -> worker -> complete``, keeps a
heartbeat, and stops only for a declared reason.

    python tools/tys_launcher.py --max-hours 8 --max-cycles 20
    python tools/tys_launcher.py --dry-run --max-cycles 3        # no worker
    python tools/tys_launcher.py --worker "python scripts/ty_task_runner.py ..."

Task contract: a queue item is only runnable when it names its checks
(``acceptance_commands``) and its write scope (``write_paths``). An item without
checks is marked ``needs-author`` and skipped - the launcher never invents a
pass criterion, because an invented criterion is how an autonomous loop ships
broken work.

Judgement: the launcher no longer decides whether a patch is good. A cycle is
judged by ``tys_evaluator``: the candidate is **frozen** to
``state/author/<item>/cand_<k>.{diff,json}``, the frozen bytes are replayed
through the five gates by ``evaluate_frozen``, and ``evaluate`` is then run over
the live tree as a drift check. Until A12b the launcher ran the checks itself
and called that a verdict, which meant the scope gate, the tamper gate and the
rejection record could never fire in a real cycle. The launcher keeps exactly one
check of its own: the **pre-run red gate** (a check that is already green proves
nothing a worker did), which is a dispatch guard, not a verdict.

Stop conditions (each recorded in the heartbeat with its reason):
    STOP file · token cap · queue empty · max-cycles · max-hours · worker failure
    streak (3) · handoff invalid (2)

Every step appends to ``state/tys_runner/launcher.jsonl`` and rewrites
``state/tys_runner/heartbeat.json`` so another process (or a human) can see what
it is doing and how long it has been doing it.

Token accounting is *measured*: after a worker run the launcher asks
``token_meter.estimate_session(session_id)`` what the session spent and puts that
in the completion payload the runner's daily cap is enforced from. Only when the
store cannot answer does it fall back to a labelled payload estimate, so the cap
is no longer fed by arithmetic over the launcher's own summary file.
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
from typing import Any, Callable, Dict, List, Optional

ROOT = Path(os.environ.get("NORTHSTAR_TY_ROOT")
            or Path(__file__).resolve().parents[1]).resolve()
sys.path.insert(0, str(Path(__file__).resolve().parent))

import token_meter as meter  # noqa: E402
import tys_evaluator as evaluator  # noqa: E402
import tys_runner as runner  # noqa: E402

STATE = ROOT / "state" / "tys_runner"
HEARTBEAT = STATE / "heartbeat.json"
JOURNAL = STATE / "launcher.jsonl"
BRIEF = ROOT / "reports" / "ty" / "cycle_handoff.json"
WORKER_TIMEOUT_S = int(os.environ.get("TY_WORKER_TIMEOUT_S", "1800"))
MAX_FAILURE_STREAK = 3

#: Files this process writes during a cycle. They are dirty or untracked by the
#: time a candidate is judged and no candidate declares them, so a judge that
#: counted them as the patch would refuse every cycle. They are recorded in the
#: dispatch snapshot because they are the launcher's bytes, never the worker's.
LAUNCHER_PATHS = (
    "state/tys_runner/task.json",
    "state/tys_runner/worker_result.json",
    "state/tys_runner/completion.json",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": _now(), **row}, ensure_ascii=False) + "\n")


def heartbeat(**fields: Any) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    payload = {"at": _now(), "pid": os.getpid(), **fields}
    tmp = HEARTBEAT.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(HEARTBEAT)


# --------------------------------------------------------------------- contracts
def dispatch_snapshot() -> List[str]:
    """Every path already dirty in the *whole* tree, before the worker is dispatched.

    Both halves of git's answer are needed. ``git status --porcelain`` collapses an
    untracked directory to one entry (``state/probes/`` stands for its whole tree),
    while ``git ls-files --others --exclude-standard`` names the files. The
    evaluator excuses a path only when the dispatch snapshot names it (or a
    directory that contains it), and this box runs parallel lanes whose edits and
    untracked scratch must not be recorded against a candidate that never touched
    them.

    Taken at dispatch, before ``task.json`` exists, so the snapshot is a picture of
    the tree the worker is about to receive.
    """
    found: List[str] = []
    out = _git("status", "--porcelain")
    for line in (out.stdout or "").splitlines():
        text = line.rstrip()
        if len(text) < 4:
            continue
        entry = text[3:].strip()
        if " -> " in entry:                       # a rename names both ends
            old, new = entry.split(" -> ", 1)
            found.extend([old.strip().strip('"'), new.strip().strip('"')])
        elif entry:
            found.append(entry.strip('"'))
    out = _git("ls-files", "--others", "--exclude-standard")
    for line in (out.stdout or "").splitlines():
        rel = line.strip()
        if rel:
            found.append(rel)
    return sorted({p.replace("\\", "/") for p in found if p.strip()})


def task_contract(item: Dict[str, Any], brief: Dict[str, Any],
                  pre_changed: Optional[List[str]] = None) -> Dict[str, Any]:
    """The task JSON `ty_task_runner.py` consumes, plus what the evaluator reads.

    The item is spread in rather than re-listed field by field. The field-by-field
    version silently dropped whatever it did not name, and what it dropped was
    ``check_sha256`` - so the tamper gate could never fire, however carefully the
    item pinned its check.

    ``pre_changed`` is the dispatch snapshot (plus the launcher's own runtime
    files). It is the only way the evaluator can tell another lane's dirty file
    from this candidate's work, so it travels with the contract and is frozen
    beside it.
    """
    commands = item.get("acceptance_commands") or []
    if isinstance(commands, str):
        commands = [[commands]]
    snapshot = pre_changed if pre_changed is not None else item.get("pre_changed")
    if isinstance(snapshot, str):
        snapshot = [snapshot]
    contract: Dict[str, Any] = {**item}
    contract.update({
        "id": item.get("id"),
        "objective": item.get("next") or item.get("title") or "",
        "write_paths": list(item.get("write_paths") or []),
        "read_paths": list(item.get("read_paths") or []),
        "acceptance_commands": commands,
        "required_files": list(item.get("required_files") or []),
        "max_steps": int(item.get("max_steps") or 12),
        "max_repairs": int(item.get("max_repairs") or 2),
        "model": item.get("model") or os.environ.get("TY_WORKER_MODEL", ""),
        "pre_changed": sorted({str(p).replace("\\", "/")
                               for p in (snapshot or []) if str(p).strip()}),
        "pre_changed_source": "dispatch",
        "_cycle": brief.get("cycle"),
    })
    return contract


def runnable(item: Dict[str, Any]) -> tuple[bool, str]:
    if not item.get("write_paths"):
        return False, "no write_paths declared"
    if not item.get("acceptance_commands"):
        return False, "no acceptance_commands declared"
    return True, ""


def estimate_tokens(payload: Any) -> int:
    """Last-resort accounting: 4 characters per token.

    Kept for callers that need a number out of an arbitrary object. It is **not**
    the cycle figure any more -- `measure_cycle_tokens` asks the session store
    first, because this arithmetic under-reported real spend by ~80x when it was
    applied to the launcher's own small result file instead of the session.
    """
    text = json.dumps(payload, default=str) if not isinstance(payload, str) else payload
    return max(0, len(text) // 4)


def measure_cycle_tokens(worker_out: Dict[str, Any]) -> Dict[str, Any]:
    """What did this cycle actually spend? Store first, payload estimate second.

    Measured 2026-11-06: one real deepseek session cost 180,803 tokens while the
    launcher recorded 2,162, because completion["tokens"] was chars/4 over the
    launcher's own ``worker_result.json``. The session store already holds the
    real number; counting the launcher's summary of it measured the wrapper, not
    the work, and left the 3M/day cap soft.

    Returns ``{"tokens": int, "source": str, "session_id": str|None}`` where
    ``source`` is the meter's own label (``session_v2`` -- real counters,
    ``session_message`` -- stored message lengths) or ``payload_estimate`` when
    the store could answer nothing and ``estimate_payload`` stood in. A meter
    failure is never allowed to kill a cycle: it degrades to the estimate and
    says so, because an unmeasured cycle must still be a completed cycle.
    """
    session_id = str((worker_out or {}).get("session_id") or "").strip()
    if session_id:
        try:
            got = meter.estimate_session(session_id) or {}
        except Exception:  # noqa: BLE001 - the meter is documented total; trust but verify
            got = {}
        tokens = got.get("tokens")
        if tokens is not None:
            return {"tokens": max(0, int(tokens)),
                    "source": str(got.get("source") or "session"),
                    "session_id": session_id}
    return {"tokens": meter.estimate_payload(worker_out or {}),
            "source": "payload_estimate",
            "session_id": session_id or None}


# ------------------------------------------------------------------------ worker
def default_worker(task_path: Path, result_path: Path) -> int:
    cmd = [sys.executable, str(ROOT / "scripts" / "ty_task_runner.py"),
           "--task", str(task_path), "--result", str(result_path)]
    proc = subprocess.run(cmd, cwd=str(ROOT), timeout=WORKER_TIMEOUT_S,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        _append(JOURNAL, {"event": "worker_failed", "code": proc.returncode,
                          "stderr": (proc.stderr or "")[-600:]})
    return proc.returncode


def _opencode_exe() -> str:
    """Resolve the real CLI binary, not the npm shell shim.

    Measured 2026-11-06 on opencode v2.2.5: `shutil.which("opencode")` returns
    ``opencode.CMD``, which only works because CreateProcess happens to hand it to
    cmd.exe, and every argument (including a prompt) is re-parsed by a shell. The
    package ships a real executable one directory down; use it.
    """
    import shutil

    override = os.environ.get("TY_OPENCODE_EXE", "").strip()
    if override:
        return override
    shim = shutil.which("opencode") or shutil.which("opencode.cmd")
    if shim:
        shim_dir = Path(shim).parent
        packaged = shim_dir / "node_modules" / "@opencode" / "cli" / "bin" / "opencode.exe"
        if packaged.is_file():
            return str(packaged)
        if Path(shim).suffix.lower() in (".cmd", ".bat", ".ps1"):
            # No packaged binary: fall back to the shim through cmd.exe, which is
            # the only thing that can execute it.
            return shim
        return shim
    return "opencode"


def _session_db() -> Path:
    return (Path(os.environ.get("USERPROFILE", ""))
            / ".local" / "share" / "opencode" / "opencode.db")


def _session_model(session_id: str,
                   db_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Which model actually answered? Read the session store, never assume.

    Measured 2026-11-06: an ``opencode run`` session leaves ``session_v2.model``
    NULL - the model is written on the assistant ``session_message`` row instead.
    Reading only ``session_v2`` reported provenance as null on every dispatch, so
    the assistant row is now the primary source and session_v2 the fallback.
    """
    if not session_id:
        return None
    db = Path(db_path) if db_path else _session_db()
    if not db.is_file():
        return None
    info: Dict[str, Any] = {"agent": None, "model_id": None, "provider": None,
                            "variant": None, "cost": None, "tokens": None,
                            "source": None}
    try:
        import sqlite3

        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        try:
            row = conn.execute(
                "SELECT agent, model, cost FROM session_v2 WHERE id=?",
                (session_id,)).fetchone()
            if row:
                info["agent"], info["cost"] = row[0], row[2]
                if row[1]:
                    try:
                        model = json.loads(row[1])
                    except (TypeError, ValueError):
                        model = {}
                    info["model_id"] = model.get("id")
                    info["provider"] = model.get("providerID")
                    info["variant"] = model.get("variant")
                    info["source"] = "session_v2"
            try:
                msg = conn.execute(
                    "SELECT data FROM session_message WHERE session_id=? AND type='assistant' "
                    "ORDER BY seq DESC LIMIT 1", (session_id,)).fetchone()
            except sqlite3.Error:
                msg = None
            if msg and msg[0]:
                data = json.loads(msg[0])
                model = data.get("model") or {}
                info["model_id"] = info["model_id"] or model.get("id")
                info["provider"] = info["provider"] or model.get("providerID")
                info["variant"] = info["variant"] or model.get("variant")
                info["agent"] = info["agent"] or data.get("agent")
                info["tokens"] = data.get("tokens")
                if data.get("cost") is not None:
                    info["cost"] = data.get("cost")
                if info["model_id"]:
                    info["source"] = "session_message"
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 - provenance is best effort, absence is reported
        return None
    if not (info["model_id"] or info["agent"]):
        return None
    return info


def _read_run_stream(stdout: str) -> Dict[str, Any]:
    """Parse `opencode run --format json` JSONL into text, session and errors.

    Measured line shape (v2.2.5):
        {"type":"text","sessionID":"ses_...","part":{"type":"text","text":"pong"}}
    The text lives in ``part.text``; an earlier reader looked only at
    ``event["text"]``, so every dispatch recorded ``text: ""`` and the launcher
    had no captured output even though the CLI had answered.
    """
    events: List[Dict[str, Any]] = []
    text: List[str] = []
    session_id = ""
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        events.append(event)
        part = event.get("part") if isinstance(event.get("part"), dict) else {}
        session_id = str(event.get("sessionID") or part.get("sessionID") or session_id)
        if event.get("type") == "text":
            chunk = part.get("text") or event.get("text") or event.get("content") or ""
            if isinstance(chunk, str) and chunk:
                text.append(chunk)
    errors = []
    for event in events:
        if event.get("type") == "error":
            err = event.get("error") or event.get("message") or "error"
            errors.append(err if isinstance(err, str) else json.dumps(err)[:400])
    return {"events": events, "text": "".join(text), "session_id": session_id,
            "errors": errors}


def deepseek_worker(task_path: Path, result_path: Path) -> int:
    """The owner's coding model (DeepSeek V4.1 Flash on OpenCode), via `run`.

    Transport measured 2026-11-06 on opencode v2.2.5 (see
    reports/ty/A17_worker_lane.md): ``opencode run --agent <lane> --format json
    --auto`` with the prompt on **stdin** exits 0 in ~1.5 s and streams JSONL;
    a positional prompt, ``--format default``, ``-s <session>`` and an explicit
    ``--model`` all work too. The prompt stays on stdin because a 16 KB contract
    would exceed the Windows command line.

    The model is told what to change and which files it may touch. The launcher
    runs the acceptance commands afterwards; the worker never grades itself.
    """
    task = json.loads(task_path.read_text(encoding="utf-8"))
    lane = os.environ.get("TY_WORKER_AGENT", "tys")
    allowed = ", ".join(task.get("write_paths") or []) or "(none - refuse)"
    checks = "; ".join(" ".join(c) for c in (task.get("acceptance_commands") or []))
    prompt = (
        "You are the Northstar OS autonomy worker. Work only in this repository. "
        f"You may modify ONLY: {allowed}. Do not touch any other file, do not edit tests, "
        "do not commit, and do not grade your own work.\n\n"
        f"TASK: {task.get('objective')}\n\n"
        f"ACCEPTANCE (the launcher runs this afterwards): {checks}\n\n"
        "Make the smallest correct change that satisfies the check. If it cannot pass "
        "without touching a file outside the allowlist, change nothing and say why in one "
        "line. When finished, stop."
    )
    exe = _opencode_exe()
    cmd = [exe, "run", "--agent", lane, "--format", "json", "--auto"]
    model_override = (task.get("model") or os.environ.get("TY_WORKER_MODEL") or "").strip()
    if model_override:
        cmd[4:4] = ["--model", model_override]
    started = time.time()
    events: List[Dict[str, Any]] = []
    parsed: Dict[str, Any] = {"text": "", "session_id": "", "errors": []}
    stderr_tail = ""
    try:
        proc = subprocess.run(cmd, cwd=str(ROOT), timeout=WORKER_TIMEOUT_S,
                              capture_output=True, text=True, input=prompt)
        code = proc.returncode
        parsed = _read_run_stream(proc.stdout)
        events = parsed["events"]
        stderr_tail = (proc.stderr or "")[-800:]
    except subprocess.TimeoutExpired:
        code, stderr_tail = 124, "worker timeout"
    except OSError as exc:
        code, stderr_tail = 127, f"opencode_not_runnable: {exc}"

    errors: List[str] = list(parsed["errors"])
    text = parsed["text"]
    if code == 0 and not text:
        # The exact failure this unit exists to remove: a silent empty answer that
        # looked like success. Say it out loud instead.
        errors.append("empty_text: opencode run exited 0 but streamed no text")
    session_id = parsed["session_id"]
    provenance = _session_model(session_id)
    ok = code == 0 and not errors
    result_path.write_text(json.dumps({
        "ok": ok,
        "steps": 1,
        "worker": "opencode/run",
        "lane": lane,
        "session_id": session_id,
        "model": provenance,
        "model_provenance_ok": bool((provenance or {}).get("model_id")),
        "seconds": round(time.time() - started, 1),
        "events": len(events),
        "errors": errors[:3],
        "text": text[:4000],
        "exe": exe,
        "stderr": stderr_tail,
        "objective": task.get("objective"),
    }, indent=2), encoding="utf-8")
    _append(JOURNAL, {"event": "deepseek_worker", "code": code, "lane": lane,
                      "session": session_id,
                      "model": (provenance or {}).get("model_id"),
                      "text_chars": len(text),
                      "seconds": round(time.time() - started, 1),
                      "errors": errors[:3]})
    return code


def pre_run_red_gate(commands: List[List[str]]) -> Dict[str, Any]:
    """Is the declared check red *before* the worker runs?

    This is the only check the launcher still runs itself, and it is not a verdict.
    A check that is already green cannot prove anything a worker did, so a cycle
    whose check starts green is deferred instead of dispatched. Whether the patch
    then deserves to ship is `tys_evaluator`'s answer, not this function's.
    """
    results = []
    ok = True
    for cmd in commands:
        if not cmd:
            continue
        started = time.time()
        try:
            proc = subprocess.run([str(c) for c in cmd], cwd=str(ROOT),
                                  timeout=WORKER_TIMEOUT_S, capture_output=True, text=True)
            passed = proc.returncode == 0
            detail = ((proc.stdout or "") + (proc.stderr or ""))[-1200:]
        except subprocess.TimeoutExpired:
            passed, detail = False, "acceptance timeout"
        except OSError as exc:
            # A command the host cannot start is a red check, not a launcher crash.
            # The C3 probe found a malformed contract reaching this point and taking
            # the process down with FileNotFoundError.
            passed, detail = False, f"could not start: {exc}"
        ok = ok and passed
        results.append({"cmd": " ".join(str(c) for c in cmd), "passed": passed,
                        "seconds": round(time.time() - started, 1),
                        "detail": detail})
    return {"ok": ok, "checks": results}


def _frozen_rel(path_text: str) -> str:
    try:
        return Path(path_text).resolve().relative_to(Path(ROOT).resolve()).as_posix()
    except (ValueError, OSError):
        return str(path_text)


def judge_cycle(*, contract: Dict[str, Any], item_id: str, candidate_id: str,
                repo: Path) -> Dict[str, Any]:
    """Freeze the candidate, replay the frozen bytes, then judge the live tree.

    The order is the design, and each step answers a different question:

    ``freeze``          what exactly is on trial? The patch as bytes, the dispatch
                        snapshot and the contract are written to
                        ``state/author/<item>/cand_<k>.{diff,json}`` and sealed, so
                        a verdict can be re-derived from disk months later.
    ``evaluate_frozen`` the verdict. Scope, malformed, target, tamper and
                        regression gates, over the frozen bytes rather than over
                        whatever the worktree says now.
    ``evaluate``        drift. Does the tree that is about to be called shipped
                        still look like the candidate that was judged?

    Returns the evaluator's verdict shape (``ok``/``gate``/``detail``/``commands``)
    plus ``frozen`` (the artifact), ``verdict`` (the frozen replay) and ``live``
    (the drift check). A candidate that cannot be frozen is ``freeze_failed``: an
    unjudged patch is never a shipped patch.

    The live contract excuses the artifact directory itself. Freeze writes into
    ``state/author/``; in this repo that path is gitignored, but a judge that
    depended on a ``.gitignore`` line would refuse every cycle the day somebody
    dropped it.
    """
    repo_path = Path(repo).resolve()
    pre_changed = contract.get("pre_changed") or []
    base = str(candidate_id)

    frozen: Dict[str, Any] = {}
    verdict: Dict[str, Any] = {}
    problem = ""
    for attempt in (base, f"{base}-b"):
        try:
            frozen = evaluator.freeze(repo=repo_path, item_id=str(item_id),
                                      candidate_id=attempt, contract=contract,
                                      pre_changed=pre_changed)
        except (RuntimeError, OSError) as exc:
            problem = str(exc)
            continue
        verdict = evaluator.evaluate_frozen(Path(frozen["json"]), repo=repo_path)
        if verdict.get("gate") != "already_scored":
            break
        # A cycle number that repeats (a reset queue) finds a candidate already
        # judged. Freezing under a second id keeps the evidence append-only and
        # still forces a fresh run of the gates.
        problem = str(verdict.get("detail") or "already scored")
    else:
        return {"ok": False, "gate": "freeze_failed",
                "detail": f"the candidate could not be frozen or re-judged: {problem}"[:2000],
                "commands": [], "frozen": "", "verdict": {}, "live": {}}

    out: Dict[str, Any] = {
        "ok": bool(verdict.get("ok")),
        "gate": str(verdict.get("gate") or "artifact_invalid"),
        "detail": str(verdict.get("detail") or ""),
        "commands": list(verdict.get("commands") or []),
        "frozen": _frozen_rel(str(frozen.get("json") or "")),
        "verdict": verdict,
        "live": {},
    }
    if not out["ok"]:
        return out

    excused = list(pre_changed)
    try:
        excused.append(Path(frozen["json"]).resolve().parent
                       .relative_to(repo_path).as_posix() + "/")
    except ValueError:
        pass
    live_contract = {**contract, "pre_changed": sorted({str(p) for p in excused})}
    live = evaluator.evaluate(contract=live_contract, repo=repo_path)
    out["live"] = live
    if not live.get("ok"):
        out.update(ok=False, gate=f"live_{live.get('gate')}",
                   detail=("the live tree no longer matches the frozen candidate: "
                           + str(live.get("detail") or ""))[:2000],
                   commands=out["commands"] + list(live.get("commands") or []))
    return out


Worker = Callable[[Path, Path], int]

MODEL_BASE_URL = os.environ.get("TY_WORKER_BASE_URL", "http://127.0.0.1:8080")#: The worker can speak to llama.cpp (OpenAI-compatible, 8080) or to Ollama's
#: native adapter (11434). The preflight must check the one the worker will use,
#: otherwise a healthy Ollama lane is reported as "down".
MODEL_PROVIDER = os.environ.get("TYS_CODING_PROVIDER", "compat").lower()
OLLAMA_BASE_URL = os.environ.get("TYS_CODING_URL", "http://127.0.0.1:11434")


def model_up(timeout_s: float = 3.0) -> bool:
    """Is the lane the worker will actually use reachable?"""
    import urllib.error
    import urllib.request

    if MODEL_PROVIDER == "ollama":
        url = OLLAMA_BASE_URL.rstrip("/") + "/api/tags"
    else:
        url = MODEL_BASE_URL.rstrip("/") + "/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, ValueError):
        return False


def start_model(wait_s: float = 240.0) -> bool:
    """Start the local LLM lane and wait for its health endpoint."""
    script = ROOT / "scripts" / "start-northstar-llm.ps1"
    if not script.is_file():
        return False
    subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                      "-File", str(script)], cwd=str(ROOT),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if model_up():
            return True
        time.sleep(5)
    return False


def deepseek_lane_up(timeout_s: float = 60.0) -> bool:
    """Is the OpenCode CLI actually runnable from this process?

    `model_up()` asks llama.cpp / Ollama for a heartbeat; it says nothing about a
    CLI lane, and a deepseek dispatch must not be refused because a local server
    the worker never calls happens to be down (or passed because it is up).
    """
    exe = _opencode_exe()
    try:
        proc = subprocess.run([exe, "--version"], cwd=str(ROOT), timeout=timeout_s,
                              capture_output=True, text=True)
    except (OSError, subprocess.TimeoutExpired):
        return False
    out = ((proc.stdout or "") + (proc.stderr or "")).lower()
    return proc.returncode == 0 and "opencode" in out


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True)


def _dirty(paths: List[str]) -> List[str]:
    """Declared paths that already differ from HEAD. A dirty target is refused."""
    if not paths:
        return []
    out = _git("status", "--porcelain", "--", *paths)
    return [line[3:].strip() for line in (out.stdout or "").splitlines() if line.strip()]


def _tracked() -> set:
    out = _git("ls-tree", "-r", "--name-only", "HEAD")
    return {line.strip() for line in (out.stdout or "").splitlines() if line.strip()}


def _restore(paths: List[str]) -> List[str]:
    """Undo a failed attempt with git, not with an in-memory snapshot.

    The snapshot version was dangerous (measured 2026-11-06): a path that was
    absent when the snapshot was taken was *deleted* on restore, which removed a
    committed file that another session had just created. Git knows what belongs
    in the tree; a memory image does not.
    """
    restored: List[str] = []
    if not paths:
        return restored
    tracked = _tracked()
    source = [p for p in paths if p in tracked]
    if source:
        _git("checkout", "--", *source)
        restored.extend(source)
    for rel in paths:
        if rel in tracked:
            continue
        path = ROOT / rel
        if path.is_file():
            try:
                path.unlink()
                restored.append(rel)
            except OSError as exc:
                _append(JOURNAL, {"event": "restore_failed", "path": rel, "error": str(exc)})
    return restored


def _run_cycle(*, worker: Worker, dry_run: bool, cycle_budget: int) -> Dict[str, Any]:
    """One cycle: reserve, run the worker, validate, complete."""
    brief_out = runner.cmd_next(write_brief=True)
    if brief_out != 0:
        # Exit 6 means the generator ran and found nothing: that is starvation, not
        # "the queue file is empty". The watchdog backs off on the word.
        return {"ok": False, "stop": True, "code": brief_out,
                "reason": {3: "STOP", 4: "token_cap", 5: "lease_held",
                           6: "starvation"}.get(brief_out, f"next_exit_{brief_out}")}
    brief = json.loads(BRIEF.read_text(encoding="utf-8"))["brief"]
    queue = runner.load_queue()
    item = next((i for i in queue.get("items", []) if i.get("id") == brief["item"]), {})
    ok, why = runnable(item)
    if not ok:
        runner.mark(queue, str(item.get("id")), "pending",
                    needs_author=why, defer_until_cycle=int(brief["cycle"]) + 1)
        runner._clear_lease("not runnable")
        _append(JOURNAL, {"event": "skipped_not_runnable", "item": item.get("id"),
                          "reason": why})
        return {"ok": True, "skipped": True, "item": item.get("id"), "reason": why}

    # ``runnable`` only asks whether the two lists are non-empty. A contract that is
    # present but malformed (a shell string, a refused token) must be refused here,
    # at dispatch, not discovered by the pre-run gate as a FileNotFoundError.
    problems = runner.validate_contract(item)
    if problems:
        detail = "; ".join(problems[:3])
        runner.mark(queue, str(item.get("id")), "pending",
                    needs_author=detail, defer_until_cycle=int(brief["cycle"]) + 1)
        runner._clear_lease("invalid contract")
        _append(JOURNAL, {"event": "skipped_invalid_contract",
                          "item": item.get("id"), "problems": problems[:5]})
        return {"ok": True, "skipped": True, "item": item.get("id"),
                "reason": "invalid_contract", "problems": problems[:5]}

    if dry_run:
        # C2 is a claim about rotations, and a dry run that never completes can never
        # show one. So the dry run exercises the real bookkeeping - reserve, record,
        # rotate - against the redirected state root, and no worker is involved.
        completion = {"item": brief["item"], "cycle": brief["cycle"],
                      "shipped": False, "tokens": 0,
                      "measurements": {"dry_run": True},
                      "evidence": []}
        path = STATE / "dry_completion.json"
        path.write_text(json.dumps(completion, indent=2), encoding="utf-8")
        rc = runner.cmd_complete(str(path))
        _append(JOURNAL, {"event": "dry_run_cycle", "item": item.get("id"),
                          "complete_exit": rc})
        return {"ok": rc == 0, "dry_run": True, "item": item.get("id"),
                "complete_exit": rc}

    task_path = STATE / "task.json"
    result_path = STATE / "worker_result.json"
    # Snapshot the tree before the worker (and before task.json exists). Every
    # path already dirty here is somebody else's - another lane's edit, an
    # operator's scratch, this launcher's own runtime files - and the evaluator
    # must not read it as the candidate's patch.
    pre_changed = sorted(set(dispatch_snapshot()) | set(LAUNCHER_PATHS))
    contract = task_contract(item, brief, pre_changed=pre_changed)
    checks = contract.get("acceptance_commands") or []

    # Pre-run red gate: a check that is already green cannot prove anything a
    # worker did. Without this, a cycle "ships" by running a passing test. This is
    # a dispatch guard, not the verdict - the verdict is the evaluator's.
    before = pre_run_red_gate(checks)
    if before.get("ok"):
        # A check that is green before the worker runs cannot prove a fix. That is a
        # mis-scoped contract, not a coincidence to retry: deferring it two cycles
        # only re-admits it immediately (deferral is soft by design), and the C3
        # probe measured 40 acceptance runs in 54 s from exactly that loop. The stop
        # has to be a status change, the same rule A13 applies to rejections.
        runner.mark(runner.load_queue(), str(item.get("id")), "needs_author",
                    check_already_green=True,
                    needs_author=("check_already_green: the check passes before any "
                                  "work, so it cannot prove a patch"),
                    defer_until_cycle=None)
        runner._clear_lease("check already green")
        _append(JOURNAL, {"event": "check_already_green", "item": item.get("id"),
                          "parked": True})
        return {"ok": True, "skipped": True, "item": item.get("id"),
                "reason": "check_already_green"}

    snap = list(contract.get("write_paths") or [])
    dirty = _dirty(snap)
    if dirty:
        # A dirty target means somebody else owns these bytes (an operator edit or
        # a parallel lane). Restore would overwrite their work, so refuse instead.
        runner.mark(runner.load_queue(), str(item.get("id")), "pending",
                    blocked_reason=f"targets_dirty: {', '.join(dirty[:3])}",
                    defer_until_cycle=int(brief["cycle"]) + 1)
        runner._clear_lease("dirty targets")
        _append(JOURNAL, {"event": "targets_dirty", "item": item.get("id"), "paths": dirty[:5]})
        return {"ok": True, "skipped": True, "item": item.get("id"),
                "reason": "targets_dirty"}
    task_path.write_text(json.dumps(contract, indent=2), encoding="utf-8")
    if result_path.exists():
        result_path.unlink()
    started = time.time()
    try:
        code = worker(task_path, result_path)
    except subprocess.TimeoutExpired:
        code = 124
    elapsed = round(time.time() - started, 1)
    worker_out = {}
    if result_path.exists():
        try:
            worker_out = json.loads(result_path.read_text(encoding="utf-8"))
        except ValueError:
            worker_out = {}
    # The verdict is not the launcher's to give. A model that writes and grades is
    # not a verification, and neither is a launcher that re-runs the same command
    # and calls the exit code a judgement: freeze the candidate, replay the frozen
    # bytes through the five gates, then check the live tree against it.
    judged = judge_cycle(contract=contract, item_id=str(item.get("id")),
                         candidate_id=f"{int(brief.get('cycle') or 0):04d}", repo=ROOT)
    shipped = bool(judged.get("ok")) and int(code or 0) == 0 \
        and bool(worker_out.get("ok", True))
    worker_out["acceptance"] = {"ok": bool(judged.get("ok")),
                                "gate": judged.get("gate"),
                                "checks": judged.get("commands") or []}
    worker_out["verdict"] = judged
    worker_out["before_green"] = before.get("ok")
    _append(JOURNAL, {"event": "candidate_judged", "item": brief["item"],
                      "cycle": brief["cycle"], "gate": judged.get("gate"),
                      "ok": bool(judged.get("ok")), "frozen": judged.get("frozen"),
                      "live_gate": (judged.get("live") or {}).get("gate"),
                      "detail": str(judged.get("detail") or "")[:600]})
    measured = measure_cycle_tokens(worker_out)
    _append(JOURNAL, {"event": "tokens_measured", "item": brief["item"],
                      "tokens": measured["tokens"], "source": measured["source"],
                      "session": measured["session_id"]})
    if not shipped:
        restored = _restore(snap)
        if restored:
            _append(JOURNAL, {"event": "reverted_bytes", "item": item.get("id"),
                              "paths": restored})
    evidence_paths: List[str] = [str(p) for p in (worker_out.get("evidence") or [])]
    if shipped and not evidence_paths:
        # The runner refuses a shipped cycle with no evidence, and it is right to:
        # "I fixed it" is not evidence. The worker's own report plus the checks it
        # ran IS the record, so persist it under state/evidence and cite that.
        ev_dir = ROOT / "state" / "evidence"
        ev_dir.mkdir(parents=True, exist_ok=True)
        ev_file = ev_dir / f"cycle_{brief['cycle']:03d}_{brief['item']}.json"
        ev_file.write_text(json.dumps({
            "item": brief["item"], "cycle": brief["cycle"],
            "task": json.loads(task_path.read_text(encoding="utf-8")),
            "worker": worker_out, "worker_exit": code, "seconds": elapsed,
            "tokens": measured["tokens"], "tokens_source": measured["source"],
            "at": _now(),
        }, indent=2, default=str), encoding="utf-8")
        evidence_paths = [str(ev_file.relative_to(ROOT)).replace("\\", "/")]
    completion = {
        "item": brief["item"],
        "cycle": brief["cycle"],
        "shipped": shipped,
        "tag": brief.get("rollback_tag") if shipped else "",
        "evidence": evidence_paths,
        # The number the daily cap is enforced with. Session measurement when the
        # store has one, payload estimate (labelled) when it does not; never 0 by
        # accident, because 0 reads as "this cycle was free".
        "tokens": measured["tokens"],
        "tokens_source": measured["source"],
        "before": worker_out.get("before") or {},
        "after": worker_out.get("after") or {},
        "worker_exit": code,
        "seconds": elapsed,
        # Which gate judged the candidate and where the frozen bytes live. A
        # rejection is only useful if it names the gate that produced it.
        "verdict": {"gate": judged.get("gate"), "ok": bool(judged.get("ok")),
                    "detail": str(judged.get("detail") or "")[:600],
                    "frozen": judged.get("frozen") or ""},
    }
    completion_path = STATE / "completion.json"
    completion_path.write_text(json.dumps(completion, indent=2), encoding="utf-8")
    rc = runner.cmd_complete(str(completion_path))
    if rc == 7 and shipped:
        # A shipped cycle with no evidence is refused by the runner; record the
        # worker's own report as the evidence so the refusal is diagnosable.
        _append(JOURNAL, {"event": "completion_refused", "item": brief["item"],
                          "worker": worker_out})
    return {"ok": rc == 0, "item": brief["item"], "shipped": shipped,
            "cycle": brief["cycle"], "seconds": elapsed, "worker_exit": code,
            "tokens": measured["tokens"], "tokens_source": measured["source"],
            "gate": judged.get("gate"), "detail": judged.get("detail"),
            "frozen": judged.get("frozen"), "complete_exit": rc}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Loop driver: next -> worker -> complete.")
    parser.add_argument("--max-cycles", type=int, default=100)
    parser.add_argument("--max-hours", type=float, default=8.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-token-budget", type=int, default=0,
                        help="stop after this many estimated tokens this run")
    parser.add_argument("--start-model", action="store_true",
                        help="start the local LLM lane if its health endpoint is down")
    parser.add_argument("--worker", choices=("ty", "deepseek"), default="ty",
                        help="ty = local coding lane; deepseek = OpenCode CLI (owner's model)")
    parser.add_argument("--per-session", type=int, default=runner.CYCLES_PER_SESSION,
                        help="rotate the worker session after this many cycles "
                             "(the gate's acceptance runs use it explicitly)")
    ns = parser.parse_args(argv)
    runner.CYCLES_PER_SESSION = max(1, int(ns.per_session))

    started = time.time()
    deadline = started + ns.max_hours * 3600
    cycles = 0
    failures = 0
    skips = 0
    tokens = 0
    reason = "max_cycles"

    heartbeat(state="starting", dry_run=ns.dry_run, max_cycles=ns.max_cycles,
              max_hours=ns.max_hours)
    lane = "deepseek" if ns.worker == "deepseek" else "ty"
    if not ns.dry_run:
        # Preflight the lane the worker will actually use. Before this, a deepseek
        # dispatch was gated on llama.cpp's health endpoint - a process the worker
        # never calls - so the launcher reported the lane down while `opencode run`
        # was fine.
        if lane == "deepseek":
            ready, label, hint = (deepseek_lane_up(), _opencode_exe(),
                                  "set TY_OPENCODE_EXE or install the opencode CLI")
        else:
            ready, label, hint = (model_up(), MODEL_BASE_URL,
                                  "run scripts/start-northstar-llm.ps1 or pass --start-model")
        if not ready:
            # A dead lane is not a failed cycle: burning an attempt per cycle
            # against a refused connection teaches nothing and quietly ages the queue.
            _append(JOURNAL, {"event": "model_lane_down", "lane": lane, "target": label})
            if lane == "ty" and ns.start_model and start_model():
                _append(JOURNAL, {"event": "model_lane_started", "base_url": MODEL_BASE_URL})
            else:
                heartbeat(state="stopped", reason="model_lane_down", lane=lane,
                          cycles=0, target=label)
                _append(JOURNAL, {"event": "launcher_stopped",
                                  "reason": "model_lane_down", "lane": lane, "cycles": 0})
                print(json.dumps({"stopped": True, "reason": "model_lane_down",
                                  "lane": lane, "target": label, "hint": hint},
                                 indent=2))
                return 0
    while cycles < ns.max_cycles:
        if time.time() >= deadline:
            reason = "max_hours"
            break
        if (ROOT / "STOP").exists():
            reason = "STOP"
            break
        before = runner._tokens_today()
        out = _run_cycle(worker=(deepseek_worker if ns.worker == "deepseek" else default_worker),
                         dry_run=ns.dry_run,
                         cycle_budget=ns.max_cycles - cycles)
        if out.get("stop"):
            reason = out.get("reason", "stop")
            _append(JOURNAL, {"event": "stopped", "reason": reason})
            break
        cycles += 1
        tokens += max(0, runner._tokens_today() - before)
        if out.get("skipped"):
            # A skipped item is not a cycle: it means the queue surfaced work that
            # cannot be dispatched (no checks, no write scope). Counting it as a
            # cycle would let the loop burn its whole budget on unrunnable items.
            cycles -= 1
            skips += 1
            if skips >= 40:
                reason = "no_runnable_items"
                break
            failures = 0
        elif out.get("ok"):
            failures = 0
            skips = 0
        else:
            failures += 1
            if failures >= MAX_FAILURE_STREAK:
                reason = "worker_failure_streak"
                break
        if ns.max_token_budget and tokens >= ns.max_token_budget:
            reason = "token_budget"
            break
        heartbeat(state="running", cycles=cycles, tokens_estimate=tokens,
                  last=out, failures=failures, skips=skips)

    heartbeat(state="stopped", reason=reason, cycles=cycles,
              tokens_estimate=tokens, seconds=round(time.time() - started, 1))
    _append(JOURNAL, {"event": "launcher_stopped", "reason": reason, "cycles": cycles,
                      "tokens_estimate": tokens})
    print(json.dumps({"stopped": True, "reason": reason, "cycles": cycles,
                      "tokens_estimate": tokens,
                      "seconds": round(time.time() - started, 1)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
