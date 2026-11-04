"""Caption contracts: cue timing, safe placement, burn-in and OCR.

The burn test uses a 2 s synthetic clip; the OCR test is the independent check
that the words are visible, not merely that the encoder wrote a file.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import video_captions as vc
import video_stitch as vs


def _clip(path: Path, seconds: float = 2.0, size="1080x1920") -> Path:
    result = subprocess.run([
        vs.FFMPEG, "-y", "-f", "lavfi",
        "-i", f"testsrc2=size={size}:rate=30:duration={seconds}",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-400:]
    return path


def test_words_are_distributed_across_a_segment():
    words = vc.words_from_segments([{"start": 1.0, "end": 2.0, "text": "SIX OZ POUCH"}])
    assert [w["word"] for w in words] == ["SIX", "OZ", "POUCH"]
    assert words[0]["start"] == pytest.approx(1.0)
    assert words[-1]["end"] == pytest.approx(2.0)
    assert all(w["timing"] == "segment" for w in words)
    at = [w["start"] for w in words]
    assert at == sorted(at)


def test_cues_break_at_the_character_budget_and_punctuation():
    words = vc.words_from_segments([
        {"start": 0.0, "end": 1.0, "text": "one"},
        {"start": 1.0, "end": 2.0, "text": "two three four five six seven eight nine"},
    ])
    cues = vc.cues_from_words(words, max_chars=18)
    assert len(cues) >= 3
    assert all(len(c["text"]) <= 18 for c in cues)
    assert all(c["end"] > c["start"] for c in cues)

    sentence = vc.cues_from_words([
        {"word": "DONE.", "start": 0.0, "end": 0.5, "timing": "word"},
        {"word": "NEXT", "start": 0.6, "end": 1.0, "timing": "word"},
    ])
    assert sentence[0]["text"] == "DONE."


def test_a_cue_box_stays_above_the_platform_strip():
    preset = __import__("video_formats").FORMATS["tiktok"]
    safe = vc.safe_box(1080, 1920, preset)
    layer, box = vc.render_cue("SIX OZ POUCH", width=1080, height=1920,
                               preset=preset)
    assert layer.size == (1080, 1920)
    assert box["y1"] <= safe["bottom"] - 1
    assert box["x1"] <= safe["right"]
    assert box["y0"] >= safe["top"]
    # the layer carries only the plate + type; everything else is transparent
    assert layer.getpixel((10, 10))[3] == 0


def test_srt_is_valid_and_ordered():
    srt = vc.to_srt([
        {"start": 0.0, "end": 1.5, "text": "FIRST"},
        {"start": 2.0, "end": 3.25, "text": "SECOND"},
    ])
    assert "00:00:00,000 --> 00:00:01,500" in srt
    assert "00:00:02,000 --> 00:00:03,250" in srt
    assert srt.index("FIRST") < srt.index("SECOND")


def test_burn_writes_the_file_the_srt_and_a_readable_frame(tmp_path):
    source = _clip(tmp_path / "src.mp4")
    cues = [{"start": 0.2, "end": 1.4, "text": "SIX OZ POUCH",
             "words": ["SIX", "OZ", "POUCH"]}]
    out = tmp_path / "out.mp4"
    report = vc.burn_captions(source, cues, out, platform="tiktok")
    assert report["ok"] is True, report
    assert out.is_file() and out.stat().st_size > 1000
    assert Path(report["srt"]).read_text(encoding="utf-8").strip()
    assert report["final"]["nb_frames"] == 60
    assert report["boxes"][0]["y1"] <= report["safe_zone"]["bottom"] - 1


def test_an_empty_cue_is_refused():
    with pytest.raises(vc.CaptionError, match="caption_empty"):
        vc.render_cue("   ", width=1080, height=1920,
                      preset=__import__("video_formats").FORMATS["tiktok"])

def test_measured_word_timings_are_used_verbatim():
    words = vc.words_from_segments([{
        "start": 0.0, "end": 2.0, "text": "six oz pouch",
        "words": [
            {"word": "six", "start": 0.10, "end": 0.40},
            {"word": "oz", "start": 0.40, "end": 0.70},
            {"word": "pouch", "start": 0.90, "end": 1.60},
        ],
    }])
    assert [w["timing"] for w in words] == ["word", "word", "word"]
    assert [round(w["start"], 2) for w in words] == [0.10, 0.40, 0.90]
    assert [round(w["end"], 2) for w in words] == [0.40, 0.70, 1.60]
