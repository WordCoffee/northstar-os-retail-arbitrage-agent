"""3D handoff: audit a mesh before any Blender bake, and refuse what cannot print.

The brief's 3D pipeline (generate -> repair -> unwrap -> bake -> GLTF/USDZ) has one
deterministic gate that does not depend on which generator produced the mesh: does
this file have geometry, faces, UVs, a sane triangle budget and a real physical
scale? Everything downstream is expensive and, on a mesh without UVs or with a
degenerate bounding box, guaranteed wasted.

So this module is the contract the generator must satisfy, plus a Blender probe
that says whether the bake step can run at all on this machine. It never guesses:
an OBJ carries no units, so the caller must declare them and the audit reports
"unspecified" rather than assuming millimetres.
"""
from __future__ import annotations

import math
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: Above this a packaging mockup costs more than it is worth at bake time.
MAX_TRIS = 250_000
#: A packaging mesh smaller than this in any axis is a unit mistake, not a product.
MIN_BBOX_MM = 1.0


def _violation(code: str, detail: str, **extra: Any) -> Dict[str, Any]:
    return {"code": code, "detail": detail, **extra}


def inspect_obj(text: str) -> Dict[str, Any]:
    """Counts, UV usage, manifold edges and bbox from OBJ text."""
    verts: List[Tuple[float, float, float]] = []
    faces = 0
    faces_with_uv = 0
    edge_use: Dict[Tuple[int, int], int] = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("v "):
            parts = line.split()
            if len(parts) < 4:
                raise ValueError("obj_vertex_malformed: a vertex needs three coordinates")
            try:
                verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
            except ValueError as exc:
                raise ValueError(f"obj_vertex_not_numeric: {line[:60]}") from exc
        elif line.startswith("f "):
            faces += 1
            refs = line.split()[1:]
            idx: List[int] = []
            has_uv = False
            for ref in refs:
                bits = ref.split("/")
                if len(bits) > 1 and bits[1]:
                    has_uv = True
                try:
                    idx.append(int(bits[0]))
                except ValueError as exc:
                    raise ValueError(f"obj_face_not_numeric: {line[:60]}") from exc
            if has_uv:
                faces_with_uv += 1
            for i in range(len(idx)):
                a, b = idx[i], idx[(i + 1) % len(idx)]
                if a == b:
                    continue
                key = (min(a, b), max(a, b))
                edge_use[key] = edge_use.get(key, 0) + 1

    if not verts:
        return {"verts": 0, "faces": faces, "uv_faces": faces_with_uv, "tris": 0,
                "non_manifold_edges": 0, "bbox_mm": None, "units": "unspecified"}
    xs = [v[0] for v in verts]
    ys = [v[1] for v in verts]
    zs = [v[2] for v in verts]
    bbox = {"x": round(max(xs) - min(xs), 4), "y": round(max(ys) - min(ys), 4),
            "z": round(max(zs) - min(zs), 4)}
    non_manifold = sum(1 for count in edge_use.values() if count > 2)
    open_edges = sum(1 for count in edge_use.values() if count == 1)
    return {"verts": len(verts), "faces": faces, "uv_faces": faces_with_uv,
            "tris": faces * 2, "non_manifold_edges": non_manifold,
            "open_edges": open_edges, "bbox_mm": bbox, "units": "unspecified"}


def inspect_ply_header(data: bytes) -> Dict[str, Any]:
    """Element counts and format from a PLY header (ascii or binary)."""
    head = data[:4096]
    end = head.find(b"end_header")
    if not head.startswith(b"ply") or end < 0:
        raise ValueError("ply_header_missing: not a PLY file")
    text = head[:end].decode("ascii", "ignore")
    info: Dict[str, Any] = {"format": "", "element": {}, "faces": 0, "verts": 0,
                            "units": "unspecified", "bbox_mm": None}
    for line in text.splitlines():
        bits = line.split()
        if len(bits) >= 3 and bits[0] == "format":
            info["format"] = bits[1]
        elif len(bits) == 3 and bits[0] == "element":
            which, count = bits[1], int(bits[2])
            info["element"][which] = count
            if which in ("vertex", "vertices"):
                info["verts"] = count
            elif which in ("face", "faces"):
                info["faces"] = count
    info["tris"] = info["faces"] * 2
    return info


