"""Tys Assistant — the admin/operator automation agent.

**Who this is.** Tys Assistant is the internal automation agent that runs
bounded admin work orders on this box: it plans a small number of steps, routes
each one to the right existing lane, records evidence, and checkpoints so an
interrupted run can be resumed. It is **admin/operator-facing only**. It is not
a subscriber feature, it is not mounted in the customer shell, and it does not
replace or rename the product chat assistant (the chat protocol keeps speaking
the `"assistant"` role — that is a wire-format name, not a persona).

**Who does the work.** Tys Assistant owns no model. It routes:

| lane      | executor                                   | why                       |
|-----------|--------------------------------------------|---------------------------|
| `inspect` | this process (bounded file reads)          | deterministic, no model   |
| `coding`  | the Qwen3.8-27B IQ3_XXS llama.cpp worker   | GPU-only, started on demand |
| `browser` | Chrome Connect controller (policy + gate)  | never a raw browser handle |
| `creative`| existing studio/ComfyUI services           | serialized on one GPU     |

Orchestration itself (deciding the plan) uses the **small persistent local CPU
model** — Bojo via Ollama, which is pinned to CPU by its own model definition
(`scripts/bojo-cpu.Modelfile`) and therefore holds no VRAM.

**What stops it.** Every work order carries a concrete objective, an allowed
scope, evidence requirements and hard limits (steps, iterations, wall clock).
There is no unbounded loop: `run()` executes at most `max_steps` steps inside at
most `max_wall_s`, then checkpoints and returns. The queue is advanced by
explicit runs (`drain()`), never by a self-scheduling daemon.

**What it will not do.** It does not approve its own spending, does not touch
Amazon, and does not bypass Chrome Connect's policy. Those stay with the owner
and with the controller.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

AGENT_ID = "tys-assistant"
AGENT_NAME = "Tys Assistant"
AGENT_KIND = "admin_automation"
AGENT_SURFACE = "admin"          # never "customer"
#: The chat wire protocol keeps this literal role name. Documented here so a
#: future edit cannot "helpfully" rename it to `tys` and break every client.
CHAT_PROTOCOL_ROLE_UNCHANGED = "assistant"

LANES = ("inspect", "coding", "browser", "creative")

#: Defaults chosen so a single `run()` is always short enough to observe and
#: always leaves a resumable checkpoint behind.
DEFAULT_LIMITS: Dict[str, Any] = {
    "max_steps": 8,
    "max_iterations": 3,
    "max_wall_s": 900,
}
HARD_LIMITS: Dict[str, Any] = {
    "max_steps": 40,
    "max_iterations": 10,
    "max_wall_s": 3600,
}

#: Roles allowed to file a work order. Production is stricter than development:
#: on a hosted multi-tenant box only platform admins may drive the operator's
#: own machine services.
ADMIN_ROLES = {
    "operator", "organization_admin", "organization_owner",
    "platform_admin", "internal_platform_admin", "owner", "admin",
}
PLATFORM_ROLES = {"platform_admin", "internal_platform_admin", "admin"}

#: Owner approval gates that this agent may not self-approve. A step whose
#: objective touches one of these is refused with `owner_approval_required`
#: instead of being executed.
PAID_SCOPE_PATTERNS = (
    r"\bspend\b", r"\bpurchase\b", r"\bbuy\b", r"\bpaid\b", r"\bcredit\b",
    r"\bsubscribe\b", r"\bbilling\b", r"\bcheckout\b",
)
AMAZON_SCOPE_PATTERN = r"\bamazon\b|\bamzn\b|\bseller\s*central\b"


class TysError(RuntimeError):
    """A refusal with a stable code the API can surface verbatim."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tys_inspect_adapter() -> "InspectAdapter":
    """A standalone read-only context gatherer (see `_context_with_text`)."""
    return InspectAdapter()


def _default_db_path() -> str:
    return os.environ.get(
        "TYS_DB_PATH",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "tys_assistant.db"),
    )


# ---------------------------------------------------------------------------
# Probe helpers shared by the adapters (cheap, offline, no side effects)
# ---------------------------------------------------------------------------

def _http_json(url: str, payload: Optional[dict] = None, timeout: float = 5.0) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace") or "{}")


def _port_open(host: str, port: int, timeout: float = 1.5) -> bool:
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _listening_pid(port: int) -> Optional[int]:
    """PID listening on `port`, or None. Windows-first, psutil when available."""
    try:
        import psutil  # type: ignore

        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and getattr(conn.laddr, "port", None) == port and conn.status == "LISTEN":
                return conn.pid
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Durable store: queue + events (evidence trail lives in both places)
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tys_tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    status TEXT NOT NULL,
    owner TEXT,
    scope_json TEXT NOT NULL,
    evidence_required_json TEXT NOT NULL,
    limits_json TEXT NOT NULL,
    steps_json TEXT NOT NULL,
    cursor INTEGER NOT NULL DEFAULT 0,
    iteration INTEGER NOT NULL DEFAULT 0,
    checkpoint_json TEXT,
    next_action TEXT,
    result_json TEXT,
    blockers_json TEXT,
    stop_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS tys_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_tys_events_task ON tys_events(task_id, seq);
