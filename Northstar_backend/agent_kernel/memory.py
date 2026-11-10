"""Project memory — authored instructions plus proposed auto-memory.

Memory is context, not enforcement. The policy engine is what blocks an action;
this module only decides what the model is told. Auto-memory writes are
proposals until an operator approves them.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

MAX_LINES = 200
MAX_IMPORT_DEPTH = 4
_IMPORT_RE = re.compile(r"(?<!`)@([^\s`]+)")


@dataclass
class MemoryFile:
    path: str
    text: str
    scope: str = "project"

    def lines(self) -> List[str]:
        return self.text.splitlines()

    def to_dict(self) -> dict:
        return {"path": self.path, "scope": self.scope, "bytes": len(self.text),
                "lines": len(self.lines())}


def _strip_comments(text: str) -> str:
    # Block-level HTML comments are maintainer notes, not context.
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def _read_limited(path: Path, *, max_lines: int = MAX_LINES) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[:max_lines])


def load_memory(root: str | Path, *, extra: Iterable[str | Path] = (),
                max_lines: int = MAX_LINES) -> List[MemoryFile]:
    """Load NORTHSTAR.md (or AGENTS.md) from the root and its parents.

    Closest-to-work loads last. Imports expand inline up to four hops; a missing
    import is reported in the text, never silently dropped.
    """
    root = Path(root)
    out: List[MemoryFile] = []
    seen: set[str] = set()
    for directory in [root, *root.parents]:
        for name in ("NORTHSTAR.md", ".northstar/NORTHSTAR.md", "AGENTS.md"):
            p = directory / name
            if not p.is_file():
                continue
            key = str(p.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            text = _strip_comments(_read_limited(p, max_lines=max_lines))
            text = _expand_imports(text, p.parent, depth=0, seen=seen)
            out.append(MemoryFile(str(p), text, scope="project"))
            break
    for p in extra:
        path = Path(p)
        if path.is_file():
            out.append(MemoryFile(str(path), _strip_comments(
                _read_limited(path, max_lines=max_lines)), scope="extra"))
    return out


def _expand_imports(text: str, base: Path, *, depth: int, seen: set[str]) -> str:
    if depth >= MAX_IMPORT_DEPTH:
        return text
    def repl(match: re.Match) -> str:
        rel = match.group(1)
        target = (base / rel).resolve()
        key = str(target).lower()
        if key in seen:
            return f"[already loaded: {rel}]"
        if not target.is_file():
            return f"[missing import: {rel}]"
        seen.add(key)
        body = _strip_comments(_read_limited(target))
        return _expand_imports(body, target.parent, depth=depth + 1, seen=seen)
    return _IMPORT_RE.sub(repl, text)


@dataclass
class AutoMemory:
    """Proposals only. Nothing reaches the model until approved."""
    path: Optional[Path] = None
    items: List[Dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.path and self.path.is_file():
            self.items = json.loads(self.path.read_text(encoding="utf-8"))

    def propose(self, text: str, *, source: str, date: str) -> Dict[str, str]:
        item = {"text": text.strip(), "source": source, "date": date,
                "status": "proposed"}
        if not item["text"]:
            raise ValueError("an empty memory proposal is not allowed")
        self.items.append(item)
        self._save()
        return item

    def approve(self, index: int) -> Dict[str, str]:
        item = self.items[index]
        item["status"] = "approved"
        self._save()
        return item

    def forget(self, index: int) -> Dict[str, str]:
        item = self.items.pop(index)
        item["status"] = "forgotten"
        self._save()
        return item

    def approved(self) -> List[Dict[str, str]]:
        return [i for i in self.items if i.get("status") == "approved"]

    def render(self) -> str:
        return "\n".join(f"- {i['text']} (source: {i['source']}, {i['date']})"
                         for i in self.approved())

    def _save(self) -> None:
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.items, indent=2), encoding="utf-8")


def render_context(files: List[MemoryFile], auto: Optional[AutoMemory] = None) -> str:
    parts = [f"<!-- {f.path} -->\n{f.text}" for f in files]
    if auto and auto.approved():
        parts.append("<!-- approved auto-memory -->\n" + auto.render())
    return "\n\n".join(parts)
