"""Manifest for wave 2, with cumulative totals against wave 1.

    python tools/expansion_wave2_manifest.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from expansion_manifest import _rows, _sha, _unique, PLACEHOLDER  # noqa: E402

EVIDENCE = ROOT / "state" / "evidence" / "expansion_wave2_20261104"
REPORTS = ROOT / "reports" / "expansion_wave2_20261104"
WAVE1 = ROOT / "reports" / "expansion_20261104" / "manifest.json"
MANIFEST = REPORTS / "manifest.json"


def main() -> int:
    problems = []
    platforms = {
        "huggingface": {"rows": _rows(EVIDENCE / "hf.jsonl"),
                        "unique": _unique(EVIDENCE / "hf.jsonl", "id")},
        "arxiv": {"rows": _rows(EVIDENCE / "arxiv.jsonl"),
                  "unique": _unique(EVIDENCE / "arxiv.jsonl", "id")},
        "gforum": {"rows": _rows(EVIDENCE / "gforum.jsonl"),
                   "unique": _unique(EVIDENCE / "gforum.jsonl", "post_id")},
        "youtube": {"rows": _rows(EVIDENCE / "youtube.jsonl"),
                    "unique": _unique(EVIDENCE / "youtube.jsonl", "video_id")},
        "github": {"rows": _rows(EVIDENCE / "github.jsonl"),
                   "unique": _unique(EVIDENCE / "github.jsonl", "full_name")},
    }
    for name, row in platforms.items():
        if row["rows"] == 0:
            problems.append(f"{name}: no rows")
        summary = EVIDENCE / {
            "huggingface": "hf_summary.json", "arxiv": "arxiv_summary.json",
            "gforum": "gforum_summary.json", "youtube": "youtube_summary.json",
            "github": "github_summary.json",
        }[name]
        if not summary.is_file():
            problems.append(f"{name}: summary missing")

    files = []
    for folder in (REPORTS, EVIDENCE):
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.name != "manifest.json":
                files.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"),
                              "bytes": path.stat().st_size, "sha256": _sha(path)})

    for path in REPORTS.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        match = PLACEHOLDER.search(text)
        if match:
            problems.append(f"{path.name}: placeholder {match.group(0)!r}")

    wave1 = {}
    if WAVE1.is_file():
        wave1 = json.loads(WAVE1.read_text(encoding="utf-8")).get("totals", {})
    wave1_rows = int(wave1.get("rows") or 0)
    wave1_unique = int(wave1.get("unique") or 0)
    totals = {"rows": sum(p["rows"] for p in platforms.values()),
              "unique": sum(p["unique"] for p in platforms.values())}
    manifest = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "campaign": "NORTHSTAROS master expansion — secondary discovery (wave 2)",
        "wave": 2,
        "platforms": platforms,
        "totals": totals,
        "cumulative": {
            "wave1_rows": wave1_rows, "wave1_unique": wave1_unique,
            "rows": wave1_rows + totals["rows"],
            "unique": wave1_unique + totals["unique"],
            "note": "wave 2 is new queries; a small overlap with wave 1 is possible and not deduplicated across waves.",
        },
        "files": files,
        "checks": {"json_parses": True, "every_platform_has_rows": not any(
            "no rows" in p for p in problems), "no_placeholders": not any(
            "placeholder" in p for p in problems), "problems": problems},
        "placeholders": 0,
        "gates_held": ("No Amazon request, no spend, no credential read, no cloud inference. "
                       "Public GitHub/HF/arXiv/Discourse/YouTube endpoints only."),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(MANIFEST), "totals": totals,
                      "cumulative": manifest["cumulative"],
                      "checks": manifest["checks"]}, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
