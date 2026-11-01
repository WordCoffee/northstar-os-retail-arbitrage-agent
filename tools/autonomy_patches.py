#!/usr/bin/env python3
"""Deterministic apply scripts for the authorized continuous-loop queue.

Each patch is small, offline, and refuses to run when its expected pre-fix text
is not present. The loop runs one patch only after its precheck has failed, then
runs the task's acceptance test and commits exactly the task paths.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "Northstar_backend"


def _replace(rel: str, old: str, new: str) -> None:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{rel}: expected exactly one pre-fix match, found {text.count(old)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _write_test(name: str, body: str) -> None:
    path = TESTS / name
    path.write_text(body.strip() + "\n", encoding="utf-8")


def hitl_pathlike() -> None:
    _replace(
        "Northstar_backend/agent_kernel/hitl_counts.py",
        "def hitl_counts(root):\n    \"\"\"Count hitl statuses in state directory.\"\"\"\n    if not root.exists():",
        "def hitl_counts(root):\n    \"\"\"Count hitl statuses in state directory.\"\"\"\n    root = Path(root)\n    if not root.exists():",
    )
    _write_test("test_autonomy_hitl_pathlike.py", """
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_kernel.hitl_counts import hitl_counts


def test_hitl_counts_accepts_a_string_root(tmp_path):
    root = tmp_path / "root"
    hitl = root / "state" / "hitl"
    hitl.mkdir(parents=True)
    (hitl / "hitl_20260101T000000_deadbeef.json").write_text(
        json.dumps({"status": "pending"}), encoding="utf-8")
    (hitl / "hitl_20260101T000001_deadbeef.json").write_text(
        json.dumps({"status": "approved"}), encoding="utf-8")
    assert hitl_counts(str(root)) == {
        "pending": 1, "approved": 1, "denied": 0, "total": 2,
    }
""")


def format_quad_guard() -> None:
    _replace(
        "Northstar_backend/format_compositors.py",
        "from io import BytesIO\nfrom typing import Any, Dict, Optional, Sequence, Tuple",
        "import math\nfrom io import BytesIO\nfrom typing import Any, Dict, Optional, Sequence, Tuple",
    )
    _replace(
        "Northstar_backend/format_compositors.py",
        "def _as_image(value: Any) -> Image.Image:\n    if isinstance(value, Image.Image):",
        "def _quad_points(quad: Quad) -> list:\n    pts = [(float(p[0]), float(p[1])) for p in (quad or [])]\n    if len(pts) != 4:\n        raise ValueError(\"quad needs exactly 4 corner points (TL, TR, BR, BL)\")\n    if not all(math.isfinite(x) and math.isfinite(y) for x, y in pts):\n        raise ValueError(\"quad corners must be finite numbers\")\n    return pts\n\n\ndef _as_image(value: Any) -> Image.Image:\n    if isinstance(value, Image.Image):",
    )
    _replace(
        "Northstar_backend/format_compositors.py",
        '    """Perspective-warp the label onto four measured corners of a box face."""\n    base = _as_image(plate)',
        '    """Perspective-warp the label onto four measured corners of a box face."""\n    quad = _quad_points(quad)\n    base = _as_image(plate)',
    )
    _replace(
        "Northstar_backend/format_compositors.py",
        '    """Cylindrical resample: vertical strips compress toward the silhouette."""\n    base = _as_image(plate)',
        '    """Cylindrical resample: vertical strips compress toward the silhouette."""\n    quad = _quad_points(quad)\n    base = _as_image(plate)',
    )
    _replace(
        "Northstar_backend/format_compositors.py",
        '    """Warp the label onto the measured tube quad (which carries the taper).\n\n    A tube\'s printable area is a trapezoid: the body can be wider at the top\n    than the base (or the reverse, depending on camera height). Warping to the\n    four measured corners follows that shape; the old fixed taper inset only\n    narrowed the top and could not represent a negative taper at all.\n    """\n    base = _as_image(plate)',
        '    """Warp the label onto the measured tube quad (which carries the taper).\n\n    A tube\'s printable area is a trapezoid: the body can be wider at the top\n    than the base (or the reverse, depending on camera height). Warping to the\n    four measured corners follows that shape; the old fixed taper inset only\n    narrowed the top and could not represent a negative taper at all.\n    """\n    quad = _quad_points(quad)\n    base = _as_image(plate)',
    )
    _write_test("test_autonomy_format_quad_guard.py", """
from io import BytesIO
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import format_compositors as fc


def _png(img):
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_bottle_and_tube_reject_a_non_quad():
    plate = _png(Image.new("RGB", (400, 500), (205, 180, 150)))
    label = _png(Image.new("RGB", (240, 300), (250, 248, 240)))
    bad = [[80, 100], [320, 100], [320, 400]]
    with pytest.raises(ValueError):
        fc.bottle_composite(plate, label, bad)
    with pytest.raises(ValueError):
        fc.tube_composite(plate, label, bad)
""")


