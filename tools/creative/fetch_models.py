"""Download approved creative components into the local runtimes.

Uses resumable HTTP (Range) so a dropped connection does not restart a 7 GB file.
Verifies byte size against the remote Content-Length and rewrites
shared/creative-components.json presence/sha fields via creative.registry.

Only approved, commercially-compatible components are listed here.
"""
from __future__ import annotations

import os
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COMFY = Path(os.environ.get("COMFYUI_DIR", r"C:\Users\T2Hol\ComfyUI"))
MODELS = COMFY / "models"

# (id, url, destination, approx_mb)
ITEMS = [
    ("real-esrgan",
     "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
     MODELS / "upscale_models" / "RealESRGAN_x4plus.pth", 64),
    ("birefnet",
     "https://huggingface.co/ZhengPeng7/BiRefNet/resolve/main/model.safetensors",
     MODELS / "background_removal" / "birefnet.safetensors", 1000),
    ("ip-adapter-sdxl",
     "https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors",
     MODELS / "ipadapter" / "ip-adapter-plus_sdxl_vit-h.safetensors", 850),
    ("clip-vit-h",
     "https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors",
     MODELS / "clip_vision" / "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors", 2500),
    ("sdxl-base-1.0",
     "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors",
     MODELS / "checkpoints" / "sd_xl_base_1.0.safetensors", 6900),
    ("controlnet-canny-sdxl",
     "https://huggingface.co/xinsir/controlnet-canny-sdxl-1.0/resolve/main/diffusion_pytorch_model.safetensors",
     MODELS / "controlnet" / "xinsir-canny-sdxl.safetensors", 2500),
    ("z-image-vae",
     "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/vae/ae.safetensors",
     MODELS / "vae" / "ae.safetensors", 335),
    ("z-image-turbo",
     "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/diffusion_models/z_image_turbo_nvfp4.safetensors",
     MODELS / "diffusion_models" / "z_image_turbo_nvfp4.safetensors", 4510),
    ("z-image-text-encoder",
     "https://huggingface.co/Comfy-Org/z_image_turbo/resolve/main/split_files/text_encoders/qwen_3_4b_fp8_mixed.safetensors",
     MODELS / "text_encoders" / "qwen_3_4b_fp8_mixed.safetensors", 5632),
]


def _remote_size(url: str) -> int:
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=30) as r:
        return int(r.headers.get("Content-Length") or 0)


def _download(url: str, dest: Path, *, retries: int = 5) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    total = _remote_size(url)
    for attempt in range(retries):
        have = dest.stat().st_size if dest.exists() else 0
        if total and have == total:
            return
        headers = {"Range": f"bytes={have}-"} if have else {}
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as r, open(dest, "ab") as fh:
                got = have
                last = time.time()
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    fh.write(chunk)
                    got += len(chunk)
                    if time.time() - last > 15:
                        pct = (got / total * 100) if total else 0
                        print(f"    {dest.name}: {got/1e9:.2f}/{total/1e9:.2f} GB ({pct:.0f}%)", flush=True)
                        last = time.time()
            if total and got < total:
                print(f"    short read ({got}/{total}); resuming…", flush=True)
                time.sleep(2)
                continue
            return
        except Exception as exc:
            print(f"    error: {exc}; retry {attempt+1}/{retries}", flush=True)
            time.sleep(3)
    raise RuntimeError(f"failed to download {url}")


def free_gb() -> float:
    import shutil
    return shutil.disk_usage(str(COMFY)).free / 1e9


def main(argv: list[str]) -> int:
    wanted = set(argv) if argv else None
    print(f"disk free: {free_gb():.1f} GB", flush=True)
    for cid, url, dest, approx in ITEMS:
        if wanted and cid not in wanted:
            continue
        if dest.exists() and dest.stat().st_size > 1024:
            print(f"[skip] {cid}: {dest} ({dest.stat().st_size/1e9:.2f} GB)", flush=True)
            continue
        if free_gb() < approx / 1000 * 1.2:
            print(f"[!!] {cid}: not enough disk ({free_gb():.1f} GB free, need ~{approx/1000:.1f} GB)",
                  flush=True)
            continue
        print(f"[dl] {cid} -> {dest} (~{approx} MB)", flush=True)
        _download(url, dest)
        print(f"[ok] {cid}: {dest.stat().st_size/1e9:.2f} GB", flush=True)

    # Refresh presence + hashes in the manifest.
    try:
        sys.path.insert(0, str(REPO / "Northstar_backend"))
        from creative import registry  # type: ignore
        registry.build_hashes(update=True)
        print("manifest refreshed:", registry.status(), flush=True)
    except Exception as exc:
        print("manifest refresh skipped:", exc, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
