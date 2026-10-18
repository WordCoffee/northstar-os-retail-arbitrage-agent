"""Chat tool registry (S2) — in-process tools for the Simple-mode Master Brain.

Design doctrine (locked in research/master_plan_v2_sweep_20261016/REPORT.md):
  • Hand-rolled registry — no agent framework. ~5 fixed tools, one local model.
  • Argument validation follows the outputguard pattern (MIT): validate → repair
    → surface a truthful error the model can react to. Our own implementation.
  • Handlers are thin wrappers over the EXISTING in-process services
    (design_studio_print, design_studio_agent, studio_generation). No URLs are
    ever guessed; no provider keys; no cost beyond the operator's own machine.
  • Progress: handlers may call ctx["progress"](pct|None, label); the ComfyUI
    render lane forwards real /ws progress through studio_generation.

Honesty boundaries:
  • An unarmed engine yields ok=False with the real reason — never a pretend.
  • generate_image renders SURFACES ONLY (the engine's no-text suffix stands);
    text/logo/legal content is authored as structured layers, never painted.
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

MAX_TOOL_STEPS = 4  # bounded tool rounds per chat turn


def _run_async(coro):
    """Run one coroutine to completion from a sync tool handler.

    Tool handlers execute in worker threads (chat_router) — usually no event
    loop is running, so asyncio.run works. If a loop IS running on this
    thread, the coroutine runs on a fresh thread to avoid "already running".
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        box: Dict[str, Any] = {}

        def _worker():
            box["r"] = asyncio.run(coro)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join()
        return box.get("r") or {"ok": False, "error": "async call failed", "assets": []}
    return asyncio.run(coro)


# ── Argument parsing + validation (outputguard-style) ───────────────────────

class ToolValidationError(ValueError):
    """Raised when tool arguments cannot be repaired into a valid shape."""


