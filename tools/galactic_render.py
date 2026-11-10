"""Render the Galactic backdrop shader headlessly and write a PNG.

Why this exists: the shader is the visual product, and a fragment shader that
compiles is not a fragment shader that looks right. The browser is not
addressable from the agent, so this uses the same GLSL, compiled by the real
driver through moderngl (ComfyUI's venv), rendered into an offscreen frame and
saved. The operator can look at the PNG; so can the agent.

    C:\\Users\\T2Hol\\ComfyUI\\venv\\Scripts\\python.exe tools/galactic_render.py

It reads northstar-os-ui/src/shell/galacticShader.js so there is exactly one
copy of the shader. Nothing here is a second implementation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHADER = ROOT / "northstar-os-ui" / "src" / "shell" / "galacticShader.js"


def extract(name: str) -> str:
    src = SHADER.read_text(encoding="utf-8")
    match = re.search(rf"export const {name} = `(.*?)`\s*(?:\n|$)", src, re.S)
    if not match:
        raise SystemExit(f"could not find {name} in {SHADER}")
    return match.group(1)


def to_desktop_glsl(body: str, stage: str = "fragment") -> str:
    """The shipped shader is GLSL ES 1.00. This is the thinnest shim that lets
    the desktop driver compile the *same text* instead of a rewrite."""
    body = re.sub(r"^\s*precision\s+\w+\s+float;\s*$", "", body, flags=re.M)
    varying = "out" if stage == "vertex" else "in"
    head = (
        "#version 330 core\n"
        f"#define varying {varying}\n"
        "#define attribute in\n"
    )
    if stage == "fragment":
        head += "out vec4 fragColor;\n#define gl_FragColor fragColor\n"
    return head + body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=int, default=1280)
    ap.add_argument("--height", type=int, default=720)
    ap.add_argument("--time", type=float, default=18.0)
    ap.add_argument("--quality", type=float, default=1.0)
    ap.add_argument("--tint", default="1.0,0.95,0.86")
    ap.add_argument("--debug", default="", choices=["", "alpha", "shadow"])
    ap.add_argument("--expo", type=float, default=1.0)
    ap.add_argument("--temp", type=float, default=1.0)
    ap.add_argument("--incl", type=float, default=5.6)
    ap.add_argument("--dist", type=float, default=16.0)
    ap.add_argument("--gal", type=float, default=1.0)
    ap.add_argument("--grade", default="1.0,1.0,1.0")
    ap.add_argument("--out", default="reports/galactic_shader_preview.png")
    args = ap.parse_args()

    import moderngl
    import numpy as np
    from PIL import Image

    tint = [float(v) for v in args.tint.split(",")]
    if len(tint) != 3:
        raise SystemExit("--tint needs three comma-separated floats")
    grade = [float(v) for v in args.grade.split(",")]
    if len(grade) != 3:
        raise SystemExit("--grade needs three comma-separated floats")

    ctx = moderngl.create_standalone_context(require=330)
    vert = to_desktop_glsl(extract("VERT"), stage="vertex")
    frag = to_desktop_glsl(extract("FRAG"), stage="fragment")

    # Debug channels are injected into the compiled text, never into the shader
    # that ships to the browser.
    if args.debug == "alpha":
        frag = frag.replace("  return col;\n}", "  return vec3(diskA);\n}", 1)
        frag = frag.replace("  // ── grade", "  gl_FragColor = vec4(col, 1.0); return;\n  // ── grade", 1)
    elif args.debug == "shadow":
        frag = frag.replace("  return col;\n}", "  return vec3(b > 2.598 ? 0.0 : 1.0);\n}", 1)
        frag = frag.replace("  // ── grade", "  gl_FragColor = vec4(col, 1.0); return;\n  // ── grade", 1)
    prog = ctx.program(vertex_shader=vert, fragment_shader=frag)

    # Full-screen triangle: three vertices, no index buffer, no geometry waste.
    verts = np.array([-1, -1, 3, -1, -1, 3], dtype="f4")
    vbo = ctx.buffer(verts.tobytes())
    vao = ctx.vertex_array(prog, [(vbo, "2f", "a_pos")])

    tex = ctx.texture((args.width, args.height), 4, dtype="f1")
    fbo = ctx.framebuffer(color_attachments=[tex])
    fbo.use()
    ctx.viewport = (0, 0, args.width, args.height)
    ctx.clear(0.0, 0.0, 0.0, 1.0)

    prog["u_res"].value = (float(args.width), float(args.height))
    prog["u_time"].value = args.time
    prog["u_quality"].value = args.quality
    prog["u_tint"].value = tuple(tint)
    for name, val in (
        ("u_expo", args.expo),
        ("u_temp", args.temp),
        ("u_incl", args.incl),
        ("u_dist", args.dist),
        ("u_gal", args.gal),
    ):
        if name in prog:
            prog[name].value = float(val)
    if "u_grade" in prog:
        prog["u_grade"].value = tuple(grade)

    vao.render(moderngl.TRIANGLES)

    raw = fbo.read(components=4, dtype="f1")
    img = Image.frombytes("RGBA", (args.width, args.height), raw).transpose(
        Image.FLIP_TOP_BOTTOM
    )

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(out, "PNG", optimize=True)

    arr = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    stats = {
        "out": str(out),
        "pixels": f"{args.width}x{args.height}",
        "mean_luma": round(float(arr.mean()), 4),
        "max_luma": round(float(arr.max()), 4),
        "black_fraction": round(float((arr.max(axis=2) < 0.02).mean()), 4),
        "clipped_fraction": round(float((arr.max(axis=2) > 0.99).mean()), 5),
        "bytes": out.stat().st_size,
    }
    print(json.dumps(stats, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
