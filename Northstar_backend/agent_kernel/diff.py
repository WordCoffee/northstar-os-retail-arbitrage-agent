"""Unified diff parsing and per-hunk selection for review.

Applying a hunk to a file is the kernel's editor job; this module's contract is
that a reviewer sees hunks and chooses them. Nothing is applied implicitly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, List, Sequence

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$")


@dataclass
class Hunk:
    index: int
    header: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[str] = field(default_factory=list)

    def text(self) -> str:
        return "\n".join([self.header, *self.lines])

    def to_dict(self) -> dict:
        return {"index": self.index, "header": self.header,
                "old": [self.old_start, self.old_count],
                "new": [self.new_start, self.new_count],
                "added": sum(1 for l in self.lines if l.startswith("+")),
                "removed": sum(1 for l in self.lines if l.startswith("-"))}


def parse_diff(text: str) -> List[Hunk]:
    hunks: List[Hunk] = []
    current: Hunk | None = None
    for line in text.splitlines():
        m = _HUNK_RE.match(line)
        if m:
            current = Hunk(len(hunks), line,
                           int(m.group(1)), int(m.group(2) or 1),
                           int(m.group(3)), int(m.group(4) or 1))
            hunks.append(current)
            continue
        if current is not None and line[:1] in (" ", "+", "-", "\\"):
            current.lines.append(line)
    return hunks


def select_hunks(text: str, indices: Sequence[int]) -> str:
    """Return a diff containing only the selected hunks (for an apply step).

    The file headers (`--- a/file`, `+++ b/file`) are kept: a hunk body without
    them names no target file, so the result could not be applied by the kernel's
    editor or by `git apply`. Each kept hunk carries the header of the file it came
    from, in the input order, and a hunk from the same file does not repeat it.
    """
    keep = set(int(i) for i in indices)
    if not keep:
        return ""
    headers: List[List[str]] = []
    current: List[str] = []
    for line in text.splitlines():
        if line.startswith("--- "):
            current = [line]
        elif line.startswith("+++ ") and current:
            current = current + [line]
            headers.append(current)
    # Map hunk index -> the header pair that precedes it in the input.
    per_hunk: List[List[str]] = []
    hunk_i = -1
    current_header: List[str] = []
    for line in text.splitlines():
        if line.startswith("--- "):
            current_header = [line]
        elif line.startswith("+++ ") and current_header:
            current_header = current_header + [line]
        elif line.startswith("@@"):
            hunk_i += 1
            per_hunk.append(current_header)

    out: List[str] = []
    last_header: List[str] = []
    for hunk in parse_diff(text):
        if hunk.index not in keep:
            continue
        header = per_hunk[hunk.index] if hunk.index < len(per_hunk) else []
        if header and header != last_header:
            out.extend(header)
            last_header = header
        out.append(hunk.header)
        out.extend(hunk.lines)
    return "\n".join(out) + ("\n" if out else "")


def review(text: str) -> List[dict]:
    return [h.to_dict() for h in parse_diff(text)]


def stats(text: str) -> dict:
    hunks = parse_diff(text)
    return {"hunks": len(hunks),
            "added": sum(h.to_dict()["added"] for h in hunks),
            "removed": sum(h.to_dict()["removed"] for h in hunks)}
