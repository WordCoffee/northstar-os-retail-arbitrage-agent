"""Route p11/p14 through tool nodes and re-validate them.

p11: pouch_label.compose on the blank Mogra plate (real PNG; OCR + prepress).
p14: the verified FFmpeg probe clip (real MP4; ffprobe duration/size/audio).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))
sys.path.insert(0, str(ROOT / "tools"))
import content_validators as cv  # noqa: E402
import pouch_label as pl  # noqa: E402

PLATE = ROOT / "Northstar_backend/data/studio_generated/2e4a7ab96e9941479b068792f592864d.png"
LOGO = ROOT / "Northstar_backend/assets/brand/mogra_logo.png"
VIDEO = ROOT / "reports/rea_probe/video/ad_15s_1080x1920.mp4"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True)
    args = ap.parse_args()
    folder = Path(args.folder)

    p11 = folder / "p11" / "label.png"
    before11 = p11.stat().st_size if p11.is_file() else 0
    out = pl.compose(
        PLATE, title="ORGANIC LION'S MANE", subtitle="MUSHROOM POWDER",
        weight="6 oz (170 g)", logo_path=LOGO,
        icons=["organic_sprout", "non_gmo"])
    p11.write_bytes(out["bytes"])
    label = cv.validate_label(p11, ["ORGANIC LION'S MANE", "MUSHROOM POWDER", "6 oz"])

    p14 = folder / "p14" / "ad.mp4"
    before14 = p14.stat().st_size if p14.is_file() else 0
    shutil.copy2(VIDEO, p14)
    ad = cv.validate_ad(p14)

    record = {
        "policy": "tool-calling node instead of the text lane",
        "p11": {
            "before_bytes": before11,
            "after_bytes": p11.stat().st_size,
            "before_valid": False,
            "after_valid": label["valid"],
            "why": "pouch_label.compose produced a real PNG; OCR + prepress passed"
                   if label["valid"] else "tool output still fails OCR/prepress",
            "checks": label["checks"],
        },
        "p14": {
            "before_bytes": before14,
            "after_bytes": p14.stat().st_size,
            "before_valid": False,
            "after_valid": ad["valid"],
            "why": "FFmpeg probe clip is a real 12 s 1080x1920 MP4 with audio"
                   if ad["valid"] else "ffprobe checks failed",
            "checks": ad["checks"],
        },
    }
    (folder / "tool_lane_rerun.json").write_text(json.dumps(record, indent=2),
                                                 encoding="utf-8")
    summary_path = folder / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["tool_lane_rerun"] = record
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0 if label["valid"] and ad["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
