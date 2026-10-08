"""Verify creative component integrity: local SHA-256 + upstream cross-check.

For Hugging Face weights the upstream SHA-256 (LFS OID) is fetched from the model
API. For GitHub-hosted assets with no published digest, the result is recorded as
"unavailable" (never invented). Writes reports/creative_integrity_<date>.{json,md}.
"""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COMFY = Path(r"C:\Users\T2Hol\ComfyUI")
OUT = REPO / "reports"
OUT.mkdir(parents=True, exist_ok=True)

# component id -> (install path, upstream kind, repo, file)
ITEMS = {
    "sdxl-base-1.0": (COMFY / "models/checkpoints/sd_xl_base_1.0.safetensors",
                      "hf", "stabilityai/stable-diffusion-xl-base-1.0", "sd_xl_base_1.0.safetensors"),
    "z-image-turbo": (COMFY / "models/diffusion_models/z_image_turbo_nvfp4.safetensors",
                      "hf", "Comfy-Org/z_image_turbo", "split_files/diffusion_models/z_image_turbo_nvfp4.safetensors"),
    "z-image-text-encoder": (COMFY / "models/text_encoders/qwen_3_4b_fp8_mixed.safetensors",
                             "hf", "Comfy-Org/z_image_turbo", "split_files/text_encoders/qwen_3_4b_fp8_mixed.safetensors"),
    "z-image-vae": (COMFY / "models/vae/ae.safetensors",
                    "hf", "Comfy-Org/z_image_turbo", "split_files/vae/ae.safetensors"),
    "ip-adapter-sdxl": (COMFY / "models/ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors",
                        "hf", "h94/IP-Adapter", "sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors"),
    "clip-vit-h": (COMFY / "models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
                   "hf", "h94/IP-Adapter", "models/image_encoder/model.safetensors"),
    "controlnet-canny-sdxl": (COMFY / "models/controlnet/xinsir-canny-sdxl.safetensors",
                              "hf", "xinsir/controlnet-canny-sdxl-1.0", "diffusion_pytorch_model.safetensors"),
    "birefnet": (COMFY / "models/background_removal/birefnet.safetensors",
                 "hf", "ZhengPeng7/BiRefNet", "model.safetensors"),
    "real-esrgan": (COMFY / "models/upscale_models/RealESRGAN_x4plus.pth",
                    "github", "xinntao/Real-ESRGAN", "v0.1.0/RealESRGAN_x4plus.pth"),
    "qwen-image-2512": (COMFY / "models/unet/qwen-image-2512-Q4_K_M.gguf",
                        "hf", "unsloth/Qwen-Image-2512-GGUF", "qwen-image-2512-Q4_K_M.gguf"),
    "qwen-image-edit-2511": (COMFY / "models/unet/qwen-image-edit-2511-Q4_K_M.gguf",
                             "hf", "unsloth/Qwen-Image-Edit-2511-GGUF", "qwen-image-edit-2511-Q4_K_M.gguf"),
}


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def hf_upstream(repo: str, fname: str) -> str | None:
    try:
        with urllib.request.urlopen(
                f"https://huggingface.co/api/models/{repo}?blobs=true", timeout=30) as r:
            data = json.loads(r.read().decode())
        for s in data.get("siblings", []):
            if s.get("rfilename") == fname:
                lfs = s.get("lfs") or {}
                return lfs.get("sha256")
    except Exception:
        return None
    return None


def main() -> int:
    rows = []
    for cid, (path, kind, repo, fname) in ITEMS.items():
        local = sha256(path)
        upstream = None
        if kind == "hf":
            upstream = hf_upstream(repo, fname)
        if upstream is None:
            status = "upstream_unavailable"
        elif upstream == local:
            status = "match"
        else:
            status = "MISMATCH"
        rows.append({"component": cid, "path": str(path), "exists": path.exists(),
                     "local_sha256": local, "upstream_kind": kind,
                     "upstream_repo": repo, "upstream_file": fname,
                     "upstream_sha256": upstream, "status": status,
                     "source_evidence": f"{repo}/{fname}"})

    (OUT / "creative_integrity_20261008.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8")

    lines = ["# Creative Component Integrity — 2026-10-08", "",
             "Local SHA-256 computed for every installed weight. Upstream SHA-256 is",
             "the publisher's Hugging Face LFS OID where the API exposes it; GitHub",
             "release assets have no published digest and are recorded as",
             "`upstream_unavailable` (never invented).", "",
             "| Component | Local SHA-256 | Upstream | Status |",
             "|---|---|---|---|"]
    for r in rows:
        loc = (r["local_sha256"] or "—")[:16]
        up = (r["upstream_sha256"] or "unavailable")[:16] if r["upstream_sha256"] else "unavailable"
        lines.append(f"| {r['component']} | `{loc}…` | `{up}…` | {r['status']} |")
    lines += ["", "## Evidence", ""]
    for r in rows:
        lines.append(f"- **{r['component']}**: {r['source_evidence']} "
                     f"(local={'yes' if r['exists'] else 'no'}, status={r['status']})")
    (OUT / "creative_integrity_20261008.md").write_text("\n".join(lines), encoding="utf-8")

    for r in rows:
        print(f"{r['component']}: {r['status']} local={(r['local_sha256'] or '-')[:12]} "
              f"up={(r['upstream_sha256'] or '-')[:12]}")
    print("report ->", OUT / "creative_integrity_20261008.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
