"""Stage executors for the shared creative pipeline.

Each function performs exactly one stage, loads only the resources it needs, and
releases ComfyUI model allocations before returning. Stages are composable; a
request runs only the stages it asks for (no forced all-through pipeline).

ComfyUI is the shared local inference runtime (torch/CUDA live in its venv). The
FastAPI backend talks to it over HTTP.
"""

from __future__ import annotations

import io
import os
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import comfy_client, provenance, registry, router, workflows

OUT_DIR = Path(__file__).resolve().parents[2] / "generated_images" / "creative"
OUT_DIR.mkdir(parents=True, exist_ok=True)


class StageError(RuntimeError):
    pass


def unload_comfy_models() -> bool:
    """Ask ComfyUI to release model allocations (called between heavy stages)."""
    try:
        client = comfy_client.ComfyClient()
        client._json("POST", "/free", {"unload_models": True, "free_memory": True})  # type: ignore[attr-defined]
        return True
    except Exception:
        return False


def _run(workflow: Dict[str, Any], out_path: Path, *, timeout: float = 1200.0) -> bytes:
    client = comfy_client.ComfyClient()
    if not client.is_up():
        raise StageError(f"ComfyUI not reachable at {comfy_client.comfy_base_url()}")
    data = client.run(workflow, timeout=timeout)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return data


def _run_collect(workflow: Dict[str, Any], out_dir: Path, *, timeout: float = 1200.0
                 ) -> List[Dict[str, Any]]:
    """Queue a workflow and persist *every* output image; returns refs + paths."""
    client = comfy_client.ComfyClient()
    if not client.is_up():
        raise StageError(f"ComfyUI not reachable at {comfy_client.comfy_base_url()}")
    prompt_id = client.queue_prompt(workflow)
    rec = client.wait_for(prompt_id, timeout=timeout)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: List[Dict[str, Any]] = []
    for _node, node_out in (rec.get("outputs") or {}).items():
        for ref in node_out.get("images", []) or []:
            data = client.fetch_image(ref)
            p = out_dir / Path(ref["filename"]).name
            p.write_bytes(data)
            saved.append({"filename": ref["filename"], "path": str(p), "bytes": len(data)})
    return saved


def generate(prompt: str, out_path: str | os.PathLike, *, mode: str = "standard",
             lane: Optional[str] = None, negative: str = "",
             width: Optional[int] = None, height: Optional[int] = None,
             steps: Optional[int] = None, cfg: Optional[float] = None,
             seed: Optional[int] = None, controlnet: Optional[Dict[str, Any]] = None,
             allow_quarantined: bool = False) -> Dict[str, Any]:
    """Text-to-image via the routed approved lane."""
    plan = router.route("generate", mode, has_reference=bool(controlnet))
    entries = ([plan["primary"]] if plan.get("primary") else []) + list(plan.get("fallbacks", []))
    if lane:
        entries = [e for e in entries if e.get("lane") == lane] or [
            e for e in plan.get("unavailable", []) if e.get("lane") == lane]

    if not entries:
        # Explicit opt-in to a quarantined lane (local evaluation only).
        if allow_quarantined and lane:
            raise StageError(
                f"lane '{lane}' is quarantined or unavailable; explicit quarantine "
                "opt-in is not enabled in this build")
        raise StageError(plan.get("error") or "no generation lane available")

    errors: List[str] = []
    for entry in entries:
        wf_name = entry.get("workflow")
        if not wf_name:
            errors.append(f"{entry.get('lane')}: no workflow"); continue
        p = dict(entry.get("preset") or {})
        kwargs: Dict[str, Any] = {
            "negative": negative,
            "width": int(width or p.get("width", 1024)),
            "height": int(height or p.get("height", 1024)),
            "steps": int(steps or p.get("steps", 20)),
            "cfg": float(cfg if cfg is not None else p.get("cfg", 4.0)),
            "seed": seed,
        }
        if entry["family"] == "sdxl":
            kwargs["sampler"] = p.get("sampler", "dpmpp_2m")
            kwargs["scheduler"] = p.get("scheduler", "karras")
            if controlnet:
                kwargs["controlnet"] = controlnet
        elif entry["family"] == "z-image":
            kwargs["sampler"] = p.get("sampler", "euler")
            kwargs["scheduler"] = p.get("scheduler", "simple")
        else:
            kwargs["sampler"] = p.get("sampler", "euler")
            kwargs["scheduler"] = p.get("scheduler", "simple")
            kwargs["shift"] = p.get("shift", 3.1)

        try:
            wf = workflows.build(wf_name, prompt, **kwargs)
            out = Path(out_path)
            _run(wf, out, timeout=1200.0)
            side = provenance.write_sidecar(
                out, task="generate", lane=entry["lane"],
                component=entry.get("component"), params=kwargs,
                inputs=[], stages=[{"stage": "generate", "lane": entry["lane"]}],
                extras={"prompt": prompt, "mode": mode})
            return {"ok": True, "output": str(out), "lane": entry["lane"],
                    "component": entry.get("component"), "mode": mode,
                    "preset": p, "provenance": str(side),
                    "fallbacks_available": plan.get("fallbacks", [])}
        except Exception as exc:
            errors.append(f"{entry.get('lane')}: {exc}")
            # Explicit, logged fallback — never silent.
            continue

    raise StageError("all generation lanes failed: " + " | ".join(errors))


