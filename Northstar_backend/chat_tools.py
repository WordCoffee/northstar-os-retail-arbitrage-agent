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


def _t_plan_project(args, ctx) -> dict:
    """Build a validated project plan with the agent kernel (read-only)."""
    from agent_kernel.model import validate_plan
    from agent_kernel.tys_adapter import work_order_to_plan

    goal = str(args.get("goal") or "").strip()
    if not goal:
        return {"ok": False, "summary": "A project goal is required.",
                "error": "goal is empty", "assets": []}
    lanes = list(args.get("lanes") or ["inspect"])
    steps = list(args.get("steps") or [])
    if not steps:
        steps = [{"lane": lanes[0], "objective": goal}]
    order = {"id": "bojo_plan", "objective": goal,
             "scope": {"lanes": lanes}, "steps": steps,
             "limits": {"max_steps": len(steps) * 2}}
    try:
        plan = work_order_to_plan(order)
    except ValueError as exc:
        return {"ok": False, "summary": "The plan could not be built.",
                "error": str(exc)[:300], "assets": []}
    errors = validate_plan(plan)
    rows = [{"label": n.title[:70], "value": f"{n.lane or n.kind} \u00b7 {n.state}"}
            for n in plan.nodes]
    if errors:
        rows.append({"label": "validation", "value": "; ".join(errors)[:90]})
    return {
        "ok": not errors,
        "summary": (f"Plan with {len(plan.nodes)} step(s), "
                    f"{len(errors)} validation error(s)."),
        "assets": [],
        "data": {
            "card": {"title": "Project plan", "rows": rows,
                     "action": {"label": "Approve the plan",
                                "message": "Approve this plan and start the first step."}},
            "plan": plan.to_dict(),
            "errors": errors,
            "note": ("This is a plan, not an execution. The kernel refuses to run "
                     "it until an operator approves it."),
        },
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


def _t_build_utility(args, ctx) -> dict:
    """BOJO-UTIL: build the small tool instead of handing it off.

    The router already says a calculator is Bojo's work; this is where that
    promise is kept. The page is one self-contained HTML file, so it needs no
    build step and no network.
    """
    from specialists import utility_apps
    request = str(args.get("request") or "").strip()
    out = utility_apps.build(request)
    if not out.get("ok"):
        return {"ok": False, "summary": "I can't build that one.",
                "error": out.get("error"), "assets": [],
                "data": {"reason": out.get("reason"), "available": out.get("available")}}
    fname = f"utility_{uuid.uuid4().hex}.html"
    db = ctx.get("db")
    acct = ctx.get("account_id")
    if db is None or not acct:
        # No account context means no asset row, and an unreachable file on disk
        # is not a deliverable. Say so instead of claiming a build.
        return {"ok": False,
                "summary": "Built the page but could not store it.",
                "error": "no account context to store the file against.",
                "assets": [], "data": {"template": out["template"]}}
    (_out_dir() / fname).write_text(str(out["html"]), encoding="utf-8")
    aid = db.design_studio.assets.create({
        "account_id": acct,
        "project_id": ctx.get("project_id"),
        "name": f"{out['title']} (HTML)",
        "asset_type": "utility-app",
        "mime_type": "text/html",
        "storage_key": fname,
        "size_bytes": out["bytes"],
        "metadata": {"utility": {
            "template": out["template"],
            "request": request[:400],
            "via": "chat-tool build_utility",
            "note": "One self-contained page: no network, no build step.",
        }},
    })
    assets: List[dict] = [{"id": aid, "kind": "utility-app",
                           "url": f"/api/design-studio/assets/{aid}/file",
                           "name": f"{out['title']} (HTML)"}]
    return {
        "ok": True,
        "summary": (f"Built the {str(out['title']).lower()} as one self-contained page "
                    f"({out['bytes']:,} bytes). It runs offline and computes only from "
                    f"what you type."),
        "assets": assets,
        "data": {"template": out["template"], "filename": fname},
    }


def _t_handoff_to_autothink(args, ctx) -> dict:
    """Carry an approved engineering handoff to Autothink — or say why not.

    The offer is priced by the router; this tool is the delivery. It refuses
    without an endpoint, an approval, a charge ceiling, or an account to
    attribute the approval to.
    """
    import os as _os
    from specialists import autothink_transport as at

    request = str(args.get("request") or "").strip()
    packet = at.build_packet(request)
    if not packet.get("ok"):
        return {"ok": False, "summary": "Nothing was sent.", "assets": [],
                "error": packet.get("error"), "data": {"reason": packet.get("reason")}}

    if not args.get("confirm"):
        return {"ok": True,
                "summary": (f"Prepared the Autothink brief ({packet['estimated_tokens']} tokens, "
                            f"estimated charge {packet['estimated_charge_usd']} USD). "
                            f"Nothing has been sent."),
                "assets": [], "data": {"packet": packet, "sent": False}}

    acct = ctx.get("account_id")
    ceiling = args.get("max_charge_usd")
    if ceiling is None:
        ceiling = (_os.environ.get("AUTOTHINK_MAX_CHARGE_USD") or "").strip() or None

    result = at.send(packet, approved_by=acct, max_charge_usd=ceiling)
    receipt = result.get("receipt") or {}
    if result.get("ok"):
        summary = (f"Sent to Autothink as {packet['packet_id']} "
                   f"(HTTP {receipt.get('http_status')}, receipt {receipt.get('response_id') or 'no id'}).")
    else:
        summary = "The handoff was not sent."
    return {"ok": bool(result.get("ok")), "summary": summary, "assets": [],
            "error": None if result.get("ok") else result.get("error"),
            "data": {"packet_id": packet.get("packet_id"), "sent": bool(result.get("ok")),
                     "status": result.get("status"), "reason": result.get("reason"),
                     "receipt": receipt,
                     "estimated_charge_usd": packet.get("estimated_charge_usd")}}


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
    fit_note = ""
    if out.get("fitted"):
        req = out.get("requested") or {}
        fit_note = (f" Requested {req.get('width')}x{req.get('height')}; the engine kept the "
                    f"aspect and fitted it to {out.get('width')}x{out.get('height')} "
                    f"({out.get('engine_max_edge_px') or 2048} px ceiling).")
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
                "requested": out.get("requested"), "fitted": bool(out.get("fitted")),
                "lane": "chat",
            }, "note": ("Rendered locally on the operator's machine via ComfyUI. "
                        "Surfaces only - no text, logos or legal copy. Use apply_label to "
                        "put the brand's real logo and copy on it.")},
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
                    f"({out['model']}, seed {out.get('seed')}).{fit_note} Surfaces only — "
                    f"run apply_label with the operator's logo and copy to finish the pack."),
        "assets": assets,
        "data": {"model": out["model"], "seed": out.get("seed"),
                 "requested": out.get("requested"), "fitted": bool(out.get("fitted"))},
    }


def _resolve_asset(db, acct, asset_id: str):
    """Look up one studio asset for this account. Returns (record, path) or (None, None)."""
    if db is None or not acct or not asset_id:
        return None, None
    rec = db.design_studio.assets.get_by_id(str(asset_id), account_id=acct)
    if not rec or not rec.get("storage_key"):
        return rec, None
    path = _out_dir() / Path(str(rec["storage_key"])).name
    return rec, (path if path.is_file() else None)


