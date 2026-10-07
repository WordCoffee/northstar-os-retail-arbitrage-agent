"""Local ``/api/<service>`` lanes for the creative cluster.

Each lane routes an existing backend module that was previously unrouted:

* ``/api/listing-forge/*``  → ``listing_forge.py``  (titles, bullets, copy, score, compliance)
* ``/api/social/*``         → ``social_pulse.py``   (captions, calendar, email, outreach, brand voice)
* ``/api/ad-pilot/*``       → ``ad_pilot.py``       (bid/tier/negative/structure/budget/target-ACoS)

Additive and local-first. Generation is screened by the moderation policy; any
response carries ``review_required`` so nothing is treated as final without a
human step. Every lane runs offline via the modules' deterministic template
fallbacks and upgrades to the local LLM (Ollama) when it is present.
"""

from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from . import approvals, cloud, moderation, providers, storage, video
from . import assets as asset_store
from . import bundles as bundle_store
from . import competitor_monitor, listing_guardian

import ad_pilot
import listing_forge
import social_pulse


def _stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")

# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------


def _screen(payload: Any) -> Dict[str, Any]:
    result = moderation.screen_payload(payload)
    if not result.allowed:
        raise HTTPException(status_code=422, detail={
            "message": "blocked by moderation policy",
            "flags": result.flags,
            "policy": result.as_dict()["policy"],
        })
    return result.as_dict()


def _as_text(v: Any, key: str) -> str:
    if isinstance(v, dict):
        return str(v.get(key) or "")
    return str(v or "")


def _as_list(v: Any, key: str) -> List[str]:
    if isinstance(v, dict):
        items = v.get(key) or []
    elif isinstance(v, list):
        items = v
    else:
        items = []
    return [str(x) for x in items]


# ---------------------------------------------------------------------------
# ListingForge  — /api/listing-forge/*


listing_router = APIRouter(prefix="/api/listing-forge", tags=["listing-forge"])


