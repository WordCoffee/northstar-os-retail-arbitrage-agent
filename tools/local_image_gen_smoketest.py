"""Local image-generation smoke test — the ARMED lane, end to end.

Exercises the same core the Creative Studio UI calls
(``Northstar_backend.local_image_gen``), so a green run here means the wired
route will render too.

Gated and bounded, like ``local_flux_smoketest.py``:
  * dry-run by default — prints what would run, generates nothing;
  * ``--yes`` submits ONE job to the loopback engine;
  * refuses unless MEDIA_GEN_LIVE=1 and the engine is reachable (the core owns
    both checks — this script adds no bypass).

Usage:
    python tools/local_image_gen_smoketest.py --prompt "a red mug on pine"
    python tools/local_image_gen_smoketest.py --prompt "..." --yes
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from Northstar_backend import local_image_gen as lig  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Local image-generation smoke test (armed lane).")
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1024)
    ap.add_argument("--steps", type=int, default=28)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--yes", action="store_true", help="actually render ONE image")
    args = ap.parse_args(argv)

    armed = lig.media_gate_on()
    reachable = lig.engine_reachable()
    print(f"engine: {lig.engine_url()}  reachable: {reachable}  media_gate: {'on' if armed else 'off'}")

    if not args.yes:
        print("\nDRY RUN — the workflow that would be submitted:")
        import json
        print(json.dumps(lig.build_flux_workflow(args.prompt, args.width, args.height,
                                                 args.steps, args.seed or 0), indent=2))
        print("\nRe-run with --yes to render ONE image on the local engine.")
        return 0

    try:
        r = lig.generate_image(args.prompt, width=args.width, height=args.height,
                               steps=args.steps, seed=args.seed,
                               save_dir=_ROOT / "generated_images" / "creative")
    except lig.GenerationError as e:
        print(f"REFUSED [{e.code}] {e.message}", file=sys.stderr)
        return 2

    print(f"done in {r['seconds']}s — {r['width']}x{r['height']} · {r['bytes'] / 1024:.0f} KB · seed {r['seed']}")
    print(f"  prompt_id: {r['prompt_id']}")
    print(f"  saved:     {r['saved_path']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
