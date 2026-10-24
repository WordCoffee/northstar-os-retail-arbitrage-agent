"""Build lessons — what a real build taught, kept so the next build inherits it.

The package lane changed three times while building one product, and each change
came from looking at the output. Without a store, that knowledge dies with the
session and the next build repeats the mistakes.

Semantics (deliberately narrow):
  PROPOSED  a lesson observed but not yet reflected in code
  APPLIED   the lesson is encoded in code, with the file that encodes it
  REJECTED  considered and not adopted, with the reason

This store never edits policy, never runs code and never calls out. It is read by
the agent prompts and by `specialists.package_designer` for its notes.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

STORE = Path(__file__).resolve().parent.parent / "data" / "build_lessons.json"

#: Lessons learned by building the Mogra Lion's Mane 6 oz doypack, 2026-10-23.
SEED: List[Dict[str, Any]] = [
    {
        "id": "L1",
        "area": "dieline",
        "status": "APPLIED",
        "lesson": ("The doypack dieline draws the GUSSET panel rotated on the flat sheet, so its "
                   "rect width is the pouch width and its rect height is the gusset depth. Using "
                   "width for both produced a 95/95/95 visible split."),
        "evidence": "build-mogra-per-panel.png (first attempt), meta.panels.gusset = [9,217,95,80]",
        "applied_in": "specialists/panel_map.py::panel_widths uses min(w, h) for the gusset",
    },
    {
        "id": "L2",
        "area": "geometry",
        "status": "APPLIED",
        "lesson": ("A gusset is edge-on in a front view, so only a fraction of its depth is "
                   "visible. Allocating the full depth gave 31/37/31 % gusset/front/gusset and the "
                   "subtitle clipped at both ends."),
        "evidence": "build-mogra-per-panel.png (second attempt): 'ORC ... DER'",
        "applied_in": "specialists/panel_map.py::GUSSET_FORESIGHTEN = 0.35",
    },
    {
        "id": "L3",
        "area": "compositing",
        "status": "APPLIED",
        "lesson": ("Warping each surface separately leaves hard seams where the strips meet the "
                   "front, because every warp carries its own surface maps. Compose ONE wrapped "
                   "artwork and warp once."),
        "evidence": "build-mogra-per-panel.png (third attempt): dashed vertical seams",
        "applied_in": "pouch_label.py::_wrap_panel + single warp_panel call",
    },
    {
        "id": "L4",
        "area": "compositing",
        "status": "PROPOSED",
        "lesson": ("The gusset strips currently carry plain field colour. A real gusset shows the "
                   "SIDE PANEL (weight, claims, cert marks) — `specialists.panels.render_side_panel` "
                   "already draws it, so the wrapped artwork should use it."),
        "evidence": "build-mogra-per-panel.png (fourth attempt): side strips are blank",
        "applied_in": None,
    },
]


def load() -> List[Dict[str, Any]]:
    if STORE.is_file():
        try:
            return json.loads(STORE.read_text(encoding="utf-8"))
        except ValueError:
            return list(SEED)
    return list(SEED)


def save(lessons: List[Dict[str, Any]]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(lessons, indent=2), encoding="utf-8")


def record(lesson: str, *, area: str, evidence: str = "",
           applied_in: Optional[str] = None, status: Optional[str] = None) -> Dict[str, Any]:
    lessons = load()
    lid = f"L{len(lessons) + 1}"
    entry = {
        "id": lid, "area": area,
        "status": status or ("APPLIED" if applied_in else "PROPOSED"),
        "lesson": lesson, "evidence": evidence, "applied_in": applied_in,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    lessons.append(entry)
    save(lessons)
    return entry


def active(area: Optional[str] = None) -> List[Dict[str, Any]]:
    return [l for l in load()
            if l.get("status") == "APPLIED" and (area is None or l.get("area") == area)]


def notes_for_prompt(area: Optional[str] = None) -> str:
    """Short block an agent prompt can carry (applied lessons only)."""
    items = active(area)
    if not items:
        return ""
    return "Known constraints from previous builds:\n" + "\n".join(
        f"- [{l['id']}] {l['lesson']}" for l in items)


def ensure_seeded() -> List[Dict[str, Any]]:
    if not STORE.is_file():
        save(list(SEED))
    return load()