def _t_apply_label(args, ctx) -> dict:
    """Composite the operator's logo + copy onto a rendered pack."""
    import pouch_label

    db = ctx.get("db")
    acct = ctx.get("account_id")
    plate_rec, plate_path = _resolve_asset(db, acct, args["plate_asset_id"])
    if plate_rec is None:
        return {"ok": False, "summary": "That plate asset was not found.",
                "error": f"no studio asset {args['plate_asset_id']!r} for this account", "assets": []}
    if plate_path is None:
        return {"ok": False, "summary": "The plate asset has no file on disk.",
                "error": f"asset {args['plate_asset_id']!r} has no stored image", "assets": []}

    logo_path = None
    logo_rec = None
    if args.get("logo_asset_id"):
        logo_rec, logo_path = _resolve_asset(db, acct, args["logo_asset_id"])
        if logo_path is None:
            return {"ok": False, "summary": "The logo asset could not be read.",
                    "error": f"asset {args['logo_asset_id']!r} is missing or empty", "assets": []}

    progress: Callable[[Optional[int], str], None] = ctx.get("progress") or (lambda p, l: None)
    progress(0, "measuring the pouch face")

    # ── argument type contract ───────────────────────────────────────────────
    # Model-supplied JSON is not trusted to be the shape we expect. A sequence
    # where a scalar belongs (or vice versa) previously surfaced as the opaque
    # "can't multiply sequence by non-int of type 'float'" from deep inside the
    # compositor. Normalise here, at the boundary, and reject what cannot be
    # normalised with a message an operator can act on.
    def _scalar_text(value, field: str) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        raise ValueError(
            f"{field} must be a single line of text, got {type(value).__name__}")

    def _string_list(value, field: str) -> Optional[List[str]]:
        if value in (None, "", []):
            return None
        if isinstance(value, str):
            return [value]                      # a lone string is one item
        if isinstance(value, (list, tuple)):
            out: List[str] = []
            for item in value:
                if isinstance(item, (str, int, float)) and not isinstance(item, bool):
                    out.append(str(item))
                else:
                    raise ValueError(
                        f"{field} entries must be text, got {type(item).__name__}")
            return out or None
        raise ValueError(f"{field} must be a list of text, got {type(value).__name__}")

    try:
        title_text = _scalar_text(args["title"], "title")
        subtitle_text = _scalar_text(args.get("subtitle"), "subtitle")
        weight_text = _scalar_text(args.get("weight"), "weight")
        bullets = _string_list(args.get("bullets"), "bullets")
        icons = _string_list(args.get("icons"), "icons")
    except ValueError as exc:
        return {"ok": False, "summary": f"The label arguments were rejected: {exc}",
                "error": str(exc), "assets": []}

    try:
        out = pouch_label.compose(
            plate_path, title=title_text, subtitle=subtitle_text,
            weight=weight_text, bullets=bullets,
            logo_path=logo_path, icons=icons,
        )
    except ValueError as exc:
        return {"ok": False, "summary": "The label could not be composited.",
                "error": str(exc)[:400], "assets": []}
    except Exception as exc:  # noqa: BLE001 - honest result, never a silent no-op
        # Keep the failing frame. A bare str(exc) hid a real compositor bug
        # behind "can't multiply sequence by non-int of type 'float'".
        import traceback as _tb
        frame = _tb.extract_tb(exc.__traceback__)[-1]
        where = f"{Path(frame.filename).name}:{frame.lineno} in {frame.name}"
        return {"ok": False, "summary": "The label compositor failed.",
                "error": f"{type(exc).__name__}: {exc} ({where})"[:400], "assets": []}

    progress(100, "label composited")
    fname = f"{uuid.uuid4().hex}.png"
    (_out_dir() / fname).write_bytes(out["bytes"])
    aid = None
    if db is not None and acct:
        aid = db.design_studio.assets.create({
            "account_id": acct,
            "project_id": ctx.get("project_id") or (plate_rec or {}).get("project_id"),
            "name": args.get("name") or f"{args['title']} — labelled mockup",
            "asset_type": "composite",
            "mime_type": "image/png",
            "storage_key": fname,
            "width": out["size"][0], "height": out["size"][1],
            "size_bytes": len(out["bytes"]),
            "metadata": {"label": {
                "plate_asset_id": args["plate_asset_id"],
                "logo_asset_id": args.get("logo_asset_id"),
                "title": out["title"], "quad": out["quad"],
                "measured": out["measured"], "icons": out["icons"],
                "via": "chat-tool apply_label",
            }, "note": out["note"]},
        })
    logos = "the operator's logo + " if out["has_logo"] else ""
    return {
        "ok": True,
        "summary": (f"Composited {logos}label onto the pouch: '{args['title']}'"
                    + (f", {args.get('subtitle')}" if args.get("subtitle") else "")
                    + (f", {args.get('weight')}" if args.get("weight") else "")
                    + ". Logo pixels and fonts are real, not generated. The face was measured "
                      "from the render — this is a mockup fit, so confirm geometry with the "
                      "pouch converter before print."),
        "assets": [{
            "id": aid, "kind": "image",
            "url": f"/api/design-studio/assets/{aid}/file" if aid else None,
            "name": args.get("name") or f"{args['title']} — labelled mockup",
            "width": out["size"][0], "height": out["size"][1],
        }],
        "data": {"quad": out["quad"], "size": out["size"],
                 "has_logo": out["has_logo"], "icons": out["icons"]},
    }


def _t_place_logo(args, ctx) -> dict:
    """Put the operator's logo on a plate at a measured or explicit anchor."""
    import logo_placement

    db = ctx.get("db")
    acct = ctx.get("account_id")
    plate_rec, plate_path = _resolve_asset(db, acct, args["plate_asset_id"])
    if plate_path is None:
        return {"ok": False, "summary": "That plate asset has no file on disk.",
                "error": f"no readable plate for {args.get('plate_asset_id')!r}", "assets": []}
    logo_rec, logo_path = _resolve_asset(db, acct, args["logo_asset_id"])
    if logo_path is None:
        return {"ok": False, "summary": "The logo asset could not be read.",
                "error": f"no readable logo for {args.get('logo_asset_id')!r}", "assets": []}

    progress: Callable[[Optional[int], str], None] = ctx.get("progress") or (lambda p, l: None)
    progress(10, "measuring where the mark sits cleanly")
    try:
        out = logo_placement.place(
            plate_path.read_bytes(), logo_path.read_bytes(),
            anchor=str(args.get("anchor") or "auto"),
            scale=float(args.get("scale") or 0.18),
            opacity=float(args.get("opacity") if args.get("opacity") is not None else 0.95),
            margin=float(args.get("margin") if args.get("margin") is not None else 0.04),
            blend=str(args.get("blend") or "normal"),
        )
    except ValueError as exc:
        return {"ok": False, "summary": "The logo placement was rejected.",
                "error": str(exc)[:300], "assets": []}
    except Exception as exc:  # noqa: BLE001 - honest result, never a silent no-op
        return {"ok": False, "summary": "The logo could not be placed.",
                "error": f"{type(exc).__name__}: {exc}"[:300], "assets": []}

    progress(90, "registering the composited asset")
    fname = f"{uuid.uuid4().hex}.png"
    (_out_dir() / fname).write_bytes(out["bytes"])
    aid = None
    if db is not None and acct:
        aid = db.design_studio.assets.create({
            "account_id": acct,
            "project_id": ctx.get("project_id") or (plate_rec or {}).get("project_id"),
            "name": args.get("name") or "logo placement",
            "asset_type": "composite", "mime_type": "image/png",
            "storage_key": fname,
            "width": out["size"][0], "height": out["size"][1],
            "size_bytes": len(out["bytes"]),
            "metadata": {"logo_placement": {
                "plate_asset_id": args["plate_asset_id"],
                "logo_asset_id": args["logo_asset_id"],
                "placement": out["placement"], "quality": out["quality"],
                "via": "chat-tool place_logo"}},
        })
    q = out["quality"]
    p = out["placement"]
    warn = "" if q["contrast_ok"] else " Contrast is low (<1.5:1) — the mark may disappear."
    return {
        "ok": True,
        "summary": (f"Placed the logo at {p['anchor']} ({p['width']}x{p['height']} px, "
                    f"{int(round(p['opacity'] * 100))}% opacity, {p['blend']} blend). "
                    f"Ink/backdrop contrast {q['contrast_ratio']}:1, coverage "
                    f"{q['coverage_pct']}% of the frame.{warn} The anchor was measured, "
                    "not guessed — the logo pixels are composited, never generated."),
        "assets": [{
            "id": aid, "kind": "image",
            "url": f"/api/design-studio/assets/{aid}/file" if aid else None,
            "name": args.get("name") or "logo placement",
            "width": out["size"][0], "height": out["size"][1],
        }],
        "data": {"placement": p, "quality": q},
    }


