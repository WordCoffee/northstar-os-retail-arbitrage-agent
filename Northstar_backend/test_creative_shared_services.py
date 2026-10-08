"""Tests for the shared creative-services layer (registry, router, jobs,
provenance, workflows, deployment workers).

Offline: ComfyUI reachability is monkeypatched so routing is deterministic.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from creative import (jobs, provenance, registry, router, workflows, workers)


# --- registry ---------------------------------------------------------------

def test_registry_loads_and_has_approved_components():
    comps = registry.components()
    assert len(comps) >= 15
    assert any(c["id"] == "sdxl-base-1.0" for c in comps)
    assert any(c["id"] == "z-image-turbo" for c in comps)
    assert any(c["id"] == "birefnet" for c in comps)


def test_flux_is_quarantined_and_non_commercial():
    flux = registry.component("flux1-dev-fp8")
    assert flux is not None
    assert flux["status"] == "quarantined"
    assert flux["commercial_use"] == "prohibited"
    assert not registry.is_commercial(flux)
    assert "flux1-dev-fp8" in [c["id"] for c in registry.quarantined()]


def test_license_manifest_shape():
    man = registry.license_manifest()
    assert man["schema"]
    ids = {c["id"] for c in man["components"]}
    assert "sdxl-base-1.0" in ids and "birefnet" in ids
    sdxl = next(c for c in man["components"] if c["id"] == "sdxl-base-1.0")
    assert sdxl["commercial_use"] == "allowed"
    assert "RAIL" in sdxl["license"]


def test_approved_roles_exclude_quarantine():
    gen = registry.by_role("generate")
    assert all(registry.is_approved(c) for c in gen)
    assert all(registry.is_commercial(c) for c in gen)
    assert "flux1-dev-fp8" not in [c["id"] for c in gen]


# --- router -----------------------------------------------------------------

def test_router_draft_prefers_z_image(monkeypatch):
    monkeypatch.setattr(router, "_comfy_up", lambda: True)
    plan = router.route("generate", "draft")
    assert plan["ok"]
    assert plan["primary"]["lane"] == "z-image-draft"
    assert plan["primary"]["component"] == "z-image-turbo"
    # explicit fallbacks, ordered
    assert [f["lane"] for f in plan["fallbacks"]] == ["sdxl-draft"]


def test_router_standard_prefers_sdxl(monkeypatch):
    monkeypatch.setattr(router, "_comfy_up", lambda: True)
    plan = router.route("generate", "standard")
    assert plan["primary"]["lane"] == "sdxl-standard"
    assert plan["quarantined"][0]["id"] == "flux1-dev-fp8"


def test_router_high_prefers_sdxl_not_qwen(monkeypatch):
    monkeypatch.setattr(router, "_comfy_up", lambda: True)
    plan = router.route("generate", "high")
    assert plan["primary"]["lane"] == "sdxl-high"
    assert plan["primary"]["component"] == "sdxl-base-1.0"
    # Qwen is never an implicit default for generation (its t2i weight was retired).
    assert all(f["lane"] != "qwen-t2i" for f in plan["fallbacks"])
    assert "qwen-t2i" not in [e["lane"] for e in plan["explicit_lanes"]]


def test_router_edit_uses_qwen_edit(monkeypatch):
    monkeypatch.setattr(router, "_comfy_up", lambda: True)
    plan = router.route("edit", "standard")
    assert plan["primary"]["lane"] == "qwen-edit"


def test_router_no_silent_fallback_when_comfy_down(monkeypatch):
    monkeypatch.setattr(router, "_comfy_up", lambda: False)
    plan = router.route("generate", "standard")
    assert plan["ok"] is False
    assert plan["primary"] is None
    assert all("ComfyUI not reachable" in e["reasons"] for e in plan["fallbacks"])


def test_router_unknown_capability():
    plan = router.route("teleport")
    assert plan["ok"] is False


def test_router_inpaint_lane(monkeypatch):
    monkeypatch.setattr(router, "_comfy_up", lambda: True)
    plan = router.route("inpaint", "standard")
    assert plan["ok"]
    assert plan["primary"]["lane"] == "sdxl-inpaint"
    assert plan["primary"]["component"] == "sdxl-base-1.0"


# --- workflows (offline builders) ------------------------------------------

def test_sdxl_workflow_nodes():
    wf = workflows.sdxl_t2i("a jar")
    types = {n["class_type"] for n in wf.values()}
    assert "CheckpointLoaderSimple" in types
    assert "KSampler" in types


def test_z_image_workflow_uses_lumina2_and_ae():
    wf = workflows.z_image_t2i("a jar")
    clip = next(n for n in wf.values() if n["class_type"] == "CLIPLoader")
    assert clip["inputs"]["type"] == "lumina2"
    vae = next(n for n in wf.values() if n["class_type"] == "VAELoader")
    assert vae["inputs"]["vae_name"] == "ae.safetensors"


def test_upscale_and_mask_workflows():
    up = workflows.upscale_image("x.png")
    assert any(n["class_type"] == "UpscaleModelLoader" for n in up.values())
    mask = workflows.remove_background("x.png")
    types = {n["class_type"] for n in mask.values()}
    assert "RemoveBackground" in types and "JoinImageWithAlpha" in types


def test_sdxl_controlnet_workflow_has_canny_thresholds():
    wf = workflows.sdxl_t2i("p", controlnet={"image": "c.png", "type": "canny"})
    canny = next(n for n in wf.values() if n["class_type"] == "Canny")
    assert "low_threshold" in canny["inputs"] and "high_threshold" in canny["inputs"]


def test_ipadapter_workflow():
    wf = workflows.sdxl_ipadapter_t2i("p", reference_image="r.png")
    types = {n["class_type"] for n in wf.values()}
    assert "IPAdapterUnifiedLoader" in types and "IPAdapter" in types


def test_sdxl_inpaint_workflow():
    wf = workflows.sdxl_inpaint("p", image_name="i.png", mask_name="m.png")
    types = {n["class_type"] for n in wf.values()}
    assert "SetLatentNoiseMask" in types and "LoadImageMask" in types


# --- finishing stages (offline, no ComfyUI) ---------------------------------

def test_compose_text_accepts_dict_spec(tmp_path):
    from PIL import Image
    from creative import stages
    src = tmp_path / "base.png"
    Image.new("RGB", (512, 512), (240, 240, 240)).save(src)
    out = tmp_path / "out.png"
    res = stages.compose_text(src, out, {"brand": "Mogra Organics",
                                         "product_name": "Organic Turmeric Powder"},
                              {"quad_norm": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.4], [0.1, 0.4]],
                               "curvature": 0.0, "style": "mogra_label_panel"})
    assert res["ok"] and out.exists()
    with Image.open(out) as im:
        assert im.size == (512, 512)


def test_ad_layout_offline_export_and_provenance(tmp_path):
    from PIL import Image
    from creative import stages
    out = tmp_path / "ad.png"
    res = stages.ad_layout(None, None, out, spec={"brand": "Mogra Organics",
                                                  "product_name": "Organic Turmeric Powder",
                                                  "descriptor": "Ground"},
                           export=[512, 512])
    assert res["ok"] and out.exists()
    with Image.open(out) as im:
        assert im.size == (512, 512)
    side = out.with_suffix(".png.json")
    assert side.exists()
    import json as _json
    rec = _json.loads(side.read_text(encoding="utf-8"))
    assert rec["task"] == "ad_layout"
    assert rec["commercial_use"] == "allowed"


def test_foundation_contract_readiness():
    from creative import foundation_contract as fc
    r = fc.build_readiness_shared()
    assert "generation" in r and "routing" in r and "quarantined" in r
    assert "flux1-dev-fp8" in r["quarantined"]


# --- jobs -------------------------------------------------------------------

def test_job_store_create_update_cancel():
    st = jobs.CreativeJobStore()
    job = st.create(task="generate", payload={"prompt": "x"})
    assert st.get(job["id"])["status"] == "queued"
    st.progress(job["id"], stage="generate", step=3, total=8, eta=12.0)
    assert st.get(job["id"])["progress"]["step"] == 3
    assert st.cancel(job["id"]) is True
    assert st.get(job["id"])["status"] == "cancelled"
    assert st.is_cancelled(job["id"]) is True


# --- provenance -------------------------------------------------------------

def test_provenance_sidecar_written(tmp_path: Path):
    out = tmp_path / "asset.png"
    out.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 16)
    side = provenance.write_sidecar(out, task="generate", lane="sdxl-standard",
                                    component="sdxl-base-1.0", params={"steps": 25})
    assert side.exists()
    rec = json.loads(side.read_text(encoding="utf-8"))
    assert rec["schema"] == "northstar-creative-provenance-v1"
    assert rec["lane"] == "sdxl-standard"
    assert rec["commercial_use"] == "allowed"
    assert rec["output_sha256"]


# --- deployment / workers ---------------------------------------------------

def test_workers_config_and_health():
    cfg = workers.config()
    assert cfg.get("workers")
    assert workers.policy()["heavy_concurrency"] == 1
    h = workers.health()
    assert h["workers"][0]["id"] == "gpu0"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
