"""Local screen lane — see the operator's desktop without a cloud round-trip.

This is the local counterpart of a hosted "screen awareness" product. Three
primitives, no provider key, no outbound request:

  capture()   the current desktop as PNG bytes (PIL ImageGrab, all monitors)
  ocr()       on-screen text as lines + one blob (RapidOCR, CPU)
  describe()  a plain-language look at the frame (qwen2.5vl via local Ollama)

Why OCR *and* a vision model: a 7B vision model cannot reliably read 10 px UI
text, but it can say "a code editor with a stack trace panel is open". OCR gets
the words, the model gets the scene. Sending the same frame through both is what
makes later questions ("what was that error an hour ago?") answerable.

Privacy rules, because this lane reads everything on the screen:

1. **Loopback only.** Every Ollama call is checked against a loopback host
   before it is made. A non-local OLLAMA_HOST raises; it never silently ships a
   screenshot to somebody's server.
2. **Redaction by default.** API keys, bearer tokens, e-mails, `password: ...`
   and card-like digit runs are masked before the text is stored or sent to a
   model. `redact=False` is available, and never the default.
3. **No frames on disk by default.** Only text is stored. A caller that wants a
   thumbnail has to ask for one.
4. **Secure desktop is reported, not guessed.** A lock/UAC screen produces a
   near-black frame; the result says `possibly_secure_desktop=True` instead of
   pretending it read the desktop.

    python Northstar_backend/local_screen.py --engines
    python Northstar_backend/local_screen.py --grab --out shot.png
    python Northstar_backend/local_screen.py --look
    python Northstar_backend/local_screen.py --ask "what is on my screen?"
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import ipaddress
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

DEFAULT_VISION_MODEL = os.environ.get("LOCAL_SCREEN_VISION_MODEL", "qwen2.5vl:7b")
DEFAULT_TEXT_MODEL = os.environ.get("LOCAL_SCREEN_MODEL", "qwen3:8b")
#: Long side of the frame handed to OCR. 2560 px costs ~6 s; 1600 px ~3 s.
DEFAULT_MAX_SIDE = int(os.environ.get("LOCAL_SCREEN_MAX_SIDE", "1600"))
#: Long side of the frame handed to the vision model (vision tokens are quadratic).
DEFAULT_VISION_MAX_SIDE = int(os.environ.get("LOCAL_SCREEN_VISION_MAX_SIDE", "1024"))
#: Cap on stored/extracted text, so one giant document cannot bloat the memory DB.
MAX_TEXT = int(os.environ.get("LOCAL_SCREEN_MAX_TEXT", "20000"))
#: GPU headroom for the vision model mirrors local_vision's rule.
GPU_HEADROOM_MB = int(os.environ.get("LOCAL_SCREEN_GPU_HEADROOM_MB", "7000"))

Poster = Callable[[str, Dict[str, Any], float], Dict[str, Any]]
Grabber = Callable[[], Any]
Ocr = Callable[[bytes], Any]


def normalise_host(value: Optional[str]) -> str:
    """Ollama's env var is a bare `host:port`; urllib needs a scheme."""
    host = (value or "").strip().rstrip("/")
    if not host:
        return "http://127.0.0.1:11434"
    if "://" not in host:
        host = f"http://{host}"
    if host.startswith("http://0.0.0.0"):
        host = host.replace("0.0.0.0", "127.0.0.1", 1)
    return host


