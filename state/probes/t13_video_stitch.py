"""Contract: a 15 s 9:16 video is stitched from clips and MEASURED.

The Wan sampler renders ~2.5 s per call, so a 15 s TikTok is six calls. Before
this module the lane refused the request (`video_needs_stitch`), which was
honest but not a deliverable. This probe requires the deliverable:

  * six source clips (synthetic here: the sampler is not what is under test),
  * one stitched MP4 at the platform canvas,
  * duration within one frame of 15.0 s,
  * H.264 in MP4,
  * under the platform's byte cap.

It uses ffmpeg/ffprobe on PATH and writes only into a temporary directory.
"""
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import video_formats  # noqa: E402
import video_stitch  # noqa: E402


def main() -> int:
    plan = video_formats.plan("tiktok", 15)
    assert plan["clips"] == 6, plan
    assert plan["target_frames"] == 450, plan

    with tempfile.TemporaryDirectory(prefix="t13-") as tmp:
        tmp_dir = Path(tmp)
        clips = []
        for i in range(plan["clips"]):
            clip = tmp_dir / f"clip_{i}.mp4"
            result = video_stitch._run([
                video_stitch.FFMPEG, "-y", "-f", "lavfi",
                "-i", f"testsrc2=size=480x832:rate=16:duration=5",
                "-frames:v", str(plan["frames_per_clip"]),
                "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                str(clip),
            ])
            assert result.returncode == 0, result.stderr[-500:]
            clips.append(clip)
        out = tmp_dir / "short.mp4"
        result = video_stitch.stitch_clips(
            clips, out, platform="tiktok", seconds=15)

        final = result["final"]
        print(f"plan: {plan['clips']} clips x {plan['frames_per_clip']} frames")
        print(f"final: {final['duration']}s {final['nb_frames']} frames "
              f"{final['width']}x{final['height']} {final['codec']} "
              f"{final['bytes']} bytes")
        assert result["ok"] is True
        assert final["width"] == 1080 and final["height"] == 1920, final
        assert final["codec"] == "h264", final
        assert final["nb_frames"] == 450, final
        tolerance = 1.0 / plan["fps"] + 1e-3
        assert abs(final["duration"] - 15.0) <= tolerance, final
        assert final["bytes"] <= plan["max_bytes"], final
        assert all(result["checks"].values()), result["checks"]
        assert out.is_file() and out.stat().st_size == final["bytes"]
    print("t13 video stitch: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
