# Captions and audio: placement first, then the measurement

**Date:** 2026-11-03 · **Commits:** `b868bda1` (captions), `095cae65` (audio) · **Probes:** t14 PASS, t15 PASS · **Tests:** 11 passed.

Work order items 2 and 3 in `reports/ty/creative_scan_20261103.md`. Both are checked against the
placement contract in `video_formats.py`, not against "a file exists".

## Captions (`Northstar_backend/video_captions.py`)

Transcript segments (or word timings) become short cues; each cue is rendered as an RGBA layer with a
computed box, burned in with ffmpeg, and written as a `.srt` sidecar. The box is calculated in Python
— the bottom sits 1.5% above the preset's safe floor, the right edge is clamped by its right strip —
so the safe-zone check tests the same numbers that drew the caption, not a second guess.

Measured (`state/probes/t14_video_captions.py`):

```
final: 3.0s 90 frames 1080x1920 h264 2695126 B
safe area: x<= 886, y 154-1498
cue "LION'S MANE": {'x0': 219, 'y0': 1322, 'x1': 709, 'y1': 1468}
cue 'SIX OZ POUCH': {'x0': 206, 'y0': 1322, 'x1': 722, 'y1': 1468}
ocr @0.78s: ['00:00:00.800', '24', "LION'S MANE"]
ocr @2.15s: ['00:00:02.167', '65', 'SIX OZ POUCH']
```

(The timecode words are the synthetic test clip's own overlay, not the caption.) A cue whose box
enters the bottom strip, or whose frame OCR cannot read, is a refusal with a named reason.

## Audio (`Northstar_backend/video_audio.py`)

* voiceover through the local Piper/SAPI voice (`local_voice`), 3.5 s for a 3 s line on this box;
* a deterministic **procedurally generated** ambient bed (root/fifth/octave, detuned stereo, fades,
  peak-normalised) when no licensed track is supplied — nothing downloaded, no licence question;
* the bed is **ducked under the voice** with `sidechaincompress` (threshold 0.03, ratio 6, 5 ms
  attack, 280 ms release);
* two-pass `loudnorm` to **-16 LUFS**, true peak -1.5 dB, then AAC 192k muxed onto the **untouched
  picture** (`-c:v copy`);
* verification: audio stream present, AAC, not silent (peak above -30 dBFS), integrated loudness
  within 2 LU of target, duration matching the picture.

Measured (`state/probes/t15_video_audio.py`):

```
bed: peak -14.9 dB, mean -24.2 dB
final: 3.0s 1080x1920 audio=aac lufs=-16.41 peak=-3.1
```

## Honest gaps

- **No endpoint yet.** Both modules are library + probe + tests; `/shorts` does not expose captions
  or audio. Wiring them needs a video asset path and a transcript, which is the next integration
  unit, not a claim made here.
- **Transcription is segment-timed.** `local_transcribe` does not request word timestamps; the cue
  builder distributes each segment's duration by character length and records `timing: "segment"`.
- **The bed is a pad, not a licensed track.** Pass `music=` to use a real one; the generator exists so
  the lane is not blocked on a download or a licence.
- **Ducking is verified by the filter being applied and the mix being measured**, not by a
  spectral comparison of bed-under-voice vs bed-alone. That is a stronger test for a later pass.
- Captions are OCR-checked at one frame per cue, not every frame.

## Files

`Northstar_backend/video_captions.py`, `video_audio.py`, `test_video_captions.py`,
`test_video_audio.py`, `state/probes/t14_video_captions.py`, `t15_video_audio.py`.
