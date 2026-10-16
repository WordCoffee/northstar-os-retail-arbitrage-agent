"""Design Studio — public API (keys + webhooks) and credit meter endpoints.

Competitive-RE build (2026-10-16), items 1 + 4: Packify sells API access on its
Business plan (dated `/api/open/2025-10/` paths, `PackifyApiKey` authorization,
async submission with JSON callbacks + retry policy). This module ships the
same contract shape for Northstar:

- Session endpoints (`/api/design-studio/api-keys ...`) mint / list / revoke
  keys. Secrets are NEVER stored — only a sha256 digest + a display prefix.
- Open endpoints (`/api/open/2026-10/packaging-design`, `.../dielines`,
  `.../jobs/{job_id}`) accept `X-Api-Key: nsk_...` (or Bearer) and reuse the
  async generation lane (identical engine gates + credit policy).
- Generation submissions accept `callback_url`; completion/failure delivers a
  JSON webhook (bounded retries; delivery recorded on the job).
- Credit meter endpoints for the enforced mode (balance / costs / grant).

No provider is called anywhere in this module: the local ComfyUI gate rules.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from design_studio_async import (_costs, credits_enforced, ensure_initial_grant,
                                 get_ledger, submit_generation)
from design_studio_api import studio_account
import design_studio_print as _print_mod

router = APIRouter(tags=["design-studio-openapi"])

_KEYS_PATH = Path(__file__).resolve().parent / "data" / "api_keys.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── API key registry (digests only) ─────────────────────────────────────────

class _KeyStore:
    """Append-only JSONL key registry. Stores sha256 digests, never secrets."""

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.Lock()
        self._rows: List[dict] = []
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:  # noqa: BLE001 - skip corrupt lines, never crash boot
                    continue
                if row.get("event") == "revoke":
                    for r in self._rows:
                        if r.get("id") == row.get("id"):
                            r["revoked_at"] = row.get("revoked_at")
                    continue
                if row.get("id"):
                    self._rows.append(row)

    def create(self, account_id: str, label: str = "") -> dict:
        secret = "nsk_" + secrets.token_hex(24)
        row = {"id": "key_" + uuid.uuid4().hex[:16], "account_id": account_id,
               "label": (label or "")[:80], "prefix": secret[:12],
               "sha256": hashlib.sha256(secret.encode()).hexdigest(),
               "created_at": _now(), "last_used_at": None, "revoked_at": None}
        with self._lock:
            self._rows.append(row)
            with open(self._path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")
        return {"id": row["id"], "prefix": row["prefix"], "label": row["label"],
                "created_at": row["created_at"], "key": secret}

    def verify(self, secret: str) -> Optional[str]:
        digest = hashlib.sha256((secret or "").encode()).hexdigest()
        for row in self._rows:
            if row.get("sha256") == digest and not row.get("revoked_at"):
                row["last_used_at"] = _now()
                return row["account_id"]
        return None

    def list_for(self, account_id: str) -> List[dict]:
        return [{"id": r["id"], "label": r["label"], "prefix": r["prefix"],
                 "created_at": r["created_at"], "last_used_at": r["last_used_at"],
                 "revoked_at": r["revoked_at"]}
                for r in self._rows if r["account_id"] == account_id]

    def revoke(self, account_id: str, key_id: str) -> bool:
        for r in self._rows:
            if r["id"] == key_id and r["account_id"] == account_id and not r.get("revoked_at"):
                r["revoked_at"] = _now()
                with self._lock:
                    with open(self._path, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps({"event": "revoke", "id": key_id,
                                             "revoked_at": r["revoked_at"]}) + "\n")
                return True
        return False


_STORE: Optional[_KeyStore] = None


def get_key_store() -> _KeyStore:
    global _STORE
    if _STORE is None:
        _STORE = _KeyStore(_KEYS_PATH)
    return _STORE


async def api_key_account(request: Request) -> str:
    """Resolve the account from an API key (`X-Api-Key` or Bearer nsk_...)."""
    xk = request.headers.get("x-api-key")
    auth = request.headers.get("authorization", "")
    bearer = auth[7:].strip() if auth.lower().startswith("bearer ") else None
    secret = xk or bearer
    if not secret or not secret.startswith("nsk_"):
        raise HTTPException(status_code=401, detail="API key required (send X-Api-Key: nsk_...)")
    acct = get_key_store().verify(secret)
    if not acct:
        raise HTTPException(status_code=401, detail="Invalid or revoked API key")
    return acct


# ── Session endpoints: key management ───────────────────────────────────────

class ApiKeyIn(BaseModel):
    label: str = Field("", max_length=80)


@router.post("/api/design-studio/api-keys", status_code=201)
def create_api_key(body: ApiKeyIn, acct: str = Depends(studio_account)):
    return {"key": get_key_store().create(acct, body.label),
            "note": "Store this key now — it is not recoverable; only its digest is kept."}


@router.get("/api/design-studio/api-keys")
def list_api_keys(acct: str = Depends(studio_account)):
    return {"keys": get_key_store().list_for(acct)}


@router.delete("/api/design-studio/api-keys/{key_id}")
def revoke_api_key(key_id: str, acct: str = Depends(studio_account)):
    if not get_key_store().revoke(acct, key_id):
        raise HTTPException(status_code=404, detail="Key not found or already revoked")
    return {"revoked": key_id}


# ── Session endpoints: credit meter (item 4) ────────────────────────────────

class CreditGrantIn(BaseModel):
    plan: str = Field("foundation", max_length=40)


@router.get("/api/design-studio/credits")
def credits_status(acct: str = Depends(studio_account)):
    enforce = credits_enforced()
    ledger = get_ledger()
    entries = [e for e in ledger.entries() if e["account_id"] == acct][-20:]
    return {"enforce": enforce, "balance": ledger.balance(acct),
            "costs": _costs(), "entries": entries}


@router.post("/api/design-studio/credits/grant")
def credits_grant(body: CreditGrantIn, acct: str = Depends(studio_account)):
    from credit_ledger import UnknownPlanError
    ledger = get_ledger()
    key = f"grant:alpha:{acct}:{body.plan}"
    already = any(e.get("idempotency_key") == key for e in ledger.entries())
    try:
        ensure_initial_grant(ledger, acct, body.plan)
    except UnknownPlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"granted": not already, "balance": ledger.balance(acct), "plan": body.plan}


# ── Open API (key-authenticated) ────────────────────────────────────────────

class OpenDesignIn(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=2000)
    callback_url: Optional[str] = Field(None, max_length=500)
    width: Optional[int] = Field(None, ge=64, le=4096)
    height: Optional[int] = Field(None, ge=64, le=4096)
    tier: str = Field("draft")
    project_id: Optional[str] = None


class OpenDielineIn(BaseModel):
    template_id: str = Field(..., min_length=3, max_length=60)
    params: Optional[Dict[str, Any]] = None
    name: Optional[str] = Field(None, max_length=120)
    project_id: Optional[str] = None


@router.post("/api/open/2026-10/packaging-design", status_code=202)
def open_packaging_design(body: OpenDesignIn, acct: str = Depends(api_key_account)):
    """Async design submission: queues a local generation, returns the job id.

    Identical gates to the UI lane: engine must be armed (409 otherwise);
    credits enforced only when DESIGN_CREDITS_ENFORCE=1 (402 when short).
    """
    if body.callback_url and not body.callback_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=422, detail="callback_url must be http(s)")
    try:
        res = submit_generation(acct, brief=body.prompt, kind="image", tier=body.tier,
                                purpose="open-api", width=body.width, height=body.height,
                                project_id=body.project_id, callback_url=body.callback_url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"contract": "open/2026-10", "job_id": res["job"]["id"], "status": "queued",
            "cost": res["job"].get("cost_preview"), "enforce": res["enforce"],
            "callback_registered": bool(body.callback_url)}


@router.post("/api/open/2026-10/dielines")
def open_dielines(body: OpenDielineIn, acct: str = Depends(api_key_account)):
    """Synchronous layered dieline (SVG + PDF assets) — our API differentiator."""
    try:
        build = _print_mod.build_from_template(body.template_id, body.params)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    svg = _print_mod.render_svg(build)
    pdf = _print_mod.render_pdf(build)
    assets = _print_mod._persist(build, svg, pdf, acct=acct,
                                 project_id=body.project_id, name=body.name)
    return {"contract": "open/2026-10", "template_id": body.template_id,
            "size_mm": {"width": build["width_mm"], "height": build["height_mm"]},
            "layers": _print_mod.LAYER_ORDER, "assets": assets,
            "note": build.get("note")}


@router.get("/api/open/2026-10/jobs/{job_id}")
def open_job_status(job_id: str, acct: str = Depends(api_key_account)):
    from data_layer import get_northstar_db
    job = get_northstar_db().design_studio.jobs.get_by_id(job_id, account_id=acct)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"contract": "open/2026-10", "job": job}
