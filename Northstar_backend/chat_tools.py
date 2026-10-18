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
