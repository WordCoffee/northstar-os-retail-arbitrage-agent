"""Run AdPilot's ad-copy pass and write its score where the scorecards read it.

Two outputs, on purpose: the proof (`state/seller/ad_copy_proof.json`, every row and every check)
and the published score (`ty/seller_scores.json` → services.adpilot), so a reader can always get
from the number back to the evidence.

    python tools/seller_tester/ad_copy_run.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from seller_tester import ad_copy  # noqa: E402

PROOF = ROOT / "state" / "seller" / "ad_copy_proof.json"
SCORES = ROOT / "ty" / "seller_scores.json"


def main() -> int:
    result = ad_copy.run_all()
    result["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    result["population"] = "service-path"
    result["note"] = ("recorded fixtures of AdPilot's own output shape; the checks are the app's "
                      "deterministic rules, never a model verdict. AD-006 is a kept failure.")
    PROOF.parent.mkdir(parents=True, exist_ok=True)
    PROOF.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    scores = json.loads(SCORES.read_text(encoding="utf-8")) if SCORES.is_file() else {}
    services = scores.setdefault("services", {})
    services["adpilot"] = {
        "mean": result["mean"],
        "scored": result["scored"],
        "passed": result["passed"],
        "at": result["at"],
        "population": "service-path",
        "path": "ad_copy",
        "proof": str(PROOF.relative_to(ROOT)).replace("\\", "/"),
        "note": "adpilot's own ad copy; a kept failure (AD-006, two variants) is in the population",
    }
    scores["at"] = result["at"]
    SCORES.write_text(json.dumps(scores, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"scored": result["scored"], "passed": result["passed"],
                      "mean": result["mean"], "proof": str(PROOF.relative_to(ROOT))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
