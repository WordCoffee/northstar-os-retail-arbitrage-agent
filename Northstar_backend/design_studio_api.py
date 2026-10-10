"""Design Studio API — backend store for projects, assets and jobs.

Phase 0 exposes honest CRUD for the merged studio. No provider calls; every
potentially paid action is recorded as a queued job and waits for explicit run.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from auth_deps import get_current_user
from data_layer import get_northstar_db

router = APIRouter(prefix="/api/design-studio", tags=["design-studio"])


class ProjectIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    section: str = Field(..., min_length=1, max_length=80)
    asin: Optional[str] = None
    brand: Optional[str] = None
    brief: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    source_record_id: Optional[str] = None
    source_record_type: Optional[str] = None


class ProjectPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    section: Optional[str] = Field(None, min_length=1, max_length=80)
    asin: Optional[str] = None
    brand: Optional[str] = None
    brief: Optional[str] = None
    state: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AssetIn(BaseModel):
    project_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=200)
    asset_type: str = Field(..., min_length=1, max_length=40)
    mime_type: Optional[str] = None
    storage_key: Optional[str] = None
    data_url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    size_bytes: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


class JobIn(BaseModel):
    project_id: Optional[str] = None
    asset_id: Optional[str] = None
    job_type: str = Field(..., min_length=1, max_length=40)
    provider: Optional[str] = "local"
    cost_preview: Optional[Dict[str, Any]] = None
    params: Optional[Dict[str, Any]] = None


class JobPatch(BaseModel):
    status: Optional[str] = None
    credits_used: Optional[float] = None
    params: Optional[Dict[str, Any]] = None
    logs: Optional[str] = None
    result_ids: Optional[List[str]] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


def _account_id(user: Dict[str, Any]) -> str:
    return user.get("user_id") or user.get("sub") or "default"


# ── Projects ───────────────────────────────────────────────────────────────

@router.post("/projects")
def create_project(body: ProjectIn, user: Dict[str, Any] = Depends(get_current_user)):
    db = get_northstar_db()
    acct = _account_id(user)
    pid = db.design_studio.projects.create({**body.model_dump(), "account_id": acct})
    return {"id": pid, "project": db.design_studio.projects.get_by_id(pid, account_id=acct)}


@router.get("/projects")
def list_projects(section: Optional[str] = None, user: Dict[str, Any] = Depends(get_current_user)):
    db = get_northstar_db()
    return {"projects": db.design_studio.projects.list_by_section(section=section, account_id=_account_id(user))}


@router.get("/projects/{pid}")
def get_project(pid: str, user: Dict[str, Any] = Depends(get_current_user)):
    db = get_northstar_db()
    project = db.design_studio.projects.get_by_id(pid, account_id=_account_id(user))
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"project": project}


@router.patch("/projects/{pid}")
def patch_project(pid: str, body: ProjectPatch, user: Dict[str, Any] = Depends(get_current_user)):
    db = get_northstar_db()
    acct = _account_id(user)
    updated = db.design_studio.projects.update(pid, body.model_dump(exclude_unset=True), account_id=acct)
    if not updated:
        # A project owned by another account is a 404, never a 403: the caller
        # must not be able to distinguish "not yours" from "does not exist".
        raise HTTPException(status_code=404, detail="Project not found")
    return {"project": db.design_studio.projects.get_by_id(pid, account_id=acct)}


@router.delete("/projects/{pid}")
def delete_project(pid: str, user: Dict[str, Any] = Depends(get_current_user)):
    db = get_northstar_db()
    deleted = db.design_studio.projects.delete(pid, account_id=_account_id(user))
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"deleted": True}


# ── Assets ─────────────────────────────────────────────────────────────────

@router.post("/assets")
def create_asset(body: AssetIn, user: Dict[str, Any] = Depends(get_current_user)):
    db = get_northstar_db()
    acct = _account_id(user)
    aid = db.design_studio.assets.create({**body.model_dump(), "account_id": acct})
    return {"id": aid, "asset": db.design_studio.assets.get_by_id(aid, account_id=acct)}


@router.get("/assets")
def list_assets(project_id: Optional[str] = None, asset_type: Optional[str] = None, user: Dict[str, Any] = Depends(get_current_user)):
    db = get_northstar_db()
    return {"assets": db.design_studio.assets.list_by_project(project_id=project_id, asset_type=asset_type, account_id=_account_id(user))}


@router.get("/assets/{aid}")
def get_asset(aid: str, user: Dict[str, Any] = Depends(get_current_user)):
    db = get_northstar_db()
    asset = db.design_studio.assets.get_by_id(aid, account_id=_account_id(user))
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"asset": asset}


@router.delete("/assets/{aid}")
def delete_asset(aid: str, user: Dict[str, Any] = Depends(get_current_user)):
    db = get_northstar_db()
    deleted = db.design_studio.assets.delete(aid, account_id=_account_id(user))
    if not deleted:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"deleted": True}


# ── Jobs ───────────────────────────────────────────────────────────────────

@router.post("/jobs")
def create_job(body: JobIn, user: Dict[str, Any] = Depends(get_current_user)):
    db = get_northstar_db()
    acct = _account_id(user)
    jid = db.design_studio.jobs.create({**body.model_dump(), "account_id": acct})
    return {"id": jid, "job": db.design_studio.jobs.get_by_id(jid, account_id=acct)}


@router.get("/jobs")
def list_jobs(project_id: Optional[str] = None, status: Optional[str] = None, user: Dict[str, Any] = Depends(get_current_user)):
    db = get_northstar_db()
    return {"jobs": db.design_studio.jobs.list_by_project(project_id=project_id, status=status, account_id=_account_id(user))}


@router.get("/jobs/{jid}")
def get_job(jid: str, user: Dict[str, Any] = Depends(get_current_user)):
    db = get_northstar_db()
    job = db.design_studio.jobs.get_by_id(jid, account_id=_account_id(user))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": job}


@router.patch("/jobs/{jid}")
def patch_job(jid: str, body: JobPatch, user: Dict[str, Any] = Depends(get_current_user)):
    db = get_northstar_db()
    acct = _account_id(user)
    updated = db.design_studio.jobs.update(jid, body.model_dump(exclude_unset=True), account_id=acct)
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": db.design_studio.jobs.get_by_id(jid, account_id=acct)}


@router.delete("/jobs/{jid}")
def delete_job(jid: str, user: Dict[str, Any] = Depends(get_current_user)):
    db = get_northstar_db()
    deleted = db.design_studio.jobs.delete(jid, account_id=_account_id(user))
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"deleted": True}



# ── Migration from the pre-backend localStorage state ──────────────────────
# The Design Studio and the two merged rooms used to keep their records in the
# browser (localStorage). This endpoint imports them once, idempotently: a
# record whose `legacyKey` is already present for this account is skipped, so
# running the migration twice can never duplicate work.

class MigrateIn(BaseModel):
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    assets: List[Dict[str, Any]] = Field(default_factory=list)
    jobs: List[Dict[str, Any]] = Field(default_factory=list)


_MIGRATABLE_SECTIONS = {
    'projects', 'listing-images', 'aplus', 'storefront', 'ads',
    'video-ugc', 'social', 'packaging', '3d-scene',
}

# The columns each store actually has. A legacy record carries keys the schema
# has never heard of (formatId, layers, purpose, tier...), and INSERTing those
# raises. Unknown keys are preserved under metadata.legacyFields instead of
# being dropped or allowed to break the import.
_PROJECT_COLS = {
    'id', 'account_id', 'name', 'section', 'asin', 'brand', 'brief', 'state',
    'metadata', 'source_record_id', 'source_record_type', 'pulled_at',
}
_ASSET_COLS = {
    'id', 'account_id', 'project_id', 'name', 'asset_type', 'mime_type',
    'storage_key', 'data_url', 'width', 'height', 'duration_seconds',
    'size_bytes', 'metadata',
}
_JOB_COLS = {
    'id', 'account_id', 'project_id', 'asset_id', 'job_type', 'provider',
    'status', 'cost_preview', 'credits_used', 'params', 'logs', 'result_ids',
    'started_at', 'finished_at', 'metadata',
}


def _fit(payload: Dict[str, Any], allowed: set) -> Dict[str, Any]:
    """Reduce a legacy record to the columns the store has.

    Anything the schema does not model is preserved under
    ``metadata.legacyFields`` so the import is lossless even though the shape
    changed.
    """
    out = {k: v for k, v in payload.items() if k in allowed}
    extra = {k: v for k, v in payload.items() if k not in allowed and k != 'metadata'}
    if extra:
        meta = dict(out.get('metadata') or {})
        current = dict(meta.get('legacyFields') or {})
        current.update(extra)
        meta['legacyFields'] = current
        out['metadata'] = meta
    return out


def _existing_legacy_keys(db, acct: str) -> set:
    """Every legacyKey this account already holds, across ALL THREE stores.

    The first version of this only scanned projects, so an asset or a job was
    re-created on every run — the idempotency it advertised did not hold for
    two of the three stores. The end-to-end migration test caught it.
    """
    def key_of(rec):
        meta = rec.get('metadata')
        if isinstance(meta, dict):
            k = meta.get('legacyKey')
            return str(k) if k else None
        return None

    keys = set()
    for p in db.design_studio.projects.list_by_section(account_id=acct, limit=5000):
        k = key_of(p)
        if k:
            keys.add('project:' + k)
    for a in db.design_studio.assets.list_by_project(account_id=acct, limit=5000):
        k = key_of(a)
        if k:
            keys.add('asset:' + k)
    for j in db.design_studio.jobs.list_by_project(account_id=acct, limit=5000):
        k = key_of(j)
        if k:
            keys.add('job:' + k)
    return keys


@router.post("/migrate")
def migrate_legacy(body: MigrateIn, user: Dict[str, Any] = Depends(get_current_user)):
    """Import browser-local records into the tenant's backend store.

    Idempotent per account across projects, assets AND jobs: a record carrying a
    `legacyKey` that is already stored is reported as skipped, never
    re-created. Unknown sections are rejected rather than silently filed under a
    guess, and legacy keys the schema does not model are preserved under
    ``metadata.legacyFields`` instead of breaking the insert.
    """
    db = get_northstar_db()
    acct = _account_id(user)
    created = {'projects': 0, 'assets': 0, 'jobs': 0}
    skipped = {'projects': 0, 'assets': 0, 'jobs': 0}
    errors: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc).isoformat()

    def legacy_key_of(meta: Any) -> Optional[str]:
        if isinstance(meta, dict):
            v = meta.get('legacyKey')
            return str(v) if v else None
        return None

    existing = _existing_legacy_keys(db, acct)
    project_map: Dict[str, str] = {}  # legacy project key -> new project id

    for raw in body.projects:
        try:
            meta = dict(raw.get('metadata') or {})
            key = legacy_key_of(meta)
            if key and ('project:' + key) in existing:
                skipped['projects'] += 1
                continue
            section = raw.get('section') or 'projects'
            if section not in _MIGRATABLE_SECTIONS:
                errors.append({'kind': 'project', 'name': raw.get('name'), 'error': f'unknown section {section!r}'})
                continue
            payload = _fit({
                **raw,
                'account_id': acct,
                'name': raw.get('name') or 'Imported draft',
                'section': section,
                # metadata must be part of the dict _fit sees, otherwise _fit's
                # legacyFields merge is thrown away by a later overwrite.
                'metadata': {**meta, 'importedFrom': 'localStorage', 'importedAt': now},
            }, _PROJECT_COLS)
            pid = db.design_studio.projects.create(payload)
            if key:
                existing.add('project:' + key)
                project_map[key] = pid
            created['projects'] += 1
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            errors.append({'kind': 'project', 'name': raw.get('name'), 'error': f'{exc.__class__.__name__}: {exc}'})

    for kind, items, cols in (
        ('assets', body.assets, _ASSET_COLS),
        ('jobs', body.jobs, _JOB_COLS),
    ):
        store = getattr(db.design_studio, kind)
        singular = 'asset' if kind == 'assets' else 'job'
        for raw in items:
            try:
                meta = dict(raw.get('metadata') or {})
                key = legacy_key_of(meta)
                if key and (singular + ':' + key) in existing:
                    skipped[kind] += 1
                    continue
                project_id = raw.get('project_id')
                legacy_project = raw.get('legacyProjectKey')
                if legacy_project and str(legacy_project) in project_map:
                    project_id = project_map[str(legacy_project)]
                payload = _fit({
                    **raw,
                    'account_id': acct,
                    'project_id': project_id,
                    'metadata': {**meta, 'importedFrom': 'localStorage', 'importedAt': now},
                }, cols)
                if kind == 'jobs':
                    payload.setdefault('job_type', 'generate')
                if kind == 'assets':
                    payload.setdefault('asset_type', 'legacy')
                # ds_jobs has no `name` column: fold a legacy name into metadata
                # rather than setting a key the table cannot take.
                if kind == 'assets' and not payload.get('name'):
                    payload['name'] = f"Imported {singular} {str(raw.get('id') or '')[:12]}".strip()
                if kind == 'jobs':
                    legacy_name = raw.get('name') or f"Imported {singular} {str(raw.get('id') or '')[:12]}".strip()
                    meta_out = dict(payload.get('metadata') or {})
                    meta_out.setdefault('legacyName', legacy_name)
                    payload['metadata'] = meta_out
                store.create(payload)
                if key:
                    existing.add(singular + ':' + key)
                created[kind] += 1
            except Exception as exc:  # noqa: BLE001
                errors.append({'kind': kind, 'name': raw.get('name'), 'error': f'{exc.__class__.__name__}: {exc}'})

    return {
        'ok': not errors,
        'created': created,
        'skipped': skipped,
        'errors': errors,
        'note': 'Idempotent per account across projects, assets and jobs: re-running reports skipped, never duplicates.',
    }



# ── Search and export (tenant-scoped) ─────────────────────────────────────
# Both exist so the isolation contract can be tested on the surfaces a seller
# actually uses to find and ship work, not only on CRUD-by-id.

@router.get("/search")
def search(
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=50, le=200),
    user: Dict[str, Any] = Depends(get_current_user),
):
    """Case-insensitive substring search over the caller's own projects,
    assets and jobs. Scoped to the account at the query, not filtered after."""
    acct = _account_id(user)
    db = get_northstar_db()
    needle = (q or "").strip()
    like = f"%{needle}%"
    projects = [p for p in db.design_studio.projects.list_by_section(account_id=acct, limit=1000)
                if not needle or needle.lower() in (p.get("name") or "").lower()]
    assets = [a for a in db.design_studio.assets.list_by_project(account_id=acct, limit=1000)
              if not needle or needle.lower() in (a.get("name") or "").lower()]
    jobs = [j for j in db.design_studio.jobs.list_by_project(account_id=acct, limit=1000)
            if not needle or needle.lower() in (j.get("job_type") or "").lower()]
    rechecks = [r for r in db.design_studio.rechecks.list_for_account(acct, limit=1000)
                if not needle or needle.lower() in ((r.get("asset_id") or "") + " " + (r.get("verdict") or "")).lower()]
    return {
        "q": needle,
        "projects": projects[:limit],
        "assets": assets[:limit],
        "jobs": jobs[:limit],
        "rechecks": rechecks[:limit],
        "counts": {"projects": len(projects), "assets": len(assets), "jobs": len(jobs), "rechecks": len(rechecks)},
    }


@router.get("/projects/{pid}/export-manifest")
def export_manifest(pid: str, user: Dict[str, Any] = Depends(get_current_user)):
    """The flat-file image manifest for one project.

    Refuses a project owned by another account with a 404, exactly like a
    missing one. Deliberately returns the documented column names so the
    operator can map them straight into a feed, and never invents a URL: a slot
    with no asset is emitted as null rather than as a placeholder path.
    """
    acct = _account_id(user)
    db = get_northstar_db()
    project = db.design_studio.projects.get_by_id(pid, account_id=acct)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    assets = db.design_studio.assets.list_by_project(project_id=pid, account_id=acct, limit=1000)
    by_slot = {a.get("metadata", {}).get("slot"): a for a in assets if isinstance(a.get("metadata"), dict)}

    def slot(col: str, role: str):
        a = by_slot.get(col)
        return {"column": col, "role": role, "assetId": a.get("id") if a else None,
                "url": (a.get("storage_key") or None) if a else None,
                "present": bool(a)}

    manifest = [
        slot("main_image_url", "main"),
        slot("swatch_image_url", "swatch"),
    ] + [slot(f"other_image_url{i}", "secondary") for i in range(1, 9)]
    return {
        "projectId": pid,
        "asin": project.get("asin"),
        "section": project.get("section"),
        "filename": project.get("metadata", {}).get("filename") if isinstance(project.get("metadata"), dict) else None,
        "manifest": manifest,
        "note": "Only assets owned by the calling account appear. An empty slot is null, never a placeholder URL.",
    }


# ── Re-check log (Phase 5 item 2): tenant-scoped ──────────────────────────

class RecheckIn(BaseModel):
    asset_id: Optional[str] = None
    verdict: str = Field(..., min_length=1, max_length=40)
    passed: bool = False
    detail: Optional[str] = None
    surface: Optional[str] = None
    tag_required: Optional[bool] = None
    checked_by: Optional[str] = None
    checked_at: Optional[str] = None
    legacy_key: Optional[str] = None


@router.post("/rechecks")
def create_recheck(body: RecheckIn, user: Dict[str, Any] = Depends(get_current_user)):
    """Record one dated verification of a live asset.

    The verdict is supplied by the caller and stores what the reader actually
    returned. A failed check is stored as a failure; this endpoint never
    upgrades a verdict.
    """
    db = get_northstar_db()
    acct = _account_id(user)
    rec = body.model_dump()
    rec["account_id"] = acct
    rid = db.design_studio.rechecks.create(rec)
    return {"id": rid, "recheck": db.design_studio.rechecks.get_by_id(rid, account_id=acct)}


@router.get("/rechecks")
def list_rechecks(
    asset_id: Optional[str] = None,
    limit: int = Query(default=200, le=1000),
    user: Dict[str, Any] = Depends(get_current_user),
):
    db = get_northstar_db()
    acct = _account_id(user)
    rows = db.design_studio.rechecks.list_for_account(acct, asset_id=asset_id, limit=limit)
    return {
        "rechecks": rows,
        "counts": {
            "total": len(rows),
            "failed": sum(1 for r in rows if not r.get("passed")),
        },
        "note": "Scoped to the calling account. A failed check is recorded as a failure.",
    }


@router.get("/rechecks/{rid}")
def get_recheck(rid: str, user: Dict[str, Any] = Depends(get_current_user)):
    db = get_northstar_db()
    rec = db.design_studio.rechecks.get_by_id(rid, account_id=_account_id(user))
    if not rec:
        raise HTTPException(status_code=404, detail="Re-check not found")
    return {"recheck": rec}


@router.delete("/rechecks/{rid}")
def delete_recheck(rid: str, user: Dict[str, Any] = Depends(get_current_user)):
    db = get_northstar_db()
    if not db.design_studio.rechecks.delete(rid, account_id=_account_id(user)):
        raise HTTPException(status_code=404, detail="Re-check not found")
    return {"deleted": True}


class RecheckMigrateIn(BaseModel):
    entries: List[Dict[str, Any]] = Field(default_factory=list)


@router.post("/rechecks/migrate")
def migrate_rechecks(body: RecheckMigrateIn, user: Dict[str, Any] = Depends(get_current_user)):
    """Import browser-local re-check entries, idempotently.

    Idempotency is enforced by a UNIQUE index on (account_id, legacy_key), so a
    second run reports `skipped` rather than duplicating. An entry with no
    legacy key is always created, because there is no way to tell it apart from
    a genuinely new check.
    """
    db = get_northstar_db()
    acct = _account_id(user)
    created = 0
    skipped = 0
    errors: List[Dict[str, Any]] = []
    seen = db.design_studio.rechecks.existing_legacy_keys(acct)

    for raw in body.entries:
        try:
            key = raw.get("legacyKey") or raw.get("legacy_key")
            if key and str(key) in seen:
                skipped += 1
                continue
            rec = {
                "account_id": acct,
                "asset_id": raw.get("assetId") or raw.get("asset_id"),
                "checked_at": raw.get("checkedAt") or raw.get("checked_at"),
                "checked_by": raw.get("user") or raw.get("checked_by"),
                "verdict": raw.get("verdict") or "unknown",
                "passed": bool(raw.get("passed")),
                "detail": raw.get("detail"),
                "surface": raw.get("surface"),
                "tag_required": raw.get("tagRequired") if raw.get("tagRequired") is not None else None,
                "legacy_key": str(key) if key else None,
            }
            db.design_studio.rechecks.create(rec)
            if key:
                seen.add(str(key))
            created += 1
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            errors.append({"verdict": raw.get("verdict"), "error": f"{exc.__class__.__name__}: {exc}"})

    return {
        "ok": not errors,
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "note": "Idempotent per account via the legacy-key index: re-running reports skipped, never duplicates.",
    }


# ── Generation arming status (read-only, NO provider call) ────────────────
# Phase 5 item 9. The Studio must be able to say truthfully whether generation
# is armed. This reads local flags only: it never contacts a provider, never
# enqueues work, and never spends anything.

@router.get("/generation-status")
def generation_status(user: Dict[str, Any] = Depends(get_current_user)):
    """Report the media-generation arming state. Read-only, zero provider calls."""
    state: Dict[str, Any] = {"media_live_armed": False, "providers": {}, "source": "unreadable"}
    try:
        import model_router  # local module; no network
        state["media_live_armed"] = bool(model_router.media_live_armed())
        state["cloud_live_armed"] = bool(model_router.cloud_live_armed())
        for p in ("local", "cloud"):
            try:
                state["providers"][p] = bool(model_router.provider_armed(p))
            except Exception:
                state["providers"][p] = False
        state["source"] = "model_router"
    except Exception as exc:  # noqa: BLE001 - the answer is UNARMED, never a guess
        state["error"] = f"{exc.__class__.__name__}: {exc}"
    state["note"] = (
        "Read-only arming state. An unreadable state is reported as UNARMED. "
        "No provider is contacted and nothing is generated by this endpoint."
    )
    return state


# ── Status / health for the merged studio ──────────────────────────────────

@router.get("/status")
def studio_status(user: Dict[str, Any] = Depends(get_current_user)):
    db = get_northstar_db()
    account = _account_id(user)
    return {
        "mode": "local",
        "projects": len(db.design_studio.projects.list_by_section(account_id=account, limit=1000)),
        "assets": len(db.design_studio.assets.list_by_project(account_id=account, limit=1000)),
        "jobs": len(db.design_studio.jobs.list_by_project(account_id=account, limit=1000)),
        "note": "Local design workspace. Provider generation is gated behind explicit Run actions.",
    }
