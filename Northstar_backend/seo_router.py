"""Brand SEO Engine router (V3 S7) — the canonical, versioned brand profile.

The SEO engine's principle (plan §5): SEO is not a listings feature; it is a
property of the brand that every service serves. This router owns the ONE
canonical profile each brand has, and its immutable version history.

Honesty boundaries:
  • Versions are append-only. Editing a profile appends a version; the old ones
    stay readable and rollback-safe. Nothing is silently rewritten.
  • A profile body is validated for shape (`seo_profile.normalize_body`) but the
    engine never invents content for the operator — absence stays absence.
  • Tenant-scoped: a profile owned by another account reports 404, never a leak.
  • These routes read/write local SQLite only; they arm no live/paid action.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from data_layer import get_northstar_db  # noqa: E402
from design_studio_api import studio_account  # noqa: E402

router = APIRouter(prefix="/api/seo", tags=["seo"])


class ProfileIn(BaseModel):
    brand_key: str = Field(..., min_length=1, max_length=80)
    name: Optional[str] = Field(None, max_length=160)
    body: Dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = Field(None, max_length=500)


class VersionIn(BaseModel):
    body: Dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = Field(None, max_length=500)
    created_by: Optional[str] = Field(None, max_length=80)


class ListingRevisionIn(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    bullets: Optional[Any] = None      # list[str] or newline-separated string
    backend_terms: Optional[str] = Field(None, max_length=2000)
    description: Optional[str] = Field(None, max_length=5000)
    asin: Optional[str] = Field(None, max_length=40)
    source: Optional[str] = Field(None, max_length=80)
    note: Optional[str] = Field(None, max_length=500)


@router.get("/profiles")
def list_profiles(limit: int = 100, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    return {"profiles": db.seo.profiles.list_profiles(
        acct, limit=min(max(int(limit), 1), 500))}


@router.post("/profiles")
def create_profile(body: ProfileIn, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    try:
        profile = db.seo.profiles.create_profile({
            "account_id": acct,
            "brand_key": body.brand_key,
            "name": body.name,
            "body": body.body,
            "note": body.note,
            "created_by": acct,
        })
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return profile


@router.get("/profiles/{pid}")
def get_profile(pid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    profile = db.seo.profiles.get_profile(pid, account_id=acct)
    if not profile:
        raise HTTPException(status_code=404, detail="SEO profile not found")
    return profile


@router.get("/profiles/{pid}/versions")
def list_versions(pid: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    if not db.seo.profiles.get_profile(pid, account_id=acct):
        raise HTTPException(status_code=404, detail="SEO profile not found")
    return {"versions": db.seo.profiles.list_versions(pid, account_id=acct)}


@router.get("/profiles/{pid}/versions/{version}")
def get_version(pid: str, version: int, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    v = db.seo.profiles.get_version(pid, version, account_id=acct)
    if not v:
        raise HTTPException(status_code=404, detail="SEO profile version not found")
    return v


@router.post("/profiles/{pid}/versions")
def add_version(pid: str, body: VersionIn, acct: str = Depends(studio_account)):
    """Append a new immutable version. The previous versions are never touched."""
    db = get_northstar_db()
    try:
        profile = db.seo.profiles.add_version(
            pid, acct, body.body, note=body.note, created_by=body.created_by or acct)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not profile:
        raise HTTPException(status_code=404, detail="SEO profile not found")
    return profile


# ── Listing revisions (S7 §5.2): the newest revision is the SEO target ──────

@router.get("/listings")
def list_listings(limit: int = 100, acct: str = Depends(studio_account)):
    """One row per listing key — its LATEST revision."""
    db = get_northstar_db()
    return {"listings": db.seo.revisions.list_latest(acct, limit=min(max(int(limit), 1), 500))}


@router.get("/listings/{listing_key}")
def get_latest_listing(listing_key: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    latest = db.seo.revisions.get_latest(acct, listing_key)
    if not latest:
        raise HTTPException(status_code=404, detail="No revisions for this listing")
    return latest


@router.get("/listings/{listing_key}/revisions")
def list_listing_revisions(listing_key: str, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    return {"revisions": db.seo.revisions.list_revisions(acct, listing_key)}


@router.get("/listings/{listing_key}/revisions/{revision}")
def get_listing_revision(listing_key: str, revision: int, acct: str = Depends(studio_account)):
    db = get_northstar_db()
    rev = db.seo.revisions.get(acct, listing_key, revision)
    if not rev:
        raise HTTPException(status_code=404, detail="Listing revision not found")
    return rev


@router.post("/listings/{listing_key}/revisions")
def add_listing_revision(listing_key: str, body: ListingRevisionIn,
                         acct: str = Depends(studio_account)):
    """Append a listing revision. Prior revisions are never mutated."""
    db = get_northstar_db()
    bullets = body.bullets
    if isinstance(bullets, str):
        bullets = [ln for ln in bullets.split("\n") if ln.strip()]
    try:
        rev = db.seo.revisions.add_revision({
            "account_id": acct,
            "listing_key": listing_key,
            "asin": body.asin,
            "title": body.title,
            "bullets": bullets,
            "backend_terms": body.backend_terms,
            "description": body.description,
            "source": body.source or "operator",
            "note": body.note,
            "created_by": acct,
        })
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return rev
