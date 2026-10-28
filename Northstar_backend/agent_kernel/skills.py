"""Skills — progressive disclosure of procedures, never a prompt dump."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional


@dataclass
class Skill:
    name: str
    description: str
    path: str
    body: str

    def metadata(self) -> dict:
        return {"name": self.name, "description": self.description,
                "path": self.path}


class SkillRegistry:
    def __init__(self, skills: Iterable[Skill] = ()):
        self._skills: Dict[str, Skill] = {s.name: s for s in skills}

    def __len__(self) -> int:
        return len(self._skills)

    def register(self, skill: Skill) -> None:
        if not skill.name.strip():
            raise ValueError("a skill needs a name")
        self._skills[skill.name] = skill

    def metadata(self) -> List[dict]:
        return [s.metadata() for s in sorted(self._skills.values(),
                                             key=lambda s: s.name)]

    def load(self, name: str) -> Skill:
        if name not in self._skills:
            raise KeyError(name)
        return self._skills[name]

    def select(self, query: str, top: int = 3) -> List[dict]:
        terms = [t for t in re.split(r"[^a-z0-9]+", query.lower()) if len(t) > 2]
        scored = []
        for s in self._skills.values():
            hay = (s.name + " " + s.description).lower()
            score = sum(hay.count(t) for t in terms)
            if score:
                scored.append((score, s))
        scored.sort(key=lambda kv: (-kv[0], kv[1].name))
        return [s.metadata() for _, s in scored[:top]]

    @classmethod
    def from_dir(cls, root: str | Path) -> "SkillRegistry":
        reg = cls()
        root = Path(root)
        if not root.is_dir():
            return reg
        for p in sorted(root.rglob("SKILL.md")):
            text = p.read_text(encoding="utf-8", errors="replace")
            meta, body = _parse_frontmatter(text)
            name = meta.get("name") or p.parent.name
            reg.register(Skill(name, meta.get("description") or "",
                               str(p), body))
        return reg


def _parse_frontmatter(text: str) -> tuple[Dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end].strip().splitlines()
    meta: Dict[str, str] = {}
    for line in block:
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[end + 4:].lstrip("\n")
