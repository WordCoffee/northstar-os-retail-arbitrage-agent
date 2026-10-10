"""Design Studio API — backend store for projects, assets and jobs.

Phase 0 exposes honest CRUD for the merged studio. No provider calls; every
potentially paid action is recorded as a queued job and waits for explicit run.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
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
    # NOTE (Phase 6 finding, left as-is deliberately): get_current_user has no
    # cookie awareness, so UI (cookie) callers are the demo fallback here and
    # every legacy caller lands in one shared bucket. Changing that moves
    # already-stored data between buckets, so it is recorded for the owner
    # rather than changed in passing. The imported-evidence endpoints do NOT
    # use this function; they resolve a strict organization via studio_account.
    return user.get("user_id") or user.get("sub") or "default"


async def studio_account(request: Request) -> str:
    """Strict, ORGANIZATION-scoped identity for the imported-evidence surfaces.

    The legacy `get_current_user` dependency predates hosted auth: with no
    token it returns a demo identity, and the cookie transport the SPA actually
    uses never reaches it, so every legacy caller collapses into one shared
    bucket. That is fine for the public demo read surface but NOT for
    tenant-scoped imported marketplace data. This dependency resolves a REAL
    session (the HttpOnly ns_session cookie or a Bearer token) and scopes the
    store to the session's organization. No anonymous fallback.
    """
    from auth_deps import require_session
    user = await require_session(request)
    org = user.get("tenant_id") or user.get("id")
    if not org:
        raise HTTPException(status_code=401, detail="Session has no resolved organization")
    return str(org)


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


# ── Imported marketplace reports (Phase 6 item 4) ─────────────────────────
# Files are archived per account with a source label and observed date. Every
# response says the data is an imported file, NOT live. Missing columns are
# NULL, never 0; the report caveats (65-day lookback, 31-day API range,
# click-only bias) travel with the records.

class ImportIn(BaseModel):
    kind: str = Field(..., min_length=1, max_length=60)
    source_label: str = Field(..., min_length=1, max_length=120)
    filename: Optional[str] = None
    content: str
    observed_from: Optional[str] = None
    observed_to: Optional[str] = None


def _parse_error(exc: Exception) -> HTTPException:
    return HTTPException(status_code=422, detail={
        "code": "import_parse_error",
        "message": str(exc),
    })


def _banner(imp: Dict[str, Any]) -> Dict[str, Any]:
    observed = imp.get("observed_from") or imp.get("observed_to")
    if imp.get("observed_from") and imp.get("observed_to") and imp["observed_from"] != imp["observed_to"]:
        observed = f"{imp['observed_from']} to {imp['observed_to']}"
    return {
        "text": f"imported file, observed {observed or 'UNKNOWN'}, not live",
        "observed_from": imp.get("observed_from"),
        "observed_to": imp.get("observed_to"),
        "live": False,
    }


@router.post("/imports")
def create_import(body: ImportIn, acct: str = Depends(studio_account)):
    from design_studio_imports import KINDS, ImportParseError, parse_import
    db = get_northstar_db()
    if body.kind not in KINDS:
        raise HTTPException(status_code=400, detail={
            "code": "unknown_import_kind",
            "message": f"kind must be one of: {', '.join(KINDS)}",
        })
    try:
        parsed = parse_import(
            kind=body.kind,
            content=body.content,
            filename=body.filename,
            observed_from=body.observed_from,
            observed_to=body.observed_to,
        )
    except ImportParseError as exc:
        raise _parse_error(exc)

    existing = db.design_studio.imports.get_by_fingerprint(acct, parsed["fingerprint"])
    if existing:
        return {
            "state": "duplicate",
            "import": existing,
            "rows_added": 0,
            "banner": _banner(existing),
            "notes": existing.get("notes") or [],
            "note": "This exact file was already imported for this account. Nothing was duplicated.",
        }

    now = datetime.now(timezone.utc).isoformat()
    import_id = db.design_studio.imports.create({
        "account_id": acct,
        "kind": body.kind,
        "source_label": body.source_label,
        "filename": body.filename,
        "format": parsed["format"],
        "observed_from": parsed["observed_from"],
        "observed_to": parsed["observed_to"],
        "observed_source": parsed["observed_source"],
        "row_count": len(parsed["rows"]),
        "skipped_rows": parsed["skipped_rows"],
        "columns_found": parsed["columns_found"],
        "missing_columns": parsed["missing_columns"],
        "notes": parsed["notes"],
        "fingerprint": parsed["fingerprint"],
        "imported_at": now,
        "imported_by": acct,
    })
    # The create above can win an integrity race and return the row that already
    # existed; only add rows when this call created the import.
    stored = db.design_studio.imports.get_by_id(import_id, account_id=acct)
    added = 0
    if stored and stored.get("fingerprint") == parsed["fingerprint"] and stored.get("imported_at") == now:
        rows = [{
            "account_id": acct,
            "import_id": import_id,
            "kind": body.kind,
            **{k: r.get(k) for k in (
                "term", "campaign", "ad_group", "match_type", "targeting",
                "currency", "impressions", "clicks", "orders", "units", "spend",
                "sales", "search_frequency_rank", "search_query_score",
                "asin_click_share", "row_from", "row_to")},
        } for r in parsed["rows"]]
        added = db.design_studio.search_terms.add_many(rows)
    else:
        return {
            "state": "duplicate",
            "import": stored,
            "rows_added": 0,
            "banner": _banner(stored or {}),
            "notes": (stored or {}).get("notes") or [],
            "note": "This exact file was already imported for this account. Nothing was duplicated.",
        }

    fresh = db.design_studio.imports.get_by_id(import_id, account_id=acct)
    return {
        "state": "imported",
        "import": fresh,
        "rows_added": added,
        "banner": _banner(fresh or {}),
        "notes": (fresh or {}).get("notes") or [],
        "note": "Archived for this account with its source label and observed date. This is file data, not a live feed.",
    }


@router.get("/imports")
def list_imports(kind: Optional[str] = None, acct: str = Depends(studio_account)):
    from design_studio_imports import KIND_BRAND_ANALYTICS_SQP, KIND_SP_SEARCH_TERMS
    db = get_northstar_db()
    rows = db.design_studio.imports.list_for_account(acct, kind=kind)
    kinds: Dict[str, Any] = {}
    for k in (KIND_SP_SEARCH_TERMS, KIND_BRAND_ANALYTICS_SQP):
        latest = next((r for r in rows if r["kind"] == k), None)
        terms = db.design_studio.search_terms.list_for_account(acct, kind=k, limit=1)
        kinds[k] = {
            "available": latest is not None,
            "latest": latest,
            "banner": _banner(latest) if latest else None,
            "row_count": latest.get("row_count") if latest else None,
            "has_term_rows": bool(terms),
        }
    return {
        "imports": rows,
        "kinds": kinds,
        "note": "Every row is an archived file for this account. Brand Analytics is UNAVAILABLE until a file is imported.",
    }


@router.get("/imports/{iid}")
def get_import(iid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    imp = db.design_studio.imports.get_by_id(iid, account_id=acct)
    if not imp:
        raise HTTPException(status_code=404, detail="Import not found")
    return {"import": imp, "banner": _banner(imp)}


@router.delete("/imports/{iid}")
def delete_import(iid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    if not db.design_studio.imports.delete(iid, account_id=acct):
        raise HTTPException(status_code=404, detail="Import not found")
    return {"deleted": True}


@router.get("/terms")
def list_terms(
    q: str = Query(default="", max_length=200),
    kind: Optional[str] = None,
    import_id: Optional[str] = None,
    limit: int = Query(default=200, le=1000),
    acct: str = Depends(studio_account),
):
    db = get_northstar_db()
    rows = db.design_studio.search_terms.list_for_account(acct, kind=kind, import_id=import_id, q=q, limit=limit)
    missing_clicks = sum(1 for r in rows if r.get("clicks") is None)
    return {
        "terms": rows,
        "counts": {
            "total": len(rows),
            "without_clicks_column": missing_clicks,
        },
        "note": "Scoped to the calling account. A term with no clicks value came from a file without that column: it is UNKNOWN, not zero.",
    }


@router.get("/terms/export")
def export_terms(
    q: str = Query(default="", max_length=200),
    kind: Optional[str] = None,
    acct: str = Depends(studio_account),
):
    import csv as _csv
    import io as _io
    db = get_northstar_db()
    rows = db.design_studio.search_terms.list_for_account(acct, kind=kind, q=q, limit=10000)
    buf = _io.StringIO()
    writer = _csv.writer(buf)
    writer.writerow(["term", "campaign", "ad_group", "match_type", "impressions",
                     "clicks", "orders", "spend", "sales", "observed_from",
                     "observed_to", "source"])
    for r in rows:
        writer.writerow([
            r.get("term"), r.get("campaign"), r.get("ad_group"), r.get("match_type"),
            _cell(r.get("impressions")), _cell(r.get("clicks")), _cell(r.get("orders")),
            _cell(r.get("spend")), _cell(r.get("sales")),
            r.get("row_from"), r.get("row_to"), "imported file, not live",
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="design-studio-search-terms.csv"'},
    )


def _cell(v):
    """A NULL cell is EMPTY in the export - never rendered as 0."""
    return "" if v is None else v


class BriefIn(BaseModel):
    term_ids: Optional[List[str]] = None
    q: str = ""
    limit: int = Field(default=25, ge=1, le=200)
    brand: Optional[Dict[str, Any]] = None
    keywords: Optional[List[str]] = None


@router.post("/terms/brief")
def terms_brief(body: BriefIn, acct: str = Depends(studio_account)):
    """Compose a creative brief from imported terms + the brand profile.

    NO generation and NO provider call: the brief is text composed from the
    operator's own imported evidence, and every ranking carries its sample size
    and the click-only caveat.
    """
    from design_studio_imports import build_brief
    db = get_northstar_db()
    rows = db.design_studio.search_terms.list_for_account(acct, q=body.q, limit=1000)
    if body.term_ids:
        wanted = set(body.term_ids)
        rows = [r for r in rows if r.get("id") in wanted]
    brief = build_brief(terms=rows[: body.limit], brand=body.brand, keywords=body.keywords)
    brief["source_rows"] = len(rows)
    return brief


# ── Creative variants (Phase 6 item 6) ────────────────────────────────────

class VariantIn(BaseModel):
    project_id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=200)
    asset_id: Optional[str] = None
    format: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class VariantPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    asset_id: Optional[str] = None
    format: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class VariantMetricIn(BaseModel):
    source: str = "user"
    import_id: Optional[str] = None
    observed_from: Optional[str] = None
    observed_to: Optional[str] = None
    impressions: Optional[float] = None
    clicks: Optional[float] = None
    orders: Optional[float] = None
    spend: Optional[float] = None
    sales: Optional[float] = None
    note: Optional[str] = None


class VariantMetricsImportIn(BaseModel):
    content: str
    filename: Optional[str] = None


@router.post("/variants")
def create_variant(body: VariantIn, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    vid = db.design_studio.variants.create({**body.model_dump(), "account_id": acct})
    return {"id": vid, "variant": db.design_studio.variants.get_by_id(vid, account_id=acct)}


@router.get("/variants")
def list_variants(project_id: Optional[str] = None, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    variants = db.design_studio.variants.list_for_account(acct, project_id=project_id)
    return {"variants": variants, "metrics": db.design_studio.variants.metrics_for_account(acct)}


@router.get("/variants/compare")
def compare_variants(acct: str = Depends(studio_account)):
    """Side-by-side comparison of this account's variants.

    Aggregates only what was entered or imported. A metric with no rows is
    UNKNOWN (never 0), sample sizes are stated with a warning below 25 clicks,
    and the payload states plainly that it makes no causation claim: Amazon's
    reports carry no creative identifier, so a difference cannot be attributed
    to the creative by this data alone.
    """
    db = get_northstar_db()
    variants = db.design_studio.variants.list_for_account(acct)
    metrics = db.design_studio.variants.metrics_for_account(acct)
    by_variant: Dict[str, List[Dict[str, Any]]] = {}
    for m in metrics:
        by_variant.setdefault(m["variant_id"], []).append(m)

    def agg(rows, field):
        vals = [r[field] for r in rows if r.get(field) is not None]
        if not vals:
            return None
        return float(sum(vals))

    out = []
    for v in variants:
        rows = by_variant.get(v["id"], [])
        clicks = agg(rows, "clicks")
        warnings = []
        if not rows:
            warnings.append("No metrics recorded for this variant yet - every figure is UNKNOWN.")
        elif clicks is None:
            warnings.append("No clicks figure is available; sample size is UNKNOWN.")
        elif clicks < 25:
            warnings.append(f"Small sample: {int(clicks)} clicks. Treat any difference as noise.")
        out.append({
            "variant": v,
            "metrics_count": len(rows),
            "totals": {
                "impressions": agg(rows, "impressions") if agg(rows, "impressions") is not None else "UNKNOWN",
                "clicks": clicks if clicks is not None else "UNKNOWN",
                "orders": agg(rows, "orders") if agg(rows, "orders") is not None else "UNKNOWN",
                "spend": agg(rows, "spend") if agg(rows, "spend") is not None else "UNKNOWN",
                "sales": agg(rows, "sales") if agg(rows, "sales") is not None else "UNKNOWN",
            },
            "warnings": warnings,
            "sources": sorted({r.get("source") for r in rows}),
        })
    return {
        "comparison": out,
        "note": "Metrics are user-entered or file-imported only. This view makes NO causation claim: it cannot attribute a performance difference to a creative.",
        "attribution_gap": "Amazon search-term reports aggregate at campaign/ad-group level and carry no creative identifier, so creative-level attribution cannot be derived from them.",
    }


@router.get("/variants/{vid}")
def get_variant(vid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    variant = db.design_studio.variants.get_by_id(vid, account_id=acct)
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    return {"variant": variant, "metrics": db.design_studio.variants.metrics_for_variant(acct, vid)}


@router.patch("/variants/{vid}")
def patch_variant(vid: str, body: VariantPatch, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    if not db.design_studio.variants.update(vid, body.model_dump(exclude_unset=True), account_id=acct):
        raise HTTPException(status_code=404, detail="Variant not found")
    return {"variant": db.design_studio.variants.get_by_id(vid, account_id=acct)}


@router.delete("/variants/{vid}")
def delete_variant(vid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    if not db.design_studio.variants.delete(vid, account_id=acct):
        raise HTTPException(status_code=404, detail="Variant not found")
    return {"deleted": True}


@router.post("/variants/{vid}/metrics")
def add_variant_metric(vid: str, body: VariantMetricIn, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    if not db.design_studio.variants.get_by_id(vid, account_id=acct):
        raise HTTPException(status_code=404, detail="Variant not found")
    if body.source not in ("user", "file"):
        raise HTTPException(status_code=400, detail={"code": "invalid_source", "message": "source must be user or file"})
    rec = {**body.model_dump(), "account_id": acct, "variant_id": vid}
    mid = db.design_studio.variants.add_metric(rec)
    return {"id": mid, "metrics": db.design_studio.variants.metrics_for_variant(acct, vid)}


@router.post("/variants/metrics/import")
def import_variant_metrics(body: VariantMetricsImportIn, acct: str = Depends(studio_account)):
    """Attach performance metrics from a CSV/JSON file to EXISTING variants.

    Rows are matched by variant id or exact name. A row that matches nothing is
    reported back as unmatched - it is never turned into a new variant.
    """
    from design_studio_imports import ImportParseError, parse_variant_metrics
    db = get_northstar_db()
    try:
        parsed = parse_variant_metrics(content=body.content, filename=body.filename)
    except ImportParseError as exc:
        raise _parse_error(exc)

    variants = db.design_studio.variants.list_for_account(acct, limit=1000)
    by_id = {v["id"]: v for v in variants}
    by_name = {v["name"]: v for v in variants}
    added = 0
    unmatched: List[Dict[str, Any]] = []
    for row in parsed["rows"]:
        target = by_id.get(row["variant"]) or by_name.get(row["variant"])
        if not target:
            unmatched.append({"variant": row["variant"], "reason": "no variant with this id or name"})
            continue
        db.design_studio.variants.add_metric({
            "account_id": acct,
            "variant_id": target["id"],
            "source": "file",
            "observed_from": row.get("observed_from"),
            "observed_to": row.get("observed_to"),
            "impressions": row.get("impressions"),
            "clicks": row.get("clicks"),
            "orders": row.get("orders"),
            "spend": row.get("spend"),
            "sales": row.get("sales"),
            "note": f"Imported from {body.filename or 'file'}",
        })
        added += 1
    return {
        "rows_added": added,
        "unmatched": unmatched,
        "skipped_rows": parsed["skipped_rows"],
        "note": "Only existing variants receive metrics. An unmatched row is reported, never invented.",
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