def geometry_bottom_guard() -> None:
    _replace(
        "Northstar_backend/geometry_profiles.py",
        "    if label_height > usable_h:\n        raise ValueError(\n            f\"label_height {label_height}mm exceeds usable height {usable_h:.1f}mm \"\n            f\"(height {height} - cap {cap_height} - seam {seam_clearance})\")",
        "    if label_height > usable_h:\n        raise ValueError(\n            f\"label_height {label_height}mm exceeds usable height {usable_h:.1f}mm \"\n            f\"(height {height} - cap {cap_height} - seam {seam_clearance})\")\n    if label_top_offset + label_height > height - seam_clearance:\n        raise ValueError(\n            \"label extends into the bottom seam clearance \"\n            f\"({label_top_offset} + {label_height} > {height - seam_clearance})\")",
    )
    _write_test("test_autonomy_geometry_bottom_guard.py", """
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geometry_profiles import bottle


def test_label_cannot_run_past_the_bottom_seam():
    with pytest.raises(ValueError):
        bottle(diameter=60, height=200, label_height=10, label_top_offset=190)
""")


def print_quad_guard() -> None:
    _replace(
        "Northstar_backend/print_prep.py",
        "import hashlib\nimport json",
        "import hashlib\nimport json\nimport math",
    )
    _replace(
        "Northstar_backend/print_prep.py",
        "    if len(quad) != 4:\n        raise ValueError(\"a dieline quad needs exactly four corners\")\n    tl, tr, br, bl = quad\n    width = (_dist(tl, tr) + _dist(bl, br)) / 2.0\n    height = (_dist(tl, bl) + _dist(tr, br)) / 2.0\n    return {\"width\": round(width, 3), \"height\": round(height, 3)}",
        "    if len(quad) != 4:\n        raise ValueError(\"a dieline quad needs exactly four corners\")\n    tl, tr, br, bl = quad\n    if not all(math.isfinite(float(c)) for point in quad for c in point):\n        raise ValueError(\"dieline quad corners must be finite numbers\")\n    width = (_dist(tl, tr) + _dist(bl, br)) / 2.0\n    height = (_dist(tl, bl) + _dist(tr, br)) / 2.0\n    if width <= 0 or height <= 0:\n        raise ValueError(\"dieline quad has zero or negative face dimensions\")\n    return {\"width\": round(width, 3), \"height\": round(height, 3)}",
    )
    _write_test("test_autonomy_print_quad_guard.py", """
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from print_prep import face_pixels


def test_degenerate_quad_is_refused():
    with pytest.raises(ValueError):
        face_pixels([[1, 1], [1, 1], [1, 1], [1, 1]])
""")


def surface_wrap_guard() -> None:
    _replace(
        "Northstar_backend/surface_measure.py",
        '    if fmt not in ("pouch", "box", "bottle", "tube"):\n        raise KeyError(f"unknown packaging format {kind!r}; known: pouch, box, bottle, tube")\n\n    if fmt == "pouch":',
        '    if fmt not in ("pouch", "box", "bottle", "tube"):\n        raise KeyError(f"unknown packaging format {kind!r}; known: pouch, box, bottle, tube")\n    if not 0.0 < float(wrap_fraction) <= 1.0:\n        raise ValueError("wrap_fraction must be in (0, 1]")\n\n    if fmt == "pouch":',
    )
    _write_test("test_autonomy_surface_wrap_guard.py", """
from pathlib import Path
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import surface_measure as sm


def test_wrap_fraction_outside_the_visible_arc_is_refused():
    with pytest.raises(ValueError):
        sm.measure_surface(Image.new("RGB", (128, 128), (230, 230, 230)),
                           "bottle", wrap_fraction=0)
    with pytest.raises(ValueError):
        sm.measure_surface(Image.new("RGB", (128, 128), (230, 230, 230)),
                           "bottle", wrap_fraction=1.5)
""")


