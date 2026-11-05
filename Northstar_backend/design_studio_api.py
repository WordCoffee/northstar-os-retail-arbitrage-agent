"""Design Studio API — backend store for projects, assets and jobs.

Phase 0 exposes honest CRUD for the merged studio. No provider calls; every
potentially paid action is recorded as a queued job and waits for explicit run.

Phase 7 (D10): EVERY route resolves a strict, organization-scoped session
(`studio_account`) — the cookie/Bearer session the SPA actually carries. Before
this, the legacy routes used `get_current_user`, which has no cookie awareness,
so every UI caller collapsed into one shared "default" bucket. Anonymous
callers are refused with 401. `migrate_ds_identity.py` moves pre-existing
shared-bucket records to their owning organization when that owner is
unambiguous and quarantines the rest.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

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
def create_project(body: ProjectIn, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    pid = db.design_studio.projects.create({**body.model_dump(), "account_id": acct})
    return {"id": pid, "project": db.design_studio.projects.get_by_id(pid, account_id=acct)}


@router.get("/projects")
def list_projects(section: Optional[str] = None, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    return {"projects": db.design_studio.projects.list_by_section(section=section, account_id=acct)}


@router.get("/projects/{pid}")
def get_project(pid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    project = db.design_studio.projects.get_by_id(pid, account_id=acct)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"project": project}


@router.patch("/projects/{pid}")
def patch_project(pid: str, body: ProjectPatch, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    updated = db.design_studio.projects.update(pid, body.model_dump(exclude_unset=True), account_id=acct)
    if not updated:
        # A project owned by another account is a 404, never a 403: the caller
        # must not be able to distinguish "not yours" from "does not exist".
        raise HTTPException(status_code=404, detail="Project not found")
    return {"project": db.design_studio.projects.get_by_id(pid, account_id=acct)}


@router.delete("/projects/{pid}")
def delete_project(pid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    deleted = db.design_studio.projects.delete(pid, account_id=acct)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"deleted": True}


# ── Assets ─────────────────────────────────────────────────────────────────

@router.post("/assets")
def create_asset(body: AssetIn, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    aid = db.design_studio.assets.create({**body.model_dump(), "account_id": acct})
    return {"id": aid, "asset": db.design_studio.assets.get_by_id(aid, account_id=acct)}


@router.get("/assets")
def list_assets(project_id: Optional[str] = None, asset_type: Optional[str] = None, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    return {"assets": db.design_studio.assets.list_by_project(project_id=project_id, asset_type=asset_type, account_id=acct)}


@router.get("/assets/{aid}")
def get_asset(aid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    asset = db.design_studio.assets.get_by_id(aid, account_id=acct)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"asset": asset}


@router.delete("/assets/{aid}")
def delete_asset(aid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    deleted = db.design_studio.assets.delete(aid, account_id=acct)
    if not deleted:
        raise HTTPException(status_code=404, detail="Asset not found")
    return {"deleted": True}


# ── Jobs ───────────────────────────────────────────────────────────────────

@router.post("/jobs")
def create_job(body: JobIn, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    jid = db.design_studio.jobs.create({**body.model_dump(), "account_id": acct})
    return {"id": jid, "job": db.design_studio.jobs.get_by_id(jid, account_id=acct)}


@router.get("/jobs")
def list_jobs(project_id: Optional[str] = None, status: Optional[str] = None, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    return {"jobs": db.design_studio.jobs.list_by_project(project_id=project_id, status=status, account_id=acct)}


@router.get("/jobs/{jid}")
def get_job(jid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    job = db.design_studio.jobs.get_by_id(jid, account_id=acct)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": job}


@router.patch("/jobs/{jid}")
def patch_job(jid: str, body: JobPatch, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    updated = db.design_studio.jobs.update(jid, body.model_dump(exclude_unset=True), account_id=acct)
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job": db.design_studio.jobs.get_by_id(jid, account_id=acct)}


@router.delete("/jobs/{jid}")
def delete_job(jid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    deleted = db.design_studio.jobs.delete(jid, account_id=acct)
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
def migrate_legacy(body: MigrateIn, acct: str = Depends(studio_account)):
    """Import browser-local records into the tenant's backend store.

    Idempotent per account across projects, assets AND jobs: a record carrying a
    `legacyKey` that is already stored is reported as skipped, never
    re-created. Unknown sections are rejected rather than silently filed under a
    guess, and legacy keys the schema does not model are preserved under
    ``metadata.legacyFields`` instead of breaking the insert.
    """
    db = get_northstar_db()
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
    acct: str = Depends(studio_account),
):
    """Case-insensitive substring search over the caller's own projects,
    assets and jobs. Scoped to the account at the query, not filtered after."""
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
def export_manifest(pid: str, acct: str = Depends(studio_account)):
    """The flat-file image manifest for one project.

    Refuses a project owned by another account with a 404, exactly like a
    missing one. Deliberately returns the documented column names so the
    operator can map them straight into a feed, and never invents a URL: a slot
    with no asset is emitted as null rather than as a placeholder path.
    """
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
def create_recheck(body: RecheckIn, acct: str = Depends(studio_account)):
    """Record one dated verification of a live asset.

    The verdict is supplied by the caller and stores what the reader actually
    returned. A failed check is stored as a failure; this endpoint never
    upgrades a verdict.
    """
    db = get_northstar_db()
    rec = body.model_dump()
    rec["account_id"] = acct
    rid = db.design_studio.rechecks.create(rec)
    return {"id": rid, "recheck": db.design_studio.rechecks.get_by_id(rid, account_id=acct)}


@router.get("/rechecks")
def list_rechecks(
    asset_id: Optional[str] = None,
    limit: int = Query(default=200, le=1000),
    acct: str = Depends(studio_account),
):
    db = get_northstar_db()
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
def get_recheck(rid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    rec = db.design_studio.rechecks.get_by_id(rid, account_id=acct)
    if not rec:
        raise HTTPException(status_code=404, detail="Re-check not found")
    return {"recheck": rec}


@router.delete("/rechecks/{rid}")
def delete_recheck(rid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    if not db.design_studio.rechecks.delete(rid, account_id=acct):
        raise HTTPException(status_code=404, detail="Re-check not found")
    return {"deleted": True}


class RecheckMigrateIn(BaseModel):
    entries: List[Dict[str, Any]] = Field(default_factory=list)


@router.post("/rechecks/migrate")
def migrate_rechecks(body: RecheckMigrateIn, acct: str = Depends(studio_account)):
    """Import browser-local re-check entries, idempotently.

    Idempotency is enforced by a UNIQUE index on (account_id, legacy_key), so a
    second run reports `skipped` rather than duplicating. An entry with no
    legacy key is always created, because there is no way to tell it apart from
    a genuinely new check.
    """
    db = get_northstar_db()
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
                "asin_click_share", "row_from", "row_to", "extras")},
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
    from design_studio_imports import KINDS
    db = get_northstar_db()
    rows = db.design_studio.imports.list_for_account(acct, kind=kind)
    kinds: Dict[str, Any] = {}
    for k in KINDS:
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


@router.get("/brand-voice")
def brand_voice(acct: str = Depends(studio_account)):
    """The latest imported brand-voice file, as fields with provenance.

    UNKNOWN is a real answer: with no import, `available` is false and no field
    is invented. The values are the operator's own wording from their file.
    """
    from design_studio_imports import BRAND_VOICE_FIELDS, KIND_BRAND_VOICE
    db = get_northstar_db()
    latest = next((r for r in db.design_studio.imports.list_for_account(acct, kind=KIND_BRAND_VOICE) if r["kind"] == KIND_BRAND_VOICE), None)
    if not latest:
        return {
            "available": False,
            "fields": {},
            "missing_fields": list(BRAND_VOICE_FIELDS),
            "note": "No brand-voice file has been imported for this account.",
        }
    rows = db.design_studio.search_terms.list_for_account(acct, kind=KIND_BRAND_VOICE, import_id=latest["id"], limit=100)
    fields: Dict[str, Any] = {}
    extras: Dict[str, Any] = {}
    for r in rows:
        val = (r.get("extras") or {}).get("value")
        if r.get("term") == "_extra":
            extras = r.get("extras") or {}
        elif val is not None:
            fields[r["term"]] = val
    return {
        "available": True,
        "fields": fields,
        "extras": extras,
        "missing_fields": [f for f in BRAND_VOICE_FIELDS if f not in fields],
        "import": latest,
        "banner": _banner(latest),
        "note": "Imported brand voice: the operator's own wording, archived with its source label and observed date.",
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
    # The default view is the metric reports; brand-voice and keyword rows are
    # not search terms and only appear when their kind is asked for explicitly.
    if not kind:
        rows = [r for r in rows if r.get("kind") in ("sp_search_terms", "brand_analytics_sqp")]
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
    voice_source: Optional[Dict[str, Any]] = None
    keywords_source: Optional[Dict[str, Any]] = None


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
    brief = build_brief(terms=rows[: body.limit], brand=body.brand, keywords=body.keywords,
                        voice_source=body.voice_source, keywords_source=body.keywords_source)
    brief["source_rows"] = len(rows)
    return brief


class BriefAssetsIn(BriefIn):
    project_id: Optional[str] = None
    variants_limit: int = Field(default=3, ge=1, le=10)
    create: bool = True


@router.post("/terms/brief/assets")
def terms_brief_assets(body: BriefAssetsIn, acct: str = Depends(studio_account)):
    """Turn a brief into copy variants + on-image text (TEMPLATES ONLY).

    No generation, no provider call. With create=true (the default) each
    template becomes a variant row tied to the brief reference, so a later
    results import can match it by id or exact name.
    """
    from design_studio_imports import brief_to_assets, build_brief
    db = get_northstar_db()
    rows = db.design_studio.search_terms.list_for_account(acct, q=body.q, limit=1000)
    if body.term_ids:
        wanted = set(body.term_ids)
        rows = [r for r in rows if r.get("id") in wanted]
    brief = build_brief(terms=rows[: body.limit], brand=body.brand, keywords=body.keywords,
                        voice_source=body.voice_source, keywords_source=body.keywords_source)
    brief["source_rows"] = len(rows)
    assets = brief_to_assets(brief=brief, brand=body.brand, limit=body.variants_limit)
    created: List[Dict[str, Any]] = []
    for v in assets["variants"]:
        if not body.create:
            created.append(v)
            continue
        vid = db.design_studio.variants.create({
            "account_id": acct,
            "project_id": body.project_id,
            "name": v["name"],
            "format": v["format"],
            "status": v["status"],
            "notes": json.dumps({
                "template_only": True,
                "brief_ref": v["brief_ref"],
                "copy": v["copy"],
                "on_image_text": v["on_image_text"],
            }, ensure_ascii=False),
        })
        created.append({**v, "id": vid})
    return {
        "brief": brief,
        "variants": created,
        "count": len(created),
        "created": bool(body.create),
        "template_only": True,
        "note": assets["note"],
    }


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

    from design_studio_imports import confidence_label
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
            "confidence": confidence_label(clicks),
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


@router.get("/variants/export")
def export_variants(acct: str = Depends(studio_account)):
    """Results CSV for the performance loop (Phase 7 item 7).

    One row per variant with its aggregated metrics, sample size, confidence
    band, sources and the no-causation caveat. A NULL metric is an EMPTY cell,
    never 0.
    """
    import csv as _csv
    import io as _io
    db = get_northstar_db()
    payload = compare_variants(acct=acct)
    buf = _io.StringIO()
    writer = _csv.writer(buf)
    writer.writerow([
        "variant", "status", "format", "asset_id", "metrics_rows",
        "impressions", "clicks", "orders", "spend", "sales",
        "sample", "confidence_note", "observed_from", "observed_to", "sources", "caveat",
    ])
    for row in payload["comparison"]:
        v = row["variant"]
        metrics = db.design_studio.variants.metrics_for_variant(acct, v["id"])
        obs_from = min([m["observed_from"] for m in metrics if m.get("observed_from")] or [None]) if metrics else None
        obs_to = max([m["observed_to"] for m in metrics if m.get("observed_to")] or [None]) if metrics else None
        conf = row.get("confidence") or {}
        # A metric with no rows is UNKNOWN in the payload and an EMPTY cell here.
        cell = lambda x: "" if x in (None, "UNKNOWN") else x  # noqa: E731
        writer.writerow([
            v.get("name"), v.get("status"), v.get("format"), v.get("asset_id") or "",
            row["metrics_count"],
            cell(row["totals"]["impressions"]), cell(row["totals"]["clicks"]),
            cell(row["totals"]["orders"]), cell(row["totals"]["spend"]), cell(row["totals"]["sales"]),
            conf.get("sample") or "UNKNOWN", conf.get("note") or "",
            obs_from or "", obs_to or "",
            ",".join(row.get("sources") or []) or "none",
            "NO CAUSATION CLAIM: imported metrics cannot be attributed to a creative (Amazon reports carry no creative identifier).",
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="design-studio-variant-results.csv"'},
    )


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


# ── Listing records (Phase 8 item 3) ──────────────────────────────────────
# The tenant-store home for the listing context. The one-shot migration from
# the browser-local ListingForge records is idempotent via a per-account legacy
# key: a second run reports `skipped`, never a duplicate.

class ListingRecordIn(BaseModel):
    asin: Optional[str] = None
    title: Optional[str] = None
    bullets: Optional[List[str]] = None
    backend_terms: Optional[str] = None
    description: Optional[str] = None
    images: Optional[List[Any]] = None
    aplus_modules: Optional[List[str]] = None
    source: Optional[str] = None
    observed_at: Optional[str] = None
    legacy_key: Optional[str] = None


class ListingMigrateIn(BaseModel):
    records: List[ListingRecordIn] = Field(default_factory=list)


@router.post("/listing-records/migrate")
def migrate_listing_records(body: ListingMigrateIn, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    created = 0
    skipped = 0
    errors: List[Dict[str, Any]] = []
    seen = db.design_studio.listing_records.existing_legacy_keys(acct)
    for raw in body.records:
        rec = raw.model_dump()
        key = rec.get("legacy_key")
        if key and key in seen:
            skipped += 1
            continue
        try:
            db.design_studio.listing_records.create({**rec, "account_id": acct})
            if key:
                seen.add(key)
            created += 1
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            errors.append({"asin": rec.get("asin"), "error": f"{exc.__class__.__name__}: {exc}"})
    return {
        "ok": not errors,
        "created": created,
        "skipped": skipped,
        "errors": errors,
        "note": "Idempotent per account via the legacy key: re-running reports skipped, never duplicates.",
    }


@router.get("/listing-records")
def list_listing_records(acct: str = Depends(studio_account)):
    db = get_northstar_db()
    rows = db.design_studio.listing_records.list_for_account(acct)
    return {
        "records": rows,
        "counts": {"total": len(rows)},
        "note": "Scoped to the calling account. Migrated from the browser-local ListingForge records; the server copy is the primary source.",
    }


class ListingRecordPatch(BaseModel):
    asin: Optional[str] = None
    title: Optional[str] = None
    bullets: Optional[List[str]] = None
    backend_terms: Optional[str] = None
    description: Optional[str] = None
    images: Optional[List[Any]] = None
    aplus_modules: Optional[List[str]] = None
    source: Optional[str] = None
    observed_at: Optional[str] = None


@router.post("/listing-records")
def create_listing_record(body: ListingRecordIn, acct: str = Depends(studio_account)):
    """Create ONE tenant-scoped listing record (2026-10-16). The ListingForge
    editor saves here; nothing leaves the machine."""
    db = get_northstar_db()
    rid = db.design_studio.listing_records.create({**body.model_dump(exclude_unset=True), "account_id": acct})
    return {"id": rid, "record": db.design_studio.listing_records.get_by_id(rid, account_id=acct)}


@router.patch("/listing-records/{rid}")
def patch_listing_record(rid: str, body: ListingRecordPatch, acct: str = Depends(studio_account)):
    """Patch ONE record (editor saves). 404 when the row is not the caller's."""
    db = get_northstar_db()
    if not db.design_studio.listing_records.update(rid, body.model_dump(exclude_unset=True), account_id=acct):
        raise HTTPException(status_code=404, detail="Listing record not found")
    return {"record": db.design_studio.listing_records.get_by_id(rid, account_id=acct)}


