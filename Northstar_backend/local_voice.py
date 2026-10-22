"""Local narration lane — the operator's own speech engine, no provider key.

This is the LOCAL counterpart of a paid TTS API. It exists so the creative
pipeline can produce narrated video and ad voiceovers on this machine with
nothing configured and nothing spent.

Engines, tried in order:

  piper   a real neural voice, when a model file is configured
          (PIPER_MODEL / PIPER_EXE). Highest quality, still offline.
  sapi    the Windows speech engine via System.Speech (PowerShell). Always
          present on this box; the fallback that makes the lane dependable.

Honesty contract: if no engine can run, this raises with the real reason. It
never returns silence and never claims a voiceover it did not produce.

    python Northstar_backend/local_voice.py --voices
    python Northstar_backend/local_voice.py --say "text" --out out.wav
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from typing import Any, Callable, Dict, List, Optional

MAX_TEXT = 2000
_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
AUDIO_DIR = os.path.join(tempfile.gettempdir(), "northstar-voice")

#: Injectable runner: (powershell_script, timeout) -> stdout. Tests replace it.
Runner = Callable[[str, int], str]


def _ps(script: str, timeout: int = 120) -> str:
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-Command", script],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "powershell failed").strip()[:300])
    return proc.stdout


def _voice_id(name: str) -> str:
    return _SAFE.sub("-", (name or "").strip()).strip("-").lower() or "voice"


# ── piper ────────────────────────────────────────────────────────────────────

def piper_paths() -> Dict[str, Optional[str]]:
    """Where a piper binary + voice model would live. Presence only."""
    exe = os.environ.get("PIPER_EXE") or shutil.which("piper")
    model = os.environ.get("PIPER_MODEL")
    return {"exe": exe, "model": model if model and os.path.isfile(model) else None}


def _piper_synthesize(text: str, out_path: str, *, timeout: int = 300) -> bool:
    paths = piper_paths()
    if not paths["exe"] or not paths["model"]:
        return False
    proc = subprocess.run(
        [str(paths["exe"]), "-m", str(paths["model"]), "-f", out_path],
        input=text, capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or "piper failed").strip()[:300])
    return os.path.isfile(out_path) and os.path.getsize(out_path) > 1000


# ── SAPI ─────────────────────────────────────────────────────────────────────

def sapi_voices(runner: Optional[Runner] = None) -> List[Dict[str, Any]]:
    """Installed OS voices. Empty when the OS has none — never invented."""
    run = runner or _ps
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        "$s.GetInstalledVoices() | ForEach-Object {"
        " if ($_.Enabled) { $i = $_.VoiceInfo;"
        " Write-Output ($i.Name + '|' + $i.Culture.Name + '|' + $i.Gender) } };"
        "$s.Dispose()"
    )
    out = run(script, 60)
    voices = []
    for line in out.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        name, culture, gender = (line.split("|") + ["", "", ""])[:3]
        voices.append({"id": _voice_id(name), "name": name,
                       "lang": (culture or "en-US")[:5],
                       "gender": (gender or "").lower(), "engine": "sapi"})
    return voices


def _sapi_synthesize(text: str, out_path: str, voice_name: str,
                     runner: Optional[Runner] = None, timeout: int = 120) -> bool:
    run = runner or _ps
    safe_text = text.replace("'", "''")
    safe_voice = voice_name.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
        f"$s.SelectVoice('{safe_voice}');"
        f"$s.SetOutputToWaveFile('{out_path}');"
        f"$s.Speak('{safe_text}');"
        "$s.Dispose()"
    )
    run(script, timeout)
    return os.path.isfile(out_path) and os.path.getsize(out_path) > 1000


# ── public surface ───────────────────────────────────────────────────────────

def engines(runner: Optional[Runner] = None) -> Dict[str, Any]:
    """What this machine can actually do, without pretending."""
    piper = piper_paths()
    try:
        voices = sapi_voices(runner)
        sapi_error = None
    except Exception as exc:  # noqa: BLE001
        voices, sapi_error = [], f"{type(exc).__name__}: {exc}"[:200]
    ffmpeg = shutil.which("ffmpeg") or os.environ.get("FFMPEG")
    return {
        "piper": {"available": bool(piper["exe"] and piper["model"]),
                  "exe": bool(piper["exe"]), "model": bool(piper["model"])},
        "sapi": {"available": bool(voices), "voices": len(voices),
                 "error": sapi_error},
        "ffmpeg": {"available": bool(ffmpeg), "path": ffmpeg},
        "preferred": "piper" if (piper["exe"] and piper["model"]) else ("sapi" if voices else None),
    }


def synthesize(text: str, *, voice: Optional[str] = None,
               runner: Optional[Runner] = None,
               out_dir: Optional[str] = None) -> Dict[str, Any]:
    """Render `text` to WAV bytes on this machine.

    Raises RuntimeError with the real reason when no engine can produce audio.
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("text is required")
    if len(text) > MAX_TEXT:
        raise ValueError(f"text is {len(text)} chars; the limit is {MAX_TEXT}")

    out_dir = out_dir or AUDIO_DIR
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"tts-{uuid.uuid4().hex[:12]}.wav")

    if piper_paths()["exe"] and piper_paths()["model"]:
        if _piper_synthesize(text, path):
            with open(path, "rb") as fh:
                return {"bytes": fh.read(), "engine": "piper", "voice": "piper",
                        "format": "wav"}

    try:
        voices = sapi_voices(runner)
    except Exception as exc:  # noqa: BLE001 - report the engine's real reason
        raise RuntimeError(
            f"no local speech engine available: {type(exc).__name__}: {exc}") from exc
    if not voices:
        raise RuntimeError("no local speech engine available: piper is not configured "
                           "and the OS reports no installed voices")
    chosen = None
    if voice:
        wanted = _voice_id(voice)
        chosen = next((v for v in voices if v["id"] == wanted), None)
        if chosen is None:
            raise ValueError(f"unknown voice {voice!r}; try --voices")
    if chosen is None:
        chosen = next((v for v in voices if v["lang"].startswith("en")), voices[0])

    if not _sapi_synthesize(text, path, chosen["name"], runner):
        raise RuntimeError("the local speech engine produced no audio")
    with open(path, "rb") as fh:
        return {"bytes": fh.read(), "engine": "sapi", "voice": chosen["id"],
                "voice_name": chosen["name"], "format": "wav"}