def _t_build_package(args, ctx) -> dict:
    """Complete package: designed panels + dieline + mockup, gated on real inputs."""
    import package_pipeline as pp

    db = ctx.get("db")
    acct = ctx.get("account_id")
    fmt = str(args.get("format") or "pouch").strip().lower()
    spec = {k: args.get(k) for k in (
        "title", "subtitle", "weight", "ingredients", "supplement_facts",
        "suggested_use", "warnings", "company", "address", "country_of_origin",
        "lot_code", "claims", "icons", "brand", "theme", "design", "servings",
        "organic_certified") if args.get(k) not in (None, "", [])}
    spec["format"] = fmt
    dim_keys = ("width_mm", "height_mm", "gusset_mm", "depth_mm", "diameter",
                "label_height", "label_top_offset", "usable_height_mm")
    dims = {k: args[k] for k in dim_keys if args.get(k) not in (None, "")}
    if dims:
        spec["dims"] = dims

    plate_path = logo_path = None
    if args.get("plate_asset_id"):
        _r, plate_path = _resolve_asset(db, acct, args["plate_asset_id"])
    if args.get("logo_asset_id"):
        _r, logo_path = _resolve_asset(db, acct, args["logo_asset_id"])

    try:
        out = pp.build_package(spec, format=fmt, plate_path=plate_path,
                               logo_path=logo_path,
                               out_dir=_out_dir(),
                               allow_incomplete=bool(args.get("allow_incomplete")))
    except (ValueError, KeyError) as exc:
        return {"ok": False, "summary": "The package could not be built.",
                "error": str(exc)[:400], "assets": []}
    if not out.get("ok"):
        return {"ok": False, "status": out.get("status"),
                "summary": out.get("summary") or "I need more information.",
                "error": "missing required inputs",
                "questions": out.get("questions") or [],
                "data": {"questions": out.get("questions") or []},
                "assets": []}

    files = pp.save_package(out, _out_dir())
    assets = []
    if db is not None and acct:
        for key, label in (("sheet", "panel sheet"), ("front", "front panel"),
                           ("back", "back panel"), ("side", "side panel"),
                           ("mockup", "labelled mockup")):
            name = files.get(key)
            if not name:
                continue
            payload = (_out_dir() / name).read_bytes()
            aid = db.design_studio.assets.create({
                "account_id": acct,
                "project_id": ctx.get("project_id"),
                "name": f"{args['title']} — {label}",
                "asset_type": "package-panel",
                "mime_type": "image/png",
                "storage_key": name,
                "size_bytes": len(payload),
                "metadata": {"package": {"role": key, "spec": spec,
                                         "validation": out.get("validation")},
                             "note": "Deterministic panel artwork; text is drawn, never generated."},
            })
            assets.append({"id": aid, "kind": "image",
                           "url": f"/api/design-studio/assets/{aid}/file",
                           "name": f"{args['title']} — {label}"})
        for kind, key in (("SVG", "dieline_svg"), ("PDF", "dieline_pdf")):
            name = files.get(key)
            if not name:
                continue
            payload = (_out_dir() / name).read_bytes()
            aid = db.design_studio.assets.create({
                "account_id": acct, "project_id": ctx.get("project_id"),
                "name": f"{args['title']} — dieline ({kind})",
                "asset_type": "dieline",
                "mime_type": "image/svg+xml" if kind == "SVG" else "application/pdf",
                "storage_key": name, "size_bytes": len(payload),
                "metadata": {"dieline": out.get("dieline", {}).get("meta") or {},
                             "note": "Draft geometry - confirm with the converter."},
            })
            assets.append({"id": aid, "kind": "dieline",
                           "url": f"/api/design-studio/assets/{aid}/file",
                           "name": f"{args['title']} — dieline ({kind})"})

    v = out.get("validation") or {}
    summary = out["summary"]
    if v.get("missing"):
        summary += " Still missing: " + ", ".join(v["missing"]) + "."
    if v.get("warnings"):
        summary += " " + v["warnings"][0]
    return {"ok": True, "summary": summary, "assets": assets,
            "data": {"validation": v, "dieline": out.get("dieline", {}).get("meta"),
                     "questions": out.get("questions") or []}}


def _t_optimize_listing(args, ctx) -> dict:
    from specialists import listing_optimizer as lo
    out = lo.optimize(
        title=str(args.get("title") or ""),
        bullets=[str(b) for b in (args.get("bullets") or [])],
        keywords=[str(k) for k in (args.get("keywords") or [])],
        description=str(args.get("description") or ""),
        backend_terms=str(args.get("backend_terms") or ""))
    if not out.get("ok"):
        return {"ok": False, "status": out.get("status"),
                "summary": out.get("summary") or "I need target keywords.",
                "error": "missing target keywords",
                "data": {"questions": out.get("questions") or []}, "assets": []}
    return {"ok": True, "summary": out["summary"], "assets": [],
            "data": {"before": out["before"], "after": out["after"],
                     "listing": out["listing"], "change_log": out["change_log"],
                     "notes": out.get("notes")}}


def _t_ppc_plan(args, ctx) -> dict:
    from specialists import ppc_agent as ppa
    rows = args.get("search_terms") or []
    out = ppa.analyze(rows, target_acos=float(args.get("target_acos") or 0.35))
    if not out.get("ok"):
        return {"ok": False, "status": out.get("status"),
                "summary": "That upload was rejected rather than guessed at.",
                "error": out.get("error") or "invalid report", "assets": []}
    data = {"harvest": out["harvest"], "negatives": out["negatives"],
            "thresholds": out["thresholds"], "notes": out.get("notes")}
    if args.get("proposed_rows"):
        data["validation"] = ppa.validate_change_rows(args["proposed_rows"], rows)
    assets = []
    if args.get("write_bulk"):
        from specialists import ppc_bulk
        db, acct = ctx.get("db"), ctx.get("account_id")
        name = f"ppc_bulk_{uuid.uuid4().hex[:10]}.xlsx"
        target = _out_dir() / name
        written = ppc_bulk.write_bulk_file(
            out, source=rows, out_path=target,
            bid=float(args["default_bid"]) if args.get("default_bid") else None)
        if not written.get("ok"):
            data["bulk_file"] = written
        else:
            data["bulk_file"] = {k: v for k, v in written.items() if k != "path"}
            if db is not None and acct:
                aid = db.design_studio.assets.create({
                    "account_id": acct, "project_id": ctx.get("project_id"),
                    "name": "PPC bulk plan (Northstar columns)",
                    "asset_type": "bulk-plan",
                    "mime_type": "application/vnd.openxmlformats-officedocument."
                                 "spreadsheetml.sheet",
                    "storage_key": name, "size_bytes": written["bytes"],
                    "metadata": {"ppc": {"rows": written["rows"],
                                         "thresholds": out["thresholds"],
                                         "note": written["note"]},
                                 "note": "Planning sheet, not an official Amazon template."},
                })
                assets.append({"id": aid, "kind": "file",
                               "url": f"/api/design-studio/assets/{aid}/file",
                               "name": "PPC bulk plan (.xlsx)"})
    return {"ok": True, "summary": out["summary"], "assets": assets, "data": data}


def _t_plan_aplus(args, ctx) -> dict:
    from specialists import image_aplus as ap
    out = ap.plan(spec={k: args.get(k) for k in (
        "product", "modules", "copy", "style", "shape", "colour", "logo_text",
        "parts", "must_not") if args.get(k)})
    if not out.get("ok"):
        return {"ok": False, "status": out.get("status"),
                "summary": out.get("summary") or "I need more information.",
                "error": "missing required inputs",
                "data": {"questions": out.get("questions") or []}, "assets": []}
    return {"ok": True, "summary": out["summary"], "assets": [],
            "data": {"modules": out["modules"], "identity_lock": out["identity_lock"],
                     "rules": out["rules"], "copy_check": out["copy_check"],
                     "validation": out["validation"]}}


def _t_plan_social(args, ctx) -> dict:
    from specialists import social_graphics as sg
    out = sg.plan(spec={k: args.get(k) for k in
                        ("product", "content_type", "aspects", "headline")
                        if args.get(k)})
    if not out.get("ok"):
        return {"ok": False, "status": out.get("status"),
                "summary": out.get("summary") or "I need more information.",
                "error": "missing required inputs",
                "data": {"questions": out.get("questions") or []}, "assets": []}
    return {"ok": True, "summary": out["summary"], "assets": [],
            "data": {"layouts": out["layouts"], "note": out["note"],
                     "rules": out["rules"]}}


def _t_plan_video(args, ctx) -> dict:
    from specialists import video_ugc as vu
    out = vu.plan(spec={k: args.get(k) for k in
                        ("product", "duration_seconds", "hook", "fps", "script")
                        if args.get(k) not in (None, "")})
    if not out.get("ok"):
        return {"ok": False, "status": out.get("status"),
                "summary": out.get("summary") or "I need more information.",
                "error": out.get("error") or "missing required inputs",
                "data": {"questions": out.get("questions") or []}, "assets": []}
    return {"ok": True, "summary": out["summary"], "assets": [],
            "data": {"scenes": out["scenes"], "fps": out["fps"],
                     "frames": out["frames"],
                     "validation_plan": out["validation_plan"],
                     "claims_check": out["claims_check"]}}