@router.get("/listing-records/{rid}")
def get_listing_record(rid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    rec = db.design_studio.listing_records.get_by_id(rid, account_id=acct)
    if not rec:
        raise HTTPException(status_code=404, detail="Listing record not found")
    return {"record": rec}


@router.delete("/listing-records/{rid}")
def delete_listing_record(rid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    if not db.design_studio.listing_records.delete(rid, account_id=acct):
        raise HTTPException(status_code=404, detail="Listing record not found")
    return {"deleted": True}


# ── Master-brain read-only context (Phase 9 item 2) ───────────────────────
# One tenant-scoped, read-only bundle of the Studio's imported evidence, for
# the other rooms (ListingForge, AdPilot, SocialPulse) to render as panels.
# Pure local-store reads: NO provider call exists in this path.

@router.get("/master-brain-context")
def master_brain_context(acct: str = Depends(studio_account)):
    from design_studio_imports import (KIND_BRAND_VOICE, KIND_KEYWORDS,
                                       KIND_SP_SEARCH_TERMS, KIND_BRAND_ANALYTICS_SQP)
    db = get_northstar_db()

    def latest_import(kind):
        rows = [r for r in db.design_studio.imports.list_for_account(acct, kind=kind)]
        return rows[0] if rows else None

    # Brand voice.
    bv_import = latest_import(KIND_BRAND_VOICE)
    brand_voice = {"available": False, "fields": {}, "source": "imported brand-voice file", "observed_at": None}
    if bv_import:
        rows = db.design_studio.search_terms.list_for_account(acct, kind=KIND_BRAND_VOICE, import_id=bv_import["id"], limit=50)
        fields = {}
        for r in rows:
            val = (r.get("extras") or {}).get("value")
            if r.get("term") != "_extra" and val is not None:
                fields[r["term"]] = val
        brand_voice = {
            "available": bool(fields),
            "fields": fields,
            "source": "imported brand-voice file",
            "source_label": bv_import.get("source_label"),
            "observed_at": bv_import.get("observed_from") or bv_import.get("imported_at"),
            "limits": ["A file the operator supplied; a snapshot, not a live read."],
        }

    # Keyword list.
    kw_import = latest_import(KIND_KEYWORDS)
    keywords = {"available": False, "items": [], "source": "imported keyword list", "observed_at": None}
    if kw_import:
        rows = db.design_studio.search_terms.list_for_account(acct, kind=KIND_KEYWORDS, import_id=kw_import["id"], limit=200)
        keywords = {
            "available": bool(rows),
            "items": [{"term": r.get("term"), "volume": (r.get("extras") or {}).get("volume")} for r in rows],
            "source": "imported keyword list",
            "source_label": kw_import.get("source_label"),
            "observed_at": kw_import.get("imported_at"),
            "limits": ["A snapshot list; a missing volume is UNKNOWN, never 0."],
        }

    # Search-term evidence (metric reports only; top by clicks).
    sp = db.design_studio.search_terms.list_for_account(acct, kind=KIND_SP_SEARCH_TERMS, limit=25)
    ba = db.design_studio.search_terms.list_for_account(acct, kind=KIND_BRAND_ANALYTICS_SQP, limit=25)
    terms = sp + ba
    search_terms = {
        "available": bool(terms),
        "items": [{
            "term": t.get("term"), "kind": t.get("kind"),
            "clicks": t.get("clicks") if t.get("clicks") is not None else "UNKNOWN",
            "impressions": t.get("impressions") if t.get("impressions") is not None else "UNKNOWN",
            "observed_from": t.get("row_from"), "observed_to": t.get("row_to"),
        } for t in terms],
        "source": "imported search-term reports",
        "limits": [
            "Click-only bias: a term appears only after at least one click.",
            "65-day lookback ceiling; at most 31 days per reporting-API request.",
        ],
        "bias": "Click-only report: impressions without a click are absent.",
    }

    # Listing records.
    lr = db.design_studio.listing_records.list_for_account(acct, limit=50)
    listing_records = {
        "available": bool(lr),
        "items": [{"id": r["id"], "asin": r.get("asin"), "title": r.get("title"),
                   "observed_at": r.get("observed_at")} for r in lr],
        "source": "tenant listing records",
        "limits": ["Migrated from browser-local records; a local record, not a marketplace read."],
    }

    return {
        "read_only": True,
        "brand_voice": brand_voice,
        "keywords": keywords,
        "search_terms": search_terms,
        "listing_records": listing_records,
        "note": "Read-only Studio evidence for this organization. Pure local-store reads: no provider is contacted and nothing here is live marketplace data. Missing sections are UNKNOWN, never zero.",
    }


# ── Amazon files: file-only workflow (2026-10-11) ─────────────────────────
# The seller downloads files from Amazon, uploads them here, approves proposed
# changes row by row, and receives a NEW change file to upload manually.
# Nothing in this section talks to Amazon: the parsers/writers are pure and the
# linkage guard test proves no API path exists.

class AmazonFileIn(BaseModel):
    filename: str = Field(..., min_length=1, max_length=200)
    content_b64: str
    downloaded_at: Optional[str] = None


class ProposalRequestIn(BaseModel):
    changes: List[Dict[str, Any]] = Field(default_factory=list)
    spend_limit_cents: Optional[int] = None


class ProposalDecisionIn(BaseModel):
    second_confirmation: bool = False


class WriteRequestIn(BaseModel):
    format: Optional[str] = None  # xlsx | tsv; defaults by file kind


class APlusPackIn(BaseModel):
    assets: List[Dict[str, Any]] = Field(default_factory=list)
    copy: Dict[str, Any] = Field(default_factory=dict)


class ReportMatchIn(BaseModel):
    filename: str = Field(..., min_length=1, max_length=200)
    content_b64: str
    change_file_id: str = Field(..., min_length=1)
    downloaded_at: Optional[str] = None


class CorrectedChangeIn(BaseModel):
    corrections: List[Dict[str, Any]] = Field(default_factory=list)
    format: Optional[str] = None


class CompareIn(BaseModel):
    after_upload_id: str = Field(..., min_length=1)
    before_from: Optional[str] = None
    before_to: Optional[str] = None
    after_from: Optional[str] = None
    after_to: Optional[str] = None


def _decode_b64(content_b64: str) -> bytes:
    import base64 as _b64
    try:
        return _b64.b64decode(content_b64, validate=True)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail={"code": "invalid_base64", "message": f"the file content could not be decoded: {exc}"})


def _upload_detail(u: Dict[str, Any], *, include_rows: int = 0) -> Dict[str, Any]:
    parsed = u.get("parsed") or {}
    sheets = []
    for s in parsed.get("sheets", []):
        sheets.append({
            "name": s.get("name"),
            "kind": s.get("kind"),
            "headers": s.get("headers"),
            "row_count": len(s.get("rows") or []),
            "mapped": s.get("mapped"),
            "sample_rows": (s.get("normalized") or [])[:include_rows] if include_rows else [],
        })
    return {
        "id": u["id"],
        "filename": u["filename"],
        "kind": u["kind"],
        "checksum": u["checksum"],
        "size_bytes": u.get("size_bytes"),
        "row_count": u.get("row_count"),
        "observed_from": u.get("observed_from"),
        "observed_to": u.get("observed_to"),
        "downloaded_at": u.get("downloaded_at"),
        "uploaded_at": u.get("uploaded_at"),
        "columns_found": u.get("columns_found") or [],
        "missing_columns": u.get("missing_columns") or [],
        "notes": u.get("notes") or [],
        "detection": u.get("detection"),
        "sheets": sheets,
        "note": "Archived read-only with its checksum. The original is never modified; change files are new files.",
    }


@router.post("/amazon-files/upload")
def amazon_file_upload(body: AmazonFileIn, acct: str = Depends(studio_account)):
    from amazon_file_parsers import ParseError, parse_upload
    db = get_northstar_db()
    content = _decode_b64(body.content_b64)
    try:
        parsed = parse_upload(body.filename, content)
    except ParseError as exc:
        raise _parse_error(exc)
    import base64 as _b64
    uid = db.design_studio.amazon_files.create_upload({
        "account_id": acct,
        "filename": body.filename,
        "kind": parsed["kind"],
        "checksum": parsed["checksum"],
        "content_b64": _b64.b64encode(content).decode("ascii"),
        "size_bytes": len(content),
        "row_count": parsed["row_count"],
        "observed_from": parsed["observed_from"],
        "observed_to": parsed["observed_to"],
        "downloaded_at": body.downloaded_at,
        "columns_found": parsed["columns_found"],
        "missing_columns": parsed["missing_columns"],
        "notes": parsed["notes"],
        "detection": parsed["detection"],
        "parsed": parsed,
    })
    stored = db.design_studio.amazon_files.get_upload(uid, account_id=acct)
    return {"upload": _upload_detail(stored or {}), "state": "imported",
            "note": "Read-only archive: the uploaded file is stored with its checksum and never modified."}


@router.get("/amazon-files")
def amazon_file_list(acct: str = Depends(studio_account)):
    db = get_northstar_db()
    rows = db.design_studio.amazon_files.list_uploads(acct)
    return {"uploads": [_upload_detail(u) for u in rows],
            "note": "Scoped to the calling account. Files are read-only archives."}


@router.get("/amazon-files/{uid}")
def amazon_file_detail(uid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    u = db.design_studio.amazon_files.get_upload(uid, account_id=acct)
    if not u:
        raise HTTPException(status_code=404, detail="Upload not found")
    return {"upload": _upload_detail(u, include_rows=5)}


@router.get("/amazon-files/{uid}/rows")
def amazon_file_rows(uid: str, sheet: Optional[str] = None, limit: int = Query(default=200, le=1000),
                     offset: int = Query(default=0, ge=0), acct: str = Depends(studio_account)):
    db = get_northstar_db()
    u = db.design_studio.amazon_files.get_upload(uid, account_id=acct)
    if not u:
        raise HTTPException(status_code=404, detail="Upload not found")
    parsed = u.get("parsed") or {}
    out: List[Dict[str, Any]] = []
    for s in parsed.get("sheets", []):
        if sheet and s.get("name") != sheet:
            continue
        rows = s.get("normalized") or []
        out.extend(rows[offset: offset + limit])
    return {"rows": out, "count": len(out),
            "note": "Normalized rows as read. A value the file did not carry is None (UNKNOWN), never zero."}


@router.delete("/amazon-files/{uid}")
def amazon_file_delete(uid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    if not db.design_studio.amazon_files.delete_upload(uid, account_id=acct):
        raise HTTPException(status_code=404, detail="Upload not found")
    return {"deleted": True}


@router.post("/amazon-files/{uid}/proposals")
def amazon_file_proposals(uid: str, body: ProposalRequestIn, acct: str = Depends(studio_account)):
    from amazon_change_files import build_proposals
    db = get_northstar_db()
    u = db.design_studio.amazon_files.get_upload(uid, account_id=acct)
    if not u:
        raise HTTPException(status_code=404, detail="Upload not found")
    parsed = u.get("parsed") or {}
    if u["kind"] in ("ads_error_report", "listing_processing_report"):
        raise HTTPException(status_code=422, detail={"code": "report_has_no_proposals",
            "message": "this upload is a processing/error report; use the report-match endpoint to map its rows "
                       "back to a change file. Reports never produce new proposals."})
    if not parsed.get("sheets"):
        raise HTTPException(status_code=422, detail={"code": "unparseable_upload",
            "message": "this upload has no parsed rows (unreadable, unknown or legacy .xls); nothing to propose against"})
    meta = {
        "upload_id": uid, "filename": u["filename"], "checksum": u["checksum"],
        "downloaded_at": u.get("downloaded_at"),
        "spend_limit_cents": body.spend_limit_cents,
        "now": datetime.now(timezone.utc).isoformat(),
    }
    proposals = build_proposals(parsed, body.changes, meta)
    stored = []
    for p in proposals:
        pid = db.design_studio.amazon_files.add_proposal({"account_id": acct, "upload_id": uid, "payload": p})
        p["id"] = pid
        stored.append(p)
    return {"proposals": stored, "count": len(stored),
            "note": "Blocked rows can never be approved. A spend-limit row needs a second confirmation. Title changes carry date-sensitive FLAGS only - nothing is edited for you."}


@router.get("/amazon-files/{uid}/proposals")
def amazon_file_proposals_list(uid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    rows = db.design_studio.amazon_files.list_proposals(acct, upload_id=uid)
    return {"proposals": rows, "count": len(rows)}


@router.post("/amazon-files/proposals/{pid}/approve")
def amazon_file_approve(pid: str, body: ProposalDecisionIn, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    rec = db.design_studio.amazon_files.get_proposal(pid, account_id=acct)
    if not rec:
        raise HTTPException(status_code=404, detail="Proposal not found")
    if rec.get("blocks"):
        raise HTTPException(status_code=409, detail={"code": "proposal_blocked",
            "message": "this row is blocked: " + "; ".join(rec["blocks"])})
    if rec.get("requires_second_confirmation") and not body.second_confirmation:
        raise HTTPException(status_code=409, detail={"code": "second_confirmation_required",
            "message": "approving this row exceeds your spend limit; confirm again to approve it"})
    db.design_studio.amazon_files.decide_proposal(pid, acct, "approved")
    return {"proposal": db.design_studio.amazon_files.get_proposal(pid, account_id=acct)}


@router.post("/amazon-files/proposals/{pid}/reject")
def amazon_file_reject(pid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    rec = db.design_studio.amazon_files.get_proposal(pid, account_id=acct)
    if not rec:
        raise HTTPException(status_code=404, detail="Proposal not found")
    db.design_studio.amazon_files.decide_proposal(pid, acct, "rejected")
    return {"proposal": db.design_studio.amazon_files.get_proposal(pid, account_id=acct)}


@router.post("/amazon-files/{uid}/write")
def amazon_file_write(uid: str, body: WriteRequestIn, acct: str = Depends(studio_account)):
    from amazon_change_files import validate_roundtrip
    from amazon_file_parsers import parse_upload
    from amazon_file_writers import write_delta
    import base64 as _b64
    db = get_northstar_db()
    u = db.design_studio.amazon_files.get_upload(uid, account_id=acct)
    if not u:
        raise HTTPException(status_code=404, detail="Upload not found")
    parsed = u.get("parsed") or {}
    if u["kind"] == "aplus_asin_list":
        raise HTTPException(status_code=422, detail={"code": "aplus_has_no_module_file",
            "message": "A+ output is an asset pack, not an uploadable module file. Use the A+ pack endpoint."})
    if u["kind"] in ("ads_error_report", "listing_processing_report"):
        raise HTTPException(status_code=422, detail={"code": "report_has_no_change_file",
            "message": "this upload is a processing/error report; a corrected file is written from a change file "
                       "via the correct endpoint, not from the report itself."})
    approved = [r for r in db.design_studio.amazon_files.list_proposals(acct, upload_id=uid) if r.get("status") == "approved"]
    if not approved:
        raise HTTPException(status_code=422, detail={"code": "nothing_approved",
            "message": "no approved proposals: nothing will be written (a no-op change file is available for the round-trip test only)"})
    approved_payloads = approved  # the serializer returns the flat proposal shape
    fmt = body.format or ("tsv" if u["kind"] == "listing_template" else "xlsx")
    try:
        delta = write_delta(parsed.get("sheets", []), approved_payloads, format=fmt)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "write_refused", "message": str(exc)})
    written_parsed = parse_upload(f"change.{fmt}", delta["content"])
    rt = validate_roundtrip(parsed, written_parsed, approved_payloads,
                            source_content=_b64.b64decode(u["content_b64"]), written_content=delta["content"])
    version = db.design_studio.amazon_files.next_version(acct, uid)
    base = u["filename"].rsplit(".", 1)[0]
    filename = f"{base}-change-v{version}.{fmt}"
    cid = db.design_studio.amazon_files.add_change_file({
        "account_id": acct, "upload_id": uid, "filename": filename, "version": version,
        "format": fmt, "checksum": hashlib.sha256(delta["content"]).hexdigest(),
        "content_b64": _b64.b64encode(delta["content"]).decode("ascii"),
        "row_count": delta["row_count"],
        "approved": [r["id"] for r in approved],
        "roundtrip": rt,
    })
    change = db.design_studio.amazon_files.get_change_file(cid, account_id=acct)
    return {
        "change_file": {k: change[k] for k in ("id", "filename", "version", "format", "checksum", "row_count", "written_at")},
        "roundtrip": rt,
        "note": "A NEW file was written; the original upload is untouched. Upload this file to Amazon yourself.",
    }


@router.get("/amazon-files/change/{cid}")
def amazon_change_file_detail(cid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    c = db.design_studio.amazon_files.get_change_file(cid, account_id=acct)
    if not c:
        raise HTTPException(status_code=404, detail="Change file not found")
    return {"change_file": {k: c[k] for k in ("id", "filename", "version", "format", "checksum", "row_count", "written_at", "approved")},
            "roundtrip": c.get("roundtrip")}


@router.get("/amazon-files/change/{cid}/download")
def amazon_change_file_download(cid: str, acct: str = Depends(studio_account)):
    import base64 as _b64
    db = get_northstar_db()
    c = db.design_studio.amazon_files.get_change_file(cid, account_id=acct)
    if not c:
        raise HTTPException(status_code=404, detail="Change file not found")
    mime = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if c["format"] == "xlsx" else "text/tab-separated-values")
    return Response(content=_b64.b64decode(c["content_b64"]), media_type=mime,
                    headers={"Content-Disposition": f'attachment; filename="{c["filename"]}"'})


@router.post("/amazon-files/{uid}/aplus-pack")
def amazon_file_aplus_pack(uid: str, body: APlusPackIn, acct: str = Depends(studio_account)):
    from amazon_change_files import build_aplus_pack
    db = get_northstar_db()
    u = db.design_studio.amazon_files.get_upload(uid, account_id=acct)
    if not u:
        raise HTTPException(status_code=404, detail="Upload not found")
    if u["kind"] != "aplus_asin_list":
        raise HTTPException(status_code=422, detail={"code": "not_an_aplus_list",
            "message": "the A+ asset pack is built from an A+ ASIN-list upload"})
    pack = build_aplus_pack(u.get("parsed") or {}, body.assets,
                            {"upload_id": uid, "filename": u["filename"],
                             "checksum": u["checksum"], "downloaded_at": u.get("downloaded_at")},
                            copy=body.copy)
    return {"pack": pack}


# ── Processing reports: match errors back to a change file (item 2) ───────
# The seller uploads the error/processing report Amazon gave them; the studio
# matches each error row to the change row and proposal that produced it, and
# can write a CORRECTED resubmittable file (a new version; originals untouched).

@router.get("/amazon-files/{uid}/changes")
def amazon_file_changes(uid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    u = db.design_studio.amazon_files.get_upload(uid, account_id=acct)
    if not u:
        raise HTTPException(status_code=404, detail="Upload not found")
    rows = db.design_studio.amazon_files.list_change_files(acct, upload_id=uid)
    keys = ("id", "filename", "version", "format", "checksum", "row_count", "written_at", "approved")
    return {"change_files": [{k: r[k] for k in keys if k in r} for r in rows],
            "count": len(rows),
            "note": "New files written from this upload, newest last. The original upload is never modified."}


@router.post("/amazon-files/reports/match")
def amazon_report_match(body: ReportMatchIn, acct: str = Depends(studio_account)):
    """Archive a processing/error report and match its rows to a change file."""
    from amazon_change_files import match_processing_report
    from amazon_file_parsers import ParseError, parse_upload
    import base64 as _b64
    db = get_northstar_db()
    content = _decode_b64(body.content_b64)
    try:
        parsed = parse_upload(body.filename, content)
    except ParseError as exc:
        raise _parse_error(exc)
    if parsed["kind"] not in ("ads_error_report", "listing_processing_report"):
        raise HTTPException(status_code=422, detail={"code": "not_a_processing_report",
            "message": "this file does not look like an Amazon processing/error report (no error column next to "
                       "entity IDs or SKUs). A report with missing columns stays UNKNOWN; nothing is guessed."})
    c = db.design_studio.amazon_files.get_change_file(body.change_file_id, account_id=acct)
    if not c:
        raise HTTPException(status_code=404, detail="Change file not found")
    try:
        change_parsed = parse_upload(c["filename"], _b64.b64decode(c["content_b64"]))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail={"code": "change_file_unreadable",
            "message": f"the change file could not be re-read for matching: {exc}"})
    proposals = db.design_studio.amazon_files.list_proposals(acct, upload_id=c["upload_id"])
    match = match_processing_report(parsed, change_parsed, proposals)
    uid = db.design_studio.amazon_files.create_upload({
        "account_id": acct,
        "filename": body.filename,
        "kind": parsed["kind"],
        "checksum": parsed["checksum"],
        "content_b64": _b64.b64encode(content).decode("ascii"),
        "size_bytes": len(content),
        "row_count": parsed["row_count"],
        "observed_from": parsed["observed_from"],
        "observed_to": parsed["observed_to"],
        "downloaded_at": body.downloaded_at,
        "columns_found": parsed["columns_found"],
        "missing_columns": parsed["missing_columns"],
        "notes": parsed["notes"],
        "detection": parsed["detection"],
        "parsed": parsed,
    })
    stored = db.design_studio.amazon_files.get_upload(uid, account_id=acct)
    return {
        "report_upload": _upload_detail(stored or {}),
        "change_file": {"id": c["id"], "filename": c["filename"], "version": c["version"]},
        "match": match,
        "note": "Error rows are matched to the change file by ID, and to the proposal that produced them. "
                "Unmatched rows are reported, never guessed at.",
    }


@router.post("/amazon-files/change/{cid}/correct")
def amazon_change_correct(cid: str, body: CorrectedChangeIn, acct: str = Depends(studio_account)):
    """Write a CORRECTED resubmittable file from a change file (new version)."""
    from amazon_change_files import build_corrected_change, validate_roundtrip
    from amazon_file_parsers import ParseError, parse_upload
    from amazon_file_writers import write_delta
    import base64 as _b64
    db = get_northstar_db()
    c = db.design_studio.amazon_files.get_change_file(cid, account_id=acct)
    if not c:
        raise HTTPException(status_code=404, detail="Change file not found")
    u = db.design_studio.amazon_files.get_upload(c["upload_id"], account_id=acct)
    try:
        change_parsed = parse_upload(c["filename"], _b64.b64decode(c["content_b64"]))
    except ParseError as exc:
        raise _parse_error(exc)
    prep = build_corrected_change(change_parsed, body.corrections)
    if prep["errors"]:
        raise HTTPException(status_code=422, detail={"code": "correction_refused",
            "message": "; ".join(prep["errors"])})
    if not prep["payloads"]:
        raise HTTPException(status_code=422, detail={"code": "nothing_to_write",
            "message": "every row was dropped; there is nothing to resubmit"})
    fmt = body.format or c["format"]
    try:
        delta = write_delta(change_parsed.get("sheets", []), prep["payloads"], format=fmt)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "write_refused", "message": str(exc)})
    written_parsed = parse_upload(f"corrected.{fmt}", delta["content"])
    rt = validate_roundtrip(change_parsed, written_parsed, prep["payloads"],
                            source_content=_b64.b64decode(c["content_b64"]), written_content=delta["content"])
    version = db.design_studio.amazon_files.next_version(acct, c["upload_id"])
    base = (u["filename"] if u else c["filename"]).rsplit(".", 1)[0]
    filename = f"{base}-corrected-v{version}.{fmt}"
    cid2 = db.design_studio.amazon_files.add_change_file({
        "account_id": acct, "upload_id": c["upload_id"], "filename": filename, "version": version,
        "format": fmt, "checksum": hashlib.sha256(delta["content"]).hexdigest(),
        "content_b64": _b64.b64encode(delta["content"]).decode("ascii"),
        "row_count": delta["row_count"],
        "approved": [p.get("id_value") for p in prep["payloads"]],
        "roundtrip": rt,
    })
    change = db.design_studio.amazon_files.get_change_file(cid2, account_id=acct)
    return {
        "change_file": {k: change[k] for k in ("id", "filename", "version", "format", "checksum", "row_count", "written_at")},
        "roundtrip": rt,
        "dropped": prep["dropped"],
        "note": "A NEW corrected file was written from the change file; both the original upload and the "
                "previous change file are untouched. Upload this file to Amazon yourself.",
    }


# ── Before/after performance comparison (item 5) ──────────────────────────

@router.post("/amazon-files/{uid}/compare")
def amazon_file_compare(uid: str, body: CompareIn, acct: str = Depends(studio_account)):
    """Compare per-entity metrics between this upload and a LATER one."""
    from amazon_change_files import compare_performance
    db = get_northstar_db()
    u = db.design_studio.amazon_files.get_upload(uid, account_id=acct)
    if not u:
        raise HTTPException(status_code=404, detail="Upload not found")
    a = db.design_studio.amazon_files.get_upload(body.after_upload_id, account_id=acct)
    if not a:
        raise HTTPException(status_code=404, detail="After upload not found")
    for label, rec in (("before", u), ("after", a)):
        if not (rec.get("parsed") or {}).get("sheets"):
            raise HTTPException(status_code=422, detail={"code": "unparseable_upload",
                "message": f"the {label} upload has no parsed rows; there is nothing to compare"})
    meta = {"before_from": body.before_from or u.get("observed_from"),
            "before_to": body.before_to or u.get("observed_to"),
            "after_from": body.after_from or a.get("observed_from"),
            "after_to": body.after_to or a.get("observed_to")}
    cmp = compare_performance(u.get("parsed") or {}, a.get("parsed") or {}, meta)
    return {
        "before": {"id": u["id"], "filename": u["filename"], "observed_from": u.get("observed_from"), "observed_to": u.get("observed_to")},
        "after": {"id": a["id"], "filename": a["filename"], "observed_from": a.get("observed_from"), "observed_to": a.get("observed_to")},
        "comparison": cmp,
        "note": "Metrics are read from the two files as-is; a missing metric is UNKNOWN, never 0. "
                "This comparison cannot prove causation - see the notice in the payload.",
    }


# ── Generation arming status (read-only, NO provider call) ────────────────
# Phase 5 item 9. The Studio must be able to say truthfully whether generation
# is armed. This reads local flags only: it never contacts a provider, never
# enqueues work, and never spends anything.

@router.get("/generation-status")
def generation_status(acct: str = Depends(studio_account)):
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
def studio_status(acct: str = Depends(studio_account)):
    db = get_northstar_db()
    return {
        "mode": "local",
        "projects": len(db.design_studio.projects.list_by_section(account_id=acct, limit=1000)),
        "assets": len(db.design_studio.assets.list_by_project(account_id=acct, limit=1000)),
        "jobs": len(db.design_studio.jobs.list_by_project(account_id=acct, limit=1000)),
        "note": "Local design workspace. Provider generation is gated behind explicit Run actions.",
    }


# ── Local media generation (ComfyUI runner) ────────────────────────────────
# Free and private: every render happens on the operator's machine through the
# local ComfyUI (studio_generation.py). Armed only when MEDIA_GEN_LIVE=1 AND
# ComfyUI answers at COMFYUI_URL. Jobs are recorded like every other studio
# action; credits_used stays 0 because nothing paid is ever called here.

#: The container forms the generator can be asked for. A schema field, so the form
#: is not left to prose the model may ignore.
FORM_CLAUSES = {
    "pouch": "a stand-up pouch",
    "box": "a rigid folding carton box",
    "bottle": "a plastic bottle with a screw cap",
    "tube": "a squeeze tube",
    "jar": "a wide-mouth jar",
}


class GenerateIn(BaseModel):
    kind: str = Field(default="image")            # image | video
    purpose: Optional[str] = None
    brief: str = Field(..., min_length=3, max_length=20000)
    tier: str = Field(default="draft")            # draft | final
    text_safe: bool = False                       # strip lettering demands; OCR-check the render
    width: Optional[int] = None
    height: Optional[int] = None
    project_id: Optional[str] = None
    seed: Optional[int] = None
    #: The container form the user asked for. A schema field, not a phrase buried in
    #: prose: the generator drifts to boxes when the form rides only in the brief.
    form: Optional[str] = Field(default=None, max_length=20)
    #: When true, a render that passes the form-adherence gate is written as a
    #: deliverable package (folder + manifest) in the same request.
    deliver: bool = False
    #: Placement canvas: square (1:1), story (9:16) or wide (16:9). A format fixes
    #: width/height; passing a contradictory pair is refused, not overridden.
    format: Optional[str] = Field(default=None, max_length=20)
    #: Review surface for the ship gate (product_picture, listing_image,
    #: social_frame, default). Floors live in config/image_review.json.
    surface: Optional[str] = Field(default=None, max_length=40)
    #: Generated assets used as product references (FLUX 3 reference conditioning).
    reference_asset_ids: Optional[list] = None
    #: Score the render with the ship gate even when no deliverable is written.
    review: bool = False
    #: Explicit acknowledgement of the human-feature warning for a video render.
    human_features_ack: bool = False


@router.get("/engine")
def engine_status(acct: str = Depends(studio_account)):
    import studio_generation as sg
    return sg.engine_status()


@router.post("/generate")
def generate_media(body: GenerateIn, acct: str = Depends(studio_account)):
    # Placement validation happens before anything else: a contradictory canvas
    # is a 422 whether or not the engine is armed, and costs no GPU time.
    import ad_formats as _af
    try:
        ad_format = _af.resolve(body.format, body.width, body.height)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    width = ad_format["width"] if ad_format else body.width
    height = ad_format["height"] if ad_format else body.height

    if str(body.kind) == "video":
        import video_guard as _vg
        guard = _vg.check_prompt(body.brief,
                                 acknowledged=body.human_features_ack)
        if guard["requires_override"]:
            _vg.audit_override(acct, "generate", body.brief, guard["matched"],
                               body.human_features_ack)
        if guard["blocked"]:
            raise HTTPException(status_code=422, detail=_vg.guard_detail(
                body.brief, acknowledged=body.human_features_ack))

    import studio_generation as sg
    st = sg.engine_status()
    if not st["armed"]:
        raise HTTPException(status_code=409, detail={
            "code": "engine_not_armed",
            "message": ("The local media engine is not armed. Set MEDIA_GEN_LIVE=1 and keep "
                        "ComfyUI reachable at COMFYUI_URL (see the Engine card)."),
            "engine": st,
        })
    if body.kind not in ("image", "video"):
        raise HTTPException(status_code=422, detail="kind must be image or video")

    from text_fidelity import render_with_text_guard
    text_safe = bool(getattr(body, "text_safe", False))

    from pathlib import Path
    import uuid as _uuid
    out_dir = Path(__file__).resolve().parent / "data" / "studio_generated"

    reference_bytes = None
    if body.reference_asset_ids:
        if body.kind != "image":
            raise HTTPException(status_code=422, detail={
                "code": "reference_requires_image",
                "message": "reference_asset_ids apply to image renders only"})
        db_ref = get_northstar_db()
        for aid in list(body.reference_asset_ids)[:2]:
            asset = db_ref.design_studio.assets.get_by_id(str(aid), account_id=acct)
            if not asset or not asset.get("storage_key"):
                raise HTTPException(status_code=422, detail={
                    "code": "reference_asset_not_found", "asset_id": str(aid)})
            name = Path(str(asset["storage_key"])).name  # basename only
            path = out_dir / name
            if not path.is_file():
                raise HTTPException(status_code=422, detail={
                    "code": "reference_asset_missing_file", "asset_id": str(aid)})
            reference_bytes = path.read_bytes()
            break

    db = get_northstar_db()
    now = datetime.now(timezone.utc).isoformat()
    job_id = db.design_studio.jobs.create({
        "account_id": acct,
        "project_id": body.project_id,
        "job_type": f"generate-{body.kind}",
        "provider": "local:comfyui",
        "status": "running",
        "cost_preview": {"provider": "local", "cost": 0,
                         "note": "Local compute on the operator's GPU; nothing paid."},
        "params": {"purpose": body.purpose, "tier": body.tier, "brief": body.brief,
                   "width": width, "height": height, "seed": body.seed,
                   **({"format": ad_format["format"],
                       "ratio": ad_format["ratio"]} if ad_format else {})},
        "started_at": now,
        "credits_used": 0,
    })
    def _render(prompt: str):
        if body.kind == "video":
            return sg.generate_video(prompt=prompt, width=width, height=height,
                                     tier=body.tier, seed=body.seed)
        if reference_bytes is not None:
            return sg.generate_reference(prompt=prompt, reference_bytes=reference_bytes,
                                         width=width, height=height,
                                         tier=body.tier, seed=body.seed)
        return sg.generate_image(prompt=prompt, width=width, height=height,
                                 tier=body.tier, seed=body.seed)
    # The requested container form is stated at the head AND the tail of the brief.
    # Observed drift: a bottle and a tube brief both rendered as a rigid box when the
    # form existed only once, mid-sentence.
    brief = str(body.brief)
    form_clause = FORM_CLAUSES.get(str(body.form or "").strip().lower())
    if form_clause:
        brief = f"The product container is {form_clause}. {brief}\nOnly a {form_clause} is shown."
    try:
        guarded = render_with_text_guard(render_fn=_render, brief=brief,
                                         text_safe=text_safe)
    except Exception as exc:  # noqa: BLE001 - recorded on the job, surfaced to the caller
        from text_fidelity import TextSafeBriefEmpty
        db.design_studio.jobs.update(job_id, {
            "status": "failed", "logs": str(exc)[:2000],
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }, account_id=acct)
        raise HTTPException(status_code=422 if isinstance(exc, TextSafeBriefEmpty) else 502,
                            detail={"code": "text_safe_brief_empty" if isinstance(exc, TextSafeBriefEmpty)
                                    else "generation_failed",
                                    "message": str(exc)[:400]})

    out = guarded["out"]
    tf_result = guarded["text_fidelity"]

    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{_uuid.uuid4().hex}.{out['ext']}"
    (out_dir / fname).write_bytes(out["bytes"])
    if guarded.get("raw_bytes") and tf_result is not None:
        raw_key = f"{_uuid.uuid4().hex}_raw.{out['ext']}"
        (out_dir / raw_key).write_bytes(guarded["raw_bytes"])
        tf_result = {**tf_result, "raw_storage_key": raw_key}

    aid = db.design_studio.assets.create({
        "account_id": acct,
        "project_id": body.project_id,
        "name": f"{body.purpose or body.kind} - {out['model']} - {now[:16]}",
        "asset_type": f"generated-{body.kind}",
        "mime_type": out["mime"],
        "storage_key": fname,
        "width": out.get("width"), "height": out.get("height"),
        "duration_seconds": out.get("duration_seconds"),
        "size_bytes": len(out["bytes"]),
        "metadata": {
            "generation": {
                "provider": "comfyui", "model": out["model"], "tier": body.tier,
                "purpose": body.purpose, "prompt": body.brief, "seed": out.get("seed"),
                "generated_at": now,
            },
            "note": "Rendered locally on the operator's machine via ComfyUI. Nothing was sent to any provider.",
            **({"text_fidelity": tf_result} if tf_result else {}),
        },
    })
    db.design_studio.jobs.update(job_id, {
        "status": "done", "result_ids": [aid],
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }, account_id=acct)
    asset = db.design_studio.assets.get_by_id(aid, account_id=acct)
    # Automation hand-off: a render that passes the quality gate becomes a
    # deliverable folder without a second manual step. A failed verdict writes
    # nothing and says which axis failed and why.
    deliverable = None
    adherence = None
    quality = None
    review = None
    review_block = None
    if body.review or body.deliver:
        import ship_gate as _sg
        review = _sg.review_image(out["bytes"], brief=body.brief,
                                  reference=reference_bytes,
                                  surface=body.surface)
        review_block = _sg.manifest_block(review)
    if body.deliver:
        import deliverables as _dl
        import quality_gate as _qg
        import text_fidelity as _tf
        text_requested = (not body.text_safe) or bool((tf_result or {}).get("expected_terms"))
        expected = list((tf_result or {}).get("expected_terms") or [])
        if not expected and text_requested:
            expected = _tf.extract_expected_terms(body.brief)
        scored = _qg.score(out["bytes"], brief=body.brief,
                           requested_form=str(body.form or ""),
                           text_requested=text_requested,
                           expected_terms=expected)
        verdict = _qg.verdict(scored)
        quality = verdict
        form_axis = (scored.get("axes") or {}).get("form") or {}
        adherence = {"ok": bool(verdict.get("ok")),
                     "requested": str(body.form or ""),
                     "observed": form_axis.get("observed"),
                     "model": scored.get("model"),
                     "score": verdict.get("score"),
                     "failed_axes": verdict.get("failed"),
                     "reasons": verdict.get("reasons")}
        if verdict.get("ok") and not (review and review.get("status") == "refused"):
            deliverable = _dl.write_deliverable(
                job_id, brief=body.brief, final_png=out["bytes"],
                adherence=adherence, extra={
                    "model": out.get("model"), "tier": body.tier,
                    "seed": out.get("seed"), "asset_id": aid,
                    "requested_form": body.form,
                    "quality": _qg.manifest_block(scored, verdict),
                    "dieline": {"built": False,
                                "reason": "mockup render; no print dieline was generated"},
                    "color_profile": {"working": "RGB", "target": "CMYK",
                                      "converted": False},
                    **({"format": ad_format["format"],
                        "canvas": {"width": ad_format["width"],
                                   "height": ad_format["height"]},
                        "ratio": ad_format["ratio"],
                        "placements": ad_format["placements"]}
                       if ad_format else {})})
    return {
        "job": db.design_studio.jobs.get_by_id(job_id, account_id=acct),
        "asset": {**(asset or {}), "file_url": f"/api/design-studio/assets/{aid}/file"},
        "engine": st,
        "text_fidelity": tf_result,
        "adherence": adherence,
        "quality": quality,
        "review": review_block,
        "delivery_blocked": ("ship_gate_refused"
                             if deliverable is None and review
                             and review.get("status") == "refused" and body.deliver
                             else None),
        "ad_format": ad_format,
        "deliverable": deliverable,
    }


@router.get("/ad-formats")
def ad_formats_route(acct: str = Depends(studio_account)):
    """The placement canvases: 1:1 feed, 9:16 story/reel/short, 16:9 banner."""
    import ad_formats as _af
    return _af.describe()


@router.get("/video-formats")
def video_formats_route(acct: str = Depends(studio_account)):
    """Video placement contracts, each flagged verified or working-assumption."""
    import video_formats as _vf
    return {"formats": _vf.describe(), "ad_lengths": list(_vf.AD_LENGTHS)}


@router.get("/deliverables")
def list_deliverables_route(acct: str = Depends(studio_account)):
    """Deliverable packages a user can reopen: manifest + file list per run."""
    import deliverables as _dl
    rows = _dl.list_deliverables()
    return {"count": len(rows), "deliverables": rows}


@router.get("/deliverables/{run_id}/final")
def deliverable_final_route(run_id: str, acct: str = Depends(studio_account)):
    """The packaged render itself, so a returning user can preview what shipped."""
    import deliverables as _dl
    from fastapi import Response as _Response
    data = _dl.read_final(run_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    return _Response(content=data, media_type="image/png")


class ShortsIn(BaseModel):
    asset_id: str = Field(..., min_length=3, max_length=80)
    prompt: str = Field("", max_length=600)
    width: int = Field(480, ge=256, le=1280)
    height: int = Field(832, ge=256, le=1280)
    length: int = Field(33, ge=9, le=121)
    steps: int = Field(20, ge=4, le=60)
    cfg: float = Field(5.0, ge=1.0, le=12.0)
    seed: int = 1
    fps: int = Field(16, ge=8, le=30)
    text_requested: bool = False
    #: Optional platform contract. When set, the duration/canvas/fps come from
    #: `video_formats.plan()`; the lane renders the planned clips, stitches them
    #: and returns an ffprobe-checked MP4 at the platform canvas.
    platform: str = Field("", max_length=40)
    seconds: Optional[float] = Field(None, ge=1, le=600)
    #: Explicit acknowledgement of the human-feature warning for this render.
    human_features_ack: bool = False


@router.post("/shorts")
def make_shorts(body: ShortsIn, acct: str = Depends(studio_account)):
    """9:16 image-to-video on Wan 2.2 TI2V 5B, gated on a decoded frame."""
    import shorts as _sh
    import text_fidelity as _tf
    import studio_generation as _sg
    import video_guard as _vg
    import uuid
    from pathlib import Path

    guard = _vg.check_prompt(body.prompt, acknowledged=body.human_features_ack)
    if guard["requires_override"]:
        _vg.audit_override(acct, "shorts", body.prompt, guard["matched"],
                           body.human_features_ack)
    if guard["blocked"]:
        raise HTTPException(status_code=422, detail=_vg.guard_detail(
            body.prompt, acknowledged=body.human_features_ack))

    # Platform contract FIRST: a bad placement request is a 422 whether or not the
    # GPU is armed, and a window that needs stitching is refused before any work.
    plan = None
    width, height, length, fps = body.width, body.height, body.length, body.fps
    if body.platform:
        import video_formats as _vf
        try:
            plan = _vf.plan(body.platform, body.seconds)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={
                "code": "video_format_invalid", "message": str(exc)[:300]})
        # A multi-clip window is not refused any more: the stitch branch below
        # renders the planned clips and checks the MP4 against the contract.
        width, height, length, fps = (plan["width"], plan["height"],
                                      plan["frames_per_clip"], plan["fps"])

    st = _sg.engine_status()
    if not st["armed"]:
        raise HTTPException(status_code=409, detail={
            "code": "engine_not_armed", "engine": st,
            "message": "the local media engine is not armed (MEDIA_GEN_LIVE / ComfyUI)"})
    db = get_northstar_db()
    asset = db.design_studio.assets.get_by_id(body.asset_id, account_id=acct)
    if not asset or not asset.get("storage_key"):
        raise HTTPException(status_code=404, detail="Asset not found")
    path = Path(__file__).resolve().parent / "data" / "studio_generated" / Path(
        str(asset["storage_key"])).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Asset file not found on disk")

    prompt = body.prompt or _sh.DEFAULT_PROMPT
    expected = _tf.extract_expected_terms(prompt) if body.text_requested else []

    if plan:
        # One sampler call per planned clip (one for a short window), chained on
        # the last decoded frame, then an ffprobe-checked MP4 at the platform's
        # canvas. The file is written only after the picture gate passes.
        out_path = (Path(__file__).resolve().parent / "data" / "studio_generated"
                    / f"short_stitched_{uuid.uuid4().hex[:10]}.mp4")
        try:
            stitched = _sh.generate_stitched(
                path.read_bytes(), out_path=out_path, platform=body.platform,
                seconds=body.seconds, prompt=prompt,
                # Wan paints lettering onto packaging unless the negative names
                # it; a video render never composes text here (the label lane
                # does that separately), so unwanted glyphs are always refused.
                negative=_sh.master_negative(),
                steps=body.steps,
                cfg=body.cfg, seed=body.seed, text_requested=body.text_requested,
                expected_terms=expected)
        except (ValueError, RuntimeError) as exc:
            raise HTTPException(status_code=502, detail={
                "code": "shorts_stitch_failed", "message": str(exc)[:400]})
        if not stitched.get("ok"):
            raise HTTPException(status_code=502, detail={
                "code": "shorts_quality_refused",
                "message": stitched.get("reason") or "the stitched video failed the gate",
                "quality": stitched.get("quality"),
                "format": plan})
        return {"ok": True, "file": str(out_path), "format": plan,
                "stitched": stitched, "quality": stitched.get("quality"),
                "checks": stitched.get("checks"), "compliance": plan["compliance"]}

    try:
        result = _sh.generate(path.read_bytes(), prompt=prompt, width=width,
                              height=height, length=length, steps=body.steps,
                              cfg=body.cfg, seed=body.seed, fps=fps)
        packaged = _sh.package_render(result, brief=prompt,
                                      text_requested=body.text_requested,
                                      expected_terms=expected)
    except (ValueError, RuntimeError, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail={
            "code": "shorts_failed", "message": str(exc)[:400]})
    return {"ok": packaged["verdict"]["ok"], "verdict": packaged["verdict"],
            "folder": packaged["folder"],
            "frame_count": result.get("frame_count"), "fps": result.get("fps"),
            "size": result.get("size"), "seconds": result.get("seconds"),
            "video_bytes": result.get("video_bytes"), "model": result.get("model"),
            **({"format": plan} if plan else {}),
            "manifest": packaged.get("manifest")}


class RelightIn(BaseModel):
    asset_id: str = Field(..., min_length=3, max_length=80)
    prompt: str = Field("", max_length=600)
    width: int = Field(1024, ge=256, le=1536)
    height: int = Field(1024, ge=256, le=1536)
    steps: int = Field(25, ge=4, le=60)
    cfg: float = Field(2.0, ge=1.0, le=12.0)
    denoise: float = Field(0.9, ge=0.3, le=1.0)
    seed: int = 1


@router.post("/relight")
def relight_asset(body: RelightIn, acct: str = Depends(studio_account)):
    """IC-Light relight of a stored asset; refuses noise and refuses to pretend."""
    import relight as _rl
    import studio_generation as _sg
    import uuid as _uuid
    from pathlib import Path

    state = _rl.availability()
    if not state["available"]:
        raise HTTPException(status_code=422, detail={
            "code": "relight_unavailable", "message": state["reason"],
            "missing": state["missing"], "partial": state["partial"]})
    st = _sg.engine_status()
    if not st["armed"]:
        raise HTTPException(status_code=409, detail={
            "code": "engine_not_armed", "engine": st})
    db = get_northstar_db()
    asset = db.design_studio.assets.get_by_id(body.asset_id, account_id=acct)
    if not asset or not asset.get("storage_key"):
        raise HTTPException(status_code=404, detail="Asset not found")
    path = Path(__file__).resolve().parent / "data" / "studio_generated" / Path(
        str(asset["storage_key"])).name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Asset file not found on disk")

    try:
        result = _rl.relight(path.read_bytes(), prompt=body.prompt or _rl.DEFAULT_PROMPT,
                             width=body.width, height=body.height, steps=body.steps,
                             cfg=body.cfg, seed=body.seed, denoise=body.denoise)
    except _rl.RelightUnavailable as exc:
        raise HTTPException(status_code=502, detail={
            "code": "relight_output_is_noise", "message": str(exc)[:400]})
    except (ValueError, RuntimeError, TimeoutError) as exc:
        raise HTTPException(status_code=502, detail={
            "code": "relight_failed", "message": str(exc)[:400]})

    # Register the asset BEFORE packaging: a failure after the folder is written
    # leaves an orphan package with no asset (observed once, a 500 on uuid).
    out_dir = Path(__file__).resolve().parent / "data" / "studio_generated"
    name = f"relit_{_uuid.uuid4().hex}.png"
    (out_dir / name).write_bytes(result["png"])
    base = asset.get("name") or "asset"
    aid = db.design_studio.assets.create({
        "account_id": acct, "project_id": asset.get("project_id"),
        "name": f"{base} (relit)", "asset_type": "relight",
        "mime_type": "image/png", "storage_key": name,
        "width": result["size"][0], "height": result["size"][1],
        "size_bytes": len(result["png"]),
        "metadata": {"relight": {"source_asset_id": body.asset_id,
                                 "base_checkpoint": result["base_checkpoint"],
                                 "noise_metric": result["noise_metric"]}},
    })
    packaged = _rl.package(result, source_asset_id=body.asset_id,
                           brief=body.prompt or _rl.DEFAULT_PROMPT)
    return {"ok": packaged["verdict"]["ok"], "asset_id": aid,
            "file_url": f"/api/design-studio/assets/{aid}/file",
            "verdict": packaged["verdict"], "folder": packaged["folder"],
            "seconds": result["seconds"], "noise_metric": result["noise_metric"],
            "manifest": packaged.get("manifest")}


@router.get("/assets/{aid}/file")
def get_asset_file(aid: str, acct: str = Depends(studio_account)):
    """Stream a generated asset file. Account-scoped; the served path is always
    the basename inside the studio output directory."""
    from pathlib import Path
    from fastapi.responses import FileResponse as _FileResponse
    db = get_northstar_db()
    asset = db.design_studio.assets.get_by_id(aid, account_id=acct)
    if not asset or not asset.get("storage_key"):
        raise HTTPException(status_code=404, detail="Asset file not found")
    name = Path(str(asset["storage_key"])).name  # basename only - no traversal
    path = Path(__file__).resolve().parent / "data" / "studio_generated" / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Asset file not found")
    return _FileResponse(str(path), media_type=asset.get("mime_type") or "application/octet-stream")

# ── Phase 3 operating-loop routes (mount points for render_bind / handoff / memory) ──
from pydantic import BaseModel as _BM


class RenderBriefIn(_BM):
    product: dict
    pricing: dict = {}
    keywords: list = []
    buyer: dict = {}
    lifestyle: bool = False


class HandoffIn(_BM):
    brief: dict
    assets: list = []


class BrandMemoryIn(_BM):
    profile: dict = {}
    account_id: str = "default"


@router.post("/render-brief")
def render_brief_route(body: RenderBriefIn) -> dict:
    """Margin -> material binding for a render. Pure; no GPU, no spend."""
    import render_bind
    brief = render_bind.bind(body.product, pricing=body.pricing, keywords=body.keywords,
                             buyer=body.buyer, lifestyle=body.lifestyle)
    out = brief.to_dict()
    out["prompt_suffix"] = render_bind.prompt_suffix(brief)
    return out


@router.post("/listing-handoff")
def listing_handoff_route(body: HandoffIn) -> dict:
    """Asset manifest + brief -> Listing Forge payload. Refuses a non-white hero."""
    import asset_handoff
    return asset_handoff.handoff(body.brief, body.assets)


@router.post("/brand-memory/propose")
def brand_memory_propose_route(body: BrandMemoryIn) -> dict:
    """Extract brand tokens as a PROPOSAL. Never writes: status is always proposed."""
    import brand_memory
    return brand_memory.propose(brand_memory.extract(body.profile),
                                account_id=body.account_id)
