"""Generator adapters — injectable, no hidden network.

`StoredGenerator` replays images already on disk (renders/, generated_images/,
Northstar_backend/data/studio_generated/). It is what tests and the real pass
use: a deterministic, offline pairing of brief to artefact.

`ComfyGenerator` is the documented live adapter. It probes the local ComfyUI
server, and refuses cleanly (no retry, no download, no spend) when ComfyUI is
not reachable. It never targets a non-loopback host.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOTS = (
    REPO_ROOT / "renders",
    REPO_ROOT / "generated_images",
    REPO_ROOT / "Northstar_backend" / "data" / "studio_generated",
)
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


class GeneratorUnavailable(RuntimeError):
    """The generator cannot produce an image right now. Never retried silently."""


def discover_images(roots: Iterable[str | Path]) -> List[Path]:
    """Deterministic, deduplicated list of image files under the roots."""
    found: List[Path] = []
    seen = set()
    for root in roots:
        base = Path(root)
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            key = str(path.resolve()).lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(path)
    return found


class StoredGenerator:
    """Replay stored artefacts. Offline, deterministic, one cursor."""

    name = "stored"

    def __init__(self, roots: Optional[Sequence[str | Path]] = None) -> None:
        self.roots = [Path(r) for r in (roots if roots is not None else DEFAULT_ROOTS)]
        self._artefacts = discover_images(self.roots)
        self._cursor = 0

    @property
    def artefacts(self) -> List[Path]:
        return list(self._artefacts)

    def __len__(self) -> int:
        return len(self._artefacts)

    def generate(self, brief: Dict[str, Any]) -> Path:
        if not self._artefacts:
            raise GeneratorUnavailable(
                "stored generator found no images under: "
                + ", ".join(str(r) for r in self.roots))
        path = self._artefacts[self._cursor % len(self._artefacts)]
        self._cursor += 1
        return path

    def pair(self, briefs: Sequence[Dict[str, Any]], limit: Optional[int] = None
             ) -> List[Tuple[Dict[str, Any], Path]]:
        """Pair brief i with artefact i (both rotate). Stops at the shorter side."""
        if not briefs:
            raise GeneratorUnavailable("no briefs supplied")
        if not self._artefacts:
            raise GeneratorUnavailable(
                "stored generator found no images under: "
                + ", ".join(str(r) for r in self.roots))
        count = min(len(self._artefacts), len(briefs))
        if limit is not None:
            count = min(count, max(0, int(limit)))
        return [(briefs[i], self._artefacts[i]) for i in range(count)]


class ComfyGenerator:
    """Documented local ComfyUI adapter (not used by tests or the stored pass).

    Contract: `available()` probes GET /system_stats on a loopback host with a
    short timeout. `generate()` raises GeneratorUnavailable unless the server is
    up. No model is downloaded, no queue item is submitted here — wiring an
    actual workflow is a separate, operator-visible step. No Amazon host, no
    cloud host, no spend.
    """

    name = "comfy"

    def __init__(self, base_url: str = "http://127.0.0.1:8188",
                 timeout: float = 1.5) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)
        if not any(host in self.base_url for host in ("127.0.0.1", "localhost", "::1")):
            raise ValueError("ComfyGenerator refuses non-loopback hosts")

    def available(self) -> Tuple[bool, str]:
        url = f"{self.base_url}/system_stats"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                payload = json.loads(response.read().decode("utf-8") or "{}")
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return False, f"comfy_unreachable: {type(exc).__name__}: {exc}"[:300]
        if not isinstance(payload, dict) or "system" not in payload:
            return False, "comfy_unreachable: unexpected /system_stats payload"
        return True, f"comfy ready at {self.base_url}"

    def generate(self, brief: Dict[str, Any]) -> Path:
        ok, detail = self.available()
        if not ok:
            raise GeneratorUnavailable(
                f"{detail}; brief {brief.get('id')!r} was not generated and nothing was retried")
        raise GeneratorUnavailable(
            "ComfyUI is reachable but this adapter has no armed workflow; "
            "wire a workflow and an explicit output dir before use")


__all__ = [
    "DEFAULT_ROOTS",
    "IMAGE_SUFFIXES",
    "GeneratorUnavailable",
    "discover_images",
    "StoredGenerator",
    "ComfyGenerator",
]
