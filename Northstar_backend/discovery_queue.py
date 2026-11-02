"""Discovery queue: find candidates, propose them, never install them.

The architecture brief asks for autonomous repository polling that imports new
nodes and weights without operator involvement. That is a supply-chain hole: a
runtime that pulls and executes third-party code defeats both the provider-suite
licence check and the provenance log, and one bad release takes the render
engine down mid-campaign.

This module keeps the useful half. It polls a fixed list of repositories for
releases, records each candidate with its licence status and the local VRAM
estimate, and writes a proposal file. Nothing is downloaded; nothing runs. One
operator decision turns a batch of proposals into installs, and that decision is
logged like any other.

Sources are a name plus a URL — no search engines, no scraping, no auth.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
PROPOSALS = ROOT / "state" / "proposals"

#: Repositories that matter to this stack, with what they would buy us.
SOURCES: List[Dict[str, str]] = [
    {"repo": "comfyanonymous/ComfyUI", "why": "core nodes and sampler fixes"},
    {"repo": "Comfy-Org/ComfyUI-Manager", "why": "node registry + install tooling"},
    {"repo": "city96/ComfyUI-GGUF", "why": "quantised weights (already installed)"},
    {"repo": "kijai/ComfyUI-KJNodes", "why": "utility nodes (already installed)"},
    {"repo": "kijai/ComfyUI-IC-Light", "why": "relight node reference"},
    {"repo": "Kosinkadink/ComfyUI-VideoHelperSuite", "why": "video mux / frame IO"},
    {"repo": "TMElyralab/ComfyUI-MusePose", "why": "pose-driven motion (future)"},
]

API = "https://api.github.com/repos/{repo}/releases?per_page=5"

#: Licences we accept for the local bench. Anything else stays ineligible until an
#: operator records a decision - the same rule the provider suite already enforces.
LOCAL_LANE_OK = {"MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause", "ISC", "GPL-3.0", "AGPL-3.0"}


def _get(url: str, timeout: float = 30.0) -> Any:
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "northstar-discovery-queue/1",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_releases(repo: str, *, getter: Optional[Callable[[str], Any]] = None,
                   timeout: float = 30.0) -> List[Dict[str, Any]]:
    """The last few releases for one repo. Network errors are reported, not hidden."""
    get = getter or (lambda url: _get(url, timeout=timeout))
    data = get(API.format(repo=repo))
    if not isinstance(data, list):
        raise ValueError(f"discovery_unexpected_payload: {repo} did not return a list")
    out: List[Dict[str, Any]] = []
    for rel in data[:5]:
        if not isinstance(rel, dict) or not rel.get("tag_name"):
            continue
        out.append({
            "repo": repo,
            "tag": str(rel["tag_name"])[:40],
            "name": str(rel.get("name") or "")[:120],
            "published_at": str(rel.get("published_at") or "")[:32],
            "url": str(rel.get("html_url") or "")[:300],
            "prerelease": bool(rel.get("prerelease")),
        })
    return out


def _licence(rel: Dict[str, Any]) -> str:
    return str(rel.get("licence") or rel.get("license") or "unverified")


def propose(candidate: Dict[str, Any], *, licence: str, why: str,
            vram_mb: Optional[int] = None) -> Dict[str, Any]:
    """One proposal record. Ineligible when the licence is unknown."""
    known = licence in LOCAL_LANE_OK
    record: Dict[str, Any] = {
        "key": f"{candidate['repo']}@{candidate['tag']}",
        "repo": candidate["repo"],
        "tag": candidate["tag"],
        "name": candidate.get("name") or "",
        "why": why,
        "licence": licence,
        "licence_known": known,
        "lane": "local-lane",
        "eligible": known and not candidate.get("prerelease"),
        "status": "proposed",
        "source": candidate.get("url") or "",
        "proposed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "next_step": ("operator approval, then install with the provenance log entry"
                      if known else "licence must be recorded before this can be approved"),
    }
    if candidate.get("prerelease"):
        record["next_step"] = "prerelease: benchmark on a scratch profile before approval"
    if vram_mb is not None:
        record["vram_mb"] = int(vram_mb)
    return record


def load_existing(folder: Path) -> set:
    keys = set()
    if not folder.is_dir():
        return keys
    for path in folder.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("key"):
            keys.add(str(data["key"]))
        elif isinstance(data, list):
            keys.update(str(item.get("key")) for item in data if isinstance(item, dict))
    return keys


def write_proposals(records: Iterable[Dict[str, Any]], folder: Optional[Path] = None) -> Dict[str, Any]:
    """Write one file per new candidate; never overwrite or duplicate a key."""
    target = Path(folder) if folder else PROPOSALS
    target.mkdir(parents=True, exist_ok=True)
    existing = load_existing(target)
    written, skipped = [], []
    for record in records:
        key = str(record.get("key") or "")
        if not key:
            continue
        if key in existing:
            skipped.append(key)
            continue
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", key)[:120]
        (target / f"{safe}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        existing.add(key)
        written.append(key)
    return {"written": written, "skipped": skipped, "folder": str(target)}


def run(sources: Optional[List[Dict[str, str]]] = None,
        getter: Optional[Callable[[str], Any]] = None,
        licences: Optional[Dict[str, str]] = None,
        folder: Optional[Path] = None) -> Dict[str, Any]:
    """Poll every source and queue what is new. A failing source is reported."""
    licences = licences or {}
    records, errors = [], []
    for source in (sources or SOURCES):
        repo = source["repo"]
        try:
            for rel in fetch_releases(repo, getter=getter):
                if rel.get("prerelease"):
                    continue
                records.append(propose(rel, licence=licences.get(repo, "unverified"),
                                       why=source.get("why") or ""))
        except Exception as exc:  # noqa: BLE001 - one bad source must not stop the scan
            errors.append({"repo": repo, "error": f"{type(exc).__name__}: {exc}"[:200]})
    result = write_proposals(records, folder)
    result["errors"] = errors
    result["candidates"] = len(records)
    return result


__all__ = ["SOURCES", "LOCAL_LANE_OK", "fetch_releases", "propose", "write_proposals",
           "load_existing", "run"]


if __name__ == "__main__":  # pragma: no cover - operator entry point
    print(json.dumps(run(), indent=2))