OLLAMA_HOST = normalise_host(os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"))


class CloudRefused(RuntimeError):
    """Raised when something tries to send screen data off this machine."""


def assert_loopback(url: str) -> str:
    """Refuse any non-loopback destination. The whole point of this lane."""
    host = urllib.parse.urlparse(url).hostname or ""
    if host == "localhost":
        return url
    try:
        addr = ipaddress.ip_address(host)
    except ValueError as exc:
        raise CloudRefused(
            f"refusing non-loopback host {host!r}: this lane never leaves the machine"
        ) from exc
    if not addr.is_loopback:
        raise CloudRefused(
            f"refusing non-loopback host {host!r}: this lane never leaves the machine"
        )
    return url


def _http_post(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    assert_loopback(url)
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace") or "{}")


def vram_free_mb() -> Optional[int]:
    """Free VRAM in MiB, or None when it cannot be read (never guessed)."""
    import subprocess
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0:
            return None
        return int(out.stdout.strip().splitlines()[0])
    except Exception:  # noqa: BLE001 - unknown VRAM means CPU, never a guess
        return None


def choose_mode(free_mb: Optional[int], allow_gpu: Optional[bool] = None) -> str:
    """'gpu' or 'cpu'. Unknown VRAM means cpu - the safe direction."""
    if allow_gpu is False:
        return "cpu"
    if allow_gpu is True:
        return "gpu"
    if free_mb is None:
        return "cpu"
    return "gpu" if free_mb >= GPU_HEADROOM_MB else "cpu"


# ── capture ──────────────────────────────────────────────────────────────────

def _resize_png(image: Any, max_side: int) -> Tuple[bytes, int, int]:
    from PIL import Image
    im = image.convert("RGB")
    w, h = im.size
    scale = max_side / float(max(w, h)) if max(w, h) else 1.0
    if scale < 1.0:
        im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="PNG", optimize=True)
    return buf.getvalue(), im.size[0], im.size[1]


def _looks_blank(png: bytes) -> bool:
    """True for a near-black frame: a locked screen, not a desktop."""
    try:
        from PIL import Image
        with Image.open(io.BytesIO(png)) as im:
            small = im.convert("L").resize((64, 40))
            data = small.tobytes()
        mean = sum(data) / max(1, len(data))
        return mean < 6.0
    except Exception:  # noqa: BLE001 - unreadable frame is reported, not assumed blank
        return False


def active_window() -> Dict[str, Any]:
    """Foreground window title + process, via Win32. Empty on any failure."""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return {"title": "", "process": "", "pid": None}
        length = user32.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        name = ""
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid.value)  # QUERY_LIMITED_INFORMATION
        if handle:
            try:
                pbuf = ctypes.create_unicode_buffer(1024)
                size = wintypes.DWORD(1024)
                if kernel32.QueryFullProcessImageNameW(handle, 0, pbuf,
                                                      ctypes.byref(size)):
                    name = os.path.basename(pbuf.value)
            finally:
                kernel32.CloseHandle(handle)
        return {"title": (title.value or "")[:300], "process": name, "pid": int(pid.value)}
    except Exception:  # noqa: BLE001 - a title is context, never a hard requirement
        return {"title": "", "process": "", "pid": None}


def _foreground_rect() -> Optional[Tuple[int, int, int, int]]:
    """Screen rect of the foreground window, in virtual-screen coordinates."""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        rect = wintypes.RECT()
        # DWM extended frame bounds include the shadow-less real edges; plain
        # GetWindowRect is the fallback when DWM is unavailable.
        ok = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect)) == 0
        if not ok:
            ok = bool(user32.GetWindowRect(hwnd, ctypes.byref(rect)))
        if not ok:
            return None
        return (int(rect.left), int(rect.top), int(rect.right), int(rect.bottom))
    except Exception:  # noqa: BLE001 - a rect is a nicety; full screen is the fallback
        return None