def parse_arguments(raw: Any) -> Dict[str, Any]:
    """Accept a dict, a JSON string, or a fenced/loose JSON string.

    Repairs applied (bounded, deterministic): ```json fences stripped, smart
    quotes normalised, a single trailing comma allowed. Anything still
    unparsable raises instead of guessing.
    """
    if isinstance(raw, dict):
        return raw
    if raw is None or raw == "":
        return {}
    s = str(raw).strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    if not s:
        return {}
    try:
        parsed = json.loads(s)
    except ValueError:
        fixed = re.sub(r",\s*([}\]])", r"\1", s)
        fixed = fixed.replace("\u201c", '"').replace("\u201d", '"')
        try:
            parsed = json.loads(fixed)
        except ValueError as exc:
            raise ToolValidationError(f"arguments are not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ToolValidationError("arguments must be a JSON object")
    return parsed


def validate_tool_arguments(spec: dict, args: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce + check arguments against the spec's JSON-schema subset.

    Checks: required presence, primitive coercion, numeric bounds, enums,
    defaults. Unknown keys are dropped (model noise), returned for logging.
    """
    schema = spec.get("parameters") or {}
    props: Dict[str, dict] = schema.get("properties") or {}
    missing = [k for k in (schema.get("required") or [])
               if k not in args or args[k] in (None, "")]
    if missing:
        raise ToolValidationError(
            f"missing required argument(s): {', '.join(missing)}. "
            f"Expected: {json.dumps({k: props.get(k, {}).get('type', 'any') for k in (schema.get('required') or [])})}")
    out: Dict[str, Any] = {}
    for key, value in args.items():
        if key not in props:
            continue  # unknown key: dropped, never forwarded
        p = props[key]
        t = p.get("type")
        if value is None:
            continue
        if t in ("number", "integer"):
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise ToolValidationError(f"{key} must be numeric")
            if t == "integer":
                value = int(value)
            lo, hi = p.get("minimum"), p.get("maximum")
            if lo is not None and value < lo:
                raise ToolValidationError(f"{key} is below the minimum ({lo})")
            if hi is not None and value > hi:
                raise ToolValidationError(f"{key} is above the maximum ({hi})")
        elif t == "string" and not isinstance(value, str):
            value = str(value)
        elif t == "boolean" and not isinstance(value, bool):
            value = bool(value)
        enum = p.get("enum")
        if enum and value not in enum:
            raise ToolValidationError(f"{key} must be one of {enum}")
        out[key] = value
    for key, p in props.items():
        if key not in out and "default" in p:
            out[key] = p["default"]
    return out


def normalize_tool_calls(raws: Optional[List[Any]]) -> List[Dict[str, Any]]:
    """Merge possibly-fragmented Ollama tool_call entries into call records.

    Fragments carry an ``index``; name arrives once, argument JSON streams in
    pieces. No-index fragments append to the current slot; a repeated name
    starts a new slot. Returns [{name, raw_args, obj_args}] — argument
    validation happens later in run_tool (so a bad call yields an honest error
    the model can read).
    """
    slots: List[Dict[str, Any]] = []
    for tc in raws or []:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") or {}
        idx = tc.get("index")
        name = fn.get("name")
        slot = None
        if idx is not None:
            while len(slots) <= int(idx):
                slots.append({"name": "", "raw": "", "obj": None})
            slot = slots[int(idx)]
        elif name and slots and not slots[-1]["name"]:
            slot = slots[-1]
        elif name:
            slot = None  # new named call (also when name repeats)
        else:
            slot = slots[-1] if slots else None
        if slot is None:
            slot = {"name": "", "raw": "", "obj": None}
            slots.append(slot)
        if name:
            slot["name"] = name
        arguments = fn.get("arguments")
        if isinstance(arguments, str):
            slot["raw"] += arguments
        elif isinstance(arguments, dict):
            slot["obj"] = arguments
        elif arguments is not None:
            slot["raw"] += str(arguments)
    out = []
    for slot in slots:
        if not slot["name"]:
            continue
        out.append({"name": slot["name"], "raw_args": slot["raw"], "obj_args": slot["obj"]})
    return out


# ── Tool handlers ────────────────────────────────────────────────────────────
# ctx = {"db", "account_id", "session_id", "project_id", "progress", "cancel"}

def _out_dir() -> Path:
    d = Path(__file__).resolve().parent / "data" / "studio_generated"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _t_system_status(args, ctx) -> dict:
    import studio_generation as sg
    st = sg.engine_status()
    return {
        "ok": True,
        "summary": (
            f"Local engine: {'armed' if st.get('armed') else 'not armed'} "
            f"({st.get('url')}); chat model ready via Ollama."
        ),
        "assets": [],
        "data": st,
    }


def _t_list_templates(args, ctx) -> dict:
    from design_studio_print import TEMPLATES
    rows = [{"id": t["id"], "name": t["name"], "kind": t["kind"],
             "editable": t["editable"]} for t in TEMPLATES]
    return {
        "ok": True,
        "summary": f"{len(rows)} parametric dieline templates available.",
        "assets": [],
        "data": {"templates": rows},
    }


def _t_design_brief(args, ctx) -> dict:
    from design_studio_agent import build_brief
    brief = build_brief(args["message"], args.get("product"))
    return {
        "ok": True,
        "summary": (
            f"Structured brief for '{brief['product'].get('title') or 'untitled'}': "
            f"palette {brief['palette']['name']}; suggested dielines "
            f"{', '.join(brief['format']['suggested_templates'])}."
        ),
        "assets": [],
        "data": brief,
    }


def _t_create_dieline(args, ctx) -> dict:
    from design_studio_print import build_from_template, render_svg, render_pdf
    try:
        build = build_from_template(args["template_id"], args.get("params"))
    except ValueError as exc:
        return {"ok": False, "summary": "Dieline parameters rejected.",
                "error": str(exc), "assets": []}
    svg = render_svg(build)
    pdf = render_pdf(build)
    assets: List[dict] = []
    db = ctx.get("db")
    acct = ctx.get("account_id")
    if args.get("persist", True) and db is not None and acct:
        for kind, payload, mime, ext in (
                ("svg", svg.encode("utf-8"), "image/svg+xml", "svg"),
                ("pdf", pdf, "application/pdf", "pdf")):
            fname = f"dieline_{uuid.uuid4().hex}.{ext}"
            (_out_dir() / fname).write_bytes(payload)
            aid = db.design_studio.assets.create({
                "account_id": acct,
                "project_id": ctx.get("project_id"),
                "name": f"{args.get('name') or build.get('title')} ({kind.upper()})",
                "asset_type": "dieline",
                "mime_type": mime,
                "storage_key": fname,
                "size_bytes": len(payload),
                "metadata": {"print_engine": {
                    "template_title": build.get("title"),
                    "meta": build.get("meta", {}),
                    "layers": ["bleed", "marks", "trim", "fold", "safe", "info"],
                    "format": kind,
                    "via": "chat-tool create_dieline",
                }, "note": build.get("note")},
            })
            assets.append({"id": aid, "kind": "dieline",
                           "url": f"/api/design-studio/assets/{aid}/file",
                           "name": f"{build.get('title')} ({ext.upper()})"})
    return {
        "ok": True,
        "summary": (f"Built {build.get('title')} — "
                    f"{build['width_mm']}x{build['height_mm']}mm layered dieline "
                    f"(bleed/trim/fold/safe/marks/info). Draft geometry: confirm "
                    f"dimensions with the manufacturer."),
        "assets": assets,
        "data": {"template_id": args["template_id"], "meta": build.get("meta")},
    }


def _t_generate_image(args, ctx) -> dict:
    import studio_generation as sg
    st = sg.engine_status()
    if not st.get("armed"):
        return {"ok": False, "summary": "The local media engine is not armed.",
                "error": f"{st.get('note')} (Set MEDIA_GEN_LIVE=1 and start ComfyUI at {st.get('url')}.)",
                "assets": []}
    progress: Callable[[Optional[int], str], None] = ctx.get("progress") or (lambda p, l: None)
    try:
        progress(0, "preparing render")
        out = sg.generate_image(
            prompt=args["prompt"], width=args.get("width"), height=args.get("height"),
            tier=args.get("tier") or "draft", on_progress=progress)
    except Exception as exc:  # noqa: BLE001 - surfaced to the model verbatim, scrubbed
        return {"ok": False, "summary": "The local render failed before producing an image.",
                "error": str(exc)[:400], "assets": []}
    fname = f"{uuid.uuid4().hex}.png"
    (_out_dir() / fname).write_bytes(out["bytes"])
    db = ctx.get("db")
    acct = ctx.get("account_id")
    aid = None
    if db is not None and acct:
        aid = db.design_studio.assets.create({
            "account_id": acct,
            "project_id": ctx.get("project_id"),
            "name": f"chat render - {out['model']}",
            "asset_type": "generated-image",
            "mime_type": out["mime"],
            "storage_key": fname,
            "width": out.get("width"), "height": out.get("height"),
            "size_bytes": len(out["bytes"]),
            "metadata": {"generation": {
                "provider": "comfyui", "model": out["model"],
                "tier": args.get("tier") or "draft", "purpose": "chat-tool",
                "prompt": args["prompt"], "seed": out.get("seed"),
                "lane": "chat",
            }, "note": ("Rendered locally on the operator's machine via ComfyUI. "
                        "Surfaces only - no text, logos or legal copy.")},
        })
    assets = [{
        "id": aid, "kind": "image",
        "url": f"/api/design-studio/assets/{aid}/file" if aid else None,
        "name": f"generated image ({out['model']})",
        "width": out.get("width"), "height": out.get("height"),
    }]
    return {
        "ok": True,
        "summary": (f"Rendered a {out.get('width')}x{out.get('height')} image locally "
                    f"({out['model']}, seed {out.get('seed')}). Surfaces only — text and "
                    f"logos are not painted into images."),
        "assets": assets,
        "data": {"model": out["model"], "seed": out.get("seed")},
    }


def _t_seo_profile(args, ctx) -> dict:
    """Show the account's canonical Brand SEO Profile (V3 S7) as an AG-UI card.

    With `brand_key`, show that brand's current profile; without it, list the
    account's profiles. Honest when nothing exists yet — it never invents a
    profile."""
    db = ctx.get("db")
    acct = ctx.get("account_id")
    profiles = getattr(getattr(db, "seo", None), "profiles", None)
    if profiles is None:
        return {"ok": False, "summary": "The SEO profile store is unavailable.",
                "error": "no SEO store in this context", "assets": []}
    key = str(args.get("brand_key") or "").strip().lower()
    if key:
        head = profiles.get_by_brand_key(acct, key)
        if not head:
            return {"ok": False, "summary": f"No brand SEO profile for '{key}'.",
                    "error": f"no profile with brand_key '{key}'", "assets": []}
        full = profiles.get_profile(head["id"], account_id=acct)
        body = full.get("body") or {}
        rows = [
            {"label": "brand", "value": full["brand_key"]},
            {"label": "version", "value": f"v{full['current_version']} of {full['version_count']}"},
        ]
        kc = body.get("keyword_clusters")
        if isinstance(kc, dict):
            terms = kc.get("head") or kc.get("heads") or []
            rows.append({"label": "head terms", "value": ", ".join(str(t) for t in terms[:8]) or "—"})
        comps = body.get("competitors") or []
        rows.append({"label": "competitors", "value": ", ".join(str(c) for c in comps[:8]) or "—"})
        return {
            "ok": True,
            "summary": f"Brand SEO profile '{full['brand_key']}' (v{full['current_version']}).",
            "assets": [],
            "data": {
                "card": {
                    "title": "Brand SEO profile",
                    "rows": rows,
                    "action": {"label": "Score a listing",
                               "message": f"Score our latest listing against the {full['brand_key']} SEO profile."},
                },
                "brand_key": full["brand_key"], "version": full["current_version"],
            },
        }
    items = profiles.list_profiles(acct, limit=20)
    rows = [{"label": p["brand_key"], "value": f"v{p['current_version']}"} for p in items] \
        or [{"label": "no profiles yet", "value": "—"}]
    return {
        "ok": True,
        "summary": f"{len(items)} brand SEO profile(s).",
        "assets": [],
        "data": {
            "card": {"title": "Brand SEO profiles", "rows": rows[:12],
                     "action": {"label": "Create a profile",
                                "message": "Create a brand SEO profile for our brand."}},
            "profiles": [{"brand_key": p["brand_key"], "current_version": p["current_version"]}
                         for p in items],
        },
    }


def _t_seo_check(args, ctx) -> dict:
    """Score content against the brand SEO profile (V3 S7 §5.3).

    Sources of copy, in order: a content surface (`content` + `surface`, used by
    Creative Studio / AdPilot / SocialPulse / SourceScout), a listing's LATEST
    stored revision (`listing_key`/`asin`), or inline title/bullets/backend_
    terms/description. Deterministic keyword coverage — never a rank or volume
    prediction. Honest when there is nothing to score."""
    from seo_score import SURFACES, score_listing, score_text
    db = ctx.get("db")
    acct = ctx.get("account_id")
    profiles = getattr(getattr(db, "seo", None), "profiles", None)
    revisions = getattr(getattr(db, "seo", None), "revisions", None)
    if profiles is None:
        return {"ok": False, "summary": "The SEO profile store is unavailable.",
                "error": "no SEO store in this context", "assets": []}

    brand_key = str(args.get("brand_key") or "").strip().lower()
    if brand_key:
        head = profiles.get_by_brand_key(acct, brand_key)
        if not head:
            return {"ok": False, "summary": f"No brand SEO profile for '{brand_key}'.",
                    "error": f"no profile with brand_key '{brand_key}'", "assets": []}
        profile = profiles.get_profile(head["id"], account_id=acct)
    else:
        items = profiles.list_profiles(acct, limit=2)
        if not items:
            return {"ok": False, "summary": "No brand SEO profile yet — create one first.",
                    "error": "no profiles for this account", "assets": []}
        if len(items) > 1:
            return {"ok": False, "summary": "More than one brand profile — pass brand_key.",
                    "error": "ambiguous brand; pass brand_key", "assets": []}
        profile = profiles.get_profile(items[0]["id"], account_id=acct)

    surface = str(args.get("surface") or "").strip().lower()
    content = args.get("content")
    if content is not None and str(content).strip():
        if surface and surface not in SURFACES:
            return {"ok": False, "summary": f"Unknown surface '{surface}'.",
                    "error": f"surface must be one of {sorted(SURFACES)}", "assets": []}
        label = SURFACES.get(surface or "creative", SURFACES["creative"])["label"]
        result = score_text(profile.get("body") or {}, content)
        source = f"{label} copy"
    else:
        inline = any(args.get(k) for k in ("title", "bullets", "backend_terms", "description"))
        if inline:
            listing = {"title": args.get("title"), "bullets": args.get("bullets"),
                       "backend_terms": args.get("backend_terms"),
                       "description": args.get("description")}
            source = "inline listing copy"
        else:
            key = str(args.get("listing_key") or args.get("asin") or "").strip().lower()
            if not key:
                return {"ok": False, "summary": "Give me a listing or content to check.",
                        "error": "provide content, listing_key/asin, or inline copy", "assets": []}
            if revisions is None:
                return {"ok": False, "summary": "Listing revisions are unavailable.",
                        "error": "no revisions store", "assets": []}
            latest = revisions.get_latest(acct, key)
            if not latest:
                return {"ok": False, "summary": f"No listing revisions for '{key}'.",
                        "error": f"no revisions for listing_key '{key}'", "assets": []}
            listing = latest
            source = f"{key} revision {latest['revision']}"
        result = score_listing(profile.get("body") or {}, listing)

    score = result["score"]
    total = result["head_total"] + result["body_total"]
    rows = [
        {"label": "score", "value": "—" if score is None else f"{score}/100"},
        {"label": "profile", "value": f"{profile['brand_key']} v{profile['current_version']}"},
        {"label": "checked", "value": source},
        {"label": "matched", "value": f"{result['matched_count']} of {total} terms"},
    ]
    head_missing = [m["term"] for m in result["missing"] if m["section"] == "head"]
    if head_missing:
        rows.append({"label": "missing head", "value": ", ".join(head_missing[:8])})
    if result["violations"]:
        rows.append({"label": "prohibited", "value": ", ".join(result["violations"][:8])})
    if result["competitor_mentions"]:
        rows.append({"label": "competitor names", "value": ", ".join(result["competitor_mentions"][:8])})

    summary = ("No keyword clusters to score against in the profile." if score is None else
               f"SEO coverage {score}/100 against {profile['brand_key']} "
               f"v{profile['current_version']}.")
    return {
        "ok": True,
        "summary": summary,
        "assets": [],
        "data": {
            "card": {"title": "SEO check", "rows": rows,
                     "action": {"label": "List missing terms",
                                "message": "List every profile keyword missing from this copy."}},
            "score": score,
            "matched": result["matched"],
            "missing": result["missing"],
            "violations": result["violations"],
            "caveats": result["caveats"],
        },
    }


def _t_seo_propose(args, ctx) -> dict:
    """Propose profile keyword additions from imported SQP rows (V3 S7 §5.4).

    Read-only: returns candidates derived from measured Search Query Performance
    rows the operator already imported. It never edits the profile; approving is
    an operator action that appends a new version. Scope the data with `asin`(s)
    — the SQP table has no account column."""
    from seo_learn import propose_from_sqp
    db = ctx.get("db")
    acct = ctx.get("account_id")
    seo = getattr(db, "seo", None)
    profiles = getattr(seo, "profiles", None)
    sqp = getattr(seo, "sqp", None)
    if profiles is None or sqp is None:
        return {"ok": False, "summary": "The SEO store is unavailable.",
                "error": "no SEO store in this context", "assets": []}

    brand_key = str(args.get("brand_key") or "").strip().lower()
    if brand_key:
        head = profiles.get_by_brand_key(acct, brand_key)
        if not head:
            return {"ok": False, "summary": f"No brand SEO profile for '{brand_key}'.",
                    "error": f"no profile with brand_key '{brand_key}'", "assets": []}
        profile = profiles.get_profile(head["id"], account_id=acct)
    else:
        items = profiles.list_profiles(acct, limit=2)
        if not items:
            return {"ok": False, "summary": "No brand SEO profile yet — create one first.",
                    "error": "no profiles for this account", "assets": []}
        if len(items) > 1:
            return {"ok": False, "summary": "More than one brand profile — pass brand_key.",
                    "error": "ambiguous brand; pass brand_key", "assets": []}
        profile = profiles.get_profile(items[0]["id"], account_id=acct)

    asins = args.get("asins") or ([args["asin"]] if args.get("asin") else [])
    asins = [str(a).strip() for a in asins if str(a).strip()]
    if not asins:
        return {"ok": False, "summary": "Name the ASIN(s) the imported data covers.",
                "error": "provide asin or asins to scope the search-query data", "assets": []}

    rows = sqp.rows(asins=asins, limit=int(args.get("row_limit") or 500))
    out = propose_from_sqp(profile.get("body") or {}, rows, limit=int(args.get("limit") or 12))

    rows_card = []
    for p in out["proposals"]:
        bits = []
        if p["search_frequency_rank"] is not None:
            bits.append(f"SFR {p['search_frequency_rank']}")
        bits.append(f"{p['impressions']} impressions")
        if p["clicks"]:
            bits.append(f"{p['clicks']} clicks")
        rows_card.append({"label": p["term"], "value": ", ".join(bits)})
    if not rows_card:
        rows_card.append({"label": "no new terms",
                          "value": "imported queries are already covered by the profile"})

    return {
        "ok": True,
        "summary": (f"{out['proposal_count']} candidate term(s) from {out['considered_query_count']} "
                    f"imported queries (proposals only — nothing was changed)."),
        "assets": [],
        "data": {
            "card": {"title": "SEO proposals", "rows": rows_card,
                     "action": {"label": "Apply a proposal",
                                "message": "Append these terms to the brand SEO profile as a new version."}},
            "proposals": out["proposals"],
            "caveats": out["caveats"],
        },
    }


def _seo_profile_or_error(ctx, brand_key):
    """Resolve the account's brand SEO profile, or return an honest error dict.

    Returns (profile, None) on success, or (None, error_result) otherwise. Shared
    by the S7 §5.3 pipeline tools so their absence handling cannot drift."""
    db = ctx.get("db")
    acct = ctx.get("account_id")
    profiles = getattr(getattr(db, "seo", None), "profiles", None)
    if profiles is None:
        return None, {"ok": False, "summary": "The SEO profile store is unavailable.",
                      "error": "no SEO store in this context", "assets": []}
    bk = str(brand_key or "").strip().lower()
    if bk:
        head = profiles.get_by_brand_key(acct, bk)
        if not head:
            return None, {"ok": False, "summary": f"No brand SEO profile for '{bk}'.",
                          "error": f"no profile with brand_key '{bk}'", "assets": []}
        return profiles.get_profile(head["id"], account_id=acct), None
    items = profiles.list_profiles(acct, limit=2)
    if not items:
        return None, {"ok": False, "summary": "No brand SEO profile yet — create one first.",
                      "error": "no profiles for this account", "assets": []}
    if len(items) > 1:
        return None, {"ok": False, "summary": "More than one brand profile — pass brand_key.",
                      "error": "ambiguous brand; pass brand_key", "assets": []}
    return profiles.get_profile(items[0]["id"], account_id=acct), None


def _t_seo_negatives(args, ctx) -> dict:
    """AdPilot hook (S7 §5.3): split search terms into negatives / harvest.

    Deterministic matching against the operator's own profile. Writes nothing."""
    from seo_ops import classify_search_terms
    profile, err = _seo_profile_or_error(ctx, args.get("brand_key"))
    if err:
        return err
    out = classify_search_terms(profile.get("body") or {}, args.get("terms"))
    rows = [
        {"label": "negatives", "value": str(out["negative_count"])},
        {"label": "harvest candidates", "value": str(out["harvest_count"])},
        {"label": "ignored", "value": str(len(out["ignored"]))},
    ]
    if out["negatives"]:
        rows.append({"label": "negative list",
                     "value": ", ".join(n["term"] for n in out["negatives"][:12])})
    if out["harvest"]:
        rows.append({"label": "harvest list",
                     "value": ", ".join(h["term"] for h in out["harvest"][:12])})
    return {
        "ok": True,
        "summary": (f"{out['negative_count']} negative(s), {out['harvest_count']} harvest "
                    f"candidate(s) against {profile['brand_key']} v{profile['current_version']}."),
        "assets": [],
        "data": {
            "card": {"title": "AdPilot term triage", "rows": rows,
                     "action": {"label": "Explain the split",
                                "message": "Why are these terms negatives vs harvest candidates?"}},
            "negatives": out["negatives"], "harvest": out["harvest"],
            "ignored": out["ignored"], "caveats": out["caveats"],
        },
    }


def _t_seo_retitle(args, ctx) -> dict:
    """SourceScout / ListingForge hook (S7 §5.3): normalise a title to the profile.

    Deterministic rewrite toward the operator's own head terms, within a budget.
    Returns a suggestion; it never writes a listing."""
    from seo_ops import retitle
    profile, err = _seo_profile_or_error(ctx, args.get("brand_key"))
    if err:
        return err
    out = retitle(profile.get("body") or {}, args.get("title"),
                  max_len=int(args.get("max_len") or 200))
    rows = [
        {"label": "suggested", "value": out["title"]},
        {"label": "length", "value": f"{out['length']} / {out['max_len']}"},
    ]
    if out["missing_head"]:
        rows.append({"label": "missing head", "value": ", ".join(out["missing_head"][:8])})
    if out["changes"]:
        rows.append({"label": "changes", "value": "; ".join(out["changes"])})
    return {
        "ok": True,
        "summary": f"Retitled toward {profile['brand_key']} v{profile['current_version']}.",
        "assets": [],
        "data": {
            "card": {"title": "Suggested title", "rows": rows,
                     "action": {"label": "Why these changes?",
                                "message": "Explain this retitle against the brand profile."}},
            "title": out["title"], "original": out["original"],
            "changes": out["changes"], "caveats": out["caveats"],
        },
    }


def _t_corpus_search(args, ctx) -> dict:
    """Retrieve from the local curated corpus (S8). Read-only.

    Returns the top matches from the operator's own local index, each with its
    source and licence AS REPORTED. Honest when empty or unavailable."""
    db = ctx.get("db")
    corpus = getattr(db, "corpus", None)
    if corpus is None:
        return {"ok": False, "summary": "The corpus index is unavailable.",
                "error": "no corpus store in this context", "assets": []}
    query = " ".join(str(args.get("query") or "").split())
    if not query:
        return {"ok": False, "summary": "Give me something to search for.",
                "error": "query is required", "assets": []}
    source = str(args.get("source") or "").strip() or None
    caveats = ["Third-party metadata from local index files; licence is as reported.",
               "Deterministic keyword search — not a semantic/vector lookup."]
    try:
        rows = corpus.search(query, limit=int(args.get("limit") or 8), source=source)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": "The corpus search failed.",
                "error": str(exc)[:200], "assets": []}

    if not rows:
        return {"ok": True, "summary": f"No corpus matches for '{query}'.",
                "assets": [],
                "data": {"card": {"title": "Corpus search",
                                  "rows": [{"label": "no matches", "value": query}]},
                         "matches": [], "caveats": caveats}}

    card_rows = []
    for r in rows[:8]:
        bits = [b for b in (r.get("source"), r.get("kind"), r.get("license")) if b]
        card_rows.append({"label": str(r.get("title") or r.get("source_id") or "")[:80],
                          "value": " · ".join(str(b) for b in bits)})
    return {
        "ok": True,
        "summary": f"{len(rows)} corpus match(es) for '{query}'.",
        "assets": [],
        "data": {
            "card": {"title": "Corpus search", "rows": card_rows,
                     "action": {"label": "Open the top source",
                                "message": "Show the provenance for the top corpus match."}},
            "matches": rows, "caveats": caveats,
        },
    }


def _t_corpus_vector_search(args, ctx) -> dict:
    """Semantic (embedding) search over the curated corpus (V4.1 §5.4). Read-only.

    Uses the local qwen3-embedding:0.6b lane + sqlite-vec cosine index. Honest when
    the lane or the vector store is unavailable — never fabricates a match."""
    import corpus_drift
    query = " ".join(str(args.get("query") or "").split())
    if not query:
        return {"ok": False, "summary": "Give me something to search for.",
                "error": "query is required", "assets": []}
    source = str(args.get("source") or "").strip() or None
    try:
        out = corpus_drift.vector_search(
            query, limit=int(args.get("limit") or 8), source=source,
            store=ctx.get("vector_store"), lane=ctx.get("embed_lane"))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": "The semantic corpus search failed.",
                "error": str(exc)[:200], "assets": []}

    caveats = out.get("caveats", [])
    if not out.get("available"):
        reason = str(out.get("reason") or "embedding lane unavailable")[:160]
        return {
            "ok": True,
            "summary": f"Semantic search is unavailable: {reason}",
            "assets": [],
            "data": {"card": {"title": "Corpus (semantic)",
                              "rows": [{"label": "unavailable", "value": reason}]},
                     "matches": [], "caveats": caveats},
        }
    matches = out.get("matches", [])
    if not matches:
        return {
            "ok": True, "summary": f"No semantic corpus matches for '{query}'.", "assets": [],
            "data": {"card": {"title": "Corpus (semantic)",
                              "rows": [{"label": "no matches", "value": query}]},
                     "matches": [], "caveats": caveats},
        }
    card_rows = []
    for m in matches[:8]:
        bits = [b for b in (m.get("source"), m.get("kind"), m.get("license")) if b]
        label = str(m.get("title") or m.get("source_id") or "")[:80]
        card_rows.append({"label": label, "value": " · ".join(str(b) for b in bits)})
    return {
        "ok": True,
        "summary": f"{len(matches)} semantic corpus match(es) for '{query}'.",
        "assets": [],
        "data": {
            "card": {"title": "Corpus (semantic)", "rows": card_rows,
                     "action": {"label": "Open the top source",
                                "message": "Show provenance for the top semantic match."}},
            "matches": matches, "caveats": caveats,
        },
    }


