"""Local transcription lane — faster-whisper on the CPU, so it costs no VRAM.

Why CPU on purpose: this box has one 16 GB GPU and the render lanes need it. A
Whisper pass on int8 CPU is slower but leaves the GPU completely alone, so a
teardown can run while ComfyUI is loaded. `device="cuda"` is available, never
automatic.

Honesty contract: no model, no ffmpeg, no audio -> raise with the real reason.
It never returns invented text.

    python Northstar_backend/local_transcribe.py --engines
    python Northstar_backend/local_transcribe.py --file clip.wav
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional

#: Small enough to be fast on CPU, good enough to find the hook in a reference
#: clip. Override per call for a full-quality transcript.
DEFAULT_MODEL = os.environ.get("WHISPER_MODEL", "base")
DEFAULT_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
DEFAULT_COMPUTE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")

_MODEL_CACHE: Dict[str, Any] = {}


def engines() -> Dict[str, Any]:
    """What this machine can actually do. Presence only, never invented."""
    info: Dict[str, Any] = {"device": DEFAULT_DEVICE, "compute_type": DEFAULT_COMPUTE,
                            "model": DEFAULT_MODEL}
    try:
        import faster_whisper
        info["faster_whisper"] = getattr(faster_whisper, "__version__", "unknown")
    except Exception as exc:  # noqa: BLE001
        info["faster_whisper"] = None
        info["error"] = f"{type(exc).__name__}: {exc}"[:200]
    try:
        import ctranslate2
        info["ctranslate2"] = ctranslate2.__version__
    except Exception as exc:  # noqa: BLE001
        info["ctranslate2"] = None
        info["ctranslate2_error"] = f"{type(exc).__name__}: {exc}"[:200]
    cache = os.environ.get("HF_HOME") or os.path.join(
        os.path.expanduser("~"), ".cache", "huggingface", "hub")
    info["model_cache"] = cache if os.path.isdir(cache) else None
    info["available"] = bool(info.get("faster_whisper"))
    return info


def _load(model_name: str, device: str, compute_type: str):
    """Load (and cache) a WhisperModel. Import errors surface with their reason."""
    key = f"{model_name}|{device}|{compute_type}"
    if key not in _MODEL_CACHE:
        from faster_whisper import WhisperModel
        _MODEL_CACHE[key] = WhisperModel(model_name, device=device,
                                         compute_type=compute_type)
    return _MODEL_CACHE[key]


def transcribe(audio_bytes: bytes, *, model: Optional[str] = None,
               language: Optional[str] = None, device: Optional[str] = None,
               compute_type: Optional[str] = None,
               beam_size: int = 1, vad_filter: bool = True,
               word_timestamps: bool = False,
               timeout_s: Optional[float] = None) -> Dict[str, Any]:
    """Transcribe audio bytes locally. Returns text + timed segments.

    `word_timestamps=True` asks faster-whisper for per-word start/end; when the
    engine returns them, each segment carries a `words` list. Callers that need
    exact caption cue boundaries should request them; segment timing alone is a
    character-length distribution, not a measurement.

    `timeout_s` is advisory: it is checked between segments so a long file can
    stop early, but it never truncates a result without saying so.
    """
    if not audio_bytes:
        raise ValueError("audio is required")
    model_name = model or DEFAULT_MODEL
    dev = device or DEFAULT_DEVICE
    comp = compute_type or DEFAULT_COMPUTE

    tmp = tempfile.mkdtemp(prefix="ns-stt-")
    path = os.path.join(tmp, "audio.bin")
    with open(path, "wb") as fh:
        fh.write(audio_bytes)

    t0 = time.time()
    try:
        engine = _load(model_name, dev, comp)
        segments, info = engine.transcribe(path, language=language,
                                           beam_size=beam_size, vad_filter=vad_filter,
                                           word_timestamps=word_timestamps)
        out: List[Dict[str, Any]] = []
        truncated = False
        for seg in segments:
            record: Dict[str, Any] = {
                "start": round(float(seg.start), 2),
                "end": round(float(seg.end), 2),
                "text": (seg.text or "").strip(),
            }
            engine_words = getattr(seg, "words", None) or []
            if engine_words:
                record["words"] = [
                    {"start": round(float(w.start), 2),
                     "end": round(float(w.end), 2),
                     "word": str(getattr(w, "word", "") or "").strip(),
                     "probability": round(float(getattr(w, "probability", 0.0) or 0.0), 4)}
                    for w in engine_words
                    if str(getattr(w, "word", "") or "").strip()
                ]
            out.append(record)
            if timeout_s and (time.time() - t0) > float(timeout_s):
                truncated = True
                break
        text = " ".join(s["text"] for s in out).strip()
        return {
            "ok": True,
            "text": text,
            "segments": out,
            "word_timestamps": bool(word_timestamps),
            "language": getattr(info, "language", None) or language,
            "duration": round(float(getattr(info, "duration", 0.0) or 0.0), 2),
            "model": model_name, "device": dev, "compute_type": comp,
            "seconds": round(time.time() - t0, 1),
            "truncated": truncated,
            "vram_used": dev == "cuda",
        }
    finally:
        try:
            os.remove(path)
            os.rmdir(tmp)
        except OSError:
            pass


def transcribe_file(path: str, **kwargs) -> Dict[str, Any]:
    with open(path, "rb") as fh:
        return transcribe(fh.read(), **kwargs)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Local transcription lane (CPU by default)")
    ap.add_argument("--engines", action="store_true")
    ap.add_argument("--file", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--language", default=None)
    ap.add_argument("--device", default=None, help="cpu (default) or cuda")
    args = ap.parse_args(argv)

    if args.engines:
        print(json.dumps(engines(), indent=2))
        return 0
    if args.file:
        out = transcribe_file(args.file, model=args.model, language=args.language,
                              device=args.device)
        print(json.dumps({k: v for k, v in out.items() if k != "segments"}, indent=2))
        for s in out["segments"]:
            print(f"  [{s['start']:>6.2f} -> {s['end']:>6.2f}] {s['text']}")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
