"""Northstar AutothinK server — FastAPI app.

Routes:
  GET  /                                serves autothink/ui/index.html
  GET  /health                          liveness probe
  GET  /api/autothink/models            installed Ollama models + provider availability
  POST /api/autothink/run               route + generate a response for a command
  GET  /api/autothink/history           session command history (per tenant)
  POST /api/autothink/cancel            cancel a running run
  GET  /api/autothink/usage             per-tenant usage / metering summary
  GET  /api/autothink/jobs/{run_id}     run state (for polling + resumability)

Local Ollama is the default provider. The cloud provider is fully coded but
gate-kept behind OPENROUTER_API_KEY presence AND CLOUD_MODEL_LIVE=1 — no live
paid calls are executed without explicit operator approval (Hard Stop Zone,
AGENTS.md §3).

Auth and tenancy (P0-04, closed 2026-10-09): these routes are called from the
suite shell, so the session identity is injected by the caller as an explicit
argument rather than resolved here. `main.py` wires the strict
``require_session`` dependency and passes org/user ids down; a run without an
org id is refused. History, usage, and cancellation are tenant-scoped, so one
tenant can never see or stop another tenant's work.
"""

import os
import sys

# Make sibling packages importable when served from the repo root.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.dirname(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# The dual-engine Brain router lives in the Northstar backend.
_BACKEND_DIR = os.path.join(os.path.dirname(_ROOT), "Northstar_backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
try:
    import model_router as _model_router
except ImportError:  # pragma: no cover - defensive
    _model_router = None

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, List, Optional

from backend.llm_adapter import (
    DEFAULT_CLOUD_MODEL,
    DEFAULT_LOCAL_MODEL,
    UnifiedLLMAdapter,
    build_system_prompt_with_context,
)
from backend.run_registry import RunRegistry
from orchestration.router import route_task, build_context, audit
from memory.session_store import SessionStore, store_path_for_org
from memory.usage_ledger import UsageLedger

UI_PATH = os.path.join(_ROOT, "ui", "index.html")
AUDIT_LOG = os.path.join(_ROOT, "audit", "autothink-runs.jsonl")
IDEMPOTENCY_PATH = os.path.join(_ROOT, "audit", "idempotency.json")
MEMORY_DIR = os.path.join(_ROOT, "memory")

# Local data the brain can reference when answering. Read-only, cache-first:
# these files are only ever opened for reading, and only when they exist.
_DATA_ROOT = os.path.join(os.path.dirname(_ROOT), "Northstar_backend", "data")
_DATA_SOURCES = [
    p
    for p in [
        os.path.join(_DATA_ROOT, "scanner-search-cache.json"),
        os.path.join(_DATA_ROOT, "scanner-search-cache.enriched-candidate.json"),
        os.path.join(_DATA_ROOT, "kirkland-discovery.json"),
        os.path.join(_DATA_ROOT, "costco-discovery-catalog.json"),
    ]
    if os.path.exists(p)
]

app = FastAPI(title="Northstar OS AutothinK", version="2.1.0")
adapter = UnifiedLLMAdapter()
store = SessionStore()
runs = RunRegistry()
usage = UsageLedger()

# One history store per tenant, created on demand from the SAME directory the
# default store uses, so a run and the history read that follows it always
# agree on where the entry lives.
_STORES: Dict[str, SessionStore] = {}


def _store_for(org_id: str) -> SessionStore:
    existing = _STORES.get(org_id)
    if existing is None:
        existing = SessionStore(path=store_path_for_org(org_id, base_dir=MEMORY_DIR))
        _STORES[org_id] = existing
    return existing


class RunRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    provider: str = Field("local", pattern="^(local|cloud)$")
    model: Optional[str] = None
    tier: Optional[str] = Field(None, pattern="^(T1|T2|T3|V1|V2|V3)$")
    prev_tier: Optional[str] = Field(None, pattern="^(T1|T2|T3|V1|V2|V3)$")
    idempotency_key: Optional[str] = Field(None, max_length=120)


class CancelRequest(BaseModel):
    run_id: str = Field(..., min_length=1, max_length=120)


# ---------------------------------------------------------------------------
# Idempotency (append-only, tenant-scoped)
# ---------------------------------------------------------------------------

def _load_idempotency() -> Dict[str, Dict]:
    import json
    if not os.path.exists(IDEMPOTENCY_PATH):
        return {}
    try:
        with open(IDEMPOTENCY_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_idempotency(payload: Dict[str, Dict]) -> None:
    import json
    parent = os.path.dirname(IDEMPOTENCY_PATH)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    tmp = IDEMPOTENCY_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, IDEMPOTENCY_PATH)


def _idempotency_slot(org_id: str, key: str) -> str:
    return "%s\x1f%s" % (org_id, key)


def _require_tenant(org_id: Optional[str]) -> str:
    """Fail closed: an unidentified caller may never run a model or read history."""
    if not org_id or not str(org_id).strip():
        raise HTTPException(
            status_code=401,
            detail="An authenticated session with a resolved organization is required.",
        )
    return str(org_id).strip()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(UI_PATH)


@app.get("/health")
def health():
    return {"status": "ok", "service": "autothink"}


@app.get("/api/autothink/models")
def models():
    installed = adapter.list_local_models()
    local_ok = adapter.local_available()
    catalog = _model_router.catalog(installed) if _model_router else None
    cloud_provider = getattr(adapter, "cloud_provider", lambda: None)()
    cloud_armed = bool(getattr(adapter, "cloud_live_armed", lambda: False)())
    return {
        "local_available": local_ok,
        "cloud_available": adapter.cloud_available(),
        "cloud_provider": cloud_provider,
        "cloud_live_armed": cloud_armed,
        "default_local_model": DEFAULT_LOCAL_MODEL,
        "default_cloud_model": DEFAULT_CLOUD_MODEL,
        "models": installed,
        "catalog": catalog,
    }


@app.post("/api/autothink/run")
def run(req: RunRequest, org_id: Optional[str] = None, user_id: Optional[str] = None):
    org_id = _require_tenant(org_id)
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query is empty")

    # ---- idempotency: a repeated key returns the ORIGINAL result, and no
    # second model run (and therefore no second usage event) is created.
    slot = None
    if req.idempotency_key:
        slot = _idempotency_slot(org_id, req.idempotency_key)
        existing = _load_idempotency().get(slot)
        if existing:
            replay = dict(existing)
            replay["idempotent_replay"] = True
            replay["run_id"] = existing.get("run_id")
            return replay

    route = route_task(query)
    context = build_context(query, route, data_sources=_DATA_SOURCES)
    # Grounding: the context bundle actually reaches the model instead of
    # being assembled and dropped (was the P1-15 gap).
    grounded_prompt = build_system_prompt_with_context(context)

    # Dual-engine Brain: resolve (provider, tier) -> concrete model + weight.
    tier = req.tier or "T2"
    resolution = None
    effective_model = req.model
    credit_weight = None
    if _model_router is not None:
        resolution = _model_router.resolve(req.provider, tier, req.model)
        effective_model = resolution.model
        credit_weight = resolution.credit_weight

    consent = None
    if _model_router is not None and req.prev_tier:
        consent = _model_router.consent_prompt(req.prev_tier, tier)

    record = runs.create(org_id=org_id, user_id=user_id)
    run_id = record["run_id"]

    result = adapter.generate(
        query,
        provider=req.provider,
        model=effective_model,
        system_prompt=grounded_prompt,
        should_cancel=runs.cancel_probe(run_id),
    )
    cancelled = result.get("reason") == "cancelled_by_user"
    runs.transition(run_id, "cancelled" if cancelled else ("completed" if result.get("ok") else "failed"))

    # ---- metering: one event per real run. Only provider-reported costs.
    provider_label = result.get("provider", req.provider)
    cost_usd = result.get("cost_usd")
    if cost_usd is None and provider_label == "local":
        cost_usd = 0.0
        cost_basis = "local lane: no provider charge"
    elif cost_usd is None:
        cost_usd = None
        cost_basis = "provider did not report a cost"
    else:
        cost_basis = "provider-reported cost"
    usage.record(
        org_id=org_id,
        user_id=user_id,
        provider=provider_label,
        model=result.get("model"),
        tier=tier,
        task_class=route["task_class"],
        prompt_tokens=result.get("prompt_tokens"),
        completion_tokens=result.get("completion_tokens"),
        ok=result.get("ok", False) and not cancelled,
        cost_usd=cost_usd,
        cost_basis=cost_basis,
        run_id=run_id,
        idempotency_key=req.idempotency_key,
    )

    entry = {
        "track": route["task_class"],
        "provider": req.provider or "local",
        "tier": tier,
        "model": result.get("model"),
        "ok": result.get("ok", False) and not cancelled,
        "task_class": route["task_class"],
        "label": route["label"],
        "files_touched": [],
        "live_action_requested": False,
        "approval_status": "not_requested",
        "reason": result.get("reason"),
        "org_id": org_id,
        "user_id": user_id or "unknown",
        "run_id": run_id,
    }
    entry["org_id"] = org_id
    _store_for(org_id).add({"query": query, **entry})
    audit(dict(entry), log_path=AUDIT_LOG)

    payload = {
        "query": query,
        "provider": provider_label,
        "model": result.get("model"),
        "tier": tier,
        "credit_weight": credit_weight,
        "resolved": ({"provider": resolution.provider, "tier": resolution.tier,
                      "available": resolution.available, "reason": resolution.reason,
                      "pin": resolution.pin} if resolution else None),
        "consent": consent,
        "ok": result.get("ok", False) and not cancelled,
        "task_class": route["task_class"],
        "label": route["label"],
        "plan": route["plan"],
        "content": result.get("content", ""),
        "reason": result.get("reason"),
        "tokens": {
            "prompt": result.get("prompt_tokens"),
            "completion": result.get("completion_tokens"),
        },
        "elapsed_ms": result.get("elapsed_ms"),
        "run_id": run_id,
        "grounded": bool(_DATA_SOURCES),
        "grounding_sources": [os.path.basename(p) for p in _DATA_SOURCES],
        "citations": [],
        "idempotent_replay": False,
    }
    if cancelled:
        payload["reason"] = "cancelled_by_user"
        payload["content"] = result.get("content", "")

    if slot:
        saved = _load_idempotency()
        saved[slot] = payload
        # Keep the map bounded; oldest-insensitive but capped for file size.
        if len(saved) > 500:
            for key in list(saved)[: len(saved) - 500]:
                saved.pop(key, None)
        _save_idempotency(saved)
    return payload


@app.get("/api/autothink/history")
def history(limit: int = 20, org_id: Optional[str] = None):
    org_id = _require_tenant(org_id)
    tenant_store = _store_for(org_id)
    entries = tenant_store.all()
    return {
        "total": len(entries),
        "entries": entries[-limit:],
        "org_id": org_id,
    }


@app.post("/api/autothink/cancel")
def cancel(req: CancelRequest, org_id: Optional[str] = None):
    org_id = _require_tenant(org_id)
    record = runs.request_cancel(req.run_id, org_id=org_id)
    if record is None:
        # Unknown OR another tenant's run. Both are a refusal, never a leak.
        raise HTTPException(
            status_code=404,
            detail="No such run for this organization.",
        )
    return {
        "run_id": req.run_id,
        "state": record["state"],
        "cancel_requested": record["cancel_requested"],
    }


@app.get("/api/autothink/jobs/{run_id}")
def job_state(run_id: str, org_id: Optional[str] = None):
    org_id = _require_tenant(org_id)
    record = runs.get(run_id, org_id=org_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No such run for this organization.")
    return record


@app.get("/api/autothink/usage")
def usage_summary(org_id: Optional[str] = None):
    org_id = _require_tenant(org_id)
    return {"org_id": org_id, **usage.summary(org_id=org_id)}


@app.exception_handler(Exception)
def unhandled(_request, exc):  # pragma: no cover - defensive
    return JSONResponse(status_code=500, content={"ok": False, "error": str(exc), "content": "[SERVER ERROR] AutothinK backend raised an unhandled exception."})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8100, log_level="info")
