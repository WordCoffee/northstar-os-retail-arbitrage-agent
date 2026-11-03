"""Contract: one command produces a checked vertical video, end to end.

The sampler is synthetic (the render is not what is under test); the stitch,
captions and audio are real. The probe requires every stage's own contract to
pass and the final file to be 90 frames / 1080x1920 / -16 LUFS / readable.

A 3 s window is used because it exercises every stage quickly; the 15 s and
30 s plans are covered by t16.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import video_ad  # noqa: E402
import video_stitch as vs  # noqa: E402

PRODUCT = {
    "brand": "MOGRA", "product": "LION'S MANE", "subtitle": "MUSHROOM POWDER",
    "weight": "6 oz (170 g)", "claims": ["100% PURE", "NO FILLERS"],
}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t18-") as tmp:
        tmp_dir = Path(tmp)

        def render(scene, frames):
            path = tmp_dir / f"clip_{scene['index']}_{frames}.mp4"
            result = subprocess.run([
                vs.FFMPEG, "-y", "-f", "lavfi",
                "-i", "testsrc2=size=480x832:rate=30:duration=10",
                "-frames:v", str(frames), "-c:v", "libx264", "-preset", "veryfast",
                "-pix_fmt", "yuv420p", str(path)], capture_output=True, text=True)
            assert result.returncode == 0, result.stderr[-300:]
            return path.read_bytes()

        out = tmp_dir / "out"
        manifest = video_ad.produce(PRODUCT, platform="tiktok", seconds=3,
                                    out_dir=out, render_scene=render, seed=11)
        final = Path(manifest["file"])
        print(f"file: {final.name} {final.stat().st_size} bytes")
        print(f"checks: {manifest['checks']}")
        print(f"video: {manifest['stitch']['final']['duration']}s "
              f"{manifest['stitch']['final']['nb_frames']} frames "
              f"{manifest['stitch']['final']['width']}x{manifest['stitch']['final']['height']} "
              f"{manifest['stitch']['final']['codec']}")
        print(f"audio: {manifest['audio']['integrated_lufs']} LUFS "
              f"peak {manifest['audio']['volume'].get('max_volume')} dB")
        print(f"captions: {manifest['captions']['cues']} cues, "
              f"ocr={manifest['captions']['check']['ok']}")

        assert manifest["ok"] is True, manifest
        assert all(manifest["checks"].values()), manifest["checks"]
        assert final.is_file() and final.stat().st_size > 100_000
        assert manifest["stitch"]["final"]["nb_frames"] == 90
        assert (manifest["stitch"]["final"]["width"],
                manifest["stitch"]["final"]["height"]) == (1080, 1920)
        assert manifest["audio"]["checks"]["has_audio"] is True
        assert abs(manifest["audio"]["integrated_lufs"] + 16.0) <= 2.0
        assert manifest["captions"]["check"]["ok"] is True
        assert (out / "video_ad_manifest.json").is_file()
    print("t18 video ad end to end: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
