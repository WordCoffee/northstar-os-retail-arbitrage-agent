"""Mogra Organics mockup pipeline — the reusable Northstar image/text path.

Given a container preset, a product preset, and an optional base image, this
module produces a finished, high-resolution PNG where the *scene* comes from the
local Qwen image lane and the *text* is composited deterministically.

It is deliberately generic: the same ``build_mockup`` call serves any Northstar
service that needs crisp product images with exact text (Creative Studio, ad
creative, hero banners, comparison graphics, UI annotations). The Mogra pieces
are just presets.

CLI
---
    python -m creative.mogra_mockup --list
    python -m creative.mogra_mockup --product organic_turmeric_powder \
        --container mogra_5lb_clear_handled_pet_jar --generate --out out.png
    python -m creative.mogra_mockup --product organic_black_peppercorns \
        --surface plain_rectangle --source base.png --out tagged.png
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

from . import comfy_client, presets
from .exact_text import LabelSpec, compose_exact_text


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_output_dir() -> Path:
    env = os.environ.get("NORTHSTAR_MOCKUP_OUT")
    if env:
        return Path(env)
    return repo_root() / "generated_images" / "mogra_mockups"


def _stamp() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


# ---------------------------------------------------------------------------
# Spec / surface resolution
# ---------------------------------------------------------------------------

def build_spec(product: Dict[str, Any] | str, *,
               brand: Optional[str] = None,
               tagline: Optional[str] = None,
               product_name: Optional[str] = None,
               descriptor: Optional[str] = None,
               net_weight: Optional[str] = None,
               ingredients: str = "",
               rear_placeholders: Optional[List[str]] = None,
               extra_lines: Optional[List[str]] = None) -> LabelSpec:
    """Build a ``LabelSpec`` from a product preset key/dict plus overrides."""
    if isinstance(product, str):
        p = presets.get_product(product)
    else:
        p = dict(product or {})
    return LabelSpec(
        brand=brand if brand is not None else p.get("brand", presets.MOGRA_BRAND["name"]),
        tagline=tagline if tagline is not None else p.get("tagline", presets.MOGRA_BRAND["tagline"]),
        product_name=product_name if product_name is not None else p.get("product_name", ""),
        descriptor=descriptor if descriptor is not None else p.get("descriptor", ""),
        net_weight=net_weight if net_weight is not None else p.get("net_weight", ""),
        ingredients=ingredients or "",
        rear_placeholders=list(rear_placeholders or []),
        extra_lines=list(extra_lines or []),
    )


def resolve_surface(*, container: Optional[str] = None,
                    surface_key: Optional[str] = None,
                    quad: Optional[List[List[float]]] = None,
                    curvature: Optional[float] = None,
                    style_key: Optional[str] = None) -> Dict[str, Any]:
    """Merge a container/surface preset with explicit overrides."""
    base: Dict[str, Any]
    if container:
        c = presets.get_container(container)
        base = {"quad_norm": list(c["quad_norm"]),
                "curvature": float(c.get("curvature", 0.0)),
                "style": c.get("default_style", "mogra_label_panel"),
                "label": c.get("label", container)}
    else:
        s = presets.get_surface(surface_key or "front_label_panel")
        base = {"quad_norm": list(s["quad_norm"]),
                "curvature": float(s.get("curvature", 0.0)),
                "style": s.get("style", "mogra_label_panel"),
                "label": s.get("label", surface_key)}
    if quad:
        base["quad_norm"] = [[float(p[0]), float(p[1])] for p in quad]
    if curvature is not None:
        base["curvature"] = float(curvature)
    base["style_key"] = style_key or base["style"]
    base["style"] = presets.get_style(base["style_key"])
    return base


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def build_mockup(*, product: Dict[str, Any] | str,
                 container: Optional[str] = None,
                 surface_key: Optional[str] = None,
                 source_image: Optional[str | os.PathLike] = None,
                 generate: bool = False,
                 scene_prompt: Optional[str] = None,
                 quad: Optional[List[List[float]]] = None,
                 curvature: Optional[float] = None,
                 style_key: Optional[str] = None,
                 width: int = 1024, height: int = 1024, steps: int = 20,
                 seed: Optional[int] = None,
                 ingredients: str = "",
                 rear_placeholders: Optional[List[str]] = None,
                 extra_lines: Optional[List[str]] = None,
                 enforce_brand: bool = True,
                 out_path: Optional[str | os.PathLike] = None,
                 write_sidecar: bool = True,
                 client: Optional[comfy_client.ComfyClient] = None,
                 **overrides: Any) -> Dict[str, Any]:
    """Full pipeline: (optionally) generate scene -> composite exact text -> PNG.

    Returns a result dict with ``output`` (PNG path), ``params`` (reusable),
    ``lane`` and the resolved spec.
    """
    spec = build_spec(product, ingredients=ingredients,
                      rear_placeholders=rear_placeholders,
                      extra_lines=extra_lines, **overrides)
    surface = resolve_surface(container=container, surface_key=surface_key,
                              quad=quad, curvature=curvature, style_key=style_key)

    out_dir = default_output_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    pkey = product if isinstance(product, str) else "custom"
    out = Path(out_path) if out_path else out_dir / f"mogra_{pkey}_{_stamp()}.png"

    lane = "composited_only"
    source_used: Optional[str] = None

    if source_image is not None:
        with Image.open(source_image) as im:
            base = im.convert("RGBA")
        source_used = str(source_image)
    elif generate:
        if not scene_prompt:
            cdict = presets.get_container(container) if container else None
            pdict = presets.get_product(product) if isinstance(product, str) else product
            scene_prompt = comfy_client.build_scene_prompt(
                container=cdict, product=pdict)
        gen_dir = out_dir / "scenes"
        gen_dir.mkdir(parents=True, exist_ok=True)
        gen_path = gen_dir / f"scene_{pkey}_{_stamp()}.png"
        gen = comfy_client.generate_scene(scene_prompt, gen_path, width=width,
                                          height=height, steps=steps, seed=seed,
                                          client=client)
        lane = gen["lane"]
        source_used = gen["output"]
        with Image.open(source_used) as im:
            base = im.convert("RGBA")
    else:
        raise ValueError("provide source_image=... or generate=True")

    composited, params = compose_exact_text(base, spec, surface, surface["style"],
                                            enforce_brand=enforce_brand,
                                            return_params=True)
    out.parent.mkdir(parents=True, exist_ok=True)
    composited.convert("RGB").save(out, format="PNG")

    result: Dict[str, Any] = {
        "output": str(out),
        "lane": lane,
        "source": source_used,
        "params": params,
        "spec": spec.__dict__,
        "surface_label": surface.get("label"),
        "style_key": surface.get("style_key"),
    }
    if write_sidecar:
        sidecar = out.with_suffix(".json")
        sidecar.write_text(json.dumps(result, indent=2), encoding="utf-8")
        result["sidecar"] = str(sidecar)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_quad(text: str) -> List[List[float]]:
    pts: List[List[float]] = []
    for chunk in text.replace(";", " ").split():
        x, _, y = chunk.partition(",")
        pts.append([float(x), float(y)])
    if len(pts) != 4:
        raise argparse.ArgumentTypeError("quad needs exactly 4 x,y pairs")
    return pts


def _print_catalog() -> None:
    print("Containers:")
    for k, v in presets.CONTAINER_PRESETS.items():
        print(f"  {k:38s} {v['label']}")
    print("Products:")
    for k, v in presets.PRODUCT_PRESETS.items():
        print(f"  {k:38s} {v['product_name']} / {v['descriptor']} / {v['net_weight']}")
    print("Surfaces:")
    for k, v in presets.SURFACE_PRESETS.items():
        print(f"  {k:38s} {v['label']}")
    print("Styles:")
    for k, v in presets.STYLE_PRESETS.items():
        print(f"  {k:38s} {v['label']}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Mogra Organics exact-text mockup builder")
    ap.add_argument("--list", action="store_true", help="list presets and exit")
    ap.add_argument("--product", help="product preset key")
    ap.add_argument("--container", help="container preset key")
    ap.add_argument("--surface", default=None, help="surface preset key (if no container)")
    ap.add_argument("--style", default=None, help="style preset key override")
    ap.add_argument("--source", help="existing base image (skips generation)")
    ap.add_argument("--generate", action="store_true", help="generate the base scene locally")
    ap.add_argument("--prompt", help="override the scene prompt")
    ap.add_argument("--quad", help="4 x,y pairs e.g. '0.3,0.2 0.7,0.2 0.7,0.6 0.3,0.6'")
    ap.add_argument("--curvature", type=float, default=None)
    ap.add_argument("--out", help="output PNG path")
    ap.add_argument("--brand", default=None)
    ap.add_argument("--tagline", default=None)
    ap.add_argument("--product-name", default=None)
    ap.add_argument("--descriptor", default=None)
    ap.add_argument("--net-weight", default=None)
    ap.add_argument("--ingredients", default="")
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1024)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--json", action="store_true", help="print full result JSON")
    args = ap.parse_args(argv)

    if args.list:
        _print_catalog()
        return 0
    if not args.product:
        ap.error("--product is required (or use --list)")

    quad = _parse_quad(args.quad) if args.quad else None
    try:
        result = build_mockup(
            product=args.product, container=args.container, surface_key=args.surface,
            source_image=args.source, generate=args.generate, scene_prompt=args.prompt,
            quad=quad, curvature=args.curvature, style_key=args.style,
            width=args.width, height=args.height, steps=args.steps, seed=args.seed,
            ingredients=args.ingredients, out_path=args.out,
            brand=args.brand, tagline=args.tagline, product_name=args.product_name,
            descriptor=args.descriptor, net_weight=args.net_weight,
        )
    except Exception as exc:  # honest, single-line failure
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"OK  lane={result['lane']}  ->  {result['output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