def upscale(image_path: str | os.PathLike, out_path: str | os.PathLike, *,
            model_name: str = "RealESRGAN_x4plus.pth") -> Dict[str, Any]:
    if not any(c["id"] == "real-esrgan" for c in registry.by_role("upscale")):
        raise StageError("no approved upscale component registered")
    client = comfy_client.ComfyClient()
    if not client.is_up():
        raise StageError("ComfyUI not reachable for upscale")
    name = client.upload_image(image_path)
    wf = workflows.upscale_image(name, model_name=model_name)
    out = Path(out_path)
    _run(wf, out)
    side = provenance.write_sidecar(out, task="upscale", lane="real-esrgan",
                                    component="real-esrgan",
                                    params={"model": model_name}, inputs=[str(image_path)],
                                    stages=[{"stage": "upscale"}])
    return {"ok": True, "output": str(out), "lane": "real-esrgan",
            "provenance": str(side)}


def remove_background(image_path: str | os.PathLike, out_path: str | os.PathLike, *,
                      model_name: str = "birefnet.safetensors",
                      cutout: bool = True) -> Dict[str, Any]:
    client = comfy_client.ComfyClient()
    if not client.is_up():
        raise StageError("ComfyUI not reachable for background removal")
    name = client.upload_image(image_path)
    wf = workflows.remove_background(name, model_name=model_name, cutout=cutout)
    out_dir = Path(out_path).parent
    saved = _run_collect(wf, out_dir)
    mask_ref = next((s for s in saved if "_mask" in s["filename"]), saved[0] if saved else None)
    cut_ref = next((s for s in saved if "_cutout" in s["filename"]), None)
    if not mask_ref:
        raise StageError("background removal produced no output")
    result = {"ok": True, "mask": mask_ref["path"], "lane": "birefnet",
              "component": "birefnet", "outputs": saved}
    if cut_ref:
        result["cutout"] = cut_ref["path"]
    side = provenance.write_sidecar(mask_ref["path"], task="mask", lane="birefnet",
                                    component="birefnet", params={"model": model_name},
                                    inputs=[str(image_path)],
                                    stages=[{"stage": "remove_background"}])
    result["provenance"] = str(side)
    return result