def _t_corpus_drift(args, ctx) -> dict:
    """Report MEASURED embedding drift: current corpus vectors vs historical SQP
    query vectors (V4.1 §5.4). Read-only; it never predicts a trend or a cause."""
    import corpus_drift
    try:
        rep = corpus_drift.drift_report(store=ctx.get("vector_store"), persist=False)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "summary": "The drift report failed.",
                "error": str(exc)[:200], "assets": []}

    caveats = rep.get("caveats", [])
    if not rep.get("available"):
        reason = str(rep.get("reason") or "insufficient data")[:160]
        return {
            "ok": True,
            "summary": f"Drift is not measurable yet: {reason}",
            "assets": [],
            "data": {"card": {"title": "Embedding drift",
                              "rows": [{"label": "insufficient data", "value": reason}]},
                     "drift": rep, "caveats": caveats},
        }
    rows = [
        {"label": "cosine drift", "value": f"{rep['drift']:.4f}"},
        {"label": "similarity", "value": f"{rep['similarity']:.4f}"},
        {"label": "corpus vectors", "value": str(rep["n_current"])},
        {"label": "SQP vectors", "value": str(rep["n_historical"])},
    ]
    return {
        "ok": True,
        "summary": (f"Drift {rep['drift']:.4f} (similarity {rep['similarity']:.4f}) "
                    f"across {rep['n_current']} corpus / {rep['n_historical']} SQP vectors."),
        "assets": [],
        "data": {"card": {"title": "Embedding drift", "rows": rows},
                 "drift": rep, "caveats": caveats},
    }


