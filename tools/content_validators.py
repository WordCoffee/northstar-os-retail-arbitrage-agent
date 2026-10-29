"""CLI wrapper for the kernel's content validators."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))
from agent_kernel.content import run  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", required=True)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    folder = Path(args.folder)
    out = run(folder)
    target = Path(args.out) if args.out else folder / "content_audit.json"
    target.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({"valid": out["valid"], "total": out["total"],
                      "rate": out["rate"],
                      "failed": [r["id"] for r in out["rows"] if not r["valid"]]},
                     indent=2))
    return 0 if out["valid"] == out["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
