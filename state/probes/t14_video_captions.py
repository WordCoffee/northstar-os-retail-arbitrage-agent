"""Contract: a caption is burned inside the safe area and OCR can read it.

A subtitle that sits under TikTok's controls is not a subtitle. This probe
builds a 3 s 9:16 clip, burns two cues, and checks the two things that are
measurable:

  * the caption boxes stay inside the declared safe area (not the phone UI),
  * OCR on a sampled frame finds the cue words (not just "a file exists").

It also checks the `.srt` sidecar and the deliverable's duration/canvas.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import text_fidelity  # noqa: E402
import video_captions as vc  # noqa: E402
import video_stitch  # noqa: E402


def main() -> int:
    cues = [
        {"start": 0.20, "end": 1.35, "text": "LION'S MANE", "words": ["LION'S", "MANE"]},
        {"start": 1.55, "end": 2.75, "text": "SIX OZ POUCH", "words": ["SIX", "OZ", "POUCH"]},
    ]
    with tempfile.TemporaryDirectory(prefix="t14-") as tmp:
        tmp_dir = Path(tmp)
        source = tmp_dir / "source.mp4"
        made = video_stitch._run([
            video_stitch.FFMPEG, "-y", "-f", "lavfi",
            "-i", "testsrc2=size=1080x1920:rate=30:duration=3",
            "-frames:v", "90", "-c:v", "libx264", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", str(source)])
        assert made.returncode == 0, made.stderr[-400:]

        out = tmp_dir / "captioned.mp4"
        report = vc.burn_captions(source, cues, out, platform="tiktok")
        assert report["ok"] is True, report
        assert report["srt"] and Path(report["srt"]).is_file()
        srt = Path(report["srt"]).read_text(encoding="utf-8")
        assert "LION'S MANE" in srt and "SIX OZ POUCH" in srt, srt

        final = report["final"]
        safe = report["safe_zone"]
        print(f"final: {final['duration']}s {final['nb_frames']} frames "
              f"{final['width']}x{final['height']} {final['codec']} {final['bytes']} B")
        print(f"safe area: x<= {safe['right']:.0f}, y {safe['top']:.0f}-{safe['bottom']:.0f}")
        assert final["width"] == 1080 and final["height"] == 1920, final
        assert abs(final["duration"] - 3.0) <= 1 / 30 + 1e-3, final
        for box, cue in zip(report["boxes"], cues):
            print(f"cue {cue['text']!r}: {box}")
            assert box["x0"] >= safe["left"] - 1, box
            assert box["x1"] <= safe["right"] + 1, (box, safe)
            assert box["y0"] >= safe["top"] - 1, (box, safe)
            assert box["y1"] <= safe["bottom"] - 1, (box, safe)

        # Independent OCR, not just the module's own verdict.
        for i, cue in enumerate(cues):
            at = (cue["start"] + cue["end"]) / 2
            frame = vc.extract_frame(out, at, tmp_dir / f"frame_{i}.png")
            seen = text_fidelity.check_text_in_image(frame.read_bytes())
            words = " ".join(seen.get("words") or []).upper()
            print(f"ocr @{at:.2f}s: {seen.get('words')}")
            assert seen.get("status") == "ok", seen
            assert "LION" in words or "MANE" in words or "POUCH" in words, words
    print("t14 video captions: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
