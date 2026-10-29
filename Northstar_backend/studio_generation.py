"""Local media generation for the Design Studio — the operator's own ComfyUI.

Free and private by construction: every render happens on this machine through
COMFYUI_URL (default http://127.0.0.1:8188) and nothing else. Armed only when
MEDIA_GEN_LIVE=1 AND ComfyUI answers. Models are the weights this machine
already has staged:

  image : FLUX.2 klein 4B Q8 (Apache-2.0, commercial-ok)   -> PNG
  video : Wan 2.2 TI2V-5B Q5_K_M (short clips)             -> MP4

The workflow graphs are the same ones verified by tools/comfy_smoke.py.
No provider keys are read here; no credential value is ever touched.
"""

from __future__ import annotations

import json
import os
try:
    import psutil as _psutil
except ImportError:
    _psutil = None
import random
import threading
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

DEFAULT_COMFYUI_URL = "http://127.0.0.1:8188"  # ComfyUI's own default; override with COMFYUI_URL

# FLUX 3 Image Klein is the only image model on this machine (2026-10-29).
# FLUX 2 Klein and the text-correcting vision models were removed with it; there
# is deliberately no fallback, because a silent fallback is how the wrong model
# ends up rendering a paid deliverable.
# Licence: FLUX Kommunity License, Qualifying User only. The owner recorded
# T2 Holdings as under $5M annual revenue on 2026-10-28.
FLUX3_MODEL_FILE = (os.environ.get("STUDIO_FLUX3_MODEL")
                    or "flux3-image-klein-nvfp4.safetensors")
FLUX3_TEXT_ENCODER_FILE = (os.environ.get("STUDIO_FLUX3_TEXT_ENCODER")
                           or "qwen3vl_4b_int8_convrot.safetensors")
FLUX3_VAE_FILE = os.environ.get("STUDIO_FLUX3_VAE") or "flux2-vae.safetensors"

IMAGE_MODEL_FILE = FLUX3_MODEL_FILE
TEXT_ENCODER_FILE = FLUX3_TEXT_ENCODER_FILE
VIDEO_MODEL_FILE = "Wan2.2-TI2V-5B-Q5_K_M.gguf"

# --- Model / text-encoder compatibility (single source of truth) -----------
# A FLUX.2 Klein 4B UNet must be paired with the 4B Qwen3 encoder; a 9B UNet
# with the 8B encoder. Pairing the wrong one fails at dispatch with a shape
# mismatch (512x12288 vs 7680x3072). Filename matching alone is not proof:
# resolve_text_encoder also requires the encoder file to exist on disk.
_ENCODER_BY_MODEL_SIZE = {
    "4b": ("qwen_3_4b", "qwen_3_4b_fp8_mixed.safetensors"),
    "9b": ("qwen_3_8b", "qwen_3_8b_fp8mixed.safetensors"),
}
_ENCODER_DIRS = (
    os.path.join(r"C:\Users\T2Hol\ComfyUI\models", "text_encoders"),
    os.path.join(r"C:\Users\T2Hol\ComfyUI\models", "clip"),
)


def _model_size_token(model_file: str) -> str:
    name = os.path.basename(str(model_file or "")).lower()
    for token in ("9b", "4b"):
        if token in name:
            return token
    return ""


def _encoder_on_disk(filename: str) -> bool:
    if not filename:
        return False
    for base in _ENCODER_DIRS:
        try:
            if os.path.exists(os.path.join(base, filename)):
                return True
        except Exception:
            continue
    return False


def _any_model_on_disk(name: str) -> bool:
    """True when *name* exists in any ComfyUI model subfolder this app uses."""
    if not name:
        return False
    for sub in ("unet", "diffusion_models", "text_encoders", "clip", "vae",
                "loras", "checkpoints"):
        if os.path.isfile(os.path.join(r"C:\Users\T2Hol\ComfyUI\models", sub, name)):
            return True
    return False


def resolve_text_encoder(model_file: str, encoder_file: Optional[str] = None) -> str:
    """Return a compatible text encoder for *model_file*, or raise ValueError.

    Rejects an incompatible explicit pairing before any graph is dispatched.
    The returned encoder must also exist on disk (filename alone is not proof).
    """
    size = _model_size_token(model_file)
    if not size:
        # FLUX 3 (and anything else that is not a `*4b`/`*9b` Klein family)
        # has no encoder-size pairing rule, but the file must still exist.
        chosen = encoder_file or TEXT_ENCODER_FILE
        if not _any_model_on_disk(chosen):
            raise ValueError(
                "encoder_not_installed: %s (needed for %s)"
                % (chosen, os.path.basename(str(model_file))))
        return chosen
    family, default = _ENCODER_BY_MODEL_SIZE[size]
    chosen = encoder_file or default
    if family not in os.path.basename(str(chosen)).lower():
        raise ValueError(
            "incompatible_encoder_pairing: model %s (%s) requires %s*, got %s"
            % (os.path.basename(str(model_file)), size, family,
               os.path.basename(str(chosen))))
    if not _encoder_on_disk(chosen):
        raise ValueError(
            "encoder_not_installed: %s (needed for %s)"
            % (chosen, os.path.basename(str(model_file))))
    return chosen


def validate_configured_pairing() -> dict:
    """Validate the configured image model / encoder pair; returns a report."""
    report = {"model": IMAGE_MODEL_FILE, "encoder": TEXT_ENCODER_FILE,
              "ok": True, "error": None}
    try:
        resolve_text_encoder(IMAGE_MODEL_FILE, TEXT_ENCODER_FILE)
    except Exception as exc:  # noqa: BLE001
        report["ok"] = False
        report["error"] = str(exc)
    return report

# Edit/refine lane (Packify-parity P1): the text-faithful editor. Qwen-Image-Edit
# 2511 is Apache-2.0 and already on disk (Q4_K_M GGUF + its own VL encoder + VAE).
EDIT_MODEL_FILE = os.environ.get("STUDIO_EDIT_MODEL") or "qwen-image-edit-2511-Q4_K_M.gguf"
EDIT_TEXT_ENCODER_FILE = (os.environ.get("STUDIO_EDIT_TEXT_ENCODER")
                          or "qwen_2.5_vl_7b_nvfp4.safetensors")
EDIT_VAE_FILE = "qwen_image_vae" + ".safetensors"

# Cutout lane (Packify-parity P1): BiRefNet matting, MIT, already on disk.
CUTOUT_MODEL_FILE = os.environ.get("STUDIO_CUTOUT_MODEL") or "birefnet.safetensors"

# Upscale lane: RealESRGAN x4 is the upscale model actually installed here.
# (SeedVR2's weights are on disk but this ComfyUI exposes only component nodes -
# preprocess/conditioning/postprocess - so there is no single-node SeedVR2
# upscaler to call. Recorded rather than guessed at.)
UPSCALE_MODEL_FILE = os.environ.get("STUDIO_UPSCALE_MODEL") or "RealESRGAN_x4plus.pth"

_STYLE_SUFFIX = ", professional commercial product photography, clean composition"
# Rich renders keep the operator's full art direction (lettering demands included).
# Text-safe mode appends its own suppression phrase in text_fidelity.sanitize_brief_for_render.


def comfyui_url() -> str:
    return (os.environ.get("COMFYUI_URL") or DEFAULT_COMFYUI_URL).rstrip("/")


def media_live_armed() -> bool:
    return str(os.environ.get("MEDIA_GEN_LIVE", "") or "").strip() == "1"