def _t_voice_list(args, ctx) -> dict:
    from voicestudio_adapter import get_adapter
    out = _run_async(get_adapter().list_voices())
    if not out.get("ok"):
        return {"ok": False, "summary": "The local voice service is not reachable.",
                "error": out.get("error", "unreachable"), "assets": []}
    data = out.get("data") or {}
    voices = data.get("voices") or []
    rows = [{"id": v.get("id"), "name": v.get("name")}
            for v in voices if isinstance(v, dict)]
    return {
        "ok": True,
        "summary": f"{len(rows)} voice profile(s) available for ad voiceovers.",
        "assets": [],
        "data": {
            "card": {
                "title": "Voice profiles",
                "rows": [{"label": r["name"] or r["id"], "value": r["id"]} for r in rows[:12]] or
                        [{"label": "no voices yet", "value": "—"}],
                "action": {"label": "Clone a voice",
                           "message": "Clone a creator voice for ad consistency."},
            },
            "voices": rows,
        },
    }


def _t_voice_tts(args, ctx) -> dict:
    from voicestudio_adapter import get_adapter
    voice_id = args.get("voice_id") or ""
    if not voice_id:
        return {"ok": False, "summary": "No voice selected.",
                "error": "voice_id is required (see voice_list).", "assets": []}
    text = str(args.get("text") or "").strip()
    if not text:
        return {"ok": False, "summary": "No script to speak.",
                "error": "text is required.", "assets": []}
    out = _run_async(get_adapter().tts(text, voice_id, lang=args.get("lang") or "en"))
    if not out.get("ok"):
        return {"ok": False, "summary": "TTS failed.",
                "error": out.get("error", "unreachable"), "assets": []}
    data = out.get("data") or {}
    return {
        "ok": True,
        "summary": f"Generated a {len(text)}-char voiceover ({out.get('elapsed_ms')} ms).",
        "assets": [],
        "data": {"card": {"title": "Voiceover ready",
                           "rows": [{"label": "voice", "value": voice_id},
                                    {"label": "lang", "value": args.get("lang") or "en"},
                                    {"label": "chars", "value": str(len(text))}],
                           "action": {"label": "Make a variant", "message": "Regenerate that voiceover with a different tone."}},
                "audio_url": data.get("audio_url"), "voice_id": voice_id},
    }


