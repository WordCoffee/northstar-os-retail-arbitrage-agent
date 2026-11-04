"""Off-box image scorers: PickScore (prompt adherence) and HPSv2 (human preference).

Both models are ViT-H/14 CLIP towers. Loading both in one process measured
**6.4 GB RSS and left 0.7 GB free** on this 16 GB box - enough to swap the whole
desktop. So each axis runs in its own short-lived child process and the weights
are released when it exits. Measured, bf16, one axis at a time:

    PickScore  2.47 GB RSS, 5.1 GB free, ~0.45 s/image
    HPSv2      4.81 GB RSS, 3.0 GB free, ~0.45 s/image (mmap load)

The models are local. Nothing is downloaded at score time: the PickScore
directory and the HPSv2 checkpoint are resolved from `config/image_review.json`
or the environment, and a missing file is an explicit error, never a fallback
download.

Scoring conventions follow the model authors:
* PickScore  -> `CLIPModel(...).logits_per_image` (cosine x learned logit scale,
  ~15-25 for this family; higher is better);
* HPSv2      -> normalised cosine between image and text features, no logit
  scale (~0.20-0.30 observed for this family; higher is better).

CLI (what the child runs):

    python -m image_review_scorers --axis preference --text "<brief>" < image.png

prints one JSON line: {"ok": true, "axis": ..., "score": ..., "model": ...}.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CONFIG_PATH = ROOT / "config" / "image_review.json"

DEFAULT_PICKSCORE_DIR = Path(
    r"C:\Users\T2Hol\ComfyUI\models\_incoming\yuvalkirstain__PickScore_v1")
DEFAULT_HPSV2_CKPT = Path(
    r"C:\Users\T2Hol\ComfyUI\models\_incoming\xswu__HPSv2\HPS_v2.1_compressed.pt")

#: axis -> (model label, resolved path key)
AXES = {"adherence": "pickscore", "preference": "hpsv2"}


# ---------------------------------------------------------------------------
# configuration
# ---------------------------------------------------------------------------

def load_config(path: Path = CONFIG_PATH) -> Dict[str, Any]:
    try:
        cfg = json.loads(Path(path).read_text(encoding="utf-8"))
        return cfg if isinstance(cfg, dict) else {}
    except Exception:
        return {}


def _model_paths(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Path]:
    cfg = cfg if cfg is not None else load_config()
    models = cfg.get("models") or {}
    pick = Path(os.environ.get("NS_PICKSCORE_DIR")
                or models.get("pickscore_dir") or DEFAULT_PICKSCORE_DIR)
    hps = Path(os.environ.get("NS_HPSV2_CKPT")
               or models.get("hpsv2_checkpoint") or DEFAULT_HPSV2_CKPT)
    return {"pickscore": pick, "hpsv2": hps}


def available(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Report whether both scorers can run, without importing torch."""
    import importlib.util

    cfg = cfg if cfg is not None else load_config()
    enabled = bool((cfg.get("scorers") or {}).get("enabled", True))
    if os.environ.get("NS_SCORERS_DISABLED") == "1":
        enabled = False
    paths = _model_paths(cfg)
    deps = {name: importlib.util.find_spec(name) is not None
            for name in ("torch", "transformers", "open_clip")}
    files = {
        "pickscore": (paths["pickscore"] / "model.safetensors").is_file(),
        "hpsv2": paths["hpsv2"].is_file(),
    }
    ok = enabled and all(deps.values()) and all(files.values())
    detail = []
    if not enabled:
        detail.append("disabled")
    detail += [f"{k}_missing" for k, v in deps.items() if not v]
    detail += [f"{k}_weights_missing" for k, v in files.items() if not v]
    return {"ok": ok, "enabled": enabled, "deps": deps, "files": files,
            "paths": {k: str(v) for k, v in paths.items()},
            "detail": ",".join(detail) or "ready"}


# ---------------------------------------------------------------------------
# the models (child process only)
# ---------------------------------------------------------------------------

