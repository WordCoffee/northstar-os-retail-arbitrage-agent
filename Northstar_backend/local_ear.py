"""Local ear — turn the operator's speech into text without a cloud service.

Two backends, tried in this order:

  whisper  a real transcript: `sounddevice` captures 16 kHz mono, then
           `local_transcribe` (faster-whisper, CPU/int8) does the words.
           Best accuracy, needs `pip install sounddevice`.
  sapi     the Windows speech recogniser via System.Speech in PowerShell.
           Zero install, already on this box, offline; a single utterance.

Honesty contract: no microphone, no recogniser, or silence -> a result with
`ok: False` and the real reason. It never invents a sentence, and it never
uploads audio: there is no network call in this module at all.

    python Northstar_backend/local_ear.py --engines
    python Northstar_backend/local_ear.py --listen --seconds 6
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time
import wave
from typing import Any, Callable, Dict, List, Optional

#: Injectable runner: (powershell_script, timeout) -> stdout. Tests replace it.
Runner = Callable[[str, int], str]
#: Injectable recorder: (seconds) -> WAV bytes. Tests replace it.
Recorder = Callable[[float], bytes]

DEFAULT_SECONDS = float(os.environ.get("LOCAL_EAR_SECONDS", "6"))
SAMPLE_RATE = 16000


def _ps(script: str, timeout: int = 120) -> str:
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-Command", script],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "powershell failed").strip()[:300])
    return proc.stdout


def sapi_recognizers(runner: Optional[Runner] = None) -> List[Dict[str, str]]:
    run = runner or _ps
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "[System.Speech.Recognition.SpeechRecognitionEngine]::InstalledRecognizers() |"
        " ForEach-Object { Write-Output ($_.Culture.Name + '|' + $_.Id) }"
    )
    out = run(script, 60)
    found = []
    for line in out.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        culture, ident = (line.split("|") + ["", ""])[:2]
        found.append({"language": culture, "id": ident})
    return found


def _wav_from_raw(pcm: bytes, rate: int = SAMPLE_RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm)
    return buf.getvalue()


def _record(seconds: float) -> bytes:
    import sounddevice as sd  # noqa: F401 - the real dependency of this backend
    frames = max(1, int(seconds * SAMPLE_RATE))
    recording = sd.rec(frames, samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    return _wav_from_raw(recording.tobytes())


def engines(runner: Optional[Runner] = None) -> Dict[str, Any]:
    """What can actually hear the operator right now."""
    info: Dict[str, Any] = {"default_seconds": DEFAULT_SECONDS}
    try:
        recs = sapi_recognizers(runner)
        info["sapi"] = {"available": bool(recs), "recognizers": recs}
    except Exception as exc:  # noqa: BLE001 - a missing OS recogniser is reported as unavailable
        info["sapi"] = {"available": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        inputs = [d for d in devices if int(d.get("max_input_channels", 0)) > 0]
        device = (sd.query_devices(kind="input") or {}).get("name") if inputs else None
        info["whisper"] = {"available": bool(inputs), "inputs": len(inputs),
                           "device": device}
    except Exception as exc:  # noqa: BLE001 - no microphone backend is reported, not invented
        info["whisper"] = {"available": False,
                           "error": f"{type(exc).__name__}: {exc}"[:200],
                           "hint": "pip install sounddevice to add the whisper backend"}
    try:
        import local_transcribe as lt
        info["transcription"] = lt.engines()
    except Exception as exc:  # noqa: BLE001 - the transcription engine is optional; its absence is reported
        info["transcription"] = {"available": False,
                                 "error": f"{type(exc).__name__}: {exc}"[:200]}
    info["preferred"] = ("whisper" if (info["whisper"].get("available")
                                       and info["transcription"].get("available"))
                         else ("sapi" if info["sapi"].get("available") else None))
    info["network"] = "none"
    return info


def listen_once(seconds: Optional[float] = None, *, runner: Optional[Runner] = None,
                recorder: Optional[Recorder] = None,
                engine: str = "auto") -> Dict[str, Any]:
    """Record one utterance and return its text.

    `engine` is 'auto' (whisper when both a mic and the models are present, else
    SAPI), 'whisper' or 'sapi'. A failure carries the reason; text is never faked.
    """
    secs = float(seconds or DEFAULT_SECONDS)
    t0 = time.time()
    info = engines(runner)
    choice = engine
    if engine == "auto":
        choice = info.get("preferred") or "sapi"
    if choice == "whisper":
        try:
            wav = (recorder or _record)(secs)
        except Exception as exc:  # noqa: BLE001 - report the real microphone reason
            return {"ok": False, "engine": "whisper", "seconds": round(time.time() - t0, 2),
                    "error": f"microphone: {type(exc).__name__}: {exc}"[:300]}
        try:
            import local_transcribe as lt
            out = lt.transcribe(wav, beam_size=1)
        except Exception as exc:  # noqa: BLE001 - a dead microphone is returned as a listen failure
            return {"ok": False, "engine": "whisper", "seconds": round(time.time() - t0, 2),
                    "error": f"transcription: {type(exc).__name__}: {exc}"[:300]}
        text = (out.get("text") or "").strip()
        return {"ok": bool(text), "engine": "whisper", "text": text,
                "language": out.get("language"), "audio_seconds": out.get("duration"),
                "seconds": round(time.time() - t0, 2),
                "error": None if text else "no speech detected"}
    if not info["sapi"].get("available"):
        return {"ok": False, "engine": "sapi", "seconds": round(time.time() - t0, 2),
                "error": info["sapi"].get("error") or "no OS speech recogniser installed"}
    run = runner or _ps
    script = (
        "Add-Type -AssemblyName System.Speech;"
        "$r = New-Object System.Speech.Recognition.SpeechRecognitionEngine;"
        "$r.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar));"
        "$r.SetInputToDefaultAudioDevice();"
        f"$res = $r.Recognize([TimeSpan]::FromSeconds({secs:g}));"
        "if ($res) { Write-Output ('OK|' + $res.Text + '|' + $res.Confidence) } "
        "else { Write-Output 'NOINPUT' };"
        "$r.Dispose()"
    )
    try:
        out = run(script, int(secs) + 30)
    except Exception as exc:  # noqa: BLE001 - a recogniser crash is returned as a listen failure
        return {"ok": False, "engine": "sapi", "seconds": round(time.time() - t0, 2),
                "error": f"recogniser: {type(exc).__name__}: {exc}"[:300]}
    line = (out or "").strip().splitlines()[-1] if (out or "").strip() else ""
    if line.startswith("OK|"):
        parts = line.split("|")
        text = parts[1].strip() if len(parts) > 1 else ""
        try:
            confidence = round(float(parts[2]), 3) if len(parts) > 2 else None
        except ValueError:  # noqa: BLE001 - an unparseable confidence is reported as None
            confidence = None
        return {"ok": bool(text), "engine": "sapi", "text": text,
                "confidence": confidence, "seconds": round(time.time() - t0, 2),
                "error": None if text else "no speech recognised"}
    return {"ok": False, "engine": "sapi", "seconds": round(time.time() - t0, 2),
            "error": "no speech detected in the window"}


def transcribe_file(path: str) -> Dict[str, Any]:
    """Transcribe an existing audio file with the local whisper lane."""
    with open(path, "rb") as fh:
        raw = fh.read()
    import local_transcribe as lt
    return lt.transcribe(raw)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Local ear (offline speech to text)")
    ap.add_argument("--engines", action="store_true")
    ap.add_argument("--listen", action="store_true")
    ap.add_argument("--seconds", type=float, default=None)
    ap.add_argument("--engine", choices=["auto", "whisper", "sapi"], default="auto")
    ap.add_argument("--file", default=None)
    args = ap.parse_args(argv)

    if args.engines:
        print(json.dumps(engines(), indent=2))
        return 0
    if args.file:
        print(json.dumps(transcribe_file(args.file), indent=2))
        return 0
    if args.listen:
        out = listen_once(args.seconds, engine=args.engine)
        print(json.dumps(out, indent=2))
        return 0 if out.get("ok") else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
