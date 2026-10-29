"""Local pre-upload validator for social canvases (REA 1.4 candidate S4).

Every rule here comes from a platform's own page, pulled 2026-10-28 and cited in
reports/social_media_asset_specs_20261028.md. Nothing is inferred, and anything
not published is reported as UNVERIFIED rather than guessed:

  * aspect-ratio tolerance is 1% because Meta states a 1% tolerance;
  * byte caps are the documented maximums, not "what usually uploads";
  * TikTok safe-zone pixels are NOT enforced — TikTok publishes .zip packages,
    not numbers (reported as unverified);
  * LinkedIn values stay flagged REPORTED because its official page 404'd.

No network, no provider, no upload. It validates a file you already have.

    from social_validate import validate
    report = validate(png_bytes, "ig-post", caption="...")

CLI:
    python social_validate.py --canvas ig-post --file ad.png --caption "..."
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

RATIO_TOLERANCE = 0.01          # Meta documents a 1% aspect-ratio tolerance

# w/h mirror northstar-os-ui/src/studio/engine/presets.js; test_social_validate.py
# asserts that parity so the two can never drift apart silently.
SPECS: Dict[str, Dict[str, Any]] = {
    "ig-post": {"w": 1440, "h": 1800, "max_bytes": 30 * 1024 * 1024,
                "formats": ("JPEG", "PNG"), "min_width": 500,
                "source": "meta-ads-feed", "confidence": "VERIFIED",
                "copy": {"primary": 125, "headline": 40, "hashtags": 30}},
    "ig-carousel": {"w": 1080, "h": 1080, "max_bytes": 30 * 1024 * 1024,
                    "formats": ("JPEG", "PNG"), "min_width": 500,
                    "source": "meta-ads-feed", "confidence": "VERIFIED",
                    "copy": {"primary": 125, "headline": 40}},
    "meta-story": {"w": 1440, "h": 2560, "max_bytes": 30 * 1024 * 1024,
                   "formats": ("JPEG", "PNG"), "min_width": 500,
                   "source": "meta-ads-story", "confidence": "VERIFIED",
                   "copy": {"primary": 125},
                   "safe_area": {"top": 0.14, "bottom": 0.35, "sides": 0.06}},
    "pin": {"w": 1000, "h": 1500, "max_bytes": 20 * 1024 * 1024,
            "formats": ("JPEG", "PNG"), "source": "pinterest-specs",
            "confidence": "VERIFIED", "copy": {"title": 100, "description": 800}},
    "pin-video": {"w": 1000, "h": 1500, "max_bytes": 2 * 1024 ** 3,
                  "formats": ("MP4", "MOV", "M4V"), "media": "video",
                  "source": "pinterest-specs", "confidence": "VERIFIED",
                  "copy": {"title": 100, "description": 800}},
    "pin-idea": {"w": 1080, "h": 1920, "max_bytes": 2 * 1024 ** 3,
                 "formats": ("JPEG", "PNG", "MP4", "MOV"),
                 "source": "pinterest-specs", "confidence": "VERIFIED",
                 "copy": {"title": 100, "description": 800},
                 "safe_area_px": {"top": 270, "left": 65, "right": 195, "bottom": 440}},
    "tiktok": {"w": 1080, "h": 1920, "max_bytes": 500 * 1024 * 1024,
               "formats": ("MP4", "MOV", "MPEG", "3GP", "AVI"), "media": "video",
               "source": "tiktok-infeed", "confidence": "VERIFIED",
               "min_width": 540, "min_bitrate_kbps": 516},
    "x-post": {"w": 1200, "h": 628, "max_bytes": 5 * 1024 * 1024,
               "formats": ("JPEG", "PNG"), "source": "x-creative-specs",
               "confidence": "VERIFIED", "copy": {"post": 280}},
    "x-carousel": {"w": 800, "h": 800, "max_bytes": 5 * 1024 * 1024,
                   "formats": ("JPEG", "PNG"), "source": "x-creative-specs",
                   "confidence": "VERIFIED", "copy": {"post": 280}},
    "x-vertical": {"w": 1080, "h": 1920, "max_bytes": 1024 * 1024 * 1024,
                   "formats": ("MP4", "MOV"), "media": "video",
                   "source": "x-creative-specs", "confidence": "VERIFIED",
                   "min_width": 720},
    "linkedin": {"w": 1200, "h": 628, "max_bytes": 5 * 1024 * 1024,
                 "formats": ("JPEG", "PNG", "GIF"), "source": "linkedin-ad-specs",
                 "confidence": "REPORTED",
                 "copy": {"headline": 70, "intro": 150},
                 "note": "official page 404'd; values are third-party and flagged"},
    "yt-thumb": {"w": 3840, "h": 2160, "max_bytes": 50 * 1024 * 1024,
                 "formats": ("JPEG", "PNG"), "min_width": 640,
                 "source": "youtube-thumbnails", "confidence": "VERIFIED"},
    "yt-shorts-thumb": {"w": 1080, "h": 1920, "max_bytes": 50 * 1024 * 1024,
                        "formats": ("JPEG", "PNG"), "min_width": 640,
                        "source": "youtube-thumbnails", "confidence": "VERIFIED",
                        "note": "UNVERIFIED: the mobile byte cap for Shorts "
                                "thumbnails is not stated on the page"},
}

UNVERIFIED_RULES = [
    "TikTok safe-zone pixels (published as .zip packages, not numbers)",
    "YouTube Shorts thumbnail mobile byte cap",
    "Instagram carousel per-card minima (no card grid is published)",
]


def _check(check_id: str, status: str, detail: str, **kw) -> Dict[str, Any]:
    return {"id": check_id, "status": status, "detail": detail, **kw}


def validate(payload: bytes, canvas: str, *, caption: Optional[str] = None,
             filename: Optional[str] = None) -> Dict[str, Any]:
    """Validate one asset against a documented canvas. Returns a report, never raises
    for a content problem (only for an unknown canvas or an unreadable file)."""
    spec = SPECS.get(canvas)
    if spec is None:
        raise ValueError(f"unknown canvas {canvas!r}; known: {sorted(SPECS)}")

    checks: List[Dict[str, Any]] = []
    warnings: List[str] = []
    size_bytes = len(payload)
    cap = spec["max_bytes"]

    checks.append(_check("bytes", "pass" if size_bytes <= cap else "block",
                         f"{size_bytes:,} bytes (cap {cap:,})",
                         value=size_bytes, limit=cap))
    if size_bytes > cap * 0.8:
        warnings.append(f"within {100 - int(100 * size_bytes / cap)}% of the byte cap; "
                        "platforms re-encode, so leave headroom")

    is_video = spec.get("media") == "video"
    fmt = None
    if not is_video:
        try:
            with Image.open(io.BytesIO(payload)) as im:
                fmt = (im.format or "").upper().replace("JPG", "JPEG")
                width, height = im.size
                mode = im.mode
            allowed = tuple(f.upper() for f in spec.get("formats", ()))
            checks.append(_check("format", "pass" if fmt in allowed else "block",
                                 f"{fmt} (allowed {', '.join(allowed)})"))
            target = spec["w"] / spec["h"]
            actual = width / height
            drift = abs(actual - target) / target
            checks.append(_check(
                "aspect_ratio", "pass" if drift <= RATIO_TOLERANCE else "block",
                f"{width}x{height} = {actual:.4f} vs {target:.4f} "
                f"({drift * 100:.2f}% off, tolerance {RATIO_TOLERANCE * 100:.0f}%)",
                value=round(drift, 4), limit=RATIO_TOLERANCE))
            min_w = spec.get("min_width")
            if min_w:
                checks.append(_check("min_dimension",
                                     "pass" if width >= min_w else "block",
                                     f"width {width} px (min {min_w})"))
            if mode not in ("RGB", "RGBA", "L"):
                checks.append(_check("colour", "warn",
                                     f"{mode}: convert to 8-bit sRGB before upload"))
            else:
                checks.append(_check("colour", "pass", f"{mode} (8-bit sRGB path)"))
        except Exception as exc:  # noqa: BLE001 - an unreadable file is a block
            checks.append(_check("decodable", "block",
                                 f"not a readable image: {type(exc).__name__}"))
    else:
        allowed = tuple(f.upper() for f in spec.get("formats", ()))
        ext = Path(filename).suffix.lstrip(".").upper() if filename else ""
        if ext:
            checks.append(_check("format", "pass" if ext in allowed else "block",
                                 f"{ext} (allowed {', '.join(allowed)})"))
        else:
            warnings.append("no filename given, so the container format was not checked")

    copy_caps = spec.get("copy") or {}
    if caption is not None and copy_caps:
        key, limit = next(iter(copy_caps.items()))
        status = "pass" if len(caption) <= limit else "block"
        checks.append(_check("caption_length", status,
                             f"{len(caption)} chars vs {key} cap {limit}",
                             value=len(caption), limit=limit))

    if spec.get("safe_area") or spec.get("safe_area_px"):
        checks.append(_check("safe_area", "manual",
                             "safe area is documented but its occupancy cannot be judged "
                             "from a flat asset — check placement in the composition"))

    blocked = [c for c in checks if c["status"] == "block"]
    return {
        "canvas": canvas,
        "ok": not blocked,
        "blocked": [c["id"] for c in blocked],
        "checks": checks,
        "warnings": warnings,
        "source": spec.get("source"),
        "confidence": spec.get("confidence"),
        "spec": {k: spec[k] for k in ("w", "h", "max_bytes") if k in spec},
        "unverified_rules": UNVERIFIED_RULES,
    }


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Validate a social asset before upload (local).")
    ap.add_argument("--canvas", required=True, choices=sorted(SPECS))
    ap.add_argument("--file", required=True)
    ap.add_argument("--caption", default=None)
    args = ap.parse_args(argv)
    payload = Path(args.file).read_bytes()
    report = validate(payload, args.canvas, caption=args.caption, filename=args.file)
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
