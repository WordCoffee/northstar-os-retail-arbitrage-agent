"""FLUX 3 graphics gateway — one local endpoint in front of FLUX 3.

`tys_ops.graphics` speaks a tiny contract (`GET /health`, `POST /generate`).
This process implements it with FLUX 3 Image Klein and nothing else: one UNET,
one Qwen3-VL text encoder, the FLUX VAE, 16 steps, CFG 1.0 — the official
text-to-image graph.

Runtime note (stated, not hidden): this machine has no CUDA PyTorch outside
ComfyUI's own virtualenv, so ComfyUI is used as the **local inference runtime**
for FLUX 3. This gateway never *starts* ComfyUI; if it is not already listening
the gateway reports `503` and the graphics lane blocks. It is not the creative
lane, does not touch video, and runs one model: FLUX 3.

    python tools/flux3_gateway.py --port 8190
    python tools/flux3_gateway.py --selftest

Environment:
    COMFYUI_URL        default http://127.0.0.1:8188
    FLUX3_UNET         default flux3-image-klein-int8-convrot.safetensors
    FLUX3_TEXT_ENCODER default qwen3vl_4b_int8_convrot.safetensors
    FLUX3_VAE          default flux2-vae.safetensors
    FLUX3_WIDTH/HEIGHT default 1024
    FLUX3_STEPS        default 16
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional

COMFY = (os.environ.get("COMFYUI_URL") or "http://127.0.0.1:8188").rstrip("/")
# The int8 "convrot" checkpoint hits a host-buffer read failure on this box's
# comfy-aimdo runtime and the GGUF quant stalls ComfyUI-GGUF's patcher on 0.43,
# so the native nvfp4 checkpoint (Blackwell) is the working path.
UNET = os.environ.get("FLUX3_UNET") or "flux3-image-klein-nvfp4.safetensors"
UNET_LOADER = (os.environ.get("FLUX3_UNET_LOADER") or
               ("UnetLoaderGGUF" if UNET.lower().endswith(".gguf") else "UNETLoader"))
TEXT_ENCODER = os.environ.get("FLUX3_TEXT_ENCODER") or "qwen3vl_4b_int8_convrot.safetensors"
VAE = os.environ.get("FLUX3_VAE") or "flux2-vae.safetensors"
DEFAULT_W = int(os.environ.get("FLUX3_WIDTH") or 1024)
DEFAULT_H = int(os.environ.get("FLUX3_HEIGHT") or 1024)
STEPS = int(os.environ.get("FLUX3_STEPS") or 16)
MODEL_ID = "flux-3-image-klein"

MODELS = Path(r"C:\Users\T2Hol\ComfyUI\models")
OUTPUT = Path(r"C:\Users\T2Hol\ComfyUI\output")


def _json(url: str, payload: Optional[Dict[str, Any]] = None,
          timeout: float = 10.0) -> Dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", "replace")
    return json.loads(body or "{}")


def models_present() -> Dict[str, Any]:
    diffs = MODELS / "diffusion_models" / UNET
    tes = MODELS / "text_encoders" / TEXT_ENCODER
    vae = MODELS / "vae" / VAE
    missing = [str(p) for p in (diffs, tes, vae) if not p.is_file()]
    return {"present": not missing, "missing": missing,
            "unet": str(diffs), "text_encoder": str(tes), "vae": str(vae)}


def health() -> Dict[str, Any]:
    models = models_present()
    comfy = False
    detail = ""
    if models["present"]:
        try:
            _json(COMFY + "/system_stats", timeout=3)
            comfy = True
        except Exception as exc:  # noqa: BLE001
            detail = f"comfyui_unreachable: {type(exc).__name__}"
    else:
        detail = "flux3_weights_missing"
    return {
        "status": "ok" if (models["present"] and comfy) else "unavailable",
        "model": MODEL_ID,
        "detail": detail or "flux3 image graph ready",
        "runtime": "comfyui (local inference; never launched by this gateway)",
        "weights": models,
        "steps": STEPS,
    }


def _graph(prompt: str, width: int, height: int, steps: int,
           seed: int, negative: str = "") -> Dict[str, Any]:
    unet_inputs = {"unet_name": UNET}
    if UNET_LOADER == "UNETLoader":
        unet_inputs["weight_dtype"] = "default"
    return {
        "101": {"class_type": UNET_LOADER, "inputs": unet_inputs},
        "102": {"class_type": "CLIPLoader",
                "inputs": {"clip_name": TEXT_ENCODER, "type": "flux3",
                           "device": "default"}},
        "103": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "104": {"class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": ["102", 0]}},
        "105": {"class_type": "CLIPTextEncode",
                "inputs": {"text": negative, "clip": ["102", 0]}},
        "106": {"class_type": "EmptyFlux2LatentImage",
                "inputs": {"width": int(width), "height": int(height),
                           "batch_size": 1}},
        "132": {"class_type": "ModelSamplingFlux",
                "inputs": {"model": ["101", 0], "max_shift": 2.77259,
                           "base_shift": 2.77259, "width": int(width),
                           "height": int(height)}},
        "107": {"class_type": "KSampler",
                "inputs": {"model": ["132", 0], "seed": int(seed),
                           "steps": int(steps), "cfg": 1.0,
                           "sampler_name": "euler", "scheduler": "simple",
                           "denoise": 1.0, "positive": ["104", 0],
                           "negative": ["105", 0], "latent_image": ["106", 0]}},
        "108": {"class_type": "VAEDecode",
                "inputs": {"samples": ["107", 0], "vae": ["103", 0]}},
        "109": {"class_type": "SaveImage",
                "inputs": {"images": ["108", 0],
                           "filename_prefix": "flux3"}},
    }


def generate(prompt: str, width: int = DEFAULT_W, height: int = DEFAULT_H,
             steps: int = STEPS, seed: Optional[int] = None,
             negative: str = "", timeout: float = 900.0) -> Dict[str, Any]:
    ready = health()
    if ready["status"] != "ok":
        raise RuntimeError(ready["detail"])
    seed = int(seed) if seed is not None else int.from_bytes(os.urandom(4), "big")
    client_id = uuid.uuid4().hex
    queued = _json(COMFY + "/prompt",
                   {"prompt": _graph(prompt, width, height, steps, seed, negative),
                    "client_id": client_id})
    prompt_id = queued.get("prompt_id")
    if not prompt_id:
        raise RuntimeError(f"comfyui rejected the graph: {queued}")

    deadline = time.time() + timeout
    while time.time() < deadline:
        history = _json(COMFY + "/history/" + prompt_id, timeout=15)
        entry = history.get(prompt_id) or {}
        status = entry.get("status") or {}
        if status.get("status_str") == "error":
            raise RuntimeError(f"flux3 render failed: {status}")
        images = []
        for node in (entry.get("outputs") or {}).values():
            for image in node.get("images") or []:
                if image.get("type") == "output":
                    images.append(image)
        if images:
            paths = []
            for image in images:
                path = OUTPUT / (image.get("subfolder") or "") / image["filename"]
                paths.append(str(path.resolve()))
            return {"status": "ok", "model": MODEL_ID, "prompt_id": prompt_id,
                    "seed": seed, "width": int(width), "height": int(height),
                    "steps": int(steps), "images": paths,
                    "path": paths[0]}
        time.sleep(1.0)
    raise RuntimeError("timed out waiting for the flux3 render")


class Handler(BaseHTTPRequestHandler):
    server_version = "Flux3Gateway/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:  # quiet by default
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib contract
        if self.path.rstrip("/") in ("/health", ""):
            report = health()
            self._send(200 if report["status"] == "ok" else 503, report)
            return
        self._send(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib contract
        if self.path.rstrip("/") != "/generate":
            self._send(404, {"error": "not_found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "bad_json"})
            return
        prompt = str(body.get("prompt") or "").strip()
        if not prompt:
            self._send(400, {"error": "prompt_required"})
            return
        try:
            result = generate(
                prompt,
                width=int(body.get("width") or DEFAULT_W),
                height=int(body.get("height") or DEFAULT_H),
                steps=int(body.get("steps") or STEPS),
                seed=body.get("seed"),
                negative=str(body.get("negative") or ""),
            )
        except Exception as exc:  # noqa: BLE001 - reported as JSON
            self._send(500, {"error": f"{type(exc).__name__}: {exc}"})
            return
        self._send(200, result)


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8190)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)

    if args.selftest:
        print(json.dumps(health(), indent=2))
        if health()["status"] != "ok":
            return 1
        print(json.dumps(generate("A red fox in fresh snow at sunrise, "
                                  "photorealistic, 35mm"), indent=2))
        return 0

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(json.dumps({"gateway": f"http://{args.host}:{args.port}",
                      "model": MODEL_ID, **health()}, indent=2))
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
