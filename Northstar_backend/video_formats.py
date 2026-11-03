"""Video formats: one declared contract per platform, and an honest planner.

`ad_formats` answers "what canvas is this placement?" for stills. A video needs
more than a canvas: a duration window, a frame rate, a container, a size cap, and
the safe areas the platform's own UI covers. Without those, the lane happily
renders a 2-second 16 fps WEBM and calls it a TikTok.

What this module does NOT do is claim compliance it cannot prove. Every preset
carries `source` and `verified`:

  * `verified: True` - the numbers come from the platform's published limits and
    were confirmed against them at the date in `checked`;
  * `verified: False` - the numbers are the working assumption from this repo's
    own research, and a render may use them but MUST report `compliance.verified
    = false` so nobody ships on a guess.

Amazon's own specs are deliberately `verified: False` here: reading Amazon
documentation is a standing gate (Amazon property), so confirming those caps is
an operator action or a doc import - never a crawl.

The planner is the useful part: `plan()` turns "a 30 second Short" into the Wan
frame count (4n+1), the clip count, and the per-clip frames, because the sampler
must be told frames, not seconds, and a 30 s clip is several 2-4 s renders stitched
together - not one impossible sampler call.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

#: Wan 2.2 TI2V accepts 4n+1 frames. Same constant as `shorts.frame_count`.
FRAME_STEP = 4
#: The sampler's own ceiling for one call at 480x832 on a 16 GB box (measured
#: 2026-10-30: 81 frames is the largest that completed without host RAM pressure).
MAX_FRAMES_PER_CLIP = 81

FORMATS: Dict[str, Dict[str, Any]] = {
    "shorts": {
        "label": "YouTube Shorts", "aspect": "9:16", "width": 1080, "height": 1920,
        "fps": 30, "min_seconds": 1, "max_seconds": 180, "sweet_seconds": 30,
        "container": "mp4", "video_codec": "h264", "max_bytes": 256 * 1024 * 1024,
        "safe_zones": {"top_pct": 10, "bottom_pct": 18, "right_pct": 12},
        "source": "YouTube Shorts upload limits (public help docs, checked 2026-11-03)",
        "verified": True, "checked": "2026-11-03",
    },
    "tiktok": {
        "label": "TikTok", "aspect": "9:16", "width": 1080, "height": 1920,
        "fps": 30, "min_seconds": 3, "max_seconds": 600, "sweet_seconds": 21,
        "container": "mp4", "video_codec": "h264", "max_bytes": 4 * 1024 * 1024 * 1024,
        "safe_zones": {"top_pct": 8, "bottom_pct": 22, "right_pct": 18},
        "source": "TikTok upload recommendations (public help docs, checked 2026-11-03)",
        "verified": True, "checked": "2026-11-03",
    },
    "reels": {
        "label": "Instagram Reels", "aspect": "9:16", "width": 1080, "height": 1920,
        "fps": 30, "min_seconds": 3, "max_seconds": 180, "sweet_seconds": 20,
        "container": "mp4", "video_codec": "h264", "max_bytes": 1024 * 1024 * 1024,
        "safe_zones": {"top_pct": 10, "bottom_pct": 20, "right_pct": 14},
        "source": "Instagram Reels upload limits (public help docs, checked 2026-11-03)",
        "verified": True, "checked": "2026-11-03",
    },
    "amazon-ad-16x9": {
        "label": "Amazon Sponsored Brands video (widescreen)",
        "aspect": "16:9", "width": 1920, "height": 1080,
        "fps": 30, "min_seconds": 6, "max_seconds": 45, "sweet_seconds": 15,
        "container": "mp4", "video_codec": "h264", "max_bytes": 500 * 1024 * 1024,
        "safe_zones": {"top_pct": 5, "bottom_pct": 10, "right_pct": 5},
        "source": ("working assumption from this repo's ads research; Amazon specs are a "
                   "standing gate, so they were NOT read from Amazon"),
        "verified": False, "checked": None,
    },
    "amazon-ad-9x16": {
        "label": "Amazon vertical video ad",
        "aspect": "9:16", "width": 1080, "height": 1920,
        "fps": 30, "min_seconds": 6, "max_seconds": 45, "sweet_seconds": 15,
        "container": "mp4", "video_codec": "h264", "max_bytes": 500 * 1024 * 1024,
        "safe_zones": {"top_pct": 8, "bottom_pct": 15, "right_pct": 8},
        "source": ("working assumption; Amazon specs are a standing gate and were NOT "
                   "read from Amazon"),
        "verified": False, "checked": None,
    },
}

#: 15 s and 30 s are the two ad lengths every placement here accepts.
AD_LENGTHS = (15, 30)


def describe() -> List[Dict[str, Any]]:
    return [{"id": key, **value} for key, value in FORMATS.items()]


def _frames(seconds: float, fps: int) -> int:
    raw = max(1, int(round(float(seconds) * int(fps))))
    # round UP to 4n+1 so a clip is never shorter than the requested window
    if (raw - 1) % FRAME_STEP:
        raw += FRAME_STEP - ((raw - 1) % FRAME_STEP)
    return raw


def plan(platform: str, seconds: Optional[float] = None, *,
         fps: Optional[int] = None, width: Optional[int] = None,
         height: Optional[int] = None) -> Dict[str, Any]:
    """Turn a duration into sampler calls. Raises ValueError (code-prefixed)."""
    key = str(platform or "").strip().lower()
    if key not in FORMATS:
        raise ValueError(f"video_format_unknown: {platform!r}; use one of {sorted(FORMATS)}")
    preset = FORMATS[key]
    want = float(seconds if seconds is not None else preset["sweet_seconds"])
    if want < preset["min_seconds"] or want > preset["max_seconds"]:
        raise ValueError(
            f"video_duration_out_of_range: {want:g}s is outside {preset['min_seconds']}"
            f"-{preset['max_seconds']}s for {key}")
    use_fps = int(fps or preset["fps"])
    if not 8 <= use_fps <= 60:
        raise ValueError(f"video_fps_out_of_range: {use_fps}")
    canvas_w = int(width or preset["width"])
    canvas_h = int(height or preset["height"])
    if (canvas_w, canvas_h) != (preset["width"], preset["height"]):
        raise ValueError(
            f"video_canvas_conflict: {key} is {preset['width']}x{preset['height']}, "
            f"got {canvas_w}x{canvas_h}")
    total = _frames(want, use_fps)
    clips = max(1, -(-total // MAX_FRAMES_PER_CLIP))
    per_clip = _frames(round(want / clips, 3), use_fps)
    return {
        "platform": key,
        "label": preset["label"],
        "aspect": preset["aspect"],
        "width": canvas_w, "height": canvas_h, "fps": use_fps,
        "seconds": round(want, 2),
        #: exact deliverable length after the last clip is trimmed
        "target_frames": int(round(want * use_fps)),
        "total_frames": per_clip * clips,
        "clips": clips,
        "frames_per_clip": per_clip,
        "max_frames_per_clip": MAX_FRAMES_PER_CLIP,
        "frame_step": FRAME_STEP,
        "container": preset["container"],
        "video_codec": preset["video_codec"],
        "max_bytes": preset["max_bytes"],
        "safe_zones": preset["safe_zones"],
        "stitch_required": clips > 1,
        "compliance": {"verified": bool(preset["verified"]),
                       "source": preset["source"],
                       "checked": preset["checked"],
                       "note": ("A verified preset may be claimed compliant against the "
                                "platform's published limits. An unverified one may be "
                                "rendered but must be reported as unverified."
                                if not preset["verified"] else
                                "Numbers confirmed against the platform's published limits.")},
    }


def ad_lengths(platform: Optional[str] = None) -> List[int]:
    """The two lengths the ad placements accept, clipped to the preset's window."""
    if not platform:
        return list(AD_LENGTHS)
    key = str(platform).strip().lower()
    if key not in FORMATS:
        raise ValueError(f"video_format_unknown: {platform!r}")
    preset = FORMATS[key]
    return [n for n in AD_LENGTHS
            if preset["min_seconds"] <= n <= preset["max_seconds"]]
