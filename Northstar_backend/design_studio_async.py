"""Design Studio — asynchronous generation lane with credit metering.

Competitive-RE build (2026-10-16): Packify.ai runs generations through a queued,
pausable agent pipeline and meters every feature in credits; DYP.ai deducts
credits per feature (balance/cost/use/history). Northstar's `/generate` is
synchronous and records `credits_used: 0`. This module adds the missing lane
WITHOUT touching the sync endpoint:

- `POST /generate-async` -> creates a `queued` ds job, optionally RESERVES
  credits (real ledger: reserve -> commit on success / release on failure),
  and executes on a bounded worker pool.
- `GET /generate-async/{job_id}` -> job status (+ live balance when enforced).
- Optional `callback_url` on submissions: completion/failure delivers a JSON
  webhook with bounded retries (Packify-style async contract). Delivery never
  fails the job; its result is recorded on the job's params.

Credit policy (honest, alpha-safe):
- Default is METER-ONLY (`DESIGN_CREDITS_ENFORCE=0`): the job records the
  planned cost + preview, but nothing is deducted — matching the current alpha
  posture where the credits meter is display-only.
- With `DESIGN_CREDITS_ENFORCE=1` the mechanic is REAL and fail-closed: a
  first-use plan allotment is granted per account (aligned with the
  `/api/v1/credits/me` display contract), then reserve -> commit/release.
  Insufficient balance refuses the job with HTTP 402.

Everything still runs on the operator's local engine (ComfyUI gate unchanged):
no provider is called, no money is spent.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import sys
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel  # noqa: F401  (kept for type context in docstrings)

from credit_ledger import CreditLedger, InsufficientCredits, allotment_for_plan
from data_layer import get_northstar_db
from design_studio_api import GenerateIn, studio_account

router = APIRouter(prefix="/api/design-studio", tags=["design-studio-async"])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _costs() -> Dict[str, int]:
    return {
        "image": int(os.environ.get("DESIGN_CREDIT_COST_IMAGE", "1")),
        "video": int(os.environ.get("DESIGN_CREDIT_COST_VIDEO", "4")),
    }


def credits_enforced() -> bool:
    return os.environ.get("DESIGN_CREDITS_ENFORCE", "0").strip().lower() in ("1", "true", "yes")


_LEDGER: Optional[CreditLedger] = None


def get_ledger() -> CreditLedger:
    """Process-wide ledger persisted as JSONL under Northstar_backend/data."""
    global _LEDGER
    if _LEDGER is None:
        path = Path(__file__).resolve().parent / "data" / "credit_ledger.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        _LEDGER = CreditLedger(path=str(path))
    return _LEDGER


def ensure_initial_grant(ledger: CreditLedger, account_id: str, plan: str = "foundation") -> None:
    """One idempotent plan allotment per account (matches the display meter)."""
    ledger.grant(account_id, allotment_for_plan(plan),
                 reason=f"alpha plan allotment ({plan})",
                 idempotency_key=f"grant:alpha:{account_id}:{plan}")


_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ds-gen")


def _out_dir() -> Path:
    d = Path(__file__).resolve().parent / "data" / "studio_generated"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _engine_status() -> dict:
    """Indirection so tests can patch the gate without patching studio_generation."""
    import studio_generation as sg
    return sg.engine_status()


# ── Webhooks ────────────────────────────────────────────────────────────────
#
# `callback_url` is caller-supplied and ends up in `urllib.request.urlopen`, so
# it is an SSRF surface, not just a convenience: without a check an authenticated
# caller could point the server at its own cloud metadata IP, at a loopback admin
# port, or at Amazon. The policy below is applied twice - when the job is
# submitted (so the caller gets a 422 instead of a silently failed delivery) and
# again inside `deliver_webhook` before the first request is built.
#
# Deliberate limits, stated so nobody over-trusts the check:
#   * no DNS resolution happens here, so a hostname that resolves to a private
#     address is not caught by this function; the transport-level guard in
#     `tools/egress_guard.py` is what covers Amazon calls everywhere else
#   * IP literals (v4 and v6, including the decimal spellings) are refused
#     outright, so loopback/link-local/private/metadata targets never reach a socket

CALLBACK_SCHEMES = ("http", "https")

#: Comma-separated host suffixes. When set, a callback host must match one of them.
CALLBACK_ALLOW_HOSTS_ENV = "DESIGN_CALLBACK_ALLOWED_HOSTS"
#: Explicit operator/dev opt-in. Loopback is refused by default and allowed only here.
CALLBACK_ALLOW_LOOPBACK_ENV = "DESIGN_CALLBACK_ALLOW_LOOPBACK"

_CALLBACK_MAX_LEN = 2048
_LOOPBACK_NAMES = ("localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback")
#: Decimal (127.1, 2130706433) and hex (0x7f.1) spellings of an IPv4 address.
_NUMERIC_HOST = re.compile(r"^(0x[0-9a-f]+|[0-9]+)(\.(0x[0-9a-f]+|[0-9]+))*$")

_TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
_EGRESS: Any = None


class CallbackRefused(ValueError):
    """A callback URL the service will not deliver to. Never a delivery result."""


def _egress() -> Any:
    """`tools/egress_guard.py` (Amazon list + journal), imported by path."""
    global _EGRESS
    if _EGRESS is None:
        if str(_TOOLS_DIR) not in sys.path:
            sys.path.append(str(_TOOLS_DIR))
        import egress_guard  # noqa: PLC0415 - local-lane tool module
        _EGRESS = egress_guard
    return _EGRESS


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def validate_callback_url(url: Any, *, allow_hosts: Optional[list] = None,
                          allow_loopback: Optional[bool] = None) -> str:
    """Return the URL when it is a legal callback target, else raise CallbackRefused.

    Order matters: the Amazon refusal runs first (it is the hard standing gate),
    then the SSRF rules, then the optional operator allowlist.
    """
    text = "" if url is None else str(url).strip()
    if not text:
        raise CallbackRefused("callback_refused: empty_url")
    if len(text) > _CALLBACK_MAX_LEN:
        raise CallbackRefused(f"callback_refused: url_too_long({len(text)})")

    try:
        parsed = urlsplit(text)
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError as exc:
        raise CallbackRefused(f"callback_refused: unparseable_url({exc})")

    scheme = (parsed.scheme or "").lower()
    if scheme not in CALLBACK_SCHEMES:
        raise CallbackRefused(f"callback_refused: scheme_{scheme or 'missing'}")
    if not host:
        raise CallbackRefused("callback_refused: missing_host")
    if parsed.username or parsed.password:
        raise CallbackRefused("callback_refused: credentials_in_url")
    if port is not None and not (1 <= port <= 65535):
        raise CallbackRefused(f"callback_refused: bad_port({port})")

    # Amazon first: a hardcoded, non-overridable refusal shared with the transport.
    try:
        guard = _egress()
    except Exception as exc:  # noqa: BLE001 - fail closed, never fail open
        raise CallbackRefused(f"callback_refused: egress_guard_unavailable({exc})")
    try:
        guard.check(text, caller="design_studio_async:validate_callback_url")
    except guard.EgressRefused:
        raise CallbackRefused(f"callback_refused: amazon_host({host})")

    if allow_loopback is None:
        allow_loopback = _flag(CALLBACK_ALLOW_LOOPBACK_ENV)

    # IP literals: refused outright. Loopback/link-local/unspecified get a precise
    # reason so the journal and the 422 say what was attempted.
    ip = None
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    if ip is not None:
        if ip.is_loopback and allow_loopback:
            return text
        if ip.is_loopback:
            reason = "loopback_ip"
        elif ip.is_link_local:
            reason = "link_local_ip"
        elif ip.is_unspecified:
            reason = "unspecified_ip"
        elif ip.is_private:
            reason = "private_ip"
        elif ip.is_multicast or ip.is_reserved:
            reason = "reserved_ip"
        else:
            reason = "ip_literal"
        raise CallbackRefused(f"callback_refused: {reason}({ip})")

    if not host:
        raise CallbackRefused("callback_refused: missing_host")
    if _NUMERIC_HOST.match(host):
        raise CallbackRefused(f"callback_refused: numeric_host({host})")

    for name in _LOOPBACK_NAMES:
        if host == name or host.endswith("." + name):
            if allow_loopback:
                return text
            raise CallbackRefused(f"callback_refused: loopback_host({host})")

    allowed = allow_hosts
    if allowed is None:
        raw = os.environ.get(CALLBACK_ALLOW_HOSTS_ENV, "")
        allowed = [h.strip().lower().rstrip(".") for h in raw.split(",") if h.strip()]
    if allowed:
        if not any(host == a or host.endswith("." + a) for a in allowed):
            raise CallbackRefused(f"callback_refused: host_not_allowed({host})")
    return text


def deliver_webhook(url: str, payload: Dict[str, Any], *, attempts: int = 3,
                    timeout: float = 10.0, opener=None) -> Dict[str, Any]:
    """POST JSON to a callback URL with bounded retries. Success = HTTP 2xx.

    The URL is validated first: a refused callback raises `CallbackRefused`
    before a request object exists, so no socket is opened and the caller sees a
    refusal rather than a retry loop.

    Retry policy (Packify-style, bounded): immediate -> 1s -> 4s backoff.
    Never raises on delivery; returns the delivery record stored on the job.
    """
    url = validate_callback_url(url)
    delays = [0.0, 1.0, 4.0]
    data = json.dumps(payload).encode("utf-8")
    last: Dict[str, Any] = {"ok": False, "status": None, "error": None, "attempts": 0}
    for i in range(max(1, int(attempts))):
        delay = delays[min(i, len(delays) - 1)]
        if delay:
            time.sleep(delay)
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "northstar-openapi/1"},
        )
        try:
            call = opener or urllib.request.urlopen
            with call(req, timeout=timeout) as resp:
                status = getattr(resp, "status", None) or resp.getcode()
            last = {"ok": 200 <= int(status) < 300, "status": int(status),
                    "error": None, "attempts": i + 1}
        except urllib.error.HTTPError as exc:  # a server-side non-2xx is a known status
            last = {"ok": False, "status": int(exc.code), "error": f"HTTP {exc.code}",
                    "attempts": i + 1}
        except Exception as exc:  # noqa: BLE001 - delivery is best-effort by design
            last = {"ok": False, "status": None, "error": str(exc)[:200], "attempts": i + 1}
        if last["ok"]:
            break
    return last


def _notify_callback(db, acct: str, job_id: str, body: Dict[str, Any],
                     payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Deliver the job webhook (if a callback was registered) and record it.

    A refused callback is recorded on the job and never breaks the job: the
    artifact is already persisted by the time this runs.
    """
    url = (body or {}).get("callback_url")
    if not url:
        return None
    try:
        result = deliver_webhook(url, payload)
    except CallbackRefused as exc:
        result = {"ok": False, "status": None, "error": str(exc)[:200],
                  "attempts": 0, "refused": True}
    try:
        db.design_studio.jobs.update(
            job_id, {"params": {**{k: v for k, v in body.items() if k != "callback_url"},
                                "callback_url": url, "webhook": result}},
            account_id=acct)
    except Exception:  # noqa: BLE001 - the webhook record must never break the job
        pass
    return result


