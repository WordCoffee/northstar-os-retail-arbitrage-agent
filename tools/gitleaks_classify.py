"""Classify the gitleaks findings that block promotion, without ever printing a secret.

The promotion hook refuses three slices with 24 findings. This walks *those slices' paths* in a temp
directory (the same input the hook sees), runs gitleaks with `--redact`, and writes a table of
file:line, rule and description only — `Secret` and `Match` are dropped on read, never written.

    python tools/gitleaks_classify.py --slices Northstar_backend-root Northstar_backend-data
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "ty" / "gitleaks_findings_classified.json"
REPORT = ROOT / "reports" / "ty" / "gitleaks_classified.md"

#: Files that are, by construction, not credentials. Each entry is a claim that has to be checked
#: against the finding's rule and path; nothing here is applied silently.
FIXTURE_HINTS = ("fixtures/", "data/", "test_", "/tests/", "sample", "example", "mock", "demo")
#: Document exports and logs that can contain a pasted credential: real until proven otherwise.
DOCUMENT_HINTS = (".md", ".txt", "chat", "export", "transcript", "log")


def slice_paths(names: List[str]) -> List[str]:
    sys.path.insert(0, str(ROOT / "tools"))
    import promote_staging as P  # noqa: PLC0415

    diff = subprocess.check_output(["git", "diff", "--name-only", "main", "staging"],
                                   cwd=str(ROOT), text=True)
    rows = P.build_slices([line for line in diff.splitlines() if line.strip()])
    wanted = set(names)
    paths: List[str] = []
    for name, slice_files in rows.items():
        if name in wanted:
            paths.extend(slice_files)
    return sorted(set(paths))


def run_gitleaks(paths: List[str]) -> List[Dict[str, Any]]:
    work = Path(tempfile.mkdtemp(prefix="gl-slice-"))
    for rel in paths:
        source = ROOT / rel
        if not source.is_file():
            continue
        target = work / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    report = work / "report.json"
    subprocess.run(["gitleaks", "dir", str(work), "--redact", "--report-format", "json",
                    "--report-path", str(report), "-c", str(ROOT / ".gitleaks.toml"),
                    "--exit-code", "0"], check=False, capture_output=True, text=True)
    if not report.exists():
        return []
    data = json.loads(report.read_text(encoding="utf-8") or "[]")
    shutil.rmtree(work, ignore_errors=True)
    findings = []
    for item in data:
        findings.append({
            "file": item.get("File"),
            "line": item.get("StartLine"),
            "end_line": item.get("EndLine"),
            "rule": item.get("RuleID"),
            "description": item.get("Description"),
            "entropy": round(float(item.get("Entropy") or 0.0), 2),
            "tags": item.get("Tags") or [],
        })
    return findings


def classify(finding: Dict[str, Any]) -> str:
    path = str(finding.get("file") or "").lower()
    rule = str(finding.get("rule") or "").lower()
    if "private-key" in rule or "aws" in rule and "access" in rule:
        return "real-until-proven"
    if any(hint in path for hint in DOCUMENT_HINTS):
        return "real-until-proven"    # a pasted credential in a document is the DIR-1 case
    if any(hint in path for hint in FIXTURE_HINTS):
        return "fixture-or-fp-review"
    return "review"


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify blocking gitleaks findings")
    parser.add_argument("--slices", nargs="+",
                        default=["Northstar_backend-root", "Northstar_backend-data",
                                 "Northstar_backend-static"])
    ns = parser.parse_args(argv)
    paths = slice_paths(ns.slices)
    print(f"{len(paths)} paths across {len(ns.slices)} slices")
    findings = run_gitleaks(paths)
    for finding in findings:
        finding["classification"] = classify(finding)
    OUT.write_text(json.dumps({"slices": ns.slices, "paths": len(paths),
                               "findings": findings}, indent=2) + "\n", encoding="utf-8")
    lines = ["# gitleaks findings that block promotion, classified", "",
             f"{len(paths)} paths across {', '.join(ns.slices)}. Values are redacted at scan time and "
             "never written here: file, line, rule and description only.", "",
             "| # | file | line | rule | description | classification |",
             "|---|---|---|---|---|---|"]
    for index, finding in enumerate(findings, 1):
        lines.append(f"| {index} | `{finding['file']}` | {finding['line']} | "
                     f"`{finding['rule']}` | {finding['description']} | "
                     f"**{finding['classification']}** |")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"findings": len(findings),
                      "by_class": {c: sum(1 for f in findings if f['classification'] == c)
                                   for c in {f['classification'] for f in findings}}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
