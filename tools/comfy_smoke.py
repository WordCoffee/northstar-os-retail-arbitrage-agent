"""NorthstarOS ComfyUI smoke tests - one run, auto-skips anything not installed.

Tests (each only runs if its model files exist):
  klein      FLUX.2 klein 4B Q8 (GGUF) text-to-image        -> output PNG + timing
  seedvr2    SeedVR2 3B upscale of the z-image mug render   -> output PNG + timing
  wan        Wan 2.2 TI2V-5B tiny clip (2s, 832x480)        -> output video + timing
  inventory  lists presence of TTS models + templates       -> JSON

Writes reports/comfy_media_smoke_<ts>.json under the repo. Stdlib only.
ComfyUI must be running on 127.0.0.1:8199.
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = "http://127.0.0.1:8199"
COMFY = Path(os.environ["USERPROFILE"]) / "ComfyUI"
REPO = Path(__file__).resolve().parents[1]
REPORT_DIR = REPO / "reports"


def api(path, payload=None, timeout=60):
    url = BASE + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def run_graph(name, graph, timeout_s=3600):
    t0 = time.time()
    try:
        res = api("/prompt", {"prompt": graph, "client_id": f"ns-smoke-{name}"})
    except Exception as e:
        return {"test": name, "ok": False, "error": f"queue failed: {e}"}
    if res.get("node_errors"):
        return {"test": name, "ok": False, "error": f"node_errors: {json.dumps(res['node_errors'])[:500]}"}
    pid = res["prompt_id"]
    while time.time() - t0 < timeout_s:
        time.sleep(3)
        try:
            h = api(f"/history/{pid}")
        except Exception:
            continue
        if pid in h:
            status = h[pid].get("status", {})
            outs = []
            for node_out in (h[pid].get("outputs") or {}).values():
                for img in node_out.get("images", []) or []:
                    outs.append(img.get("filename"))
                for v in node_out.get("gifs", []) or []:
                    outs.append(v.get("filename"))
                for v in node_out.get("videos", []) or []:
                    outs.append(v.get("filename"))
                for v in node_out.get("audio", []) or []:
                    outs.append(v.get("filename"))
            return {"test": name, "ok": status.get("status_str") == "success",
                    "status": status.get("status_str"), "seconds": round(time.time() - t0, 1),
                    "outputs": outs}
    return {"test": name, "ok": False, "error": "timeout waiting for history"}


def has(p):
    f = COMFY / "models" / p
    return f.exists() and f.stat().st_size > 1_000_000


def t_klein():
    if not has("unet/flux-2-klein-4b-Q8_0.gguf") or not has("vae/flux2-vae.safetensors"):
        return {"test": "klein", "ok": None, "skipped": "files not staged yet"}
    g = {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "flux-2-klein-4b-Q8_0.gguf"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b_fp8_mixed.safetensors", "type": "flux2", "device": "default"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": "Professional studio photo of a matte black electric kettle on a slate countertop with steam rising, dramatic side lighting, fine droplets, photorealistic product photography"}},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "6": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": 1024, "height": 1024, "batch_size": 1}},
        "7": {"class_type": "CFGGuider", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "cfg": 1}},
        "8": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "9": {"class_type": "Flux2Scheduler", "inputs": {"steps": 4, "width": 1024, "height": 1024}},
        "10": {"class_type": "RandomNoise", "inputs": {"noise_seed": 42}},
        "11": {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["10", 0], "guider": ["7", 0], "sampler": ["8", 0], "sigmas": ["9", 0], "latent_image": ["6", 0]}},
        "12": {"class_type": "VAEDecode", "inputs": {"samples": ["11", 0], "vae": ["3", 0]}},
        "13": {"class_type": "SaveImage", "inputs": {"images": ["12", 0], "filename_prefix": "ns-smoke-klein"}},
    }
    return run_graph("klein", g, timeout_s=1800)


def t_seedvr2():
    if not has("diffusion_models/seedvr2_3b_fp8_e4m3fn.safetensors") or not has("vae/seedvr2_ema_vae_fp16.safetensors"):
        return {"test": "seedvr2", "ok": None, "skipped": "files not staged yet"}
    g = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "ns_input_mug.png"}},
        "2": {"class_type": "ResizeImageMaskNode", "inputs": {"input": ["1", 0], "resize_type": "scale by multiplier", "multiplier": 2.0, "scale_method": "lanczos"}},
        "3": {"class_type": "SeedVR2Preprocess", "inputs": {"resized_images": ["2", 0]}},
        "4": {"class_type": "UNETLoader", "inputs": {"unet_name": "seedvr2_3b_fp8_e4m3fn.safetensors", "weight_dtype": "default"}},
        "5": {"class_type": "VAELoader", "inputs": {"vae_name": "seedvr2_ema_vae_fp16.safetensors"}},
        "6": {"class_type": "VAEEncodeTiled", "inputs": {"pixels": ["3", 0], "vae": ["5", 0], "tile_size": 512, "overlap": 128, "temporal_size": 4096, "temporal_overlap": 8}},
        "7": {"class_type": "SeedVR2Conditioning", "inputs": {"model": ["4", 0], "vae_conditioning": ["6", 0]}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["4", 0], "positive": ["7", 0], "negative": ["7", 1], "latent_image": ["6", 0], "seed": 42, "steps": 1, "cfg": 1, "sampler_name": "euler", "scheduler": "simple", "denoise": 1}},
        "9": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["8", 0], "vae": ["5", 0], "tile_size": 512, "overlap": 128, "temporal_size": 4096, "temporal_overlap": 8}},
        "10": {"class_type": "SeedVR2PostProcessing", "inputs": {"images": ["9", 0], "original_resized_images": ["2", 0], "color_correction_method": "none"}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "ns-smoke-seedvr2"}},
    }
    return run_graph("seedvr2", g, timeout_s=1800)


def t_wan():
    if not has("unet/Wan2.2-TI2V-5B-Q5_K_M.gguf") or not has("text_encoders/umt5-xxl-encoder-Q5_K_M.gguf") or not has("vae/wan2.2_vae.safetensors"):
        return {"test": "wan", "ok": None, "skipped": "files not staged yet"}
    g = {
        "1": {"class_type": "UnetLoaderGGUF", "inputs": {"unet_name": "Wan2.2-TI2V-5B-Q5_K_M.gguf"}},
        "2": {"class_type": "CLIPLoaderGGUF", "inputs": {"clip_name": "umt5-xxl-encoder-Q5_K_M.gguf", "type": "wan"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "wan2.2_vae.safetensors"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": "A travel mug rotates slowly on a white turntable in a bright studio, soft shadows, product b-roll"}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": "blurry, low quality, static, watermark"}},
        "6": {"class_type": "ModelSamplingSD3", "inputs": {"model": ["1", 0], "shift": 8}},
        "7": {"class_type": "Wan22ImageToVideoLatent", "inputs": {"vae": ["3", 0], "width": 832, "height": 480, "length": 49, "batch_size": 1}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["6", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["7", 0], "seed": 42, "steps": 20, "cfg": 5, "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "CreateVideo", "inputs": {"images": ["9", 0], "fps": 24}},
        "11": {"class_type": "SaveVideo", "inputs": {"video": ["10", 0], "filename_prefix": "ns-smoke-wan", "format": "auto", "codec": "auto"}},
    }
    return run_graph("wan", g, timeout_s=5400)


def inventory():
    def stat(p):
        f = COMFY / "models" / p
        return round(f.stat().st_size / 1e6, 1) if f.exists() else None
    return {
        "test": "inventory",
        "ok": True,
        "models": {
            "klein_q8": stat("unet/flux-2-klein-4b-Q8_0.gguf"),
            "seedvr2_3b": stat("diffusion_models/seedvr2_3b_fp8_e4m3fn.safetensors"),
            "wan_5b": stat("unet/Wan2.2-TI2V-5B-Q5_K_M.gguf"),
            "umt5": stat("text_encoders/umt5-xxl-encoder-Q5_K_M.gguf"),
            "wan_vae": stat("vae/wan2.2_vae.safetensors"),
            "flux2_vae": stat("vae/flux2-vae.safetensors"),
            "seedvr2_vae": stat("vae/seedvr2_ema_vae_fp16.safetensors"),
        },
        "tts": sorted(p.name for p in (COMFY / "models" / "TTS" / "Qwen3-TTS").glob("*")) if (COMFY / "models" / "TTS" / "Qwen3-TTS").exists() else [],
        "qwentts_node": (COMFY / "custom_nodes" / "ComfyUI-QwenTTS" / "requirements.txt").exists(),
    }


def t_tts():
    node_req = COMFY / "custom_nodes" / "ComfyUI-QwenTTS" / "requirements.txt"
    if not node_req.exists():
        return {"test": "tts", "ok": None, "skipped": "QwenTTS node not installed"}
    g = {
        "1": {"class_type": "AILab_Qwen3TTSCustomVoice", "inputs": {"text": "Northstar OS local narration test. This voiceover was generated fully offline on the operator's machine.", "speaker": "Ryan", "model_size": "1.7B", "language": "English", "unload_models": False, "seed": 42}},
        "2": {"class_type": "SaveAudio", "inputs": {"audio": ["1", 0], "filename_prefix": "ns-smoke-tts"}},
    }
    return run_graph("tts", g, timeout_s=3600)


def main():
    want = set(sys.argv[1:]) if len(sys.argv) > 1 else None
    results = [inventory()]
    for name, fn in (("klein", t_klein), ("seedvr2", t_seedvr2), ("wan", t_wan), ("tts", t_tts)):
        if want and name not in want:
            continue
        try:
            results.append(fn())
        except Exception as e:
            results.append({"test": name, "ok": False, "error": str(e)})
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = REPORT_DIR / f"comfy_media_smoke_{ts}.json"
    REPORT_DIR.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    for r in results:
        print(json.dumps(r)[:300])
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
