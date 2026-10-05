"""Local creative media suite — model-chaining architecture (offline, unarmed).

On a 16 GB GPU you don't run one giant model; you run a *pipeline* of small
specialists, one at a time, unloading between stages. This module is the
provider-neutral **registry + planner + status** for that suite. It never
downloads, installs, loads a model, generates, or contacts a provider.

Engine: **ComfyUI** (headless). The planner produces a *job plan*; the runners
submit **workflow templates** to ComfyUI's API via ``comfyui_client`` — the
planner does not invent graphs. Templates come from ComfyUI's template library or
a local ``creative_workflows/`` directory.

Hybrid rule: local for volume (UGC, product b-roll, social clips, variations);
cloud (Kling/Veo-class) for long, physics-heavy cinematic shots.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Dict, List, Optional

from . import local_image_engine as lie

ENGINE = "comfyui"
HYBRID_NOTE = ("Local for volume (UGC, product b-roll, social, variations); "
               "cloud (Kling/Veo-class) for long physics-heavy cinematic shots.")

# Draft -> final: iterate cheap on the fast model, re-render only approved seeds.
RENDER_MODES: Dict[str, Dict[str, object]] = {
    "draft": {"label": "Draft pass", "stage_model": "video_fast",
              "note": "Low resolution, few steps, LTX-2.3. Many variations; pick winners."},
    "final": {"label": "Final pass", "stage_model": "video_hero",
              "note": "Re-render only the approved seed/shot at full quality (Wan 14B hero)."},
}

# commercial_ok: True = license permits commercial use (per published terms).
STAGES: List[Dict[str, object]] = [
    {
        "stage": "image", "label": "Keyframes / product shots",
        "models": [
            {"key": "flux2", "label": "FLUX.2 (NVFP4/FP8)", "license": "Apache-2.0 (Klein) / BFL",
             "commercial_ok": True, "vram_gb": 13, "source": "black-forest-labs/FLUX.2",
             "note": "Test FLUX.2 vs Qwen-Image-Edit on real product photos for consistency."},
            {"key": "qwen-image-edit", "label": "Qwen-Image-Edit", "license": "Apache-2.0",
             "commercial_ok": True, "vram_gb": 12, "source": "Qwen/Qwen-Image-Edit",
             "note": "Reference-lock / composite real product packaging."},
            {"key": "flux-dev-fp8", "label": "FLUX.1 [dev] fp8", "license": "FLUX.1-dev (non-commercial)",
             "commercial_ok": False, "vram_gb": 12, "source": "Kijai/flux-fp8",
             "note": "Installed. Test-only — non-commercial."},
        ],
    },
    {
        "stage": "video_fast", "label": "Fast video + sound (b-roll, shorts, drafts)",
        "models": [
            {"key": "ltx-2.3", "label": "LTX-Video 2.3 (22B, NVFP4/FP8)", "license": "LTX Open Weights",
             "commercial_ok": True, "vram_gb": 16, "source": "Lightricks/LTX-Video",
             "note": "Native synchronized audio; ~16GB at FP8/720p. Draft engine."},
        ],
    },
    {
        "stage": "video_hero", "label": "Hero shots (best motion quality)",
        "models": [
            {"key": "wan22-14b-gguf", "label": "Wan 2.2 14B (GGUF Q5/Q6 or FP8)", "license": "Apache-2.0",
             "commercial_ok": True, "vram_gb": 16, "source": "Wan-AI/Wan2.2",
             "note": "GGUF Q5 ~11-16GB with block swapping. Needs high system RAM."},
        ],
    },
    {
        "stage": "lipsync", "label": "Talking-head UGC (image + audio -> video)",
        "models": [
            {"key": "wan22-s2v", "label": "Wan 2.2 S2V", "license": "Apache-2.0",
             "commercial_ok": True, "vram_gb": 16, "source": "Wan-AI/Wan2.2-S2V",
             "note": "One pass from image + audio; fewer stages to drift."},
            {"key": "infinitetalk", "label": "InfiniteTalk", "license": "Apache-2.0",
             "commercial_ok": True, "vram_gb": 16, "source": "MeiGen-AI/InfiniteTalk",
             "note": "Long-form talking avatar."},
            {"key": "latentsync-1.6", "label": "LatentSync 1.6 (fix-up pass)", "license": "Apache-2.0",
             "commercial_ok": True, "vram_gb": 18, "source": "ByteDance/LatentSync-1.6",
             "note": "Use only as a lip-sync fix-up, not the primary pass."},
        ],
    },
    {
        "stage": "voice", "label": "Voice / TTS (+ cloning)",
        "models": [
            {"key": "chatterbox", "label": "Chatterbox Turbo", "license": "MIT",
             "commercial_ok": True, "vram_gb": 6, "source": "ResembleAI/chatterbox",
             "note": "Run a shootout on your own scripts; don't trust vendor blind tests."},
        ],
    },
    {
        "stage": "music", "label": "Music / SFX",
        "models": [
            {"key": "ace-step", "label": "ACE-Step", "license": "Apache-2.0",
             "commercial_ok": True, "vram_gb": 8, "source": "ACE-Step/ACE-Step",
             "note": "Local music generation."},
        ],
    },
    {
        "stage": "upscale", "label": "Upscale",
        "models": [
            {"key": "seedvr2", "label": "SeedVR2 video upscaler", "license": "Apache-2.0",
             "commercial_ok": True, "vram_gb": 12, "source": "ByteDance-Seed/SeedVR2",
             "note": "Render small + fast, finish at high resolution."},
        ],
    },
    {
        "stage": "interpolate", "label": "Frame interpolation",
        "models": [
            {"key": "rife", "label": "RIFE (ComfyUI-Frame-Interpolation)", "license": "MIT",
             "commercial_ok": True, "vram_gb": 4, "source": "ComfyUI-Frame-Interpolation",
             "note": "Smooth motion / raise fps."},
        ],
    },
    {
        "stage": "mux", "label": "Mux / encode / captions",
        "models": [
            {"key": "ffmpeg-nvenc", "label": "ffmpeg (NVENC)", "license": "LGPL/GPL",
             "commercial_ok": True, "vram_gb": 0, "source": "system ffmpeg",
             "note": "GPU encode; mux audio, burn captions, concat."},
        ],
    },
]

GOALS: Dict[str, Dict[str, object]] = {
    "product_image": {"label": "Product still (commerce)", "stages": ["image", "upscale"]},
    "ugc_talking_head": {"label": "UGC talking-head testimonial",
                         "stages": ["image", "voice", "lipsync", "mux"]},
    "cinematic_short": {"label": "Cinematic short (b-roll, draft->final)",
                        "stages": ["image", "video_fast", "music", "upscale", "interpolate", "mux"]},
    "ad_short": {"label": "Ad short (voice + music)",
                 "stages": ["image", "video_fast", "voice", "music", "upscale", "mux"]},
    "hero_cinematic": {"label": "Hero cinematic (Wan 14B)",
                       "stages": ["image", "video_hero", "music", "upscale", "interpolate", "mux"]},
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


def _models_present(home: Optional[Path], *tokens: str, suffix: str = ".safetensors") -> bool:
    if not home:
        return False
    for d in ("models/diffusion_models", "models/unet", "models/checkpoints"):
        p = home / d
        try:
            if p.is_dir() and any(x.suffix.lower() in (suffix, ".gguf") and
                                  any(t in x.name.lower() for t in tokens)
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
        if key == "flux2":
            return "installed" if _models_present(home, "flux2", "klein") else "missing"
        if key == "qwen-image-edit":
            return "installed" if _models_present(home, "qwen") else "missing"
        if key == "ltx-2.3":
            return "installed" if _models_present(home, "ltx") else "missing"
        if key == "wan22-14b-gguf":
            return "installed" if _models_present(home, "wan") else "missing"
        if key == "wan22-s2v":
            return "installed" if _models_present(home, "s2v") else "missing"
        if key == "infinitetalk":
            return "installed" if (custom and _has_dir(custom / "ComfyUI-InfiniteTalk", custom / "InfiniteTalk")) else "missing"
        if key == "latentsync-1.6":
            return "installed" if (custom and _has_dir(custom / "ComfyUI-LatentSyncWrapper", custom / "ComfyUI-LatentSync")) else "missing"
        if key == "chatterbox":
            return "installed" if (custom and _has_dir(custom / "ComfyUI-Chatterbox", home / "models/audio/chatterbox")) else "missing"
        if key == "ace-step":
            return "installed" if (custom and _has_dir(custom / "ComfyUI-ACE-Step", home / "models/ace_step")) else "missing"
        if key == "seedvr2":
            return "installed" if (custom and _has_dir(custom / "ComfyUI-SeedVR2_VideoUpscaler", home / "models/seedvr2")) else "missing"
        if key == "rife":
            return "installed" if (custom and _has_dir(custom / "ComfyUI-Frame-Interpolation")) else "missing"
        if key == "ffmpeg-nvenc":
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
        "lane": "local-creative-suite", "engine": ENGINE,
        "note": "Model-chaining suite. Localhost only; runs one model at a time. "
                "Readiness here does not install, download, or enable anything.",
        "hybrid_rule": HYBRID_NOTE,
        "render_modes": RENDER_MODES,
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
        "goal": goal, "known": True, "label": g["label"], "engine": ENGINE,
        "steps": steps, "owner_gated_steps": gated,
        "note": "Plan only — no model is downloaded, loaded, or run.",
    }


def render_plan(goal: str, mode: str = "draft") -> Dict[str, object]:
    """Draft->final plan for a goal: which stage/model runs in each pass.

    'draft' renders cheap variations on the fast model; 'final' re-renders only
    approved seeds on the hero model. Never executes.
    """
    if mode not in RENDER_MODES:
        return {"goal": goal, "known": False, "reason": "unknown_mode", "modes": list(RENDER_MODES)}
    base = plan_pipeline(goal)
    if not base.get("known"):
        return base
    mode_stage = str(RENDER_MODES[mode]["stage_model"])
    passes = []
    for s in base["steps"]:
        if s["stage"] == mode_stage or mode == "draft":
            passes.append(s)
    return {
        "goal": goal, "mode": mode, "label": RENDER_MODES[mode]["label"],
        "engine": ENGINE, "steps": passes,
        "mode_note": RENDER_MODES[mode]["note"],
        "finish_stack": ["upscale", "interpolate", "mux"],
        "note": "Plan only — submit approved steps as ComfyUI workflow templates.",
    }
