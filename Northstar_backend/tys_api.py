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
async def get_state(_user: Dict[str, Any] = Depends(require_tys_admin)) -> Dict[str, Any]:
    """Agent identity, queue summary, lane availability and model placement."""
    return _assistant().state()


@router.get("/identity")
async def get_identity(_user: Dict[str, Any] = Depends(require_tys_admin)) -> Dict[str, Any]:
    return _assistant().identity()


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
    """One bounded run. Returns the task with its checkpoint and evidence trail."""
    try:
        return {"task": _assistant().run(task_id, max_steps=max_steps)}
    except tys.TysError as exc:
        raise _http_error(exc) from exc


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
