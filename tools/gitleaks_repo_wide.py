"""Group the repo-wide gitleaks findings by file and rule, without ever reading a secret value.

The classification question is per *file*: a finding in a test module that builds fake data is a
fixture; a finding in a document export is a credential someone pasted. Values are irrelevant to that
judgement and are never printed.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

SRC = Path.home() / "AppData" / "Local" / "Temp" / "gitleaks_scan_20261109.json"
ROOT = Path(r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent")
OUT = ROOT / "reports" / "ty" / "gitleaks_repo_wide.md"

DOC = (".md", ".txt", ".json", ".log", ".csv")
TEST = ("test_", "/tests/", "fixtures/", "sample", "mock")


def classify(path: str, rule: str) -> str:
    low = path.lower()
    if any(hint in low for hint in TEST):
        return "fixture-or-test"
    if any(low.endswith(ext) for ext in DOC):
        return "review-document"
    return "review-code"


def main() -> int:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    rows = []
    for item in data:
        rows.append({"file": item.get("File"), "line": item.get("StartLine"),
                     "rule": item.get("RuleID"), "description": item.get("Description")})
    by_file: Counter = Counter(row["file"] for row in rows)
    by_class: Counter = Counter(classify(row["file"] or "", row["rule"] or "") for row in rows)
    lines = ["# Repo-wide gitleaks findings, grouped by file", "",
             f"{len(rows)} findings. Values were redacted at scan time (`--redact`) and are not in "
             "this file, this tool's memory, or the scan report.", "",
             "| findings | class | file |", "|---|---|---|"]
    for path, count in by_file.most_common(40):
        lines.append(f"| {count} | {classify(path or '', '')} | `{path}` |")
    lines += ["", "| class | findings |", "|---|---|"]
    for name, count in by_class.most_common():
        lines.append(f"| {name} | {count} |")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"findings": len(rows), "files": len(by_file),
                      "by_class": dict(by_class)}, indent=2))
    for path, count in by_file.most_common(12):
        print(f"  {count:3d}  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
