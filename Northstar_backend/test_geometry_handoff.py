"""3D handoff: the mesh contract, and an honest answer about Blender."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import geometry_handoff as gh  # noqa: E402

CUBE = """# a 100mm cube with UVs
v 0 0 0
v 100 0 0
v 100 100 0
v 0 100 0
vt 0 0
vt 1 0
vt 1 1
vt 0 1
f 1/1 2/2 3/3 4/4
f 1/1 3/3 2/2
"""

NO_UV = """v 0 0 0
v 10 0 0
v 10 10 0
f 1 2 3
"""

NON_MANIFOLD = """v 0 0 0
v 10 0 0
v 10 10 0
v 0 10 0
v 5 5 10
vt 0 0
f 1/1 2/1 3/1
f 1/1 2/1 4/1
f 1/1 2/1 5/1
"""


def test_a_uv_cube_passes_with_millimetres_declared():
    mesh = gh.inspect_obj(CUBE)
    assert mesh["verts"] == 4 and mesh["faces"] == 2
    assert mesh["uv_faces"] == 2
    assert mesh["bbox_mm"] == {"x": 100.0, "y": 100.0, "z": 0.0}
    report = gh.audit(mesh, units="mm")
    assert report["ok"] is True, report["violations"]


def test_unspecified_units_are_refused_rather_than_assumed():
    mesh = gh.inspect_obj(CUBE)
    report = gh.audit(mesh, units="unspecified")
    assert "units_unspecified" in [v["code"] for v in report["violations"]]


def test_missing_uvs_block_the_bake():
    mesh = gh.inspect_obj(NO_UV)
    codes = [v["code"] for v in gh.audit(mesh, units="mm")["violations"]]
    assert "missing_uv" in codes


def test_a_non_manifold_edge_is_reported():
    mesh = gh.inspect_obj(NON_MANIFOLD)
    assert mesh["non_manifold_edges"] >= 1
    codes = [v["code"] for v in gh.audit(mesh, units="mm")["violations"]]
    assert "non_manifold_edges" in codes


def test_a_degenerate_bounding_box_is_reported():
    mesh = gh.inspect_obj("v 0 0 0\nv 1 0 0\nv 0 1 0\nvt 0 0\nf 1/1 2/1 3/1\n")
    codes = [v["code"] for v in gh.audit(mesh, units="mm")["violations"]]
    assert "bbox_degenerate" in codes


def test_an_empty_file_is_refused_with_both_codes():
    mesh = gh.inspect_obj("")
    codes = [v["code"] for v in gh.audit(mesh, units="mm")["violations"]]
    assert "no_geometry" in codes and "no_faces" in codes


def test_a_malformed_vertex_is_an_error_not_a_zero():
    with pytest.raises(ValueError) as caught:
        gh.inspect_obj("v 0 0\n")
    assert "obj_vertex_malformed" in str(caught.value)


def test_polycount_over_budget_is_refused():
    mesh = gh.inspect_obj(CUBE)
    mesh["tris"] = gh.MAX_TRIS + 1
    codes = [v["code"] for v in gh.audit(mesh, units="mm")["violations"]]
    assert "polycount_over_budget" in codes


def test_a_ply_header_is_parsed():
    data = (b"ply\nformat binary_little_endian 1.0\n"
            b"element vertex 8\nproperty float x\nelement face 12\n"
            b"property list uchar int vertex_indices\nend_header\n")
    info = gh.inspect_ply_header(data)
    assert info["format"] == "binary_little_endian"
    assert info["verts"] == 8 and info["faces"] == 12


def test_a_non_ply_file_is_refused():
    with pytest.raises(ValueError) as caught:
        gh.inspect_ply_header(b"not a ply")
    assert "ply_header_missing" in str(caught.value)


def test_the_bake_refuses_before_it_costs_anything():
    mesh = gh.inspect_obj(NO_UV)
    with pytest.raises(ValueError) as caught:
        gh.bake_plan(mesh, units="mm")
    assert "bake_refused" in str(caught.value)


def test_the_blender_probe_answers_with_a_reason_when_absent(monkeypatch):
    monkeypatch.setattr(gh.shutil, "which", lambda name: None)
    monkeypatch.setattr(gh.Path, "is_file", lambda self: False)
    probe = gh.blender_probe()
    assert probe["available"] is False
    assert "Blender" in probe["reason"]