def compose_text(source_path: str | os.PathLike, out_path: str | os.PathLike, spec: Dict[str, Any],
                 surface: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic exact-text/brand compositing (existing compositor)."""
    from PIL import Image
    from .exact_text import compose_exact_text
    base = Image.open(source_path).convert("RGBA")
    out_img, params = compose_exact_text(base, spec, surface, surface["style"],
                                         supersample=2, enforce_brand=True,
                                         return_params=True)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out_img.convert("RGB").save(out, format="PNG")
    provenance.write_sidecar(out, task="compose_text", lane="exact_text",
                             component="brand-fonts-libre-baskerville",
                             params=params, inputs=[str(source_path)],
                             stages=[{"stage": "compose_text"}])
    return {"ok": True, "output": str(out), "params": params}


def condition(prompt: str, reference_path: str | os.PathLike, out_path: str | os.PathLike, *,
              width: int = 1024, height: int = 1024, steps: int = 25, cfg: float = 7.0,
              seed: Optional[int] = None, negative: str = "", weight: float = 0.8) -> Dict[str, Any]:
    """Reference-conditioned SDXL generation via IP-Adapter Plus."""
    if not registry.installed(registry.component("ip-adapter-sdxl")):
        raise StageError("IP-Adapter component not installed")
    client = comfy_client.ComfyClient()
    if not client.is_up():
        raise StageError("ComfyUI not reachable for conditioning")
    name = client.upload_image(reference_path)
    wf = workflows.sdxl_ipadapter_t2i(prompt, reference_image=name, negative=negative,
                                      width=width, height=height, steps=steps, cfg=cfg,
                                      seed=seed, weight=weight)
    out = Path(out_path)
    _run(wf, out)
    side = provenance.write_sidecar(out, task="condition", lane="ip-adapter-sdxl",
                                    component="ip-adapter-sdxl",
                                    params={"weight": weight, "steps": steps, "cfg": cfg},
                                    inputs=[str(reference_path)],
                                    stages=[{"stage": "condition"}])
    return {"ok": True, "output": str(out), "lane": "ip-adapter-sdxl",
            "component": "ip-adapter-sdxl", "provenance": str(side)}


def control(prompt: str, control_path: str | os.PathLike, out_path: str | os.PathLike, *,
            control_type: str = "canny", strength: float = 0.6, width: int = 1024,
            height: int = 1024, steps: int = 25, cfg: float = 7.0,
            seed: Optional[int] = None, negative: str = "") -> Dict[str, Any]:
    """SDXL + ControlNet (canny) conditioned generation."""
    if not registry.installed(registry.component("controlnet-canny-sdxl")):
        raise StageError("ControlNet component not installed")
    client = comfy_client.ComfyClient()
    if not client.is_up():
        raise StageError("ComfyUI not reachable for control")
    cname = client.upload_image(control_path, name=f"ctrl_{Path(control_path).name}")
    wf = workflows.sdxl_t2i(prompt, negative=negative, width=width, height=height,
                            steps=steps, cfg=cfg, seed=seed,
                            controlnet={"image": cname, "type": control_type,
                                        "strength": strength})
    out = Path(out_path)
    _run(wf, out)
    side = provenance.write_sidecar(out, task="control", lane="controlnet-canny-sdxl",
                                    component="controlnet-canny-sdxl",
                                    params={"type": control_type, "strength": strength},
                                    inputs=[str(control_path)],
                                    stages=[{"stage": "control"}])
    return {"ok": True, "output": str(out), "lane": "controlnet-canny-sdxl",
            "component": "controlnet-canny-sdxl", "provenance": str(side)}


def capabilities() -> Dict[str, Any]:
    return {
        "comfyui_up": comfy_client.ComfyClient(timeout=1.5).is_up(),
        "runtime_ready": {
            "generate": bool(router.route("generate", "standard").get("primary")),
            "edit": bool(router.route("edit", "standard").get("primary")),
            "upscale": registry.installed(registry.component("real-esrgan") or {}),
            "mask": registry.installed(registry.component("birefnet") or {}),
            "control": registry.installed(registry.component("controlnet-canny-sdxl") or {}),
            "condition": registry.installed(registry.component("ip-adapter-sdxl") or {}),
            "compose_text": True,
        },
        "unload_between_stages": True,
        "heavy_concurrency": 1,
    }
