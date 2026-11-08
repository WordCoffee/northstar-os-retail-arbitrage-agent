"""Gap filing — every failed output becomes a tracked record.

The tracked file is `ty/seller_gaps.json` (state/ is gitignored). The same
records are mirrored to `state/seller/gaps.json` for runtime readers.

Record shape (exact):

    {"id", "brief_id", "score", "failed_checks", "artefact_path", "at"}

The id is deterministic in (brief_id, artefact_path), so re-running the same
brief against the same artefact updates the record instead of duplicating it.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GAPS_PATH = REPO_ROOT / "ty" / "seller_gaps.json"
DEFAULT_MIRROR_PATH = REPO_ROOT / "state" / "seller" / "gaps.json"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def gap_id(brief_id: str, artefact_path: str) -> str:
    digest = hashlib.sha1(f"{brief_id}:{artefact_path}".encode("utf-8")).hexdigest()
    return f"gap-{digest[:12]}"


def _relative(path: str | Path) -> str:
    try:
        resolved = Path(path).resolve()
        return resolved.relative_to(REPO_ROOT).as_posix()
    except (ValueError, OSError):
        return str(path)


def build_gap(brief_id: str, result: Dict[str, Any], artefact_path: str | Path,
              at: Optional[str] = None) -> Dict[str, Any]:
    rel = _relative(artefact_path)
    return {
        "id": gap_id(brief_id, rel),
        "brief_id": brief_id,
        "score": round(float(result.get("score", 0.0)), 1),
        "failed_checks": list(result.get("failed_checks") or []),
        "artefact_path": rel,
        "at": at or _now(),
    }


def read_gaps(path: str | Path = DEFAULT_GAPS_PATH) -> List[Dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    try:
        with open(target, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except (OSError, ValueError):
        return []
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict) and isinstance(payload.get("gaps"), list):
        return [row for row in payload["gaps"] if isinstance(row, dict)]
    return []


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), prefix=path.name + ".", suffix=".tmp",
        delete=False)
    try:
        with handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        os.replace(handle.name, path)
    except BaseException:
        try:
            os.unlink(handle.name)
        except OSError:
            pass
        raise


def file_gap(gap: Dict[str, Any], path: str | Path = DEFAULT_GAPS_PATH,
             mirror: str | Path | None = DEFAULT_MIRROR_PATH) -> Dict[str, Any]:
    """Insert or update one gap record; mirror it when a mirror path is given."""
    missing = {"id", "brief_id", "score", "failed_checks", "artefact_path", "at"} - set(gap)
    if missing:
        raise ValueError(f"gap record missing fields: {sorted(missing)}")
    record = {
        "id": str(gap["id"]),
        "brief_id": str(gap["brief_id"]),
        "score": round(float(gap["score"]), 1),
        "failed_checks": [str(c) for c in (gap["failed_checks"] or [])],
        "artefact_path": str(gap["artefact_path"]),
        "at": str(gap["at"]),
    }

    tracked_path = Path(path)
    rows = read_gaps(tracked_path)
    replaced = False
    for index, row in enumerate(rows):
        if row.get("id") == record["id"]:
            rows[index] = record
            replaced = True
            break
    if not replaced:
        rows.append(record)
    rows.sort(key=lambda row: (str(row.get("brief_id")), str(row.get("artefact_path"))))
    _atomic_write_json(tracked_path, rows)

    if mirror is not None:
        _atomic_write_json(Path(mirror), rows)

    return record


__all__ = [
    "DEFAULT_GAPS_PATH",
    "DEFAULT_MIRROR_PATH",
    "gap_id",
    "build_gap",
    "read_gaps",
    "file_gap",
]