def _t_voice_dub(args, ctx) -> dict:
    from voicestudio_adapter import get_adapter
    text = str(args.get("text") or "").strip()
    target = str(args.get("target_lang") or "").strip()
    if not text or not target:
        return {"ok": False, "summary": "Dubbing needs text + target_lang.",
                "error": "text and target_lang are required.", "assets": []}
    out = _run_async(get_adapter().dub(text, target, voice_id=args.get("voice_id")))
    if not out.get("ok"):
        return {"ok": False, "summary": "Dubbing failed.",
                "error": out.get("error", "unreachable"), "assets": []}
    data = out.get("data") or {}
    return {
        "ok": True,
        "summary": f"Dubbed {len(text)} chars into {target} ({out.get('elapsed_ms')} ms).",
        "assets": [],
        "data": {"card": {"title": f"Dub · {target}",
                           "rows": [{"label": "source chars", "value": str(len(text))},
                                    {"label": "target", "value": target},
                                    {"label": "voice", "value": args.get("voice_id") or "auto"}],
                           "action": {"label": "Dub another", "message": f"Dub that script into another language."}},
                "audio_url": data.get("audio_url"), "target_lang": target},
    }


# ── Registry ─────────────────────────────────────────────────────────────────
TOOLS: Dict[str, dict] = {
    "system_status": {
        "description": "Report the local media engine + chat model status. Read-only.",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "handler": _t_system_status,
    },
    "list_templates": {
        "description": ("List the parametric dieline/label/carton templates the print "
                        "engine can build (id, name, kind, editable params). Read-only."),
        "parameters": {"type": "object", "properties": {}, "required": []},
        "handler": _t_list_templates,
    },
    "design_brief": {
        "description": ("Convert a chat request into a structured packaging design brief "
                        "(palette, suggested dielines, copy blocks, directives, negative "
                        "prompt). Deterministic and offline."),
        "parameters": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "The design request in natural language.", "minLength": 3},
                "product": {"type": "object", "description": "Optional product context {title, category, brand, asin}."},
            },
            "required": ["message"],
        },
        "handler": _t_design_brief,
    },
    "create_dieline": {
        "description": ("Build a layered, dimension-true dieline/label/carton from a template "
                        "id (see list_templates) and persist it as studio assets (SVG+PDF). "
                        "Draft geometry — the summary carries the manufacturer-verification note."),
        "parameters": {
            "type": "object",
            "properties": {
                "template_id": {"type": "string", "description": "Template id from list_templates."},
                "params": {"type": "object", "description": "Editable params (mm) for that template."},
                "name": {"type": "string", "description": "Optional asset name."},
                "persist": {"type": "boolean", "default": True},
            },
            "required": ["template_id"],
        },
        "handler": _t_create_dieline,
    },
    "generate_image": {
        "description": ("Render ONE image locally via ComfyUI (surfaces/photography only). "
                        "Text, logos, weights, barcodes and legal copy are NEVER painted by the "
                        "image model — author those as structured layers instead. Requires the "
                        "media engine armed (MEDIA_GEN_LIVE + ComfyUI)."),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Scene/surface description. No text requests.", "minLength": 3, "maxLength": 2000},
                "width": {"type": "integer", "minimum": 512, "maximum": 1216},
                "height": {"type": "integer", "minimum": 512, "maximum": 1216},
                "tier": {"type": "string", "enum": ["draft", "final"], "default": "draft"},
            },
            "required": ["prompt"],
        },
        "handler": _t_generate_image,
    },
    "seo_check": {
        "description": ("Score content against the brand SEO profile (S7). Copy "
                        "source: a content surface (`content`+`surface`), a listing's "
                        "latest stored revision (listing_key/asin), or inline "
                        "title/bullets/backend_terms. Deterministic keyword "
                        "coverage — never predicts rank or volume."),
        "parameters": {
            "type": "object",
            "properties": {
                "brand_key": {"type": "string", "description": "Brand slug (optional if the account has one profile).", "maxLength": 80},
                "content": {"type": "string", "description": "Free copy to score (any surface: alt text, ad copy, hook, pack title).", "maxLength": 4000},
                "surface": {"type": "string", "description": "Which service's copy: listing | creative | ad | social | source.", "maxLength": 20},
                "listing_key": {"type": "string", "description": "Listing key / ASIN of a stored revision.", "maxLength": 80},
                "asin": {"type": "string", "description": "Alias for listing_key.", "maxLength": 40},
                "title": {"type": "string", "description": "Inline title to score (optional).", "maxLength": 500},
                "bullets": {"type": "string", "description": "Inline bullets to score (optional; newline-separated).", "maxLength": 4000},
                "backend_terms": {"type": "string", "description": "Inline backend search terms (optional).", "maxLength": 2000},
                "description": {"type": "string", "description": "Inline description (optional).", "maxLength": 4000},
            },
            "required": [],
        },
        "handler": _t_seo_check,
    },
    "seo_propose": {
        "description": ("Propose brand SEO profile keyword additions from the "
                        "Search Query Performance rows the operator already "
                        "imported (S7 §5.4). Read-only: candidates only, never an "
                        "edit. Scope with asin/asins. No rank or volume claims."),
        "parameters": {
            "type": "object",
            "properties": {
                "brand_key": {"type": "string", "description": "Brand slug (optional if the account has one profile).", "maxLength": 80},
                "asin": {"type": "string", "description": "ASIN whose imported SQP rows to use.", "maxLength": 40},
                "asins": {"type": "array", "items": {"type": "string", "maxLength": 40}, "description": "ASINs to scope the imported data (alternative to asin)."},
                "limit": {"type": "integer", "description": "Max proposals to return (default 12).", "minimum": 1, "maximum": 50},
            },
            "required": [],
        },
        "handler": _t_seo_propose,
    },
    "seo_profile": {
        "description": ("Show the account's canonical, versioned Brand SEO Profile "
                        "(S7). Pass brand_key to narrow to one brand; omit to list "
                        "all. Read-only; never invents a profile."),
        "parameters": {
            "type": "object",
            "properties": {
                "brand_key": {"type": "string", "description": "Brand slug (optional).", "maxLength": 80},
            },
            "required": [],
        },
        "handler": _t_seo_profile,
    },
    "seo_negatives": {
        "description": ("AdPilot hook (S7): split search terms into negatives "
                        "(match the profile's negative cluster or a competitor) and "
                        "harvest candidates (match a head/body cluster). Deterministic; "
                        "writes nothing."),
        "parameters": {
            "type": "object",
            "properties": {
                "brand_key": {"type": "string", "description": "Brand slug (optional if the account has one profile).", "maxLength": 80},
                "terms": {"type": "string", "description": "Search terms to triage (newline- or comma-separated).", "maxLength": 4000},
            },
            "required": [],
        },
        "handler": _t_seo_negatives,
    },
    "seo_retitle": {
        "description": ("SourceScout / ListingForge hook (S7): normalise a raw title "
                        "toward the profile's head clusters within a length budget. "
                        "Deterministic suggestion; writes nothing."),
        "parameters": {
            "type": "object",
            "properties": {
                "brand_key": {"type": "string", "description": "Brand slug (optional if the account has one profile).", "maxLength": 80},
                "title": {"type": "string", "description": "The raw title to normalise.", "minLength": 1, "maxLength": 500},
                "max_len": {"type": "integer", "description": "Title length budget (default 200).", "minimum": 20, "maximum": 500},
            },
            "required": ["title"],
        },
        "handler": _t_seo_retitle,
    },
    "corpus_search": {
        "description": ("Search the local curated corpus (S8) — the operator's own "
                        "pre-aggregated research index (GitHub/HF sweeps, source "
                        "registries, research docs), each with source + licence as "
                        "reported. Read-only; deterministic keyword search."),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for.", "minLength": 1, "maxLength": 200},
                "limit": {"type": "integer", "description": "Max matches (default 8, max 25).", "minimum": 1, "maximum": 25},
                "source": {"type": "string", "description": "Restrict to one corpus source (github | hf | registry | doc).", "maxLength": 20},
            },
            "required": ["query"],
        },
        "handler": _t_corpus_search,
    },
    "corpus_vector_search": {
        "description": ("Semantic search over the local curated corpus using the local "
                        "qwen3-embedding:0.6b lane + sqlite-vec cosine index (V4.1 §5.4). "
                        "An ADDITIONAL mode beside keyword search. Read-only; honest when "
                        "the embedding lane is unavailable."),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look for.", "minLength": 1, "maxLength": 300},
                "limit": {"type": "integer", "description": "Max matches (default 8, max 25).", "minimum": 1, "maximum": 25},
                "source": {"type": "string", "description": "Restrict to one corpus source (github | hf | registry | doc).", "maxLength": 20},
            },
            "required": ["query"],
        },
        "handler": _t_corpus_vector_search,
    },
    "corpus_drift": {
        "description": ("Report MEASURED embedding drift between the current corpus vectors "
                        "and historical Search-Query-Performance query vectors (V4.1 §5.4). "
                        "A cosine distance — never a trend, forecast or cause. Read-only."),
        "parameters": {"type": "object", "properties": {}, "required": []},
        "handler": _t_corpus_drift,
    },
    "voice_list": {
        "description": ("List voice profiles on the local VoiceStudio service for ad "
                        "voiceovers (id + name). Requires VoiceStudio running (VOICESTUDIO_URL)."),
        "parameters": {"type": "object", "properties": {}, "required": []},
        "handler": _t_voice_list,
    },
    "voice_tts": {
        "description": ("Generate a voiceover from an ad script using a VoiceStudio "
                        "voice (see voice_list). Requires VoiceStudio running."),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The ad script / voiceover text.", "minLength": 3, "maxLength": 2000},
                "voice_id": {"type": "string", "description": "Voice id from voice_list."},
                "lang": {"type": "string", "description": "Language code (default en).", "default": "en"},
            },
            "required": ["text", "voice_id"],
        },
        "handler": _t_voice_tts,
    },
    "voice_dub": {
        "description": ("Dub an ad script into another language via VoiceStudio "
                        "(translate + synthesize) for marketplace expansion."),
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The script to dub.", "minLength": 3, "maxLength": 2000},
                "target_lang": {"type": "string", "description": "Target language code (e.g. es, de, ja)."},
                "voice_id": {"type": "string", "description": "Optional voice id (auto if omitted)."},
            },
            "required": ["text", "target_lang"],
        },
        "handler": _t_voice_dub,
    },
}


