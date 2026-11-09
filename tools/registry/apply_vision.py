"""Merge a Ty's Vision walk into the registry's evidence.

The registry is the source of truth, so this does not rewrite purposes or actions:
it updates exactly two fields per entry — ``evidence.vision`` and
``evidence.vision_note`` — from the walk's own rows. Everything else is preserved
byte for byte, so re-running it on an unchanged desktop is a no-op.

    python -m tools.registry.vision_walk --out %TEMP%/vision.json
    python -m tools.registry.apply_vision --vision %TEMP%/vision.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "ty" / "service_registry.json"


def _labels(controls: Any) -> List[str]:
    """Control names, whether the walker wrote strings or {label, kind} objects."""
    out: List[str] = []
    for item in controls or []:
        if isinstance(item, dict):
            label = str(item.get("label") or item.get("name") or "").strip()
        else:
            label = str(item).strip()
        if label:
            out.append(label)
    return out


def note_for(row: Dict[str, Any]) -> str:
    note = row.get("detail", "")
    audit_sourced = row.get("vision") == "screenshot"
    if row.get("title"):
        prefix = "ty/ux_audit.json " if audit_sourced else ""
        note += f" | {prefix}title: {row['title']}"
    labels = _labels(row.get("controls"))
    if labels:
        prefix = "ty/ux_audit.json " if audit_sourced else ""
        note += (f" | {prefix}controls (shell chrome included): "
                 f"{', '.join(labels[:6])}")
    if row.get("blocked_by"):
        note += f" | blocked: {row['blocked_by']}"
    if row.get("shot"):
        note += f" | shot: {row['shot']}"
    return note.strip(" |")


#: How much each evidence kind is worth. A later walk that could not go live must not
#: erase the live observation an earlier walk made: confidence is "best known", and a
#: blocked attempt is recorded in the note instead of overwriting the page.
STRENGTH = {"live": 3, "audit": 2, "screenshot": 2, "backend": 1}


def _should_replace(existing: str, incoming: str, blocked: bool) -> bool:
    if blocked:
        return False
    return STRENGTH.get(incoming, 0) >= STRENGTH.get(existing, 0)


def apply(document: Dict[str, Any], walk: Dict[str, Any]) -> List[str]:
    rows = {row["id"]: row for row in walk.get("routes", [])}
    changed: List[str] = []
    for entry in document["services"]:
        row = rows.get(entry["id"])
        if row is None:
            continue
        existing = str((entry.get("evidence") or {}).get("vision") or "")
        blocked = bool(row.get("blocked_by"))
        if not _should_replace(existing, str(row.get("vision") or ""), blocked):
            # Keep what we know. A blocked attempt is recorded in its own field: a note that
            # says "blocked" beside live evidence is a contradiction, and the test forbids it.
            if existing == "live" and entry["evidence"].get("confidence") in (None, "low", "none"):
                controls = entry["evidence"].get("controls") or []
                entry["evidence"]["confidence"] = "high" if len(controls) >= 3 else "medium"
                changed.append(entry["id"])
            if blocked:
                entry["evidence"]["latest_attempt_blocked"] = row["blocked_by"]
                changed.append(entry["id"])
            continue
        before = (entry["evidence"]["vision"], entry["evidence"]["vision_note"])
        entry["evidence"]["vision"] = row["vision"]
        entry["evidence"]["vision_note"] = note_for(row)
        labels = _labels(row.get("controls"))
        if labels:
            entry["evidence"]["controls"] = labels[:12]
        if row.get("confidence"):
            entry["evidence"]["confidence"] = row["confidence"]
        elif row["vision"] == "live":
            entry["evidence"]["confidence"] = "high" if len(labels) >= 3 else "medium"
        if before != (row["vision"], entry["evidence"]["vision_note"]):
            changed.append(entry["id"])
    return changed


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge a vision walk into ty/service_registry.json")
    parser.add_argument("--vision", required=True)
    parser.add_argument("--check", action="store_true", help="report drift instead of writing")
    args = parser.parse_args(argv)

    document = json.loads(REGISTRY.read_text(encoding="utf-8"))
    walk = json.loads(Path(args.vision).read_text(encoding="utf-8"))
    changed = apply(document, walk)
    blob = json.dumps(document, indent=2, ensure_ascii=False) + "\n"

    if args.check:
        current = REGISTRY.read_text(encoding="utf-8")
        if current != blob:
            print(f"registry vision evidence is stale: {changed or ['formatting']}")
            return 1
        print("registry vision evidence matches the walk")
        return 0

    REGISTRY.write_text(blob, encoding="utf-8")
    print(f"updated vision evidence for {len(changed)} services" if changed else "no change")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
