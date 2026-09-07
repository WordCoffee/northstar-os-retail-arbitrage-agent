"""Northstar AutoThink server — FastAPI app.

Routes:
  GET  /                                serves autothink/ui/index.html
  GET  /health                          liveness probe
  GET  /api/autothink/models            installed Ollama models + provider availability
  POST /api/autothink/run               route + generate a response for a command
  GET  /api/autothink/history           session command history (persisted locally)

Local Ollama is the default provider. The cloud provider is fully coded but
gate-kept behind OPENAI_API_KEY presence — no live paid calls are executed
without explicit operator approval (Hard Stop Zone, AGENTS.md §3).
"""

import os
import sys

# Make sibling packages importable when served from the repo root.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_ROOT, os.path.dirname(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional

from backend.llm_adapter import UnifiedLLMAdapter, DEFAULT_LOCAL_MODEL, DEFAULT_CLOUD_MODEL
from orchestration.router import route_task, build_context, audit
from memory.session_store import SessionStore

UI_PATH = os.path.join(_ROOT, "ui", "index.html")
AUDIT_LOG = os.path.join(_ROOT, "audit", "autothink-runs.jsonl")

# Local data the brain can reference when answering.
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

app = FastAPI(title="Northstar OS AutoThink", version="2.0.0")
adapter = UnifiedLLMAdapter()
store = SessionStore()


class RunRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    provider: str = Field("local", pattern="^(local|cloud)$")
    model: Optional[str] = None


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
    return {
        "local_available": local_ok,
        "cloud_available": adapter.cloud_available(),
        "default_local_model": DEFAULT_LOCAL_MODEL,
        "default_cloud_model": DEFAULT_CLOUD_MODEL,
        "models": installed,
    }


@app.post("/api/autothink/run")
def run(req: RunRequest):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=422, detail="query is empty")

    route = route_task(query)
    context = build_context(query, route, data_sources=_DATA_SOURCES)

    result = adapter.generate(query, provider=req.provider, model=req.model)

    entry = {
        "track": route["task_class"],
        "provider": req.provider or "local",
        "model": result.get("model"),
        "ok": result.get("ok", False),
        "task_class": route["task_class"],
        "label": route["label"],
        "files_touched": [],
        "live_action_requested": False,
        "approval_status": "not_requested",
        "reason": result.get("reason"),
    }
    store.add({"query": query, **entry})
    audit(dict(entry), log_path=AUDIT_LOG)

    return {
        "query": query,
        "provider": result.get("provider", req.provider),
        "model": result.get("model"),
        "ok": result.get("ok", False),
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
    }


@app.get("/api/autothink/history")
def history(limit: int = 20):
    entries = store.all()
    return {"total": len(entries), "entries": entries[-limit:]}


@app.exception_handler(Exception)
def unhandled(_request, exc):  # pragma: no cover - defensive
    return JSONResponse(status_code=500, content={"ok": False, "error": str(exc), "content": "[SERVER ERROR] AutoThink backend raised an unhandled exception."})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8100, log_level="info")