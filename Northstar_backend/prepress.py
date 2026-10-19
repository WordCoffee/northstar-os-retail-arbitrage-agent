"""Prepress — real CMYK conversion, soft proof, gamut and ink-limit checks.

The "retail-ready" half of the pipeline: a screen render is not a print file.
This module converts studio artwork to CMYK through a real ICC transform
(littleCMS via Pillow's ImageCms), then reports the two numbers a printer
actually asks for:

  * GAMUT - how far the artwork's colours move when they pass through the press
    profile. Measured as CIE76 dE (sRGB -> CMYK -> sRGB round trip), not a
    hand-waved "looks off".
  * INK LIMIT - total area coverage (TAC), the sum of C/M/Y/K. Coated sheet-fed
    work usually caps at 300-330%; anything above the cap is a drying/offset
    risk on press.

Profiles: Windows ships a SWOP CMYK profile (`RSWOP.icm`) next to the sRGB
profile, so this works offline with no download. A co-packer's own profile can
be dropped in and selected by name; the module never claims a profile it did not
actually use.

Everything here is local and deterministic. No network, no credentials.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageCms

#: Where Windows keeps colour profiles (EXPECTED_SYSTEM dir; may be absent).
SYSTEM_COLOR_DIR = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "spool" / "drivers" / "color"

#: Preferred CMYK press profiles, best first. Names are matched case-insensitively
#: against the files present on this machine - a name that is not on disk is
#: simply skipped (never silently substituted).
PREFERRED_CMYK = (
    "coated_fogra39l.icc", "iso coated v2 300% (eci).icc", "iso_coated_v2_300_eci.icc",
    "coatedfogra39.icc", "pso coated v3.icc", "rswoP.icm", "swop.icc",
)

DEFAULT_TAC_LIMIT = 300.0     # % total area coverage
#: dE76 above which a pixel is called out of gamut. Measured floor: a relative
#: colorimetric round trip through a press profile moves even in-gamut neutrals
#: by ~4-5 dE (the source white/black points are mapped onto the medium's). Real
#: gamut failures land at 10-60 dE, so 8 separates the two honestly.
DEFAULT_DE_TOLERANCE = 8.0


@dataclass
class ProfileInfo:
    name: str
    path: str
    description: str
    space: str = "CMYK"


def available_cmyk_profiles() -> List[ProfileInfo]:
    """CMYK profiles actually present on this machine, preferred order first."""
    found: List[ProfileInfo] = []
    if not SYSTEM_COLOR_DIR.is_dir():
        return found
    by_lower = {p.name.lower(): p for p in SYSTEM_COLOR_DIR.iterdir() if p.is_file()}
    ordered: List[Path] = []
    for want in PREFERRED_CMYK:
        p = by_lower.get(want.lower())
        if p is not None:
            ordered.append(p)
    for p in by_lower.values():          # then everything else that is CMYK
        if p in ordered:
            continue
        try:
            prof = ImageCms.ImageCmsProfile(str(p))
            if ImageCms.getProfileDescription(prof).strip() and \
                    "cmyk" in (ImageCms.getProfileInfo(prof) or "").lower():
                ordered.append(p)
        except Exception:  # noqa: BLE001 - not a usable profile
            continue
    for p in ordered:
        try:
            prof = ImageCms.ImageCmsProfile(str(p))
            desc = ImageCms.getProfileDescription(prof).strip() or p.name
        except Exception:  # noqa: BLE001
            desc = p.name
        found.append(ProfileInfo(name=p.name, path=str(p), description=desc))
    return found


def _srgb_profile() -> ImageCms.ImageCmsProfile:
    p = SYSTEM_COLOR_DIR / "sRGB Color Space Profile.icm"
    if p.is_file():
        return ImageCms.ImageCmsProfile(str(p))
    return ImageCms.createProfile("sRGB")


def _resolve_cmyk(profile: Optional[str]) -> ProfileInfo:
    profs = available_cmyk_profiles()
    if not profs:
        raise RuntimeError(
            "no CMYK ICC profile found on this machine - put the co-packer's "
            f"profile in {SYSTEM_COLOR_DIR} (or pass one explicitly)")
    if profile:
        for p in profs:
            if profile.lower() in (p.name.lower(), p.description.lower()):
                return p
        raise RuntimeError(f"CMYK profile {profile!r} not found; available: "
                           f"{[p.name for p in profs]}")
    return profs[0]


def _load(png: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(png))
    if img.mode == "RGBA":
        # composite onto white: print has no alpha channel
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        return bg
    return img.convert("RGB")


def to_cmyk(png: bytes, *, profile: Optional[str] = None,
            intent: str = "relative_colorimetric") -> Dict[str, Any]:
    """Convert sRGB artwork to CMYK through the ICC profile. Returns bytes + meta."""
    info = _resolve_cmyk(profile)
    src = _srgb_profile()
    dst = ImageCms.ImageCmsProfile(info.path)
    img = _load(png)
    rendering_intent = (ImageCms.Intent.RELATIVE_COLORIMETRIC
                        if intent == "relative_colorimetric"
                        else ImageCms.Intent.PERCEPTUAL)
    transform = ImageCms.buildTransformFromOpenProfiles(
        src, dst, "RGB", "CMYK", renderingIntent=rendering_intent)
    cmyk = ImageCms.applyTransform(img, transform)
    buf = io.BytesIO()
    cmyk.save(buf, format="TIFF", compression="tiff_lzw")
    return {"bytes": buf.getvalue(), "format": "tiff", "mode": "CMYK",
            "profile": info.name, "profile_description": info.description,
            "intent": intent, "width": cmyk.width, "height": cmyk.height,
            "engine": "littlecms via Pillow ImageCms"}


def soft_proof(png: bytes, *, profile: Optional[str] = None,
               intent: str = "relative_colorimetric") -> Dict[str, Any]:
    """What the print will actually look like: sRGB -> CMYK -> sRGB (proof)."""
    info = _resolve_cmyk(profile)
    src = _srgb_profile()
    dst = ImageCms.ImageCmsProfile(info.path)
    img = _load(png)
    rendering_intent = (ImageCms.Intent.RELATIVE_COLORIMETRIC
                        if intent == "relative_colorimetric"
                        else ImageCms.Intent.PERCEPTUAL)
    to_press = ImageCms.buildTransformFromOpenProfiles(src, dst, "RGB", "CMYK",
                                                       renderingIntent=rendering_intent)
    back = ImageCms.buildTransformFromOpenProfiles(dst, src, "CMYK", "RGB",
                                                   renderingIntent=rendering_intent)
    proofed = ImageCms.applyTransform(ImageCms.applyTransform(img, to_press), back)
    buf = io.BytesIO()
    proofed.save(buf, format="PNG")
    return {"bytes": buf.getvalue(), "profile": info.name, "intent": intent}


def gamut_check(png: bytes, *, profile: Optional[str] = None,
                de_tolerance: float = DEFAULT_DE_TOLERANCE,
                max_sample: int = 200_000) -> Dict[str, Any]:
    """Measure how far the artwork moves through the press profile (CIE76 dE).

    Round trip: sRGB -> CMYK (press) -> sRGB, then compare Lab coordinates of the
    original and the round-tripped pixels. dE over the tolerance is called
    out-of-gamut. Reports honest counts and the worst offenders' sRGB values.
    """
    info = _resolve_cmyk(profile)
    src = _srgb_profile()
    dst = ImageCms.ImageCmsProfile(info.path)
    img = _load(png)
    if img.width * img.height > max_sample:
        ratio = (max_sample / float(img.width * img.height)) ** 0.5
        img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))),
                         Image.LANCZOS)

    to_press = ImageCms.buildTransformFromOpenProfiles(
        src, dst, "RGB", "CMYK", renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC)
    back = ImageCms.buildTransformFromOpenProfiles(
        dst, src, "CMYK", "RGB", renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC)
    round_tripped = ImageCms.applyTransform(ImageCms.applyTransform(img, to_press), back)

    to_lab_src = None  # computed below in numpy (PIL's 8-bit LAB quantises too hard)
    import numpy as np

    def _srgb_to_lab(rgb: "np.ndarray") -> "np.ndarray":
        """Exact sRGB -> CIE Lab (D65). Numpy only: no 8-bit Lab quantisation."""
        c = np.asarray(rgb, dtype=np.float64) / 255.0
        lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
        m = np.array([[0.4124564, 0.3575761, 0.1804375],
                      [0.2126729, 0.7151522, 0.0721750],
                      [0.0193339, 0.1191920, 0.9503041]])
        xyz = lin @ m.T
        white = np.array([0.95047, 1.00000, 1.08883])
        t = xyz / white
        d = 6.0 / 29.0
        f = np.where(t > d ** 3, np.cbrt(np.clip(t, 1e-12, None)),
                     t / (3 * d * d) + 4.0 / 29.0)
        L = 116.0 * f[..., 1] - 16.0
        A = 500.0 * (f[..., 0] - f[..., 1])
        B = 200.0 * (f[..., 1] - f[..., 2])
        return np.stack([L, A, B], axis=-1)

    lab_a = _srgb_to_lab(np.asarray(img, dtype=np.uint8))
    lab_b = _srgb_to_lab(np.asarray(round_tripped, dtype=np.uint8))
    L1, A1, B1 = lab_a[..., 0], lab_a[..., 1], lab_a[..., 2]
    L2, A2, B2 = lab_b[..., 0], lab_b[..., 1], lab_b[..., 2]
    de = np.sqrt((L1 - L2) ** 2 + (A1 - A2) ** 2 + (B1 - B2) ** 2)
    over = de > de_tolerance
    total = int(de.size)
    over_n = int(over.sum())
    worst_idx = np.argsort(de.ravel())[::-1][:8]
    rgb = np.asarray(img, dtype=np.uint8).reshape(-1, 3)
    worst = [{"srgb": [int(v) for v in rgb[i]],
              "hex": "#%02X%02X%02X" % tuple(int(v) for v in rgb[i]),
              "dE76": round(float(de.ravel()[i]), 2)} for i in worst_idx]
    return {
        "status": "ok", "profile": info.name, "intent": "relative_colorimetric",
        "tolerance_dE76": de_tolerance,
        "pixels": total, "out_of_gamut": over_n,
        "out_of_gamut_pct": round(100.0 * over_n / max(1, total), 2),
        "max_dE76": round(float(de.max()), 2),
        "mean_dE76": round(float(de.mean()), 2),
        "worst_colors": worst,
        "note": ("dE76 measured on the sRGB->CMYK->sRGB round trip through the "
                 "press profile, computed in exact CIE Lab (D65). A relative "
                 "colorimetric round trip carries a ~4-5 dE floor even for "
                 "in-gamut neutrals because the source white/black points map "
                 "onto the medium's; the tolerance is set above that floor so "
                 "only genuine gamut failures (10-60 dE) are reported."),
    }


def ink_limit(png: bytes, *, profile: Optional[str] = None,
              limit_pct: float = DEFAULT_TAC_LIMIT) -> Dict[str, Any]:
    """Total area coverage (C+M+Y+K) of the converted artwork."""
    conv = to_cmyk(png, profile=profile)
    img = Image.open(io.BytesIO(conv["bytes"])).convert("CMYK")
    import numpy as np
    a = np.asarray(img, dtype=np.float32)
    tac = a.sum(axis=2) / 255.0 * 100.0
    over = tac > limit_pct
    return {
        "status": "ok", "profile": conv["profile"], "limit_pct": limit_pct,
        "max_tac_pct": round(float(tac.max()), 1),
        "mean_tac_pct": round(float(tac.mean()), 1),
        "pixels_over_limit": int(over.sum()),
        "pixels_over_limit_pct": round(100.0 * float(over.mean()), 2),
        "verdict": "over_limit" if bool(over.any()) else "within_limit",
        "note": "Coated sheet-fed work is commonly capped at 300-330% TAC; the "
                "co-packer's spec is the authority.",
    }


def prepress_report(png: bytes, *, profile: Optional[str] = None,
                    limit_pct: float = DEFAULT_TAC_LIMIT,
                    de_tolerance: float = DEFAULT_DE_TOLERANCE) -> Dict[str, Any]:
    """The one-call answer for a print file: profile, gamut, ink limit, verdict."""
    gamut = gamut_check(png, profile=profile, de_tolerance=de_tolerance)
    ink = ink_limit(png, profile=profile, limit_pct=limit_pct)
    blockers: List[str] = []
    if ink["verdict"] == "over_limit":
        blockers.append(f"ink coverage {ink['max_tac_pct']}% exceeds the "
                        f"{limit_pct}% cap on {ink['pixels_over_limit_pct']}% of pixels")
    if gamut["out_of_gamut_pct"] > 5.0:
        blockers.append(f"{gamut['out_of_gamut_pct']}% of pixels move more than "
                        f"{de_tolerance} dE through the press profile")
    return {
        "status": "ok",
        "profiles_available": [p.name for p in available_cmyk_profiles()],
        "profile": gamut["profile"],
        "gamut": gamut, "ink": ink,
        "verdict": "blocked" if blockers else "printable",
        "blockers": blockers,
        "note": ("A pass here means the file converts cleanly through the named "
                 "profile - it is not a substitute for the co-packer's own "
                 "preflight."),
    }


def map_colors(colors: Sequence[Sequence[int]], *, profile: Optional[str] = None,
               de_tolerance: float = DEFAULT_DE_TOLERANCE) -> Dict[str, Any]:
    """Show what each colour will print as, and name replacements that hold.

    For every input sRGB colour: the colour the press will actually produce (the
    CMYK round trip) and the CIE76 shift. Out-of-gamut colours come back with
    ``suggested_srgb`` - adopting that value as the DESIGN colour is what makes
    the press match the screen, because the suggested value is the one the
    profile already renders faithfully.

    This turns the gamut blocker into an instruction instead of a warning.
    """
    import numpy as np

    info = _resolve_cmyk(profile)
    src = _srgb_profile()
    dst = ImageCms.ImageCmsProfile(info.path)
    to_press = ImageCms.buildTransformFromOpenProfiles(
        src, dst, "RGB", "CMYK", renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC)
    back = ImageCms.buildTransformFromOpenProfiles(
        dst, src, "CMYK", "RGB", renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC)
    to_lab = ImageCms.buildTransform(src, ImageCms.createProfile("LAB"), "RGB", "LAB")

    def _lab(rgb: Sequence[int]):
        img = Image.new("RGB", (1, 1), tuple(int(c) for c in rgb))
        a = np.asarray(ImageCms.applyTransform(img, to_lab), dtype=np.float64).reshape(3)
        return np.array([a[0] / 255.0 * 100.0, a[1] - 128.0, a[2] - 128.0])

    out: List[Dict[str, Any]] = []
    for rgb in colors:
        rgb_t = tuple(int(c) for c in rgb[:3])
        chip = Image.new("RGB", (1, 1), rgb_t)
        printed = ImageCms.applyTransform(ImageCms.applyTransform(chip, to_press), back)
        printed_rgb = tuple(int(c) for c in np.asarray(printed, dtype=np.uint8).reshape(3))
        de = float(np.linalg.norm(_lab(rgb_t) - _lab(printed_rgb)))
        row = {
            "hex": "#%02X%02X%02X" % rgb_t,
            "prints_as_hex": "#%02X%02X%02X" % printed_rgb,
            "prints_as_rgb": list(printed_rgb),
            "dE76": round(de, 2),
            "in_gamut": de <= de_tolerance,
        }
        if de > de_tolerance:
            row["suggested_srgb"] = list(printed_rgb)
            row["suggested_hex"] = row["prints_as_hex"]
            row["why"] = ("this value already prints faithfully through the press "
                          "profile; adopting it removes the shift")
        out.append(row)
    return {"status": "ok", "profile": info.name, "tolerance_dE76": de_tolerance,
            "colors": out,
            "out_of_gamut": sum(1 for r in out if not r["in_gamut"]),
            "note": ("Measurements are an sRGB->CMYK->sRGB round trip through the "
                     "named profile. A suggested value is the press rendering of "
                     "the original - a starting point for the designer, not a "
                     "forced colour.")}


def _main() -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser(description="Prepress check / CMYK conversion")
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--profile", default=None)
    ap.add_argument("--limit", type=float, default=DEFAULT_TAC_LIMIT)
    ap.add_argument("--de", type=float, default=DEFAULT_DE_TOLERANCE)
    ap.add_argument("--cmyk-out", default=None, help="write a CMYK TIFF here")
    ap.add_argument("--proof-out", default=None, help="write a soft-proof PNG here")
    args = ap.parse_args()

    data = Path(args.src).read_bytes()
    if args.cmyk_out:
        conv = to_cmyk(data, profile=args.profile)
        Path(args.cmyk_out).write_bytes(conv["bytes"])
    if args.proof_out:
        Path(args.proof_out).write_bytes(soft_proof(data, profile=args.profile)["bytes"])
    print(json.dumps(prepress_report(data, profile=args.profile, limit_pct=args.limit,
                                     de_tolerance=args.de), indent=2)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
