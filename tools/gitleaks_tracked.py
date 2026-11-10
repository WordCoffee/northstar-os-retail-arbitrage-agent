"""Which gitleaks findings sit in files git actually tracks — the only ones that are "leaked".

A `.env` on disk is a credential in a file the owner controls; the same value inside a tracked
document is a credential in history. Those are different problems and get different entries in
`needs_you.md`. Values are never read: only the path, the line and the rule.
"""
from __future__ import annotations

import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent")
SRC = Path.home() / "AppData" / "Local" / "Temp" / "gitleaks_scan_20261109.json"
OUT = ROOT / "reports" / "ty" / "gitleaks_classified.md"


def tracked(paths: set) -> set:
    if not paths:
        return set()
    listing: list = []
    for start in range(0, len(paths), 200):
        chunk = sorted(paths)[start:start + 200]
        result = subprocess.run(["git", "ls-files", "--", *chunk], cwd=str(ROOT),
                                capture_output=True, text=True)
        listing.extend(line.strip() for line in result.stdout.splitlines())
    return set(listing)


def classify(path: str, is_tracked: bool) -> str:
    low = (path or "").lower()
    if low.startswith(".env") or low.endswith("/.env"):
        return "real-local-only"
    if "venv" in low or "site-packages" in low or "node_modules" in low:
        return "vendor-false-positive"
    if any(hint in low for hint in ("test_", "/tests/", "fixtures/", ".playwright-mcp/")):
        return "fixture-or-capture"
    if is_tracked:
        return "real-committed"
    return "review-untracked"


def main() -> int:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    rows = [{"file": item.get("File"), "line": item.get("StartLine"),
             "rule": item.get("RuleID"), "description": item.get("Description")}
            for item in data]
    files = {row["file"] for row in rows if row["file"]}
    tracked_files = tracked(files)
    by_class: dict = defaultdict(list)
    for row in rows:
        row["classification"] = classify(row["file"] or "", row["file"] in tracked_files)
        by_class[row["classification"]].append(row)

    lines = ["# gitleaks findings: classified, values never read", "",
             f"{len(rows)} findings over {len(files)} files. Scanned with `--redact`; `Secret` and "
             "`Match` were dropped when the report was read, so no value is in this file, the tool's "
             "output, or the JSON it wrote.", "",
             "## Summary", "", "| class | findings | files |", "|---|---|---|"]
    for name, items in sorted(by_class.items()):
        lines.append(f"| **{name}** | {len(items)} | {len({i['file'] for i in items})} |")
    lines += ["", "## Every finding with a committed file", "",
              "| file | line | rule | class |", "|---|---|---|---|"]
    for row in sorted(by_class.get("real-committed", []), key=lambda r: (r["file"], r["line"])):
        lines.append(f"| `{row['file']}` | {row['line']} | `{row['rule']}` | "
                     f"**{row['classification']}** |")
    lines += ["", "## Real but local only (`.env`)", "",
              "| file | line | rule |", "|---|---|---|"]
    for row in sorted(by_class.get("real-local-only", []), key=lambda r: (r["file"], r["line"]))[:40]:
        lines.append(f"| `{row['file']}` | {row['line']} | `{row['rule']}` |")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"findings": len(rows), "tracked_files": len(tracked_files),
                      "by_class": {name: len(items) for name, items in by_class.items()},
                      "real_committed_files": sorted({i["file"] for i in
                                                      by_class.get("real-committed", [])})},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
