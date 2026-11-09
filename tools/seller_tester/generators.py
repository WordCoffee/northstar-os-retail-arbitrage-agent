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

        situation = str(brief.get("situation") or "")
        if self.layout != "deterministic" or situation not in deterministic.SITUATIONS:
            return placed
        try:
            # The render lane gives a square; the brief may ask for 4:5. Extend first, so the
            # product box and the copy band are both in the canvas the brief asked for.
            fitted = deterministic.fit_aspect(placed["bytes"], placed["product_box"],
                                              deterministic.brief_aspect(brief))
            box = fitted["product_box"]
            record["aspect_fit"] = dict(fitted["added"])
            if situation == "infographic":
                result = deterministic.infographic(fitted["bytes"], box, brief)
            else:
                result = deterministic.panel_warp(fitted["bytes"], box, brief)
        except Exception as exc:  # noqa: BLE001 - a refused layout is a named record entry
            record["layout"] = {"kind": "refused", "situation": situation,
                                "reason": f"{type(exc).__name__}: {exc}"}
            return placed
        updated = dict(placed)
        updated["bytes"] = result["bytes"]
        updated["product_box"] = list(box)
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
