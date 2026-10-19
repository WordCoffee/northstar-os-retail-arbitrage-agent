"""Scrub credential-shaped strings out of swept repo metadata.

Why: GitHub repo DESCRIPTIONS sometimes contain sample tokens and keys the
author committed by accident. They are not ours, but they must not be copied
into this repository either. This redacts the credential-shaped segment in place
and keeps the row (the description is still useful; the secret is not).

Reported honestly: how many rows were touched, per rule. Nothing is silently
dropped - rows are preserved, only the matching substring is replaced.

Usage: python scrub_repos.py [--check]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPLACEMENT = "[redacted-credential-shaped-string]"

#: Ordered: the most specific shapes first so a generic rule cannot eat a known
#: one and leave half of it behind.
RULES: list[tuple[str, re.Pattern]] = [
    ("telegram_bot_token", re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,45}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,255}\b")),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("discord_token", re.compile(r"\b[A-Za-z0-9_-]{24,30}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,40}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("labelled_secret", re.compile(
        r"(?i)\b(secret|token|api[_-]?key|apikey|password|passwd|pwd)\b"
        r"[^A-Za-z0-9\n]{1,8}([A-Za-z0-9_\-/+]{16,})")),
]


def scrub_text(text: str) -> tuple[str, list[str]]:
    hits: list[str] = []
    for name, rx in RULES:
        def _sub(m: re.Match) -> str:
            hits.append(name)
            # keep the label for labelled_secret so the text still reads
            if name == "labelled_secret" and m.re.groups >= 2:
                return f"{m.group(1)} {REPLACEMENT}"
            return REPLACEMENT
        text = rx.sub(_sub, text)
    return text, hits


def scrub_row(row: dict) -> tuple[dict, list[str]]:
    hits: list[str] = []
    for field in ("description", "topics"):
        if isinstance(row.get(field), str) and row[field]:
            new, h = scrub_text(row[field])
            if h:
                row[field] = new
                hits.extend(h)
    return row, hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report only; write nothing")
    args = ap.parse_args()

    total_rows = touched_rows = 0
    by_rule: dict[str, int] = {}
    touches: list[dict] = []

    csv_path = HERE / "repos.csv"
    rows: list[dict] = []
    if csv_path.is_file():
        with csv_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            fields = reader.fieldnames
            for row in reader:
                total_rows += 1
                new, hits = scrub_row(dict(row))
                if hits:
                    touched_rows += 1
                    for h in hits:
                        by_rule[h] = by_rule.get(h, 0) + 1
                    touches.append({"full_name": new.get("full_name"),
                                    "rules": sorted(set(hits))})
                rows.append(new)
    if not args.check and rows:
        with csv_path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    jsonl_path = HERE / "repos.jsonl"
    if jsonl_path.is_file():
        out_lines: list[str] = []
        j_touched = 0
        with jsonl_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                new, hits = scrub_row(obj)
                if hits:
                    j_touched += 1
                    for h in hits:
                        by_rule[h] = by_rule.get(h, 0) + 1
                out_lines.append(json.dumps(new, ensure_ascii=False))
        if not args.check and out_lines:
            jsonl_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
        print(f"jsonl rows scanned={len(out_lines)} touched={j_touched}")

    print(json.dumps({
        "csv_rows": total_rows, "rows_touched": touched_rows,
        "by_rule": by_rule, "check_only": args.check,
        "examples": touches[:10],
    }, indent=2)[:2500])
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
