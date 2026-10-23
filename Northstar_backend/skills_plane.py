"""Skills plane: markdown skills resolved into a prompt block.

Ported pattern: `coreyhaines31/marketingskills` (MIT) — one foundation skill that every
other skill reads first. No text is copied; the skills live in `<repo>/skills`.

Contract
--------
* ``catalog()``          -> list of skill metadata, base skill first.
* ``context_block()``    -> prompt text, or ``""`` when nothing applies.
* Everything fails closed: a missing directory, a broken file or a bad budget returns ``""``
  and never raises into a chat turn. Same rule as ``chat_adapter.knowledge_block``.

No network, no third-party imports, no writes.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

#: Hard ceiling for an injected block. Skills are prompt budget, not documentation.
DEFAULT_BUDGET = 5500
#: The skill every block carries. Missing base is not fatal — the other skills still load.
BASE_SKILL = "product-marketing"

_HEADER = "\n\n[Skills — apply the relevant one]"
_TRIGGER_SPLIT = re.compile(r"[,\s]+")


def skills_dir() -> Path:
    env = os.environ.get("NORTHSTAR_SKILLS_DIR", "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent / "skills"


def _parse_frontmatter(text: str) -> tuple[Dict[str, str], str]:
    """Parse a tiny `key: value` frontmatter block. Never raises."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end].strip("\n")
    body = text[end + 4:].lstrip("\n")
    meta: Dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split(":", 1)
        meta[key.strip().lower()] = value.strip()
    return meta, body


def _triggers(meta: Dict[str, str]) -> List[str]:
    raw = meta.get("triggers", "")
    return [t for t in (w.strip().lower() for w in _TRIGGER_SPLIT.split(raw)) if t]


def _truthy(value: Optional[str]) -> bool:
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def catalog() -> List[Dict[str, object]]:
    """Every readable skill, base first, then alphabetical."""
    root = skills_dir()
    rows: List[Dict[str, object]] = []
    try:
        entries = sorted(root.iterdir(), key=lambda p: p.name.lower())
    except Exception:  # noqa: BLE001 - missing/unreadable dir is not an error here
        return rows
    for folder in entries:
        path = folder / "SKILL.md"
        try:
            if not folder.is_dir() or not path.is_file():
                continue
            meta, body = _parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:  # noqa: BLE001
            continue
        sid = (meta.get("name") or folder.name).strip()
        rows.append({
            "id": sid,
            "name": sid,
            "description": meta.get("description", ""),
            "triggers": _triggers(meta),
            "always": _truthy(meta.get("always")),
            "path": str(path),
            "body": body,
            "chars": len(body),
        })
    rows.sort(key=lambda r: (0 if r["always"] else 1, str(r["id"])))
    return rows


def load(skill_id: str) -> str:
    """Body of one skill, or "" when unknown."""
    for row in catalog():
        if row["id"] == skill_id:
            return str(row["body"])
    return ""


def route(query: Optional[str], limit: int = 2) -> List[str]:
    """Skill ids whose triggers match the query, strongest first (base excluded)."""
    if not query or not str(query).strip():
        return []
    text = str(query).lower()
    scored: List[tuple[int, str]] = []
    for row in catalog():
        if row["always"]:
            continue
        hits = sum(1 for t in row["triggers"] if t and t in text)
        if hits:
            scored.append((hits, str(row["id"])))
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [sid for _, sid in scored[:max(0, int(limit))]]


def _render(rows: Sequence[Dict[str, object]], budget: int) -> str:
    parts: List[str] = [_HEADER]
    used = len(_HEADER)
    for row in rows:
        chunk = f"\n\n## {row['id']}\n{row['body']}".rstrip()
        if used + len(chunk) > budget:
            room = budget - used
            if room < 240:  # not worth a truncated stub
                break
            cut = chunk[:room]
            cut = cut[: cut.rfind("\n")]
            parts.append(cut + "\n…(truncated)")
            break
        parts.append(chunk)
        used += len(chunk)
    return "".join(parts)


def context_block(query: Optional[str] = None,
                  ids: Optional[Iterable[str]] = None,
                  budget_chars: int = DEFAULT_BUDGET,
                  include_base: bool = True) -> str:
    """Prompt block for a turn, or "" when nothing applies.

    ``ids`` wins over ``query``. The base skill always leads when ``include_base`` is set,
    so a listing task cannot load the copy rules without the fact contract.
    """
    try:
        budget = int(budget_chars)
    except Exception:  # noqa: BLE001
        budget = DEFAULT_BUDGET
    if budget <= 0:
        return ""
    try:
        rows = catalog()
        if not rows:
            return ""
        wanted: List[str] = []
        if ids is not None:
            wanted = [str(i) for i in ids]
        elif query:
            wanted = route(query)
        if not wanted:
            return ""
        selected = _select(rows, wanted, include_base)
        if not selected:
            return ""
        return _render(selected, budget)
    except Exception:  # noqa: BLE001 - never break a turn over prompt decoration
        return ""


def _select(rows: Sequence[Dict[str, object]], wanted: Sequence[str],
            include_base: bool) -> List[Dict[str, object]]:
    by_id = {str(r["id"]): r for r in rows}
    out: List[Dict[str, object]] = []
    if include_base and BASE_SKILL in by_id:
        out.append(by_id[BASE_SKILL])
    seen = {str(r["id"]) for r in out}
    for sid in wanted:
        row = by_id.get(sid)
        if row is None or str(row["id"]) in seen:
            continue
        out.append(row)
        seen.add(str(row["id"]))
    return out
