"""Design Studio API — backend store for projects, assets and jobs.

Phase 0 exposes honest CRUD for the merged studio. No provider calls; every
potentially paid action is recorded as a queued job and waits for explicit run.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
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


@router.post("/migrate")
def migrate_legacy(body: MigrateIn, user: Dict[str, Any] = Depends(get_current_user)):
    """Import browser-local records into the tenant's backend store.

    Idempotent per account: a record carrying a `legacyKey` that is already
    stored is reported as skipped, never re-created. Unknown sections are
    rejected rather than silently filed under a guess.
    """
    db = get_northstar_db()
    acct = _account_id(user)
    created = {'projects': 0, 'assets': 0, 'jobs': 0}
    skipped = {'projects': 0, 'assets': 0, 'jobs': 0}
    errors: List[Dict[str, Any]] = []

    def legacy_key_of(meta: Any) -> Optional[str]:
        if isinstance(meta, dict):
            v = meta.get('legacyKey')
            return str(v) if v else None
        return None

    # Existing legacy keys for this account, so the import is idempotent.
    existing = set()
    for p in db.design_studio.projects.list_by_section(account_id=acct, limit=5000):
        k = legacy_key_of(p.get('metadata'))
        if k:
            existing.add('project:' + k)

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
            pid = db.design_studio.projects.create({
                'account_id': acct,
                'name': raw.get('name') or 'Imported draft',
                'section': section,
                'asin': raw.get('asin'),
                'brand': raw.get('brand'),
                'brief': raw.get('brief'),
                'state': raw.get('state') or 'draft',
                'metadata': {**meta, 'importedFrom': 'localStorage', 'importedAt': datetime.now(timezone.utc).isoformat()},
            })
            if key:
                existing.add('project:' + key)
            created['projects'] += 1
            # Remember the new id so assets/jobs can be re-pointed by legacy key.
            if key:
                _LEGACY_PROJECT_MAP[(acct, key)] = pid
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            errors.append({'kind': 'project', 'name': raw.get('name'), 'error': f'{exc.__class__.__name__}: {exc}'})

    # Assets and jobs resolve their project by legacy key where one was given.
    for kind, items in (('assets', body.assets), ('jobs', body.jobs)):
        store = getattr(db.design_studio, kind)
        for raw in items:
            try:
                meta = dict(raw.get('metadata') or {})
                key = legacy_key_of(meta)
                if key and (kind + ':' + key) in existing:
                    skipped[kind] += 1
                    continue
                payload = {k: v for k, v in raw.items() if k not in ('id', 'account_id')}
                payload['account_id'] = acct
                legacy_project = raw.get('legacyProjectKey')
                if legacy_project:
                    payload['project_id'] = _LEGACY_PROJECT_MAP.get((acct, str(legacy_project))) or raw.get('project_id')
                payload['metadata'] = {**meta, 'importedFrom': 'localStorage', 'importedAt': datetime.now(timezone.utc).isoformat()}
                if kind == 'assets':
                    store.create({**payload, 'account_id': acct})
                else:
                    payload.setdefault('job_type', 'generate')
                    store.create({**payload, 'account_id': acct})
                if key:
                    existing.add(kind + ':' + key)
                created[kind] += 1
            except Exception as exc:  # noqa: BLE001
                errors.append({'kind': kind, 'name': raw.get('name'), 'error': f'{exc.__class__.__name__}: {exc}'})

    return {
        'ok': not errors,
        'created': created,
        'skipped': skipped,
        'errors': errors,
        'note': 'Idempotent per account: re-running reports skipped, never duplicates.',
    }


# Maps (account, legacy project key) -> new project id for the current process.
# Only used to re-point assets/jobs inside a single migrate call.
_LEGACY_PROJECT_MAP: Dict[tuple, str] = {}


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
