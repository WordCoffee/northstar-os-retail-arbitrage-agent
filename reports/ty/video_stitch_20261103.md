# Stitched video: a 15 s TikTok is now a checked MP4, not a refusal

**Date:** 2026-11-03 · **Commit:** `435d0033` · **Probe:** `state/probes/t13_video_stitch.py` PASS · **Tests:** 20 passed.

Work order item 1 in `reports/ty/creative_scan_20261103.md`. The lane used to refuse any window longer
than one sampler call with `422 video_needs_stitch`, which was honest but not a deliverable. It now
renders the planned clips, stitches them and measures the file against the placement contract.

## What it does

`Northstar_backend/video_stitch.py`:

1. **normalise** every clip to the preset canvas, fps, pixel format and codec with a Lanczos scale +
   letterbox pad (the sampler renders at 464×832 for a 9:16 contract; the deliverable is 1080×1920);
2. **concatenate** the normalised clips and **trim** to the exact frame count the plan asks for
   (`target_frames = round(seconds × fps)`), not the rounded-up per-clip total;
3. **encode** H.264 MP4 with `+faststart`, optional AAC track;
4. **probe** with ffprobe and refuse unless: duration within one frame, exact canvas, exact fps,
   H.264, MP4 container, size under the platform cap, audio present when requested.

An over-cap file gets **one** bounded bitrate retry, then a refusal with the measured byte count.
Nothing over the cap is ever returned as a success.

`POST /shorts` with `platform` now renders the planned clips through `shorts.generate_stitched`:
each clip starts from the previous clip's last decoded frame (motion continues instead of
restarting), the MP4 is stitched and checked, and a decoded frame goes through the picture gate. A
failed picture gate deletes the MP4 and returns the verdict.

`video_formats.plan()` now exposes `target_frames` alongside `total_frames`, so "the plan covers the
window" and "the deliverable is exactly this long" are separate, named numbers.

## Evidence (measured)

```
python state/probes/t13_video_stitch.py
plan: 6 clips x 77 frames
final: 15.0s 450 frames 1080x1920 h264 6121413 bytes
t13 video stitch: OK
```

The probe builds six synthetic 77-frame clips (the sampler is not what is under test), stitches them
for `tiktok/15s`, and asserts each contract check. Final size 6.1 MB against TikTok's 4 GB cap; the
frame budget is the binding check, not bytes.

```
python -m pytest test_shorts test_shorts_stitch test_video_formats test_video_stitch -> 20 passed
```

Includes: the planner's exact target length; a multi-clip request rendered with 2 calls × 45 frames
and delivered as 90 frames at 1080×1920; a wrong canvas refused with `canvas_exact`; a failed picture
gate deleting the file; `sampler_canvas` capping the long edge at 832.

## Honest gaps

- **Captions, audio and the script→scenes planner are not built.** This unit is the stitch contract
  only. The next work order items (2 and 3 in the creative scan) remain open.
- **A no-platform `/shorts` request still takes the legacy single-WEBM path**, where the sampler
  canvas is not scaled to a declared deliverable. Declared platform requests are checked; the loose
  path is not. Recorded rather than implied.
- **The 464×832 → 1080×1920 upscale is soft.** The sampler ceiling on this box is 832 px; the
  contract is 1080 px. A higher-resolution sampler or an upscale pass is a quality decision for the
  operator, not something to hide in an ffmpeg flag.
- **Amazon ad-video presets remain `verified: false`** (standing gate). They stitch and check against
  the working assumption, and the response says `compliance.verified = false`.
- The quality gate runs on one decoded frame per clip chain, not every frame. Sampling is recorded;
  a per-frame scan is a later unit.

## Files

`Northstar_backend/video_stitch.py`, `video_formats.py` (`target_frames`), `shorts.py`
(`sampler_canvas`, `generate_stitched`), `design_studio_api.py` (`/shorts` branch),
`test_video_stitch.py`, `test_shorts_stitch.py`, `state/probes/t13_video_stitch.py`.
