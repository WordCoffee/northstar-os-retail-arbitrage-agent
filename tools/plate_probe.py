"""Save ONE real plate (and the composed picture) so the measurement can be
iterated offline instead of spending a lane start per attempt."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from tools import comfy_lane  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design", default="word-coffee-mug")
    parser.add_argument("--face", default="front")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1536)
    parser.add_argument("--out", default=str(Path.home() / "AppData" / "Local" / "Temp"
                                             / "opencode" / "plate_probe"))
    args = parser.parse_args()

    def work() -> dict:
        import brand_art as ba  # noqa: PLC0415
        import product_picture as pp  # noqa: PLC0415

        design = ba.design_for(args.design)
        result = pp.build(design, out_dir=args.out, out_root=str(Path(args.out).parent),
                          faces=(args.face,), width=args.width, height=args.height,
                          seed=args.seed)
        return result

    result = comfy_lane.lane(work, role="plate-probe")
    payload = result.get("result") or {}
    print(json.dumps({"ok": result.get("ok"), "build_ok": payload.get("ok"),
                      "faces": [{k: f.get(k) for k in ("face", "stage", "reason",
                                                       "bands", "quad", "file")}
                                for f in payload.get("faces") or []]}, indent=1))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