def _threads() -> None:
    import torch

    torch.set_num_threads(int(os.environ.get("NS_SCORER_THREADS")
                              or max(1, min(8, (os.cpu_count() or 4) // 2))))


def _load_pickscore(path: Path):
    import torch
    from transformers import CLIPModel, CLIPProcessor

    kwargs = {"low_cpu_mem_usage": True}
    try:
        model = CLIPModel.from_pretrained(str(path), dtype=torch.bfloat16, **kwargs)
    except TypeError:  # transformers < 5 calls the argument torch_dtype
        model = CLIPModel.from_pretrained(str(path), torch_dtype=torch.bfloat16,
                                          **kwargs)
    processor = CLIPProcessor.from_pretrained(str(path))
    model.eval()
    return model, processor


def _load_hpsv2(checkpoint: Path, processor_dir: Path):
    import open_clip
    import torch

    model, _, _ = open_clip.create_model_and_transforms("ViT-H-14", pretrained=None)
    model = model.to(torch.bfloat16)
    payload = torch.load(str(checkpoint), map_location="cpu", weights_only=True,
                         mmap=True)
    model.load_state_dict(payload["state_dict"])
    del payload
    model.eval()
    # the CLIP tokenizer is identical (vocab 49408); reuse it instead of
    # downloading open_clip's BPE. Text must be padded to the model's 77 tokens.
    from transformers import CLIPProcessor

    processor = CLIPProcessor.from_pretrained(str(processor_dir))
    return model, processor


def _image_from_stdin():
    from PIL import Image

    data = sys.stdin.buffer.read()
    if not data:
        raise ValueError("no image on stdin")
    return Image.open(io.BytesIO(data)).convert("RGB")


def _score_axis(axis: str, text: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    import torch

    paths = _model_paths(cfg)
    image = _image_from_stdin()
    started = time.time()
    if AXES.get(axis) == "hpsv2":
        model, processor = _load_hpsv2(paths["hpsv2"], paths["pickscore"])
        pixel = processor(images=image, return_tensors="pt")["pixel_values"]
        pixel = pixel.to(torch.bfloat16)
        ids = processor(text=[text or "an image"], return_tensors="pt",
                        padding=True, truncation=True)["input_ids"]
        if ids.shape[1] < 77:
            padded = torch.zeros((ids.shape[0], 77), dtype=ids.dtype)
            padded[:, : ids.shape[1]] = ids
            ids = padded
        with torch.inference_mode():
            image_features = model.encode_image(pixel)
            text_features = model.encode_text(ids)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            score = float((image_features @ text_features.T).squeeze())
        label = "hpsv2"
    elif AXES.get(axis) == "pickscore":
        model, processor = _load_pickscore(paths["pickscore"])
        inputs = processor(text=[text or "an image"], images=image,
                           return_tensors="pt", padding=True, truncation=True)
        inputs = {k: (v.to(torch.bfloat16) if v.is_floating_point() else v)
                  for k, v in inputs.items()}
        with torch.inference_mode():
            out = model(**inputs)
            score = float(out.logits_per_image)
        label = "pickscore"
    else:
        raise ValueError(f"unknown axis {axis!r}; known: {sorted(AXES)}")
    return {"ok": True, "axis": axis, "model": label, "score": round(score, 4),
            "seconds": round(time.time() - started, 2)}


# ---------------------------------------------------------------------------
# the parent-side call
# ---------------------------------------------------------------------------

def score(axis: str, image_png: bytes, text: str = "",
          timeout: Optional[float] = None) -> Dict[str, Any]:
    """Run one axis in a child process and return its JSON result."""
    cfg = load_config()
    ready = available(cfg)
    if not ready["ok"]:
        return {"ok": False, "axis": axis, "error": "scorers_unavailable",
                "detail": ready["detail"]}
    if axis not in AXES:
        return {"ok": False, "axis": axis, "error": f"unknown_axis: {axis}"}
    limit = float(timeout or os.environ.get("NS_SCORER_TIMEOUT_S")
                  or (cfg.get("scorers") or {}).get("timeout_s") or 300)
    encoded = base64.b64encode((text or "").encode("utf-8")).decode("ascii")
    cmd = [sys.executable, "-m", "image_review_scorers", "--axis", axis,
           "--text-b64", encoded]
    env = dict(os.environ)
    env["PYTHONPATH"] = str(HERE) + os.pathsep + env.get("PYTHONPATH", "")
    threads = (cfg.get("scorers") or {}).get("threads")
    if threads:
        env["NS_SCORER_THREADS"] = str(int(threads))
    try:
        proc = subprocess.run(cmd, input=bytes(image_png), capture_output=True,
                              cwd=str(HERE), env=env, timeout=limit)
    except subprocess.TimeoutExpired:
        return {"ok": False, "axis": axis, "error": f"scorer_timeout_{int(limit)}s"}
    for line in reversed((proc.stdout or b"").decode("utf-8", "replace").splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and "score" in payload:
            return payload
    detail = (proc.stderr or b"").decode("utf-8", "replace")[-400:]
    return {"ok": False, "axis": axis, "error": f"scorer_exit_{proc.returncode}",
            "detail": detail}


def default_scorer(axis: str):
    """A `(png_bytes, brief) -> float` callable for `ship_gate.review_image`."""
    def _call(png: bytes, brief: str) -> float:
        result = score(axis, png, brief)
        if not result.get("ok"):
            raise RuntimeError(str(result.get("error") or "scorer_failed"))
        return float(result["score"])
    return _call


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--axis", required=True, choices=sorted(AXES))
    ap.add_argument("--text-b64", default="")
    args = ap.parse_args(argv)
    text = ""
    if args.text_b64:
        try:
            text = base64.b64decode(args.text_b64.encode("ascii")).decode("utf-8")
        except Exception:
            text = ""
    _threads()
    try:
        result = _score_axis(args.axis, text, load_config())
    except Exception as exc:  # noqa: BLE001 - the parent must see the failure
        result = {"ok": False, "axis": args.axis, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
