"""Refuse a chat export that contains anything shaped like a key ON AN ASSIGNMENT.

The five flagged lines in this repository were all pasted transcripts: someone exported a chat and
committed it, and a key came along. gitleaks catches those after the fact, with false positives on
test fixtures; this check is narrower on purpose — it looks **only at files whose name says they are
a chat export**, and only at lines that *assign* a secret.

The first version also flagged two prose lines ("… argues: your API key must be rotated…"), which is
how a guard gets switched off. A guard that cries wolf on a sentence is worse than no guard.

Values are never printed. A finding names the file, the line and the shape.

    python -m tools.chat_export_guard --staged      # what the pre-commit hook calls
    python -m tools.chat_export_guard FILE [FILE]   # manual
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]

#: A file is a chat export when its name says so. Narrow on purpose: a `*.md` that happens to
#: contain the word "chat" is not a transcript, and refusing ordinary docs would get this removed.
EXPORT_NAME = re.compile(r"(chat[-_ ]?(export|transcript)|automation[-_ ]?chat|chat[-_ ]?log)",
                         re.IGNORECASE)
EXPORT_SUFFIXES = (".md", ".txt", ".log", ".json", ".html")

#: Key-shaped strings, each matched on a line that also assigns them. The generic ones require an
#: assignment and a **value-shaped token** — no spaces, no punctuation runs — so prose about keys
#: does not trip them.
_VALUE = r"['\"]?[A-Za-z0-9][A-Za-z0-9_\-]{11,}"
SHAPES = (
    ("openai-style", re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b")),
    ("github-pat", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b")),
    ("github-fine-grained", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("google-api", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("aws-access", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("slack", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b")),
    ("stripe", re.compile(r"\b[rs]k_(live|test)_[A-Za-z0-9]{16,}\b")),
    ("bearer", re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]{24,}=*")),
    # `NAME=value` / `NAME: value` / `12: NAME=value`, quoted or not — the shape the five flagged
    # lines actually had. The value must be one unbroken token: a sentence has spaces and commas.
    ("assigned-secret",
     re.compile(r"(?i)(?:^|\s)(?:[A-Z0-9_\-]*"
                r"(?:api[_-]?key|secret|token|password|passwd)[A-Z0-9_\-]*)"
                r"\s*[:=]\s*['\"]?" + _VALUE)),
)


def is_export(path: str) -> bool:
    name = Path(path).name
    return name.lower().endswith(EXPORT_SUFFIXES) and bool(EXPORT_NAME.search(name))


def scan_text(text: str) -> List[Dict[str, object]]:
    """Every key-shaped assignment in a transcript, as line + shape. Never the value."""
    findings: List[Dict[str, object]] = []
    for number, line in enumerate(text.splitlines(), 1):
        for name, pattern in SHAPES:
            if pattern.search(line):
                findings.append({"line": number, "shape": name})
                break                     # one finding per line is enough to refuse the commit
    return findings


def scan_file(path: Path) -> List[Dict[str, object]]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return scan_text(text)


def _staged_exports() -> List[str]:
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                         cwd=str(ROOT), capture_output=True, text=True)
    return [line.strip() for line in out.stdout.splitlines()
            if line.strip() and is_export(line.strip())]


def _staged_blob(path: str) -> str:
    out = subprocess.run(["git", "show", f":{path}"], cwd=str(ROOT),
                         capture_output=True, text=True, errors="replace")
    return out.stdout or ""


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Refuse chat exports that assign a key-shaped value")
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--staged", action="store_true")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(list(argv) if argv is not None else None)

    results = []
    if ns.staged:
        for rel in _staged_exports():
            findings = scan_text(_staged_blob(rel))
            if findings:
                results.append({"file": rel, "findings": findings})
    else:
        for rel in ns.paths:
            if not is_export(rel):
                continue
            findings = scan_file(ROOT / rel)
            if findings:
                results.append({"file": rel, "findings": findings})

    if ns.json:
        print(json.dumps({"exports_with_secrets": results}, indent=2))
    elif results:
        print("BLOCKED: a chat export assigns a key-shaped value.", file=sys.stderr)
        for item in results:
            for finding in item["findings"]:
                print(f"  {item['file']}:{finding['line']}  {finding['shape']}", file=sys.stderr)
        print("Rotate the key, then remove the export from the tree. Do not paste transcripts into "
              "the repository.", file=sys.stderr)
    return 1 if results else 0


if __name__ == "__main__":
    raise SystemExit(main())