# ── Job execution ───────────────────────────────────────────────────────────

def run_generation_job(*, job_id: str, acct: str, body: Dict[str, Any],
                       reservation_id: Optional[str] = None,
                       enforce: bool = False,
                       db=None, ledger: Optional[CreditLedger] = None,
                       out_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Execute one queued generation job. Shared by the worker pool and tests."""
    import studio_generation as sg

    db = db or get_northstar_db()
    ledger = ledger if ledger is not None else (get_ledger() if enforce else None)
    out_dir = out_dir or _out_dir()
    kind = body.get("kind", "image")
    db.design_studio.jobs.update(job_id, {"status": "running", "started_at": _now()},
                                 account_id=acct)
    from text_fidelity import render_with_text_guard

    def _render(prompt: str):
        if kind == "video":
            return sg.generate_video(prompt=prompt, width=body.get("width"),
                                     height=body.get("height"), tier=body.get("tier", "draft"),
                                     seed=body.get("seed"))
        return sg.generate_image(prompt=prompt, width=body.get("width"),
                                 height=body.get("height"), tier=body.get("tier", "draft"),
                                 seed=body.get("seed"))
    try:
        guarded = render_with_text_guard(render_fn=_render, brief=body.get("brief") or "",
                                         text_safe=bool(body.get("text_safe")))
    except Exception as exc:  # noqa: BLE001 - recorded on the job, surfaced to the caller
        if enforce and reservation_id and ledger is not None:
            try:
                ledger.release(reservation_id, idempotency_key=f"release:{reservation_id}")
            except KeyError:
                pass
        db.design_studio.jobs.update(job_id, {
            "status": "failed", "logs": str(exc)[:2000],
            "credits_used": 0,  # released (or never charged) on failure
            "finished_at": _now(),
        }, account_id=acct)
        _notify_callback(db, acct, job_id, body, {
            "job_id": job_id, "status": "failed", "error": str(exc)[:400],
            "provenance": {"lane": "async", "provider": "local:comfyui",
                           "note": "Failure before any artifact was produced."},
        })
        return {"status": "failed", "error": str(exc)[:400]}

    out = guarded["out"]
    tf_result = guarded["text_fidelity"]
    fname = f"{uuid.uuid4().hex}.{out['ext']}"
    (out_dir / fname).write_bytes(out["bytes"])
    if guarded.get("raw_bytes") and tf_result is not None:
        raw_key = f"{uuid.uuid4().hex}_raw.{out['ext']}"
        (out_dir / raw_key).write_bytes(guarded["raw_bytes"])
        tf_result = {**tf_result, "raw_storage_key": raw_key}
    aid = db.design_studio.assets.create({
        "account_id": acct,
        "project_id": body.get("project_id"),
        "name": f"{body.get('purpose') or kind} - {out['model']} - {_now()[:16]}",
        "asset_type": f"generated-{kind}",
        "mime_type": out["mime"],
        "storage_key": fname,
        "width": out.get("width"), "height": out.get("height"),
        "duration_seconds": out.get("duration_seconds"),
        "size_bytes": len(out["bytes"]),
        "metadata": {
            "generation": {
                "provider": "comfyui", "model": out["model"], "tier": body.get("tier", "draft"),
                "purpose": body.get("purpose"), "prompt": body["brief"],
                "seed": out.get("seed"), "generated_at": _now(), "lane": "async",
            },
            "note": "Rendered locally on the operator's machine via ComfyUI. Nothing was sent to any provider.",
            **({"text_fidelity": tf_result} if tf_result else {}),
        },
    })
    if enforce and reservation_id and ledger is not None:
        try:
            ledger.commit(reservation_id, idempotency_key=f"commit:{reservation_id}")
        except KeyError:
            pass
    db.design_studio.jobs.update(job_id, {
        "status": "done", "result_ids": [aid], "finished_at": _now(),
    }, account_id=acct)
    _notify_callback(db, acct, job_id, body, {
        "job_id": job_id, "status": "done", "asset_ids": [aid],
        "asset_urls": [f"/api/design-studio/assets/{aid}/file"],
        "text_fidelity": tf_result,
        "provenance": {"lane": "async", "provider": "local:comfyui",
                       "note": "Rendered locally on the operator's machine; no provider received the data."},
    })
    return {"status": "done", "asset_id": aid, "text_fidelity": tf_result}


def submit_generation(acct: str, *, brief: str, kind: str = "image", tier: str = "draft",
                      purpose: Optional[str] = None, width: Optional[int] = None,
                      height: Optional[int] = None, seed: Optional[int] = None,
                      project_id: Optional[str] = None,
                      callback_url: Optional[str] = None,
                      text_safe: bool = False) -> Dict[str, Any]:
    """Create the queued job (+reservation) and schedule it. Raises HTTPException on gates."""
    if kind not in ("image", "video"):
        raise ValueError("kind must be image or video")
    if callback_url:
        try:
            callback_url = validate_callback_url(callback_url)
        except CallbackRefused as exc:
            raise HTTPException(status_code=422, detail={
                "code": "callback_url_refused", "message": str(exc),
                "note": ("A callback must be an http(s) URL on a named host; IP literals, "
                         "loopback and Amazon hosts are refused.")})
    st = _engine_status()
    if not st.get("armed"):
        raise HTTPException(status_code=409, detail={
            "code": "engine_not_armed",
            "message": ("The local media engine is not armed. Set MEDIA_GEN_LIVE=1 and keep "
                        "ComfyUI reachable at COMFYUI_URL (see the Engine card)."),
            "engine": st,
        })

    enforce = credits_enforced()
    cost = _costs()[kind]
    ledger = get_ledger() if enforce else None
    reservation: Optional[Dict[str, Any]] = None
    if enforce and ledger is not None:
        ensure_initial_grant(ledger, acct)
        try:
            res = ledger.reserve(acct, cost, action=f"design_studio.{kind}",
                                 idempotency_key=f"reserve:{uuid.uuid4().hex}")
        except InsufficientCredits as exc:
            raise HTTPException(status_code=402, detail={
                "code": "insufficient_credits", "message": str(exc), "cost": cost,
            })
        reservation = {"reservation_id": res.reservation_id, "amount": cost}

    db = get_northstar_db()
    job_id = db.design_studio.jobs.create({
        "account_id": acct,
        "project_id": project_id,
        "job_type": f"generate-{kind}",
        "provider": "local:comfyui",
        "status": "queued",
        "cost_preview": {
            "provider": "local",
            "credits": cost,
            "enforced": enforce,
            "note": ("Local compute on the operator's GPU; nothing paid. "
                     f"Credit enforcement {'ON' if enforce else 'OFF (meter-only alpha)'}."),
        },
        "params": {"purpose": purpose, "tier": tier, "brief": brief,
                   "width": width, "height": height, "seed": seed,
                   "callback_url": callback_url, "text_safe": text_safe},
        "credits_used": cost if enforce else 0,
    })
    _EXECUTOR.submit(run_generation_job, job_id=job_id, acct=acct,
                     body={"kind": kind, "brief": brief, "tier": tier, "width": width,
                           "height": height, "seed": seed, "project_id": project_id,
                           "purpose": purpose, "callback_url": callback_url,
                           "text_safe": text_safe},
                     reservation_id=(reservation or {}).get("reservation_id"),
                     enforce=enforce)
    return {
        "job": db.design_studio.jobs.get_by_id(job_id, account_id=acct),
        "reservation": reservation,
        "enforce": enforce,
        "engine": st,
    }


@router.post("/generate-async", status_code=202)
def generate_async(body: GenerateIn, acct: str = Depends(studio_account)):
    """Queue a local generation. Same gates as /generate; returns immediately."""
    try:
        return submit_generation(acct, brief=body.brief, kind=body.kind, tier=body.tier,
                                 purpose=body.purpose, width=body.width, height=body.height,
                                 seed=body.seed, project_id=body.project_id,
                                 text_safe=body.text_safe)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


# ── Video assembly lane (V2) ────────────────────────────────────────────────
# Mirrors the generation pattern above (gate -> optional reserve -> job row ->
# executor -> status/asset/webhook) rather than forking it, with one deliberate
# difference: assembly needs FFmpeg + PIL, NOT the GPU engine. Gating it on
# ComfyUI would refuse a job that does not use ComfyUI.

def assembly_available() -> Dict[str, Any]:
    """Is the assembly lane runnable? FFmpeg is the only requirement."""
    import shutil
    exe = shutil.which("ffmpeg")
    return {"ready": bool(exe), "ffmpeg": exe,
            "needs_engine": False,
            "note": "Assembly is FFmpeg + PIL on stills; it never touches the GPU lane."}


def _assembly_cost() -> int:
    # 0 by default: local FFmpeg costs nothing. Still metered when enforcement is on.
    return int(os.environ.get("DESIGN_CREDIT_COST_ASSEMBLE", "0"))


def _resolve_assembly_inputs(db, acct: str, images, out_dir: Path):
    """Asset ids only, or a path already inside the studio output dir.

    Arbitrary filesystem paths are refused on purpose: a job parameter must not
    be able to read any file on the machine.
    """
    from pathlib import Path as _P
    resolved = []
    for item in images or []:
        item = str(item)
        rec = db.design_studio.assets.get_by_id(item, account_id=acct) if db is not None else None
        if rec and rec.get("storage_key"):
            path = out_dir / _P(str(rec["storage_key"])).name
            if not path.is_file():
                raise FileNotFoundError(f"asset {item!r} has no file on disk")
            resolved.append(path)
            continue
        candidate = _P(item)
        try:
            candidate.resolve().relative_to(out_dir.resolve())
        except Exception:
            raise ValueError(f"input {item!r} is neither an asset id nor a file in the studio "
                             "output directory")
        if not candidate.is_file():
            raise FileNotFoundError(f"input file not found: {item}")
        resolved.append(candidate)
    if not resolved:
        raise ValueError("at least one input image is required")
    return resolved


def run_assembly_job(*, job_id: str, acct: str, body: Dict[str, Any],
                     reservation_id: Optional[str] = None, enforce: bool = False,
                     db=None, ledger: Optional[CreditLedger] = None,
                     out_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Execute one queued assembly job. Same status/asset/webhook contract as a render."""
    import studio_video_assemble as sva

    db = db or get_northstar_db()
    ledger = ledger if ledger is not None else (get_ledger() if enforce else None)
    out_dir = out_dir or _out_dir()
    db.design_studio.jobs.update(job_id, {"status": "running", "started_at": _now()},
                                 account_id=acct)
    try:
        images = _resolve_assembly_inputs(db, acct, body.get("images"), out_dir)
        widths = int(body.get("width") or 1080)
        heights = int(body.get("height") or 1920)
        meta = sva.assemble(
            images,
            captions=body.get("captions") or [],
            narration=body.get("narration"),
            out_path=out_dir / f"{uuid.uuid4().hex}.mp4",
            seconds_per_shot=float(body.get("seconds") or 4.0),
            size=(widths, heights),
        )
    except Exception as exc:  # noqa: BLE001 - recorded on the job, surfaced to the caller
        if enforce and reservation_id and ledger is not None:
            try:
                ledger.release(reservation_id, idempotency_key=f"release:{reservation_id}")
            except KeyError:
                pass
        db.design_studio.jobs.update(job_id, {
            "status": "failed", "ended_at": _now(), "credits_used": 0,
            "error": str(exc)[:400],
        }, account_id=acct)
        _notify_callback(db, acct, job_id, body, {
            "job_id": job_id, "status": "failed", "error": str(exc)[:400],
            "provenance": {"lane": "assemble", "provider": "local:ffmpeg",
                           "note": "Failure before any artifact was produced."},
        })
        return {"status": "failed", "error": str(exc)[:400]}

    path = Path(meta["out_path"])
    probe = meta.get("probe") or {}
    video = next((s for s in probe.get("streams", []) if s.get("type") == "video"), {})
    aid = db.design_studio.assets.create({
        "account_id": acct,
        "project_id": body.get("project_id"),
        "name": body.get("name") or f"assembled clip - {_now()[:16]}",
        "asset_type": "generated-video",
        "mime_type": "video/mp4",
        "storage_key": path.name,
        "width": video.get("width"), "height": video.get("height"),
        "duration_seconds": probe.get("duration_s"),
        "size_bytes": probe.get("size_bytes") or path.stat().st_size,
        "metadata": {
            "assembly": {
                "shots": meta.get("shots"), "seconds_per_shot": meta.get("seconds_per_shot"),
                "captions": meta.get("captions"), "audio": meta.get("audio"),
                "audio_present": meta.get("audio_present"),
                "probe": probe, "assembled_at": _now(), "lane": "assemble",
            },
            "note": "Assembled locally from the operator's own stills with FFmpeg. "
                    "Nothing was generated and nothing was sent to any provider.",
        },
    })
    if enforce and reservation_id and ledger is not None:
        try:
            ledger.commit(reservation_id, idempotency_key=f"commit:{reservation_id}")
        except KeyError:
            pass
    db.design_studio.jobs.update(job_id, {
        "status": "done", "ended_at": _now(), "asset_id": aid,
        "credits_used": _assembly_cost() if enforce else 0,
        "duration_seconds": probe.get("duration_s"),
    }, account_id=acct)
    _notify_callback(db, acct, job_id, body, {
        "job_id": job_id, "status": "done", "asset_ids": [aid],
        "provenance": {"lane": "assemble", "provider": "local:ffmpeg",
                       "duration_s": probe.get("duration_s")},
    })
    return {"status": "done", "asset_id": aid, "duration_s": probe.get("duration_s")}


def submit_assembly(acct: str, *, images, captions=None, narration: Optional[str] = None,
                    seconds: float = 4.0, width: int = 1080, height: int = 1920,
                    project_id: Optional[str] = None,
                    callback_url: Optional[str] = None,
                    name: Optional[str] = None) -> Dict[str, Any]:
    """Queue a video assembly. Raises HTTPException when FFmpeg is absent."""
    if callback_url:
        try:
            callback_url = validate_callback_url(callback_url)
        except CallbackRefused as exc:
            raise HTTPException(status_code=422, detail={
                "code": "callback_url_refused", "message": str(exc),
                "note": ("A callback must be an http(s) URL on a named host; IP literals, "
                         "loopback and Amazon hosts are refused.")})
    st = assembly_available()
    if not st["ready"]:
        raise HTTPException(status_code=409, detail={
            "code": "ffmpeg_missing",
            "message": "Video assembly needs FFmpeg on PATH; it is not installed. "
                       "The GPU engine is not required for this lane.",
            "assembly": st,
        })
    enforce = credits_enforced()
    cost = _assembly_cost()
    ledger = get_ledger() if enforce else None
    reservation: Optional[Dict[str, Any]] = None
    if enforce and ledger is not None and cost > 0:
        ensure_initial_grant(ledger, acct)
        try:
            res = ledger.reserve(acct, cost, action="design_studio.assemble",
                                 idempotency_key=f"reserve:{uuid.uuid4().hex}")
        except InsufficientCredits as exc:
            raise HTTPException(status_code=402, detail={
                "code": "insufficient_credits", "message": str(exc), "cost": cost})
        reservation = {"reservation_id": res.reservation_id, "amount": cost}

    db = get_northstar_db()
    job_id = db.design_studio.jobs.create({
        "account_id": acct, "project_id": project_id,
        "job_type": "assemble-video", "provider": "local:ffmpeg", "status": "queued",
        "cost_preview": {"provider": "local", "credits": cost, "enforced": enforce,
                         "note": "Local FFmpeg assembly; nothing paid. "
                                 f"Credit enforcement {'ON' if enforce else 'OFF'}."},
        "params": {"images": list(images or []), "captions": list(captions or []),
                   "narration": narration, "seconds": seconds, "width": width,
                   "height": height, "callback_url": callback_url, "name": name},
        "credits_used": cost if enforce else 0,
    })
    _EXECUTOR.submit(run_assembly_job, job_id=job_id, acct=acct,
                     body={"images": list(images or []), "captions": list(captions or []),
                           "narration": narration, "seconds": seconds, "width": width,
                           "height": height, "project_id": project_id,
                           "callback_url": callback_url, "name": name},
                     reservation_id=(reservation or {}).get("reservation_id"),
                     enforce=enforce)
    return {"job": db.design_studio.jobs.get_by_id(job_id, account_id=acct),
            "reservation": reservation, "enforce": enforce, "assembly": st}


class AssembleIn(BaseModel):  # noqa: F811 - defined here to keep the lane self-contained
    images: list = []
    captions: list = []
    narration: Optional[str] = None
    seconds: float = 4.0
    width: int = 1080
    height: int = 1920
    project_id: Optional[str] = None
    callback_url: Optional[str] = None
    name: Optional[str] = None


@router.post("/assemble-async", status_code=202)
def assemble_async(body: AssembleIn, acct: str = Depends(studio_account)):
    """Queue a video assembly from stills. Returns immediately."""
    return submit_assembly(acct, images=body.images, captions=body.captions,
                           narration=body.narration, seconds=body.seconds,
                           width=body.width, height=body.height,
                           project_id=body.project_id, callback_url=body.callback_url,
                           name=body.name)


@router.get("/generate-async/{job_id}")
def async_status(job_id: str, acct: str = Depends(studio_account)):
    """Poll a queued/running/done job (credits view included when enforced)."""
    db = get_northstar_db()
    job = db.design_studio.jobs.get_by_id(job_id, account_id=acct)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    payload: Dict[str, Any] = {"job": job, "enforce": credits_enforced()}
    if credits_enforced():
        payload["balance"] = get_ledger().balance(acct)
    return payload