def panels_format_guard() -> None:
    _replace(
        "Northstar_backend/specialists/panels.py",
        "    warnings: List[str] = []\n    dims = spec.get(\"dims\") or {}\n    # The 1.2-1.9 ratio is a pouch heuristic.",
        "    warnings: List[str] = []\n    fmt = str(spec.get(\"format\") or \"pouch\").strip().lower()\n    unknown_format = fmt not in (\"pouch\", \"box\", \"bottle\", \"tube\")\n    if unknown_format:\n        warnings.append(f\"unknown package format {fmt!r}; expected pouch, box, bottle or tube\")\n    dims = spec.get(\"dims\") or {}\n    # The 1.2-1.9 ratio is a pouch heuristic.",
    )
    _replace(
        "Northstar_backend/specialists/panels.py",
        "    if str(spec.get(\"format\") or \"pouch\").strip().lower() == \"pouch\":\n        if dims.get(\"width_mm\")",
        "    if fmt == \"pouch\":\n        if dims.get(\"width_mm\")",
    )
    _replace(
        "Northstar_backend/specialists/panels.py",
        "    return {\"ready_for_print\": not missing, \"missing\": missing, \"warnings\": warnings}",
        "    return {\"ready_for_print\": not missing and not unknown_format,\n            \"missing\": missing, \"warnings\": warnings}",
    )
    _write_test("test_autonomy_panels_format_guard.py", """
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from specialists.panels import validate_panels


def test_an_unknown_package_format_is_not_print_ready():
    out = validate_panels({
        "title": "Test product", "weight": "NET WT 1 OZ",
        "ingredients": ["one ingredient"], "company": "Test Co",
        "address": "1 Test Way", "country_of_origin": "USA",
        "format": "sachet",
    })
    assert out["ready_for_print"] is False
    assert any("format" in w for w in out["warnings"])
""")


def dead_code_cleanup() -> None:
    _replace(
        "Northstar_backend/package_art.py",
        "from typing import Any, Dict, Optional, Sequence, Tuple",
        "from typing import Any, Dict, Optional",
    )
    _replace("Northstar_backend/package_pipeline.py", "import uuid\n", "")
    _write_test("test_autonomy_dead_code.py", """
import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[1]


def _imported(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[-1] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(a.name for a in node.names)
    return names


def test_new_creative_modules_do_not_import_unused_names():
    assert "Sequence" not in _imported(ROOT / "Northstar_backend" / "package_art.py")
    assert "Tuple" not in _imported(ROOT / "Northstar_backend" / "package_art.py")
    assert "uuid" not in _imported(ROOT / "Northstar_backend" / "package_pipeline.py")
""")


def docs_autonomy() -> None:
    path = ROOT / "docs" / "CONTINUOUS_LOOP.md"
    text = path.read_text(encoding="utf-8")
    marker = "## Autonomy readiness and long campaigns"
    if marker in text:
        raise SystemExit("docs already contain the autonomy section")
    text += """

## Autonomy readiness and long campaigns

Run the full GO/NO-GO preflight before a campaign:

```powershell
python scripts/continuous_loop.py --ready
```

The gate creates a checkpoint under `state/checkpoints/`, records the working
tree and uncommitted patch, copies the DBs/configs/model manifest, proves a
sandbox restore byte-for-byte, checks the policy envelope against `HEAD`, and
resolves the installed model lane. Any failure prints `NO-GO` with a
remediation; a campaign refuses to start.

A long campaign enforces both bounds and stops on consecutive failures:

```powershell
python scripts/continuous_loop.py --max-tasks 8 --deadline-minutes 180 --max-consecutive-failures 2
python scripts/continuous_loop.py --status
Get-Content reports/autonomy_log_YYYYMMDD.log -Tail 40 -Wait
python scripts/continuous_loop.py --stop
python scripts/continuous_loop.py --resume <task-id>
```

The campaign heartbeat is `state/continuous_loop_campaign.json`; the final
manifest is `state/campaigns/<run-id>.json` and a report copy under `reports/`.
The live log is scrubbed and one line per phase transition. There is no service
or scheduler: the campaign runs in the foreground until termination.
"""
    path.write_text(text, encoding="utf-8")
    _write_test("test_autonomy_docs.py", """
from pathlib import Path


def test_autonomy_docs_cover_the_long_campaign_controls():
    text = (Path(__file__).resolve().parents[1] / "docs" / "CONTINUOUS_LOOP.md").read_text(
        encoding="utf-8")
    for token in ("--ready", "--max-consecutive-failures", "--status",
                  "autonomy_log_YYYYMMDD.log", "no service"):
        assert token in text
""")


PATCHES = {
    "hitl-pathlike": hitl_pathlike,
    "format-quad-guard": format_quad_guard,
    "geometry-bottom-guard": geometry_bottom_guard,
    "print-quad-guard": print_quad_guard,
    "surface-wrap-guard": surface_wrap_guard,
    "panels-format-guard": panels_format_guard,
    "dead-code-cleanup": dead_code_cleanup,
    "docs-autonomy": docs_autonomy,
}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1 or argv[0] not in PATCHES:
        print("usage: python tools/autonomy_patches.py " + "|".join(sorted(PATCHES)))
        return 2
    PATCHES[argv[0]]()
    print(f"applied {argv[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
