"""Scan the full history, every ref, for sensitive content — and report counts only.

The gitleaks pass answers "is there a key here". It does not answer "is there a customer's email, a
supplier's name, a phone number, or a dev password in the history". This does, over **every line ever
added on any ref**, and it prints **counts, never values**: no match text, no surrounding line, no
filename fragment that contains a match.

How it reads history: `git log --all -p --unified=0` and a streaming scan of the patch text. Blob
streaming was the first approach and is the wrong tool here — the pack is 2 GiB of model weights and
images, and inflating every object takes tens of minutes to find nothing. A patch stream sees every
line that was ever introduced, which is what "in history" means, and skips binaries by itself.

Categories, deliberately blunt:

* **email** — anything shaped like an address, plus how many are obviously machine-generated.
* **phone** — E.164-ish runs and US formatted numbers.
* **vendor** — supplier/provider names, counted because a name in a committed document is commercial
  information even when it is not a credential.
* **dev-credential** — basic-auth URLs, `Authorization: Basic`, and `password=`/`token=` assignments
  that are not the key-shaped strings gitleaks already covers.

    python tools/history_sensitive_scan.py --write
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "ty" / "history_sensitive_counts.json"
REPORT = ROOT / "reports" / "ty" / "history_sensitive.md"

EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
MACHINE_EMAIL = re.compile(r"(?i)(noreply|no-reply|example\.(com|org)|users\.noreply\.github\.com|"
                           r"localhost|@example)")
# A phone number is a *shape*, not a run of digits: the first version matched any 10-15 digit
# number and reported 188,710 "phones" that were order ids, hashes and timestamps. It now needs
# either a leading + or a human separator.
PHONE_E164 = re.compile(r"(?<![\d+])\+[1-9]\d{8,14}(?!\d)")
PHONE_US = re.compile(r"(\(\d{3}\)\s*\d{3}[-. ]\d{4}|(?<!\d)\d{3}-\d{3}-\d{4}(?!\d))")
BASIC_AUTH_URL = re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]*://[^/\s:@]{1,64}:[^/\s@]{1,64}@")
BASIC_HEADER = re.compile(r"(?i)authorization\s*:\s*basic\s+[A-Za-z0-9+/=]{8,}")
DEV_SECRET = re.compile(r"(?i)\b(password|passwd|pwd|secret|token)\s*[:=]\s*[^\s'\"]{4,}")

VENDORS = (
    "costco", "amazon", "brightdata", "bright data", "scavio", "unwrangle", "chocodata",
    "easyparser", "canopy", "keepa", "faire", "packify", "pacdora", "openwebninja",
    "rapidapi", "dataforseo", "ultralytics", "openai", "anthropic", "comfyui",
)


def scan_line(line: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    emails = EMAIL.findall(line)
    if emails:
        counts["email"] = len(emails)
        counts["email_machine_generated"] = sum(1 for item in emails if MACHINE_EMAIL.search(item))
    phones = len(PHONE_E164.findall(line)) + len(PHONE_US.findall(line))
    if phones:
        counts["phone"] = phones
    if BASIC_AUTH_URL.search(line):
        counts["dev_credential_url"] = len(BASIC_AUTH_URL.findall(line))
    if BASIC_HEADER.search(line):
        counts["dev_credential_basic_header"] = len(BASIC_HEADER.findall(line))
    if DEV_SECRET.search(line):
        counts["dev_credential_assignment"] = len(DEV_SECRET.findall(line))
    low = line.lower()
    for vendor in VENDORS:
        hits = low.count(vendor)
        if hits:
            counts[f"vendor:{vendor}"] = hits
    return counts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Counts-only sensitive-content scan over all history")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--limit-commits", type=int, default=0)
    ns = parser.parse_args(argv)

    command = ["git", "log", "--all", "-p", "--unified=0", "--no-color", "--no-textconv"]
    if ns.limit_commits:
        command.insert(2, f"-n{ns.limit_commits}")
    refs = subprocess.run(["git", "for-each-ref", "--format=%(refname)"], cwd=str(ROOT),
                          capture_output=True, text=True).stdout.split()
    commits = subprocess.run(["git", "rev-list", "--all"], cwd=str(ROOT),
                             capture_output=True, text=True).stdout.split()

    totals: Counter = Counter()
    commits_with: Counter = Counter()
    process = subprocess.Popen(command, cwd=str(ROOT), stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                               errors="replace")
    assert process.stdout
    commit_hits: set = set()
    current = ""
    files_touched: set = set()
    for line in process.stdout:
        if line.startswith("commit "):
            if current and commit_hits:
                for key in commit_hits:
                    commits_with[key] += 1
            current = line.split()[1]
            commit_hits = set()
            continue
        if line.startswith("+++ b/"):
            files_touched.add(line[6:].strip())
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for key, value in scan_line(line[1:]).items():
            totals[key] += value
            commit_hits.add(key)
    if current and commit_hits:
        for key in commit_hits:
            commits_with[key] += 1
    process.stdout.close()
    process.wait()

    result = {"refs": len(refs), "commits": len(commits),
              "files_touched": len(files_touched),
              "totals": dict(sorted(totals.items())),
              "commits_containing": dict(sorted(commits_with.items()))}
    if ns.write:
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        lines = ["# History scan: sensitive content beyond keys, counts only", "",
                 f"**{len(commits):,} commits** across **{len(refs)} refs**. Every added line was "
                 "scanned. No value, line or filename is printed here — only how many were found and "
                 "in how many commits.", "",
                 "| category | occurrences | commits containing it |", "|---|---|---|"]
        for key, value in sorted(result["totals"].items()):
            lines.append(f"| `{key}` | {value:,} | {commits_with[key]:,} |")
        lines += ["",
                  "Reading the table: `vendor:*` counts **mentions of the name**, which is commercial "
                  "information density, not a secret. `dev_credential_assignment` counts lines that "
                  "assign something to a password/token-shaped name — much of that is code, so it is "
                  "the noisiest row; `dev_credential_url` (a URL carrying user:pass) and "
                  "`dev_credential_basic_header` are the high-signal ones. `phone` requires a leading "
                  "`+` or human separators, because bare digit runs are ids, not numbers.", ""]
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if ns.json or not ns.write:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps({"refs": len(refs), "commits": len(commits),
                          "categories": len(result["totals"])}, indent=2))
        print("report:", REPORT.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
