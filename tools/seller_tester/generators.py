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
import time
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


class ProductPipelineGenerator:
    """Render the seller's brief through the **app's own** product-picture path.

    D-011: the harness used to draw its own label (`label_warp.compose_label`) and
    warp it with its own quad, so every seller number was a number about the
    harness. `product_picture.build` is what the product actually ships, and it
    takes an injectable plate, so this adapter supplies the plate and lets the app
    measure the face, compose its own artwork and run its own OCR gate.

    Contract is the same as `CompositeGenerator`: `generate(brief) -> Path`,
    `pair(briefs)`, `route(brief)`, `record_for(brief_id)`. A brief the app cannot
    serve raises `GeneratorUnavailable` with the app's own refusal reason — it is
    never replayed as a lookalike.

    The records carry the build manifest per face, so a summary can say *why* a
    picture was refused instead of only that it was.
    """

    name = "product_pipeline"

    def __init__(self, *, renderer: Optional[Any] = None,
                 renderer_name: str = "comfy",
                 out_dir: Optional[str | Path] = None,
                 repo_root: str | Path = REPO_ROOT,
                 seed: Optional[int] = None,
                 face: str = "front") -> None:
        self.repo_root = Path(repo_root)
        self.out_dir = Path(out_dir) if out_dir is not None else (
            self.repo_root / "renders" / "seller_product")
        self.seed = seed
        self.face = face
        if renderer is not None:
            self.renderer = renderer
            if type(renderer).__name__ == "ComfySceneRenderer":
                self.renderer_name = "comfy"
            elif renderer_name in ("drawn", "synthetic"):
                self.renderer_name = renderer_name
            else:
                self.renderer_name = "injected"
        else:
            from .scene_render import renderer_from_name  # noqa: PLC0415

            self.renderer = renderer_from_name(renderer_name)
            self.renderer_name = renderer_name
        self.records: List[Dict[str, Any]] = []

    # ---------------------------------------------------------------- contract
    def available(self) -> Tuple[bool, str]:
        if self.renderer_name in ("injected", "drawn", "synthetic"):
            return True, f"{self.renderer_name} plate"
        from .scene_render import lane_ready  # noqa: PLC0415

        return lane_ready()

    def route(self, brief: Dict[str, Any]) -> str:
        return "product_picture"

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
    def _design(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        import brand_art  # noqa: PLC0415

        try:
            return brand_art.design_for_brief(brief)
        except ValueError as exc:
            raise GeneratorUnavailable(str(exc)) from exc

    def _plate(self, brief: Dict[str, Any], size: Tuple[int, int]) -> Dict[str, Any]:
        """The photograph the app prints on: an unlettered body on the brief's field."""
        if str(brief.get("label_mode") or "") != "warp":
            raise GeneratorUnavailable(
                "brief asks the model for the lettering; the app composes lettering "
                "from the design, so this brief needs label_mode 'warp' with a "
                "body_prompt before the app path can serve it")
        kwargs: Dict[str, Any] = {}
        if self.renderer_name == "drawn":
            kwargs["size"] = (int(size[0]), int(size[1]))
        scene = self.renderer(brief, **kwargs)
        record = {
            "source": scene.get("source"),
            "prompt": scene.get("prompt"),
            "model": scene.get("model"),
            "width": scene.get("width"),
            "height": scene.get("height"),
            "seed": scene.get("seed"),
            "note": scene.get("note"),
        }
        if scene.get("source") == "synthetic_plate":
            return {"bytes": scene["bytes"], "plate": record}
        raise GeneratorUnavailable(
            "the render lane returned a scene, not a plate: this adapter has no "
            "plate step for a scene ('synthetic_plate' or a real blank-package "
            f"render is required, got {scene.get('source')!r})")

    def generate(self, brief: Dict[str, Any]) -> Path:
        started = time.time()
        brief_id = str(brief.get("id") or "brief")
        size = _required_size(brief) or (1536, 1536)
        width, height = int(size[0]), int(size[1])
        record: Dict[str, Any] = {
            "brief_id": brief_id,
            "route": "product_picture",
            "fidelity": brief.get("fidelity"),
            "renderer": self.renderer_name,
            "design": None,
            "form": None,
            "plate": None,
            "build": None,
            "product_box": None,
        }
        try:
            import brand_art  # noqa: PLC0415
            import product_picture as pp  # noqa: PLC0415

            design = self._design(brief)
            record["design"] = design.get("id") or design.get("brand")
            plate = self._plate(brief, (width, height))
            payload = plate["bytes"]
            record["plate"] = plate["plate"]
            record["form"] = brand_art.form_of(design)

            def _plate_source(_brief_text, *, width, height, tier, seed):
                return {"bytes": payload, "seed": seed, "model": "supplied-plate",
                        "width": width, "height": height, "contains_text": False}

            result = pp.build(
                design,
                out_dir=str(self.out_dir / brief_id),
                out_root=str(self.out_dir),
                faces=(self.face,),
                width=width,
                height=height,
                seed=self.seed,
                units=int(brief.get("units") or 1),
                generator=_plate_source,
            )
            record["build"] = {
                "ok": result.get("ok"),
                "form": (result.get("product") or {}).get("form"),
                "units": (result.get("product") or {}).get("units"),
                "faces": [{k: face.get(k) for k in ("face", "stage", "gate_ok", "reason",
                                                    "units_found")}
                          for face in result.get("faces") or []],
                "manifest": str(self.out_dir / brief_id / "product_picture_manifest.json"),
            }
            face_record = (result.get("faces") or [{}])[0]
            if not result.get("ok") or not face_record.get("file"):
                reasons = "; ".join(
                    f"{row.get('face')}: {row.get('reason')}"
                    for row in result.get("faces") or [] if not row.get("ok"))
                raise GeneratorUnavailable(
                    f"product_picture refused brief {brief_id}: {reasons or 'no file'}")
        except GeneratorUnavailable as exc:
            record["error"] = str(exc)
            record["artefact"] = None
            record["seconds"] = round(time.time() - started, 2)
            self.records.append(record)
            raise
        except Exception as exc:  # noqa: BLE001 - a lane failure is the reason
            record["error"] = f"{type(exc).__name__}: {exc}"
            record["artefact"] = None
            record["seconds"] = round(time.time() - started, 2)
            self.records.append(record)
            raise GeneratorUnavailable(str(exc)) from exc

        target = Path(face_record["file"])
        record["artefact"] = str(target)
        record["bytes"] = int(face_record.get("bytes") or 0)
        record["seconds"] = round(time.time() - started, 2)
        self.records.append(record)
        return target

    def record_for(self, brief_id: Any) -> Optional[Dict[str, Any]]:
        for record in reversed(self.records):
            if str(record.get("brief_id")) == str(brief_id):
                return record
        return None


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

#: The Amazon main-image situation is a *pure composite on flat white*: no scene
#: model, no grade, no gradient. Canvas and subject fill are requirements, not
#: preferences (2026-11-08 owner instruction after MG-C01 produced a grey "white"
#: studio and failed its own background check).
WHITE_MAIN_SITUATION = "white_background_main"
WHITE_CANVAS_PX = 2000
WHITE_FILL = 0.85
WHITE_LEVEL = 255


def _as_rgb(png: bytes):
    from io import BytesIO  # noqa: PLC0415

    from PIL import Image  # noqa: PLC0415

    return Image.open(BytesIO(png)).convert("RGB")


def split_rgba_bytes(png: bytes):
    """RGB and alpha (0..1) from a PNG the generator saved, or (None, None)."""
    from io import BytesIO  # noqa: PLC0415

    import numpy as np  # noqa: PLC0415

    from .composite_check import split_rgba  # noqa: PLC0415

    try:
        from PIL import Image  # noqa: PLC0415

        with Image.open(BytesIO(png)) as opened:
            return split_rgba(np.asarray(opened.convert("RGBA")))
    except Exception:  # noqa: BLE001
        return None, None


def _resize_png(png: bytes, side: int) -> bytes:
    """Resample a square plate up to the brief's size. Recorded, never silent."""
    from io import BytesIO  # noqa: PLC0415

    from PIL import Image  # noqa: PLC0415

    with Image.open(BytesIO(png)) as opened:
        image = opened.convert("RGB")
        if image.width == side and image.height == side:
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            return buffer.getvalue()
        resized = image.resize((side, side), Image.LANCZOS)
        buffer = BytesIO()
        resized.save(buffer, format="PNG")
        return buffer.getvalue()


def _required_px(brief: Dict[str, Any]) -> int:
    """Side length for the re-composition canvas: the brief's minimum, at least 1024."""
    required = _required_size(brief)
    if required is None:
        return 1024
    return max(1024, max(required))


def flat(brief: Dict[str, Any]) -> bool:
    """True when the brief requires a **flat** canvas, not a generated background.

    A brief asks for a flat field when its background is a uniform value or when it asks for a
    clean white matte. Both are properties of a composited plate: the product sits on a flat
    field and the outer ring is that field. A `free` background is the opposite — it wants the
    generated scene kept.

    Until 2026-11-11 this function returned `mode != "uniform"`, which meant a **white-matte**
    brief was handed the generated scene, whose edge grain then failed `white_matte` on border
    std (measured 7.17–9.00 against a 6.0 limit) while its brightness passed (250.8–253.3). Six
    prompt-only briefs scored exactly 90.0 for that reason, which read like a rubric constant
    and was in fact an inverted branch.
    """
    constraints = brief.get("constraints") or {}
    background = constraints.get("background") or {}
    matte = constraints.get("matte") or {}
    mode = str(background.get("mode") or "").lower()
    matte_mode = str(matte.get("mode") or "").lower()
    if mode == "uniform" or matte_mode == "white_matte":
        return True
    return mode.startswith("white") or mode.startswith("solid")


def _required_size(brief: Dict[str, Any]) -> Optional[Tuple[int, int]]:
    """The brief's minimum output size, when it asks for more than the scene gives."""
    dimensions = ((brief.get("constraints") or {}).get("dimensions") or {})
    min_width = int(dimensions.get("min_width") or 0)
    min_height = int(dimensions.get("min_height") or 0)
    if min_width <= 0 and min_height <= 0:
        return None
    return (max(1, min_width), max(1, min_height))


def white_canvas_png(size: int = WHITE_CANVAS_PX, level: int = WHITE_LEVEL) -> bytes:
    """A flat RGB canvas at `level` (255 white, 245 off-white). No model, no grade."""
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    value = int(max(0, min(255, level)))
    Image.new("RGB", (int(size), int(size)), (value, value, value)
              ).save(buffer, format="PNG")
    return buffer.getvalue()


def _measure_white(png: bytes, product_box: Sequence[int],
                   level: int = WHITE_LEVEL) -> Dict[str, Any]:
    """Corners, area fill and height/width fill of the finished flat canvas."""
    from io import BytesIO

    import numpy as np
    from PIL import Image

    from . import scorers  # noqa: PLC0415

    with Image.open(BytesIO(png)) as opened:
        rgb = np.asarray(opened.convert("RGB"), dtype=np.uint8)
    height, width = rgb.shape[:2]
    corners = scorers.sample_corners(rgb, 24)
    fill = scorers.check_subject_fill(rgb, {"min": 0, "max": 100, "distance": 20},
                                      {"value": level, "tolerance": 0, "mode": "uniform"})
    left, top, right, bottom = (int(v) for v in product_box)
    value = int(level)
    return {
        "canvas": [width, height],
        "corners": [list(c) for c in corners],
        "level": value,
        "corners_exactly_255": all(all(int(ch) == WHITE_LEVEL for ch in c) for c in corners),
        "corners_exact": all(all(int(ch) == value for ch in c) for c in corners),
        "subject_fill_pct": fill["fill_pct"],
        "height_fill_pct": round(100.0 * (bottom - top) / height, 2),
        "width_fill_pct": round(100.0 * (right - left) / width, 2),
    }


def _upscale_to(png: bytes, required: Tuple[int, int],
                record: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
    """Upscale to the brief's minimum with the *measured* upscaler.

    ``tools/upscale.py --benchmark`` decides which backend runs; Lanczos is the
    control it must beat and the recorded fallback when the winner is refused.
    The record states the method, its licence and the refusal reason, so a
    resample can never pass as a reconstruction.
    """
    tools_dir = str(REPO_ROOT / "tools")
    if tools_dir not in sys.path:
        sys.path.insert(0, tools_dir)
    import upscale  # noqa: PLC0415

    return upscale.upscale_to_min(png, required, record)


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
                 seed: Optional[int] = None,
                 layout: str = "deterministic") -> None:
        if layout not in ("deterministic", "scene"):
            raise ValueError(f"layout must be 'deterministic' or 'scene', got {layout!r}")
        self.layout = layout
        self.repo_root = Path(repo_root)
        self.method = method
        self.cutout_fn = cutout_fn
        self.out_dir = Path(out_dir) if out_dir is not None else (
            self.repo_root / "renders" / "seller_composite")
        self.seed = seed
        if renderer is not None:
            self.renderer = renderer
            self.renderer_name = ("comfy" if type(renderer).__name__ == "ComfySceneRenderer"
                                  else "injected")
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

        started = time.time()
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
            record["seconds"] = round(time.time() - started, 2)
            self.records.append(record)
            self._journal(record, started)
            raise

        self.out_dir.mkdir(parents=True, exist_ok=True)
        target = self.out_dir / f"{brief.get('id') or 'brief'}.png"
        target.write_bytes(png)
        record["artefact"] = str(target)
        record["bytes"] = len(png)
        record["seconds"] = round(time.time() - started, 2)
        # The sidecar is what makes the artefact auditable later: route, cutout, and the
        # box the product occupies. Written for every route, not only composites.
        try:
            sidecar = target.with_suffix(".json")
            sidecar.write_text(json.dumps({
                "brief_id": record.get("brief_id"),
                "route": record.get("route"),
                "fidelity": record.get("fidelity"),
                "artefact": record.get("artefact"),
                "cutout_path": record.get("cutout_path"),
                "product_box": record.get("product_box"),
                "product_scale": record.get("product_scale"),
                "identity_ssim": record.get("identity"),
                "scene_source": (record.get("scene") or {}).get("source"),
                "upscaled_from": record.get("upscaled_from"),
                "upscaled_to": record.get("upscaled_to"),
                "upscaler": record.get("upscaler"),
            }, indent=2) + "\n", encoding="utf-8")
            record["sidecar"] = str(sidecar)
        except OSError as exc:  # noqa: BLE001
            record["sidecar_error"] = f"{type(exc).__name__}: {exc}"
        self.records.append(record)
        self._journal(record, started)
        return target

    def _journal(self, record: Dict[str, Any], started: float) -> None:
        """One row per render in the lane journal, including the failed attempts.

        It nests the lane row (snapshots, unload/reload, budget) beside the
        upscaler and the white-canvas measurement, so the journal answers the
        whole question for a render rather than half of it.
        """
        try:
            import comfy_lane  # noqa: PLC0415

            scene = record.get("scene") or {}
            comfy_lane.record_render({
                "brief_id": record.get("brief_id"),
                "route": record.get("route"),
                "renderer": record.get("renderer"),
                "scene_source": scene.get("source"),
                "model": scene.get("model"),
                "white_canvas": record.get("white_canvas"),
                "upscaler": record.get("upscale"),
                "upscaled_to": record.get("upscaled_to"),
                "product_box": record.get("product_box"),
                "identity_ssim": record.get("identity"),
                "lane": scene.get("lane"),
                "seconds": record.get("seconds", round(time.time() - started, 2)),
                "artefact": record.get("artefact"),
                "error": record.get("error"),
            })
        except Exception:  # noqa: BLE001 - the journal must never fail a render
            pass

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

    def _cut(self, rgb: Any, method: Optional[str] = None) -> Any:
        import product_cutout as pc  # noqa: PLC0415

        if self.cutout_fn is not None:
            return self.cutout_fn(rgb)
        return pc.cutout(rgb, method or self.method)

    def _layout_stage(self, brief: Dict[str, Any], placed: Dict[str, Any],
                      record: Dict[str, Any]) -> Dict[str, Any]:
        """Run the deterministic stage for the situations a free render cannot satisfy.

        Off by default only when the caller sets `layout="scene"`; the point of the stage is that
        the brief's geometry is not left to a sampling model. A failure here is recorded and the
        scene is kept rather than crashing the pass — but it is never silent.
        """
        from . import deterministic  # noqa: PLC0415

        from .stage_guard import StageRefused, declined  # noqa: PLC0415

        situation = str(brief.get("situation") or "")
        if self.layout != "deterministic" or situation not in deterministic.SITUATIONS:
            return placed
        try:
            # `place_product` records (left, top, right, bottom); every layout helper in
            # `deterministic` works in (x, y, width, height). Convert once, here, and convert
            # back at the end: mixing the two conventions is what made a correct composite
            # score as a geometry mismatch twice on this project.
            left, top, right, bottom = (int(v) for v in placed["product_box"])
            xywh = [left, top, max(1, right - left), max(1, bottom - top)]
            # The render lane gives a square; the brief may ask for 4:5. Extend first, so the
            # product box and the copy band are both in the canvas the brief asked for.
            fitted = declined("fit_aspect", deterministic.fit_aspect, placed["bytes"], xywh,
                              deterministic.brief_aspect(brief))
            box = fitted["product_box"]
            record["aspect_fit"] = dict(fitted["added"])
            if situation == "infographic":
                result = declined("infographic", deterministic.infographic,
                                  fitted["bytes"], box, brief)
                box = result.get("product_box", box)
            else:
                result = declined("panel_warp", deterministic.panel_warp,
                                  fitted["bytes"], box, brief)
        except StageRefused as exc:
            # A typed refusal: the geometry genuinely cannot be laid out. Recorded, and the
            # scene is kept. ValueError/RuntimeError no longer land here by type alone — the
            # `declined()` calls above name the steps allowed to say "cannot".
            record["layout"] = {"kind": "refused", "situation": situation,
                                "reason": exc.reason or str(exc), "declined": True}
            return placed
        except Exception as exc:  # noqa: BLE001 - re-raised loud, never degraded
            from .stage_guard import StageFailed  # noqa: PLC0415

            record["layout"] = {"kind": "error", "situation": situation,
                                "error": f"{type(exc).__name__}: {exc}"}
            raise StageFailed(
                f"layout stage for {situation!r} raised {type(exc).__name__}: {exc} — a bug, not a "
                "refusal") from exc
        updated = dict(placed)
        updated["bytes"] = result["bytes"]
        updated["product_box"] = [box[0], box[1], box[0] + box[2], box[1] + box[3]]
        if result.get("quad"):
            updated["product_quad"] = result["quad"]
        record["layout"] = {"kind": "deterministic", **result["meta"]}
        return updated

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

        # A brief whose own background constraint is a flat uniform value cannot be
        # satisfied by a generated scene: a scene has texture, a horizon and corners
        # that are not that value. The main-image situation is the common case, but the
        # rule is the constraint, not the situation name, so every uniform-background
        # brief takes the flat canvas at the value the brief asks for.
        background_spec = (brief.get("constraints") or {}).get("background") or {}
        flat_level = int(background_spec.get("value", WHITE_LEVEL)) \
            if str(background_spec.get("mode") or "") == "uniform" else None
        white_main = (str(brief.get("situation") or "") == WHITE_MAIN_SITUATION
                      or flat_level is not None)
        cut = None
        if white_main:
            # No ComfyUI, no scene model, no grade: the real pixels on a flat canvas.
            canvas_level = WHITE_LEVEL if flat_level is None else flat_level
            scene = {
                "bytes": white_canvas_png(WHITE_CANVAS_PX, canvas_level),
                "source": "flat_white_canvas",
                "prompt": None,
                "note": (f"flat {canvas_level} canvas; the subject is the only ink, so "
                         "the background check is exact rather than approximate"),
                "image_path": None, "seed": None, "steps": 0, "lane": None,
            }
            chosen_method = self.method
            if chosen_method == "birefnet" and self.cutout_fn is None:
                # BiRefNet needs the ComfyUI lane, and this path deliberately starts
                # no lane. The substitution is recorded, never silent.
                chosen_method = "grabcut"
                record["cutout_refused"] = {
                    "method": "birefnet",
                    "reason": ("birefnet runs inside the ComfyUI lane; the white-main "
                               "path starts no lane. grabcut (14/14 on the same eval, "
                               "5.08 px mean edge) was used instead."),
                }
            cut = self._cut(rgb, method=chosen_method)
            record["method"] = chosen_method
            record["background_path"] = "flat_canvas"
            record["flat_level"] = canvas_level
            in_lane = False
            record["cutout_in_lane"] = False
        else:
            # BiRefNet lives in the media lane; the default renderer runs it inside
            # the same fresh instance it uses for the scene. Everyone else is CPU-only.
            in_lane = self.method == "birefnet" and self.cutout_fn is None
            scene = self._render(brief, "scene",
                                 inside_lane=(lambda: self._cut(rgb)) if in_lane else None)
            if in_lane:
                cut = (scene.get("inside_lane") or {})
            if cut is None:
                cut = self._cut(rgb)
            record["method"] = self.method
            record["cutout_in_lane"] = bool(in_lane)

        reference_coverage = float(reference_check.subject_mask(rgb).mean())
        situation_now = str(brief.get("situation") or "")
        metrics = pc.alpha_metrics(cut.alpha, reference_coverage=reference_coverage)
        if metrics["subject_px"] == 0:
            raise GeneratorUnavailable(
                f"cutout method {self.method!r} found no product in {resolved}")
        record["cutout"] = {**metrics, "seconds": round(cut.seconds, 3)}

        record["scene"] = {
            "source": scene.get("source"), "prompt": scene.get("prompt"),
            "prompt_used": scene_prompt(brief),
            "model": scene.get("model"),
            "image_path": scene.get("image_path"),
            "seed": scene.get("seed"), "steps": scene.get("steps"),
            "width": scene.get("width"), "height": scene.get("height"),
            "lane": scene.get("lane"),
            "lane_stopped": bool(((scene.get("lane") or {}).get("stopped") or {}).get("ok")),
            "note": scene.get("note"),
        }

        placement = brief.get("placement") or {}
        if white_main:
            # 85 % of the frame's long side. A wide pair (two pouches side by side)
            # cannot be 85 % tall without running past the frame width, and cropping
            # a main image is worse than a smaller height fill; the measured values
            # are recorded either way.
            bbox = metrics.get("bbox") or [0, 0, 1, 1]
            product_w = max(1, int(bbox[2]) - int(bbox[0]))
            product_h = max(1, int(bbox[3]) - int(bbox[1]))
            scale = WHITE_FILL
            if product_w > product_h:
                scale = WHITE_FILL * (product_h / float(product_w))
            anchor = (0.5, 0.5)
            record["fill_basis"] = ("longest side 85 % of the canvas "
                                    f"(cutout bbox {product_w}x{product_h})")
        else:
            scale = float(placement.get("scale", 0.72))
            anchor = tuple(placement.get("anchor", (0.5, 0.68)))
            if self.layout == "deterministic" and situation_now == "packaging_mockup":
                # A wide subject at 0.72 of the frame height fills ~90 % of a 4:5 page, which the
                # brief's own fill range rejects. 0.55 lands inside 15-80 % and still fills the
                # panel; the value is recorded below.
                scale = min(scale, 0.55)
                record["fill_cap"] = {"situation": situation_now, "scale": scale,
                                      "why": "a page mockup must leave margin around the panel"}
        cut_png = pc.rgba_png_bytes(cut.rgb, cut.alpha)
        placed = composite.place_product(scene["bytes"], cut_png, scale=scale,
                                         anchor=anchor)
        # Two situations cannot be satisfied by a generated render: an infographic needs machine-
        # readable copy in the margin, and a packaging mockup needs the seller's own artwork on a
        # panel. Both are laid out deterministically *after* the product is placed, so the product
        # region is still the real cutout at a recorded geometry.
        placed = self._layout_stage(brief, placed, record)
        if white_main:
            # A contact shadow is allowed only if it leaves every corner at the level.
            measured = _measure_white(placed["bytes"], placed["product_box"],
                                      canvas_level)
            if not measured["corners_exact"]:
                placed = composite.place_product(scene["bytes"], cut_png, scale=scale,
                                                 anchor=anchor, shadow=False)
                measured = _measure_white(placed["bytes"], placed["product_box"],
                                          canvas_level)
                record["shadow_dropped"] = "a contact shadow reached a corner"
            record["white_canvas"] = measured
            record["shadow"] = bool(placed.get("shadow"))
        quad = placed.get("product_quad")
        if quad:
            import numpy as np  # noqa: PLC0415

            from .composite_check import quad_similarity  # noqa: PLC0415

            cut_rgb, cut_alpha = split_rgba_bytes(cut_png)
            verdict = quad_similarity(np.asarray(_as_rgb(placed["bytes"])), cut_rgb,
                                      cut_alpha, quad)
            identity = {"ssim": verdict.get("similarity"), "verdict": "quad",
                        "detail": verdict.get("detail")}
        else:
            identity = composite.identity_check(placed["bytes"], cut_png,
                                                tuple(placed["product_box"]))
        record["product_box"] = list(placed["product_box"])
        record["product_quad"] = list(quad) if quad else None
        record["product_scale"] = placed["product_scale"]
        record["identity"] = identity.get("ssim")
        record["identity_verdict"] = identity.get("verdict")

        png = placed["bytes"]
        required = _required_size(brief)
        if required is not None:
            png, record = _upscale_to(png, required, record)
            if white_main and record.get("upscaled_to"):
                record["white_canvas"] = _measure_white(
                    png, record["product_box"], canvas_level)

        # Save the cutout that was actually used, beside the artefact it produced.
        # Without it the product-region check cannot tell "the real pouch" from
        # "a pouch that prints the same words", and it must say cannot_verify.
        try:
            self.out_dir.mkdir(parents=True, exist_ok=True)
            cut_target = self.out_dir / f"{brief.get('id') or 'brief'}.cutout.png"
            cut_target.write_bytes(cut_png)
            record["cutout_path"] = str(cut_target)
        except OSError as exc:  # noqa: BLE001 - a missing cutout is recorded, not hidden
            record["cutout_path"] = None
            record["cutout_error"] = f"{type(exc).__name__}: {exc}"
        return png, record

    def _full_generation(self, brief: Dict[str, Any], record: Dict[str, Any]
                         ) -> Tuple[bytes, Dict[str, Any]]:
        """Prompt-only: generate a plate, cut the product out of it, then run the layout stages.

        The first version stopped after the render, which measured "what does the model draw" and
        nothing else: all twelve held-out prompt-only briefs failed the brief's own background, fill
        and text rules. The pipeline now treats the render as *material* — the same way a composite
        treats the seller's photograph — so the rest of the stages apply uniformly:

        1. generate the plate from the brief's description;
        2. cut the product out of that plate;
        3. re-compose it on a canvas the brief's constraints can actually satisfy;
        4. run the deterministic stage for `infographic` / `packaging_mockup`.

        Fidelity stays `tolerant`: nothing here claims the product pixels are the seller's.
        """
        scene = self._render(brief, "full")
        record["scene"] = {
            "source": scene.get("source"), "prompt": scene.get("prompt"),
            "model": scene.get("model"), "image_path": scene.get("image_path"),
            "seed": scene.get("seed"), "steps": scene.get("steps"),
            "width": scene.get("width"), "height": scene.get("height"),
            "lane": scene.get("lane"),
            "lane_stopped": bool(((scene.get("lane") or {}).get("stopped") or {}).get("ok")),
            "note": scene.get("note"),
        }
        png, record = self._generate_cut_and_compose(brief, scene, record)
        return png, record

    def _generate_cut_and_compose(self, brief: Dict[str, Any], scene: Dict[str, Any],
                                  record: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
        """Cut the product out of the generated plate and re-compose it, then lay it out."""
        from io import BytesIO  # noqa: PLC0415

        import numpy as np  # noqa: PLC0415

        from PIL import Image  # noqa: PLC0415

        import product_composite as composite  # noqa: PLC0415
        import product_cutout as pc  # noqa: PLC0415

        from .stage_guard import StageFailed, StageRefused, declined  # noqa: PLC0415

        try:
            plate = Image.open(BytesIO(scene["bytes"])).convert("RGB")
            array = np.asarray(plate)
            cut = declined("cutout", self._cut, array, method="grabcut")
            if int(np.asarray(cut.alpha).sum()) == 0:
                raise StageRefused("the cutout is empty: the generated plate has no separable subject")
            cut_png = declined("rgba_png_bytes", pc.rgba_png_bytes, cut.rgb, cut.alpha)
            # The canvas has to be the brief's size, not the lane's 768: using the raw scene for a
            # free background meant every prompt-only brief failed `dimensions` at 768x768 (12 of 12,
            # 2026-11-10). A free background is the scene resampled up; a flat one (a uniform value
            # or a clean white matte) is the flat canvas at the brief's level, because edge grain
            # from a resampled scene is exactly what `white_matte` measures and fails.
            target_px = _required_px(brief)
            background_spec = (brief.get("constraints") or {}).get("background") or {}
            if flat(brief):
                level = int(background_spec.get("value", WHITE_LEVEL))
                background = white_canvas_png(target_px, level)
                record["background_path"] = "flat_canvas"
                record["flat_level"] = level
            else:
                background = _resize_png(scene["bytes"], target_px)
                record["background_resampled"] = {"from": "scene", "to": target_px}
            placed = declined("place_product", composite.place_product, background, cut_png,
                              scale=0.62, anchor=(0.5, 0.6))
            if str(brief.get("label_mode") or "") == "warp":
                # The body was drawn without lettering; the label is composed and warped on here, so
                # the copy is readable by construction rather than by luck.
                from . import label_warp  # noqa: PLC0415

                label_png = declined("compose_label", label_warp.compose_label, brief)
                warped = declined("warp_label", label_warp.warp_label, placed["bytes"],
                                  placed["product_box"], label_png)
                placed = dict(placed)
                placed["bytes"] = warped["bytes"]
                record["label"] = {"mode": "warp", **warped["meta"]}
            placed = self._layout_stage(brief, placed, record)
            record["cut_from_generation"] = {
                "method": "grabcut",
                "subject_px": int(np.asarray(cut.alpha).sum()),
                "note": ("prompt-only runs generate -> cut -> compose -> layout; the product is "
                         "the model's drawing, not the seller's pixels"),
            }
            record["product_box"] = list(placed["product_box"])
            if placed.get("product_quad"):
                record["product_quad"] = placed["product_quad"]
            self.out_dir.mkdir(parents=True, exist_ok=True)
            cut_target = self.out_dir / f"{brief.get('id') or 'brief'}.cutout.png"
            cut_target.write_bytes(cut_png)
            record["cutout_path"] = str(cut_target)
            return placed["bytes"], record
        except StageRefused as exc:
            # A typed refusal: the plate is kept and the run says why. An empty cutout is a
            # business outcome, not a bug.
            record["cut_from_generation"] = {"method": "refused", "declined": True,
                                             "reason": exc.reason or str(exc)}
            return scene["bytes"], record
        except StageFailed:
            raise
        except Exception as exc:  # noqa: BLE001 - re-raised as loud, never swallowed
            # A programmer error is not a refused stage. Swallowing these made a missing `import
            # numpy` look like "the stage refused" for two scoring rounds, and the score silently
            # fell back to the raw plate (2026-11-10). stage_guard is the one place that decides.
            record["cut_from_generation"] = {"method": "error",
                                             "error": f"{type(exc).__name__}: {exc}"}
            raise StageFailed(
                f"prompt-only compose raised {type(exc).__name__}: {exc} — a bug in the pipeline, "
                "not a refused stage") from exc

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
