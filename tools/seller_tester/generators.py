"""Generator adapters — injectable, no hidden network.

`StoredGenerator` replays images already on disk (renders/, generated_images/,
Northstar_backend/data/studio_generated/). It is what tests and the real pass
use: a deterministic, offline pairing of brief to artefact.

`ComfyGenerator` is the documented live adapter. It probes the local ComfyUI
server, and refuses cleanly (no retry, no download, no spend) when ComfyUI is
not reachable. It never targets a non-loopback host.

`CompositeGenerator` is the path the owner asked for (2026-11-08): for a brief
that must keep the seller's product, cut the product out of the reference, render
only the *scene*, and place the real pixels into it. Fidelity decides:

    fidelity "exact"    -> composite (reference modes default to this)
    fidelity "tolerant" -> full generation allowed
    source_mode prompt_only -> always full generation

When the render lane is unavailable the generator raises `GeneratorUnavailable`
with the reason. It never falls back to a replayed image and never labels a
synthetic backdrop as a generated scene.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "Northstar_backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "Northstar_backend"))
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


DEFAULT_CUTOUT_METHOD = "birefnet"


def _required_size(brief: Dict[str, Any]) -> Optional[Tuple[int, int]]:
    """The brief's minimum output size, when it asks for more than the scene gives."""
    dimensions = ((brief.get("constraints") or {}).get("dimensions") or {})
    min_width = int(dimensions.get("min_width") or 0)
    min_height = int(dimensions.get("min_height") or 0)
    if min_width <= 0 and min_height <= 0:
        return None
    return (max(1, min_width), max(1, min_height))