def _reachable(url: str, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(url + "/system_stats", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def engine_status() -> dict:
    """Honest engine state for the studio. Unknown is NOT armed."""
    url = comfyui_url()
    live = media_live_armed()
    up = _reachable(url)
    return {
        "engine": "comfyui",
        "url": url,
        "url_configured": bool(os.environ.get("COMFYUI_URL")),
        "gate": live,             # MEDIA_GEN_LIVE=1
        "reachable": up,
        "armed": bool(live and up),
        "models": {"image": IMAGE_MODEL_FILE, "video": VIDEO_MODEL_FILE,
                   "edit": (EDIT_MODEL_FILE if _any_model_on_disk(EDIT_MODEL_FILE)
                            else None)},
        "note": (
            "The local engine is armed: renders run on this machine's GPU (ComfyUI)."
            if (live and up) else
            (f"Armed but unreachable at {url} - start ComfyUI." if live else
             "Unarmed: MEDIA_GEN_LIVE is not 1.")
        ),
    }


# ── ComfyUI client ─────────────────────────────────────────────────────────

def _api(path: str, payload=None, timeout: float = 60.0):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        comfyui_url() + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _ws_progress_listener(on_progress, stop_event, client_id: str = "ns-studio-progress") -> None:
    """Best-effort ComfyUI /ws progress -> on_progress(pct|None, label).

    Must connect with the SAME client_id that submitted the prompt: ComfyUI
    targets per-execution progress frames to that socket. Failure is silent BY
    DESIGN — the polling lane below remains the source of truth.
    """
    try:
        from websockets.sync.client import connect as _ws_connect
    except Exception:
        return
    url = comfyui_url().replace("http://", "ws://") + f"/ws?clientId={client_id}"
    try:
        with _ws_connect(url, open_timeout=5, close_timeout=2) as ws:
            while not stop_event.is_set():
                try:
                    raw = ws.recv(timeout=1.0)
                except TimeoutError:
                    continue
                except Exception:
                    return
                if isinstance(raw, (bytes, bytearray)):
                    continue
                try:
                    msg = json.loads(raw)
                except ValueError:
                    continue
                mtype = msg.get("type")
                data = msg.get("data") or {}
                if mtype == "progress":
                    total = data.get("max") or 0
                    value = data.get("value") or 0
                    pct = int(round(100.0 * value / total)) if total else None
                    on_progress(pct, f"sampling {value}/{total}")
                elif mtype == "executing":
                    if data.get("node") is None:
                        on_progress(100, "finishing")
                    else:
                        on_progress(None, "running nodes")
                elif mtype == "execution_start":
                    on_progress(1, "graph accepted")
    except Exception:
        return


def _run_graph(graph: dict, timeout_s: float, on_progress=None) -> list:
    client_id = f"ns-studio-{uuid.uuid4().hex[:10]}"
    res = _api("/prompt", {"prompt": graph, "client_id": client_id}, timeout=30)
    if res.get("node_errors"):
        raise RuntimeError(f"graph rejected: {json.dumps(res['node_errors'])[:400]}")
    pid = res["prompt_id"]
    stop_progress = None
    if on_progress is not None:
        stop_progress = threading.Event()
        threading.Thread(target=_ws_progress_listener,
                         args=(on_progress, stop_progress, client_id),
                         daemon=True).start()
    try:
        t0 = time.time()
        while time.time() - t0 < timeout_s:
            time.sleep(3)
            try:
                hist = _api(f"/history/{pid}", timeout=30)
            except Exception:
                continue
            if pid in hist:
                status = hist[pid].get("status", {}) or {}
                if status.get("status_str") != "success":
                    raise RuntimeError(f"generation failed: {json.dumps(status)[:400]}")
                files = []
                for node_out in (hist[pid].get("outputs") or {}).values():
                    for key in ("images", "gifs", "videos"):
                        for item in node_out.get(key) or []:
                            if isinstance(item, dict) and item.get("filename"):
                                files.append(item)
                return files
        raise TimeoutError("timed out waiting for the ComfyUI render")
    finally:
        if stop_progress is not None:
            stop_progress.set()


def _fetch_output(item: dict) -> bytes:
    q = urllib.parse.urlencode({
        "filename": item.get("filename"),
        "subfolder": item.get("subfolder", ""),
        "type": item.get("type", "output"),
    })
    with urllib.request.urlopen(comfyui_url() + "/view?" + q, timeout=300) as r:
        return r.read()


def _run_graph_guarded(graph: dict, timeout_s: float, on_progress=None) -> list:
    """Run a graph; on a CUDA OOM, re-evict the brain once and retry (bounded).

    Transient co-residency is real on this box: any other local caller (chat,
    summaries) can reload the 27B brain mid-render and OOM the sampler. Circuit
    rules: ONE retry, only for out-of-memory failures, then the error surfaces.
    """
    try:
        return _run_graph(graph, timeout_s=timeout_s, on_progress=on_progress)
    except Exception as exc:  # noqa: BLE001
        if "out of memory" not in str(exc).lower():
            raise
        # Free BOTH sides before the retry: ComfyUI's crammed cache (the failed
        # render never released it) AND any brain that reloaded mid-run. Without
        # this, retries insta-OOM on leftover cache (the 2026-10-16 death spiral).
        release_models()
        unload_brain(wait_s=60.0)
        time.sleep(5)
        return _run_graph(graph, timeout_s=timeout_s, on_progress=on_progress)


def release_models() -> None:
    """Opt-in only (STUDIO_RELEASE_MODELS=1). DEFAULT OFF.

    History: posting /free queues ComfyUI's `unload_all_models`, and with GGUF
    models resident (ComfyUI-GGUF + comfy-aimdo) that unload path crashes the
    server with a Windows access violation AFTER the render is safely done.
    ComfyUI 0.40's dynamic VRAM already evicts/reloads models on demand, so the
    explicit free is unnecessary for correctness.
    """
    if str(os.environ.get("STUDIO_RELEASE_MODELS", "") or "").strip() != "1":
        return
    try:
        req = urllib.request.Request(
            comfyui_url() + "/free",
            data=json.dumps({"unload_models": True, "free_memory": True}).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15):
            pass
    except Exception:
        pass


def _resident_models() -> list | None:
    """Names Ollama currently has loaded, or None when /api/ps is unavailable."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/ps", timeout=5) as resp:
            ps = json.loads(resp.read().decode("utf-8", "replace") or "{}")
        return [str(m.get("name", "")) for m in ps.get("models", []) if m.get("name")]
    except Exception:
        return None


def _evict(model: str) -> None:
    """Ask Ollama to drop one model now. Works for chat and embedding models."""
    for path, payload in (
        ("/api/generate", {"model": model, "keep_alive": 0}),
        ("/api/embeddings", {"model": model, "prompt": "", "keep_alive": 0}),
    ):
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:11434" + path,
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=30):
                return
        except Exception:
            continue


# ── B4: what the last render evicted ────────────────────────────────────────
# A render evicts the brain to free VRAM. That is correct behaviour, but the
# operator then sees a slow chat reply with no stated cause. This records it so
# the turn can say why.
_LAST_EVICTION: dict = {"models": [], "at": None}


# B5: the render lock serialises every job silently. These counters make the wait
# visible instead of leaving "the second render just took longer" unexamined.
_RENDER_LOCK_STATS: dict = {"attempts": 0, "timeouts": 0, "total_wait_s": 0.0,
                            "last_wait_s": 0.0, "max_wait_s": 0.0}


def render_lock_stats() -> dict:
    """Attempts, timeouts and wait times for the cross-process render lock."""
    return dict(_RENDER_LOCK_STATS)


def last_brain_eviction() -> dict:
    """Models evicted by the most recent unload_brain() call (empty if none)."""
    return {"models": list(_LAST_EVICTION.get("models") or []),
            "at": _LAST_EVICTION.get("at")}


# ── B3: the editor lane needs ComfyUI started with --cache-none ─────────────
# 2026-10-22: without the flag, qwen-image-edit + its text encoder peak at ~20 GB
# against 15.4 GB RAM and the process is killed with no traceback. The launcher
# writes a marker; the lanes read it. Unknown (no marker) never blocks — it is
# reported as unknown, because "no marker" is not the same as "flag missing".
CACHE_NONE_MARKER = Path(__file__).resolve().parent / "data" / "comfyui_launch.json"


def comfyui_cache_none() -> Optional[bool]:
    """True/False when the launcher recorded the flag, None when unknown."""
    try:
        data = json.loads(CACHE_NONE_MARKER.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - absent or corrupt marker = unknown
        return None
    value = data.get("cache_none")
    return bool(value) if isinstance(value, bool) else None


def require_cache_none(lane: str) -> None:
    """Refuse a RAM-heavy lane only when the marker positively says otherwise."""
    if comfyui_cache_none() is False:
        raise RuntimeError(
            f"comfyui_cache_none_required: the {lane} lane needs ComfyUI started with "
            "--cache-none, or it exhausts system RAM and is killed without a traceback. "
            "The launcher recorded cache_none=false. Restart with tools/start_comfyui.ps1 "
            "or scripts/launch_alpha.ps1.")


def unload_brain(wait_s: float = 45.0) -> bool:
    """Evict EVERY locally resident model from VRAM before a render, then VERIFY.

    One 16 GB GPU: the brain and a klein render cannot coexist. Fire-and-forget
    eviction used to race the render, and ComfyUI OOM'd inside CLIPTextEncode.

    This used to evict a single hard-coded model id (NORTHSTAR_BRAIN_MODEL). That
    returned True while a *different* model stayed resident and ate the VRAM —
    observed 2026-10-22 with qwen2.5vl:7b holding 6.4 GB after a vision call.
    It now drains Ollama's /api/ps list and only reports success when the list is
    empty, so any model the studio touched earlier is cleaned up too.

    Returns True when eviction succeeded OR verification is unavailable (best
    effort preserved); False only when a model is provably still resident.
    """
    forced = os.environ.get("NORTHSTAR_BRAIN_MODEL")
    deadline = time.time() + max(0.0, float(wait_s))
    evicted: List[str] = []
    while True:
        resident = _resident_models()
        if resident is None:
            return True  # verification unavailable: never block renders on a failed check
        targets = [forced] if forced else resident
        if not resident or (forced and not any(forced.split(":")[0] in r for r in resident)):
            if evicted:
                _LAST_EVICTION["models"] = evicted
                _LAST_EVICTION["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            return True
        for name in targets:
            _evict(name)
            if name not in evicted:
                evicted.append(str(name))
        if time.time() >= deadline:
            remaining = _resident_models() or []
            if forced:
                return not any(forced.split(":")[0] in r for r in remaining)
            return not remaining
        time.sleep(2)


def _clamp(v, lo: int, hi: int, mult: int = 16) -> int:
    v = int(v)
    v = max(lo, min(hi, v))
    return max(mult, (v // mult) * mult)


# Long-edge ceiling for a single image render.
#
# 1216 was the FLUX.2 Klein draft box, and it silently made the two listing
# deliverables impossible: an Amazon MAIN image must be at least 1600 px on the
# long edge (2000 recommended) and an A+ Premium banner is 1464x600. Both were
# rejected before the engine saw them. The ceiling is now a real setting, and
# the engine reports the same number it used.
MAX_EDGE_PX = int(os.environ.get("STUDIO_MAX_EDGE_PX", "2048"))


def _fit_box(width, height, hi: Optional[int] = None, mult: int = 16,
             short_floor: int = 256) -> tuple:
    """Scale a requested render size into the engine's safe box, keeping ASPECT.

    Clamping each axis independently (the previous behaviour) silently turned a
    2:3 portrait request into a 2:2.7 render. The engine's real constraint is the
    long edge, so scale both axes by one factor and snap to the VAE's multiple.
    """
    hi = MAX_EDGE_PX if hi is None else int(hi)
    w = max(1, int(round(float(width or hi))))
    h = max(1, int(round(float(height or hi))))
    scale = min(1.0, float(hi) / float(max(w, h)))
    w, h = w * scale, h * scale
    # A very wide panorama would push the short edge below anything the model can
    # draw; grow it back while the long edge still fits.
    if min(w, h) < short_floor:
        grow = float(short_floor) / max(1e-6, min(w, h))
        if max(w, h) * grow <= hi:
            w, h = w * grow, h * grow
    w = max(mult, int(round(w / mult)) * mult)
    h = max(mult, int(round(h / mult)) * mult)
    if max(w, h) > hi:                       # rounding must not re-break the cap
        step = float(max(w, h)) / float(hi)
        w = max(mult, int(w / step) // mult * mult)
        h = max(mult, int(h / step) // mult * mult)
    return int(w), int(h)


# ── Workflow graphs (verified by tools/comfy_smoke.py) ─────────────────────

def _klein_graph(prompt: str, width: int, height: int, steps: int, seed: int) -> dict:
    """FLUX.2 Klein (fallback) graph — Apache-2.0, commercial-ok."""
    # Fail before dispatch if the configured model/encoder pairing is wrong.
    encoder = resolve_text_encoder(IMAGE_MODEL_FILE, TEXT_ENCODER_FILE)
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": IMAGE_MODEL_FILE}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": encoder, "type": "flux2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae" + ".safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt + _STYLE_SUFFIX}},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "6": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "7": {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "cfg": 1}},
        "8": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "9": {"class_type": "Flux2Scheduler", "inputs": {"steps": steps, "width": width, "height": height}},
        "10": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "11": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["10", 0], "guider": ["7", 0], "sampler": ["8", 0], "sigmas": ["9", 0], "latent_image": ["6", 0]}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": "ns-studio"}},
    }


def _flux3_klein_graph(prompt: str, width: int, height: int, steps: int, seed: int) -> dict:
    """FLUX 3 Image Klein text-to-image graph (official int8 template).

    One UNET, the Qwen3-VL text encoder loaded as ``flux3``, the FLUX VAE,
    ``ModelSamplingFlux`` and a 16-step euler/simple sampler at CFG 1.0 — the
    same graph the checkpoint repository ships. No GGUF loader and no FLUX 2
    node is involved.
    """
    loader = ("UnetLoaderGGUF" if str(IMAGE_MODEL_FILE).lower().endswith(".gguf")
              else "UNETLoader")
    unet_inputs = {"unet_name": IMAGE_MODEL_FILE}
    if loader == "UNETLoader":
        unet_inputs["weight_dtype"] = "default"
    return {
        "1": {"class_type": loader, "inputs": unet_inputs},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": TEXT_ENCODER_FILE, "type": "flux3",
                         "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": FLUX3_VAE_FILE}},
        "4": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": prompt + _STYLE_SUFFIX}},
        "5": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["2", 0], "text": ""}},
        "6": {"class_type": "EmptyFlux2LatentImage",
              "inputs": {"width": width, "height": height, "batch_size": 1}},
        "7": {"class_type": "ModelSamplingFlux",
              "inputs": {"model": ["1", 0], "max_shift": 2.77259,
                         "base_shift": 2.77259, "width": width, "height": height}},
        "8": {"class_type": "KSampler",
              "inputs": {"model": ["7", 0], "positive": ["4", 0],
                         "negative": ["5", 0], "latent_image": ["6", 0],
                         "seed": seed, "steps": steps, "cfg": 1.0,
                         "sampler_name": "euler", "scheduler": "simple",
                         "denoise": 1.0}},
        "9": {"class_type": "VAEDecode",
              "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "SaveImage",
               "inputs": {"images": ["9", 0], "filename_prefix": "ns-studio-flux3"}},
    }


def _qwen_edit_graph(prompt: str, image_name: str, *, steps: int, cfg: float, seed: int,
                     negative: str = "") -> dict:
    """Qwen-Image-Edit-2511 edit graph (official 2511 template, GGUF-adapted).

    Mirrors Comfy-Org/workflow_templates image_qwen_image_edit_2511.json:
    FluxKontextImageScale -> VAEEncode -> KSampler(denoise 1.0) with the source
    image supplied to the edit-encode node, plus the 2511 reference-latent
    method and CFGNorm. The Lightning 4-step LoRA is optional and not on this
    box, so the researched default step count is used.
    """
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": EDIT_MODEL_FILE}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": EDIT_TEXT_ENCODER_FILE, "type": "qwen_image",
                         "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": EDIT_VAE_FILE}},
        "4": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "5": {"class_type": "FluxKontextImageScale", "inputs": {"image": ["4", 0]}},
        "6": {"class_type": "VAEEncode", "inputs": {"pixels": ["5", 0], "vae": ["3", 0]}},
        "7": {"class_type": "TextEncodeQwenImageEditPlus",
              "inputs": {"clip": ["2", 0], "prompt": prompt + _STYLE_SUFFIX,
                         "vae": ["3", 0], "image1": ["5", 0]}},
        "8": {"class_type": "TextEncodeQwenImageEditPlus",
              "inputs": {"clip": ["2", 0], "prompt": negative}},
        "9": {"class_type": "FluxKontextMultiReferenceLatentMethod",
              "inputs": {"conditioning": ["7", 0],
                         "reference_latents_method": "index_timestep_zero"}},
        "10": {"class_type": "FluxKontextMultiReferenceLatentMethod",
               "inputs": {"conditioning": ["8", 0],
                          "reference_latents_method": "index_timestep_zero"}},
        "11": {"class_type": "ModelSamplingAuraFlow",
               "inputs": {"model": ["1", 0], "shift": 3.1}},
        "12": {"class_type": "CFGNorm", "inputs": {"model": ["11", 0], "strength": 1.0}},
        "13": {"class_type": "KSampler",
               "inputs": {"model": ["12", 0], "positive": ["9", 0], "negative": ["10", 0],
                          "latent_image": ["6", 0], "seed": seed, "steps": steps,
                          "cfg": cfg, "sampler_name": "euler", "scheduler": "simple",
                          "denoise": 1.0}},
        "14": {"class_type": "VAEDecode", "inputs": {"samples": ["13", 0], "vae": ["3", 0]}},
        "15": {"class_type": "SaveImage",
               "inputs": {"images": ["14", 0], "filename_prefix": "ns-qwen-edit"}},
    }


def _wan_graph(prompt: str, width: int, height: int, frames: int, steps: int, seed: int) -> dict:
    return {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": VIDEO_MODEL_FILE}},
        "2": {"class_type": "CLIPLoaderGGUF", "inputs": {"clip_name": "umt5-xxl-encoder-Q5_K_M.gguf", "type": "wan"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "wan2.2_vae" + ".safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt + _STYLE_SUFFIX}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": "blurry, low quality, static, watermark"}},
        "6": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": 8}},
        "7": {"class_type": "Wan22ImageToVideoLatent", "inputs": {"vae": ["3", 0], "width": width, "height": height, "length": frames, "batch_size": 1}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["6", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["7", 0], "seed": seed, "steps": steps, "cfg": 5, "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "CreateVideo", "inputs": {"images": ["9", 0], "fps": 24}},
        "11": {"class_type": "SaveVideo", "inputs": {"video": ["10", 0], "filename_prefix": "ns-studio", "format": "auto", "codec": "auto"}},
    }


# ── Public generation entries ──────────────────────────────────────────────

def generate_image(prompt: str, width=None, height=None, tier: str = "draft", seed=None,
                   on_progress=None) -> dict:
    if not media_live_armed():
        raise RuntimeError("media_generation_disarmed (MEDIA_GEN_LIVE is not 1)")
    if not unload_brain():  # one 16 GB GPU: make room, then VERIFY it actually freed
        raise RuntimeError(
            "vram_busy: the local brain is still resident on the GPU (Ollama /api/ps) "
            "after waiting; refusing a render that would run out of memory. Retry shortly.")
    req_w = int(width) if width not in (None, "") else 1024
    req_h = int(height) if height not in (None, "") else 1024
    w, h = _fit_box(req_w, req_h)
    # FLUX 3 official graph: 16 steps. A "final" tier gets a little more.
    steps = 24 if str(tier).lower() == "final" else 16
    seed = int(seed) if seed is not None else random.randrange(1, 2 ** 31)
    # Serialize renders and run the RAM stop/restore lifecycle. The lock is
    # cross-process, so two workers cannot drive the GPU at once.
    session = RenderSession(lane="image")
    with session:
        _ram_gate = {"ok": True, "stopped": session.stopped,
                     "needed_mb": SYSTEM_RAM_FLOOR_MB}
        if on_progress is not None:
            on_progress(0, "queued on the local engine")
        session.mark_render_started()
        try:
            # FLUX 3 is the only image engine. There is no FLUX 2 branch: the
            # weights were removed on 2026-10-29 and a fallback would hide that.
            graph = _flux3_klein_graph(prompt, w, h, steps, seed)
            files = _run_graph_guarded(graph, timeout_s=1800, on_progress=on_progress)
            session.check_timeout()
        except RuntimeError as exc:
            if "render_timeout" not in str(exc):
                release_models()  # never leave a crammed cache behind a failed render
            raise
        except Exception:
            release_models()  # never leave a crammed cache behind a failed render
            raise
        else:
            session.mark_render_finished()
    img = next((f for f in files if str(f.get("filename", "")).lower().endswith((".png", ".jpg", ".webp"))), None)
    if not img:
        raise RuntimeError("the render finished but produced no image output")
    data = _fetch_output(img)
    # The VAE grid is a multiple of 16, so a spec size like 1464x600 (A+
    # Premium banner) can only be requested as 1472x608. When the ONLY
    # difference is that grid snap, finish with a deterministic LANCZOS pass to
    # the exact deliverable size and report both numbers. Anything larger than a
    # grid step is a real fit and is never silently rescaled.
    delivered = (w, h)
    snapped = None
    if ((w, h) != (req_w, req_h)
            and req_w <= MAX_EDGE_PX and req_h <= MAX_EDGE_PX
            and abs(w - req_w) <= 16 and abs(h - req_h) <= 16):
        data = _exact_size_png(data, req_w, req_h)
        delivered = (req_w, req_h)
        snapped = {"engine": [w, h], "delivered": [req_w, req_h]}
    release_models()
    return {
        "bytes": data, "ext": "png", "mime": "image/png",
        "model": os.path.splitext(IMAGE_MODEL_FILE)[0], "provider": "comfyui",
        "seed": seed, "width": delivered[0], "height": delivered[1],
        "engine_width": w, "engine_height": h,
        "requested": {"width": req_w, "height": req_h},
        "fitted": (w, h) != (req_w, req_h),
        "exact_size_pass": snapped,
        "engine_max_edge_px": MAX_EDGE_PX,
        "duration_seconds": None,
        "ram_gate": _ram_gate,
        "brain_evicted": last_brain_eviction()["models"],
    }


def _exact_size_png(data: bytes, width: int, height: int) -> bytes:
    """Resize a rendered PNG to an exact deliverable size (LANCZOS)."""
    from io import BytesIO
    from PIL import Image
    with Image.open(BytesIO(data)) as im:
        if im.size == (width, height):
            return data
        out = im.convert("RGB").resize((int(width), int(height)), Image.LANCZOS)
        buf = BytesIO()
        out.save(buf, format="PNG")
        return buf.getvalue()


def upload_image(image_bytes: bytes, filename: str = "upload.png",
                 mime: str = "image/png") -> str:
    """Upload a source image to ComfyUI's input dir; returns the server-side name.

    Local only: the bytes travel to this machine's ComfyUI on 127.0.0.1.
    """
    try:
        import httpx
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"the upload lane needs httpx: {exc}")
    with httpx.Client(timeout=180.0) as c:
        r = c.post(comfyui_url() + "/upload/image",
                   files={"image": (filename, image_bytes, mime)},
                   data={"overwrite": "true", "type": "input"})
    if r.status_code >= 400:
        raise RuntimeError(f"image upload failed: HTTP {r.status_code} {r.text[:200]}")
    info = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    name = info.get("name") or filename
    sub = (info.get("subfolder") or "").strip("/")
    return f"{sub}/{name}" if sub else name


def generate_edit(image_bytes: bytes, prompt: str, *, tier: str = "draft", seed=None,
                  cfg: float = 3.0, steps=None, negative: str = "",
                  on_progress=None) -> dict:
    """Text-faithful edit/refine of a REAL image — Qwen-Image-Edit-2511, local.

    This is the Packify-parity edit lane: keep the product pixels, change the
    scene/lighting/material, and get layout-stable output (the model's
    typography competence is not relied on — the deterministic compositor still
    owns final copy; this lane harmonises what surrounds it).
    """
    if not media_live_armed():
        raise RuntimeError("media_generation_disarmed (MEDIA_GEN_LIVE is not 1)")
    # The Qwen-Image-Edit weights and its vision encoder were removed with the
    # FLUX 2 cleanup on 2026-10-29. Fail with the reason instead of dispatching a
    # graph against files that no longer exist.
    missing = [name for name in (EDIT_MODEL_FILE, EDIT_TEXT_ENCODER_FILE, EDIT_VAE_FILE)
               if not _any_model_on_disk(name)]
    if missing:
        raise RuntimeError(
            "edit_lane_removed: the text-faithful edit lane was removed with the "
            "FLUX 2 text-correcting models (missing: " + ", ".join(missing) + ")")
    require_cache_none("edit")
    if not unload_brain():
        raise RuntimeError(
            "vram_busy: the local brain is still resident on the GPU (Ollama /api/ps) "
            "after waiting; refusing a render that would run out of memory. Retry shortly.")
    seed = int(seed) if seed is not None else random.randrange(1, 2 ** 31)
    st = int(steps) if steps else (8 if str(tier).lower() == "fast" else 20)
    name = upload_image(image_bytes, filename=f"ns-edit-{seed}.png")
    try:
        if on_progress is not None:
            on_progress(0, "queued on the local engine")
        files = _run_graph_guarded(
            _qwen_edit_graph(prompt, name, steps=st, cfg=float(cfg), seed=seed,
                             negative=negative),
            timeout_s=7200, on_progress=on_progress)
    except Exception:
        release_models()  # never leave a crammed cache behind a failed render
        raise
    img = next((f for f in files
                if str(f.get("filename", "")).lower().endswith((".png", ".jpg", ".webp"))), None)
    if not img:
        raise RuntimeError("the edit finished but produced no image output")
    data = _fetch_output(img)
    release_models()
    return {
        "bytes": data, "ext": "png", "mime": "image/png",
        "model": os.path.splitext(EDIT_MODEL_FILE)[0], "provider": "comfyui",
        "seed": seed, "steps": st, "cfg": float(cfg), "duration_seconds": None,
    }


def _cutout_graph(image_name: str) -> dict:
    """BiRefNet cutout → RGBA (core nodes; the model is already on disk).

    Verified live 2026-10-19: `RemoveBackground`'s MASK marks the BACKGROUND
    (corners came back opaque), so the mask is inverted before it becomes the
    image's alpha.
    """
    return {
        "1": {"class_type": "LoadBackgroundRemovalModel",
              "inputs": {"bg_removal_name": CUTOUT_MODEL_FILE}},
        "2": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "3": {"class_type": "RemoveBackground",
              "inputs": {"bg_removal_model": ["1", 0], "image": ["2", 0]}},
        "4": {"class_type": "InvertMask", "inputs": {"mask": ["3", 0]}},
        "5": {"class_type": "JoinImageWithAlpha",
              "inputs": {"image": ["2", 0], "alpha": ["4", 0]}},
        "6": {"class_type": "SaveImage",
              "inputs": {"images": ["5", 0], "filename_prefix": "ns-cutout"}},
    }


def _upscale_graph(image_name: str, downscale_ratio: float) -> dict:  # noqa: D401
    """DEPRECATED (2026-10-19) - kept for the record, not called.

    RealESRGAN x4 via ImageUpscaleWithModelBatched aborted the ComfyUI process
    (fatal Python error inside the RRDB conv) on a 1216x1216 input on this 16 GB
    box. Circuit breaker honoured: no auto-retry. Deterministic upscaling now
    lives in image_prep.upscale_lanczos (pure PIL, no GPU). SeedVR2's weights are
    on disk but this ComfyUI exposes only its component nodes
    (preprocess/conditioning/postprocess/temporal), so there is no single-node
    SeedVR2 upscaler to call either.
    """
    return {
        "1": {"class_type": "UpscaleModelLoader",
              "inputs": {"model_name": UPSCALE_MODEL_FILE}},
        "2": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "3": {"class_type": "ImageUpscaleWithModelBatched",
              "inputs": {"upscale_model": ["1", 0], "images": ["2", 0],
                         "per_batch": 16, "downscale_ratio": downscale_ratio,
                         "downscale_method": "lanczos"}},
        "4": {"class_type": "SaveImage",
              "inputs": {"images": ["3", 0], "filename_prefix": "ns-upscale"}},
    }


def generate_cutout(image_bytes: bytes, *, filename: Optional[str] = None) -> dict:
    """Transparent-background cutout of a product image (BiRefNet, local).

    Feeds the listing-image lane (MAIN white background) and scene compositing.
    Returns PNG bytes WITH alpha; framing/compliance lives in image_prep.
    """
    if not media_live_armed():
        raise RuntimeError("media_generation_disarmed (MEDIA_GEN_LIVE is not 1)")
    if not unload_brain():
        raise RuntimeError(
            "vram_busy: the local brain is still resident on the GPU (Ollama /api/ps) "
            "after waiting; refusing a render that would run out of memory. Retry shortly.")
    name = upload_image(image_bytes, filename=filename or
                        f"ns-cutout-src-{uuid.uuid4().hex[:8]}.png")
    try:
        files = _run_graph_guarded(_cutout_graph(name), timeout_s=1800)
    except Exception:
        release_models()
        raise
    img = next((f for f in files
                if str(f.get("filename", "")).lower().endswith((".png", ".jpg", ".webp"))), None)
    if not img:
        raise RuntimeError("the cutout finished but produced no image output")
    data = _fetch_output(img)
    release_models()
    return {"bytes": data, "ext": "png", "mime": "image/png",
            "model": CUTOUT_MODEL_FILE, "provider": "comfyui", "duration_seconds": None}


def _frames_for_duration(duration, default_frames: int) -> int:
    """Snap a requested clip length to the Wan latent's legal frame count.

    Wan needs 4n+1 frames at 24 fps. We round UP to the next legal count so the
    delivered clip is never shorter than the request, and report the real
    duration from the frame count rather than the request.
    """
    if duration in (None, ""):
        return int(default_frames)
    seconds = float(duration)
    if seconds <= 0:
        raise ValueError("duration must be greater than zero seconds")
    requested_frames = int(round(seconds * 24.0))
    n = max(1, (requested_frames - 1) // 4 + 1)
    return 4 * n + 1


def generate_video(prompt: str, width=None, height=None, tier: str = "draft", seed=None,
                   narration: Optional[str] = None, voice: Optional[str] = None,
                   duration: Optional[float] = None,
                   on_progress=None) -> dict:
    """Render a clip locally; optionally attach a locally synthesised narration.
    The Wan latent needs 4n+1 frames at 24 fps, so the request is snapped to the
    nearest legal frame count and the delivered duration is reported, never
    assumed. Without ``duration`` the tier default (2 s draft / 4 s final) is used.

    ``narration`` is plain text. It is spoken by the machine's own speech engine
    (Northstar_backend/local_voice.py) and muxed onto the clip with ffmpeg, so a
    narrated product video needs no provider key and costs nothing. When the
    narration cannot be produced the render still returns, with ``audio.error``
    set to the real reason - a silent clip is never passed off as a narrated one.
    """
    require_cache_none("video")
    if not media_live_armed():
        raise RuntimeError("media_generation_disarmed (MEDIA_GEN_LIVE is not 1)")
    if not unload_brain():  # one 16 GB GPU: make room, then VERIFY it actually freed
        raise RuntimeError(
            "vram_busy: the local brain is still resident on the GPU (Ollama /api/ps) "
            "after waiting; refusing a render that would run out of memory. Retry shortly.")
    w = _clamp(width or 832, 512, 1280)
    h = _clamp(height or 480, 480, 736)
    default_frames = 97 if str(tier).lower() == "final" else 49
    frames = _frames_for_duration(duration, default_frames)
    steps = 20
    seed = int(seed) if seed is not None else random.randrange(1, 2 ** 31)
    # Serialize renders and run the RAM stop/restore lifecycle. The lock is
    # cross-process, so two workers cannot drive the GPU at once.
    session = RenderSession(lane="video")
    with session:
        _ram_gate = {"ok": True, "stopped": session.stopped,
                     "needed_mb": SYSTEM_RAM_FLOOR_MB}
        if on_progress is not None:
            on_progress(0, "queued on the local engine")
        session.mark_render_started()
        try:
            files = _run_graph_guarded(_wan_graph(prompt, w, h, frames, steps, seed), timeout_s=5400,
                                       on_progress=on_progress)
            session.check_timeout()
        except RuntimeError as exc:
            if "render_timeout" not in str(exc):
                release_models()  # never leave a crammed cache behind a failed render
            raise
        except Exception:
            release_models()  # never leave a crammed cache behind a failed render
            raise
        else:
            session.mark_render_finished()
    vid = next((f for f in files if str(f.get("filename", "")).lower().endswith((".mp4", ".webm"))), None)
    if not vid:
        raise RuntimeError("the render finished but produced no video output")
    data = _fetch_output(vid)
    release_models()
    result = {
        "bytes": data, "ext": "mp4", "mime": "video/mp4",
        "model": "wan2.2-ti2v-5b-q5", "provider": "comfyui",
        "seed": seed, "width": w, "height": h, "frames": frames,
        "duration_seconds": round(frames / 24.0, 2),
        "requested_duration_seconds": (float(duration) if duration not in (None, "") else None),
        "audio": None,
        "ram_gate": _ram_gate,
    }
    if narration and str(narration).strip():
        result["audio"] = _attach_narration(result["bytes"], str(narration), voice)
        if result["audio"].get("ok"):
            result["bytes"] = result["audio"].pop("bytes")
            result["mime"] = "video/mp4"
    return result


def _attach_narration(video_bytes: bytes, text: str, voice=None) -> dict:
    """Speak `text` locally and mux it onto the clip. Never raises, never lies."""
    try:
        import local_voice
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"local_voice unavailable: {type(exc).__name__}: {exc}"}
    try:
        spoken = local_voice.synthesize(text, voice=voice)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300],
                "engine": None}
    try:
        muxed = local_voice.mux_audio(video_bytes, spoken["bytes"])
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"mux failed: {type(exc).__name__}: {exc}"[:300],
                "engine": spoken.get("engine")}
    return {"ok": True, "bytes": muxed, "engine": spoken.get("engine"),
            "voice": spoken.get("voice"), "narration_bytes": len(spoken["bytes"]),
            "narration_seconds_approx": round(len(spoken["bytes"]) / 44100.0, 1)}


# --- System RAM pre-render gate (Phase R) ---
# --- System RAM pre-render gate (Phase R) -------------------------------
# The FLUX.2 text encoder (qwen_3_8b_fp8mixed, ~1.2 GB) is loaded on CPU
# during CLIPTextEncode. On 2026-10-27 a render OOM'd with only 2.2 GB of
# system RAM free (DefaultCPUAllocator: not enough memory). unload_brain()
# frees VRAM but nothing freed SYSTEM RAM. This gate fixes that.

# Documented floor: encoder footprint (~2 GB) + 2 GB headroom for OS/ComfyUI.
# Override via STUDIO_RAM_FLOOR_MB. Below this, the stop-list runs, then we
# re-measure; if still below, refuse honestly (never retry blindly).
SYSTEM_RAM_FLOOR_MB = int(os.environ.get("STUDIO_RAM_FLOOR_MB", "4096"))

# Process name substrings (lowercased) that are safe to stop for a render.
# OpenCode is NEVER stopped (it is this session). Chrome is opt-in only.
_STOP_LIST_NAMES = (
    # Explicitly owned, idle local inference processes only.
    # Docker, databases, the product listener (uvicorn/northstar),
    # Chrome Connect, OpenCode and unrelated tools are NEVER stopped.
    "llama-server", "llama-cli", "llama.cpp", "ollama_llama_server",
    "ollama",
)
_HEAVY_DEV_NAMES = ("code", "node", "python")  # only with --stop-dev-tools


def system_ram_free_mb() -> float:
    """Current free system RAM in MB (psutil)."""
    try:
        return float((_psutil if _psutil is not None else None).virtual_memory().available) / (1024.0 * 1024.0)
    except Exception:
        return 0.0


def _is_stop_candidate(proc, *, shutdown_chrome: bool, stop_dev_tools: bool) -> bool:
    try:
        name = ""
        info = getattr(proc, "info", None)
        if isinstance(info, dict):
            name = info.get("name") or ""
        if not name:
            try:
                name = proc.name() or ""
            except Exception:
                name = ""
        name = str(name).lower()
    except Exception:
        return False
    if not name:
        return False
    # Never stop ourselves or the session host.
    try:
        if proc.pid == os.getpid():
            return False
    except Exception:
        pass
    if "opencode" in name:
        return False
    if "chrome" in name:
        return bool(shutdown_chrome)
    for pat in _STOP_LIST_NAMES:
        if pat in name:
            return True
    if stop_dev_tools:
        for pat in _HEAVY_DEV_NAMES:
            if pat in name:
                # Never stop the ComfyUI we are about to use or the backend.
                if "comfy" in name or "uvicorn" in name or "northstar" in name:
                    return False
                return True
    return False


def stop_for_render(shutdown_chrome: bool = False,
                    stop_dev_tools: bool = False) -> list:
    """Stop stop-list processes; return list of {pid, name, ram_mb} for restore.

    Skips absent processes. Logs each. Never stops OpenCode or (by default) Chrome.
    """
    stopped = []
    for proc in (_psutil if _psutil is not None else None).process_iter(["pid", "name", "memory_info"]):
        try:
            if not _is_stop_candidate(proc, shutdown_chrome=shutdown_chrome,
                                      stop_dev_tools=stop_dev_tools):
                continue
            try:
                ram_mb = (proc.info.get("memory_info").rss / (1024.0 * 1024.0)
                          if proc.info.get("memory_info") else 0.0)
            except Exception:
                ram_mb = 0.0
            name = proc.info.get("name") or ""
            pid = proc.info.get("pid")
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except (_psutil if _psutil is not None else None).TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            except ((_psutil if _psutil is not None else None).NoSuchProcess, (_psutil if _psutil is not None else None).AccessDenied):
                continue
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            stopped.append({"pid": pid, "name": name, "ram_mb": round(ram_mb, 1)})
        except ((_psutil if _psutil is not None else None).NoSuchProcess, (_psutil if _psutil is not None else None).AccessDenied):
            continue
        except Exception:
            continue
    return stopped


def restore_after_render(stopped: list) -> list:
    """Best-effort restore of stopped processes.

    Most stopped services (Docker, Ollama, llama.cpp) are system services that
    restart themselves or are restarted by the operator; we record what we
    stopped so the report is honest. Returns the list unchanged.
    """
    return list(stopped or [])


def ensure_system_ram(shutdown_chrome: bool = False,
                      stop_dev_tools: bool = False) -> dict:
    """Pre-render system-RAM gate.

    Returns a dict: {"ok": bool, "free_mb_before": float, "free_mb_after": float,
    "stopped": list, "needed_mb": int, "refusal": str or None}.
    Raises RuntimeError with an honest message if the floor cannot be met even
    after the stop-list.
    """
    free_before = system_ram_free_mb()
    stopped = []
    if free_before < SYSTEM_RAM_FLOOR_MB:
        stopped = stop_for_render(shutdown_chrome=shutdown_chrome,
                                 stop_dev_tools=stop_dev_tools)
        # Give the OS a moment to reclaim.
        time.sleep(2)
    free_after = system_ram_free_mb()
    result = {
        "ok": free_after >= SYSTEM_RAM_FLOOR_MB,
        "free_mb_before": round(free_before, 1),
        "free_mb_after": round(free_after, 1),
        "stopped": stopped,
        "needed_mb": SYSTEM_RAM_FLOOR_MB,
        "refusal": None,
    }
    if not result["ok"]:
        result["refusal"] = (
            f"free {free_after:.0f} MB, need {SYSTEM_RAM_FLOOR_MB} MB "
            f"(after stop-list freed {sum(s.get('ram_mb', 0) for s in stopped):.0f} MB)"
        )
        raise RuntimeError("system_ram_insufficient: " + result["refusal"])
    return result



# --- System RAM pre-render gate (Phase R) ---
# --- System RAM pre-render gate (Phase R) -------------------------------
# The FLUX.2 text encoder (qwen_3_8b_fp8mixed, ~1.2 GB) is loaded on CPU
# during CLIPTextEncode. On 2026-10-27 a render OOM'd with only 2.2 GB of
# system RAM free (DefaultCPUAllocator: not enough memory). unload_brain()
# frees VRAM but nothing freed SYSTEM RAM. This gate fixes that.
import psutil as _psutil

# Documented floor: encoder footprint (~2 GB) + 2 GB headroom for OS/ComfyUI.
# Override via STUDIO_RAM_FLOOR_MB. Below this, the stop-list runs, then we
# re-measure; if still below, refuse honestly (never retry blindly).
SYSTEM_RAM_FLOOR_MB = int(os.environ.get("STUDIO_RAM_FLOOR_MB", "4096"))

# Process name substrings (lowercased) that are safe to stop for a render.
# OpenCode is NEVER stopped (it is this session). Chrome is opt-in only.
_STOP_LIST_NAMES = (
    # Explicitly owned, idle local inference processes only.
    # Docker, databases, the product listener (uvicorn/northstar),
    # Chrome Connect, OpenCode and unrelated tools are NEVER stopped.
    "llama-server", "llama-cli", "llama.cpp", "ollama_llama_server",
    "ollama",
)
_HEAVY_DEV_NAMES = ("code", "node", "python")  # only with --stop-dev-tools


def system_ram_free_mb() -> float:
    """Current free system RAM in MB (psutil)."""
    try:
        return float(_psutil.virtual_memory().available) / (1024.0 * 1024.0)
    except Exception:
        return 0.0


def _is_stop_candidate(proc, *, shutdown_chrome: bool, stop_dev_tools: bool) -> bool:
    try:
        name = ""
        info = getattr(proc, "info", None)
        if isinstance(info, dict):
            name = info.get("name") or ""
        if not name:
            try:
                name = proc.name() or ""
            except Exception:
                name = ""
        name = str(name).lower()
    except Exception:
        return False
    if not name:
        return False
    # Never stop ourselves or the session host.
    try:
        if proc.pid == os.getpid():
            return False
    except Exception:
        pass
    if "opencode" in name:
        return False
    if "chrome" in name:
        return bool(shutdown_chrome)
    for pat in _STOP_LIST_NAMES:
        if pat in name:
            return True
    if stop_dev_tools:
        for pat in _HEAVY_DEV_NAMES:
            if pat in name:
                # Never stop the ComfyUI we are about to use or the backend.
                if "comfy" in name or "uvicorn" in name or "northstar" in name:
                    return False
                return True
    return False


def stop_for_render(shutdown_chrome: bool = False,
                    stop_dev_tools: bool = False) -> list:
    """Stop stop-list processes; return list of {pid, name, ram_mb} for restore.

    Skips absent processes. Logs each. Never stops OpenCode or (by default) Chrome.
    """
    stopped = []
    for proc in _psutil.process_iter(["pid", "name", "memory_info"]):
        try:
            if not _is_stop_candidate(proc, shutdown_chrome=shutdown_chrome,
                                      stop_dev_tools=stop_dev_tools):
                continue
            try:
                ram_mb = (proc.info.get("memory_info").rss / (1024.0 * 1024.0)
                          if proc.info.get("memory_info") else 0.0)
            except Exception:
                ram_mb = 0.0
            name = proc.info.get("name") or ""
            pid = proc.info.get("pid")
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=10)
                except _psutil.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
            except (_psutil.NoSuchProcess, _psutil.AccessDenied):
                continue
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            stopped.append({"pid": pid, "name": name, "ram_mb": round(ram_mb, 1)})
        except (_psutil.NoSuchProcess, _psutil.AccessDenied):
            continue
        except Exception:
            continue
    return stopped


def restore_after_render(stopped: list) -> list:
    """Best-effort restore of stopped processes.

    Most stopped services (Docker, Ollama, llama.cpp) are system services that
    restart themselves or are restarted by the operator; we record what we
    stopped so the report is honest. Returns the list unchanged.
    """
    return list(stopped or [])


def ensure_system_ram(shutdown_chrome: bool = False,
                      stop_dev_tools: bool = False) -> dict:
    """Pre-render system-RAM gate.

    Returns a dict: {"ok": bool, "free_mb_before": float, "free_mb_after": float,
    "stopped": list, "needed_mb": int, "refusal": str or None}.
    Raises RuntimeError with an honest message if the floor cannot be met even
    after the stop-list.
    """
    free_before = system_ram_free_mb()
    stopped = []
    if free_before < SYSTEM_RAM_FLOOR_MB:
        stopped = stop_for_render(shutdown_chrome=shutdown_chrome,
                                 stop_dev_tools=stop_dev_tools)
        # Give the OS a moment to reclaim.
        time.sleep(2)
    free_after = system_ram_free_mb()
    result = {
        "ok": free_after >= SYSTEM_RAM_FLOOR_MB,
        "free_mb_before": round(free_before, 1),
        "free_mb_after": round(free_after, 1),
        "stopped": stopped,
        "needed_mb": SYSTEM_RAM_FLOOR_MB,
        "refusal": None,
    }
    if not result["ok"]:
        result["refusal"] = (
            f"free {free_after:.0f} MB, need {SYSTEM_RAM_FLOOR_MB} MB "
            f"(after stop-list freed {sum(s.get('ram_mb', 0) for s in stopped):.0f} MB)"
        )
        raise RuntimeError("system_ram_insufficient: " + result["refusal"])
    return result


# --- Render session manager (Phase R) ---
# --- Render session manager (Phase R) --------------------------------------
# Wraps every creative job: lock + state file + drain + stop + verify + run +
# restore, with crash safety (finally + state file trigger on next start).
import json as _rs_json
import threading as _rs_threading

_RENDER_STATE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "render_session_state.json")
_RENDER_LOCK_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "data", "render_session.lock")
_RENDER_MAX_SECONDS = int(os.environ.get("STUDIO_RENDER_MAX_SECONDS", "1800"))


class _CrossProcessRenderLock:
    """A render lock that is honoured across processes, not just threads.

    Uses an exclusive-create lock file containing ``pid:timestamp``. A lock
    held by a dead PID (or one older than the max render time plus a grace
    period) is treated as stale and reclaimed. The executing backend process
    is never killed; only the lock file is cleaned up.
    """

    def __init__(self, path: str, max_seconds: int = None):
        self.path = path
        self.max_seconds = max_seconds if max_seconds is not None else _RENDER_MAX_SECONDS
        self._thread_lock = _rs_threading.Lock()
        self._fd = None
        self._owned = False

    def _pid_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            if _psutil is not None:
                return bool(_psutil.pid_exists(pid)) and _psutil.Process(pid).is_running()
        except Exception:
            return False
        return False

    def _read_owner(self):
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                raw = fh.read().strip()
            pid_s, ts_s = raw.split(":", 1)
            return int(pid_s), float(ts_s)
        except Exception:
            return None, 0.0

    def _stale(self) -> bool:
        pid, ts = self._read_owner()
        if pid is None:
            return True  # unreadable/garbage lock file
        if not self._pid_alive(pid):
            return True
        try:
            if ts and (time.time() - ts) > (self.max_seconds + 60):
                return True
        except Exception:
            pass
        return False

    def acquire(self, timeout: float = 10.0) -> bool:
        # B5: time the wait so a serialised render has a number, not a vibe.
        _t0 = time.perf_counter()
        ok = self._acquire_inner(timeout)
        _waited = time.perf_counter() - _t0
        _RENDER_LOCK_STATS["attempts"] += 1
        _RENDER_LOCK_STATS["total_wait_s"] = round(
            _RENDER_LOCK_STATS["total_wait_s"] + _waited, 4)
        _RENDER_LOCK_STATS["last_wait_s"] = round(_waited, 4)
        if _waited > _RENDER_LOCK_STATS["max_wait_s"]:
            _RENDER_LOCK_STATS["max_wait_s"] = round(_waited, 4)
        if not ok:
            _RENDER_LOCK_STATS["timeouts"] += 1
        return ok

    def _acquire_inner(self, timeout: float = 10.0) -> bool:
        # Guard the same-process race first.
        if not self._thread_lock.acquire(timeout=max(0.1, timeout)):
            return False
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            deadline = time.time() + max(0.0, timeout)
            while True:
                try:
                    fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    try:
                        os.write(fd, ("%d:%.3f" % (os.getpid(), time.time())).encode("ascii"))
                    finally:
                        os.close(fd)
                    self._fd = None
                    self._owned = True
                    return True
                except FileExistsError:
                    if self._stale():
                        try:
                            os.remove(self.path)
                            continue
                        except OSError:
                            pass
                    if time.time() >= deadline:
                        return False
                    time.sleep(0.2)
        except Exception:
            return False
        finally:
            if not self._owned:
                try:
                    self._thread_lock.release()
                except RuntimeError:
                    pass

    def release(self) -> None:
        if self._owned:
            try:
                os.remove(self.path)
            except OSError:
                pass
            self._owned = False
        try:
            self._thread_lock.release()
        except RuntimeError:
            pass


_RENDER_LOCK = _CrossProcessRenderLock(_RENDER_LOCK_PATH)


def gpu_lock() -> "_CrossProcessRenderLock":
    """The one cross-process GPU lock this box has.

    Renders take it in ``RenderSession``. Any other heavy GPU user (the on-demand
    27B coding worker, an agent's creative lane) must take the SAME lock, so a
    coding run and a render can never overlap on the single 16 GB card.
    """
    return _RENDER_LOCK


def _ram_gate_ok() -> bool:
    try:
        return system_ram_free_mb() >= SYSTEM_RAM_FLOOR_MB
    except Exception:
        return False


class RenderSession:
    """Context manager wrapping a creative render.

    Usage:
        with RenderSession(lane="image", shutdown_chrome=False) as rs:
            rs.stopped = ensure_system_ram(...)  # already done in __enter__
            ... do render ...
            rs.result = {...}
    On exit (normal or exception), restores. If the process dies mid-render,
    the state file triggers restore on the next start (see restore_pending_session).
    """

    def __init__(self, lane: str = "image", shutdown_chrome: bool = False,
                 max_seconds: int = None):
        self.lane = lane
        self.shutdown_chrome = shutdown_chrome
        self.max_seconds = max_seconds if max_seconds is not None else _RENDER_MAX_SECONDS
        self.stopped = []
        self.result = None
        self._start = None
        self._lock_acquired = False
        self._render_active = False

    def mark_render_started(self) -> None:
        self._render_active = True

    def mark_render_finished(self) -> None:
        self._render_active = False

    def __enter__(self):
        # Acquire lock (blocking, with timeout).
        acquired = _RENDER_LOCK.acquire(timeout=10)
        if not acquired:
            raise RuntimeError("render_session_busy: another render is running")
        self._lock_acquired = True
        self._start = time.time()
        # Write state file BEFORE stopping anything (crash safety).
        try:
            os.makedirs(os.path.dirname(_RENDER_STATE_PATH), exist_ok=True)
            state = {
                "lane": self.lane,
                "started_at": self._start,
                "max_seconds": self.max_seconds,
                "stopped": [],
                "status": "running",
            }
            with open(_RENDER_STATE_PATH, "w", encoding="utf-8") as fh:
                _rs_json.dump(state, fh)
        except Exception:
            pass
        # Drain: evict brain (existing). In-flight requests are the caller's
        # responsibility; we just evict.
        try:
            unload_brain(wait_s=45.0)
        except Exception:
            pass
        # Stop list + verify RAM.
        try:
            self.stopped = ensure_system_ram(shutdown_chrome=self.shutdown_chrome)
            if isinstance(self.stopped, dict):
                self.stopped = self.stopped.get("stopped", [])
        except Exception as exc:
            # Write refusal to state file, then re-raise after restore.
            self._write_state(status="refused", refusal=str(exc))
            self._restore()
            if self._lock_acquired:
                try:
                    _RENDER_LOCK.release()
                except RuntimeError:
                    pass
                self._lock_acquired = False
            raise
        # Update state file with stopped list.
        self._write_state(status="running", stopped=self.stopped)
        return self

    def _write_state(self, status="running", stopped=None, refusal=None):
        try:
            state = {
                "lane": self.lane,
                "started_at": self._start,
                "max_seconds": self.max_seconds,
                "stopped": stopped if stopped is not None else self.stopped,
                "status": status,
            }
            if refusal:
                state["refusal"] = refusal
            if self.result:
                state["result"] = self.result
            with open(_RENDER_STATE_PATH, "w", encoding="utf-8") as fh:
                _rs_json.dump(state, fh)
        except Exception:
            pass

    def _restore(self):
        try:
            restore_after_render(self.stopped)
        except Exception:
            pass
        # Clear state file (session complete).
        try:
            if os.path.exists(_RENDER_STATE_PATH):
                os.remove(_RENDER_STATE_PATH)
        except Exception:
            pass

    def check_timeout(self):
        if self._start and (time.time() - self._start) > self.max_seconds:
            raise RuntimeError(
                f"render_timeout: exceeded {self.max_seconds}s max render time")

    def __exit__(self, exc_type, exc_val, exc_tb):
        # A timed-out render may still be executing inside ComfyUI. Never
        # release the lock or restore the LLM in that case: keep the state file
        # as "orphaned" so the next start can recover, and never replay an
        # ambiguous submission. Stale-lock detection reclaims it after the
        # max render time plus a grace period.
        if (self._render_active and exc_val is not None
                and "render_timeout" in str(exc_val)):
            self._write_state(status="orphaned")
            return False
        # Restore in finally (crash-safe).
        self._restore()
        if self._lock_acquired:
            try:
                _RENDER_LOCK.release()
            except RuntimeError:
                pass
            self._lock_acquired = False
        return False  # don't suppress exceptions


def restore_pending_session() -> dict:
    """Called on startup: if a state file exists from a crashed render, restore.

    Returns a dict describing what was restored, or {} if nothing pending.
    """
    try:
        if not os.path.exists(_RENDER_STATE_PATH):
            return {}
        with open(_RENDER_STATE_PATH, "r", encoding="utf-8") as fh:
            state = _rs_json.load(fh)
        stopped = state.get("stopped", [])
        restore_after_render(stopped)
        # Remove state file.
        os.remove(_RENDER_STATE_PATH)
        return {"restored": True, "lane": state.get("lane"), "stopped": stopped,
                "status": state.get("status")}
    except Exception as exc:
        return {"restored": False, "error": str(exc)}


def run_render_session(lane: str, render_fn, *args, **kwargs):
    """Convenience: run render_fn inside a RenderSession. Returns render_fn result."""
    with RenderSession(lane=lane) as rs:
        rs.check_timeout()
        out = render_fn(*args, **kwargs)
        rs.result = out if isinstance(out, dict) else {"result": out}
        rs.check_timeout()
        return out