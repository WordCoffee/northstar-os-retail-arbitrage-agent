"""Generate the synthetic fixture pairs that prove the diff works.

These exist so the gate can be verified with **no server and no browser**: four
pairs that must fail and two that must pass. Each pair is a scene drawn twice —
once as the baseline, once with exactly one thing changed — so a verdict can be
attributed to a cause rather than to "something moved somewhere".

    python -m tools.visual_regression.make_fixtures           # write PNGs
    python -m tools.visual_regression.make_fixtures --check   # verify up to date

Rendering is supersampled 4x and downsampled with LANCZOS, then every pair is
written with fixed, non-timestamped input, so the bytes are reproducible.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from PIL import Image, ImageChops, ImageDraw, ImageFont

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
WIDTH, HEIGHT = 400, 260
SS = 4  # supersample factor


def _font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size * SS)
    except TypeError:  # very old Pillow: bitmap font only, still deterministic
        return ImageFont.load_default()


def render(
    *,
    dx: float = 0.0,
    dy: float = 0.0,
    recolour: bool = False,
    revenue: str = "Revenue $12,480",
    noise: int = 0,
    noise_seed: int = 3,
) -> Image.Image:
    """Draw the fixture scene. ``dx``/``dy`` are in final-image pixels."""
    img = Image.new("RGB", (WIDTH * SS, HEIGHT * SS), (246, 243, 236))
    draw = ImageDraw.Draw(img)
    ox, oy = int(round(dx * SS)), int(round(dy * SS))

    draw.rounded_rectangle(
        [24 * SS + ox, 40 * SS + oy, 244 * SS + ox, 168 * SS + oy],
        8 * SS,
        fill=(255, 255, 255),
        outline=(31, 58, 45),
        width=SS,
    )
    accent = (196, 120, 42) if recolour else (31, 94, 68)
    draw.rectangle(
        [40 * SS + ox, 60 * SS + oy, 90 * SS + ox, 104 * SS + oy], fill=accent
    )
    draw.text((100 * SS + ox, 60 * SS + oy), "Northstar OS", font=_font(18), fill=(24, 32, 28))
    draw.text((100 * SS + ox, 88 * SS + oy), "margin 41.2%", font=_font(13), fill=(70, 78, 72))
    draw.text((40 * SS + ox, 118 * SS + oy), revenue, font=_font(13), fill=(70, 78, 72))
    draw.text((40 * SS + ox, 140 * SS + oy), "ledger \u00b7 watch \u00b7 prospector", font=_font(11), fill=(120, 128, 122))

    for i in range(6):
        draw.rectangle(
            [30 * SS + i * 58 * SS, 190 * SS, 30 * SS + i * 58 * SS + 44 * SS, 236 * SS],
            fill=(216, 224, 214),
        )

    out = img.resize((WIDTH, HEIGHT), Image.LANCZOS)

    if noise:
        import numpy as np

        rng = np.random.default_rng(noise_seed)
        arr = np.asarray(out, dtype=np.int16)
        jitter = rng.integers(-noise, noise + 1, size=arr.shape)
        out = Image.fromarray(np.clip(arr + jitter, 0, 255).astype("uint8"), "RGB")
    return out


#: pair name -> (baseline render kwargs, candidate render kwargs, expected verdict, case, why)
PAIRS: List[Dict[str, Any]] = [
    {
        "pair": "identical",
        "case": "identical",
        "expected": "pass",
        "why": "same deterministic render; a gate that fails this is pure noise",
        "baseline": {},
        "candidate": {},
    },
    {
        "pair": "antialias",
        "case": "antialias",
        "expected": "pass",
        "why": "half-pixel re-render: the antialias tolerance must absorb it",
        "baseline": {},
        "candidate": {"dx": 0.4},
    },
    {
        "pair": "noise",
        "case": "noise",
        "expected": "pass",
        "why": "uniform +/-6 channel jitter, below the perceptual threshold",
        "baseline": {},
        "candidate": {"noise": 6},
    },
    {
        "pair": "moved",
        "case": "moved",
        "expected": "fail",
        "why": "card translated 28px to the right",
        "baseline": {},
        "candidate": {"dx": 28},
    },
    {
        "pair": "recolour",
        "case": "recolour",
        "expected": "fail",
        "why": "accent block pine #1f5e44 -> amber #c4782a",
        "baseline": {},
        "candidate": {"recolour": True},
    },
    {
        "pair": "text",
        "case": "text",
        "expected": "fail",
        "why": "revenue figure $12,480 -> $48,210 (small area, must still be caught)",
        "baseline": {},
        "candidate": {"revenue": "Revenue $48,210"},
    },
]


def build_all(out_dir: Path = FIXTURES_DIR) -> Dict[str, Any]:
    manifest: Dict[str, Any] = {"schema": "northstar.visual_fixtures.v1", "fixtures": []}
    for spec in PAIRS:
        pair_dir = out_dir / spec["pair"]
        pair_dir.mkdir(parents=True, exist_ok=True)
        baseline = render(**spec["baseline"])
        candidate = render(**spec["candidate"])
        baseline.save(pair_dir / "baseline.png", optimize=True)
        candidate.save(pair_dir / "candidate.png", optimize=True)
        identical_bytes = ImageChops.difference(baseline, candidate).getbbox() is None
        manifest["fixtures"].append(
            {
                "pair": spec["pair"],
                "case": spec["case"],
                "expected": spec["expected"],
                "why": spec["why"],
                "baseline": f"{spec['pair']}/baseline.png",
                "candidate": f"{spec['pair']}/candidate.png",
                "images_identical": identical_bytes,
            }
        )
    (out_dir / "expected.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the committed fixtures")
    args = parser.parse_args(argv)

    if not args.check:
        manifest = build_all()
        print(f"wrote {len(manifest['fixtures'])} fixture pairs to {FIXTURES_DIR}")
        return 0

    expected_path = FIXTURES_DIR / "expected.json"
    if not expected_path.exists():
        print("MISSING: fixtures/expected.json", file=sys.stderr)
        return 1
    committed = json.loads(expected_path.read_text(encoding="utf-8"))
    problems = []
    for item in committed["fixtures"]:
        for key in ("baseline", "candidate"):
            path = FIXTURES_DIR / item[key]
            if not path.exists():
                problems.append(f"missing {path.relative_to(FIXTURES_DIR)}")
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    print(f"OK: {len(committed['fixtures'])} fixture pairs present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
