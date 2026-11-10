"""Northstar Local Voice — a local TTS engine on 127.0.0.1:8321.

Why this exists: the repository ships only the VoiceStudio *adapter*; the engine it
talks to is an external application and is not part of this repo, so `Bojo` had no
voice. This service fills that gap with the operating system's own speech engine
(Windows SAPI), which is fully offline, free, and installs nothing.

It implements the adapter's documented contract exactly:

    GET  /health            -> {"ok": true, "engine": ..., "version": ...}
    GET  /api/voices        -> {"voices": [{"id", "name", "lang", "gender"}]}
    POST /api/tts           -> {"audio_url": "http://127.0.0.1:8321/audio/<f>.wav"}
    POST /api/voices/clone  -> 501 (an OS engine cannot clone a voice - honest)
    POST /api/dub           -> 501 (no translation engine here - honest)

The commercial VoiceStudio can replace this at any time: set VOICESTUDIO_URL to it
and the app never notices. This service never claims to be that product.

Run:
    python tools/local_voice_service.py            # 127.0.0.1:8321
    python tools/local_voice_service.py --port 8321 --host 127.0.0.1

Safety: loopback-only by default, text bounded, voice names validated against the
installed list, output written to a temp dir with unique names, and there is no
network code beyond serving its own audio.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import tempfile
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

VERSION = "1.0.0"
ENGINE = "northstar-local-voice (Windows SAPI)"
MAX_TEXT = 2000
AUDIO_DIR = os.path.join(tempfile.gettempdir(), "northstar-voice")

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


# ── OS speech engine ─────────────────────────────────────────────────────────
def _ps(script: str, timeout: int = 60) -> str:
    """Run one PowerShell snippet. Raises with the real reason on failure."""
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-Command", script],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "powershell failed").strip()[:300])
    return proc.stdout


def list_voices() -> List[Dict[str, Any]]:
    """Installed SAPI voices. Empty when the OS has none - never invented."""
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$s.GetInstalledVoices() | ForEach-Object {"
        " if ($_.Enabled) { $i = $_.VoiceInfo;"
        " Write-Output ($i.Name + '|' + $i.Culture.Name + '|' + $i.Gender) } };"
        "$s.Dispose()"
    )
    out = _ps(script)
    voices = []
    for line in out.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        name, culture, gender = (line.split("|") + ["", "", ""])[:3]
        voices.append({
            "id": _voice_id(name),
            "name": name,
            "lang": (culture or "en-US")[:5],
            "gender": (gender or "").lower(),
        })
    return voices


def _voice_id(name: str) -> str:
    return _SAFE.sub("-", name.strip()).strip("-").lower() or "voice"


def synthesize(text: str, voice_id: Optional[str] = None) -> Dict[str, Any]:
    """Render `text` to a WAV in the served directory. Returns the file info."""
    text = (text or "").strip()
    if not text:
        raise ValueError("text is required")
    if len(text) > MAX_TEXT:
        raise ValueError(f"text is {len(text)} chars; the limit is {MAX_TEXT}")

    voices = list_voices()
    if not voices:
        raise RuntimeError("no speech voices are installed on this system")
    chosen = None
    if voice_id:
        chosen = next((v for v in voices if v["id"] == _voice_id(voice_id)), None)
        if chosen is None:
            raise ValueError(f"unknown voice {voice_id!r}")
    if chosen is None:
        chosen = next((v for v in voices if v["lang"].startswith("en")), voices[0])

    os.makedirs(AUDIO_DIR, exist_ok=True)
    name = f"tts-{uuid.uuid4().hex[:12]}.wav"
    path = os.path.join(AUDIO_DIR, name)
    # Escape single quotes for the PowerShell literal; the path is generated, and
    # only the validated voice NAME and the operator's text are interpolated.
    safe_text = text.replace("'", "''")
    safe_voice = chosen["name"].replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        f"$s.SelectVoice('{safe_voice}');"
        f"$s.SetOutputToWaveFile('{path}');"
        f"$s.Speak('{safe_text}');"
        "$s.Dispose()"
    )
    _ps(script, timeout=120)
    if not os.path.isfile(path) or os.path.getsize(path) < 1000:
        raise RuntimeError("the speech engine produced no audio")
    return {"file": name, "bytes": os.path.getsize(path), "voice": chosen["id"]}


# ── HTTP surface ─────────────────────────────────────────────────────────────
app = FastAPI(title="Northstar Local Voice", version=VERSION)
# The SPA (:8101) and the API (:8000) may both reach this service during local dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8101", "http://localhost:8101",
                   "http://127.0.0.1:8000", "http://localhost:8000"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


class TtsIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=MAX_TEXT)
    voice_id: Optional[str] = Field(None, max_length=120)
    lang: str = Field("en", max_length=12)


@app.get("/health")
def health():
    try:
        voices = list_voices()
        return {"ok": True, "engine": ENGINE, "version": VERSION,
                "voices": len(voices)}
    except Exception as exc:  # noqa: BLE001 - report the real reason
        return {"ok": False, "engine": ENGINE, "version": VERSION,
                "error": str(exc)[:300]}


@app.get("/api/voices")
def voices():
    try:
        return {"voices": list_voices()}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"speech engine unavailable: {exc}")


@app.post("/api/tts")
def tts(body: TtsIn):
    try:
        out = synthesize(body.text, body.voice_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"synthesis failed: {exc}")
    return {"ok": True, "audio_url": f"http://127.0.0.1:8321/audio/{out['file']}",
            "voice_id": out["voice"], "bytes": out["bytes"], "engine": ENGINE}


@app.post("/api/voices/clone")
def clone():
    raise HTTPException(status_code=501,
                        detail="voice cloning is not supported by the OS speech engine; "
                               "point VOICESTUDIO_URL at a real VoiceStudio to clone")


@app.post("/api/dub")
def dub():
    raise HTTPException(status_code=501,
                        detail="dubbing needs a translation engine; not provided here")


os.makedirs(AUDIO_DIR, exist_ok=True)
app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Local TTS engine for Bojo (Windows SAPI).")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8321)
    args = ap.parse_args(argv)
    import uvicorn
    print(f"{ENGINE} v{VERSION} on http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