def _virtual_screen() -> Tuple[int, int, int, int]:
    """(x, y, width, height) of the whole virtual desktop."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        return (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77),
                user32.GetSystemMetrics(78), user32.GetSystemMetrics(79))
    except Exception:  # noqa: BLE001 - unknown VRAM means CPU, never a guess
        return (0, 0, 0, 0)


def _crop_to_window(image: Any, scope: str) -> Tuple[Any, Dict[str, Any]]:
    """Return the region to read. `active` is the crisp default on a multi-monitor box."""
    native = tuple(getattr(image, "size", (0, 0)))
    info: Dict[str, Any] = {"scope": scope, "cropped": False}
    if scope != "active":
        return image, info
    rect = _foreground_rect()
    if not rect:
        info["fallback"] = "no foreground rect"
        return image, info
    vx, vy, vw, vh = _virtual_screen()
    img_x = rect[0] - vx if vw else rect[0]
    img_y = rect[1] - vy if vh else rect[1]
    left, top = max(0, img_x), max(0, img_y)
    right = min(native[0], img_x + (rect[2] - rect[0]))
    bottom = min(native[1], img_y + (rect[3] - rect[1]))
    if right - left < 200 or bottom - top < 120:
        info["fallback"] = "foreground window too small"
        return image, info
    cropped = image.crop((left, top, right, bottom))
    info.update({"cropped": True, "region": {"left": left, "top": top,
                                             "width": right - left, "height": bottom - top}})
    return cropped, info


def capture(*, max_side: Optional[int] = None, grabber: Optional[Grabber] = None,
            include_window: bool = True, scope: str = "active") -> Dict[str, Any]:
    """Grab the screen as PNG bytes, downscaled for OCR.

    `scope` is 'active' (the foreground window's monitor region - the crisp
    default on a multi-monitor box), 'primary' or 'all'. It falls back to the
    whole desktop when a window rect cannot be read, and says so.

    Returns timestamp, native + stored size, sha1 of the stored frame, the active
    window, and `possibly_secure_desktop`. Nothing is written to disk here.
    """
    t0 = time.time()
    grab = grabber
    if grab is None:
        from PIL import ImageGrab
        grab = lambda: ImageGrab.grab(all_screens=True)  # noqa: E731 - lazy, no import cost when faked
    try:
        image = grab()
    except Exception as exc:  # noqa: BLE001 - report the real reason
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300],
                "seconds": round(time.time() - t0, 2)}
    natural = tuple(getattr(image, "size", (0, 0)))
    region, crop_info = _crop_to_window(image, scope)
    side = int(max_side or DEFAULT_MAX_SIDE)
    png, width, height = _resize_png(region, side)
    out: Dict[str, Any] = {
        "ok": True,
        "png": png,
        "bytes": len(png),
        "width": width,
        "height": height,
        "native": {"width": int(natural[0]), "height": int(natural[1])},
        "scope": crop_info,
        "sha1": hashlib.sha1(png).hexdigest(),
        "captured_at": time.time(),
        "max_side": side,
        "possibly_secure_desktop": _looks_blank(png),
        "seconds": round(time.time() - t0, 2),
    }
    if include_window:
        out["window"] = active_window()
    return out


# ── OCR ──────────────────────────────────────────────────────────────────────

_OCR_ENGINE: Any = None


def _ocr_engine() -> Any:
    global _OCR_ENGINE
    if _OCR_ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


def ocr(png: bytes, *, engine: Optional[Ocr] = None,
        max_lines: int = 400) -> Dict[str, Any]:
    """Read the on-screen text. CPU only, and the engine is cached per process."""
    if not png:
        raise ValueError("image is required")
    t0 = time.time()
    try:
        reader = engine or _ocr_engine()
        result, _elapsed = reader(png)
    except Exception as exc:  # noqa: BLE001 - an OCR failure is reported with its reason
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300],
                "seconds": round(time.time() - t0, 2), "text": "", "lines": []}
    lines: List[Dict[str, Any]] = []
    for item in (result or [])[:max_lines]:
        try:
            box, text, score = item[0], str(item[1]), float(item[2])
        except (IndexError, TypeError, ValueError):  # noqa: BLE001 - a malformed OCR item is skipped, never guessed
            continue
        text = text.strip()
        if not text:
            continue
        ys = [pt[1] for pt in box] if box else []
        xs = [pt[0] for pt in box] if box else []
        lines.append({
            "text": text,
            "score": round(score, 3),
            "y": int(min(ys)) if ys else None,
            "x": int(min(xs)) if xs else None,
        })
    lines.sort(key=lambda ln: ((ln.get("y") if ln.get("y") is not None else 10 ** 6),
                               (ln.get("x") if ln.get("x") is not None else 0)))
    text = "\n".join(ln["text"] for ln in lines)
    return {"ok": True, "text": text[:MAX_TEXT], "lines": lines,
            "line_count": len(lines), "seconds": round(time.time() - t0, 2)}


# ── redaction ────────────────────────────────────────────────────────────────

_REDACTIONS: Tuple[Tuple[re.Pattern, str], ...] = (
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "«email»"),
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/-]{12,}=*"), r"\1 «token»"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), "«api-key»"),
    (re.compile(r"\b(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{16,}\b"), "«api-key»"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "«aws-key»"),
    (re.compile(r"\bnsk_[A-Za-z0-9]{12,}\b"), "«api-key»"),
    (re.compile(r"(?i)\b(password|passwd|pwd|secret|api[ _-]?key|token)\b\s*[:=]\s*\S+"),
     r"\1: «redacted»"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "«number»"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
     "«jwt»"),
)


def redact(text: str) -> Dict[str, Any]:
    """Mask secrets before text is stored or sent to a model.

    Deliberately conservative: it masks patterns that are almost always secrets
    and leaves ordinary prose, prices, code and short ids alone. It does not
    claim to be complete - `redactions` says how many substitutions it made.
    """
    out = text or ""
    counts: Dict[str, int] = {}
    for pattern, replacement in _REDACTIONS:
        out, n = pattern.subn(replacement, out)
        if n:
            counts[replacement.strip("«»").replace("\\1 ", "")] = n
    return {"text": out, "redactions": counts,
            "total": sum(counts.values())}


# ── vision ───────────────────────────────────────────────────────────────────

_VISION_PROMPT = (
    "You are looking at a screenshot of the operator's own computer. Describe what "
    "is on screen in 2-4 short sentences: which application is in front, what the "
    "main panel shows, and anything that looks like an error, a dialog or an "
    "unfinished task. Do not transcribe small text; say what the screen is for. "
    "If the image is black or unreadable, say exactly that."
)


def describe(png: bytes, question: Optional[str] = None, *,
             model: Optional[str] = None, allow_gpu: Optional[bool] = None,
             max_side: Optional[int] = None, timeout: float = 600.0,
             poster: Optional[Poster] = None,
             vram_reader: Optional[Callable[[], Optional[int]]] = None) -> Dict[str, Any]:
    """Ask the local vision model what is on screen.

    `keep_alive: 0` so the 6 GB model is not left parked in VRAM between looks.
    A failure returns `ok: False` with the real reason, never an invented scene.
    """
    if not png:
        raise ValueError("image is required")
    post = poster or _http_post
    read_vram = vram_reader or vram_free_mb
    mdl = model or DEFAULT_VISION_MODEL
    before = read_vram()
    mode = choose_mode(before, allow_gpu)
    frame, width, height = _resize_png(
        _open_image(png), int(max_side or DEFAULT_VISION_MAX_SIDE))
    prompt = _VISION_PROMPT
    if question:
        prompt = f"{prompt}\n\nOperator question: {question.strip()[:400]}"

    payload: Dict[str, Any] = {
        "model": mdl,
        "prompt": prompt,
        "images": [base64.b64encode(frame).decode("ascii")],
        "stream": False,
        "keep_alive": 0,
        "options": {"temperature": 0.2, "num_predict": 260},
    }
    if mode == "cpu":
        payload["options"]["num_gpu"] = 0

    t0 = time.time()
    try:
        resp = post(f"{OLLAMA_HOST}/api/generate", payload, timeout)
    except CloudRefused:  # noqa: BLE001 - a refused host must surface, never become a model error
        raise
    except Exception as exc:  # noqa: BLE001 - report, never fabricate
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300],
                "model": mdl, "mode": mode, "seconds": round(time.time() - t0, 1)}
    return {
        "ok": True,
        "answer": str(resp.get("response", "")).strip()[:1200],
        "model": mdl,
        "mode": mode,
        "width": width,
        "height": height,
        "seconds": round(time.time() - t0, 1),
        "vram_free_mb_before": before,
        "vram_free_mb_after": read_vram(),
    }


def _open_image(png: bytes) -> Any:
    from PIL import Image
    return Image.open(io.BytesIO(png))


# ── text model ───────────────────────────────────────────────────────────────

def ask_screen(question: str, *, ocr_text: str, scene: str = "",
               window: Optional[Dict[str, Any]] = None,
               model: Optional[str] = None, timeout: float = 300.0,
               poster: Optional[Poster] = None,
               allow_gpu: Optional[bool] = None) -> Dict[str, Any]:
    """Answer a question from the captured evidence, on the local text model.

    The model is told what it is looking at and that it must not invent detail:
    if the OCR text and the scene description do not answer the question, it says
    so. It has no tools and no network.
    """
    if not (question or "").strip():
        raise ValueError("question is required")
    post = poster or _http_post
    mdl = model or DEFAULT_TEXT_MODEL
    win = window or {}
    context = (
        f"Active window: {win.get('process') or 'unknown'} - "
        f"{win.get('title') or 'untitled'}\n"
        f"Scene description (from a local vision model): {scene.strip() or '(none)'}\n"
        f"On-screen text (OCR, may be partial and out of order):\n"
        f"{ocr_text.strip()[:6000] or '(no text detected)'}"
    )
    system = (
        "You are the operator's local screen companion. You answer questions about "
        "what is on their screen right now, using ONLY the evidence provided. The "
        "window title and OCR text are a trustworthy but incomplete picture; the "
        "scene description is a vision model's summary and may be wrong. If the "
        "evidence does not answer the question, say what you can see and what is "
        "missing. Never invent values, never claim to have read something that is "
        "not in the evidence, and keep the answer under 120 words. Plain prose, no "
        "markdown headings."
    )
    payload: Dict[str, Any] = {
        "model": mdl,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"EVIDENCE\n{context}\n\nQUESTION\n{question.strip()[:500]}"},
        ],
        "stream": False,
        "keep_alive": "5m",
        # qwen3 and friends think by default; a 48 s monologue is not a live
        # companion. The answer is grounded in supplied evidence, so thinking off.
        "think": False,
        "options": {"temperature": 0.3, "num_predict": 500},
    }
    if allow_gpu is False:
        payload["options"]["num_gpu"] = 0
    t0 = time.time()
    try:
        resp = post(f"{OLLAMA_HOST}/api/chat", payload, timeout)
    except CloudRefused:  # noqa: BLE001 - a refused host must surface, never become a model error
        raise
    except Exception as exc:  # noqa: BLE001 - a refused host is re-raised above; other model failures are returned
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300],
                "model": mdl, "seconds": round(time.time() - t0, 1)}
    message = resp.get("message") or {}
    return {"ok": True, "answer": str(message.get("content", "")).strip()[:1200],
            "model": mdl, "seconds": round(time.time() - t0, 1),
            "grounded_on": {"ocr_chars": len(ocr_text or ""),
                            "scene_chars": len(scene or ""),
                            "window": win.get("process") or None}}


# ── status ───────────────────────────────────────────────────────────────────

def lane_gated() -> bool:
    """True only when the model lane points at this machine.

    This is a real gate, not decoration: a non-loopback OLLAMA_HOST would mean
    screenshots leave the box, so the lane reports itself ungated and refuses.
    """
    try:
        assert_loopback(OLLAMA_HOST)
        return True
    except CloudRefused:  # noqa: BLE001 - ungated is the answer here, not an error
        return False


def engines() -> Dict[str, Any]:
    """What this lane can do right now, without pretending."""
    gated = lane_gated()
    info: Dict[str, Any] = {
        "loopback_only": True,
        "gated": gated,
        "ollama_host": OLLAMA_HOST,
        "text_model": DEFAULT_TEXT_MODEL,
        "vision_model": DEFAULT_VISION_MODEL,
        "max_side": DEFAULT_MAX_SIDE,
        "vision_max_side": DEFAULT_VISION_MAX_SIDE,
        "scope": os.environ.get("LOCAL_SCREEN_SCOPE", "active"),
    }
    if not gated:
        info["error"] = "OLLAMA_HOST is not loopback: this lane will not send screen data off-box"
        return info
    try:
        from PIL import ImageGrab  # noqa: F401
        info["capture"] = {"available": True, "backend": "PIL.ImageGrab",
                           "all_screens": True}
    except Exception as exc:  # noqa: BLE001 - an unreadable image is reported, never assumed blank
        info["capture"] = {"available": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
    try:
        import rapidocr_onnxruntime  # noqa: F401
        info["ocr"] = {"available": True, "backend": "rapidocr", "device": "cpu"}
    except Exception as exc:  # noqa: BLE001 - the OCR dependency is optional; its absence is reported
        info["ocr"] = {"available": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
    free = vram_free_mb()
    info["vram_free_mb"] = free
    info["vision_mode"] = choose_mode(free, None)
    try:
        assert_loopback(OLLAMA_HOST)
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=4) as resp:
            names = [m.get("name", "") for m in
                     json.loads(resp.read().decode("utf-8", "replace")).get("models", [])]
        info["ollama"] = {"available": True, "models": len(names)}
        info["text_model_installed"] = any(
            n == DEFAULT_TEXT_MODEL or n.split(":")[0] == DEFAULT_TEXT_MODEL.split(":")[0]
            for n in names)
        info["vision_model_installed"] = any(n.startswith("qwen2.5vl") or
                                             n == DEFAULT_VISION_MODEL for n in names)
    except Exception as exc:  # noqa: BLE001 - Ollama being down is reported as unavailable
        info["ollama"] = {"available": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
        info["text_model_installed"] = False
        info["vision_model_installed"] = False
    try:
        win = active_window()
        info["active_window"] = win
    except Exception:  # noqa: BLE001 - a missing window title is context, never a hard requirement
        info["active_window"] = {"title": "", "process": ""}
    return info


def look(*, question: Optional[str] = None, vision: str = "auto",
         max_side: Optional[int] = None, poster: Optional[Poster] = None,
         grabber: Optional[Grabber] = None, ocr_engine: Optional[Ocr] = None,
         vram_reader: Optional[Callable[[], Optional[int]]] = None,
         keep_png: bool = False, scope: str = "active") -> Dict[str, Any]:
    """One full pass: capture -> OCR -> optional scene description -> redact.

    `vision` is 'auto' (describe when the question is visual or OCR is thin),
    'always' or 'never'. The frame is not written to disk; `keep_png` hands the
    bytes back to the caller so it can decide (the thumbnail path does).
    """
    frame = capture(max_side=max_side, grabber=grabber, scope=scope)
    if not frame.get("ok"):
        return {"ok": False, "error": frame.get("error"), "stage": "capture"}
    png = frame.pop("png")
    text = ocr(png, engine=ocr_engine)
    safe = redact(text.get("text", ""))
    blank = bool(frame.get("possibly_secure_desktop"))
    want_vision = not blank and (vision == "always" or (
        vision == "auto" and (
            len(safe["text"].strip()) < 40 or _looks_visual(question or ""))))
    scene = ""
    vision_out: Dict[str, Any] = {"skipped": True,
                                  "reason": "blank frame" if blank else "vision=never"}
    if want_vision:
        vision_out = describe(png, question, poster=poster, vram_reader=vram_reader)
        vision_out["skipped"] = False
        scene = vision_out.get("answer", "") if vision_out.get("ok") else ""
    out: Dict[str, Any] = {
        "ok": bool(text.get("ok")),
        "blank": blank,
        "frame": frame,
        "ocr": {"ok": text.get("ok"), "error": text.get("error"),
                "line_count": text.get("line_count", 0), "seconds": text.get("seconds"),
                "text": safe["text"], "redactions": safe["redactions"],
                "redacted_total": safe["total"]},
        "vision": vision_out,
        "scene": scene,
        "note": ("Text is redacted before it leaves this function. "
                 "`vision.skipped` says why a look was not taken."),
    }
    if keep_png:
        out["png"] = png
    return out


_VISUAL_WORDS = re.compile(
    r"(?i)\b(see|looks?|look at|colour|color|image|picture|chart|graph|layout|"
    r"design|logo|button|icon|dialog|popup|screenshot|render|video|draw)\b")


def _looks_visual(question: str) -> bool:
    return bool(_VISUAL_WORDS.search(question or ""))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Local screen lane (capture + OCR + vision)")
    ap.add_argument("--engines", action="store_true")
    ap.add_argument("--grab", action="store_true", help="capture and (optionally) write a PNG")
    ap.add_argument("--out", default=None)
    ap.add_argument("--look", action="store_true", help="capture + OCR + scene description")
    ap.add_argument("--ask", default=None, help="ask a question about the current screen")
    ap.add_argument("--vision", choices=["auto", "always", "never"], default="auto")
    ap.add_argument("--scope", choices=["active", "primary", "all"], default="active")
    ap.add_argument("--model", default=None)
    args = ap.parse_args(argv)

    if args.engines:
        print(json.dumps(engines(), indent=2))
        return 0
    if args.grab:
        frame = capture(scope=args.scope)
        png = frame.get("png", b"")
        if args.out and png:
            with open(args.out, "wb") as fh:
                fh.write(png)
        print(json.dumps({k: v for k, v in frame.items() if k != "png"}, indent=2))
        return 0 if frame.get("ok") else 1
    if args.look:
        result = look(vision=args.vision, scope=args.scope)
        print(json.dumps(result, indent=2, ensure_ascii=False)[:6000])
        return 0 if result.get("ok") else 1
    if args.ask:
        result = look(question=args.ask, vision=args.vision, scope=args.scope)
        if not result.get("ok"):
            print(json.dumps(result, indent=2))
            return 1
        answer = ask_screen(args.ask, ocr_text=result["ocr"]["text"],
                            scene=result.get("scene", ""),
                            window=result["frame"].get("window"), model=args.model)
        print(json.dumps({"answer": answer, "look_seconds": result["frame"].get("seconds"),
                          "ocr_seconds": result["ocr"].get("seconds")}, indent=2))
        return 0 if answer.get("ok") else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