def _t_write_content(args, ctx) -> dict:
    from specialists import content as ct
    out = ct.plan(spec={k: args.get(k) for k in
                        ("product", "surface", "keywords", "benefits", "tone", "brand")
                        if args.get(k)})
    if not out.get("ok"):
        return {"ok": False, "status": out.get("status"),
                "summary": out.get("summary") or "I need more information.",
                "error": out.get("error") or "missing required inputs",
                "data": {"questions": out.get("questions") or []}, "assets": []}
    return {"ok": True, "summary": out["summary"], "assets": [],
            "data": {"variants": out["variants"],
                     "claim_policy": out["claim_policy"]}}


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


def _t_purpose_command(args, ctx) -> dict:
    """Read-only self-analysis of this repository (Project Thorn v5.0 purpose commands).

    Proposal-only by construction: `purpose_commands` parses source with `ast` and
    never writes, imports or executes the analysed code."""
    import purpose_commands  # local import keeps the chat-tool import surface light

    report = purpose_commands.run_purpose_command(
        args.get("command"), path=args.get("path"), limit=args.get("limit"))
    if not report.get("ok"):
        return {"ok": False, "summary": report.get("summary") or "The purpose command failed.",
                "error": report.get("error") or "", "assets": []}

    counts = report.get("counts") or {}
    scanned = report.get("scanned") or {}
    findings = report.get("findings") or []
    units = scanned.get("modules", scanned.get("files", 0))
    lines = [f"/{report['command']}: {sum(counts.values())} finding(s) across {units} scanned unit(s)."]
    for kind, n in counts.items():
        lines.append(f"  - {kind}: {n}")
    for f in findings[:8]:
        lines.append(f"  [{f['severity']}] {f['kind']} :: {f['target']} — {f['detail']}")
    if len(findings) > 8:
        lines.append(f"  … {len(findings) - 8} more not shown.")
    return {
        "ok": True,
        "summary": "\n".join(lines),
        "command": report["command"],
        "counts": counts,
        "scanned": scanned,
        "caveats": report.get("caveats", []),
        "findings": findings[:10],
        "assets": [],
    }


def _t_build_preset(args, ctx) -> dict:
    """Read-only BUILD preset resolution (Thorn v5.0 §User Work Presets).

    BUILD presets shape the brain's work on its own materials — design system,
    code, architecture. They are separate from the six WORK focus modes and never
    replace them."""
    import build_presets  # local import keeps the chat-tool import surface light

    preset_id = args.get("preset")
    track = args.get("track")
    if preset_id:
        out = build_presets.resolve(str(preset_id))
    elif track:
        out = build_presets.for_track(str(track))
    else:
        out = build_presets.catalogue()

    if out.get("ok") is False:
        return {"ok": False, "summary": out.get("error") or "Unknown BUILD preset.",
                "error": out.get("error") or "", "assets": []}
    if "presets" in out:
        return {"ok": True,
                "summary": (f"{len(out['presets'])} BUILD preset(s): "
                            + ", ".join(p["label"] for p in out["presets"])
                            + " — separate from the six work foci."),
                "catalogue": out, "assets": []}
    return {"ok": True,
            "summary": (f"BUILD preset '{out['label']}': {len(out['tools'])} tool(s), "
                        f"memory={out['memory_retention']}, model={out['model_family']}."),
            "preset": out, "assets": []}


def _t_creative_plan(args, ctx) -> dict:
    """Build, confirm, or EXECUTE a creative plan (Bojo).

    Planning returns a card the UI renders with four actions. Confirming draft/final
    runs the job for real: reserve -> generate -> commit (or release on failure), so
    a paid job actually happens and a failed one costs nothing."""
    import creative_plan

    action = str(args.get("action") or "").strip().lower()
    if action:
        plan_id = str(args.get("plan_id") or "").strip()
        plan = creative_plan.get(plan_id)
        if plan is None:
            return {"ok": False,
                    "summary": "That plan is no longer open — ask for a fresh plan.",
                    "error": "unknown or expired plan_id", "assets": []}
        decision = creative_plan.confirm(plan, action)
        if not decision.get("ok"):
            return {"ok": False, "summary": decision.get("error") or "That choice was refused.",
                    "error": decision.get("error") or "", "data": decision, "assets": []}
        if action == "cancel":
            creative_plan.forget(plan_id)
            return {"ok": True, "summary": decision["message"], "data": decision, "assets": []}
        if action == "edit":
            return {"ok": True, "summary": decision["message"], "data": decision, "assets": []}

        # draft / final -> actually run it
        import creative_execute

        account_id = str((ctx or {}).get("account_id") or "default")
        ledger = creative_execute.default_ledger()
        generator = _CREATIVE_GENERATOR or (
            lambda instruction: creative_execute.default_generate(instruction, ctx=ctx))
        receipt = creative_execute.execute(
            ledger, plan, action, generate=generator, account_id=account_id,
            subscription=plan.get("subscription"))
        if not receipt.get("ok"):
            return {"ok": False,
                    "summary": (f"That job did not run: {receipt.get('error')}. "
                                "No credits were charged."),
                    "error": receipt.get("error") or "", "data": {"receipt": receipt},
                    "assets": []}
        creative_plan.forget(plan_id)
        return {"ok": True,
                "summary": (f"{receipt['quality'].title()} generated — {receipt['credits_charged']} "
                            f"credits charged (real cost ${receipt['real_cost_usd']:.3f}, "
                            f"balance {receipt.get('balance')})."),
                "data": {"receipt": receipt}, "assets": receipt.get("assets") or []}

    request_text = str(args.get("request") or "").strip()
    if not request_text:
        return {"ok": False, "summary": "Tell me what to make and I will build a plan.",
                "error": "request is required to build a plan", "assets": []}
    plan = creative_plan.build_plan(
        request_text,
        media=str(args.get("media") or "image"),
        detail=str(args.get("detail") or "quick"),
        count=int(args.get("count") or 1),
        subscription=str(args.get("subscription") or "foundation"),
    )
    creative_plan.remember(plan)
    card = creative_plan.render_card(plan)
    return {"ok": True, "summary": plan["summary"],
            "data": {"plan": plan, "card": card}, "assets": []}


# Tests may inject a fake renderer so the money path is verifiable without a GPU.
_CREATIVE_GENERATOR = None


# ── Registry ─────────────────────────────────────────────────────────────────
# ── skill warehouse: service tools every focus can call ─────────────────────
# These are read-only and cheap, so they are offered in every focus. They are
# how Bojo resolves a request in any service area instead of guessing.

SERVICES = [
    {"id": "listing", "label": "Listing Forge / Guardian",
     "tools": ["listing_audit", "optimize_listing", "knowledge_lookup", "seo_check",
               "seo_retitle"],
     "can": ("audit a title and bullets against Amazon rules, SCORE and REWRITE a "
             "listing against target keywords, check claims, retitle to the SEO profile")},
    {"id": "ads", "label": "AdPilot",
     "tools": ["ads_math", "ppc_plan", "knowledge_lookup", "seo_negatives"],
     "can": ("compute ACOS/TACOS/break-even, judge a campaign, split negatives, turn "
             "ad reports into a validated bulk change plan")},
    {"id": "aplus", "label": "A+ Content",
     "tools": ["knowledge_lookup", "creative_plan"],
     "can": "plan A+ modules, check eligibility and module limits"},
    {"id": "creator-connections", "label": "Creator Connections",
     "tools": ["knowledge_lookup", "creative_plan"],
     "can": "write creator briefs, set commission and deliverables, check disclosure"},
    {"id": "brand-store", "label": "Brand & Store",
     "tools": ["knowledge_lookup", "creative_plan"],
     "can": "structure store pages and brand story, check what not to claim"},
    {"id": "reseller", "label": "Reseller Ops",
     "tools": ["knowledge_lookup", "listing_audit"],
     "can": "check gating and invoices, grade condition, audit a reseller listing"},
    {"id": "creative", "label": "Creative Studio",
     "tools": ["creative_plan", "generate_image", "apply_label", "place_logo", "build_package",
               "plan_aplus", "plan_social", "plan_video", "write_content",
               "design_brief", "create_dieline", "voice_list", "voice_tts",
               "voice_dub", "list_templates", "plan_project"],
     "can": ("plan and price a job, render images, build a COMPLETE package "
             "(front/back/side panels + dieline), put the real logo and copy on a "
             "render, plan A+ pages and social sets at exact pixel sizes, storyboard "
             "video, write screened copy, add voiceover")},
    {"id": "research", "label": "Research & Corpus",
     "tools": ["corpus_search", "corpus_vector_search", "corpus_drift", "knowledge_lookup"],
     "can": "search the local corpus, report drift, look up a rule with its source"},
    {"id": "system", "label": "System & Improvement",
     "tools": ["system_status", "improvement_status", "service_catalog",
               "purpose_command", "plan_project"],
     "can": "report engine health, coverage and gaps, list its own skills, plan a project"},
]


