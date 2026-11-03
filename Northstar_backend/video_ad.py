"""One product video, end to end, with every stage checked.

This is the capstone over the lanes built this session:

    script -> scenes -> per-scene clips -> stitch -> captions -> audio -> check

Each stage already owns its own contract (`video_script`, `video_stitch`,
`video_captions`, `video_audio`). This module runs them in order, keeps the
intermediate evidence, and returns a file only when all of them pass. A failure
deletes the final file and names the stage and the reason.

The sampler is injectable (`render_scene`) so the orchestration can be tested
without spending minutes on Wan; the default renders each scene on the local
Wan lane from a supplied product picture. No network, no provider call.
"""
from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union

import shorts
import video_audio
import video_captions
import video_formats
import video_script
import video_stitch

FINAL_NAME = "video_ad.mp4"


class VideoAdError(RuntimeError):
    """A stage refused; the message names the stage and the measured reason."""


def _wan_frames(n: int) -> int:
    """Round a frame request UP to the 4n+1 the Wan latent accepts."""
    n = max(5, int(n))
    return n + ((1 - n) % 4)


def _chunks(frames: int, max_frames: int = video_formats.MAX_FRAMES_PER_CLIP
            ) -> List[int]:
    """Split a scene into sampler-sized chunks, each rounded up to 4n+1."""
    count = max(1, int(math.ceil(float(frames) / float(max_frames))))
    base, extra = divmod(int(frames), count)
    return [_wan_frames(base + (1 if i < extra else 0)) for i in range(count)]


