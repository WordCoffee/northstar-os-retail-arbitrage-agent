"""Local creative media suite — model-chaining architecture (offline, unarmed).

On a 16 GB GPU you don't run one giant model; you run a *pipeline* of small
specialists, one at a time, unloading between stages. This module is the
provider-neutral **registry + planner + status** for that suite. It never
downloads, installs, loads a model, generates, or contacts a provider.

Stage -> specialist models (commercial-safe preferred). Each entry records
license, whether commercial use is OK, rough VRAM, source, and an install probe.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable, Dict, List, Optional

from . import local_image_engine as lie

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
# commercial_ok: True = license permits commercial use (per published terms).
STAGES: List[Dict[str, object]] = [
    {
        "stage": "image", "label": "Still image / keyframe",
        "models": [
            {"key": "flux-dev-fp8", "label": "FLUX.1 [dev] fp8", "license": "FLUX.1-dev (non-commercial)",
             "commercial_ok": False, "vram_gb": 12, "source": "Kijai/flux-fp8",
             "note": "Installed. Test-only — non-commercial."},
            {"key": "flux2-klein-4b", "label": "FLUX.2 Klein 4B", "license": "Apache-2.0",
             "commercial_ok": True, "vram_gb": 13, "source": "black-forest-labs/FLUX.2-klein-4B",
             "note": "Commercial-safe upgrade path."},
        ],
    },
    {
        "stage": "voice", "label": "Voice / TTS (+ cloning)",
        "models": [
            {"key": "chatterbox", "label": "Chatterbox Turbo", "license": "MIT",
             "commercial_ok": True, "vram_gb": 6, "source": "ResembleAI/chatterbox",
             "note": "Zero-shot cloning (~5-10s clip); watermarked output."},
            {"key": "kokoro", "label": "Kokoro-82M", "license": "Apache-2.0",
             "commercial_ok": True, "vram_gb": 3, "source": "hexgrad/Kokoro-82M",
             "note": "Fast preset voices, no cloning."},
        ],
    },
    {
        "stage": "lipsync", "label": "Talking-head / lip-sync (UGC)",
        "models": [
            {"key": "latentsync-1.6", "label": "LatentSync 1.6", "license": "Apache-2.0",
             "commercial_ok": True, "vram_gb": 18, "source": "ByteDance/LatentSync-1.6",
             "note": "Runs on 16GB with UNet CPU-offload (official needs 18GB)."},
            {"key": "sadtalker", "label": "SadTalker", "license": "Apache-2.0",
             "commercial_ok": True, "vram_gb": 6, "source": "OpenTalker/SadTalker",
             "note": "Lighter image->talking-head; older quality."},
        ],
    },
    {
        "stage": "video", "label": "Video / short clip (t2v / i2v)",
        "models": [
            {"key": "wan22-ti2v-5b", "label": "Wan 2.2 TI2V-5B", "license": "Apache-2.0",
             "commercial_ok": True, "vram_gb": 8, "source": "Wan-AI/Wan2.2-TI2V-5B",
             "note": "720p ~5s on 16GB with ComfyUI offloading."},
            {"key": "ltx-2.3", "label": "LTX-Video 2.3 (nvfp4)", "license": "LTX Open Weights",
             "commercial_ok": True, "vram_gb": 16, "source": "Lightricks/LTX-Video",
             "note": "Native synchronized audio+video; nvfp4 to fit 16GB."},
        ],
    },
    {
        "stage": "music", "label": "Music / SFX",
        "models": [
            {"key": "ace-step", "label": "ACE-Step", "license": "Apache-2.0",
             "commercial_ok": True, "vram_gb": 8, "source": "ACE-Step/ACE-Step",
             "note": "Local music generation."},
            {"key": "stable-audio-open", "label": "Stable Audio Open", "license": "Stability Community",
             "commercial_ok": True, "vram_gb": 8, "source": "stabilityai/stable-audio-open-1.0",
             "note": "SFX / short loops."},
        ],
    },
    {
        "stage": "upscale", "label": "Upscale / finishing",
        "models": [
            {"key": "ffmpeg-scale", "label": "ffmpeg scale/lanczos", "license": "LGPL/GPL",
             "commercial_ok": True, "vram_gb": 0, "source": "system ffmpeg",
             "note": "Basic upscale; no model download."},
        ],
    },
    {
        "stage": "mux", "label": "Mux / captions / assembly",
        "models": [
            {"key": "ffmpeg", "label": "ffmpeg", "license": "LGPL/GPL",
             "commercial_ok": True, "vram_gb": 0, "source": "system ffmpeg",
             "note": "Mux video+audio, burn captions, concat."},
        ],
    },
]

GOALS: Dict[str, Dict[str, object]] = {
    "product_image": {"label": "Product still (commerce)",
                      "stages": ["image", "upscale"]},
    "ugc_talking_head": {"label": "UGC talking-head testimonial",
                         "stages": ["image", "voice", "lipsync", "mux"]},
    "cinematic_short": {"label": "Cinematic short (b-roll)",
                        "stages": ["image", "video", "music", "mux"]},
    "ad_short": {"label": "Ad short (voice + music)",
                 "stages": ["image", "video", "voice", "music", "mux"]},
}


# ---------------------------------------------------------------------------
# Install probes (heuristics; never installs)
# ---------------------------------------------------------------------------
def _has_dir(*paths: Path) -> bool:
    for p in paths:
        try:
            if p.is_dir():
                return True
        except OSError:
            continue
    return False


def _video_models_present(home: Optional[Path], token: str) -> bool:
    if not home:
        return False
    for d in ("models/diffusion_models", "models/unet"):
        p = home / d
        try:
            if p.is_dir() and any(x.suffix == ".safetensors" and token in x.name.lower()
                                  for x in p.iterdir()):
                return True
        except OSError:
            continue
    return False


def _model_installed(key: str) -> str:
    """installed | missing | unknown — filesystem/exe probe only; never installs."""
    home = lie.resolve_comfyui_home()
    custom = (home / "custom_nodes") if home else None
    try:
        if key == "flux-dev-fp8":
            return "installed" if lie.weights_status(home)["found"] else "missing"
        if key == "flux2-klein-4b":
            return "installed" if _video_models_present(home, "klein") else "missing"
        if key == "chatterbox":
            return "installed" if (custom and _has_dir(custom / "ComfyUI-Chatterbox", home / "models/audio/chatterbox")) else "missing"
        if key == "kokoro":
            return "installed" if (custom and _has_dir(custom / "ComfyUI-Kokoro", home / "models/audio/kokoro")) else "missing"
        if key == "latentsync-1.6":
            return "installed" if (custom and _has_dir(custom / "ComfyUI-LatentSyncWrapper", custom / "ComfyUI-LatentSync")) else "missing"
        if key == "sadtalker":
            return "installed" if (custom and _has_dir(custom / "ComfyUI-SadTalker", custom / "SadTalker")) else "missing"
        if key == "wan22-ti2v-5b":
            return "installed" if _video_models_present(home, "wan") else "missing"
        if key == "ltx-2.3":
            return "installed" if _video_models_present(home, "ltx") else "missing"
        if key == "ace-step":
            return "installed" if (custom and _has_dir(custom / "ComfyUI-ACE-Step", home / "models/ace_step")) else "missing"
        if key == "stable-audio-open":
            return "installed" if (custom and _has_dir(custom / "ComfyUI-StableAudioOpen")) else "missing"
        if key in ("ffmpeg", "ffmpeg-scale"):
            return "installed" if shutil.which("ffmpeg") else "missing"
    except Exception:  # noqa: BLE001
        return "unknown"
    return "unknown"


def pipeline_status() -> Dict[str, object]:
    stages = []
    for st in STAGES:
        models = [{**m, "install_state": _model_installed(str(m["key"]))} for m in st["models"]]
        stages.append({
            "stage": st["stage"], "label": st["label"],
            "install_state": "installed" if any(m["install_state"] == "installed" for m in models) else "missing",
            "models": models,
        })
    return {
        "lane": "local-creative-suite",
        "note": "Model-chaining suite. Localhost only; runs one model at a time. "
                "Readiness here does not install, download, or enable anything.",
        "stages": stages,
        "goals": GOALS,
    }


def plan_pipeline(goal: str, prefer_commercial: bool = True) -> Dict[str, object]:
    """A pipeline PLAN — never executes. Picks a model per stage and lists the
    owner-gated steps still required."""
    g = GOALS.get(goal)
    if not g:
        return {"goal": goal, "known": False, "reason": "unknown_goal", "available_goals": list(GOALS)}
    steps = []
    gated = []
    for stage in g["stages"]:
        st = next(s for s in STAGES if s["stage"] == stage)
        models = [{**m, "install_state": _model_installed(str(m["key"]))} for m in st["models"]]
        if prefer_commercial:
            models.sort(key=lambda m: (not m["commercial_ok"], m["install_state"] != "installed"))
        else:
            models.sort(key=lambda m: (m["install_state"] != "installed",))
        chosen = models[0]
        steps.append({"stage": stage, "label": st["label"], "model": chosen})
        if chosen["install_state"] != "installed":
            gated.append(f"install {chosen['label']} ({chosen['license']})")
    return {
        "goal": goal, "known": True, "label": g["label"],
        "steps": steps,
        "owner_gated_steps": gated,
        "note": "Plan only — no model is downloaded, loaded, or run.",
    }
