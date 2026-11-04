"""Captions: word timing -> cues -> a burned-in layer inside the safe zones.

A caption is a placement decision before it is a text decision. TikTok's own UI
covers the bottom ~22% and the right ~18% of the frame; a subtitle centred at the
bottom of the canvas is under the controls and unreadable on a phone. This
module:

  * turns transcript segments (or word timings) into short cues,
  * renders each cue as an RGBA layer with a measured box,
  * burns the layers into the video with ffmpeg,
  * writes the `.srt` sidecar,
  * OCRs a frame from each cue and refuses the result when the words cannot be
    read or a box enters a declared safe-zone exclusion.

The box is computed here, not by libass, so the safe-zone check is against the
same numbers that drew it. No network, no provider call, no cost.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from PIL import Image, ImageDraw, ImageFont

import video_formats
import video_stitch

FONT_PATH = Path(__file__).resolve().parent / "assets" / "fonts" / "Anton.ttf"


class CaptionError(RuntimeError):
    """A caption that cannot be placed or verified, with the reason."""


# ── cue construction ────────────────────────────────────────────────────────

def _split_words(text: str) -> List[str]:
    return [w for w in re.split(r"\s+", str(text).strip()) if w]


def words_from_segments(segments: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Distribute a segment's duration across its words by character length.

    faster-whisper can return word timings, but the existing wrapper reads
    segment timings. Distributing proportionally is an approximation; the
    result says so (`timing: "segment"`) instead of pretending to be word-exact.
    """
    words: List[Dict[str, Any]] = []
    for seg in segments:
        text = str(seg.get("text") or "").strip()
        start, end = float(seg.get("start") or 0.0), float(seg.get("end") or 0.0)
        engine_words = seg.get("words") or []
        exact = [w for w in engine_words
                 if isinstance(w, dict) and str(w.get("word") or "").strip()
                 and w.get("start") is not None and w.get("end") is not None]
        if exact:
            # The engine measured these; do not redistribute them.
            for w in exact:
                words.append({"word": str(w["word"]).strip(),
                              "start": round(float(w["start"]), 3),
                              "end": round(float(w["end"]), 3),
                              "timing": "word"})
            if words:
                words[-1]["break_after"] = True
            continue
        tokens = _split_words(text)
        if not tokens or end <= start:
            continue
        weights = [len(t) + 1 for t in tokens]
        total = float(sum(weights))
        cursor = start
        for token, weight in zip(tokens, weights):
            span = max(0.05, (end - start) * weight / total)
            words.append({"word": token, "start": round(cursor, 3),
                          "end": round(min(end, cursor + span), 3),
                          "timing": "segment"})
            cursor += span
        if words:
            words[-1]["break_after"] = True
    return words


def cues_from_words(words: Sequence[Dict[str, Any]], *, max_chars: int = 32,
                    max_lines: int = 2, max_seconds: float = 3.2,
                    min_seconds: float = 0.6) -> List[Dict[str, Any]]:
    """Group word timings into readable cues, breaking at sentence punctuation."""
    cues: List[Dict[str, Any]] = []
    current: List[Dict[str, Any]] = []

    def flush() -> None:
        if not current:
            return
        text = " ".join(w["word"] for w in current).strip()
        start = float(current[0]["start"])
        end = max(float(current[-1]["end"]), start + min_seconds)
        cues.append({"start": round(start, 3), "end": round(end, 3),
                     "text": text, "words": [w["word"] for w in current]})
        current.clear()

    for word in words:
        candidate = current + [word]
        text = " ".join(w["word"] for w in candidate)
        span = float(candidate[-1]["end"]) - float(candidate[0]["start"])
        if current and (len(text) > max_chars or span > max_seconds
                        or len(candidate) > max_lines * 16):
            flush()
            candidate = [word]
        current.append(word)
        if word.get("break_after") or re.search(r"[.!?]$", str(word["word"])):
            flush()
    flush()
    return cues


