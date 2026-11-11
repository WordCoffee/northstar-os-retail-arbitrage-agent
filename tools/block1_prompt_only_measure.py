"""Block 1: measure the prompt-only mode from the artefacts on disk, check by check.

Publishes two things and nothing else:

1. a **per-check table** — every brief against every check, pass / fail / not-applicable;
2. a **per-mode table** — n, pass, mean, one row per input mode, never blended.

The bar is read from the briefs and printed, not changed. `--dir` selects the artefact set, so the
same instrument can be pointed at any run and the numbers compared.

    python tools/block1_prompt_only_measure.py --dir renders/heldout_prompt_only8 --write
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for _extra in (str(ROOT), str(ROOT / "tools")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

from seller_tester.scorers import DEFAULT_WEIGHTS, score_image  # noqa: E402

CATALOG = ROOT / "ty" / "seller_briefs_heldout_modes.json"
CHECK_ORDER = ["dimensions", "aspect", "background", "subject_fill", "alpha_matte",
               "file_size", "text_free", "reference_subject"]


def briefs(mode: str) -> list[dict]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    rows = data.get("briefs") if isinstance(data, dict) else data
    return [b for b in rows if str(b.get("source_mode") or "") == mode]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default="renders/heldout_prompt_only8")
    parser.add_argument("--mode", default="prompt_only")
    parser.add_argument("--write", action="store_true")
    ns = parser.parse_args(argv)

    art_dir = ROOT / ns.dir
    rows = []
    missing = []
    for brief in briefs(ns.mode):
        path = art_dir / f"{brief['id']}.png"
        if not path.is_file():
            missing.append(brief["id"])
            continue
        result = score_image(path.read_bytes(), brief)
        checks = result.get("checks") or {}
        rows.append({
            "brief": brief["id"],
            "situation": brief.get("situation"),
            "route": result.get("route"),
            "bar": result.get("pass_score"),
            "score": float(result.get("score") or 0.0),
            "passed": bool(result.get("passed")),
            "checks": {name: {"ok": c.get("ok"), "skipped": bool(c.get("skipped")),
                              "detail": c.get("detail")}
                       for name, c in checks.items() if name in CHECK_ORDER},
        })

    n = len(rows)
    passed = sum(1 for r in rows if r["passed"])
    mean = round(sum(r["score"] for r in rows) / n, 1) if n else 0.0
    fails = Counter()
    for row in rows:
        for name, c in row["checks"].items():
            if c["skipped"] or c["ok"]:
                continue
            fails[name] += 1

    payload = {
        "mode": ns.mode,
        "artefact_dir": str(art_dir.relative_to(ROOT)).replace("\\", "/"),
        "n": n, "passed": passed, "failed": n - passed, "mean": mean,
        "pass_rate": round(100.0 * passed / n, 1) if n else 0.0,
        "missing_artefacts": missing,
        "check_failures": dict(fails),
        "weights": DEFAULT_WEIGHTS,
        "rows": rows,
        "note": ("the bar is each brief's own pass_score, printed per row; no weight and no bar "
                 "was changed for this measurement"),
    }

    if ns.write:
        out = ROOT / "reports" / "ty" / "block1_prompt_only_measured.json"
        out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        lines = [
            "# Block 1 — prompt-only, measured from the artefacts on disk",
            "",
            f"Artefacts: `{payload['artefact_dir']}`. Scored with the current instrument "
            f"(`tools/seller_tester/scorers.py`). **No bar and no weight was changed.**",
            "",
            f"**n {n} · pass {passed} · mean {mean}** (per-mode row; not a blended headline).",
            "",
            "## Per-check table",
            "",
            "`P` pass · `F` fail · `–` not applicable to this brief (recorded as skipped, with a reason)",
            "",
            "| brief | situation | score | passed | " + " | ".join(CHECK_ORDER) + " |",
            "|---|---|---|---|" + "---|" * len(CHECK_ORDER),
        ]
        for row in rows:
            cells = []
            for name in CHECK_ORDER:
                c = row["checks"].get(name)
                if c is None:
                    cells.append("·")
                elif c["skipped"]:
                    cells.append("–")
                else:
                    cells.append("P" if c["ok"] else "F")
            lines.append(f"| {row['brief']} | {row['situation']} | {row['score']} | "
                         f"{'yes' if row['passed'] else 'no'} | " + " | ".join(cells) + " |")
        lines += ["", "## Which checks fail, and on how many briefs", "",
                  "| check | briefs failing |", "|---|---|"]
        for name in CHECK_ORDER:
            lines.append(f"| `{name}` | {fails.get(name, 0)} |")
        lines += ["", "## Details for every non-passing cell", "",
                  "| brief | check | measurement |", "|---|---|---|"]
        for row in rows:
            for name, c in row["checks"].items():
                if c["skipped"] or c["ok"]:
                    continue
                lines.append(f"| {row['brief']} | `{name}` | {c['detail']} |")
        lines += ["", "· = check not run for this brief (a composite-only check on a full "
                  "generation). – = recorded as not applicable.", ""]
        (ROOT / "reports" / "ty" / "block1_prompt_only_measured.md").write_text(
            "\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote reports/ty/block1_prompt_only_measured.md ({n} rows, mean {mean})")
        return 0

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