def mux_audio(video_bytes: bytes, audio_bytes: bytes, *,
              ffmpeg: Optional[str] = None, timeout: int = 300) -> bytes:
    """Attach a WAV track to an MP4, returning new MP4 bytes.

    ``-shortest`` keeps the result honest: the clip ends when the shorter of the
    two streams ends, so a short clip is never padded with a frozen frame.
    """
    exe = ffmpeg or shutil.which("ffmpeg") or os.environ.get("FFMPEG")
    if not exe:
        raise RuntimeError("ffmpeg not found: cannot attach narration")
    tmp = tempfile.mkdtemp(prefix="ns-mux-")
    vpath = os.path.join(tmp, "in.mp4")
    apath = os.path.join(tmp, "in.wav")
    opath = os.path.join(tmp, "out.mp4")
    try:
        with open(vpath, "wb") as fh:
            fh.write(video_bytes)
        with open(apath, "wb") as fh:
            fh.write(audio_bytes)
        proc = subprocess.run(
            [str(exe), "-y", "-loglevel", "error", "-i", vpath, "-i", apath,
             "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", opath],
            capture_output=True, text=True, timeout=timeout,
        )
        if proc.returncode != 0 or not os.path.isfile(opath):
            raise RuntimeError((proc.stderr or "ffmpeg mux failed").strip()[:300])
        with open(opath, "rb") as fh:
            return fh.read()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Local narration lane")
    ap.add_argument("--voices", action="store_true")
    ap.add_argument("--engines", action="store_true")
    ap.add_argument("--say", default=None)
    ap.add_argument("--voice", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if args.engines:
        import json
        print(json.dumps(engines(), indent=2))
        return 0
    if args.voices:
        import json
        print(json.dumps(sapi_voices(), indent=2))
        return 0
    if args.say:
        out = synthesize(args.say, voice=args.voice)
        target = args.out or os.path.join(os.getcwd(), "narration.wav")
        with open(target, "wb") as fh:
            fh.write(out["bytes"])
        print(f"{out['engine']} -> {target} ({len(out['bytes'])} bytes)")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
