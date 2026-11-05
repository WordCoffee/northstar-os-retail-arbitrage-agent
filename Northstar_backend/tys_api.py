"""Tys Assistant — admin-only API.

Every route lives under ``/api/admin/tys``. That namespace is deliberate:

* it is **not** ``/api/chat``, so the customer/product chat lane is untouched;
* it is **not** mounted in the customer shell, so a subscriber never sees it;
* the only thing it exposes is the operator's own automation queue.

Authorization is fail-closed. A production process admits platform admins only;
a development process also admits operator-and-above, because the operator runs
the product locally through the dev identity shim. Anyone else gets 403 with a
stable code, including the agent's own identity document.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

try:  # pragma: no cover - import shape depends on how the app is booted
    from auth_deps import require_session as _require_session
except Exception:  # pragma: no cover
    async def _require_session():  # type: ignore[misc]
        return None

try:
    from foundation.authn import environment as _environment
except Exception:  # pragma: no cover
    def _environment() -> str:  # type: ignore[misc]
        return os.environ.get("ENVIRONMENT", "").strip().lower()

import tys_assistant as tys

router = APIRouter(prefix="/api/admin/tys", tags=["tys-assistant"])

ADMIN_ROLES = tys.ADMIN_ROLES
PLATFORM_ROLES = tys.PLATFORM_ROLES


def _role_of(user: Optional[Dict[str, Any]]) -> str:
    return str((user or {}).get("role") or "").strip().lower()


async def require_tys_admin(user: Optional[Dict[str, Any]] = Depends(_require_session)) -> Dict[str, Any]:
    """Admit the operator (dev) or a platform admin (any environment). Never a customer."""
    if not user:
        raise HTTPException(status_code=401, detail={"code": "tys_auth_required"})
    role = _role_of(user)
    if role in PLATFORM_ROLES:
        return user
    if _environment() == "production":
        # On a hosted multi-tenant box this agent drives the operator's own
        # machine services; a tenant role must never reach it.
        raise HTTPException(status_code=403, detail={"code": "tys_platform_admin_only"})
    if role in ADMIN_ROLES:
        return user
    raise HTTPException(status_code=403, detail={"code": "tys_admin_only"})


def _assistant() -> tys.TysAssistant:
    return tys.default_assistant()


def _http_error(exc: tys.TysError) -> HTTPException:
    status = 404 if exc.code == "task_not_found" else 400
    if exc.code in ("amazon_requires_owner_approval", "paid_action_requires_owner_approval"):
        status = 403
    return HTTPException(status_code=status, detail={"code": exc.code, "detail": exc.detail})


# ---------------------------------------------------------------------------
# Identity + state
# ---------------------------------------------------------------------------

@router.get("/state")
async def get_state(fresh: bool = Query(default=False),
                    _user: Dict[str, Any] = Depends(require_tys_admin)) -> Dict[str, Any]:
    """Agent identity, queue summary, lane availability and model placement.

    ``fresh=1`` re-probes every lane. The default is a 3-second snapshot so a
    burst of mobile clients cannot each spawn a Chrome Connect probe.
    """
    return _assistant().cached_state(fresh=fresh)


@router.get("/identity")
async def get_identity(_user: Dict[str, Any] = Depends(require_tys_admin)) -> Dict[str, Any]:
    return _assistant().identity()


@router.get("/ui")
async def get_ui(
    profile: str = Query(default="operator"),
    density: Optional[str] = Query(default=None),
    _user: Dict[str, Any] = Depends(require_tys_admin),
) -> Dict[str, Any]:
    """Adaptive UI component spec for this profile.

    The client renders the tree; the server decides what belongs in it from the
    queue, the lanes and the profile's habits. Always returns a complete tree —
    a degraded one carries an explicit alert instead of dropping regions.
    """
    from tys_ops import ui as _ui

    habits = {"density": density} if density else None
    return _ui.render(profile, _assistant().cached_state(), habits)


@router.get("/storage")
async def get_storage(_user: Dict[str, Any] = Depends(require_tys_admin)) -> Dict[str, Any]:
    """Media ledger summary: tiers, bytes, alerts, pending download prompts."""
    from tys_ops import storage as _storage

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "data", "tys", "storage_ledger.json")
    ledger = _storage.StorageLedger(path)
    return {"summary": ledger.summary(),
            "disk": _storage.guard_disk(os.path.dirname(path))}


# ---------------------------------------------------------------------------
# Work orders
# ---------------------------------------------------------------------------

@router.post("/work-orders")
async def submit_work_order(
    body: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(require_tys_admin),
) -> Dict[str, Any]:
    """File one explicit admin work order.

    Body: ``{title, objective, scope:{lanes,paths,hosts}, evidence_required[],
    limits:{max_steps,max_iterations,max_wall_s}, steps[]?, planning?}``.
    """
    agent = _assistant()
    try:
        task = agent.submit(body, owner=str(user.get("id") or user.get("user_id") or ""))
    except tys.TysError as exc:
        raise _http_error(exc) from exc
    return {"status": "queued", "task": task}


@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    _user: Dict[str, Any] = Depends(require_tys_admin),
) -> Dict[str, Any]:
    return {"tasks": _assistant().store.list(status=status, limit=limit)}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str, _user: Dict[str, Any] = Depends(require_tys_admin)) -> Dict[str, Any]:
    try:
        return _assistant().task_with_events(task_id)
    except tys.TysError as exc:
        raise _http_error(exc) from exc


@router.post("/tasks/{task_id}/run")
async def run_task(
    task_id: str,
    max_steps: Optional[int] = Query(default=None, ge=1, le=40),
    _user: Dict[str, Any] = Depends(require_tys_admin),
) -> Dict[str, Any]:
    """One bounded run. Returns the task with its checkpoint and evidence trail.

    This is the only task-execution contract: authenticated admin POST, executed
    inside the request, `200 OK` with the completed work order. There is no
    engine query parameter and no 202/SSE path — the assistant decides the lane
    from the work order itself. When the order ran through the agent kernel, the
    kernel's evidence payload rides back on the same response as `kernel`.
    """
    assistant = _assistant()
    try:
        task = assistant.run(task_id, max_steps=max_steps)
    except tys.TysError as exc:
        raise _http_error(exc) from exc
    return {"task": task, "kernel": _kernel_evidence(assistant, task_id)}


def _kernel_evidence(assistant: Any, task_id: str) -> Optional[Dict[str, Any]]:
    """The most recent kernel result recorded for this task, if any."""
    try:
        events = assistant.store.events(task_id)
    except Exception:  # noqa: BLE001 - evidence is additive, never a failed run
        return None
    for ev in reversed(events):
        if ev.get("kind") == "kernel_result":
            return ev.get("payload") or {}
    return None


@router.post("/tasks/{task_id}/resume")
async def resume_task(
    task_id: str,
    max_steps: Optional[int] = Query(default=None, ge=1, le=40),
    _user: Dict[str, Any] = Depends(require_tys_admin),
) -> Dict[str, Any]:
    """Continue from the stored checkpoint after an interruption."""
    try:
        return {"task": _assistant().resume(task_id, max_steps=max_steps)}
    except tys.TysError as exc:
        raise _http_error(exc) from exc


@router.post("/tasks/{task_id}/controller-result")
async def submit_controller_result(
    task_id: str,
    body: Dict[str, Any] = Body(...),
    _user: Dict[str, Any] = Depends(require_tys_admin),
) -> Dict[str, Any]:
    """Accept a Chrome Connect result for an `awaiting_controller` step.

    Chrome Connect allows one live session per Chrome profile, so the browser
    lane is executed by the controller session that owns the profile and its
    structured result is posted back here. The agent records it as evidence,
    advances the checkpoint and continues.
    """
    try:
        return {"task": _assistant().complete_controller_step(task_id, body)}
    except tys.TysError as exc:
        raise _http_error(exc) from exc


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, _user: Dict[str, Any] = Depends(require_tys_admin)) -> Dict[str, Any]:
    try:
        return {"task": _assistant().cancel(task_id)}
    except tys.TysError as exc:
        raise _http_error(exc) from exc


@router.post("/drain")
async def drain_queue(
    max_tasks: int = Query(default=1, ge=1, le=5),
    _user: Dict[str, Any] = Depends(require_tys_admin),
) -> Dict[str, Any]:
    """Advance the queue by at most `max_tasks` bounded runs (never a daemon)."""
    return {"ran": _assistant().drain(max_tasks=max_tasks)}


# ---------------------------------------------------------------------------
# Long-term memory (semantic when the local embedder answers)
# ---------------------------------------------------------------------------

_MEMORY: Optional[Any] = None


def _memory_index():
    """One process-wide memory index: 1024-d local embeddings + sqlite-vec.

    Falls back to the hashed index if the embedder or the extension is
    unavailable, and says so in `/memory/stats`.
    """
    global _MEMORY
    if _MEMORY is None:
        from pathlib import Path

        from tys_ops import memory as tys_memory

        path = Path(__file__).resolve().parent / "data" / "tys_memory.db"
        _MEMORY = tys_memory.MemoryIndex(str(path), semantic=True)
    return _MEMORY


@router.get("/memory/stats")
async def memory_stats(account: str = Query(default="operator"),
                       _user: Dict[str, Any] = Depends(require_tys_admin)) -> Dict[str, Any]:
    return _memory_index().stats(account)


@router.post("/memory/text")
async def memory_text(body: Dict[str, Any] = Body(...),
                      _user: Dict[str, Any] = Depends(require_tys_admin)) -> Dict[str, Any]:
    account = str(body.get("account") or "operator")
    text = str(body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail={"code": "memory_text_required"})
    return _memory_index().remember_text(account, text,
                                         source=str(body.get("source") or ""))


@router.get("/memory/search")
async def memory_search(q: str = Query(..., min_length=1),
                        account: str = Query(default="operator"),
                        k: int = Query(default=5, ge=1, le=20),
                        _user: Dict[str, Any] = Depends(require_tys_admin)) -> Dict[str, Any]:
    index = _memory_index()
    return {"query": q, "account": account, "semantic": index.semantic,
            "hits": index.search(account, q, k=k)}


@router.post("/memory/facts")
async def memory_assert_fact(body: Dict[str, Any] = Body(...),
                             _user: Dict[str, Any] = Depends(require_tys_admin)) -> Dict[str, Any]:
    required = ("subject", "predicate", "value")
    if not all(str(body.get(key) or "").strip() for key in required):
        raise HTTPException(status_code=422, detail={"code": "memory_fact_fields_required"})
    return _memory_index().assert_fact(
        str(body.get("account") or "operator"), str(body["subject"]),
        str(body["predicate"]), str(body["value"]),
        confidence=float(body.get("confidence") or 0.7),
        source=str(body.get("source") or ""))


@router.get("/memory/facts")
async def memory_facts(account: str = Query(default="operator"),
                       include_superseded: bool = Query(default=False),
                       _user: Dict[str, Any] = Depends(require_tys_admin)) -> Dict[str, Any]:
    return {"account": account,
            "facts": _memory_index().facts(account, include_superseded=include_superseded)}