def scene_chunks(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Public view of the clip plan, for a dry run or a progress estimate."""
    return [{"scene": int(s["index"]), "beat": s["beat"],
             "chunks": _chunks(int(s["frames"]))}
            for s in plan.get("scenes") or []]


def produce(product: Dict[str, Any], *, platform: str,
            seconds: Optional[float] = None,
            out_dir: Union[str, Path],
            plate_png: Optional[bytes] = None,
            render_scene: Optional[Callable[[Dict[str, Any], int], bytes]] = None,
            steps: int = 24, cfg: float = 5.0, seed: int = 0,
            music: Optional[Union[str, Path]] = None,
            voice: Optional[str] = None,
            voiceover_text: Optional[str] = None,
            on_progress: Optional[Callable[[str, Dict[str, Any]], None]] = None
            ) -> Dict[str, Any]:
    """Produce the full video. Returns the manifest; raises on a stage refusal."""
    def emit(stage: str, **detail: Any) -> None:
        if on_progress is None:
            return
        try:
            on_progress(stage, detail)
        except Exception:  # noqa: BLE001 - progress must never break the render
            pass

    plan = video_script.plan_scenes(product, platform=platform, seconds=seconds,
                                    seed=seed)
    emit("script", scenes=len(plan["scenes"]), seconds=plan["seconds"])
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    final_path = out / FINAL_NAME
    final_path.unlink(missing_ok=True)

    if render_scene is None and not plate_png:
        raise VideoAdError(
            "video_ad_plate_missing: a product picture is required for the local "
            "Wan lane, or pass render_scene for a different renderer")

    width, height = plan["canvas"]
    render_w, render_h = shorts.sampler_canvas(width, height)

    with tempfile.TemporaryDirectory(prefix="ns-video-ad-") as tmp:
        tmp_dir = Path(tmp)

        # 1. clips ---------------------------------------------------------
        clip_paths: List[Path] = []
        clip_records: List[Dict[str, Any]] = []
        for scene in plan["scenes"]:
            for piece, frames in enumerate(_chunks(scene["frames"])):
                emit("clip", scene=scene["index"], beat=scene["beat"],
                     piece=piece, frames=frames)
                if render_scene is not None:
                    payload = render_scene(scene, frames)
                else:
                    payload = shorts.generate(
                        plate_png or b"", prompt=scene["prompt"], width=render_w,
                        height=render_h, length=frames, steps=steps, cfg=cfg,
                        seed=seed + scene["index"] * 10 + piece,
                        fps=plan["fps"])["video"] or b""
                if not payload:
                    raise VideoAdError(
                        f"video_ad_clip_empty: scene {scene['index']} piece {piece} "
                        "returned no bytes")
                path = tmp_dir / f"scene_{scene['index']:02d}_{piece:02d}.webm"
                path.write_bytes(payload)
                clip_paths.append(path)
                clip_records.append({"scene": scene["index"], "piece": piece,
                                     "frames": frames, "bytes": len(payload),
                                     "prompt": scene["prompt"]})
        if not clip_paths:
            raise VideoAdError("video_ad_no_clips: the script produced no clips")

        # 2. stitch --------------------------------------------------------
        emit("stitch", clips=len(clip_paths))
        stitched = video_stitch.stitch_clips(
            clip_paths, tmp_dir / "stitched.mp4", platform=plan["platform"],
            seconds=plan["seconds"])
        if not stitched.get("ok"):
            raise VideoAdError("video_ad_stitch_failed: " + str(stitched.get("reason")))
        stitched_path = Path(stitched["final"]["path"])

        # 3. captions ------------------------------------------------------
        cues = [{"start": s["start"], "end": s["end"],
                 "text": s["on_screen_text"],
                 "words": [w for w in s["on_screen_text"].split() if w]}
                for s in plan["scenes"]]
        emit("captions", cues=len(cues))
        captioned = video_captions.burn_captions(
            stitched_path, cues, tmp_dir / "captioned.mp4",
            platform=plan["platform"])
        if not captioned.get("ok"):
            raise VideoAdError("video_ad_caption_failed: " + str(captioned.get("reason")))

        # 4. audio ---------------------------------------------------------
        script = voiceover_text or " ".join(s["voiceover"] for s in plan["scenes"])
        emit("audio", script_chars=len(script))
        voiced = video_audio.add_audio(
            Path(captioned["file"]), tmp_dir / "final.mp4", script=script,
            voice=voice, music=music)
        if not voiced.get("ok"):
            raise VideoAdError("video_ad_audio_failed: " + str(voiced.get("reason")))
        payload = Path(voiced["file"]).read_bytes()
        final_path.write_bytes(payload)

        final = video_stitch.probe(final_path)
        checks = {
            "stitch_contract": all(stitched["checks"].values()),
            "captions_checked": bool(captioned["check"].get("ok")),
            "audio_checked": bool(voiced.get("ok")),
            "has_audio": bool(final.get("has_audio")),
            "canvas_exact": (final["width"], final["height"]) == (width, height),
            # The stitch stage proved the exact frame count. The caption burn
            # re-encodes the picture, so the final check is the one-frame
            # duration tolerance, not a container frame count that AAC muxing
            # may omit (probe then derives it from duration, which can round).
            "duration_within_one_frame": abs(final["duration"] - plan["seconds"])
            <= 1.0 / plan["fps"] + 1e-3,
        }
        failed = [k for k, ok in checks.items() if not ok]
        manifest = {
            "schema": "northstar.video_ad.v1",
            "ok": not failed,
            "file": str(final_path),
            "platform": plan["platform"],
            "seconds": plan["seconds"],
            "canvas": [width, height],
            "fps": plan["fps"],
            "render_canvas": [render_w, render_h],
            "final": final,
            "scenes": plan["scenes"],
            "clips": clip_records,
            "stitch": {"checks": stitched["checks"], "final": stitched["final"],
                       "compliance": stitched["compliance"]},
            "captions": {"cues": len(cues), "check": captioned.get("check"),
                         "boxes": captioned.get("boxes"), "srt": captioned.get("srt")},
            "audio": {"checks": voiced.get("checks"),
                      "integrated_lufs": voiced.get("integrated_lufs"),
                      "volume": voiced.get("volume"),
                      "music_source": voiced.get("music_source")},
            "checks": checks,
            "reason": "" if not failed else "video_ad_contract_failed: " + ", ".join(failed),
        }
        if failed:
            final_path.unlink(missing_ok=True)
        (out / "video_ad_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8")
        emit("done", ok=not failed, file=str(final_path))
    if not manifest["ok"]:
        raise VideoAdError(manifest["reason"])
    return manifest


__all__ = ["produce", "VideoAdError", "FINAL_NAME", "scene_chunks"]