def _upscale_to(png: bytes, required: Tuple[int, int],
                record: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
    """Lanczos upscale to the brief's minimum. Recorded, never silent.

    The lane may render smaller than the brief asks (VRAM headroom is shared with
    the resident models). Upscaling is a resample of the composited picture; it adds
    no detail, and the record says so.
    """
    from io import BytesIO

    from PIL import Image

    with Image.open(BytesIO(png)) as opened:
        width, height = opened.size
        target_w, target_h = required
        if width >= target_w and height >= target_h:
            return png, record
        factor = max(target_w / float(width), target_h / float(height))
        new_size = (int(round(width * factor)), int(round(height * factor)))
        resized = opened.convert("RGB").resize(new_size, Image.LANCZOS)
    buffer = BytesIO()
    resized.save(buffer, format="PNG")
    record["upscaled_from"] = [width, height]
    record["upscaled_to"] = list(new_size)
    record["upscale_note"] = "lanczos resample to the brief's minimum; adds no detail"
    box = record.get("product_box")
    if isinstance(box, list) and len(box) == 4:
        record["product_box"] = [int(round(value * factor)) for value in box]
    return buffer.getvalue(), record


class CompositeGenerator:
    """Cut the seller's product out of the reference and composite it into a scene.

    Same interface as the other adapters: `generate(brief) -> Path` and
    `pair(briefs) -> [(brief, path)]`. Every result is also recorded in
    `self.records`, which carries the route taken, the cutout measurements and the
    scene evidence, so a pass can report *how* each brief was produced instead of
    only what came out.

    The default method is the measured leaderboard winner
    (`tools/seller_tester/editor_bench.py`); when it needs BiRefNet the matte is
    produced inside the same ComfyUI lane as the scene, so one fresh process serves
    both steps and the stop is proved once.

    `renderer` is injectable and has the contract
    ``renderer(brief, mode, inside_lane=None) -> {bytes, source, prompt, ...}``.
    A renderer that cannot run must raise — the generator turns that into
    `GeneratorUnavailable` and produces no file.
    """

    name = "composite"

    def __init__(self, *, renderer: Optional[Any] = None,
                 renderer_name: str = "comfy",
                 method: str = DEFAULT_CUTOUT_METHOD,
                 cutout_fn: Optional[Any] = None,
                 out_dir: Optional[str | Path] = None,
                 repo_root: str | Path = REPO_ROOT,
                 seed: Optional[int] = None) -> None:
        self.repo_root = Path(repo_root)
        self.method = method
        self.cutout_fn = cutout_fn
        self.out_dir = Path(out_dir) if out_dir is not None else (
            self.repo_root / "renders" / "seller_composite")
        self.seed = seed
        if renderer is not None:
            self.renderer = renderer
            self.renderer_name = "injected"
        else:
            from .scene_render import renderer_from_name  # noqa: PLC0415

            self.renderer = renderer_from_name(renderer_name)
            self.renderer_name = renderer_name
        self.records: List[Dict[str, Any]] = []

    # ---------------------------------------------------------------- contract
    def available(self) -> Tuple[bool, str]:
        """Can this generator produce a picture right now? A stated reason if not."""
        if self.renderer_name == "injected":
            return True, "injected renderer"
        from .scene_render import lane_ready  # noqa: PLC0415

        return lane_ready()

    def route(self, brief: Dict[str, Any]) -> str:
        from .briefs import route_for_brief  # noqa: PLC0415

        return route_for_brief(brief)

    def pair(self, briefs: Sequence[Dict[str, Any]], limit: Optional[int] = None
             ) -> List[Tuple[Dict[str, Any], Path]]:
        if not briefs:
            raise GeneratorUnavailable("no briefs supplied")
        count = len(briefs) if limit is None else min(len(briefs), max(0, int(limit)))
        pairs: List[Tuple[Dict[str, Any], Path]] = []
        for brief in briefs[:count]:
            pairs.append((brief, self.generate(brief)))
        return pairs

    # ---------------------------------------------------------------- work
    def generate(self, brief: Dict[str, Any]) -> Path:
        from .briefs import brief_fidelity, route_for_brief  # noqa: PLC0415

        route = route_for_brief(brief)
        fidelity = brief_fidelity(brief)
        record: Dict[str, Any] = {
            "brief_id": brief.get("id"), "route": route, "fidelity": fidelity,
            "renderer": self.renderer_name, "method": None, "scene": None,
            "cutout": None, "product_box": None, "identity": None,
        }
        try:
            if route == "composite":
                png, record = self._composite(brief, record)
            else:
                png, record = self._full_generation(brief, record)
        except GeneratorUnavailable as exc:
            record["error"] = str(exc)
            record["artefact"] = None
            self.records.append(record)
            raise

        self.out_dir.mkdir(parents=True, exist_ok=True)
        target = self.out_dir / f"{brief.get('id') or 'brief'}.png"
        target.write_bytes(png)
        record["artefact"] = str(target)
        record["bytes"] = len(png)
        self.records.append(record)
        return target

    def _render(self, brief: Dict[str, Any], mode: str,
                inside_lane: Optional[Any] = None) -> Dict[str, Any]:
        try:
            if inside_lane is not None and self._accepts_inside_lane():
                scene = self.renderer(brief, mode, inside_lane=inside_lane)
            else:
                scene = self.renderer(brief, mode)
        except GeneratorUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001 - a renderer failure is a stated failure
            raise GeneratorUnavailable(
                f"scene render failed: {type(exc).__name__}: {exc}") from exc
        if not isinstance(scene, dict) or not scene.get("bytes"):
            raise GeneratorUnavailable("scene renderer returned no image bytes")
        return scene

    def _accepts_inside_lane(self) -> bool:
        import inspect

        try:
            parameters = inspect.signature(self.renderer).parameters
        except (TypeError, ValueError):
            return False
        return "inside_lane" in parameters or any(
            p.kind is inspect.Parameter.VAR_KEYWORD for p in parameters.values())

    def _cut(self, rgb: Any) -> Any:
        import product_cutout as pc  # noqa: PLC0415

        if self.cutout_fn is not None:
            return self.cutout_fn(rgb)
        return pc.cutout(rgb, self.method)

    def _composite(self, brief: Dict[str, Any], record: Dict[str, Any]
                   ) -> Tuple[bytes, Dict[str, Any]]:
        from . import reference_check  # noqa: PLC0415
        from .scene_render import scene_prompt  # noqa: PLC0415

        reference = brief.get("reference")
        rgb, reason, resolved = reference_check.load_reference_rgb(
            reference, repo_root=self.repo_root)
        if rgb is None:
            raise GeneratorUnavailable(f"reference unavailable: {reason}")
        record["reference_path"] = resolved

        import product_composite as composite  # noqa: PLC0415
        import product_cutout as pc  # noqa: PLC0415

        # BiRefNet lives in the media lane; the default renderer runs it inside the
        # same fresh instance it uses for the scene. Everyone else is CPU-only.
        in_lane = self.method == "birefnet" and self.cutout_fn is None
        cut = None
        scene = self._render(brief, "scene",
                             inside_lane=(lambda: self._cut(rgb)) if in_lane else None)
        if in_lane:
            cut = (scene.get("inside_lane") or {})
        if cut is None:
            cut = self._cut(rgb)
        record["method"] = self.method
        record["cutout_in_lane"] = bool(in_lane)

        reference_coverage = float(reference_check.subject_mask(rgb).mean())
        metrics = pc.alpha_metrics(cut.alpha, reference_coverage=reference_coverage)
        if metrics["subject_px"] == 0:
            raise GeneratorUnavailable(
                f"cutout method {self.method!r} found no product in {resolved}")
        record["cutout"] = {**metrics, "seconds": round(cut.seconds, 3)}

        record["scene"] = {
            "source": scene.get("source"), "prompt": scene.get("prompt"),
            "prompt_used": scene_prompt(brief),
            "image_path": scene.get("image_path"),
            "seed": scene.get("seed"), "steps": scene.get("steps"),
            "lane_stopped": bool(((scene.get("lane") or {}).get("stopped") or {}).get("ok")),
            "note": scene.get("note"),
        }

        placement = brief.get("placement") or {}
        scale = float(placement.get("scale", 0.72))
        anchor = tuple(placement.get("anchor", (0.5, 0.68)))
        cut_png = pc.rgba_png_bytes(cut.rgb, cut.alpha)
        placed = composite.place_product(scene["bytes"], cut_png, scale=scale,
                                         anchor=anchor)
        identity = composite.identity_check(placed["bytes"], cut_png,
                                            tuple(placed["product_box"]))
        record["product_box"] = list(placed["product_box"])
        record["product_scale"] = placed["product_scale"]
        record["identity"] = identity.get("ssim")
        record["identity_verdict"] = identity.get("verdict")

        png = placed["bytes"]
        required = _required_size(brief)
        if required is not None:
            png, record = _upscale_to(png, required, record)
        return png, record

    def _full_generation(self, brief: Dict[str, Any], record: Dict[str, Any]
                         ) -> Tuple[bytes, Dict[str, Any]]:
        scene = self._render(brief, "full")
        record["scene"] = {
            "source": scene.get("source"), "prompt": scene.get("prompt"),
            "image_path": scene.get("image_path"), "seed": scene.get("seed"),
            "steps": scene.get("steps"),
            "lane_stopped": bool(((scene.get("lane") or {}).get("stopped") or {}).get("ok")),
            "note": scene.get("note"),
        }
        return scene["bytes"], record

    def record_for(self, brief_id: Any) -> Optional[Dict[str, Any]]:
        for row in reversed(self.records):
            if row.get("brief_id") == brief_id:
                return row
        return None


__all__ = [
    "DEFAULT_ROOTS",
    "IMAGE_SUFFIXES",
    "GeneratorUnavailable",
    "discover_images",
    "StoredGenerator",
    "ComfyGenerator",
    "CompositeGenerator",
    "DEFAULT_CUTOUT_METHOD",
]
