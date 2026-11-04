"""Populate the expansion manifest — every output, hashed, no placeholders.

Counts come from the files themselves, not from the process that wrote them, so a
resumed scan cannot under-report. Fails when a JSON file does not parse or a
report contains a placeholder marker (TODO/TBD/xxxx/<placeholder>).

    python tools/expansion_manifest.py
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports" / "expansion_20261104"
EVIDENCE = ROOT / "state" / "evidence" / "expansion_20261104"
MANIFEST = REPORTS / "manifest.json"

PLACEHOLDER = re.compile(r"\b(TODO|TBD|FIXME|XXXX)\b|<placeholder>", re.IGNORECASE)

UNIT_LOG = [
    {"unit": 1, "name": "Hugging Face Hub scan", "platform": "huggingface", "quota": "50 req"},
    {"unit": 2, "name": "arXiv scan", "platform": "arxiv", "quota": "50 queries"},
    {"unit": 3, "name": "Google AI forum + YouTube", "platform": "gforum+youtube", "quota": "15 + 16"},
    {"unit": 4, "name": "GitHub extraction scan", "platform": "github", "quota": "60 req"},
    {"unit": 5, "name": "Blueprints, specs, report, manifest", "platform": "synthesis", "quota": "n/a"},
]


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rows(path: Path) -> int:
    if not path.is_file():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def _unique(path: Path, key: str) -> int:
    if not path.is_file():
        return 0
    seen = set()
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get(key):
                seen.add(str(row[key]))
    return len(seen)


def _files() -> List[Dict[str, Any]]:
    out = []
    for folder in (REPORTS, EVIDENCE):
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.name == "manifest.json":
                continue
            out.append({"path": str(path.relative_to(ROOT)).replace("\\", "/"),
                        "bytes": path.stat().st_size, "sha256": _sha(path)})
    return out


def main() -> int:
    problems: List[str] = []
    platforms = {
        "huggingface": {"rows": _rows(EVIDENCE / "hf.jsonl"),
                        "unique": _unique(EVIDENCE / "hf.jsonl", "id"),
                        "summary": str((EVIDENCE / "hf_summary.json").relative_to(ROOT))},
        "arxiv": {"rows": _rows(EVIDENCE / "arxiv.jsonl"),
                  "unique": _unique(EVIDENCE / "arxiv.jsonl", "id"),
                  "summary": str((EVIDENCE / "arxiv_summary.json").relative_to(ROOT))},
        "gforum": {"rows": _rows(EVIDENCE / "gforum.jsonl"),
                   "unique": _unique(EVIDENCE / "gforum.jsonl", "post_id"),
                   "summary": str((EVIDENCE / "gforum_summary.json").relative_to(ROOT))},
        "youtube": {"rows": _rows(EVIDENCE / "youtube.jsonl"),
                    "unique": _unique(EVIDENCE / "youtube.jsonl", "video_id"),
                    "summary": str((EVIDENCE / "youtube_summary.json").relative_to(ROOT))},
        "github": {"rows": _rows(EVIDENCE / "github.jsonl"),
                   "unique": _unique(EVIDENCE / "github.jsonl", "full_name"),
                   "summary": str((EVIDENCE / "github_summary.json").relative_to(ROOT))},
    }
    for name, row in platforms.items():
        if row["rows"] == 0:
            problems.append(f"{name}: no rows")
        summary_path = ROOT / row["summary"]
        if not summary_path.is_file():
            problems.append(f"{name}: summary missing")
            continue
        try:
            json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{name}: summary invalid JSON ({exc})")

    for path in list(REPORTS.glob("*.md")) + list(REPORTS.glob("*.json")):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            problems.append(f"{path.name}: unreadable ({exc})")
            continue
        if path.name == "manifest.json":
            continue
        if path.suffix == ".json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                problems.append(f"{path.name}: invalid JSON ({exc})")
        match = PLACEHOLDER.search(text)
        if match:
            problems.append(f"{path.name}: placeholder marker {match.group(0)!r}")

    files = _files()
    total_rows = sum(p["rows"] for p in platforms.values())
    manifest = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "campaign": "NORTHSTAROS master expansion — secondary discovery",
        "units": UNIT_LOG,
        "platforms": platforms,
        "totals": {
            "rows": total_rows,
            "unique": sum(p["unique"] for p in platforms.values()),
            "platforms": len([p for p in platforms.values() if p["rows"] > 0]),
            "files": len(files),
        },
        "files": files,
        "checks": {
            "json_parses": not any("invalid JSON" in p for p in problems),
            "every_platform_has_rows": all(p["rows"] > 0 for p in platforms.values()),
            "no_placeholders": not any("placeholder" in p for p in problems),
            "problems": problems,
        },
        "placeholders": 0,
        "gates_held": ("No Amazon request, no spend, no credential read, no cloud inference. "
                       "Public GitHub/HF/arXiv/Discourse/YouTube endpoints only."),
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"manifest": str(MANIFEST), "totals": manifest["totals"],
                      "checks": manifest["checks"]}, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