@listing_router.post("/generate")
def listing_generate(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    product = body.get("product")
    if not isinstance(product, dict) or not product:
        raise HTTPException(status_code=400, detail="product (object) is required")
    mod = _screen(body)

    brand_voice = body.get("brand_voice")
    top_keywords = body.get("top_keywords")
    use_llm = bool(body.get("use_llm", True))
    model = body.get("model", "northstar-qwen3:rev1") if use_llm else ""

    title = listing_forge.generate_title(product, brand_voice=brand_voice,
                                        top_keywords=top_keywords,
                                        competitor_titles=body.get("competitor_titles"),
                                        model=model)
    bullets = listing_forge.generate_bullets(product, brand_voice=brand_voice,
                                             top_keywords=top_keywords, model=model)
    description = listing_forge.generate_description(product, brand_voice=brand_voice,
                                                     model=model)
    backend_terms = listing_forge.generate_backend_terms(product, top_keywords=top_keywords)
    search_terms = listing_forge.generate_search_terms(product, top_keywords=top_keywords)

    score = listing_forge.score_listing(
        product, title=_as_text(title, "title"),
        bullets=_as_list(bullets, "bullets"),
        description=_as_text(description, "description"),
        keywords=top_keywords,
    )
    compliance = listing_forge.check_compliance(
        title=_as_text(title, "title"), bullets=_as_list(bullets, "bullets"),
        brand=str(product.get("brand", "")),
    )
    return {
        "ok": True, "review_required": mod["review_required"], "moderation": mod,
        "title": title, "bullets": bullets, "description": description,
        "backend_terms": backend_terms, "search_terms": search_terms,
        "score": score, "compliance": compliance,
        "basis": "listing_forge local lane (template fallback; local LLM when available)",
    }


@listing_router.post("/score")
def listing_score(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    product = body.get("product") or {}
    return {"ok": True, "score": listing_forge.score_listing(
        product, title=body.get("title", ""), bullets=body.get("bullets") or [],
        description=body.get("description", ""), keywords=body.get("keywords"))}


@listing_router.post("/compliance")
def listing_compliance(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    return {"ok": True, **listing_forge.check_compliance(
        title=body.get("title", ""), bullets=body.get("bullets") or [],
        brand=body.get("brand", ""))}


# ---------------------------------------------------------------------------
# SocialPulse  — /api/social/*


social_router = APIRouter(prefix="/api/social", tags=["social"])


@social_router.post("/caption")
def social_caption(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    product = body.get("product")
    if not isinstance(product, dict) or not product:
        raise HTTPException(status_code=400, detail="product (object) is required")
    mod = _screen(body)
    result = social_pulse.generate_caption(
        product, platform=body.get("platform", "instagram"),
        brand=body.get("brand", "Mogra Organics"),
        angle=body.get("angle", "quality"), voice=body.get("voice"),
        model=(body.get("model", "northstar-qwen3:rev1") if body.get("use_llm", True) else ""))
    return {"ok": True, "review_required": mod["review_required"],
            "moderation": mod, **result,
            "basis": "social_pulse local lane (template fallback; local LLM when available)"}


@social_router.post("/calendar")
def social_calendar(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    products = body.get("products")
    if not isinstance(products, list) or not products:
        raise HTTPException(status_code=400, detail="products (array) is required")
    mod = _screen(body)
    calendar = social_pulse.generate_content_calendar(
        products, brand=body.get("brand", "Mogra Organics"),
        days=int(body.get("days", 30)), platforms=body.get("platforms"))
    return {"ok": True, "review_required": mod["review_required"],
            "moderation": mod, "days": len(calendar), "calendar": calendar}


@social_router.post("/review-email")
def social_review_email(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    product = body.get("product")
    if not isinstance(product, dict) or not product:
        raise HTTPException(status_code=400, detail="product (object) is required")
    mod = _screen(body)
    result = social_pulse.generate_review_request_email(
        product, brand=body.get("brand", "Mogra Organics"), tone=body.get("tone", "friendly"))
    return {"ok": True, "review_required": mod["review_required"], "moderation": mod, **result}


@social_router.post("/outreach")
def social_outreach(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    product = body.get("product")
    name = body.get("influencer_name")
    if not isinstance(product, dict) or not product:
        raise HTTPException(status_code=400, detail="product (object) is required")
    if not name:
        raise HTTPException(status_code=400, detail="influencer_name is required")
    mod = _screen(body)
    result = social_pulse.generate_influencer_outreach(
        product, name, platform=body.get("platform", "instagram"),
        brand=body.get("brand", "Mogra Organics"))
    return {"ok": True, "review_required": mod["review_required"], "moderation": mod, **result}


@social_router.get("/brand-voice")
def social_brand_voice_get(brand: str = Query(...)) -> Dict[str, Any]:
    return {"ok": True, "brand": brand, "voice": social_pulse.load_brand_voice(brand)}


@social_router.post("/brand-voice")
def social_brand_voice_put(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Upload a brand voice profile. The same path a customer uses for theirs."""
    brand = body.get("brand")
    profile = body.get("profile")
    if not brand:
        raise HTTPException(status_code=400, detail="brand is required")
    if not isinstance(profile, dict) or not profile:
        raise HTTPException(status_code=400, detail="profile (object) is required")
    mod = _screen(profile)
    entry_id = social_pulse.save_brand_voice(
        brand, profile, account_id=body.get("account_id", "default"))
    return {"ok": True, "entry_id": entry_id, "brand": brand,
            "review_required": mod["review_required"], "moderation": mod,
            "saved": social_pulse.load_brand_voice(brand)}


# ---------------------------------------------------------------------------
# AdPilot  — /api/ad-pilot/*  (planning / recommendation only; no spend)


adpilot_router = APIRouter(prefix="/api/ad-pilot", tags=["ad-pilot"])


@adpilot_router.post("/bid-recommendation")
def adpilot_bid(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    for req in ("keyword", "current_bid"):
        if req not in body:
            raise HTTPException(status_code=400, detail=f"{req} is required")
    result = ad_pilot.optimize_bid(
        body["keyword"], float(body["current_bid"]), acos=body.get("acos"),
        target_acos=float(body.get("target_acos", 30.0)), clicks=int(body.get("clicks", 0)),
        orders=int(body.get("orders", 0)), impressions=int(body.get("impressions", 0)),
        ctr=body.get("ctr"), cvr=body.get("cvr"), margin_pct=body.get("margin_pct"))
    return {"ok": True, **result,
            "notice": "recommendation only — no live ad change is applied by this lane"}


@adpilot_router.post("/classify-keywords")
def adpilot_classify(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    keywords = body.get("keywords")
    if not isinstance(keywords, list) or not keywords:
        raise HTTPException(status_code=400, detail="keywords (array) is required")
    target = float(body.get("target_acos", 30.0))
    out = []
    for k in keywords:
        if not isinstance(k, dict):
            continue
        out.append({
            "keyword": k.get("keyword", ""),
            "tier": ad_pilot.classify_keyword_tier(
                impressions=int(k.get("impressions", 0)), clicks=int(k.get("clicks", 0)),
                orders=int(k.get("orders", 0)), acos=k.get("acos"), target_acos=target),
        })
    return {"ok": True, "count": len(out), "keywords": out}


@adpilot_router.post("/negative-candidates")
def adpilot_negatives(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    keywords = body.get("keywords")
    if not isinstance(keywords, list) or not keywords:
        raise HTTPException(status_code=400, detail="keywords (array) is required")
    rows = ad_pilot.detect_negative_keyword_candidates(
        keywords, min_clicks=int(body.get("min_clicks", 10)),
        max_orders=int(body.get("max_orders", 0)))
    return {"ok": True, "count": len(rows), "candidates": rows}


@adpilot_router.post("/campaign-structure")
def adpilot_structure(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    for req in ("asin", "product_title", "keywords"):
        if req not in body:
            raise HTTPException(status_code=400, detail=f"{req} is required")
    result = ad_pilot.generate_campaign_structure(
        body["asin"], body["product_title"], body["keywords"],
        daily_budget=float(body.get("daily_budget", 25.0)),
        target_acos=float(body.get("target_acos", 30.0)))
    return {"ok": True, **result,
            "notice": "proposed structure only — not applied to any ad account"}


@adpilot_router.post("/budget-allocation")
def adpilot_budget(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    campaigns = body.get("campaigns")
    if not isinstance(campaigns, list) or not campaigns:
        raise HTTPException(status_code=400, detail="campaigns (array) is required")
    rows = ad_pilot.allocate_budget(campaigns, float(body["total_budget"]),
                                    performance_weight=float(body.get("performance_weight", 0.5)))
    return {"ok": True, "allocations": rows,
            "notice": "planned allocation only — no budget change is applied"}


@adpilot_router.post("/target-acos")
def adpilot_target_acos(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    for req in ("product_cost", "amazon_price"):
        if req not in body:
            raise HTTPException(status_code=400, detail=f"{req} is required")
    result = ad_pilot.compute_target_acos(
        float(body["product_cost"]), float(body["amazon_price"]),
        referral_fee_pct=float(body.get("referral_fee_pct", 15.0)),
        fba_fee=float(body.get("fba_fee", 0.0)),
        desired_profit_margin=float(body.get("desired_profit_margin", 20.0)))
    return {"ok": True, **result}


# ---------------------------------------------------------------------------
# Capabilities  — /api/creative/*


capabilities_router = APIRouter(prefix="/api/creative", tags=["creative"])

_CREATIVE_SERVICES = [
    {"id": "creativestudio", "room": "/creative-studio", "label": "Creative Studio",
     "lanes": ["exact-text mockup", "scene generation", "edit"],
     "backend": "creative/", "status": "local"},
    {"id": "listingforge", "room": "/listingforge", "label": "ListingForge",
     "lanes": ["/api/listing-forge/*"], "backend": "listing_forge.py", "status": "local"},
    {"id": "socialpulse", "room": "/socialpulse", "label": "SocialPulse",
     "lanes": ["/api/social/*"], "backend": "social_pulse.py", "status": "local"},
    {"id": "adpilot", "room": "/adpilot", "label": "AdPilot",
     "lanes": ["/api/ad-pilot/*"], "backend": "ad_pilot.py", "status": "local (planning-only)"},
]


@capabilities_router.get("/capabilities")
def capabilities() -> Dict[str, Any]:
    return {
        "ok": True,
        "services": _CREATIVE_SERVICES,
        "providers": providers.provider_status(),
        "storage": storage.storage_status(),
        "moderation": moderation.policy(),
        "policy": providers.policy(),
    }


# ---------------------------------------------------------------------------
# Asset registry + export bundles — /api/creative/assets*, /api/creative/bundles


assets_router = APIRouter(prefix="/api/creative", tags=["creative-assets"])


@assets_router.get("/assets")
def list_assets(kind: Optional[str] = None, product: Optional[str] = None,
                container: Optional[str] = None, limit: int = 500) -> Dict[str, Any]:
    return {
        "ok": True,
        "assets": asset_store.list_assets(kind=kind, product=product,
                                          container=container, limit=limit),
        "sets": asset_store.sets(),
        "index": str(asset_store._index_path()),
        "storage": storage.storage_status(),
    }


@assets_router.post("/assets/scan")
def scan_assets() -> Dict[str, Any]:
    """Register any media files already on disk that are not yet indexed."""
    return asset_store.scan()


@assets_router.post("/assets/register")
def register_asset(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    key = body.get("key")
    if not key:
        raise HTTPException(status_code=400, detail="key is required")
    asset = asset_store.register(
        key=key, url=body.get("url"), kind=body.get("kind", "image"),
        product=body.get("product"), container=body.get("container"),
        tags=body.get("tags"), meta=body.get("meta"))
    return {"ok": True, "asset": asset}


@assets_router.get("/bundles")
def list_bundles() -> Dict[str, Any]:
    return {"ok": True, "bundles": asset_store.list_assets(kind="bundle")}


@assets_router.post("/bundles")
def create_bundle(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    ids = body.get("asset_ids")
    if not isinstance(ids, list) or not ids:
        raise HTTPException(status_code=400, detail="asset_ids (array) is required")
    return bundle_store.create_bundle(ids, name=body.get("name", "creative-bundle"))


@assets_router.post("/assets/upload")
def upload_asset(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Upload/register an external asset (base64) into the local registry."""
    data_b64 = body.get("data_base64")
    name = body.get("filename")
    if not data_b64 or not name:
        raise HTTPException(status_code=400, detail="data_base64 and filename are required")
    try:
        raw = base64.b64decode(str(data_b64).split(",", 1)[-1])
    except Exception:
        raise HTTPException(status_code=400, detail="data_base64 is not valid base64")
    safe = Path(name).name
    info = storage.get_backend().put(safe, raw, body.get("content_type", "image/png"))
    asset = asset_store.register(
        key=safe, url=f"/api/creative/file/{safe}", kind=body.get("kind", "image"),
        product=body.get("product"), container=body.get("container"),
        meta={"source": "upload"})
    return {"ok": True, "asset": asset, "bytes": info["bytes"]}


# ---------------------------------------------------------------------------
# Cloud media (gated) + video (gated) — /api/creative/cloud*, /api/creative/video*


media_router = APIRouter(prefix="/api/creative", tags=["creative-media"])


@media_router.post("/cloud/generate")
def cloud_generate(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    prompt = body.get("prompt")
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    provider = body.get("provider", "fal")
    _screen({"prompt": prompt})
    out = storage._local_root() / f"cloud_{provider}_{_stamp()}.png"
    try:
        res = cloud.generate(prompt, provider, out, model=body.get("model"),
                             image_size=body.get("image_size", "1024x1024"),
                             num_images=int(body.get("num_images", 1)))
    except cloud.ProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"ok": True, **res, "url": f"/api/creative/file/{out.name}"}


@media_router.get("/video/models")
def video_models() -> Dict[str, Any]:
    return {"ok": True, **video.video_catalog()}


@media_router.get("/video/estimate")
def video_estimate(model: str, seconds: float = 5.0, audio: bool = False) -> Dict[str, Any]:
    return {"ok": True, "model": model, "seconds": seconds,
            "cost_estimate": video.estimate_video_cost(model, seconds, audio=audio)}


@media_router.post("/video/generate")
def video_generate(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    prompt = body.get("prompt")
    model = body.get("model", "kling-2.6-pro")
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    _screen({"prompt": prompt})
    try:
        res = video.generate_video(model, prompt, image_url=body.get("image_url"),
                                   duration=int(body.get("duration", 5)),
                                   aspect=body.get("aspect", "9:16"))
    except cloud.ProviderUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, **res}


# ---------------------------------------------------------------------------
# Write-action approvals — /api/creative/approvals*


approvals_router = APIRouter(prefix="/api/creative", tags=["creative-approvals"])


@approvals_router.get("/approvals")
def list_approvals(status: Optional[str] = None) -> Dict[str, Any]:
    return {"ok": True, "posture": approvals.posture(),
            "requests": approvals.list_requests(status)}


@approvals_router.post("/approvals")
def create_approval(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    kind = body.get("kind")
    if kind not in approvals.WRITE_KINDS:
        raise HTTPException(status_code=400,
                            detail=f"kind must be one of {sorted(approvals.WRITE_KINDS)}")
    rec = approvals.request(kind, body.get("payload") or {},
                            requested_by=body.get("requested_by", "operator"),
                            note=body.get("note", ""))
    return {"ok": True, "request": rec}


@approvals_router.post("/approvals/{rid}/decide")
def decide_approval(rid: str, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    try:
        rec = approvals.decide(rid, approve=bool(body.get("approve")),
                               by=body.get("by", "operator"), note=body.get("note", ""))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"ok": True, "request": rec}


@approvals_router.post("/approvals/{rid}/execute")
def execute_approval(rid: str) -> Dict[str, Any]:
    return approvals.execute(rid)


# ---------------------------------------------------------------------------
# Listing Guardian + Competitor Monitor — local, no live source required


guardian_router = APIRouter(prefix="/api/listing-guardian", tags=["listing-guardian"])


@guardian_router.post("/audit")
def guardian_audit(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    listing = body.get("listing") if isinstance(body.get("listing"), dict) else body
    _screen({"title": listing.get("title", ""), "bullets": listing.get("bullets") or [],
             "description": listing.get("description", "")})
    return listing_guardian.audit(listing)


competitor_router = APIRouter(prefix="/api/competitor-monitor", tags=["competitor-monitor"])


@competitor_router.get("/watchlist")
def cm_list() -> Dict[str, Any]:
    return {"ok": True, "entries": competitor_monitor.list_watch(),
            "overview": competitor_monitor.overview()}


@competitor_router.post("/watchlist")
def cm_add(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    entry = competitor_monitor.add(name, url=body.get("url", ""),
                                   asin=body.get("asin", ""), notes=body.get("notes", ""))
    return {"ok": True, "entry": entry}


@competitor_router.delete("/watchlist/{wid}")
def cm_remove(wid: str) -> Dict[str, Any]:
    return {"ok": True, "removed": competitor_monitor.remove(wid)}


@competitor_router.post("/watchlist/{wid}/snapshot")
def cm_snapshot(wid: str, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    try:
        snap = competitor_monitor.snapshot(wid, data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"ok": True, "snapshot": snap, "deltas": competitor_monitor.deltas(wid)}


@competitor_router.get("/watchlist/{wid}/deltas")
def cm_deltas(wid: str) -> Dict[str, Any]:
    try:
        return {"ok": True, **competitor_monitor.deltas(wid)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
