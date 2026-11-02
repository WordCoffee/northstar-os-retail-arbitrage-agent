"""Print lane unit tests — layered SVG/PDF dielines (no providers, no DB, no cost).

RE build 2026-10-16: verifies the parametric dieline geometry + renderers that
close the "print lane" gap identified against Packify.ai / DYP.ai.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import design_studio_print as dp  # noqa: E402


def test_templates_catalog_covers_labels_and_cartons():
    ids = {t["id"] for t in dp.TEMPLATES}
    for required in ("label_rounded_rectangle", "label_circle", "rsc_box", "tuck_end", "sleeve"):
        assert required in ids, required
    for t in dp.TEMPLATES:
        assert t["kind"] in ("label", "carton")
        for key in t["editable"]:
            assert key in t["params"], (t["id"], key)


def test_label_build_layers_and_dimensions():
    build = dp.build_label("rounded_rectangle", 90, 60, bleed_mm=3, safe_mm=3)
    assert abs(build["width_mm"] - 96) < 0.01
    assert abs(build["height_mm"] - 66) < 0.01
    layers = {it["layer"] for it in build["layers"]}
    assert {"bleed", "trim", "safe", "info"} <= layers
    assert build["meta"]["shape"] == "rounded_rectangle"


def test_rsc_blank_geometry_math():
    build = dp.build_carton("rsc_box", 200, 150, 100, flap_mm=75, glue_mm=15, bleed_mm=3)
    meta = build["meta"]
    assert meta["panels"] == [200, 150, 200, 150, 15]
    # blank width = 2*(L+W) + glue + 2*bleed ; height = H + 2*flap + 2*bleed
    assert abs(build["width_mm"] - (2 * 200 + 2 * 150 + 15 + 6)) < 0.5
    assert abs(build["height_mm"] - (100 + 2 * 75 + 6)) < 0.5
    # fold lines present (top/bottom + 4 vertical boundaries) and cut slits exist
    folds = [it for it in build["layers"] if it["layer"] == "fold"]
    assert len(folds) >= 6
    trims = [it for it in build["layers"] if it["layer"] == "trim" and it["kind"] == "line"]
    assert trims  # outline + equal-depth slits


def test_tuck_end_with_mixed_depths_builds():
    build = dp.build_carton("tuck_end", 90, 60, 160)
    assert build["meta"]["template"] == "tuck_end"
    assert build["meta"]["tuck_mm"] > build["meta"]["dust_mm"]


def test_svg_layers_units_and_determinism():
    build = dp.build_from_template("label_circle", {"width_mm": 50, "height_mm": 50})
    svg = dp.render_svg(build)
    for layer_id in ("layer-bleed", "layer-trim", "layer-fold", "layer-safe", "layer-info"):
        assert f'id="{layer_id}"' in svg
    assert svg.startswith("<svg") and 'width="56mm"' in svg and "viewBox=" in svg
    again = dp.render_svg(dp.build_from_template("label_circle", {"width_mm": 50, "height_mm": 50}))
    # generated_at differs; geometry must be identical
    import re
    strip = lambda s: re.sub(r"<desc>.*?</desc>", "", s, flags=re.S)
    assert strip(svg) == strip(again)


def test_pdf_renders_real_bytes():
    build = dp.build_from_template("rsc_box", {"length_mm": 150, "width_mm": 120, "height_mm": 90})
    pdf = dp.render_pdf(build)
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 800


def test_sanitize_empty_values_keep_defaults():
    """A cleared field must never 422 - it falls back to the template default."""
    clean = dp.sanitize_params("rsc_box", {"height_mm": "", "width_mm": None, "length_mm": "  "})
    defaults = dp._TEMPLATE_BY_ID["rsc_box"]["params"]
    assert clean["height_mm"] == defaults["height_mm"]
    assert clean["width_mm"] == defaults["width_mm"]
    assert clean["length_mm"] == defaults["length_mm"]


def test_doypack_dieline_geometry():
    b = dp.build_doypack(130, 210, gusset_mm=40, weld_mm=6, top_weld_mm=8,
                         zip_offset_mm=25, bleed_mm=3)
    m = b["meta"]
    assert m["template"] == "doypack"
    # sheet 130 + 2*6 weld + 2*3 bleed = 148 wide
    assert abs(b["width_mm"] - (130 + 12 + 6)) < 0.5
    # sheet height = 2*bleed + top seal + front + bottom seal + gusset + bottom
    # seal + back  (2026-10-19: two bottom seal bands now drawn, matching the
    # real film run: the gusset is welded to BOTH the front and the back)
    assert abs(b["height_mm"] - (2 * 3 + 8 + 210 + 6 + 40 + 6 + 210)) < 0.5
    folds = [it for it in b["layers"] if it["layer"] == "fold"]
    assert len(folds) >= 8, "6 structure folds + gusset centre crease + zipper line expected"
    texts = [it["text"] for it in b["layers"] if it["kind"] == "text"]
    assert any("zipper" in t for t in texts)
    # the planning dieline now marks the no-print zones and the seal zones
    safe = [it for it in b["layers"] if it["layer"] == "safe"]
    marks = [it for it in b["layers"] if it["layer"] == "marks"]
    assert len(safe) >= 3, "zipper keep-out + front and back print-safe areas"
    assert len(marks) >= 2, "both side weld zones"
    assert "planning dieline" in m["confidence"]
    assert m["seal_style"].startswith("assumed")
    svg = dp.render_svg(b)
    assert 'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"' in svg, \
        "standalone SVG must declare the inkscape namespace or browsers refuse to render it"
    assert 'id="layer-fold"' in svg and 'width="148mm"' in svg
    pdf = dp.render_pdf(b)
    assert pdf[:4] == b"%PDF"


def test_doypack_proportion_check_flags_the_half_gusset_case():
    """The blueprint's §2.5 finding, encoded as a check: Mogra's 8 oz pouch spec
    (150x210+40) is roughly HALF the published gusset for that fill weight."""
    chk = dp.check_doypack_proportions(150, 210, 40, fill_g=227)
    assert chk["status"] == "warnings"
    assert any("gusset" in w for w in chk["warnings"])
    assert chk["ladder_row"]["fill_g"] == 250
    assert chk["ladder_row"]["gusset_mm"] == 80
    # a spec on the ladder is clean
    ok = dp.check_doypack_proportions(140, 200, 80, fill_g=250)
    assert ok["status"] == "ok", ok["warnings"]
    # the warning text never silently reshapes the operator's numbers
    built = dp.build_doypack(150, 210, gusset_mm=40, fill_g=227)
    assert built["meta"]["gusset_mm"] == 40


def test_doypack_in_catalog_and_buildable_from_template():
    ids = {t["id"] for t in dp.TEMPLATES}
    assert "doypack" in ids
    b = dp.build_from_template("doypack", {"width_mm": 150, "height_mm": 210,
                                           "gusset_mm": 40, "zip_offset_mm": 25})
    assert b["meta"]["width_mm"] == 150
    with pytest.raises(ValueError):
        dp.sanitize_params("doypack", {"gusset_mm": 500})


def test_sanitize_rejects_unknown_keys_and_ranges():
    with pytest.raises(ValueError):
        dp.sanitize_params("rsc_box", {"heigth_mm": 100})  # typo key
    with pytest.raises(ValueError):
        dp.sanitize_params("rsc_box", {"height_mm": 99999})
    with pytest.raises(ValueError):
        dp.sanitize_params("no_such_template", {})
    with pytest.raises(ValueError):
        dp.build_label("square", 60, 40)  # square requires w == h
    with pytest.raises(ValueError):
        dp.build_label("hexagon", 60, 40)
    with pytest.raises(ValueError):
        dp.build_carton("mailer", 100, 100, 100)


# -- prepress endpoints: ICC check + CMYK conversion (2026-10-19) --------------

class _Assets:
    def __init__(self, plate_name):
        self.plate_name = plate_name
        self.created = []

    def get_by_id(self, aid, account_id=None):
        if aid == "plate-dev":
            return {"id": aid, "storage_key": self.plate_name,
                    "project_id": None, "name": "dev plate"}
        return None

    def create(self, data):
        self.created.append(data)
        return f"aid-{len(self.created)}"


def _plate_name() -> str | None:
    """Resolve the dev plate filename from the compositor preset (no literal)."""
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parent / "data" / "compose_presets.json"
    if not p.is_file():
        return None
    try:
        preset = json.loads(p.read_text(encoding="utf-8")).get("mogra-forest-dusk") or {}
    except Exception:
        return None
    return preset.get("plate_file")


class _DB:
    def __init__(self, plate_name=None):
        class _DS:
            def __init__(self):
                self.assets = _Assets(plate_name)
        self.design_studio = _DS()


def _client():
    from fastapi.testclient import TestClient
    from main import app
    return app, TestClient(app)


def test_prepress_check_requires_auth_and_404s_on_unknown_asset(monkeypatch):
    app, client = _client()
    # Loopback TestClient is handed the dev demo session unless the shim is off;
    # assert the hosted fail-closed path (see test_text_fidelity).
    previous = getattr(app.state, "dev_auto_session", False)
    app.state.dev_auto_session = False
    try:
        r = client.post("/api/design-studio/print/prepress/check", json={"asset_id": "x"})
        assert r.status_code == 401
    finally:
        app.state.dev_auto_session = previous

    import design_studio_api
    app.dependency_overrides[design_studio_api.studio_account] = lambda: "org-pp"
    try:
        monkeypatch.setattr(dp, "get_northstar_db", lambda: _DB())
        r = client.post("/api/design-studio/print/prepress/check",
                        json={"asset_id": "no-such"})
        assert r.status_code == 404
        r = client.get("/api/design-studio/print/prepress/profiles")
        assert r.status_code == 200
        assert "profiles" in r.json()
    finally:
        app.dependency_overrides = {}


def test_prepress_check_runs_on_the_real_dev_plate(monkeypatch):
    import prepress as pp
    plate_name = _plate_name()
    if not pp.available_cmyk_profiles():
        pytest.skip("no CMYK ICC profile on this machine")
    if not plate_name:
        pytest.skip("no compositor preset on disk")
    plate = dp._out_dir() / plate_name
    if not plate.is_file():
        pytest.skip("dev plate not on disk")

    app, client = _client()
    import design_studio_api
    app.dependency_overrides[design_studio_api.studio_account] = lambda: "org-pp"
    db = _DB(plate_name)
    try:
        monkeypatch.setattr(dp, "get_northstar_db", lambda: db)
        r = client.post("/api/design-studio/print/prepress/check",
                        json={"asset_id": "plate-dev", "persist_cmyk": True})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["verdict"] in ("printable", "blocked")
        assert body["gamut"]["profile"]
        assert body["ink"]["max_tac_pct"] > 0
        assert body["cmyk_asset"]["asset_id"] and body["proof_asset"]["asset_id"]
        roles = [a["metadata"]["prepress"]["role"] for a in db.design_studio.assets.created]
        assert roles == ["cmyk", "soft_proof"]
        # the created CMYK file really is a TIFF on disk
        for a in db.design_studio.assets.created:
            p = dp._out_dir() / a["storage_key"]
            assert p.is_file() and p.stat().st_size > 0
            p.unlink()
    finally:
        app.dependency_overrides = {}