def cues_from_segments(segments: Sequence[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
    return cues_from_words(words_from_segments(segments), **kwargs)


# ── safe zones and layout ───────────────────────────────────────────────────

def safe_box(width: int, height: int, preset: Dict[str, Any]) -> Dict[str, float]:
    """The rectangle captions may occupy, from the preset's declared UI strips."""
    z = preset.get("safe_zones") or {}
    top = float(height) * float(z.get("top_pct", 0)) / 100.0
    bottom = float(height) * (1.0 - float(z.get("bottom_pct", 0)) / 100.0)
    right = float(width) * (1.0 - float(z.get("right_pct", 0)) / 100.0)
    return {"left": float(width) * 0.04, "right": right,
            "top": top, "bottom": bottom,
            "width": max(1.0, right - float(width) * 0.04),
            "height": max(1.0, bottom - top)}


def _font(size: int) -> ImageFont.FreeTypeFont:
    if FONT_PATH.is_file():
        return ImageFont.truetype(str(FONT_PATH), int(size))
    return ImageFont.load_default()


def _wrap(d: ImageDraw.ImageDraw, text: str, font, max_w: float) -> List[str]:
    words, lines, line = _split_words(text), [], ""
    for word in words:
        trial = f"{line} {word}".strip()
        if d.textlength(trial, font=font) <= max_w or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def render_cue(text: str, *, width: int, height: int, preset: Dict[str, Any],
               font_px: Optional[int] = None, max_lines: int = 2
               ) -> Tuple[Image.Image, Dict[str, int]]:
    """Render one cue as an RGBA layer and return its measured box.

    The block's BOTTOM is placed at the safe-area floor, so a cue can never grow
    into the platform's bottom strip; its right edge is clamped by the safe-area
    right margin. The plate makes the words readable over any frame, and the box
    is what the check measures.
    """
    box = safe_box(width, height, preset)
    size = int(font_px or max(28, round(height * 0.046)))
    font = _font(size)
    measure = ImageDraw.Draw(Image.new("L", (8, 8)))
    max_w = box["width"] * 0.92
    lines = _wrap(measure, text, font, max_w)[:max_lines]
    if not lines:
        raise CaptionError("caption_empty: a cue needs at least one word")

    line_h = int(size * 1.12)
    text_w = max(int(measure.textlength(line, font=font)) for line in lines)
    pad_x, pad_y = int(size * 0.45), int(size * 0.28)
    block_w = min(int(box["width"]), text_w + 2 * pad_x)
    block_h = line_h * len(lines) + 2 * pad_y

    x1 = min(int(box["right"]), width)
    x0 = max(0, min(int((box["left"] + x1) / 2 - block_w / 2), x1 - block_w))
    y1 = int(box["bottom"] - height * 0.015)      # keep a 1.5% gap from the strip
    y0 = max(int(box["top"]), y1 - block_h)

    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    radius = int(size * 0.22)
    d.rounded_rectangle([x0, y0, x0 + block_w, y1], radius=radius,
                        fill=(8, 10, 9, 232))
    ty = y0 + pad_y
    for line in lines:
        line_w = measure.textlength(line, font=font)
        tx = x0 + (block_w - line_w) / 2
        d.text((tx, ty), line, font=font, fill=(255, 252, 244, 255))
        ty += line_h
    return layer, {"x0": int(x0), "y0": int(y0),
                   "x1": int(x0 + block_w), "y1": int(y1)}


def to_srt(cues: Sequence[Dict[str, Any]]) -> str:
    def stamp(seconds: float) -> str:
        ms = int(round(max(0.0, float(seconds)) * 1000))
        h, ms = divmod(ms, 3_600_000)
        m, ms = divmod(ms, 60_000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    blocks = []
    for i, cue in enumerate(cues, 1):
        blocks.append(f"{i}\n{stamp(cue['start'])} --> {stamp(cue['end'])}\n"
                      f"{cue['text']}\n")
    return "\n".join(blocks)


# ── burn + verify ───────────────────────────────────────────────────────────

def _ffmpeg(argv: Sequence[str], *, timeout: float = 1200.0) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(list(argv), capture_output=True, text=True,
                              timeout=timeout, check=False)
    except FileNotFoundError as exc:
        raise CaptionError(f"video_tool_missing: ffmpeg ({exc})") from exc


def extract_frame(video: Union[str, Path], at_seconds: float, out_path: Union[str, Path]) -> Path:
    result = _ffmpeg([video_stitch.FFMPEG, "-y", "-ss", f"{max(0.0, float(at_seconds)):.3f}",
                      "-i", str(video), "-frames:v", "1", str(out_path)])
    if result.returncode != 0 or not Path(out_path).is_file():
        raise CaptionError("frame_extract_failed: "
                           + (result.stderr.strip().splitlines() or [""])[-1][:300])
    return Path(out_path)


def check_captions(video: Union[str, Path], cues: Sequence[Dict[str, Any]],
                   boxes: Sequence[Dict[str, int]], *, preset: Dict[str, Any],
                   work_dir: Path) -> Dict[str, Any]:
    """OCR one frame per cue and check every box against the safe area."""
    import text_fidelity as tf

    width, height = int(preset["width"]), int(preset["height"])
    box = safe_box(width, height, preset)
    placements = []
    for cue, rect in zip(cues, boxes):
        inside = (rect["x0"] >= box["left"] and rect["x1"] <= box["right"]
                  and rect["y0"] >= box["top"] and rect["y1"] <= box["bottom"])
        placements.append({"text": cue["text"], "box": rect, "inside_safe_area": inside})
    placement_ok = all(p["inside_safe_area"] for p in placements)

    ocr_rows = []
    ocr_ok = True
    ocr_status = "ok"
    for i, cue in enumerate(cues):
        at = (float(cue["start"]) + float(cue["end"])) / 2.0
        frame_path = work_dir / f"cue_{i:02d}.png"
        try:
            extract_frame(video, at, frame_path)
        except CaptionError as exc:
            ocr_rows.append({"text": cue["text"], "at": round(at, 3), "ok": False,
                             "reason": str(exc)})
            ocr_ok = False
            continue
        result = tf.check_text_in_image(frame_path.read_bytes())
        status = result.get("status")
        if status != "ok":
            ocr_status = status or "error"
            ocr_rows.append({"text": cue["text"], "at": round(at, 3), "ok": False,
                             "reason": f"ocr_{status}", "words": result.get("words")})
            ocr_ok = False
            continue
        seen = " ".join(result.get("words") or []).upper()
        expected = [w for w in cue["words"] if len(w) >= 3]
        hits = [w for w in expected if w.upper().strip(".,!?") in seen]
        ratio = len(hits) / max(1, len(expected))
        ok = bool(expected) and ratio >= 0.5
        ocr_rows.append({"text": cue["text"], "at": round(at, 3), "ok": ok,
                         "hit_ratio": round(ratio, 3), "words": result.get("words")})
        ocr_ok = ocr_ok and ok

    return {
        "ok": bool(placement_ok and ocr_ok and ocr_status == "ok"),
        "safe_zone": box,
        "placements": placements,
        "ocr": ocr_rows,
        "ocr_status": ocr_status,
        "reason": ("" if placement_ok and ocr_ok and ocr_status == "ok" else
                   ("caption_ocr_unavailable: " + ocr_status if ocr_status != "ok"
                    else "caption_outside_safe_area" if not placement_ok
                    else "caption_not_readable")),
    }


def burn_captions(video: Union[str, Path], cues: Sequence[Dict[str, Any]],
                  out_path: Union[str, Path], *, platform: str,
                  font_px: Optional[int] = None, crf: int = 20,
                  verify: bool = True) -> Dict[str, Any]:
    """Burn the cue layers into the video, write the SRT, then check both."""
    try:
        plan = video_formats.plan(platform)
    except ValueError as exc:
        raise CaptionError(str(exc)) from exc
    if not cues:
        raise CaptionError("no_cues: a caption pass needs at least one cue")
    video = Path(video)
    if not video.is_file():
        raise CaptionError(f"video_missing: {video}")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ns-captions-") as tmp:
        tmp_dir = Path(tmp)
        src = video_stitch.probe(video)
        src_seconds = float(src.get("duration") or plan["seconds"])
        boxes: List[Dict[str, int]] = []
        inputs: List[str] = []
        for i, cue in enumerate(cues):
            layer, rect = render_cue(str(cue["text"]), width=plan["width"],
                                     height=plan["height"], preset=plan,
                                     font_px=font_px)
            path = tmp_dir / f"cue_{i:03d}.png"
            layer.save(path)
            boxes.append(rect)
            inputs += ["-loop", "1", "-t", f"{src_seconds:.3f}", "-i", str(path)]

        chains = []
        last = "0:v"
        for i, cue in enumerate(cues):
            label = f"v{i + 1}"
            chains.append(
                f"[{last}][{i + 1}:v]overlay=0:0:"
                f"enable='between(t,{float(cue['start']):.3f},{float(cue['end']):.3f})'"
                f"[{label}]")
            last = label
        filter_complex = ";".join(chains)

        argv = [video_stitch.FFMPEG, "-y", "-i", str(video), *inputs,
                "-filter_complex", filter_complex, "-map", f"[{last}]"]
        # Keep the source audio when there is one; never invent a track.
        if src.get("has_audio"):
            argv += ["-map", "0:a", "-c:a", "copy"]
        else:
            argv += ["-an"]
        argv += ["-t", f"{src_seconds:.3f}", "-c:v", "libx264", "-preset", "medium",
                 "-crf", str(int(crf)), "-pix_fmt", "yuv420p",
                 "-movflags", "+faststart", str(out)]
        result = _ffmpeg(argv)
        if result.returncode != 0:
            raise CaptionError("caption_burn_failed: "
                               + (result.stderr.strip().splitlines() or [""])[-1][:400])

        final = video_stitch.probe(out)
        srt = out.with_suffix(".srt")
        srt.write_text(to_srt(cues), encoding="utf-8")

        report: Dict[str, Any] = {
            "ok": True, "file": str(out), "srt": str(srt),
            "platform": plan["platform"], "cues": len(cues),
            "boxes": boxes, "final": final,
        }
        if verify:
            checked = check_captions(out, cues, boxes, preset=plan, work_dir=tmp_dir)
            report["check"] = checked
            report["ok"] = bool(checked["ok"])
            report["reason"] = checked["reason"]
            report["safe_zone"] = checked["safe_zone"]
        return report


def cues_from_transcript(transcript: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
    """Cue list from a `local_transcribe.transcribe()` result."""
    segments = transcript.get("segments") or []
    if not segments and transcript.get("text"):
        segments = [{"start": 0.0,
                     "end": float(transcript.get("duration") or 0.0),
                     "text": transcript["text"]}]
    return cues_from_segments(segments, **kwargs)


__all__ = ["cues_from_words", "cues_from_segments", "cues_from_transcript",
           "words_from_segments", "cues_from_transcript", "render_cue",
           "safe_box", "to_srt", "burn_captions", "check_captions",
           "extract_frame", "CaptionError", "FONT_PATH"]