def audit(mesh: Dict[str, Any], *, units: str = "unspecified",
          max_tris: int = MAX_TRIS, require_uv: bool = True) -> Dict[str, Any]:
    """Every reason a mesh cannot go to bake, as data."""
    problems: List[Dict[str, Any]] = []
    verts = int(mesh.get("verts") or 0)
    faces = int(mesh.get("faces") or 0)
    if verts == 0:
        problems.append(_violation("no_geometry", "the file carries no vertices"))
    if faces == 0:
        problems.append(_violation("no_faces", "the file carries no faces"))
    if require_uv and faces and int(mesh.get("uv_faces") or 0) == 0:
        problems.append(_violation(
            "missing_uv", "no face references a texture coordinate; bake is impossible"))
    if int(mesh.get("non_manifold_edges") or 0) > 0:
        problems.append(_violation(
            "non_manifold_edges",
            f"{mesh['non_manifold_edges']} edges are shared by more than two faces"))
    if int(mesh.get("tris") or 0) > max_tris:
        problems.append(_violation(
            "polycount_over_budget",
            f"{mesh['tris']} triangles exceeds the {max_tris} budget"))
    bbox = mesh.get("bbox_mm")
    if bbox:
        # A planar mesh is legitimate here (dielines and decals are flat); the
        # defect this catches is a unit mistake, where the whole object is tiny.
        largest = max(float(bbox.get(k) or 0) for k in ("x", "y", "z"))
        if not math.isfinite(largest) or largest <= MIN_BBOX_MM:
            problems.append(_violation(
                "bbox_degenerate",
                f"largest axis is {largest}mm; check the mesh and its units"))
    elif verts:
        problems.append(_violation(
            "bbox_unknown", "vertices exist but no bounding box could be computed"))
    if units == "unspecified":
        problems.append(_violation(
            "units_unspecified",
            "OBJ/PLY carry no units; declare millimetres before tooling or printing"))
    return {"ok": not problems, "violations": problems}


def blender_probe(executable: Optional[str] = None) -> Dict[str, Any]:
    """Is a headless Blender available for decimate/unwrap/bake?"""
    candidates = [executable] if executable else [
        shutil.which("blender"),
        r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.1\blender.exe",
        r"C:\Program Files\Blender Foundation\Blender 4.0\blender.exe",
    ]
    for path in candidates:
        if path and Path(path).is_file():
            return {"available": True, "path": str(path),
                    "note": "run bpy scripts with -b --python; never the GUI"}
    try:
        import bpy  # noqa: F401
        return {"available": True, "path": "bpy (module)", "note": "bpy importable"}
    except Exception:  # noqa: BLE001 - absence is the answer
        pass
    return {"available": False,
            "reason": ("no blender executable on PATH or in Program Files, and bpy is "
                       "not importable; install Blender 4.x to enable the bake lane")}


def bake_plan(mesh: Dict[str, Any], *, units: str):
    """Refuse the bake before it costs anything when a precondition is missing."""
    report = audit(mesh, units=units)
    if not report["ok"]:
        raise ValueError("bake_refused: " + ", ".join(v["code"] for v in report["violations"]))
    probe = blender_probe()
    if not probe["available"]:
        raise ValueError("bake_unavailable: " + probe["reason"])
    return {"ok": True, "blender": probe["path"], "mesh": mesh}


__all__ = ["MAX_TRIS", "MIN_BBOX_MM", "inspect_obj", "inspect_ply_header", "audit",
           "blender_probe", "bake_plan"]
