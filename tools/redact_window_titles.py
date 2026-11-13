"""Remove window titles from everything the loop writes, and keep them out.

A window title is not telemetry. It is a tab name, a mailbox, a customer's file, a document the
owner has open while doing their day job. The heartbeat, the vision state, the run logs, the
handoff and the digests are files that outlive the moment they describe, so a title in any of them
is a leak that nobody notices.

This tool does two things and nothing else:

* `--scan` reports how many title-shaped strings each scoped file still carries;
* `--apply` replaces them with a fixed marker and prints the per-file count, so the change is
  reviewable rather than silent.

The writers were changed first (`tools/director_vision.py` records the process name and the
blocked/unblocked verdict, never the title); this tool cleans what was written before that.

    python tools/redact_window_titles.py --scan
    python tools/redact_window_titles.py --apply
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]

#: Where titles have been written. Globs, resolved under the repo root.
SCOPES = (
    "state/director/heartbeat.json",
    "state/director/vision.json",
    "state/soak.json",
    "state/v3_then_soak.json",
    "reports/ty/*.log",
    "reports/ty/handoff.md",
    "reports/ty/digest_2026-11-*.md",
    "reports/ty/digest_2026-12-*.md",
    "logs/ty_director*.log",
    "logs/tys_watchdog.log",
)

MARKER = "[title redacted]"

#: Title shapes the code has actually written. Each is (pattern, replacement). The replacements are
#: deliberately unquoted so they cannot match their own pattern: a scrubber that rewrites its own
#: marker is a scrubber that never reports zero.
PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r'"foreground"\s*:\s*"[^"\n]*"'),
     '"foreground_process": "chrome.exe (title redacted)"'),
    (re.compile(r"foreground\s+is\s+'[^'\n]*'"), "foreground is [title redacted]"),
    (re.compile(r"foreground\s+'[^'\n]*'"), "foreground [title redacted]"),
    (re.compile(r'foreground\s+"[^"\n]*"'), "foreground [title redacted]"),
    (re.compile(r"foreground window:\s*[^\n]+"), "foreground window: [title redacted]"),
]


def targets() -> List[Path]:
    found: List[Path] = []
    for scope in SCOPES:
        for path in sorted(ROOT.glob(scope)):
            if path.is_file() and path not in found:
                found.append(path)
    return found


def count(text: str) -> int:
    return sum(len(pattern.findall(text)) for pattern, _ in PATTERNS)


def scrub(text: str) -> Tuple[str, int]:
    total = 0
    for pattern, replacement in PATTERNS:
        text, hits = pattern.subn(replacement, text)
        total += hits
    return text, total


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Redact window titles from loop artifacts")
    parser.add_argument("--scan", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    rows: List[Dict[str, object]] = []
    for path in targets():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hits = count(text)
        if hits:
            rows.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"), "hits": hits})
        if ns.apply and hits:
            cleaned, applied = scrub(text)
            path.write_text(cleaned, encoding="utf-8")
            rows[-1]["applied"] = applied

    if ns.json:
        print(json.dumps({"files": rows, "total": sum(int(r["hits"]) for r in rows)}, indent=2))
        return 0
    if not rows:
        print("no window titles found in the scoped files")
        return 0
    for row in rows:
        print(f"  {row['file']}: {row['hits']} title-shaped string(s)"
              + (f" — redacted {row.get('applied')}" if ns.apply else ""))
    print(f"total: {sum(int(r['hits']) for r in rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
