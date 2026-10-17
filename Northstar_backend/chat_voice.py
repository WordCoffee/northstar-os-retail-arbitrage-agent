"""Design Studio — voice intake (S3): local whisper.cpp transcription.

PTT pipeline (all local): browser records opus/webm → ffmpeg converts to
16 kHz mono WAV → whisper-cli (the operator's own binaries in
%USERPROFILE%\\whisper-tools) → clean transcript for the chat composer.
Nothing leaves the machine.

Honesty boundaries:
  • Missing binary/model → 503 with the exact remediation path; never a
    fabricated transcript.
  • Silence → ok:true with an empty text ("heard nothing"), never invented.
  • Latency + model name are reported, not estimated.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from design_studio_api import studio_account

router = APIRouter(prefix="/api/chat/voice", tags=["chat-voice"])

MAX_UPLOAD_BYTES = 25 * 1024 * 1024

# PTT prefers the fast base model; set NS_VOICE_MODEL to the turbo model for
# accuracy-first transcription.
MODEL_ORDER = ("ggml-base.en.bin", "ggml-large-v3-turbo-q5_0.bin")
NOISE_PREFIXES = ("system_info", "whisper_print", "whisper_", "main:",
                  "ggml_", "load_", "ggml_backend")


class VoiceUnavailable(RuntimeError):
    pass


def _whisper_cli() -> Optional[str]:
    env = os.environ.get("NS_WHISPER_CLI")
    if env and Path(env).is_file():
        return env
    home = Path.home()
    for cand in (home / "whisper-tools" / "whisper-cli.exe",):
        if cand.is_file():
            return str(cand)
    return shutil.which("whisper-cli")


def _models_dir() -> Path:
    env = os.environ.get("NS_WHISPER_MODELS")
    return Path(env) if env else (Path.home() / ".local" / "share" / "whisper-cpp")


def _model_path() -> Optional[Path]:
    env = os.environ.get("NS_VOICE_MODEL")
    if env and Path(env).is_file():
        return Path(env)
    d = _models_dir()
    for name in MODEL_ORDER:
        cand = d / name
        if cand.is_file():
            return cand
    return None


def _parse_whisper_output(raw: str) -> str:
    """Keep transcript lines only.

    Filters, in order: special tokens (<|endoftext|> …), timestamp prefixes,
    loader/server noise, punctuation-only lines (the operator's own bat-file
    rule). A transcript that is ONLY a parenthesized non-speech annotation
    like "(eerie music)" is treated as heard-nothing, not as speech.
    """
    lines = []
    for line in str(raw or "").splitlines():
        s = line.strip()
        if not s:
            continue
        if any(s.startswith(p) for p in NOISE_PREFIXES):
            continue
        if any(p in s[:40] for p in ("system_info:", "whisper_print_")):
            continue
        s = re.sub(r"<\|[^|]*\|>", " ", s)          # <|endoftext|> and friends
        s = s.strip()
        if s.startswith("["):
            continue  # timestamp-form line (the operator's bat-file rule: skip)
        if not s:
            continue
        if re.fullmatch(r"[()\[\].,!?\u2026\-–—\s]*", s):
            continue  # punctuation-only line
        lines.append(s)
    text = " ".join(lines).strip()
    if text and re.fullmatch(r"(\([^)]*\)\s*)+", text):
        return ""  # annotation-only → non-speech, honestly empty
    return text


def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, **kw)


def transcribe_file(src_path: Path, language: str = "en") -> dict:
    """ffmpeg → 16 kHz mono WAV → whisper-cli. Raises VoiceUnavailable when the
    toolchain is absent; returns {ok, text, model, elapsed_ms} otherwise."""
    cli = _whisper_cli()
    model = _model_path()
    if not cli:
        raise VoiceUnavailable(
            "whisper-cli.exe not found. Expected in %USERPROFILE%\\whisper-tools "
            "or set NS_WHISPER_CLI to its full path.")
    if not model:
        raise VoiceUnavailable(
            "whisper model not found. Expected ggml-base.en.bin in "
            "%USERPROFILE%\\.local\\share\\whisper-cpp or set NS_VOICE_MODEL.")
    started = time.time()
    with tempfile.TemporaryDirectory(prefix="ns-voice-") as td:
        wav = Path(td) / "in.wav"
        conv = _run(["ffmpeg", "-y", "-i", str(src_path), "-ar", "16000",
                     "-ac", "1", str(wav)], timeout=120)
        if conv.returncode != 0 or not wav.is_file():
            detail = (conv.stderr or b"").decode("utf-8", "replace")[-300:]
            raise VoiceUnavailable(f"audio conversion failed (ffmpeg): {detail}")
        proc = _run([cli, "-m", str(model), "-f", str(wav), "-l", language,
                     "-nt", "--print-special", "false"], timeout=600)
        raw = (proc.stdout or b"").decode("utf-8", "replace")
    if proc.returncode != 0 and not raw.strip():
        raise VoiceUnavailable(
            f"whisper-cli exited {proc.returncode}: "
            f"{(proc.stderr or b'').decode('utf-8', 'replace')[-300:]}")
    return {
        "ok": True,
        "text": _parse_whisper_output(raw),
        "model": model.name,
        "elapsed_ms": int((time.time() - started) * 1000),
    }


@router.get("/status")
def voice_status(acct: str = Depends(studio_account)):
    cli = _whisper_cli()
    model = _model_path()
    available = bool(cli and model)
    return {
        "ok": True,
        "available": available,
        "whisper_cli": bool(cli),
        "model": model.name if model else None,
        "models_dir": str(_models_dir()),
        "note": ("Local whisper.cpp transcription ready."
                 if available else
                 "Voice unavailable: " + ("" if cli else "whisper-cli.exe missing. ")
                 + ("" if model else f"no model in {_models_dir()}.")),
    }


@router.post("/transcribe")
def transcribe(acct: str = Depends(studio_account),
               audio: UploadFile = File(...)):
    """Transcribe one push-to-talk recording. Sync endpoint (threadpool): the
    whisper subprocess must not block the event loop."""
    data = audio.file.read()
    if not data:
        raise HTTPException(status_code=422, detail="empty audio upload")
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="recording too large (25 MB max)")
    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    with tempfile.TemporaryDirectory(prefix="ns-voice-up-") as td:
        src = Path(td) / f"upload{suffix}"
        src.write_bytes(data)
        try:
            return transcribe_file(src)
        except VoiceUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc))
