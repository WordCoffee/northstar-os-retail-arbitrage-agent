"""Contract: a video with a voice and a bed, mixed, ducked and normalised.

The lane was silent. This probe puts a spoken line and a generated bed on a 3 s
9:16 clip and requires the result to be measurable:

  * an AAC audio stream on the same picture (no re-encode of the video),
  * not silent (peak above -30 dBFS),
  * integrated loudness within 2 LU of -16,
  * duration matching the picture,
  * the bed actually ducked under the voice (the mix reports it).
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import video_audio as va  # noqa: E402
import video_stitch as vs  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="t15-") as tmp:
        tmp_dir = Path(tmp)
        source = tmp_dir / "source.mp4"
        made = vs._run([
            vs.FFMPEG, "-y", "-f", "lavfi",
            "-i", "testsrc2=size=1080x1920:rate=30:duration=3",
            "-frames:v", "90", "-c:v", "libx264", "-preset", "veryfast",
            "-pix_fmt", "yuv420p", str(source)])
        assert made.returncode == 0, made.stderr[-400:]

        bed = tmp_dir / "bed.wav"
        bed.write_bytes(va.ambient_bed(3.0))
        bed_vol = va.volume(bed)
        assert bed_vol["max_volume"] > -30, bed_vol
        print(f"bed: peak {bed_vol['max_volume']} dB, mean {bed_vol['mean_volume']} dB")

        out = tmp_dir / "with_audio.mp4"
        result = va.add_audio(
            source, out,
            script="Lion mane. Six ounces. One ingredient. Nothing else.",
            music=bed)
        assert result["ok"] is True, result
        print(f"final: {result['probe']['duration']}s "
              f"{result['probe']['width']}x{result['probe']['height']} "
              f"audio={result['probe']['audio_codec']} "
              f"lufs={result['integrated_lufs']} peak={result['volume'].get('max_volume')}")
        assert out.is_file() and out.stat().st_size > 10_000
        assert result["checks"]["has_audio"] and result["checks"]["audio_aac"], result
        assert result["checks"]["not_silent"], result
        assert abs(result["integrated_lufs"] - (-16.0)) <= 2.0, result
        assert abs(result["probe"]["duration"] - 3.0) <= 1 / 30 + 1e-3, result
        assert result["mix"]["ducked"] is True, result["mix"]
        assert result["probe"]["width"] == 1080 and result["probe"]["height"] == 1920
    print("t15 video audio: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