def _t_knowledge_lookup(args, ctx) -> dict:
    """Return the verified do/don't rules for a question."""
    import knowledge_pack as kp
    query = str(args.get("query") or "").strip()
    domain = str(args.get("domain") or "").strip() or None
    limit = int(args.get("limit") or 5)
    if domain and domain not in kp.domains():
        return {"ok": False, "summary": "Unknown knowledge domain.",
                "error": f"known domains: {', '.join(kp.domains())}"}
    # A weak lexical match is not a rule. Below this bar Bojo should say it has
    # nothing rather than quote an unrelated guideline.
    hits = kp.retrieve(query, domain, limit=max(1, min(limit, 10)), min_score=0.25)
    if not hits:
        return {"ok": True, "summary": "No verified rule matches that question yet.",
                "rules": [],
                "note": "Say plainly that you have no verified rule and offer to research it."}
    rules = [{
        "id": atom.get("id"), "do": atom.get("do"), "dont": atom.get("dont"),
        "why": atom.get("why"), "source": atom.get("source"),
        "confidence": atom.get("confidence"),
        "needs_verification": bool(atom.get("needs_verification")),
        "match": round(score, 3),
    } for score, atom in hits]
    return {"ok": True, "summary": f"{len(rules)} rule(s) matched.",
            "rules": rules, "pack_versions": kp.pack_versions()}


_TITLE_CHECKS = [
    {"type": "max_chars", "value": 200},
    {"type": "forbidden_terms",
     "terms": ["best seller", "free shipping", "sale", "deal", "money back",
               "#1", "guaranteed"]},
    {"type": "no_all_caps"},
]
_BULLET_CHECKS = [
    {"type": "max_chars", "value": 500},
    {"type": "forbidden_terms",
     "terms": ["fda approved", "cures", "treats", "prevents disease", "guaranteed"]},
]


def _t_listing_audit(args, ctx) -> dict:
    """Deterministic check of a title/bullets against Amazon listing rules."""
    import cie_eval
    import knowledge_pack as kp
    title = str(args.get("title") or "").strip()
    bullets = [str(b) for b in (args.get("bullets") or []) if str(b).strip()][:5]
    if not title and not bullets:
        return {"ok": False, "summary": "Nothing to audit.",
                "error": "pass a title and/or up to 5 bullets"}
    result: Dict[str, Any] = {"ok": True}
    if title:
        score, failures = cie_eval.grade(title, _TITLE_CHECKS)
        result["title"] = {"score": score, "failures": failures, "chars": len(title)}
    if bullets:
        bad = []
        for index, bullet in enumerate(bullets, 1):
            _score, failures = cie_eval.grade(bullet, _BULLET_CHECKS)
            if failures:
                bad.append({"index": index, "failures": failures})
        result["bullets"] = {"checked": len(bullets), "failures": bad}
    hits = kp.retrieve(title or " ".join(bullets), "listing", limit=3)
    result["rules"] = [{"id": a.get("id"), "do": a.get("do"), "dont": a.get("dont"),
                        "source": a.get("source")} for _s, a in hits]
    problems = (len(result.get("title", {}).get("failures", []))
                + len(result.get("bullets", {}).get("failures", [])))
    result["summary"] = ("No deterministic problems found."
                         if problems == 0 else f"{problems} problem(s) found.")
    return result


def _t_ads_math(args, ctx) -> dict:
    """ACOS, TACOS and break-even maths. Pure arithmetic, no network."""
    def num(key: str, default: float = 0.0) -> float:
        try:
            return float(args.get(key, default) or default)
        except (TypeError, ValueError):
            return default

    price, cogs = num("price"), num("cogs")
    spend, ad_sales = num("ad_spend"), num("ad_sales")
    total_revenue = num("total_revenue")
    if price <= 0:
        return {"ok": False, "summary": "A positive unit price is required.",
                "error": "price must be > 0"}
    margin = (price - cogs) / price
    out: Dict[str, Any] = {
        "ok": True, "unit_margin_pct": round(margin * 100, 2),
        "break_even_acos_pct": round(margin * 100, 2),
        "acos_pct": None, "verdict": "no ad data",
        "tacos_pct": None,
    }
    if ad_sales > 0:
        acos = spend / ad_sales
        out["acos_pct"] = round(acos * 100, 2)
        out["verdict"] = ("profitable" if acos <= margin else "losing money")
        out["profit_per_ad_dollar"] = round(margin - acos, 4)
        out["spend"] = spend
    if total_revenue > 0:
        out["tacos_pct"] = round(spend / total_revenue * 100, 2)
    out["summary"] = (f"ACOS {out['acos_pct']}% vs break-even {out['break_even_acos_pct']}% "
                      f"-> {out['verdict']}." if out["acos_pct"] is not None
                      else f"Break-even ACOS is {out['break_even_acos_pct']}% at this margin.")
    return out


def _t_improvement_status(args, ctx) -> dict:
    """What Bojo has learned, what it is missing, and the pack versions."""
    import cie_loop
    state = cie_loop.status()
    packs = {d: v.get("version") for d, v in (state.get("packs") or {}).get("domains", {}).items()}
    return {
        "ok": True,
        "summary": (f"Coverage {round((state.get('coverage') or 0) * 100)}% "
                    f"over {state.get('golden_items')} questions, "
                    f"{(state.get('packs') or {}).get('total', 0)} rules, "
                    f"{state.get('open_gaps', 0)} open gaps."),
        "coverage": state.get("coverage"),
        "atoms": (state.get("packs") or {}).get("total"),
        "open_gaps": state.get("open_gaps"),
        "stopped": state.get("stopped"),
        "live_ready": state.get("live_ready"),
        "packs": packs,
        "last_cycle": state.get("last_cycle"),
    }


def _t_service_catalog(args, ctx) -> dict:
    """List the services Bojo can act on and the tool that handles each."""
    return {
        "ok": True,
        "summary": f"{len(SERVICES)} service areas routed to {len(TOOLS)} tools.",
        "services": SERVICES,
        "tools": tool_names(),
    }


_CANVAS_VERBS = ('set ', 'change ', 'rename ', 'make ', 'add ', 'select ', 'swap ', 'replace ', 'switch ', 'scale ', 'resize ')

_CANVAS_ROLE_WORDS = {
    "headline": "headline", "title": "headline", "heading": "headline",
    "subhead": "subhead", "subheading": "subhead", "subtitle": "subhead",
    "body": "body", "copy": "body",
}


def _t_canvas_edit(args, ctx):
    """Propose one bounded edit to the canvas the operator has open (U8).

    It does not mutate anything: the browser applies the instruction through the
    same command layer the workbench registers, so the edit semantics live in one
    place. This handler only checks that the canvas CAN satisfy it, and refuses
    with the reason when it cannot.
    """
    canvas = (ctx or {}).get("canvas") or None
    instruction = str((args or {}).get("instruction") or "").strip()
    if not canvas:
        return {"ok": False, "summary": "No canvas is open.",
                "error": ("The workbench has not published a canvas to this turn, so there is "
                          "nothing to edit."), "assets": []}
    if not instruction:
        return {"ok": False, "summary": "No instruction.", "error": "instruction is empty", "assets": []}

    layers = canvas.get("layers") or []
    text_roles = {str(l.get("role") or "") for l in layers if l.get("kind") == "text"}
    words = instruction.lower()
    # Only the verbs the browser's parser can actually apply. "delete the
    # headline" names a real layer but is not an edit this path performs, and a
    # tool that answers ok:true to it invites a false success claim.
    if not words.startswith(_CANVAS_VERBS):
        return {"ok": False, "summary": "Not a canvas edit this path performs.",
                "error": (f'"{instruction}" is not one of the edits the canvas applies '
                          f"(set, scale, add, select, swap). Nothing was changed."),
                "assets": []}
    for word, role in _CANVAS_ROLE_WORDS.items():
        if word in words and role not in text_roles:
            return {"ok": False, "summary": f"No {role} layer on the canvas.",
                    "error": (f"This canvas has no {role} layer. Add one in the canvas "
                              f"workspace first."), "assets": []}
    return {"ok": True,
            "summary": f'Applying to "{canvas.get("name") or "the open design"}": {instruction}',
            "instruction": instruction, "assets": []}


