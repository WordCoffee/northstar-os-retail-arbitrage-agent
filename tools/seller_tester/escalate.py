"""Difficulty escalation — the brief ladder never runs dry.

After a pass the brief gets harder, in this order:

1. `raise_tier`      difficulty 1 -> 2 -> 3, with tighter fill and background.
2. `add_constraint`  one new hard constraint (tight background, narrow fill,
                     4 MB file cap, strict text-free).
3. `new_category`    a fresh brief in a category the loop has not hit yet,
                     carrying a fresh constraint set.

Escalation stays **inside the brief's input mode**: a `stored_reference` brief
escalates to another stored-reference brief, never to a prompt-only one, and a
new reference brief keeps a reference (reusing the original when the catalog
has no same-mode template for that category). A mode that changes mid-ladder
would silently test a different product input.

`escalate()` is pure and always returns a usable brief. `EscalationLog` records
every step (tracked in the run summary, mirrored to runtime state) so a later
session can resume the ladder without guessing.
"""
from __future__ import annotations

import copy
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .briefs import CATEGORIES, REFERENCE_MODES, SITUATIONS, brief_mode

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ESCALATION_PATH = REPO_ROOT / "state" / "seller" / "escalation.json"

CONSTRAINT_POOL = (
    "tight_background",
    "narrow_fill",
    "file_size_cap_4mb",
    "strict_text_free",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _tighten_fill(brief: Dict[str, Any], margin: float = 5.0) -> None:
    fill = brief.setdefault("constraints", {}).setdefault("fill_pct", {})
    low = float(fill.get("min", 0.0)) + margin
    high = float(fill.get("max", 100.0)) - margin
    if high - low >= 5:
        fill["min"] = round(low, 1)
        fill["max"] = round(high, 1)


def _apply_constraint(brief: Dict[str, Any], name: str) -> None:
    constraints = brief.setdefault("constraints", {})
    if name == "tight_background":
        background = constraints.setdefault("background", {"value": 255, "mode": "uniform"})
        background["tolerance"] = max(2, int(background.get("tolerance", 6)) - 2)
    elif name == "narrow_fill":
        _tighten_fill(brief, 5.0)
    elif name == "file_size_cap_4mb":
        size = constraints.setdefault("file_size", {"min_bytes": 20000, "max_bytes": 20_000_000})
        size["max_bytes"] = min(int(size.get("max_bytes", 20_000_000)), 4_000_000)
    elif name == "strict_text_free":
        constraints["text_rule"] = "no_text"
        constraints["text_max_ink"] = 0.01
    else:  # pragma: no cover - pool is closed
        raise ValueError(f"unknown constraint {name!r}")
    added = brief.setdefault("added_constraints", [])
    if name not in added:
        added.append(name)


def _fresh_brief_from_catalog(brief: Dict[str, Any], category: str,
                              situation: str, catalog: Sequence[Dict[str, Any]],
                              index: int, mode: str) -> Dict[str, Any]:
    """A new brief that keeps the ladder inside the same input mode."""
    same_category = [row for row in catalog
                     if row.get("category") == category and brief_mode(row) == mode]
    same_mode = [row for row in catalog if brief_mode(row) == mode]
    template = None
    if same_category:
        template = same_category[0]
    elif same_mode:
        template = same_mode[0]
    else:
        template = next((row for row in catalog if row.get("category") == category), brief)
    derived = copy.deepcopy(template)
    derived["id"] = f"{brief.get('id', 'ST')}-c{index}"
    derived["category"] = category
    derived["situation"] = situation
    derived["difficulty"] = 1
    derived["derived_from"] = brief.get("id")
    derived["added_constraints"] = []
    if mode in REFERENCE_MODES:
        derived["source_mode"] = mode
        if not isinstance(derived.get("reference"), dict):
            reference = brief.get("reference")
            if isinstance(reference, dict):
                derived["reference"] = copy.deepcopy(reference)
                derived["reference_reused"] = True
    elif mode in ("prompt_only", "unclassified"):
        derived["source_mode"] = mode
        derived.pop("reference", None)
    return derived


def escalate(brief: Dict[str, Any], catalog: Sequence[Dict[str, Any]],
             used_categories: Optional[Sequence[str]] = None,
             source_mode: Optional[str] = None) -> Dict[str, Any]:
    """Return {action, detail, brief, constraint}. Never returns None.

    `source_mode` overrides the brief's own mode; both must be a known mode (or
    `unclassified` for ad-hoc briefs built in process). An unknown mode is
    refused rather than guessed.
    """
    mode = source_mode if source_mode is not None else brief_mode(brief)
    if mode not in ("prompt_only", "stored_reference", "uploaded_reference", "unclassified"):
        raise ValueError(f"unknown source_mode {mode!r}; escalation will not guess an input")
    used = set(used_categories or ())
    used.add(str(brief.get("category")))
    tier = int(brief.get("difficulty", 1) or 1)

    if tier < 3:
        derived = copy.deepcopy(brief)
        derived["source_mode"] = mode
        derived["difficulty"] = tier + 1
        derived["escalated_from"] = brief.get("escalated_from") or brief.get("id")
        _tighten_fill(derived, 4.0)
        background = derived.setdefault("constraints", {}).setdefault(
            "background", {"value": 255, "mode": "uniform"})
        if background.get("mode", "uniform") == "uniform":
            background["tolerance"] = max(2, int(background.get("tolerance", 6)) - 1)
        derived["pass_score"] = min(95, int(derived.get("pass_score", 70)) + 5)
        return {"action": "raise_tier",
                "detail": f"difficulty {tier} -> {tier + 1} ({mode})",
                "brief": derived, "constraint": None}

    added = list(brief.get("added_constraints") or [])
    remaining = [name for name in CONSTRAINT_POOL if name not in added]
    if remaining:
        name = remaining[0]
        derived = copy.deepcopy(brief)
        derived["source_mode"] = mode
        derived["escalated_from"] = brief.get("escalated_from") or brief.get("id")
        _apply_constraint(derived, name)
        derived["pass_score"] = min(95, int(derived.get("pass_score", 70)) + 3)
        return {"action": "add_constraint",
                "detail": f"added hard constraint {name} ({mode})",
                "brief": derived, "constraint": name}

    situation = str(brief.get("situation") or SITUATIONS[0])
    next_situation = SITUATIONS[(SITUATIONS.index(situation) + 1) % len(SITUATIONS)] \
        if situation in SITUATIONS else SITUATIONS[0]
    unused = [name for name in CATEGORIES if name not in used]
    category = unused[0] if unused else CATEGORIES[len(used) % len(CATEGORIES)]
    index = len(used) + 1
    derived = _fresh_brief_from_catalog(
        brief, category, next_situation, catalog, index, mode)
    return {"action": "new_category",
            "detail": f"new {category} brief in {next_situation} (id {derived['id']}, {mode})",
            "brief": derived, "constraint": None}


class EscalationLog:
    """Append-only escalation history with optional JSON persistence."""

    def __init__(self, path: str | Path | None = DEFAULT_ESCALATION_PATH) -> None:
        self.path = Path(path) if path is not None else None
        self.entries: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, ValueError):
            return
        rows = payload.get("entries") if isinstance(payload, dict) else payload
        if isinstance(rows, list):
            self.entries = [row for row in rows if isinstance(row, dict)]

    def record(self, brief: Dict[str, Any], step: Dict[str, Any], *,
               score: Optional[float] = None, artefact_path: Optional[str] = None,
               at: Optional[str] = None,
               source_mode: Optional[str] = None) -> Dict[str, Any]:
        new_brief = step.get("brief") or {}
        entry = {
            "at": at or _now(),
            "from_brief_id": brief.get("id"),
            "from_difficulty": brief.get("difficulty"),
            "source_mode": source_mode or brief_mode(brief),
            "action": step.get("action"),
            "detail": step.get("detail"),
            "constraint": step.get("constraint"),
            "to_brief_id": new_brief.get("id"),
            "to_difficulty": new_brief.get("difficulty"),
            "score": None if score is None else round(float(score), 1),
            "artefact_path": artefact_path,
        }
        self.entries.append(entry)
        return entry

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=str(self.path.parent),
            prefix=self.path.name + ".", suffix=".tmp", delete=False)
        try:
            with handle:
                json.dump({"schema_version": 1, "entries": self.entries},
                          handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            os.replace(handle.name, self.path)
        except BaseException:
            try:
                os.unlink(handle.name)
            except OSError:
                pass
            raise


__all__ = [
    "CONSTRAINT_POOL",
    "DEFAULT_ESCALATION_PATH",
    "escalate",
    "EscalationLog",
]
