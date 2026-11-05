"""Local screen companion — watch the desktop, remember it, answer out loud.

The whole loop stays on this machine:

    screen  ->  OCR + optional vision note  ->  local SQLite memory
                        |                              |
                        +--> local text model <--------+
                                   |
                              local speech (piper/SAPI)

Three ways to use it:

  * `--once`     sample the screen once into memory (the watcher's unit of work)
  * `--watch`    sample every N seconds in the background; dedupes idle frames
  * `--live`     listen on the mic, answer the question out loud (hands-free)

Safety rails, all deliberate:

* **Nothing leaves the box.** Every model call goes through `local_screen`,
  which refuses a non-loopback host. Audio is written locally and played from a
  local path; there is no upload path in this module.
* **One watcher, one owner.** A process-wide singleton; start twice returns the
  existing one rather than spawning a second capture thread.
* **Stop switches win.** The repo's `STOP` file pauses capture, and
  `stop()`/`pause()` are honoured at the top of every tick.
* **Bounded failure.** A capture error is logged and the next tick continues,
  but five consecutive failures stop the watcher with the reason recorded. It
  never retries forever in silence.
* **Recording is explicit.** `--live` is the only thing that opens the mic, and
  it is never started implicitly by the watcher.

    python Northstar_backend/local_screen_agent.py --status
    python Northstar_backend/local_screen_agent.py --once
    python Northstar_backend/local_screen_agent.py --ask "what is this error?"
    python Northstar_backend/local_screen_agent.py --ask "summarise my screen" --speak
    python Northstar_backend/local_screen_agent.py --watch --interval 5
    python Northstar_backend/local_screen_agent.py --live --seconds 5
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import local_screen as screen
import local_screen_memory as memory

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("LOCAL_SCREEN_DIR", BASE_DIR / "data" / "local_screen"))
AUDIO_DIR = DATA_DIR / "audio"
THUMB_DIR = DATA_DIR / "thumbs"
STOP_FILE = BASE_DIR.parent / "STOP"

#: Consecutive capture failures that stop the watcher. Never an infinite retry.
MAX_CONSECUTIVE_ERRORS = int(os.environ.get("LOCAL_SCREEN_MAX_ERRORS", "5"))
#: Keep a JPEG thumbnail per distinct frame? Off by default: text is the memory.
KEEP_THUMBS = os.environ.get("LOCAL_SCREEN_THUMBS", "0") == "1"
#: What to read: the foreground window's region (crisp), the primary screen, or all.
DEFAULT_SCOPE = os.environ.get("LOCAL_SCREEN_SCOPE", "active")


def _thumb_path(sha1: str) -> str:
    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    return str(THUMB_DIR / f"{sha1[:24]}.jpg")


def _write_thumb(png: bytes, sha1: str) -> Optional[str]:
    try:
        from PIL import Image
        import io
        with Image.open(io.BytesIO(png)) as im:
            im = im.convert("RGB")
            im.thumbnail((640, 640))
            path = _thumb_path(sha1)
            im.save(path, format="JPEG", quality=70)
        return path
    except Exception:  # noqa: BLE001 - a thumbnail is a convenience, not the record
        return None


def sample(*, vision: str = "auto", question: Optional[str] = None,
           store: bool = True, thumbs: Optional[bool] = None,
           scope: Optional[str] = None) -> Dict[str, Any]:
    """One watch tick: capture, OCR, optional scene note, store the text."""
    keep = KEEP_THUMBS if thumbs is None else bool(thumbs)
    seen = screen.look(question=question, vision=vision, keep_png=keep,
                       scope=scope or DEFAULT_SCOPE)
    if not seen.get("ok"):
        return {"ok": False, "error": seen.get("error"), "stage": "look", "seen": seen}
    frame = seen["frame"]
    if seen.get("blank"):
        # A locked screen is not a read: storing a black frame teaches nothing
        # and asking a model about it invites an invented answer.
        return {"ok": True, "blank": True, "stored": False, "frame_id": None,
                "at": time.strftime("%Y-%m-%d %H:%M:%S",
                                    time.localtime(frame.get("captured_at") or time.time())),
                "window": frame.get("window"), "line_count": 0,
                "possibly_secure_desktop": True,
                "note": "screen appears locked or blank; nothing stored"}
    thumb = None
    png = seen.pop("png", None)
    if keep and png:
        thumb = _write_thumb(png, frame.get("sha1") or "")
    record = {
        "captured_at": frame.get("captured_at"),
        "sha1": frame.get("sha1") or "",
        "text": seen["ocr"].get("text", ""),
        "process": (frame.get("window") or {}).get("process", ""),
        "title": (frame.get("window") or {}).get("title", ""),
        "line_count": seen["ocr"].get("line_count", 0),
        "ocr_seconds": seen["ocr"].get("seconds"),
        "scene": seen.get("scene", ""),
        "thumb": thumb,
    }
    saved = memory.record(**record) if store else {"id": None, "duplicate": False}
    return {
        "ok": True,
        "frame_id": saved.get("id"),
        "duplicate": bool(saved.get("duplicate")),
        "seen_count": saved.get("seen_count"),
        "at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(frame.get("captured_at") or time.time())),
        "window": frame.get("window"),
        "line_count": seen["ocr"].get("line_count", 0),
        "ocr_seconds": seen["ocr"].get("seconds"),
        "vision": {"skipped": seen["vision"].get("skipped", False),
                   "seconds": seen["vision"].get("seconds"),
                   "ok": seen["vision"].get("ok")},
        "possibly_secure_desktop": frame.get("possibly_secure_desktop"),
        "preview": (seen["ocr"].get("text") or "")[:280],
        "redactions": seen["ocr"].get("redactions") or {},
    }


def say(text: str, *, voice: Optional[str] = None) -> Dict[str, Any]:
    """Speak `text` with the local voice engine; return the WAV path."""
    import local_voice
    text = (text or "").strip()
    if not text:
        raise ValueError("text is required")
    audio = local_voice.synthesize(text, voice=voice)
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    name = f"say-{uuid.uuid4().hex[:12]}.wav"
    path = AUDIO_DIR / name
    path.write_bytes(audio["bytes"])
    return {"ok": True, "file": str(path), "name": name, "bytes": len(audio["bytes"]),
            "engine": audio.get("engine"), "voice": audio.get("voice")}


def play(path: str) -> Dict[str, Any]:
    """Play a WAV through the default output device (Windows `winsound`)."""
    try:
        import winsound
        winsound.PlaySound(str(path), winsound.SND_FILENAME)
        return {"ok": True, "played": True}
    except Exception as exc:  # noqa: BLE001 - a silent box is reported, not hidden
        return {"ok": False, "played": False,
                "error": f"{type(exc).__name__}: {exc}"[:200]}


def ask(question: str, *, speak: bool = False, voice: Optional[str] = None,
        vision: str = "auto", store: bool = True,
        scope: Optional[str] = None) -> Dict[str, Any]:
    """Answer a question about the current screen, optionally out loud."""
    question = (question or "").strip()
    if not question:
        raise ValueError("question is required")
    seen = screen.look(question=question, vision=vision, scope=scope or DEFAULT_SCOPE)
    if not seen.get("ok"):
        return {"ok": False, "error": seen.get("error"), "stage": "look"}
    frame = seen["frame"]
    if seen.get("blank"):
        return {"ok": False, "question": question, "stage": "blank",
                "error": ("screen appears locked or blank: no evidence to answer from"),
                "possibly_secure_desktop": True}
    answer = screen.ask_screen(question, ocr_text=seen["ocr"]["text"],
                               scene=seen.get("scene", ""),
                               window=frame.get("window"))
    result: Dict[str, Any] = {
        "ok": bool(answer.get("ok")),
        "question": question,
        "answer": answer.get("answer", ""),
        "error": answer.get("error"),
        "model": answer.get("model"),
        "seconds": answer.get("seconds"),
        "grounded_on": answer.get("grounded_on"),
        "at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(frame.get("captured_at") or time.time())),
        "window": frame.get("window"),
        "possibly_secure_desktop": frame.get("possibly_secure_desktop"),
        "vision_used": not seen["vision"].get("skipped", False),
    }
    if store:
        saved = memory.record(
            captured_at=frame.get("captured_at"), sha1=frame.get("sha1") or "",
            text=seen["ocr"].get("text", ""),
            process=(frame.get("window") or {}).get("process", ""),
            title=(frame.get("window") or {}).get("title", ""),
            line_count=seen["ocr"].get("line_count", 0),
            ocr_seconds=seen["ocr"].get("seconds"),
            scene=seen.get("scene", ""),
        )
        result["frame_id"] = saved.get("id")
    if speak and result["ok"] and result["answer"]:
        result["voice"] = say(result["answer"], voice=voice)
    return result


class Watcher:
    """A single background sampler. Idempotent start, bounded failures."""

    def __init__(self) -> None:
        # Reentrant: start() reads state() while holding the lock, and state()
        # takes the same lock. A plain Lock deadlocked the first real caller.
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._state: Dict[str, Any] = {
            "running": False, "paused": False, "interval_s": None,
            "samples": 0, "stored": 0, "duplicates": 0, "errors": 0,
            "consecutive_errors": 0, "last_error": None, "last_at": None,
            "last_frame_id": None, "last_window": None,
            "started_at": None, "stopped_at": None, "stop_reason": None,
            "vision": "auto", "scope": DEFAULT_SCOPE,
        }

    # -- state ---------------------------------------------------------------
    def state(self) -> Dict[str, Any]:
        with self._lock:
            data = dict(self._state)
        data["thread_alive"] = bool(self._thread and self._thread.is_alive())
        data["stop_file"] = STOP_FILE.exists()
        return data

    def _set(self, **kw: Any) -> None:
        with self._lock:
            self._state.update(kw)

    # -- lifecycle -----------------------------------------------------------
    def start(self, *, interval_s: float = 5.0, vision: str = "auto",
              scope: str = DEFAULT_SCOPE) -> Dict[str, Any]:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return {"started": False, "already_running": True, **self.state()}
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="local-screen-watcher",
                                            args=(float(interval_s), vision, scope),
                                            daemon=True)
            self._thread.start()
        return {"started": True, "already_running": False, **self.state()}

    def stop(self, reason: str = "operator") -> Dict[str, Any]:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=30)
        self._set(running=False, paused=False, stopped_at=time.time(), stop_reason=reason)
        return self.state()

    def pause(self) -> Dict[str, Any]:
        self._set(paused=True)
        return self.state()

    def resume(self) -> Dict[str, Any]:
        self._set(paused=False)
        return self.state()

    def _run(self, interval_s: float, vision: str, scope: str = DEFAULT_SCOPE) -> None:
        self._set(running=True, paused=False, interval_s=interval_s, vision=vision,
                  scope=scope,
                  started_at=time.time(), stopped_at=None, stop_reason=None,
                  samples=0, stored=0, duplicates=0, errors=0,
                  consecutive_errors=0, last_error=None)
        while not self._stop.is_set():
            if STOP_FILE.exists():
                self._set(paused=True, stop_reason="stop_file")
                self._stop.wait(interval_s)
                continue
            with self._lock:
                paused = self._state["paused"]
            if paused:
                self._stop.wait(interval_s)
                continue
            try:
                result = sample(vision=vision, scope=scope)
                if result.get("ok"):
                    with self._lock:
                        self._state["samples"] += 1
                        if result.get("duplicate"):
                            self._state["duplicates"] += 1
                        elif result.get("frame_id"):
                            self._state["stored"] += 1
                        self._state["last_at"] = time.time()
                        self._state["last_frame_id"] = result.get("frame_id")
                        self._state["last_window"] = result.get("window")
                        self._state["consecutive_errors"] = 0
                        self._state["last_error"] = None
                else:
                    raise RuntimeError(str(result.get("error") or "capture failed"))
            except Exception as exc:  # noqa: BLE001 - count it, then continue or stop
                with self._lock:
                    self._state["errors"] += 1
                    self._state["consecutive_errors"] += 1
                    self._state["last_error"] = f"{type(exc).__name__}: {exc}"[:300]
                    exhausted = self._state["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS
                if exhausted:
                    self._set(running=False, stop_reason=f"error_budget_exhausted ({MAX_CONSECUTIVE_ERRORS})")
                    return
            self._stop.wait(interval_s)
        self._set(running=False, stopped_at=time.time())

    # -- live voice ----------------------------------------------------------
    def listen(self, *, seconds: float = 6.0, speak: bool = True,
               voice: Optional[str] = None, vision: str = "auto",
               scope: Optional[str] = None) -> Dict[str, Any]:
        """One hands-free turn: hear, answer, speak."""
        import local_ear
        heard = local_ear.listen_once(seconds)
        if not heard.get("ok"):
            return {"ok": False, "stage": "listen", "listen": heard}
        question = (heard.get("text") or "").strip()
        lower = question.lower()
        if lower in {"stop listening", "stop the watcher", "pause watching", "stop watching"}:
            self.pause()
            reply = say("Paused.", voice=voice) if speak else None
            return {"ok": True, "stage": "command", "heard": question,
                    "action": "pause", "voice": reply}
        if lower in {"resume watching", "start watching", "resume"}:
            self.resume()
            reply = say("Resumed.", voice=voice) if speak else None
            return {"ok": True, "stage": "command", "heard": question,
                    "action": "resume", "voice": reply}
        out = ask(question, speak=speak, voice=voice, vision=vision, scope=scope)
        out["heard"] = question
        out["listen"] = heard
        return out


WATCHER = Watcher()


def status() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "watcher": WATCHER.state(),
        "memory": memory.stats(),
        "screen": screen.engines(),
    }
    try:
        import local_voice
        info["voice"] = local_voice.engines()
    except Exception as exc:  # noqa: BLE001 - report, never fake a voice
        info["voice"] = {"preferred": None, "error": f"{type(exc).__name__}: {exc}"[:200]}
    try:
        import local_ear
        info["ear"] = local_ear.engines()
    except Exception as exc:  # noqa: BLE001 - a failed tick is counted and retried within the error budget
        info["ear"] = {"preferred": None, "error": f"{type(exc).__name__}: {exc}"[:200]}
    info["fully_local"] = {
        "loopback_only": True,
        "audio_on_disk": str(AUDIO_DIR),
        "memory_db": memory.stats().get("db"),
        "network_calls": "none outside 127.0.0.1 Ollama",
    }
    return info


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Local screen companion")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--ask", default=None)
    ap.add_argument("--speak", action="store_true")
    ap.add_argument("--voice", default=None)
    ap.add_argument("--vision", choices=["auto", "always", "never"], default="auto")
    ap.add_argument("--scope", choices=["active", "primary", "all"], default=DEFAULT_SCOPE)
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--interval", type=float, default=5.0)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--no-speak", action="store_true")
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--search", default=None)
    ap.add_argument("--recent", type=int, default=None)
    ap.add_argument("--minutes", type=float, default=None)
    ap.add_argument("--say", default=None)
    args = ap.parse_args(argv)

    if args.status:
        print(json.dumps(status(), indent=2, ensure_ascii=False)[:8000])
        return 0
    if args.once:
        print(json.dumps(sample(vision=args.vision, scope=args.scope), indent=2, ensure_ascii=False))
        return 0
    if args.ask:
        out = ask(args.ask, speak=args.speak, voice=args.voice, vision=args.vision,
                 scope=args.scope)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        if out.get("voice") and out["voice"].get("ok"):
            print(f"voice: {out['voice']['file']}")
            play(out["voice"]["file"])
        return 0 if out.get("ok") else 1
    if args.say:
        out = say(args.say, voice=args.voice)
        print(json.dumps(out, indent=2))
        play(out["file"])
        return 0
    if args.search is not None:
        print(json.dumps(memory.search(args.search, since_minutes=args.minutes),
                         indent=2, ensure_ascii=False)[:8000])
        return 0
    if args.recent is not None:
        print(json.dumps(memory.recent(limit=args.recent, since_minutes=args.minutes),
                         indent=2, ensure_ascii=False)[:8000])
        return 0
    if args.live:
        WATCHER.start(interval_s=args.interval, vision=args.vision, scope=args.scope)
        print(json.dumps({"live": True, "seconds": args.seconds,
                          "watcher": WATCHER.state()}, indent=2))
        try:
            while True:
                out = WATCHER.listen(seconds=args.seconds, speak=not args.no_speak,
                                     voice=args.voice, vision=args.vision,
                                     scope=args.scope)
                print(json.dumps({k: out.get(k) for k in
                                  ("ok", "heard", "answer", "stage", "error", "action")},
                                 ensure_ascii=False), flush=True)
                if out.get("voice", {}).get("file"):
                    play(out["voice"]["file"])
        except KeyboardInterrupt:  # noqa: BLE001 - Ctrl+C is the documented way to stop the CLI
            print(json.dumps(WATCHER.stop("operator_interrupt"), indent=2))
            return 0
    if args.watch:
        WATCHER.start(interval_s=args.interval, vision=args.vision, scope=args.scope)
        print(json.dumps(WATCHER.state(), indent=2))
        try:
            while True:
                time.sleep(max(1.0, args.interval))
                print(json.dumps({k: v for k, v in WATCHER.state().items()
                                  if k in ("running", "samples", "stored", "duplicates",
                                           "errors", "last_error", "last_frame_id",
                                           "last_window", "paused")}), flush=True)
        except KeyboardInterrupt:  # noqa: BLE001 - Ctrl+C is the documented way to stop the CLI
            print(json.dumps(WATCHER.stop("operator_interrupt"), indent=2))
            return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