TOOLS: Dict[str, dict] = {    "system_status": {
        "description": "Report the local media engine + chat model status. Read-only.",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "handler": _t_system_status,
    },
    "canvas_edit": {
        "description": ("Apply one concrete instruction to the design canvas the operator has "
                        "open (headline text, text size, selection, image swap). The browser "
                        "performs the edit; this tool checks it is possible and refuses when the "
                        "canvas is absent or the named layer does not exist."),
        "parameters": {
            "type": "object",
            "properties": {
                "instruction": {"type": "string", "minLength": 3, "maxLength": 240,
                                "description": "The instruction, in the operator's own words."},
            },
            "required": ["instruction"],
        },
        "handler": _t_canvas_edit,
    },
    "plan_project": {
        "description": ("Build a validated, visible project plan (steps, lanes, "
                        "acceptance) with the agent kernel. Read-only: it plans, it "
                        "does not execute. Use for a multi-step request before doing "
                        "the work, then ask the operator to approve it."),
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "minLength": 4,
                         "description": "The project goal in one sentence."},
                "lanes": {"type": "array", "items": {"type": "string",
                          "enum": ["inspect", "coding", "browser", "creative"]},
                          "description": "Lanes this project may use."},
                "steps": {"type": "array", "items": {"type": "object",
                          "properties": {
                              "lane": {"type": "string",
                                       "enum": ["inspect", "coding", "browser", "creative"]},
                              "objective": {"type": "string"},
                              "acceptance": {"type": "array", "items": {"type": "object"}}},
                          "required": ["lane", "objective"]},
                          "description": "Optional explicit steps; omit for a one-step plan."},
            },
            "required": ["goal"],
        },
        "handler": _t_plan_project,
    },
    "handoff_to_autothink": {
        "description": ("Carry an engineering request to Autothink, the premium coding "
                        "service. Use ONLY after the operator has explicitly approved the "
                        "handoff and its charge: pass confirm=true then. Without confirm it "
                        "prepares the brief and sends nothing. Refuses with the exact missing "
                        "piece when the lane is not armed."),
        "parameters": {
            "type": "object",
            "properties": {
                "request": {"type": "string", "description": "The engineering work to hand off.", "minLength": 8},
                "confirm": {"type": "boolean", "default": False, "description": "true only after the operator approved the charge."},
                "max_charge_usd": {"type": "number", "description": "Charge ceiling the operator accepted. Falls back to AUTOTHINK_MAX_CHARGE_USD."},
            },
            "required": ["request"],
        },
        "handler": _t_handoff_to_autothink,
    },
    "build_utility": {
        "description": ("Build a small self-contained utility page (tip, percentage, "
                        "break-even) as ONE html file: no network, no build step, no "
                        "account. Use this for 'make me a quick calculator' instead of "
                        "handing simple work to Autothink. Refuses honestly when the "
                        "request is not one of the supported tools."),
        "parameters": {
            "type": "object",
            "properties": {
                "request": {"type": "string", "description": "The utility in natural language, e.g. 'a quick tip calculator'.", "minLength": 3},
            },
            "required": ["request"],
        },
        "handler": _t_build_utility,
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
                        "image model — author those as structured layers instead (see "
                        "apply_label). Requires the media engine armed (MEDIA_GEN_LIVE + ComfyUI). "
                        "Ask for the shape you want: the local engine keeps the aspect ratio and "
                        "scales the long edge to its configured ceiling (2048 px), reports the real "
                        "size, and exact-sizes a spec dimension such as 1464x600 when the only "
                        "difference is the model's 16 px grid."),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Scene/surface description. No text requests.", "minLength": 3, "maxLength": 2000},
                "width": {"type": "integer", "minimum": 64, "maximum": 4096,
                          "description": "Requested width in px. Any sensible value is accepted; the engine fits it into its 1216 px box without distorting the ratio."},
                "height": {"type": "integer", "minimum": 64, "maximum": 4096,
                           "description": "Requested height in px. A portrait product shot is usually 832x1216 or 896x1216."},
                "tier": {"type": "string", "enum": ["draft", "final"], "default": "draft"},
            },
            "required": ["prompt"],
        },
        "handler": _t_generate_image,
    },
    "apply_label": {
        "description": ("Put the operator's real logo and real copy ON a rendered pouch/tube/carton "
                        "image — the deterministic typography pass. Use this whenever the operator "
                        "wants a product mockup that actually shows their brand, product name and "
                        "net weight: the render supplies the photograph, this supplies the print. "
                        "Logo pixels and fonts are composited, never generated, so spelling is exact. "
                        "The face is measured from the render; the fit is a mockup fit, not a die."),        "parameters": {
            "type": "object",
            "properties": {
                "plate_asset_id": {"type": "string", "minLength": 3, "maxLength": 80,
                                   "description": "Asset id of the rendered pouch/product image (from generate_image)."},
                "title": {"type": "string", "minLength": 1, "maxLength": 60,
                          "description": "Product name as it must appear, e.g. \"Lion's Mane\"."},
                "subtitle": {"type": "string", "maxLength": 80,
                             "description": "Supporting line, e.g. \"Organic Mushroom Powder\"."},
                "weight": {"type": "string", "maxLength": 40,
                           "description": "Net weight line, e.g. \"NET WT 6 OZ (170 g)\"."},
                "bullets": {"type": "array", "items": {"type": "string", "maxLength": 60},
                            "maxItems": 5, "description": "Optional short claim lines."},
                "logo_asset_id": {"type": "string", "maxLength": 80,
                                  "description": "Asset id of the operator's logo (an attachment). Omit for a type-only label."},
                "icons": {"type": "array",
                          "items": {"type": "string", "enum": ["organic_sprout", "non_gmo", "gluten_free", "fruiting_body"]},
                          "maxItems": 4,
                          "description": "Certification marks to draw (vectors, not generated art)."},
                "name": {"type": "string", "maxLength": 120, "description": "Optional asset name."},
            },
            "required": ["plate_asset_id", "title"],
        },
        "handler": _t_apply_label,
    },
    "place_logo": {
        "description": ("Put the operator's logo ON a rendered image at a measured or explicit "
                        "anchor — the brand-mark pass (apply_label is the full print pass). Use "
                        "this when the ask is 'put my logo on it', not 'label this pouch'. The "
                        "anchor is chosen by measuring the calmest perimeter cell, or you may name "
                        "one; the logo pixels are composited, never generated. It reports the "
                        "ink/backdrop contrast it achieved, so a low-contrast mark is flagged "
                        "instead of shipped silently."),
        "parameters": {
            "type": "object",
            "properties": {
                "plate_asset_id": {"type": "string", "minLength": 3, "maxLength": 80,
                                   "description": "Asset id of the image to place the logo on."},
                "logo_asset_id": {"type": "string", "minLength": 3, "maxLength": 80,
                                  "description": "Asset id of the operator's logo."},
                "anchor": {"type": "string",
                           "enum": ["auto", "top-left", "top-center", "top-right",
                                    "middle-left", "center", "middle-right",
                                    "bottom-left", "bottom-center", "bottom-right"],
                           "description": "auto = flattest perimeter cell (never dead centre)."},
                "scale": {"type": "number", "minimum": 0.02, "maximum": 0.9,
                          "description": "Logo width as a fraction of the plate's short edge (default 0.18)."},
                "opacity": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.95},
                "margin": {"type": "number", "minimum": 0, "maximum": 0.25, "default": 0.04,
                           "description": "Margin as a fraction of each axis."},
                "blend": {"type": "string", "enum": ["normal", "multiply"], "default": "normal",
                          "description": "multiply keeps the surface shading through the mark."},
                "name": {"type": "string", "maxLength": 120},
            },
            "required": ["plate_asset_id", "logo_asset_id"],
        },
        "handler": _t_place_logo,
    },
    "build_package": {
        "description": ("Build a COMPLETE package, not one image: front panel, back panel "
                        "(ingredients/supplement facts, warnings, company, origin, reserved barcode "
                        "zone), side panel, a flat panel sheet, a print dieline (SVG + PDF) and, when "
                        "a plate is supplied, a mockup. Ask the operator for any missing fact first — "
                        "it will not invent ingredients, claims, an address or a net weight."),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "maxLength": 60, "description": "Product name exactly as it must appear."},
                "subtitle": {"type": "string", "maxLength": 80},
                "weight": {"type": "string", "maxLength": 40, "description": "e.g. NET WT 6 OZ (170 g)"},
                "format": {"type": "string", "enum": ["pouch", "box", "bottle", "tube"],
                           "default": "pouch",
                           "description": "The physical package format; dimensions differ per format."},
                "width_mm": {"type": "number"}, "height_mm": {"type": "number"},
                "gusset_mm": {"type": "number"}, "depth_mm": {"type": "number"},
                "diameter": {"type": "number"}, "label_height": {"type": "number"},
                "label_top_offset": {"type": "number"},
                "usable_height_mm": {"type": "number"},
                "brand": {"type": "string", "maxLength": 80},
                "theme": {"type": "string", "maxLength": 30,
                          "description": "Design palette: forest, midnight, kraft, bone, clay, sage or slate."},
                "design": {"type": "string", "maxLength": 40,
                           "description": "Optional catalogue design key; omit for a dynamic brand design."},
                "servings": {"type": "string", "maxLength": 20},
                "organic_certified": {"type": "boolean", "default": False,
                                      "description": "Render an organic seal only when certification is substantiated."},
                "ingredients": {"type": "array", "items": {"type": "string", "maxLength": 300}, "maxItems": 20},
                "supplement_facts": {"type": "array", "items": {"type": "string", "maxLength": 200}, "maxItems": 30},
                "suggested_use": {"type": "string", "maxLength": 300},
                "warnings": {"type": "array", "items": {"type": "string", "maxLength": 300}, "maxItems": 10},
                "company": {"type": "string", "maxLength": 120},
                "address": {"type": "string", "maxLength": 200},
                "country_of_origin": {"type": "string", "maxLength": 60},
                "lot_code": {"type": "string", "maxLength": 40},
                "claims": {"type": "array", "items": {"type": "string", "maxLength": 60}, "maxItems": 4},
                "icons": {"type": "array",
                          "items": {"type": "string", "enum": ["organic_sprout", "non_gmo", "gluten_free", "fruiting_body"]},
                          "maxItems": 4},
                "plate_asset_id": {"type": "string", "maxLength": 80},
                "logo_asset_id": {"type": "string", "maxLength": 80},
                "allow_incomplete": {"type": "boolean", "default": False,
                                     "description": "Build anyway and draw [MISSING: field] markers. Only when the operator insists."},
            },
            "required": [],
        },
        "handler": _t_build_package,
    },
    "optimize_listing": {
        "description": ("Score and rewrite an Amazon listing against the operator's target keywords: "
                        "deterministic rubric (title, bullets, promo/emoji, keyword coverage), a "
                        "before/after score out of 100, a rewritten title and bullets, backend search "
                        "terms within the 250-byte limit, and a change log. Never invents keywords or "
                        "search volumes; asks when no keywords are supplied."),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "maxLength": 500},
                "bullets": {"type": "array", "items": {"type": "string", "maxLength": 600}, "maxItems": 5},
                "keywords": {"type": "array", "items": {"type": "string", "maxLength": 80}, "maxItems": 30},
                "backend_terms": {"type": "string", "maxLength": 500},
                "description": {"type": "string", "maxLength": 4000},
            },
            "required": ["title", "bullets", "keywords"],
        },
        "handler": _t_optimize_listing,
    },
    "ppc_plan": {
        "description": ("Turn Amazon ad reports into a change plan: validate the upload is really a "
                        "search-term report, harvest converting terms, propose negative exacts, and "
                        "reject any change that references a campaign or ad group absent from the "
                        "source. Report-in, file-out — nothing is uploaded to Amazon."),
        "parameters": {
            "type": "object",
            "properties": {
                "search_terms": {"type": "array", "items": {"type": "object"},
                                 "description": "Parsed search-term rows (campaign, ad group, customer search term, clicks, spend, sales, orders)."},
                "target_acos": {"type": "number", "minimum": 0, "maximum": 5, "default": 0.35},
                "proposed_rows": {"type": "array", "items": {"type": "object"},
                                  "description": "Optional proposed changes to validate against the source."},
                "write_bulk": {"type": "boolean", "default": False,
                               "description": "Write a validated .xlsx planning sheet (Northstar columns, not an official Amazon template)."},
                "default_bid": {"type": "number", "minimum": 0,
                                "description": "Optional bid to apply to harvested exact-match rows."},
            },
            "required": ["search_terms"],
        },
        "handler": _t_ppc_plan,
    },
    "plan_aplus": {
        "description": ("Plan an Amazon A+ page: module list with EXACT pixel sizes (970x600 header, "
                        "970x300 banner, 300x300 x3, 220x220 x4, 1464x600 premium), one render "
                        "prompt per module, the product identity lock, and a screen for prices, "
                        "promotions, shipping claims and competitor references."),
        "parameters": {
            "type": "object",
            "properties": {
                "product": {"type": "string", "maxLength": 120},
                "modules": {"type": "array", "items": {"type": "string", "maxLength": 24}, "maxItems": 10},
                "copy": {"type": "string", "maxLength": 2000},
                "style": {"type": "string", "maxLength": 120},
                "shape": {"type": "string", "maxLength": 200},
                "colour": {"type": "string", "maxLength": 200},
                "logo_text": {"type": "string", "maxLength": 200},
                "parts": {"type": "string", "maxLength": 300},
                "must_not": {"type": "string", "maxLength": 200},
            },
            "required": ["product"],
        },
        "handler": _t_plan_aplus,
    },
    "plan_social": {
        "description": ("Plan ad/social graphics at exact canvas sizes and safe zones for 1:1, 4:5, "
                        "9:16, 16:9 and 2:3, with copy slots and one prompt per aspect."),
        "parameters": {
            "type": "object",
            "properties": {
                "product": {"type": "string", "maxLength": 120},
                "content_type": {"type": "string", "enum": ["ad", "social", "banner", "aplus"]},
                "aspects": {"type": "array", "items": {"type": "string", "enum": ["1:1", "4:5", "9:16", "16:9", "2:3"]}, "maxItems": 5},
                "headline": {"type": "string", "maxLength": 120},
            },
            "required": ["product", "content_type"],
        },
        "handler": _t_plan_social,
    },
    "plan_video": {
        "description": ("Plan a UGC/short video: scene beats timed to the requested duration, the "
                        "frame count at a declared fps, and the exact arithmetic to verify the "
                        "finished clip is the right length (frames / fps, one frame tolerance). "
                        "Rejects a duration the lane does not support instead of promising it."),
        "parameters": {
            "type": "object",
            "properties": {
                "product": {"type": "string", "maxLength": 120},
                "duration_seconds": {"type": "integer", "enum": [5, 10, 15, 30]},
                "hook": {"type": "string", "enum": ["problem", "result", "proof"]},
                "fps": {"type": "integer", "minimum": 12, "maximum": 60},
                "script": {"type": "string", "maxLength": 2000},
            },
            "required": ["product", "duration_seconds"],
        },
        "handler": _t_plan_video,
    },
    "write_content": {
        "description": ("Write ad copy, social captions, email subject/body, brand story or a listing "
                        "bullet, tied to the operator's keywords and screened for disease/treatment "
                        "claims. Returns three variants with keyword coverage per variant."),
        "parameters": {
            "type": "object",
            "properties": {
                "product": {"type": "string", "maxLength": 120},
                "surface": {"type": "string", "enum": ["ad", "social", "email", "brand_story", "listing_bullet"]},
                "keywords": {"type": "array", "items": {"type": "string", "maxLength": 80}, "maxItems": 20},
                "benefits": {"type": "array", "items": {"type": "string", "maxLength": 120}, "maxItems": 5},
                "tone": {"type": "string", "maxLength": 30},
                "brand": {"type": "string", "maxLength": 80},
            },
            "required": ["product", "surface"],
        },
        "handler": _t_write_content,
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
    "purpose_command": {
        "description": ("Evaluate THIS system's own codebase and return a read-only, "
                        "proposal-only report. optimize-architecture = import cycles, "
                        "wide interfaces, most-depended-on modules; refactor-performance "
                        "= long functions, deep nesting, nested loops, blocking calls "
                        "inside async defs, unbounded reads, in-loop string growth, "
                        "missing timeouts; expand-vectors = modules with no test "
                        "reference plus suggested expansion scenarios. It writes nothing "
                        "and never executes the analysed code."),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string",
                            "enum": ["optimize-architecture", "refactor-performance",
                                     "expand-vectors"],
                            "description": "Which purpose command to run."},
                "path": {"type": "string",
                         "description": "Optional sub-path under the repository root "
                                        "(default: the whole repo)."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 60,
                          "description": "Max findings returned by expand-vectors."},
            },
            "required": ["command"],
        },
        "handler": _t_purpose_command,
    },
    "build_preset": {
        "description": ("Resolve a BUILD preset (Thorn v5.0): product_design, coding, "
                        "system_architecture, general_chat. Each carries a system addendum, "
                        "a registered tool subset, a memory-retention depth and a model "
                        "family. Read-only: adopting a preset is the caller's decision, and "
                        "these never replace the six work focus modes. Omit both arguments "
                        "for the whole catalogue."),
        "parameters": {
            "type": "object",
            "properties": {
                "preset": {"type": "string",
                           "enum": ["product_design", "coding", "system_architecture",
                                    "general_chat"],
                           "description": "Which BUILD preset to resolve."},
                "track": {"type": "string",
                          "description": "Alternatively, map an AutothinK router track "
                                         "(build / research / design) onto a preset."},
            },
            "required": [],
        },
        "handler": _t_build_preset,
    },
    "creative_plan": {
        "description": ("Plan and price a CREATIVE job before generating anything. Builds a "
                        "quick or detailed plan (real steps from real tools), quotes the "
                        "in-house credit cost for a draft and a final, lists what it still "
                        "needs from the operator, and returns an interactive plan card with "
                        "four actions: generate draft (cheaper), generate final (best), edit "
                        "the plan, or cancel. Pass action + plan_id to confirm a choice. It "
                        "never generates and never charges credits."),
        "parameters": {
            "type": "object",
            "properties": {
                "request": {"type": "string",
                            "description": "What to make, in the operator's own words.",
                            "minLength": 3, "maxLength": 2000},
                "media": {"type": "string", "enum": ["image", "video"], "default": "image"},
                "detail": {"type": "string", "enum": ["quick", "detailed"], "default": "quick",
                           "description": "quick = fast plan; detailed = prompt scaffold, extra direction and QC."},
                "count": {"type": "integer", "minimum": 1, "maximum": 4, "default": 1},
                "subscription": {"type": "string",
                                 "enum": ["foundation", "scout", "mover", "autothink"],
                                 "default": "foundation",
                                 "description": "Which tier is asking — gates final quality and video."},
                "action": {"type": "string", "enum": ["cancel", "edit", "draft", "final"],
                           "description": "Confirm a plan: cancel | edit | draft | final."},
                "plan_id": {"type": "string",
                            "description": "The plan_id from the plan card (required with action)."},
            },
            "required": [],
        },
        "handler": _t_creative_plan,
    },
    "knowledge_lookup": {
        "description": ("Look up the verified Amazon selling rules for a question and return "
                        "the matched DO / DON'T pairs with source, confidence and pack version. "
                        "Use this before answering any listing, ads, A+, Creator Connections, "
                        "brand-store or reseller policy question. Read-only."),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 3, "maxLength": 500,
                          "description": "The question or topic, in the operator's words."},
                "domain": {"type": "string",
                           "enum": ["listing", "ads-amazon", "aplus", "creator-connections",
                                    "brand-store", "reseller", "ads-google-bing", "creative"],
                           "description": "Optional: restrict to one knowledge domain."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
            },
            "required": ["query"],
        },
        "handler": _t_knowledge_lookup,
    },
    "listing_audit": {
        "description": ("Deterministically audit an Amazon title and up to five bullets: "
                        "character limits, promotional language, all-caps, prohibited claims. "
                        "Returns the failing checks and the rules that apply. Read-only."),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "maxLength": 500},
                "bullets": {"type": "array", "maxItems": 5,
                            "items": {"type": "string", "maxLength": 600}},
            },
            "required": [],
        },
        "handler": _t_listing_audit,
    },
    "ads_math": {
        "description": ("Compute ACOS, break-even ACOS from unit margin, profit per ad dollar "
                        "and TACOS from raw numbers. Use it instead of guessing arithmetic."),
        "parameters": {
            "type": "object",
            "properties": {
                "price": {"type": "number", "minimum": 0},
                "cogs": {"type": "number", "minimum": 0},
                "ad_spend": {"type": "number", "minimum": 0},
                "ad_sales": {"type": "number", "minimum": 0},
                "total_revenue": {"type": "number", "minimum": 0,
                                  "description": "Optional: total revenue for TACOS."},
            },
            "required": ["price"],
        },
        "handler": _t_ads_math,
    },
    "improvement_status": {
        "description": ("Report what Bojo has learned: knowledge coverage, rule count, open "
                        "gaps, pack versions and the last improvement cycle. Read-only."),
        "parameters": {"type": "object", "properties": {}, "required": []},
        "handler": _t_improvement_status,
    },
    "service_catalog": {
        "description": ("List every service area Bojo can act on and the exact tool that "
                        "handles it. Use it when the operator asks what you can do, or when "
                        "a request does not clearly match a service."),
        "parameters": {"type": "object", "properties": {}, "required": []},
        "handler": _t_service_catalog,
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


def _t_bojo_domain(name: str):
    """Adapter: a domain tool takes plain kwargs and returns {ok, tool, data|reason}."""

    def handler(args: Dict[str, Any], ctx: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        from bojo_tools_registry import call  # noqa: PLC0415 - keeps import cost lazy

        result = call(name, **{key: value for key, value in (args or {}).items()
                               if not str(key).startswith("_")})
        payload = result.get("data")
        summary = (f"{name} returned {len(payload)} field(s)."
                   if isinstance(payload, dict) else f"{name} finished.")
        if not result.get("ok"):
            summary = str(result.get("reason") or f"{name} failed.")
        return {"ok": bool(result.get("ok")), "summary": summary[:400],
                "error": "" if result.get("ok") else str(result.get("reason") or "")[:400],
                "data": payload, "assets": []}

    return handler


#: Bojo tools implemented by domain modules (see `bojo_tools_registry`). A service is only
#: drivable by Bojo when its tool is here AND the module behind it exists — which is exactly
#: what the scorecard's `complete` dimension measures.
TOOLS.update({
    "catalog_pull": {
        "description": ("Pull the sourcing catalog for a query and return the rows, with the "
                        "source reported honestly (stock, live, empty). Prospector's tool."),
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "minLength": 2},
            "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            "category": {"type": "string"},
            "live": {"type": "boolean"},
        }, "required": ["query"]},
        "handler": _t_bojo_domain("catalog_pull"),
    },
    "golden_goose_scan": {
        "description": ("Score candidate products through the real Golden Goose economics "
                        "and filters, returning ranked opportunities with tier, scores and "
                        "the arithmetic behind each one."),
        "parameters": {"type": "object", "properties": {
            "candidates": {"type": "array", "items": {"type": "object"}},
            "roi_floor": {"type": "number"},
            "min_monthly_sales": {"type": "integer", "minimum": 0},
            "include_rejected": {"type": "boolean"},
            "limit": {"type": "integer", "minimum": 1, "maximum": 100},
        }, "required": ["candidates"]},
        "handler": _t_bojo_domain("golden_goose_scan"),
    },
    "offer_recommendation": {
        "description": ("Recommend an offer price from cost, target margin, competitor "
                        "prices and fees, with every arithmetic step returned so a seller "
                        "can check it."),
        "parameters": {"type": "object", "properties": {
            "cost": {"type": "number", "minimum": 0},
            "target_margin_pct": {"type": "number", "minimum": 0, "maximum": 99},
            "competitor_prices": {"type": "array", "items": {"type": "number"}},
            "fees": {"type": "object", "description":
                     "Flat fees per unit, e.g. {referral_pct, referral_min, fulfilment, other}"},
            "competitor_policy": {"type": "string", "enum": ["lowest", "median", "ignore"]},
            "undercut_pct": {"type": "number", "minimum": 0, "maximum": 50},
            "currency": {"type": "string"},
        }, "required": ["cost", "target_margin_pct"]},
        "handler": _t_bojo_domain("offer_recommendation"),
    },
    "hub_status": {
        "description": ("Aggregate service health from the real status probes: disk, "
                        "database, lanes, models and the render lock, per component with "
                        "its evidence."),
        "parameters": {"type": "object", "properties": {
            "disk_path": {"type": "string"},
        }, "required": []},
        "handler": _t_bojo_domain("hub_status"),
    },
})


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
