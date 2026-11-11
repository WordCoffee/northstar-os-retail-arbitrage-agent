"""Remap git hashes after a history rewrite — measurable, reversible, counts first.

A rewrite changes every commit hash. Those hashes are not decoration: they are cited in the
director queue, the tags, the reports, the baseline file and the handoff. Left alone, every one
of those citations becomes a claim about a commit that no longer exists — the exact class of
"verified" this project refuses.

Three modes:

    python tools/remap_hashes.py --scan                 # what cites a hash, and how many
    python tools/remap_hashes.py --map <commit-map> --check
    python tools/remap_hashes.py --map <commit-map> --apply

`--scan` is read-only and prints one row per file with counts. `--check` reports how many of the
hashes it finds are covered by the map and names the files that would change. `--apply` rewrites
only hashes that appear in the map's **old** column, full (40 hex) or short (7-12 hex) when the
prefix is unique in the map; it writes a `.remap-backup` beside each file first, so the change is
reversible without git. Nothing else in a file is touched.

Map format: the one `git filter-repo` writes (`.git/filter-repo/commit-map`), which is a header
line `old new` (or `old,new`) followed by `<old-sha> <new-sha>` pairs — a deleted commit maps to
the all-zero sha and is reported, never silently kept.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]

FULL = re.compile(r"\b[0-9a-f]{40}\b")
SHORT = re.compile(r"(?<![0-9A-Za-z])[0-9a-f]{7,12}(?![0-9A-Za-z])")
ZERO = "0" * 40


def is_hash_like(token: str) -> bool:
    """A 7-12 char token is only a *hash* citation if it carries a hex letter.

    `0-9` are hex digits too, so a bare timestamp or row count ("1234567890") matches the
    shape. Rewriting one of those would corrupt a number that was never a commit.
    """
    return any(ch in "abcdef" for ch in token.lower())

#: Where a hash citation actually lives. Globs, resolved under the repo root.
DEFAULT_GLOBS = (
    "reports/ty/*.md",
    "reports/ty/*.json",
    "ty/*.json",
    "ty/*.md",
    "state/director/*.json",
    "docs/*.md",
    "tests/BASELINE.json",
    "00_STATE.json",
)


def parse_map(path: Path) -> Dict[str, str]:
    """old-sha -> new-sha, from a filter-repo commit-map (or a plain 'old new' list)."""
    mapping: Dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip().replace(",", " ")
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            continue
        old, new = parts[0].lower(), parts[1].lower()
        if not re.fullmatch(r"[0-9a-f]{40}", old) or not re.fullmatch(r"[0-9a-f]{40}", new):
            continue  # header
        mapping[old] = new
    return mapping


def targets(globs: Iterable[str]) -> List[Path]:
    seen: List[Path] = []
    for pattern in globs:
        for path in sorted(ROOT.glob(pattern)):
            if path.is_file() and path not in seen:
                seen.append(path)
    return seen


def find_hashes(text: str) -> Tuple[int, int]:
    """(full-hash occurrences, short-hash occurrences that are not part of a full one)."""
    full = FULL.findall(text)
    stripped = FULL.sub("", text)
    short = [token for token in SHORT.findall(stripped) if is_hash_like(token)]
    return len(full), len(short)


def scan(paths: List[Path]) -> List[Dict[str, object]]:
    rows = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        full, short = find_hashes(text)
        if full or short:
            rows.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"),
                         "full": full, "short": short,
                         "bytes": len(text)})
    return rows


def rewrite(text: str, mapping: Dict[str, str]) -> Tuple[str, Dict[str, int], List[str]]:
    """Replace mapped hashes. Returns (new_text, counts, unmapped_full_hashes)."""
    counts = {"full": 0, "short": 0}
    unmapped: List[str] = []
    prefixes: Dict[str, str] = {}
    for old in mapping:
        for length in range(7, 13):
            prefix = old[:length]
            if prefix in prefixes:
                prefixes[prefix] = ""  # ambiguous: never rewrite a short prefix
            else:
                prefixes[prefix] = old

    def sub_full(match: "re.Match[str]") -> str:
        old = match.group(0)
        new = mapping.get(old)
        if new is None:
            unmapped.append(old)
            return old
        counts["full"] += 1
        return new

    def sub_short(match: "re.Match[str]") -> str:
        short = match.group(0)
        if not is_hash_like(short):
            return short
        old = prefixes.get(short)
        if not old:
            return short
        new = mapping.get(old)
        if not new or new == ZERO:
            return short
        counts["short"] += 1
        return new[:len(short)]

    new_text = FULL.sub(sub_full, text)
    new_text = SHORT.sub(sub_short, new_text)
    return new_text, counts, unmapped


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Remap git hashes across queue, tags and reports")
    parser.add_argument("--scan", action="store_true", help="count hash citations, change nothing")
    parser.add_argument("--map", type=str, default="", help="filter-repo commit-map path")
    parser.add_argument("--check", action="store_true", help="report coverage, change nothing")
    parser.add_argument("--apply", action="store_true", help="rewrite the files")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    paths = targets(DEFAULT_GLOBS)

    if ns.scan or (not ns.map and not ns.apply):
        rows = scan(paths)
        total = {"files": len(rows), "full": sum(r["full"] for r in rows),
                 "short": sum(r["short"] for r in rows)}
        if ns.json:
            print(json.dumps({"totals": total, "files": rows}, indent=2))
        else:
            print(f"{total['files']} file(s) cite a hash: {total['full']} full, {total['short']} short")
            for row in rows:
                print(f"  {row['file']}: full {row['full']}, short {row['short']}")
        return 0

    if not ns.map:
        print("--apply/--check needs --map <commit-map>")
        return 2
    mapping = parse_map(Path(ns.map))
    if not mapping:
        print("the map has no old/new pairs")
        return 2
    replaced = sum(1 for new in mapping.values() if new != ZERO)
    deleted = len(mapping) - replaced
    print(f"map: {len(mapping)} commit(s) — {replaced} rewritten, {deleted} dropped")

    report = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        new_text, counts, unmapped = rewrite(text, mapping)
        if counts["full"] or counts["short"] or unmapped:
            report.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"),
                           "full": counts["full"], "short": counts["short"],
                           "unmapped": sorted(set(unmapped))})
        if ns.apply and (counts["full"] or counts["short"]):
            backup = path.with_suffix(path.suffix + ".remap-backup")
            backup.write_text(text, encoding="utf-8")
            path.write_text(new_text, encoding="utf-8")

    if ns.json:
        print(json.dumps(report, indent=2))
    else:
        for row in report:
            state = "rewritten" if ns.apply else "would change"
            print(f"  {row['file']}: {row['full']} full, {row['short']} short — {state}")
            for sha in row["unmapped"]:
                print(f"    unmapped full hash left as-is: {sha}")
    if ns.apply:
        print("done. each file has a .remap-backup beside it; restore by copying it back.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