CREATE INDEX IF NOT EXISTS idx_tys_tasks_status ON tys_tasks(status, created_at);
"""


class TysStore:
    """SQLite-backed task queue + append-only event log.

    One file, one connection, guarded by a lock: the agent is single-writer by
    design (it is an automation agent, not a worker pool), and a lost SQLite
    connection would otherwise be the only thing standing between a crash and a
    resumable checkpoint.
    """

    def __init__(self, path: Optional[str] = None):
        self.path = path or _default_db_path()
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- tasks -------------------------------------------------------------

    def save(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task = dict(task)
        task["updated_at"] = _now()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO tys_tasks (id, title, objective, status, owner, scope_json,
                    evidence_required_json, limits_json, steps_json, cursor, iteration,
                    checkpoint_json, next_action, result_json, blockers_json, stop_reason,
                    created_at, updated_at, started_at, finished_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title, objective=excluded.objective,
                    status=excluded.status, scope_json=excluded.scope_json,
                    evidence_required_json=excluded.evidence_required_json,
                    limits_json=excluded.limits_json, steps_json=excluded.steps_json,
                    cursor=excluded.cursor, iteration=excluded.iteration,
                    checkpoint_json=excluded.checkpoint_json,
                    next_action=excluded.next_action, result_json=excluded.result_json,
                    blockers_json=excluded.blockers_json, stop_reason=excluded.stop_reason,
                    updated_at=excluded.updated_at, started_at=excluded.started_at,
                    finished_at=excluded.finished_at
                """,
                (
                    task["id"], task["title"], task["objective"], task["status"],
                    task.get("owner"), json.dumps(task.get("scope") or {}),
                    json.dumps(task.get("evidence_required") or []),
                    json.dumps(task.get("limits") or {}),
                    json.dumps(task.get("steps") or []),
                    int(task.get("cursor") or 0), int(task.get("iteration") or 0),
                    json.dumps(task.get("checkpoint")) if task.get("checkpoint") is not None else None,
                    task.get("next_action"), json.dumps(task.get("result")),
                    json.dumps(task.get("blockers") or []),
                    task.get("stop_reason"), task["created_at"], task["updated_at"],
                    task.get("started_at"), task.get("finished_at"),
                ),
            )
            self._conn.commit()
        return task

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute("SELECT * FROM tys_tasks WHERE id=?", (task_id,)).fetchone()
        return _row_to_task(row) if row else None

    def list(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            if status:
                rows = self._conn.execute(
                    "SELECT * FROM tys_tasks WHERE status=? ORDER BY created_at LIMIT ?",
                    (status, int(limit)),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM tys_tasks ORDER BY created_at LIMIT ?", (int(limit),)
                ).fetchall()
        return [_row_to_task(r) for r in rows]

    def next_queued(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM tys_tasks WHERE status IN ('queued','paused') "
                "ORDER BY created_at LIMIT 1"
            ).fetchone()
        return _row_to_task(row) if row else None

    def mark_interrupted(self) -> List[str]:
        """Any task left `running` by a dead process becomes `paused`.

        Called on startup. It is the difference between "resume from checkpoint"
        and "a task that claims to be running forever".
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT id FROM tys_tasks WHERE status='running'"
            ).fetchall()
            ids = [r["id"] for r in rows]
            for tid in ids:
                self._conn.execute(
                    "UPDATE tys_tasks SET status='paused', stop_reason='interrupted', "
                    "next_action='resume', updated_at=? WHERE id=?",
                    (_now(), tid),
                )
            self._conn.commit()
        return ids

    # -- events ------------------------------------------------------------

    def event(self, task_id: str, kind: str, payload: Optional[dict] = None) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO tys_events (task_id, ts, kind, payload_json) VALUES (?,?,?,?)",
                (task_id, _now(), kind, json.dumps(payload or {}, default=str)),
            )
            self._conn.commit()
            return int(cur.lastrowid)

    def events(self, task_id: str, limit: int = 500) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT seq, ts, kind, payload_json FROM tys_events WHERE task_id=? "
                "ORDER BY seq LIMIT ?",
                (task_id, int(limit)),
            ).fetchall()
        out = []
        for r in rows:
            try:
                payload = json.loads(r["payload_json"] or "{}")
            except json.JSONDecodeError:
                payload = {"_raw": r["payload_json"]}
            out.append({"seq": r["seq"], "ts": r["ts"], "kind": r["kind"], "payload": payload})
        return out

    def close(self) -> None:
        with self._lock:
            self._conn.close()


def _row_to_task(row: sqlite3.Row) -> Dict[str, Any]:
    def _loads(key: str, default):
        raw = row[key]
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return default

    return {
        "id": row["id"],
        "title": row["title"],
        "objective": row["objective"],
        "status": row["status"],
        "owner": row["owner"],
        "scope": _loads("scope_json", {}),
        "evidence_required": _loads("evidence_required_json", []),
        "limits": _loads("limits_json", dict(DEFAULT_LIMITS)),
        "steps": _loads("steps_json", []),
        "cursor": row["cursor"],
        "iteration": row["iteration"],
        "checkpoint": _loads("checkpoint_json", None),
        "next_action": row["next_action"],
        "result": _loads("result_json", None),
        "blockers": _loads("blockers_json", []),
        "stop_reason": row["stop_reason"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "started_at": row["started_at"],
        "finished_at": row["finished_at"],
    }


# ---------------------------------------------------------------------------
# Adapters — one per lane. Every adapter returns the same envelope so the agent
# loop never has to special-case a lane.
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    ok: bool
    summary: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    detail: str = ""
    blocked: bool = False          # needs the owner / an external condition
    retriable: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok, "summary": self.summary, "evidence": self.evidence,
            "artifacts": self.artifacts, "detail": self.detail,
            "blocked": self.blocked, "retriable": self.retriable,
        }


class Adapter:
    name = "adapter"

    def available(self) -> Dict[str, Any]:
        return {"adapter": self.name, "available": True, "detail": ""}

    def run_step(self, step: Dict[str, Any], task: Dict[str, Any]) -> StepResult:
        raise NotImplementedError


class InspectAdapter(Adapter):
    """Bounded, deterministic file inspection. No model, no network, no shell.

    Reads are confined to `task.scope.paths` (or the repo root when the scope
    names none). It is the lane Tys Assistant uses to gather the exact context a
    coding step needs, so the 27B worker never has to guess at file contents.
    """

    name = "inspect"
    MAX_BYTES = 120_000
    MAX_FILES = 6

    def _roots(self, task: Dict[str, Any]) -> List[str]:
        """Directories a read must stay inside.

        `scope.paths` is a list of files/dirs the work order allows. The
        allowlist is their containing directories (or the dirs themselves) plus
        nothing else — so declaring a single file does not silently grant the
        whole repository.
        """
        declared = [p for p in (task.get("scope") or {}).get("paths") or [] if p]
        root = _repo_root()
        out: List[str] = []
        for p in declared:
            absolute = p if os.path.isabs(p) else os.path.join(root, p)
            base = absolute if os.path.isdir(absolute) else os.path.dirname(absolute)
            base = os.path.normpath(base)
            if base and base not in out:
                out.append(base)
        return out or [root]

    def _read(self, rel: str, roots: List[str]) -> Dict[str, Any]:
        root = _repo_root()
        candidate = os.path.normpath(rel if os.path.isabs(rel) else os.path.join(root, rel))
        allowed = [os.path.normpath(r) for r in roots]
        if not any(candidate == a or candidate.startswith(a + os.sep) for a in allowed):
            return {"path": rel, "error": "outside_scope"}
        if not os.path.isfile(candidate):
            return {"path": rel, "error": "not_found"}
        try:
            with open(candidate, "r", encoding="utf-8", errors="replace") as fh:
                body = fh.read(self.MAX_BYTES)
            size = os.path.getsize(candidate)
            return {
                "path": os.path.relpath(candidate, root).replace("\\", "/"),
                "abs": candidate,
                "bytes": size,
                "truncated": size > self.MAX_BYTES,
                "text": body,
            }
        except OSError as e:
            return {"path": rel, "error": str(e)}

    def _resolve_files(self, step: Dict[str, Any], task: Dict[str, Any]) -> List[str]:
        """Which files this inspect step may read.

        An explicit `params.files` always wins. Otherwise the step is resolved
        against the work order's `scope.paths` — deterministically, never by
        guessing: a declared path is used when its basename appears in the
        objective, else the declared file paths themselves are used. That is what
        lets a planner (which names objectives, not paths) produce a step that
        actually executes while the scope still bounds what can be read.
        """
        params = step.get("params") or {}
        explicit = [str(f) for f in (params.get("files") or []) if f]
        if explicit:
            return explicit[: self.MAX_FILES]
        declared = [str(p) for p in (task.get("scope") or {}).get("paths") or [] if p]
        if not declared:
            return []
        objective = str(step.get("objective") or "").lower()
        named = [p for p in declared if os.path.basename(p).lower() in objective]
        picks = named or [p for p in declared
                          if os.path.isfile(p if os.path.isabs(p) else os.path.join(_repo_root(), p))]
        return picks[: self.MAX_FILES]

    def run_step(self, step: Dict[str, Any], task: Dict[str, Any]) -> StepResult:
        files = self._resolve_files(step, task)
        roots = self._roots(task)
        if not files:
            return StepResult(
                False, "inspect: nothing readable in scope",
                detail="name files in params.files or in the work order's scope.paths")
        found = [self._read(f, roots) for f in files]
        missing = [f["path"] for f in found if f.get("error")]
        return StepResult(
            ok=not missing,
            summary=f"inspected {len(found) - len(missing)}/{len(files)} file(s)",
            evidence={"files": [{k: v for k, v in f.items() if k != "text"} for f in found],
                      "missing": missing},
            detail="" if not missing else f"not readable: {', '.join(missing)}",
        )


class CodingWorkerAdapter(Adapter):
    """Routes a coding objective to the Qwen3.8-27B llama.cpp worker.

    The worker is **GPU-only and on demand**: this adapter acquires the shared
    cross-process GPU lock, starts the existing launcher if the worker is not
    already listening, waits for `/health`, sends one bounded completion, and —
    when *it* was the one that started the worker — stops it again so nothing
    stays resident on the GPU or in RAM after the task.
    """

    name = "coding"
    BASE = os.environ.get("TYS_CODING_URL", "http://127.0.0.1:8080")
    MODEL = os.environ.get("TYS_CODING_MODEL", "northstaros-qwen3.8:27b")
    LAUNCHER = os.environ.get("TYS_CODING_LAUNCHER", "scripts/start-northstar-llm.ps1")
    START_TIMEOUT_S = float(os.environ.get("TYS_CODING_START_TIMEOUT_S", "180"))

    def __init__(self, runner: Optional[Callable[..., Any]] = None):
        # `runner` is the injection point for tests: (prompt, files) -> text.
        self._runner = runner

    def available(self) -> Dict[str, Any]:
        up = _port_open("127.0.0.1", 8080)
        return {"adapter": self.name, "available": up, "detail":
                "worker listening on 127.0.0.1:8080" if up else "worker not started (on demand)"}

    # -- lifecycle ---------------------------------------------------------

    def _start(self) -> Tuple[bool, str]:
        launcher = self.LAUNCHER
        if not os.path.isabs(launcher):
            launcher = os.path.join(_repo_root(), launcher)
        if not os.path.exists(launcher):
            return False, f"launcher not found: {launcher}"
        flags = 0
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            subprocess.Popen(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", launcher],
                cwd=_repo_root(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
        except OSError as e:
            return False, f"launcher failed to start: {e}"
        deadline = time.time() + self.START_TIMEOUT_S
        while time.time() < deadline:
            if _port_open("127.0.0.1", 8080):
                try:
                    _http_json(f"{self.BASE}/health", timeout=3)
                    return True, "started"
                except Exception:
                    pass
            time.sleep(2)
        return False, f"worker did not answer /health within {self.START_TIMEOUT_S:.0f}s"

    def _stop(self) -> str:
        pid = _listening_pid(8080)
        if not pid:
            return "nothing_listening"
        try:
            import psutil  # type: ignore

            proc = psutil.Process(pid)
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except Exception:
                proc.kill()
            return f"stopped pid {pid}"
        except Exception as e:  # noqa: BLE001 - report, never raise from cleanup
            return f"stop_failed: {e}"

    # -- the step ----------------------------------------------------------

    def _prompt(self, step: Dict[str, Any], context_files: List[Dict[str, Any]]) -> str:
        parts = [
            "You are the Northstar OS coding worker. Answer the inspection request below.",
            "Be concrete and short. Cite file paths and line numbers when they are given to you.",
            "You have no tools. Use ONLY the file contents provided. If something is not shown, say so.",
            "",
            f"REQUEST: {step.get('objective', '')}",
            "",
        ]
        for f in context_files:
            if f.get("text") is None:
                continue
            shown = str(f["path"]).replace("\\", "/")
            parts.append(f"--- FILE {shown} ({f['bytes']} bytes"
                         f"{', truncated' if f.get('truncated') else ''}) ---")
            parts.append(f["text"])
            parts.append("--- END FILE ---")
        return "\n".join(parts)

    def run_step(self, step: Dict[str, Any], task: Dict[str, Any]) -> StepResult:
        params = step.get("params") or {}
        context = list(params.get("_context_files") or [])
        prompt = self._prompt(step, context)

        if self._runner is not None:
            try:
                text = self._runner(prompt, context)
            except Exception as e:  # noqa: BLE001 - surfaced as a step failure
                return StepResult(False, "coding worker call failed", detail=str(e), retriable=True)
            return StepResult(True, "coding worker answered", evidence={
                "worker": self.MODEL, "injected": True, "prompt_chars": len(prompt),
            }, detail=text[:4000])

        gpu = _gpu_lock()
        if gpu is not None and not gpu.acquire(timeout=5):
            return StepResult(False, "gpu busy — another heavy job owns the GPU",
                              detail="gpu_lock_timeout", blocked=True, retriable=True,
                              evidence={"lock": "render_session"})
        started_here = False
        try:
            if not _port_open("127.0.0.1", 8080):
                ok, why = self._start()
                if not ok:
                    return StepResult(False, "coding worker unavailable", detail=why,
                                      blocked=True, retriable=True,
                                      evidence={"launcher": self.LAUNCHER, "reason": why})
                started_here = True
            payload = {
                "model": self.MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": int(params.get("max_tokens") or 1200),
                "stream": False,
            }
            # The worker is a task executor here, not a reasoning puzzle. With
            # thinking on and a large file in the prompt, the reasoning block ate
            # the whole budget (finish_reason=length, empty content — measured
            # 2026-10-28 on the Tys Assistant module itself). Thinking is off by
            # default and the flag is reported in evidence, never assumed.
            disable_thinking = bool(params.get("disable_thinking", True))
            if disable_thinking:
                payload["chat_template_kwargs"] = {"enable_thinking": False}
            allow_thinking = not disable_thinking
            try:
                out = _http_json(f"{self.BASE}/v1/chat/completions", payload,
                                 timeout=float(params.get("timeout_s") or 600))
            except Exception as e:  # noqa: BLE001 - transport failure is a step failure
                return StepResult(False, "coding worker did not answer", detail=str(e),
                                  retriable=True,
                                  evidence={"url": self.BASE, "worker": self.MODEL,
                                            "disable_thinking": disable_thinking})

            endpoint = f"{self.BASE}/v1/chat/completions"
            choice = (out.get("choices") or [{}])[0] or {}
            message = choice.get("message") or {}
            text = str(message.get("content") or "").strip()
            finish_initial = choice.get("finish_reason")
            reasoning_chars = len(str(message.get("reasoning_content") or "").strip())
            finish_retry = None
            recovered = None

            # One bounded recovery. Only when the caller actually asked for
            # thinking (never when it was already disabled), only when the answer
            # is empty, and only when the budget was provably eaten: the worker
            # said finish_reason=length, or it emitted a non-empty reasoning
            # block instead of content.
            budget_eaten = finish_initial == "length" or reasoning_chars > 0
            if allow_thinking and not text and budget_eaten:
                retry = dict(payload)
                retry["chat_template_kwargs"] = {"enable_thinking": False}
                retry["max_tokens"] = min(4000, int(payload["max_tokens"]) * 2)
                try:
                    out2 = _http_json(endpoint, retry,
                                      timeout=float(params.get("timeout_s") or 600))
                except Exception:  # noqa: BLE001 - a failed retry is reported, not raised
                    out2 = None
                if out2:
                    choice2 = (out2.get("choices") or [{}])[0] or {}
                    text2 = str((choice2.get("message") or {}).get("content") or "").strip()
                    finish_retry = choice2.get("finish_reason")
                    if text2:
                        text = text2
                        out = out2
                        recovered = "reasoning_budget_retry"

            evidence = {
                "worker": self.MODEL,
                "endpoint": endpoint,
                "prompt_chars": len(prompt),
                "answer_chars": len(text),
                "disable_thinking": disable_thinking,
                "finish_reason_initial": finish_initial,
                "finish_reason_retry": finish_retry,
                "reasoning_chars": reasoning_chars,
                "recovered_from": recovered,
                "usage": (out or {}).get("usage"),
            }
            if not text:
                return StepResult(
                    False, "coding worker returned no content",
                    detail=json.dumps({"finish_reason_initial": finish_initial,
                                       "finish_reason_retry": finish_retry,
                                       "reasoning_chars": reasoning_chars})[:600],
                    retriable=True, evidence=evidence)
            return StepResult(True, "coding worker answered", detail=text[:4000],
                              evidence=evidence)
        finally:
            if started_here:
                # On demand means on demand: nothing stays resident after the task.
                report = self._stop()
                _unload_ollama_brain()
                setattr(self, "_last_stop", report)
            if gpu is not None:
                try:
                    gpu.release()
                except Exception:
                    pass


def _pid_alive(pid: int) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        import psutil  # type: ignore

        return psutil.pid_exists(pid)
    except Exception:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def chrome_controller_holder(profile_dir: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """The live Chrome Connect controller that owns `profile_dir`, or None.

    Chrome Connect allows exactly one controller session per Chrome profile, and
    it records that ownership as a lock file (`mcp_profile_<dir>.lock`, written by
    `lib/chromecontrol/mcp-session.js`). Reading it is the difference between
    "hand this work to the controller that owns the profile" and "spawn a second
    controller that will refuse and leave the task stuck".
    """
    import tempfile

    directory = profile_dir or os.environ.get("TYS_CHROME_PROFILE_DIR", "Profile 6")
    lock_dir = os.environ.get(
        "TYS_CHROME_LOCK_DIR", os.path.join(tempfile.gettempdir(), "chromeconnect-locks"))
    path = os.path.join(lock_dir, f"mcp_profile_{directory}.lock")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            held = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    pid = int(held.get("pid") or 0)
    if not _pid_alive(pid):
        return None  # stale lock: the owner is gone, so it is not a holder
    return {"pid": pid, "profile": directory,
            "owner": held.get("owner"), "acquired_at": held.get("acquired_at"),
            "lock_path": path}


class ChromeConnectAdapter(Adapter):
    """Routes a browser objective through the Chrome Connect controller.

    The controller — not this module — owns the Playwright client, the host
    allowlist, the Amazon blocklist, the per-host grants and the gate. This
    adapter only hands it a task string and reads the structured result back.

    **One controller per profile.** Chrome Connect allows exactly one live
    session per Chrome profile. When an interactive controller session already
    owns Profile 6, a second controller must not be spawned to fight it for the
    relay. In that case the step becomes an explicit *assignment*: the exact
    controller task is recorded, the task moves to `awaiting_controller`, and the
    owning controller posts its structured result back through
    `TysAssistant.complete_controller_step`. That is the architecture working as
    designed, not a workaround.
    """

    name = "browser"

    def __init__(self, caller: Optional[Callable[..., Dict[str, Any]]] = None,
                 mode: str = "auto"):
        self._caller = caller
        #: auto | direct | assigned
        self.mode = mode

    def _cc(self):
        if self._caller is not None:
            return self._caller
        guard_path = os.path.join(_repo_root(), "tools")
        if guard_path not in sys.path:
            sys.path.insert(0, guard_path)
        import chromeconnect_guard  # noqa: WPS433 - deliberate late import

        return chromeconnect_guard.cc_call

    def available(self) -> Dict[str, Any]:
        try:
            self._cc()
        except Exception as e:  # noqa: BLE001 - availability probe
            return {"adapter": self.name, "available": False, "detail": str(e)}
        return {"adapter": self.name, "available": True, "mode": self.mode,
                "detail": "controller CLI reachable; policy enforced by the controller"}

    def _assignment(self, step: Dict[str, Any], params: Dict[str, Any], reason: str,
                    holder: Optional[Dict[str, Any]] = None) -> StepResult:
        task_text = str(params.get("task") or step.get("objective") or "")
        return StepResult(
            ok=False,
            summary="Chrome Connect is owned by another controller session",
            detail=reason[:400],
            blocked=True,
            evidence={
                "code": "browser_controller_busy",
                "assignment": {
                    "controller": "chromeconnect",
                    "task": task_text,
                    "url": params.get("url"),
                    "max_steps": int(params.get("max_steps") or 8),
                    "profile": (holder or {}).get("profile")
                               or os.environ.get("TYS_CHROME_PROFILE_DIR", "Profile 6"),
                    "owner_pid": (holder or {}).get("pid"),
                    "post_result_to": "POST /api/admin/tys/tasks/{task_id}/controller-result",
                },
            },
        )

    def run_step(self, step: Dict[str, Any], task: Dict[str, Any]) -> StepResult:
        params = step.get("params") or {}
        url = params.get("url")
        # The controller takes ONE task string; the plan grammar lives in it.
        task_text = str(params.get("task") or step.get("objective") or "")
        if not task_text.strip():
            return StepResult(False, "browser step has no task text", detail="params.task required")

        if self.mode == "assigned":
            # The caller declared that an interactive controller owns the profile.
            return self._assignment(step, params, "mode=assigned")

        # Check ownership BEFORE spawning anything: a second controller would be
        # refused by the one-controller rule and the step would hang as an
        # unexplained error. The holder is recorded so the hand-off is auditable.
        holder = chrome_controller_holder(params.get("profile"))
        if holder and holder["pid"] != os.getpid():
            return self._assignment(
                step, params,
                f"Chrome profile '{holder['profile']}' is owned by pid {holder['pid']} "
                f"({holder.get('owner') or 'controller session'})",
                holder=holder)

        try:
            call = self._cc()
        except Exception as e:  # noqa: BLE001 - unavailable controller is a blocker
            return StepResult(False, "Chrome Connect controller unavailable", detail=str(e), blocked=True)

        try:
            result = call(
                task_text,
                url=url,
                dry_run=bool(params.get("dry_run", False)),
                require_isolated=bool(params.get("require_isolated", False)),
                timeout=float(params.get("timeout_s") or 420),
            )
        except Exception as e:  # noqa: BLE001 - controller failure is a step failure
            return StepResult(False, "Chrome Connect call failed", detail=str(e), retriable=True)

        status = str(result.get("status") or "UNKNOWN")
        blob = json.dumps(result, default=str)
        if "already owned by pid" in blob:
            # A live controller session holds the profile: hand the work to it.
            return self._assignment(step, params, "profile is owned by another controller session")
        ok = status == "COMPLETE"
        return StepResult(
            ok=ok,
            summary=f"Chrome Connect {status.lower()} ({result.get('stop_reason') or 'n/a'})",
            evidence={
                "controller": "chromeconnect",
                "delegation": "direct",
                "run_id": result.get("run_id"),
                "status": status,
                "stop_reason": result.get("stop_reason"),
                "steps": result.get("steps"),
                "refusals": result.get("refusals"),
                "blockers": result.get("blockers"),
                "mode": (result.get("stats") or {}).get("mode"),
                "url": (result.get("data") or {}).get("url") or url,
                "journal": (result.get("journal") or {}).get("name") if isinstance(result.get("journal"), dict) else result.get("journal"),
            },
            artifacts=[] if not result.get("journal") else [str(result.get("journal"))],
            detail=str(result.get("error") or result.get("stop_reason") or "")[:800],
            blocked=status in ("BLOCKED",),
            retriable=status in ("ERROR", "INCOMPLETE"),
        )


class CreativeWorkerAdapter(Adapter):
    """Routes a creative objective to the existing ComfyUI studio services.

    Heavy GPU work is serialized by the same cross-process lock the render lanes
    already use, so a Tys Assistant render can never overlap a studio render or
    the coding worker.
    """

    name = "creative"

    def __init__(self, generator: Optional[Callable[..., Dict[str, Any]]] = None):
        self._generator = generator

    def available(self) -> Dict[str, Any]:
        try:
            import studio_generation as sg  # noqa: WPS433

            armed = sg.media_live_armed()
            up = _port_open("127.0.0.1", 8188, timeout=1.0)
            return {"adapter": self.name, "available": bool(armed and up),
                    "detail": f"media_live={armed} comfyui={up}"}
        except Exception as e:  # noqa: BLE001 - availability probe
            return {"adapter": self.name, "available": False, "detail": str(e)}

    def run_step(self, step: Dict[str, Any], task: Dict[str, Any]) -> StepResult:
        params = step.get("params") or {}
        prompt = str(params.get("prompt") or step.get("objective") or "").strip()
        if not prompt:
            return StepResult(False, "creative step has no prompt", detail="params.prompt required")
        if self._generator is not None:
            try:
                out = self._generator(prompt=prompt, width=params.get("width"),
                                      height=params.get("height"))
            except Exception as e:  # noqa: BLE001
                return StepResult(False, "creative generation failed", detail=str(e), retriable=True)
            return StepResult(True, "creative render completed", evidence={"injected": True},
                              artifacts=[str(a) for a in (out.get("assets") or [])],
                              detail=str(out)[:600])
        try:
            import studio_generation as sg  # noqa: WPS433
        except Exception as e:  # noqa: BLE001
            return StepResult(False, "studio services unavailable", detail=str(e), blocked=True)
        try:
            out = sg.generate_image(prompt, width=params.get("width") or 1024,
                                    height=params.get("height") or 1024,
                                    tier=str(params.get("tier") or "draft"))
        except Exception as e:  # noqa: BLE001 - reported, never swallowed
            return StepResult(False, "creative render failed", detail=str(e), retriable=True)
        assets = []
        for key in ("assets", "files", "asset_ids"):
            if isinstance(out.get(key), list):
                assets.extend(str(a) for a in out[key])
        return StepResult(True, "creative render completed", evidence={"engine": "comfyui"},
                          artifacts=assets, detail=json.dumps(out, default=str)[:800])


def _gpu_lock():
    """The one cross-process GPU lock this box has (shared with the render lanes)."""
    try:
        import studio_generation as sg  # noqa: WPS433

        getter = getattr(sg, "gpu_lock", None)
        if callable(getter):
            return getter()
        return getattr(sg, "_RENDER_LOCK", None)
    except Exception:
        return None


def _unload_ollama_brain() -> None:
    """Ask Ollama to drop whatever it has resident (best effort).

    The coding worker wants ~13 GB of VRAM and this box also runs Bojo on CPU;
    freeing Ollama's RAM before a heavy GPU load is the same discipline
    `unload_brain()` applies to renders.
    """
    try:
        ps = _http_json("http://127.0.0.1:11434/api/ps", timeout=4)
        for m in ps.get("models") or []:
            name = m.get("name")
            if name:
                _http_json("http://127.0.0.1:11434/api/generate",
                           {"model": name, "keep_alive": 0}, timeout=20)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# The orchestrator: the small persistent CPU model decides the plan
# ---------------------------------------------------------------------------

class OllamaOrchestrator:
    """Bojo on CPU proposes the plan. Bounded output space, validated, fail-closed.

    Bojo is CPU-pinned by its own model definition, so orchestration never takes
    VRAM from the render or coding lanes. The reply is constrained to JSON and
    re-validated here: a lane outside the task's scope, an over-long plan, or
    anything unparseable is refused rather than "interpreted".
    """

    BASE = os.environ.get("TYS_ORCHESTRATOR_URL", "http://127.0.0.1:11434")
    MODEL = os.environ.get("TYS_ORCHESTRATOR_MODEL", "bojo:latest")
    MAX_PLAN_STEPS = 4

    def __init__(self, chat: Optional[Callable[[str], str]] = None):
        self._chat = chat
        self.last_raw: str = ""
        self.last_meta: Dict[str, Any] = {}
        self.last_attempts: List[Dict[str, Any]] = []

    def available(self) -> Dict[str, Any]:
        try:
            v = _http_json(f"{self.BASE}/api/version", timeout=4)
            return {"adapter": "orchestrator", "available": bool(v), "model": self.MODEL}
        except Exception as e:  # noqa: BLE001
            return {"adapter": "orchestrator", "available": False, "detail": str(e), "model": self.MODEL}

    def _ask(self, prompt: str) -> str:
        if self._chat is not None:
            content = self._chat(prompt)
            self.last_meta = {"mode": "injected", "think": None, "format": None}
            return content
        started = time.time()
        out = _http_json(
            f"{self.BASE}/api/chat",
            {
                "model": self.MODEL,
                "messages": [
                    {"role": "system", "content":
                        "You are Tys Assistant's planner. Reply with JSON only. "
                        "No prose, no markdown, no explanation."},
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
                "format": "json",
                # Measured 2026-10-28 with bojo:latest (a thinking model): with
                # thinking enabled the planner spent all 2154 tokens reasoning,
                # came back done_reason="length" with EMPTY content, and every
                # plan was unusable. With think=false the same request answered
                # the JSON in 1.5 s. Planning is a routing decision, not a
                # reasoning task — so thinking is off for the planner only, and
                # this module never claims thinking was used.
                "think": False,
                "options": {"temperature": 0, "num_predict": 500},
            },
            timeout=180,
        )
        msg = out.get("message") or {}
        content = str(msg.get("content") or "")
        thinking = str(msg.get("thinking") or "")
        self.last_meta = {
            "mode": "ollama",
            "model": self.MODEL,
            "think": False,
            "format": "json",
            "num_predict": 500,
            "done_reason": out.get("done_reason"),
            "eval_count": out.get("eval_count"),
            "prompt_eval_count": out.get("prompt_eval_count"),
            "latency_ms": int((time.time() - started) * 1000),
            "content_chars": len(content),
            "thinking_chars": len(thinking),
        }
        if not content.strip() and thinking.strip():
            raise RuntimeError("orchestrator_returned_thinking_only")
        return content

    def _corrective_prompt(self, base: str, rejected: str, lanes: List[str]) -> str:
        return (
            base
            + "\nYour previous reply was rejected. It was:\n"
            + (rejected or "(empty)")[:600]
            + "\nIt must be a JSON object with a 'steps' array. Every step needs "
              "BOTH a 'lane' from this exact list: " + ", ".join(lanes)
            + " AND a non-empty 'objective'. Output the JSON only."
        )

    def plan(self, task: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str]:
        """Return (steps, raw_reply). Empty steps means "could not plan".

        Two attempts: the plain prompt, then one corrective prompt that repeats
        the rejection and the exact contract. Both attempts are preserved so the
        blocked task carries the real reason rather than a generic failure.
        """
        lanes = [l for l in (task.get("scope") or {}).get("lanes") or list(LANES) if l in LANES]
        base = (
            "Plan at most %d steps for this admin task.\n"
            "OBJECTIVE: %s\n"
            "ALLOWED LANES: %s\n"
            "Reply with exactly this JSON shape:\n"
            '{"steps":[{"lane":"<one of the allowed lanes>","objective":"<one short sentence>"}]}\n'
            "Rules: only use the allowed lanes; 1 to %d steps; never mention Amazon, "
            "spending money or buying anything.\n"
            % (self.MAX_PLAN_STEPS, task.get("objective", ""), ", ".join(lanes), self.MAX_PLAN_STEPS)
        )
        attempts: List[Dict[str, Any]] = []
        last_reply = ""
        for attempt in range(2):
            prompt = base if attempt == 0 else self._corrective_prompt(base, last_reply, lanes)
            try:
                last_reply = self._ask(prompt)
            except Exception as e:  # noqa: BLE001 - orchestrator outage is reported
                attempts.append({"attempt": attempt + 1, "ok": False,
                                 "error": f"{type(e).__name__}: {e}",
                                 "meta": dict(self.last_meta or {})})
                self.last_attempts = attempts
                self.last_raw = f"orchestrator_error: {e}"
                return [], self.last_raw
            steps = self._parse(last_reply, lanes)
            attempts.append({
                "attempt": attempt + 1,
                "ok": bool(steps),
                "corrective": attempt > 0,
                "reply": (last_reply or "")[:800],
                "meta": dict(self.last_meta or {}),
            })
            if steps:
                self.last_attempts = attempts
                self.last_raw = last_reply
                return steps, last_reply
        self.last_attempts = attempts
        self.last_raw = (last_reply or "empty_reply")[:2000]
        return [], self.last_raw

    def _parse(self, raw: str, lanes: List[str]) -> List[Dict[str, Any]]:
        text = (raw or "").strip()
        if not text:
            return []
        # Tolerate a fenced block from a chatty model, nothing more.
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return []
        try:
            doc = json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
        steps_in = doc.get("steps")
        if not isinstance(steps_in, list):
            return []
        out: List[Dict[str, Any]] = []
        for s in steps_in[: self.MAX_PLAN_STEPS]:
            if not isinstance(s, dict):
                return []
            lane = str(s.get("lane") or "").strip().lower()
            objective = str(s.get("objective") or "").strip()
            if lane not in lanes or not objective:
                return []
            if _touches_owner_gate(objective):
                return []
            out.append({"lane": lane, "objective": objective, "params": {}})
        return out

    def next_action(self, task: Dict[str, Any], note: str) -> str:
        """One short recommendation recorded on the task. Best effort."""
        try:
            prompt = (
                "In one short sentence, say what the operator should do next.\n"
                f"TASK: {task.get('objective','')}\nSTATE: {note}\n"
                'Reply as JSON: {"next_action":"..."}'
            )
            doc = json.loads(re.search(r"\{[\s\S]*\}", self._ask(prompt)).group(0))
            value = str(doc.get("next_action") or "").strip()
            return value[:300] or note
        except Exception:
            return note


# ---------------------------------------------------------------------------
# Owner approval gates the agent may not self-approve
# ---------------------------------------------------------------------------

def _touches_owner_gate(text: str) -> Optional[str]:
    low = (text or "").lower()
    if re.search(AMAZON_SCOPE_PATTERN, low):
        return "amazon_requires_owner_approval"
    for pat in PAID_SCOPE_PATTERNS:
        if re.search(pat, low):
            return "paid_action_requires_owner_approval"
    return None


# ---------------------------------------------------------------------------
# The agent
# ---------------------------------------------------------------------------

class TysAssistant:
    """Admin automation agent: submit work orders, run them bounded, checkpoint."""

    def __init__(
        self,
        store: Optional[TysStore] = None,
        *,
        orchestrator: Optional[OllamaOrchestrator] = None,
        adapters: Optional[Dict[str, Adapter]] = None,
        evidence_dir: Optional[str] = None,
    ):
        self.store = store or TysStore()
        self.orchestrator = orchestrator or OllamaOrchestrator()
        self.adapters: Dict[str, Adapter] = adapters or {
            "inspect": InspectAdapter(),
            "coding": CodingWorkerAdapter(),
            "browser": ChromeConnectAdapter(),
            "creative": CreativeWorkerAdapter(),
        }
        self.evidence_dir = evidence_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "data", "tys", "evidence")
        os.makedirs(self.evidence_dir, exist_ok=True)
        # Any task a previous process left `running` is resumable, not running.
        self.recovered = self.store.mark_interrupted()

    # -- identity / state --------------------------------------------------

    def identity(self) -> Dict[str, Any]:
        return {
            "id": AGENT_ID,
            "name": AGENT_NAME,
            "kind": AGENT_KIND,
            "surface": AGENT_SURFACE,
            "user_facing": False,
            "chat_protocol_role": CHAT_PROTOCOL_ROLE_UNCHANGED,
            "routing": {
                "inspect": "this process (bounded file reads)",
                "coding": "Qwen3.8-27B IQ3_XXS llama.cpp worker (GPU-only, on demand)",
                "browser": "Chrome Connect controller (policy + gate enforced by the controller)",
                "creative": "existing studio/ComfyUI services",
                "orchestrator": f"local CPU model {self.orchestrator.MODEL}",
            },
            "gates": ["owner approval before spend", "owner approval before Amazon",
                      "Chrome Connect policy + profile lease"],
        }

    def state(self) -> Dict[str, Any]:
        tasks = self.store.list(limit=200)
        by_status: Dict[str, int] = {}
        for t in tasks:
            by_status[t["status"]] = by_status.get(t["status"], 0) + 1
        return {
            "identity": self.identity(),
            "queue": {
                "total": len(tasks),
                "by_status": by_status,
                "next": (tasks[0]["id"] if tasks else None),
            },
            "recovered_on_start": self.recovered,
            "lanes": {name: a.available() for name, a in self.adapters.items()},
            "orchestrator": self.orchestrator.available(),
        }

    # -- work orders -------------------------------------------------------

    def submit(self, work_order: Dict[str, Any], owner: str = "") -> Dict[str, Any]:
        """Validate and queue one explicit admin work order."""
        title = str(work_order.get("title") or "").strip()
        objective = str(work_order.get("objective") or "").strip()
        if not objective:
            raise TysError("objective_required", "a work order needs a concrete objective")

        gate = _touches_owner_gate(objective)
        if gate:
            raise TysError(gate, "this objective needs the owner's explicit approval first")

        scope_in = work_order.get("scope") or {}
        lanes = [l for l in (scope_in.get("lanes") or list(LANES)) if l in LANES]
        if not lanes:
            raise TysError("empty_scope", "scope.lanes must name at least one of " + ", ".join(LANES))
        scope = {
            "lanes": lanes,
            "paths": list(scope_in.get("paths") or []),
            "hosts": list(scope_in.get("hosts") or []),
        }

        limits = dict(DEFAULT_LIMITS)
        for k, v in (work_order.get("limits") or {}).items():
            if k in HARD_LIMITS and isinstance(v, (int, float)):
                limits[k] = min(int(v), HARD_LIMITS[k])

        steps_in = work_order.get("steps") or []
        steps: List[Dict[str, Any]] = []
        for s in steps_in:
            if not isinstance(s, dict):
                raise TysError("invalid_step", "each step must be an object")
            lane = str(s.get("lane") or "").strip().lower()
            if lane not in lanes:
                raise TysError("step_outside_scope", f"lane '{lane}' is not in scope {lanes}")
            objective_s = str(s.get("objective") or "").strip()
            if not objective_s:
                raise TysError("invalid_step", "each step needs an objective")
            gate = _touches_owner_gate(objective_s) or _touches_owner_gate(
                json.dumps(s.get("params") or {}))
            if gate:
                raise TysError(gate, f"step '{objective_s[:80]}' needs owner approval")
            steps.append({
                "lane": lane, "objective": objective_s,
                "params": dict(s.get("params") or {}),
                "optional": bool(s.get("optional", False)),
            })
        if len(steps) > limits["max_steps"]:
            raise TysError("plan_too_long", f"{len(steps)} steps exceeds max_steps={limits['max_steps']}")
        if not steps and str(work_order.get("planning") or "orchestrator") != "orchestrator":
            raise TysError("steps_required", "planning=explicit requires at least one step")

        task = {
            "id": "tys_" + uuid.uuid4().hex[:12],
            "title": title or objective[:80],
            "objective": objective,
            "status": "queued",
            "owner": owner or "",
            "scope": scope,
            "evidence_required": list(work_order.get("evidence_required") or
                                      ["per-step result", "controller run id for browser steps"]),
            "limits": limits,
            "steps": steps,
            "cursor": 0,
            "iteration": 0,
            "checkpoint": None,
            "next_action": "run" if steps else "plan",
            "result": None,
            "blockers": [],
            "stop_reason": None,
            "created_at": _now(),
            "updated_at": _now(),
            "started_at": None,
            "finished_at": None,
            "_planning": str(work_order.get("planning") or "orchestrator"),
        }
        task = self.store.save(task)
        self.store.event(task["id"], "task_created", {
            "title": task["title"], "objective": objective, "scope": scope,
            "limits": limits, "steps": len(steps), "planning": task["_planning"],
            "owner": task["owner"],
        })
        return task

    # -- execution ---------------------------------------------------------

    def run_kernel(self, task_id: str, *, approve_by: str = "operator") -> Dict[str, Any]:
        """Execute a work order through the agent kernel (opt-in).

        The default `run()` is unchanged. This path gives the order a visible
        plan, a policy check per lane, evidence per step and a checkpoint.
        """
        from agent_kernel.policy import grant
        from agent_kernel.tys_adapter import run_order

        task = self.store.get(task_id)
        if not task:
            raise TysError("not_found", f"no task {task_id}")
        if task.get("status") not in ("queued", "running", "interrupted"):
            raise TysError("not_runnable",
                           f"task {task_id} is {task.get('status')!r}")
        task["status"] = "running"
        self.store.save(task)
        order = {"id": task["id"], "title": task.get("title") or "",
                 "objective": task["objective"],
                 "scope": task.get("scope") or {},
                 "steps": task.get("steps") or [],
                 "limits": task.get("limits") or {}}
        grants = [grant("edit", minutes=240, why="approved work order"),
                  grant("browser_click", minutes=240, why="approved work order"),
                  grant("creative_generate", minutes=240, why="approved work order")]
        res = run_order(self, order, approve_by=approve_by, grants=grants, task=task)
        task["status"] = "done" if res.status == "complete" else res.status
        self.store.save(task)
        self.store.event(task_id, "kernel_result", res.to_dict())
        self._checkpoint(task)
        return res.to_dict()

    def run(self, task_id: str, max_steps: Optional[int] = None) -> Dict[str, Any]:
        """Execute at most `max_steps` steps, then checkpoint and return."""
        task = self.store.get(task_id)
        if not task:
            raise TysError("task_not_found", task_id)
        if task["status"] in ("done", "cancelled"):
            return task

        limits = task["limits"] or dict(DEFAULT_LIMITS)
        effective_max = min(int(max_steps or limits["max_steps"]), HARD_LIMITS["max_steps"])
        wall_deadline = time.time() + float(limits["max_wall_s"])

        # Planning happens exactly once, before the first step, and is recorded.
        if not task["steps"]:
            steps, raw = self.orchestrator.plan(task)
            self.store.event(task_id, "plan_requested", {
                "raw": raw[:2000],
                "attempts": getattr(self.orchestrator, "last_attempts", []),
            })
            if not steps:
                task.update(status="blocked", stop_reason="orchestrator_plan_invalid",
                            next_action="supply explicit steps or retry planning")
                task["blockers"].append({
                    "code": "orchestrator_plan_invalid",
                    "detail": (raw or "")[:600],
                    "at": _now(),
                })
                self.store.event(task_id, "blocked", task["blockers"][-1])
                return self.store.save(task)
            task["steps"] = steps
            self.store.event(task_id, "plan_accepted", {"steps": steps})
            task["next_action"] = "run"

        task["status"] = "running"
        task["started_at"] = task["started_at"] or _now()
        task = self.store.save(task)
        self.store.event(task_id, "run_started", {
            "cursor": task["cursor"], "max_steps": effective_max,
            "iteration": task["iteration"],
        })

        executed = 0
        while task["cursor"] < len(task["steps"]) and executed < effective_max:
            if time.time() >= wall_deadline:
                task.update(status="paused", stop_reason="wall_clock_limit",
                            next_action="resume")
                break
            step = task["steps"][task["cursor"]]
            result = self._execute_step(task, step)
            executed += 1
            task["iteration"] = int(task["iteration"]) + 1

            if result.ok:
                task["cursor"] += 1
            elif step.get("optional"):
                # Recorded, not hidden: an optional step that failed is evidence.
                task["cursor"] += 1
            else:
                assignment = (result.evidence or {}).get("assignment")
                if assignment:
                    # Not a failure: the browser lane is handed to whichever
                    # controller session owns the profile. The work item is
                    # recorded verbatim so it can be executed and posted back.
                    task.update(status="awaiting_controller",
                                stop_reason="controller_assignment",
                                next_action="controller_execute")
                    self.store.event(task_id, "controller_assignment", {
                        "step": task["cursor"], "lane": step["lane"],
                        "assignment": assignment,
                    })
                    self._checkpoint(task)
                    break
                task["blockers"].append({
                    "code": "step_failed",
                    "step": task["cursor"],
                    "lane": step["lane"],
                    "detail": result.detail[:400],
                    "at": _now(),
                })
                if result.blocked:
                    task.update(status="blocked", stop_reason="step_blocked",
                                next_action="operator_action_required")
                else:
                    task.update(status="paused", stop_reason="step_failed",
                                next_action="resume_or_fix")
                self._checkpoint(task)
                self.store.event(task_id, "blocked" if result.blocked else "step_failed", {
                    "lane": step["lane"], "objective": step["objective"][:200],
                    "detail": result.detail[:400],
                })
                break

            self._checkpoint(task)
            task = self.store.save(task)
            if not result.ok and not step.get("optional"):
                break

        if task["cursor"] >= len(task["steps"]):
            task.update(status="done", stop_reason="all_steps_completed",
                        next_action="", finished_at=_now())
            self.store.event(task_id, "completed", {
                "steps": len(task["steps"]), "iteration": task["iteration"],
            })
        elif task["status"] == "running":
            task.update(status="paused", stop_reason="step_limit",
                        next_action="resume")

        task = self.store.save(task)
        self.store.event(task_id, "run_finished", {
            "status": task["status"], "stop_reason": task["stop_reason"],
            "cursor": task["cursor"], "of": len(task["steps"]),
        })
        return task

    def _execute_step(self, task: Dict[str, Any], step: Dict[str, Any]) -> StepResult:
        lane = step["lane"]
        lane_scope = (task.get("scope") or {}).get("lanes") or list(LANES)
        if lane not in lane_scope:
            result = StepResult(False, "step outside the work order's scope",
                                detail=f"{lane} not in {lane_scope}", blocked=True)
            self.store.event(task["id"], "scope_violation",
                             {"lane": lane, "scope": lane_scope})
            return result

        adapter = self.adapters.get(lane)
        if adapter is None:
            return StepResult(False, "no adapter for lane", detail=lane, blocked=True)

        # A coding step gets its context gathered deterministically first: the
        # worker has no file access and must never be asked to guess contents.
        params = step.setdefault("params", {})
        if lane == "coding" and params.get("files") and "_context_files" not in params:
            params["_context_files"] = self._context_with_text(task, params["files"])

        self.store.event(task["id"], "step_started", {
            "index": task["cursor"], "lane": lane, "objective": step["objective"][:200],
        })
        started = time.time()
        try:
            result = adapter.run_step(step, task)
        except Exception as e:  # noqa: BLE001 - an adapter crash is a step failure
            result = StepResult(False, "adapter raised", detail=f"{type(e).__name__}: {e}",
                                retriable=True)
        elapsed_ms = int((time.time() - started) * 1000)

        record = {
            "index": task["cursor"], "lane": lane, "objective": step["objective"][:200],
            "ok": result.ok, "summary": result.summary, "detail": result.detail[:1500],
            "artifacts": result.artifacts, "blocked": result.blocked,
            "duration_ms": elapsed_ms, "ts": _now(),
            "evidence": result.evidence,
        }
        if (result.evidence or {}).get("assignment"):
            # A hand-off is not a result. The single `step_result` for this step
            # is written when the owning controller posts its outcome back, so
            # the evidence file never carries a phantom "failed" attempt.
            return result
        self.store.event(task["id"], "step_result", record)
        self._write_evidence(task["id"], record)
        return result

    def _context_with_text(self, task: Dict[str, Any], files: Iterable[str]) -> List[Dict[str, Any]]:
        """Read the named files for a coding prompt.

        Deliberately done with a fresh `InspectAdapter` rather than whatever is
        plugged into the `inspect` lane: context gathering is a capability of the
        agent, so swapping the inspect adapter (or running with a recorder in
        tests) must not change what the coding worker is shown.
        """
        gatherer = tys_inspect_adapter()
        out = []
        for rel in list(files)[: gatherer.MAX_FILES]:
            got = gatherer._read(rel, gatherer._roots(task))  # noqa: SLF001 - same module
            if got.get("text") is not None:
                out.append(got)
        return out

    def _checkpoint(self, task: Dict[str, Any]) -> None:
        checkpoint = {
            "cursor": task["cursor"],
            "of": len(task["steps"]),
            "iteration": task["iteration"],
            "completed_lanes": [s["lane"] for s in task["steps"][: task["cursor"]]],
            "next_step": (task["steps"][task["cursor"]] if task["cursor"] < len(task["steps"]) else None),
            "at": _now(),
        }
        task["checkpoint"] = checkpoint
        self.store.event(task["id"], "checkpoint", checkpoint)

    def _write_evidence(self, task_id: str, record: Dict[str, Any]) -> None:
        path = os.path.join(self.evidence_dir, f"{task_id}.jsonl")
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
        except OSError:
            # Evidence that cannot be written is recorded as an event instead of
            # being silently dropped.
            self.store.event(task_id, "evidence_write_failed", {"path": path})

    # -- queue helpers -----------------------------------------------------

    def drain(self, max_tasks: int = 1) -> List[Dict[str, Any]]:
        """Advance the queue by at most `max_tasks` bounded runs."""
        done: List[Dict[str, Any]] = []
        for _ in range(max(0, int(max_tasks))):
            task = self.store.next_queued()
            if not task:
                break
            done.append(self.run(task["id"]))
        return done

    def complete_controller_step(self, task_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Accept a Chrome Connect result posted back by the owning controller.

        The browser lane hands its work item to whichever controller session owns
        the Chrome profile. That session executes it through Chrome Connect and
        returns the controller's own structured result; this records it as the
        step's evidence, advances the checkpoint and continues the task.
        """
        task = self.store.get(task_id)
        if not task:
            raise TysError("task_not_found", task_id)
        if task["status"] != "awaiting_controller":
            raise TysError("task_not_awaiting_controller",
                           f"status is '{task['status']}'")
        cursor = int(task["cursor"])
        if cursor >= len(task["steps"]):
            raise TysError("no_pending_step", f"cursor {cursor} is past the last step")

        status = str(result.get("status") or "UNKNOWN").upper()
        ok = status == "COMPLETE"
        step = task["steps"][cursor]
        journal = result.get("journal")
        if isinstance(journal, dict):
            journal = journal.get("path") or journal.get("name")
        record = {
            "index": cursor,
            "lane": step["lane"],
            "objective": step["objective"][:200],
            "ok": ok,
            "summary": f"Chrome Connect {status.lower()} ({result.get('stop_reason') or 'n/a'})",
            "detail": str(result.get("error") or result.get("stop_reason") or "")[:1500],
            "artifacts": [str(journal)] if journal else [],
            "blocked": status == "BLOCKED",
            "duration_ms": None,
            "ts": _now(),
            "evidence": {
                "controller": "chromeconnect",
                "delegation": "assigned",
                "run_id": result.get("run_id"),
                "status": status,
                "stop_reason": result.get("stop_reason"),
                "steps": result.get("steps"),
                "refusals": result.get("refusals"),
                "blockers": result.get("blockers"),
                "mode": (result.get("stats") or {}).get("mode"),
                "url": (result.get("data") or {}).get("url")
                       or (step.get("params") or {}).get("url"),
                "journal": journal,
                "page_text_excerpt": str((result.get("data") or {}).get("text") or "")[:600] or None,
            },
        }
        self.store.event(task_id, "step_result", record)
        self._write_evidence(task_id, record)

        if ok:
            task["cursor"] = cursor + 1
        else:
            task["blockers"].append({
                "code": "controller_step_failed", "step": cursor, "lane": step["lane"],
                "detail": record["detail"][:400], "at": _now(),
            })
            task.update(status="blocked" if record["blocked"] else "paused",
                        stop_reason="controller_step_failed",
                        next_action="operator_action_required" if record["blocked"] else "resume_or_fix")
            self._checkpoint(task)
            return self.store.save(task)

        self._checkpoint(task)
        task = self.store.save(task)
        self.store.event(task_id, "controller_result_accepted", {
            "run_id": result.get("run_id"), "status": status, "cursor": task["cursor"],
        })
        return self.run(task_id)

    def resume(self, task_id: str, max_steps: Optional[int] = None) -> Dict[str, Any]:
        task = self.store.get(task_id)
        if not task:
            raise TysError("task_not_found", task_id)
        self.store.event(task_id, "resumed", {
            "cursor": task["cursor"], "checkpoint": task.get("checkpoint"),
        })
        return self.run(task_id, max_steps=max_steps)

    def cancel(self, task_id: str) -> Dict[str, Any]:
        task = self.store.get(task_id)
        if not task:
            raise TysError("task_not_found", task_id)
        task.update(status="cancelled", stop_reason="cancelled_by_operator",
                    next_action="", finished_at=_now())
        self.store.event(task_id, "cancelled", {})
        return self.store.save(task)

    def task_with_events(self, task_id: str) -> Dict[str, Any]:
        task = self.store.get(task_id)
        if not task:
            raise TysError("task_not_found", task_id)
        return {"task": task, "events": self.store.events(task_id),
                "evidence_file": os.path.join(self.evidence_dir, f"{task_id}.jsonl")}


# ---------------------------------------------------------------------------
# Process-wide default (the API and the CLI share one agent per process)
# ---------------------------------------------------------------------------

_DEFAULT: Optional[TysAssistant] = None
_DEFAULT_LOCK = threading.Lock()


def default_assistant() -> TysAssistant:
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is None:
            _DEFAULT = TysAssistant()
        return _DEFAULT


def reset_default() -> None:
    """Testing hook: drop the shared instance so the next call rebuilds it."""
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is not None:
            try:
                _DEFAULT.store.close()
            except Exception:
                pass
        _DEFAULT = None


# ---------------------------------------------------------------------------
# CLI — the operator's own handle on the agent
# ---------------------------------------------------------------------------

def _cli(argv: List[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="tys_assistant", description="Tys Assistant (admin automation agent)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("state", help="identity, queue and lane availability")
    p_submit = sub.add_parser("submit", help="file a work order from a JSON file")
    p_submit.add_argument("path")
    p_submit.add_argument("--owner", default="")
    p_run = sub.add_parser("run", help="run a task (bounded)")
    p_run.add_argument("task_id")
    p_run.add_argument("--max-steps", type=int, default=None)
    p_resume = sub.add_parser("resume", help="resume a task from its checkpoint")
    p_resume.add_argument("task_id")
    p_list = sub.add_parser("list", help="list tasks")
    p_list.add_argument("--status", default=None)
    p_show = sub.add_parser("show", help="task + events + evidence path")
    p_show.add_argument("task_id")
    p_drain = sub.add_parser("drain", help="advance the queue")
    p_drain.add_argument("--max-tasks", type=int, default=1)

    args = ap.parse_args(argv)
    agent = default_assistant()

    if args.cmd == "state":
        print(json.dumps(agent.state(), indent=2, default=str))
        return 0
    if args.cmd == "submit":
        with open(args.path, "r", encoding="utf-8") as fh:
            order = json.load(fh)
        task = agent.submit(order, owner=args.owner)
        print(json.dumps(task, indent=2, default=str))
        return 0
    if args.cmd in ("run", "resume"):
        if args.cmd == "resume":
            task = agent.resume(args.task_id, max_steps=args.max_steps)
        else:
            task = agent.run(args.task_id, max_steps=args.max_steps)
        print(json.dumps(task, indent=2, default=str))
        return 0
    if args.cmd == "list":
        print(json.dumps(agent.store.list(status=args.status), indent=2, default=str))
        return 0
    if args.cmd == "show":
        print(json.dumps(agent.task_with_events(args.task_id), indent=2, default=str))
        return 0
    if args.cmd == "drain":
        print(json.dumps(agent.drain(max_tasks=args.max_tasks), indent=2, default=str))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
