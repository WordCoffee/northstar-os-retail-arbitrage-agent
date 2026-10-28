"""Context engineering: a repo map, on-demand search, and compaction anchors."""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

SKIP_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv", "dist",
             "build", ".pytest_cache", ".mypy_cache", "venv-phase1c02"}
SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mp3", ".wav",
            ".zip", ".gguf", ".safetensors", ".bin", ".exe", ".dll", ".pyc"}

_PY_SYMBOL = re.compile(r"^\s*(?:class|def)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)
_JS_SYMBOL = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(?:function|class|const)\s+"
                        r"([A-Za-z_$][A-Za-z0-9_$]*)", re.M)


@dataclass
class FileEntry:
    path: str
    bytes: int
    sha256: str
    symbols: List[str]

    def to_dict(self) -> dict:
        return {"path": self.path, "bytes": self.bytes, "sha256": self.sha256,
                "symbols": list(self.symbols[:20])}


class RepoMap:
    def __init__(self, root: str | Path, *, max_files: int = 5000,
                 extensions: Optional[Iterable[str]] = None):
        self.root = Path(root).resolve()
        self.max_files = max_files
        self.extensions = set(extensions) if extensions else {".py", ".js", ".jsx",
                                                             ".ts", ".tsx", ".md"}
        self.files: List[FileEntry] = []

    def build(self) -> List[FileEntry]:
        out: List[FileEntry] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                p = Path(dirpath) / name
                if len(out) >= self.max_files:
                    break
                if p.suffix.lower() not in self.extensions:
                    continue
                try:
                    data = p.read_bytes()
                except OSError:
                    continue
                text = data.decode("utf-8", errors="replace")
                symbols: List[str] = []
                if p.suffix == ".py":
                    symbols = _PY_SYMBOL.findall(text)
                elif p.suffix in (".js", ".jsx", ".ts", ".tsx"):
                    symbols = _JS_SYMBOL.findall(text)
                out.append(FileEntry(str(p.relative_to(self.root)).replace("\\", "/"),
                                     len(data), hashlib.sha256(data).hexdigest(),
                                     symbols[:20]))
            if len(out) >= self.max_files:
                break
        self.files = sorted(out, key=lambda f: f.path)
        return self.files

    def search(self, query: str, top: int = 20) -> List[FileEntry]:
        terms = [t for t in re.split(r"[^a-z0-9_]+", query.lower()) if len(t) > 1]
        if not terms:
            return []
        scored = []
        for f in self.files:
            hay = (f.path + " " + " ".join(f.symbols)).lower()
            score = sum(hay.count(t) for t in terms)
            if score:
                scored.append((score, f))
        scored.sort(key=lambda kv: (-kv[0], kv[1].path))
        return [f for _, f in scored[:top]]

    def digest(self) -> str:
        blob = "\n".join(f"{f.path}:{f.sha256}" for f in self.files)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


@dataclass
class CompactionResult:
    messages: List[dict]
    dropped: int
    anchors_kept: int
    reason: str = ""

    def to_dict(self) -> dict:
        return {"dropped": self.dropped, "anchors_kept": self.anchors_kept,
                "reason": self.reason, "messages": len(self.messages)}


class Compactor:
    def __init__(self, *, threshold: float = 0.80, max_chars: int = 16000):
        self.threshold = threshold
        self.max_chars = max_chars

    @staticmethod
    def estimate_tokens(text: str) -> int:
        return max(1, len(text) // 4)

    def should_compact(self, used_tokens: int, limit_tokens: int) -> bool:
        return limit_tokens > 0 and used_tokens / float(limit_tokens) >= self.threshold

    def compact(self, messages: Sequence[dict], anchors: Sequence[dict],
                *, limit_tokens: int = 8000) -> CompactionResult:
        """Keep anchors + the most recent messages, and say what was dropped."""
        anchors = list(anchors)
        used = sum(self.estimate_tokens(str(m.get("content", ""))) for m in messages)
        if not self.should_compact(used, limit_tokens):
            return CompactionResult(list(messages), 0, len(anchors), "below threshold")
        keep_recent = 4
        recent = list(messages[-keep_recent:])
        dropped = max(0, len(messages) - keep_recent)
        # No model summary is fabricated here. The anchors are the summary.
        marker = {"role": "system",
                  "content": f"[compacted {dropped} messages at "
                             f"{used}/{limit_tokens} tokens; anchors retained]"}
        return CompactionResult([marker, *anchors, *recent], dropped,
                                len(anchors), "threshold reached")


def write_handoff(path: str | Path, *, goal: str, constraints: Sequence[str],
                  decisions: Sequence[str], evidence_paths: Sequence[str]) -> Path:
    """A durable, human-readable handoff — survives a compaction."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Handoff", "", f"Goal: {goal}", "", "## Constraints"]
    lines += [f"- {c}" for c in constraints] or ["- none"]
    lines += ["", "## Decisions"] + ([f"- {d}" for d in decisions] or ["- none"])
    lines += ["", "## Evidence"] + ([f"- {e}" for e in evidence_paths] or ["- none"])
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p
