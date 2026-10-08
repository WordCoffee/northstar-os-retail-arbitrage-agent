"""Shared creative pipeline orchestrator.

A request names a *task* and the stages it needs; the pipeline runs only those
stages, reports stage progress, honours cancellation between stages, and releases
ComfyUI model allocations between independent heavy stages (resource policy:
heavy concurrency == 1).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from . import jobs as jobmod
from . import provenance as prov
from . import registry, router, stages

OUT_DIR = Path(__file__).resolve().parents[2] / "generated_images" / "creative"
OUT_DIR.mkdir(parents=True, exist_ok=True)


class _Cancelled(RuntimeError):
    pass


def _out(prefix: str) -> Path:
    return OUT_DIR / f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}_{int(time.time()*1000)%100000}.png"


def _check(store, jid):
    if store.is_cancelled(jid):
        raise jobmod.JobCancelled("cancelled by operator")


def run_job(jid: str, payload: Dict[str, Any], store) -> Dict[str, Any]:
    task = payload.get("task") or "generate"
    _check(store, jid)
    if task == "generate":
        return _task_generate(jid, payload, store)
    if task == "upscale":
        return _task_upscale(jid, payload, store)
    if task == "mask":
        return _task_mask(jid, payload, store)
    if task == "compose_text":
        return _task_compose(jid, payload, store)
    if task == "condition":
        return _task_condition(jid, payload, store)
    if task == "control":
        return _task_control(jid, payload, store)
    if task == "product_ad":
        return _task_product_ad(jid, payload, store)
    if task == "packaging_concept":
        return _task_packaging_concept(jid, payload, store)
    raise ValueError(f"unknown creative task: {task}")


def _finish(store, jid, result: Dict[str, Any], *, lane: str, sidecar: Optional[str] = None):
    store.update(jid, status="done", output=result.get("output") or result.get("mask"),
                 images=[v for v in (result.get("output"), result.get("mask"),
                                     result.get("cutout")) if v],
                 provenance=sidecar or result.get("provenance"),
                 result=result,
                 progress={"stage": "complete", "message": "done"})


def _task_generate(jid, payload, store):
    mode = payload.get("mode", "standard")
    store.progress(jid, stage="generate", message=f"routing ({mode})")
    plan = router.route("generate", mode)
    store.update(jid, plan=plan)
    if not plan.get("ok"):
        raise RuntimeError(plan.get("error") or "no generation lane")
    store.progress(jid, stage="generate", message=f"running lane {plan['primary']['lane']}")
    out = _out("gen")
    res = stages.generate(payload.get("prompt", ""), out, mode=mode,
                          lane=payload.get("lane"),
                          negative=payload.get("negative", ""),
                          width=payload.get("width"), height=payload.get("height"),
                          steps=payload.get("steps"), cfg=payload.get("cfg"),
                          seed=payload.get("seed"))
    stages.unload_comfy_models()
    _finish(store, jid, res, lane=res.get("lane", "generate"))
    return res


def _task_upscale(jid, payload, store):
    src = payload.get("source")
    if not src or not Path(src).exists():
        raise ValueError("upscale requires an existing 'source' image path")
    store.progress(jid, stage="upscale", message="upscaling")
    out = _out("up")
    res = stages.upscale(src, out, model_name=payload.get(
        "model", "RealESRGAN_x4plus.pth"))
    stages.unload_comfy_models()
    _finish(store, jid, res, lane="real-esrgan")
    return res


def _task_mask(jid, payload, store):
    src = payload.get("source")
    if not src or not Path(src).exists():
        raise ValueError("mask requires an existing 'source' image path")
    store.progress(jid, stage="mask", message="detecting foreground")
    out = _out("mask")
    res = stages.remove_background(src, out, model_name=payload.get(
        "model", "birefnet.safetensors"), cutout=payload.get("cutout", True))
    stages.unload_comfy_models()
    _finish(store, jid, res, lane="birefnet")
    return res


def _task_compose(jid, payload, store):
    src = payload.get("source")
    if not src or not Path(src).exists():
        raise ValueError("compose_text requires an existing 'source' image path")
    spec = payload.get("spec")
    surface = payload.get("surface")
    if not spec or not surface:
        raise ValueError("compose_text requires 'spec' and 'surface'")
    store.progress(jid, stage="compose_text", message="drawing exact brand text")
    out = _out("compose")
    res = stages.compose_text(src, out, spec, surface)
    _finish(store, jid, res, lane="exact_text")
    return res


def _task_condition(jid, payload, store):
    src = payload.get("source")
    if not src or not Path(src).exists():
        raise ValueError("condition requires an existing 'source' reference image")
    store.progress(jid, stage="condition", message="reference-conditioned generation")
    out = _out("cond")
    res = stages.condition(payload.get("prompt", ""), src, out,
                           width=payload.get("width", 1024), height=payload.get("height", 1024),
                           steps=payload.get("steps", 25), cfg=payload.get("cfg", 7.0),
                           seed=payload.get("seed"), negative=payload.get("negative", ""),
                           weight=payload.get("weight", 0.8))
    stages.unload_comfy_models()
    _finish(store, jid, res, lane="ip-adapter-sdxl")
    return res


def _task_control(jid, payload, store):
    src = payload.get("source")
    if not src or not Path(src).exists():
        raise ValueError("control requires an existing 'source' control image")
    store.progress(jid, stage="control", message="ControlNet-conditioned generation")
    out = _out("ctrl")
    res = stages.control(payload.get("prompt", ""), src, out,
                         control_type=payload.get("control_type", "canny"),
                         strength=payload.get("strength", 0.6),
                         width=payload.get("width", 1024), height=payload.get("height", 1024),
                         steps=payload.get("steps", 25), cfg=payload.get("cfg", 7.0),
                         seed=payload.get("seed"), negative=payload.get("negative", ""))
    stages.unload_comfy_models()
    _finish(store, jid, res, lane="controlnet-canny-sdxl")
    return res


def _task_product_ad(jid, payload, store):
    """Faithful product ad: keep an approved product photo/cutout, generate the
    scene separately, then apply exact brand text deterministically."""
    source = payload.get("source")
    if not source or not Path(source).exists():
        raise ValueError("product_ad requires an approved 'source' product image")
    stages_list = []
    base = source
    if payload.get("cutout", True):
        store.progress(jid, stage="product_ad.mask", message="isolating product")
        cut = stages.remove_background(source, _out("pa_cut"),
                                       model_name=payload.get("mask_model", "birefnet.safetensors"))
        stages.unload_comfy_models()
        stages_list.append({"stage": "mask", "out": cut.get("cutout") or cut.get("mask")})
        base = cut.get("cutout") or cut.get("mask")
    if payload.get("compose"):
        store.progress(jid, stage="product_ad.compose", message="applying exact brand text")
        res = stages.compose_text(base, _out("pa"), payload["compose"]["spec"],
                                  payload["compose"]["surface"])
        stages_list.append({"stage": "compose_text", "out": res["output"]})
        base = res["output"]
    out = base
    res = {"ok": True, "output": out, "stages": stages_list}
    side = prov.write_sidecar(out, task="product_ad", lane="shared_pipeline",
                              component="birefnet", params=payload,
                              inputs=[source], stages=stages_list)
    _finish(store, jid, res, lane="product_ad", sidecar=str(side))
    return res


def _task_packaging_concept(jid, payload, store):
    """Generated packaging *concept* (clearly a concept, not a faithful SKU)."""
    mode = payload.get("mode", "standard")
    store.progress(jid, stage="packaging_concept", message="generating concept scene")
    prompt = payload.get("prompt", "")
    if not prompt:
        raise ValueError("packaging_concept requires a 'prompt'")
    out = _out("pkg")
    res = stages.generate(prompt, out, mode=mode, negative=payload.get("negative", ""),
                          width=payload.get("width"), height=payload.get("height"),
                          steps=payload.get("steps"), cfg=payload.get("cfg"),
                          seed=payload.get("seed"))
    stages.unload_comfy_models()
    res["concept"] = True
    res["disclaimer"] = ("Generated packaging concept — not a faithful representation "
                         "of a real SKU. Apply approved labels via the compositor.")
    if payload.get("compose"):
        c = stages.compose_text(res["output"], _out("pkg_label"),
                                payload["compose"]["spec"], payload["compose"]["surface"])
        res["composited"] = c["output"]
    side = prov.write_sidecar(res["output"], task="packaging_concept",
                              lane=res.get("lane", "generate"), component=res.get("component"),
                              params=payload, inputs=[], stages=[{"stage": "packaging_concept"}])
    _finish(store, jid, res, lane=res.get("lane", "packaging_concept"), sidecar=str(side))
    return res


# Register the runner with the shared job store.
jobmod.run_from_runner = run_job


def submit(task: str, payload: Dict[str, Any], *, plan: Optional[Dict[str, Any]] = None):
    payload = dict(payload or {})
    payload["task"] = task
    return jobmod.store.submit(task=task, payload=payload, runner=run_job, plan=plan)
