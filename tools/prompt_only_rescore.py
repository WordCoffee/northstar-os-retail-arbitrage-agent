"""Rescore the prompt-only artefacts against the current scorer, and show the arithmetic.

The question this answers: why do several prompt-only briefs land on *exactly* 90.0?

The score is a weighted sum of binary checks, normalised by the weights of the checks that were
graded. For a prompt-only (full-generation) brief, `reference_subject` is not graded, so the
denominator is exactly 1.00 and each check contributes its own weight. Failing only `alpha_matte`
(weight 0.10) therefore scores 0.90 × 100 = 90.0, every time, for every brief — the number is a
constant of the rubric, not a coincidence of quality.

    python tools/prompt_only_rescore.py                 # table + explanation
    python tools/prompt_only_rescore.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _extra in (str(ROOT), str(ROOT / "tools")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

from seller_tester.scorers import DEFAULT_WEIGHTS, score_image  # noqa: E402

ARTEFACT_DIR = ROOT / "renders" / "heldout_prompt_only4"
BRIEFS = ROOT / "ty" / "seller_briefs_heldout_modes.json"


def load_briefs() -> list[dict]:
    data = json.loads(BRIEFS.read_text(encoding="utf-8"))
    briefs = data.get("briefs") if isinstance(data, dict) else data
    return [b for b in briefs if str(b.get("source_mode") or "") == "prompt_only"]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    rows = []
    for brief in load_briefs():
        path = ARTEFACT_DIR / f"{brief['id']}.png"
        if not path.is_file():
            rows.append({"brief": brief["id"], "situation": brief.get("situation"),
                         "status": "missing artefact"})
            continue
        result = score_image(path.read_bytes(), brief)
        checks = result.get("checks") or {}
        failed = [name for name, row in checks.items()
                  if not row.get("ok") and not row.get("skipped")]
        graded = [name for name, row in checks.items()
                  if not row.get("skipped")]
        rows.append({
            "brief": brief["id"],
            "situation": brief.get("situation"),
            "score": round(float(result.get("score") or 0.0), 1),
            "passed": bool(result.get("passed")),
            "failed": failed,
            "graded": graded,
            "weights_of_failures": {name: DEFAULT_WEIGHTS.get(name) for name in failed},
            "zero_score_checks": [name for name, row in checks.items() if row.get("score") == 0.0],
        })

    scored = [r for r in rows if "score" in r]
    n = len(scored)
    passed = sum(1 for r in scored if r["passed"])
    mean = round(sum(r["score"] for r in scored) / n, 1) if n else 0.0
    at_90 = [r["brief"] for r in scored if r["score"] == 90.0]

    payload = {
        "mode": "prompt-only",
        "artefact_dir": str(ARTEFACT_DIR.relative_to(ROOT)).replace("\\", "/"),
        "n": n, "passed": passed, "mean": mean,
        "pass_bar": 70,
        "at_exactly_90": at_90,
        "rows": rows,
        "weights": DEFAULT_WEIGHTS,
        "why_90": (
            "score = 100 x (weight of passed graded checks) / (weight of graded checks). "
            "A prompt-only brief does not grade reference_subject, so the denominator is 1.00. "
            "A plate with no alpha channel fails alpha_matte (0.10) and nothing else, which is "
            "exactly 90.0 — the constant, not a quality score."),
    }

    if ns.json:
        print(json.dumps(payload, indent=2))
        return 0

    print(f"prompt-only: n={n}, passed={passed}, mean={mean}  (bar 70)")
    print(f"at exactly 90.0: {len(at_90)} — {', '.join(at_90) or 'none'}")
    print()
    print("| brief | situation | score | passed | failed checks (weight) |")
    print("|---|---|---|---|---|")
    for r in scored:
        failed = ", ".join(f"{k} ({v:.2f})" for k, v in r["weights_of_failures"].items()) or "—"
        print(f"| {r['brief']} | {r['situation']} | {r['score']} | "
              f"{'yes' if r['passed'] else 'no'} | {failed} |")
    print()
    print(payload["why_90"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
