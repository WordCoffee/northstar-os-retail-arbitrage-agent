"""Baseline protocol.

A visual gate that updates its own baselines is not a gate — it is a screenshot
tool. So promotion of a captured image to a baseline is a separate, explicitly
armed operation:

    python -m tools.visual_regression.gate --base-url ... --update-baseline --scorecard-passed

``--scorecard-passed`` is required and is not implied by anything else. Without
it the gate refuses (exit 2) and touches no file.

Every accepted promotion appends to ``baselines/CHANGELOG.json``: timestamp,
view, viewport, commit sha, scorecard result, and the sha256 of the image it
replaced. The changelog is append-only; nothing in this module deletes history.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

BASELINES_ROOT = Path(__file__).resolve().parent / "baselines"
CHANGELOG_NAME = "CHANGELOG.json"
CHANGELOG_SCHEMA = "northstar.visual_baseline_changelog.v1"


class BaselineRefused(RuntimeError):
    """Promotion was attempted without the required evidence."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def baseline_path(
    view_id: str, viewport_id: str, root: str | Path = BASELINES_ROOT
) -> Path:
    return Path(root) / view_id / f"{viewport_id}.png"


def changelog_path(root: str | Path = BASELINES_ROOT) -> Path:
    return Path(root) / CHANGELOG_NAME


def load_changelog(root: str | Path = BASELINES_ROOT) -> Dict[str, Any]:
    path = changelog_path(root)
    if not path.exists():
        return {"schema": CHANGELOG_SCHEMA, "entries": []}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("schema", CHANGELOG_SCHEMA)
    data.setdefault("entries", [])
    return data


def _write_json_atomic(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=False)
            fh.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _copy_atomic(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(dest.parent), prefix=".tmp-", suffix=".png")
    os.close(fd)
    try:
        shutil.copyfile(src, tmp)
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _normalise_scorecard(
    scorecard: Optional[Mapping[str, Any]], scorecard_passed: bool
) -> Dict[str, Any]:
    if scorecard is None:
        return {
            "passed": bool(scorecard_passed),
            "source": "--scorecard-passed",
        }
    out = dict(scorecard)
    out.setdefault("passed", bool(scorecard_passed))
    out.setdefault("source", "scorecard-file")
    if out["passed"] is not True:
        raise BaselineRefused(
            f"scorecard file reports passed={out['passed']!r}; refusing to move the baseline"
        )
    return out


def update_baselines(
    artifacts: Sequence[Mapping[str, Any]],
    *,
    scorecard_passed: bool,
    scorecard: Optional[Mapping[str, Any]] = None,
    commit: str,
    root: str | Path = BASELINES_ROOT,
    timestamp: Optional[str] = None,
    prior_verdicts: Optional[Mapping[tuple, str]] = None,
) -> List[Dict[str, Any]]:
    """Promote captured artifacts to baselines and append changelog entries.

    ``artifacts``: ``[{"view": id, "viewport": id, "path": "/abs/x.png"}, ...]``
    ``prior_verdicts``: optional ``{(view, viewport): verdict}`` from the diff run
    that is being accepted, recorded so the changelog says what was accepted.
    """
    if not scorecard_passed:
        raise BaselineRefused(
            "refusing to update baseline: --scorecard-passed is required. "
            "A baseline may only move when the scorecard for the build passed."
        )
    if not artifacts:
        raise BaselineRefused("refusing to update baseline: no captured artifacts")

    scorecard_out = _normalise_scorecard(scorecard, scorecard_passed)
    ts = timestamp or utc_now()
    log = load_changelog(root)
    entries: List[Dict[str, Any]] = []

    for artifact in artifacts:
        view_id = str(artifact["view"])
        viewport_id = str(artifact["viewport"])
        src = Path(str(artifact["path"]))
        if not src.is_file() or src.stat().st_size == 0:
            raise BaselineRefused(f"refusing to promote missing or empty artifact: {src}")

        dest = baseline_path(view_id, viewport_id, root)
        previous = sha256_file(dest) if dest.exists() else None
        _copy_atomic(src, dest)

        entry = {
            "ts": ts,
            "view": view_id,
            "viewport": viewport_id,
            "commit": commit,
            "scorecard": scorecard_out,
            "baseline": str(dest.relative_to(Path(root)).as_posix()),
            "baseline_sha256": sha256_file(dest),
            "previous_baseline_sha256": previous,
            "source_artifact": str(src),
            "prior_verdict": (
                prior_verdicts.get((view_id, viewport_id)) if prior_verdicts else None
            ),
        }
        log["entries"].append(entry)
        entries.append(entry)

    log["updated"] = ts
    _write_json_atomic(changelog_path(root), log)
    return entries


def describe_missing(
    results: Iterable[Mapping[str, Any]],
) -> List[tuple]:
    """(view, viewport) pairs that have no baseline yet."""
    return [
        (r["view"], r["viewport"])
        for r in results
        if r.get("verdict") == "no_baseline"
    ]