def tool_names() -> List[str]:
    return list(TOOLS.keys())


def ollama_tool_schemas(names: Optional[List[str]] = None) -> List[dict]:
    """Ollama `tools` payload for the registered tools."""
    out = []
    for name in (names or tool_names()):
        spec = TOOLS.get(name)
        if not spec:
            continue
        out.append({"type": "function", "function": {
            "name": name, "description": spec["description"], "parameters": spec["parameters"],
        }})
    return out


def run_tool(name: str, raw_args: Any, ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Validate → execute one tool call. Never raises; failures are honest results."""
    ctx = ctx or {}
    spec = TOOLS.get(name)
    if spec is None:
        return {"ok": False, "summary": f"Unknown tool '{name}'.",
                "error": f"known tools: {', '.join(tool_names())}", "assets": []}
    try:
        args = parse_arguments(raw_args)
        args = validate_tool_arguments(spec, args)
    except ToolValidationError as exc:
        return {"ok": False, "summary": "Tool arguments were rejected.", "error": str(exc), "assets": []}
    try:
        result = spec["handler"](args, ctx)
    except Exception as exc:  # noqa: BLE001 - surfaced honestly, never hidden
        return {"ok": False, "summary": f"The '{name}' tool failed.",
                "error": str(exc)[:400], "assets": []}
    result.setdefault("assets", [])
    result.setdefault("ok", False)
    result.setdefault("summary", "")
    return result
