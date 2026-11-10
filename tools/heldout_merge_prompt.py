"""Merge the re-scored prompt-only rows into the held-out modes proof.

The first prompt-only pass marked all twelve briefs `cannot_verify` because the product-region check
was applied to a route that has no cutout by design. That is fixed, the twelve were re-rendered and
re-scored, and their rows replace the old ones here. The stored-reference rows are kept from the run
that produced them; merging keeps one proof per set rather than publishing two numbers for one mode.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent")
MODES = ROOT / "state" / "seller" / "heldout_modes_proof.json"
PROMPT = ROOT / "state" / "seller" / "heldout_prompt_only_proof3.json"


def main() -> int:
    modes = json.loads(MODES.read_text(encoding="utf-8"))
    prompt = json.loads(PROMPT.read_text(encoding="utf-8"))
    new_prompt = {str(row.get("brief_id")): row for row in prompt.get("results") or []}
    kept = [row for row in modes.get("results") or []
            if str(row.get("brief_id")) not in new_prompt]
    merged = kept + list(new_prompt.values())
    merged.sort(key=lambda row: str(row.get("brief_id")))
    modes["results"] = merged
    modes["prompt_only_rerun"] = {
        "proof": str(PROMPT.relative_to(ROOT)),
        "rows": len(new_prompt),
        "why": ("the first prompt-only pass failed every brief on a product-region check that does "
                "not apply to a route with no reference; the check now skips with a stated reason"),
    }
    MODES.write_text(json.dumps(modes, indent=2) + "\n", encoding="utf-8")
    prompt_rows = [row for row in merged if str(row.get("brief_id")).startswith("PO-")]
    print(json.dumps({
        "total_rows": len(merged),
        "prompt_only": len(prompt_rows),
        "prompt_only_passed": sum(1 for row in prompt_rows if row.get("passed")),
        "prompt_only_cannot_verify": sum(1 for row in prompt_rows if row.get("cannot_verify")),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
