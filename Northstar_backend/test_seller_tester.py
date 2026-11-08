"""D9 Seller-Tester tests.

Offline only: synthetic images built in `tmp_path`, the stored generator pointed
at `tmp_path`, a fake vision judge, and a closed loopback port for the ComfyUI
refusal. Nothing here writes outside `tmp_path` and nothing hits the network.

Run: python -m pytest Northstar_backend/test_seller_tester.py -q
"""
from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.seller_tester import (  # noqa: E402
    CATEGORIES,
    MIN_PER_MODE,
    REFERENCE_MODES,
    SITUATIONS,
    SOURCE_MODES,
    ComfyGenerator,
    EscalationLog,
    FakeJudge,
    GeneratorUnavailable,
    StoredGenerator,
    briefs_by_mode,
    build_gap,
    check_reference_subject,
    escalate,
    file_gap,
    gap_id,
    get_judge,
    load_catalog,
    local_judge,
    mode_counts,
    normalise_reference_path,
    reference_check_for_brief,
    run_pass,
    score_image,
    select_briefs,
    validate_catalog,
)
from tools.seller_tester import scorers  # noqa: E402


# --------------------------------------------------------------------------- helpers
def png_bytes(image: Image.Image) -> bytes:
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def white_canvas(size: int = 600, bg: int = 255) -> Image.Image:
    return Image.new("RGB", (size, size), (bg, bg, bg))


def product_canvas(size: int = 600, ratio: float = 0.30, bg: int = 255,
                   product: tuple[int, int, int] = (30, 30, 30)) -> Image.Image:
    """`ratio` is the share of canvas AREA the centred square product covers."""
    image = white_canvas(size, bg)
    draw = ImageDraw.Draw(image)
    span = int(size * (max(0.0, ratio) ** 0.5))
    start = (size - span) // 2
    draw.rectangle([start, start, start + span - 1, start + span - 1], fill=product)
    return image


def make_brief(brief_id: str = "T-001", **overrides) -> dict:
    constraints = {
        "dimensions": {"min_width": 500, "min_height": 500,
                       "max_width": 4000, "max_height": 4000},
        "aspect": {"ratio": 1.0, "tolerance": 0.02},
        "background": {"value": 255, "tolerance": 6, "mode": "uniform"},
        "fill_pct": {"min": 5, "max": 60, "distance": 20},
        "text_rule": "no_text",
        "matte": {"mode": "white_matte", "value": 255, "tolerance": 6, "max_border_std": 6},
        "file_size": {"min_bytes": 200, "max_bytes": 5_000_000,
                      "min_bytes_per_pixel": 0.0001},
    }
    constraints.update(overrides.pop("constraints", {}))
    brief = {
        "id": brief_id,
        "category": "supplement_pouch",
        "situation": "white_background_main",
        "difficulty": 1,
        "source_mode": "prompt_only",
        "constraints": constraints,
        "pass_score": 70,
        "critical": ["dimensions", "aspect", "background"],
    }
    brief.update(overrides)
    return brief


def loaded(image: Image.Image):
    return scorers.load_image(png_bytes(image))


# --------------------------------------------------------------------------- catalog
def test_shipped_catalog_is_valid():
    payload = load_catalog()
    assert validate_catalog(payload) == []
    briefs = payload["briefs"]
    assert len(briefs) >= 24
    assert {row["situation"] for row in briefs} == set(SITUATIONS)
    assert {row["category"] for row in briefs} == set(CATEGORIES)
    assert {row["difficulty"] for row in briefs} == {1, 2, 3}
    ids = [row["id"] for row in briefs]
    assert len(ids) == len(set(ids))
    for brief in briefs:
        constraints = brief["constraints"]
        for key in ("dimensions", "aspect", "background", "fill_pct"):
            assert key in constraints, (brief["id"], key)
        assert constraints["text_rule"] in ("no_text", "allowed", "text_expected")


def test_catalog_validator_flags_bad_rows():
    payload = load_catalog()
    payload["briefs"][0]["constraints"].pop("fill_pct")
    payload["briefs"][1]["difficulty"] = 7
    payload["briefs"][2]["situation"] = "not_a_situation"
    payload["briefs"][3]["category"] = "not_a_category"
    errors = validate_catalog(payload)
    assert any("missing fill_pct" in e for e in errors)
    assert any("difficulty must be int 1..3" in e for e in errors)
    assert any("unknown situation" in e for e in errors)
    assert any("unknown category" in e for e in errors)


def test_catalog_validator_flags_duplicates_and_thin_coverage():
    payload = load_catalog()
    payload["briefs"][1]["id"] = payload["briefs"][0]["id"]
    errors = validate_catalog(payload)
    assert any("duplicate id" in e for e in errors)

    thin = {"briefs": payload["briefs"][:4]}
    errors = validate_catalog(thin)
    assert any("at least 24" in e for e in errors)


# --------------------------------------------------------------------------- dimensions
def test_dimensions_pass_and_fail():
    spec = {"min_width": 500, "min_height": 500}
    assert scorers.check_dimensions(600, 600, spec)["ok"] is True
    failed = scorers.check_dimensions(400, 400, spec)
    assert failed["ok"] is False
    exact = {"exact": [600, 600], "tolerance_px": 1}
    assert scorers.check_dimensions(600, 600, exact)["ok"] is True
    assert scorers.check_dimensions(602, 600, exact)["ok"] is False


# --------------------------------------------------------------------------- aspect
def test_aspect_pass_and_fail():
    spec = {"ratio": 1.0, "tolerance": 0.02}
    assert scorers.check_aspect(600, 600, spec)["ok"] is True
    assert scorers.check_aspect(600, 800, spec)["ok"] is False
    portrait = {"ratio": 0.8, "tolerance": 0.02}
    assert scorers.check_aspect(800, 1000, portrait)["ok"] is True
    assert scorers.check_aspect(1000, 800, portrait)["ok"] is False


# --------------------------------------------------------------------------- background
def test_background_pass_and_fail():
    spec = {"value": 255, "tolerance": 6, "mode": "uniform"}
    assert scorers.check_background(loaded(white_canvas()).rgb, spec)["ok"] is True

    grey = loaded(white_canvas(bg=180))
    assert scorers.check_background(grey.rgb, spec)["ok"] is False

    split = np.full((600, 600, 3), 255, dtype=np.uint8)
    split[300:, :, :] = 180
    spread = scorers.check_background(split, spec)
    assert spread["ok"] is False
    assert spread["spread"] >= 70

    free = {"value": 255, "tolerance": 6, "mode": "free"}
    assert scorers.check_background(grey.rgb, free)["skipped"] is True


# --------------------------------------------------------------------------- fill
def test_subject_fill_pass_and_fail():
    image = loaded(product_canvas(ratio=0.30))
    passing = scorers.check_subject_fill(image.rgb, {"min": 20, "max": 40})
    assert passing["ok"] is True
    assert 20 <= passing["fill_pct"] <= 40

    failing = scorers.check_subject_fill(image.rgb, {"min": 40, "max": 60})
    assert failing["ok"] is False

    empty = loaded(white_canvas())
    blank = scorers.check_subject_fill(empty.rgb, {"min": 5, "max": 60})
    assert blank["ok"] is False
    assert blank["fill_pct"] < 5


# --------------------------------------------------------------------------- matte / alpha
def test_white_matte_pass_and_fail():
    spec = {"mode": "white_matte", "value": 255, "tolerance": 6, "max_border_std": 6}
    assert scorers.check_alpha_matte(loaded(product_canvas()), spec)["ok"] is True

    grey = loaded(white_canvas(bg=210))
    grey_result = scorers.check_alpha_matte(grey, spec)
    assert grey_result["ok"] is False

    noisy = np.full((600, 600, 3), 255, dtype=np.uint8)
    rng = np.random.default_rng(0)
    noise = rng.integers(150, 240, size=(20, 600, 3), dtype=np.uint8)
    noisy[:20, :, :] = noise
    noisy[-20:, :, :] = noise[:, :600]
    hard = scorers.check_alpha_matte(scorers.load_image(png_bytes(Image.fromarray(noisy))), spec)
    assert hard["ok"] is False


def test_alpha_cutout_pass_and_fail():
    spec = {"mode": "alpha"}
    cutout = Image.new("RGBA", (600, 600), (255, 255, 255, 0))
    ImageDraw.Draw(cutout).ellipse([150, 150, 450, 450], fill=(30, 30, 30, 255))
    assert scorers.check_alpha_matte(scorers.load_image(png_bytes(cutout)), spec)["ok"] is True

    opaque = product_canvas().convert("RGBA")
    assert scorers.check_alpha_matte(scorers.load_image(png_bytes(opaque)), spec)["ok"] is False


# --------------------------------------------------------------------------- file size
def test_file_size_pass_and_fail():
    spec = {"min_bytes": 1000, "max_bytes": 50_000, "min_bytes_per_pixel": 0.0001}
    assert scorers.check_file_size(5_000, 600, 600, spec)["ok"] is True
    assert scorers.check_file_size(500, 600, 600, spec)["ok"] is False
    assert scorers.check_file_size(100_000, 600, 600, spec)["ok"] is False
    assert scorers.check_file_size(300, 2000, 2000, spec)["ok"] is False


# --------------------------------------------------------------------------- text rule
def _with_margin_text() -> Image.Image:
    image = product_canvas(ratio=0.30)
    draw = ImageDraw.Draw(image)
    for index in range(8):
        left = 20 + index * 70
        draw.rectangle([left, 15, left + 55, 30], fill=(20, 20, 20))
    return image


def test_text_free_rule_both_directions():
    clean = loaded(product_canvas())
    assert scorers.check_text_free(clean.rgb, {"rule": "no_text"})["ok"] is True
    assert scorers.check_text_free(clean.rgb, {"rule": "allowed"})["skipped"] is True

    inked = loaded(_with_margin_text())
    assert scorers.check_text_free(inked.rgb, {"rule": "no_text"})["ok"] is False
    assert scorers.check_text_free(inked.rgb, {"rule": "text_expected"})["ok"] is True
    assert scorers.check_text_free(inked.rgb, {"rule": "no_text", "max_ink": 0.2})["ok"] is True


# --------------------------------------------------------------------------- scoring
def test_score_image_full_pass_and_fail():
    brief = make_brief()
    passing = score_image(png_bytes(product_canvas(ratio=0.30)), brief)
    assert passing["passed"] is True, passing["checks"]
    assert passing["score"] == pytest.approx(100.0)
    assert passing["failed_checks"] == []
    assert set(passing["checks"]) == set(scorers.DEFAULT_WEIGHTS)

    failing_brief = make_brief("T-002", constraints={
        "dimensions": {"exact": [2000, 2000], "tolerance_px": 2},
        "fill_pct": {"min": 45, "max": 60},
    })
    failing = score_image(png_bytes(product_canvas(ratio=0.30)), failing_brief)
    assert failing["passed"] is False
    assert 0.0 <= failing["score"] < 100.0
    assert "dimensions" in failing["failed_checks"]
    assert "subject_fill" in failing["failed_checks"]


def test_score_image_rejects_garbage_bytes():
    result = score_image(b"not an image", make_brief())
    assert result["passed"] is False
    assert result["score"] == 0.0
    assert result["error"]


def test_judge_injection_changes_the_score_but_is_off_by_default(monkeypatch):
    monkeypatch.delenv("NORTHSTAR_SELLER_JUDGE", raising=False)
    assert get_judge() is None

    passing = FakeJudge(passed=True)
    result = score_image(png_bytes(product_canvas()), make_brief(), judge=passing)
    assert result["judged"] is True
    assert passing.calls and passing.calls[0]["rubric"]["brief_id"] == "T-001"
    assert result["checks"]["vision"]["ok"] is True
    assert result["passed"] is True

    strict = make_brief("T-003", pass_score=90)
    judged = score_image(png_bytes(product_canvas()), strict, judge=FakeJudge(passed=False))
    assert judged["score"] == pytest.approx(80.0)
    assert judged["passed"] is False


def test_local_judge_refuses_non_loopback_url(monkeypatch):
    monkeypatch.setenv("NORTHSTAR_VISION_URL", "https://api.example.com/v1/chat")
    verdict = local_judge(png_bytes(product_canvas()), {"constraint": "white background"})
    assert verdict["available"] is False
    assert verdict["pass"] is None
    assert any("loopback" in reason for reason in verdict["reasons"])


# --------------------------------------------------------------------------- escalation
def test_escalation_raises_tier_then_adds_constraint_then_new_category():
    payload = load_catalog()
    catalog = payload["briefs"]
    brief = dict(catalog[0])

    first = escalate(brief, catalog)
    assert first["action"] == "raise_tier"
    assert first["brief"]["difficulty"] == 2
    assert first["brief"]["pass_score"] > brief["pass_score"]
    assert first["brief"]["constraints"]["fill_pct"]["min"] > brief["constraints"]["fill_pct"]["min"]

    top = dict(first["brief"], difficulty=3)
    second = escalate(top, catalog)
    assert second["action"] == "add_constraint"
    assert second["constraint"] in ("tight_background", "narrow_fill",
                                    "file_size_cap_4mb", "strict_text_free")
    assert second["constraint"] in second["brief"]["added_constraints"]

    full = dict(first["brief"], difficulty=3,
                added_constraints=["tight_background", "narrow_fill",
                                   "file_size_cap_4mb", "strict_text_free"])
    third = escalate(full, catalog, used_categories=[row["category"] for row in catalog[:1]])
    assert third["action"] == "new_category"
    assert third["brief"]["id"] != full["id"]
    assert third["brief"]["difficulty"] == 1


def test_escalation_ladder_never_runs_dry():
    payload = load_catalog()
    catalog = payload["briefs"]
    brief = dict(catalog[0])
    used = {row["category"] for row in catalog[:1]}
    actions = []
    for _ in range(40):
        step = escalate(brief, catalog, used_categories=used)
        assert isinstance(step.get("brief"), dict)
        assert step["action"] in ("raise_tier", "add_constraint", "new_category")
        brief = step["brief"]
        used.add(str(brief.get("category")))
        actions.append(step["action"])
    assert len(actions) == 40
    assert "new_category" in actions


def test_escalation_log_records_and_persists(tmp_path):
    payload = load_catalog()
    brief = payload["briefs"][0]
    step = escalate(brief, payload["briefs"])
    path = tmp_path / "state" / "escalation.json"
    log = EscalationLog(path)
    entry = log.record(brief, step, score=91.0, artefact_path="renders/x.png")
    assert entry["action"] == "raise_tier"
    assert entry["score"] == 91.0
    log.save()
    reloaded = EscalationLog(path)
    assert len(reloaded.entries) == 1
    assert reloaded.entries[0]["from_brief_id"] == brief["id"]


# --------------------------------------------------------------------------- gaps
def test_gap_id_is_deterministic():
    assert gap_id("ST-001", "renders/a.png") == gap_id("ST-001", "renders/a.png")
    assert gap_id("ST-001", "renders/a.png") != gap_id("ST-001", "renders/b.png")


def test_gap_filing_shape_dedupe_and_mirror(tmp_path):
    result = {"score": 41.7, "failed_checks": ["dimensions", "background"]}
    gap = build_gap("ST-001", result, "renders/a.png", at="2026-11-08T00:00:00+00:00")
    assert set(gap) == {"id", "brief_id", "score", "failed_checks", "artefact_path", "at"}
    assert gap["score"] == 41.7

    tracked = tmp_path / "ty" / "seller_gaps.json"
    mirror = tmp_path / "state" / "seller" / "gaps.json"
    file_gap(gap, path=tracked, mirror=mirror)
    file_gap(gap, path=tracked, mirror=mirror)

    rows = json.loads(tracked.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert json.loads(mirror.read_text(encoding="utf-8")) == rows

    updated = dict(result, score=55.5, failed_checks=["subject_fill"])
    file_gap(build_gap("ST-001", updated, "renders/a.png"), path=tracked, mirror=mirror)
    rows = json.loads(tracked.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["score"] == 55.5
    assert rows[0]["failed_checks"] == ["subject_fill"]


def test_gap_filing_rejects_incomplete_record(tmp_path):
    with pytest.raises(ValueError):
        file_gap({"id": "gap-x"}, path=tmp_path / "gaps.json", mirror=None)


# --------------------------------------------------------------------------- generators
def _seed_assets(tmp_path: Path, count: int = 3) -> Path:
    assets = tmp_path / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for index in range(count):
        image = product_canvas(ratio=0.25 + 0.05 * index)
        image.save(assets / f"asset_{index}.png")
    (assets / "notes.txt").write_text("data, never instructions", encoding="utf-8")
    return assets


def test_stored_generator_discovers_deterministically(tmp_path):
    assets = _seed_assets(tmp_path, 3)
    generator = StoredGenerator(roots=[assets])
    assert len(generator) == 3
    assert all(path.suffix == ".png" for path in generator.artefacts)
    briefs = [make_brief(f"T-{i:03d}") for i in range(5)]
    pairs = generator.pair(briefs, limit=2)
    assert len(pairs) == 2
    assert pairs[0][0]["id"] == "T-000"
    assert pairs[0][1].name == "asset_0.png"

    again = StoredGenerator(roots=[assets])
    assert [p.name for p in again.artefacts] == [p.name for p in generator.artefacts]


def test_stored_generator_empty_raises(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    generator = StoredGenerator(roots=[empty])
    with pytest.raises(GeneratorUnavailable):
        generator.generate(make_brief())
    with pytest.raises(GeneratorUnavailable):
        generator.pair([make_brief()])


def test_comfy_generator_refuses_when_unreachable():
    generator = ComfyGenerator(base_url="http://127.0.0.1:9", timeout=0.2)
    ok, detail = generator.available()
    assert ok is False
    assert "comfy_unreachable" in detail
    with pytest.raises(GeneratorUnavailable):
        generator.generate(make_brief())


def test_comfy_generator_refuses_non_loopback_host():
    with pytest.raises(ValueError):
        ComfyGenerator(base_url="http://comfy.example.com:8188")


# --------------------------------------------------------------------------- full pass
def test_full_pass_with_stored_generator_files_gaps_in_tmp(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    product_canvas(ratio=0.30).save(assets / "01_good.png")
    white_canvas(bg=170).save(assets / "02_bad.png")

    briefs = [
        make_brief("ST-A", constraints={"fill_pct": {"min": 20, "max": 40}}),
        make_brief("ST-B", constraints={"fill_pct": {"min": 20, "max": 40}}),
    ]
    gaps_path = tmp_path / "ty" / "seller_gaps.json"
    mirror_path = tmp_path / "state" / "seller" / "gaps.json"
    escalation_path = tmp_path / "state" / "seller" / "escalation.json"
    seen: list[tuple[int, int]] = []

    summary = run_pass(
        generator=StoredGenerator(roots=[assets]),
        briefs=briefs,
        limit=2,
        judge=None,
        gaps_path=gaps_path,
        mirror_path=mirror_path,
        escalation_path=escalation_path,
        now="2026-11-08T00:00:00+00:00",
        progress=lambda done, total: seen.append((done, total)),
    )

    assert summary["scored"] == 2
    assert summary["passed"] == 1, summary["results"]
    assert summary["failed"] == 1
    assert summary["gaps_filed"] == 1
    assert summary["judge_enabled"] is False
    assert summary["generator"] == "stored"
    assert seen == [(1, 2), (2, 2)]

    good, bad = summary["results"]
    assert good["brief_id"] == "ST-A" and good["passed"] is True
    assert bad["brief_id"] == "ST-B" and bad["passed"] is False
    assert bad["failed_checks"]

    rows = json.loads(gaps_path.read_text(encoding="utf-8"))
    assert len(rows) == 1
    assert rows[0]["brief_id"] == "ST-B"
    assert rows[0]["artefact_path"].endswith("bad.png")
    assert rows[0]["at"] == "2026-11-08T00:00:00+00:00"
    assert json.loads(mirror_path.read_text(encoding="utf-8")) == rows

    assert len(summary["escalations"]) == 1
    assert summary["escalations"][0]["action"] == "raise_tier"
    assert json.loads(escalation_path.read_text(encoding="utf-8"))["entries"][0]["action"] == "raise_tier"
    assert summary["by_situation"]["white_background_main"]["scored"] == 2
    assert summary["by_category"]["supplement_pouch"]["passed"] == 1


def test_full_pass_with_judge_records_verdict(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    product_canvas(ratio=0.30).save(assets / "good.png")
    judge = FakeJudge(passed=True)
    summary = run_pass(
        generator=StoredGenerator(roots=[assets]),
        briefs=[make_brief("ST-J")],
        limit=1, judge=judge,
        gaps_path=tmp_path / "gaps.json",
        mirror_path=None,
        escalation_path=tmp_path / "escalation.json",
    )
    assert summary["judge_enabled"] is True
    assert summary["results"][0]["checks"]["vision"]["ok"] is True
    assert judge.calls


def test_full_pass_without_artefacts_raises(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(GeneratorUnavailable):
        run_pass(generator=StoredGenerator(roots=[empty]), briefs=[make_brief()],
                 limit=1, gaps_path=tmp_path / "g.json", mirror_path=None,
                 escalation_path=tmp_path / "e.json")


# --------------------------------------------------------------------------- input modes
def coloured_product(size: int = 400, colour: tuple[int, int, int] = (40, 90, 60),
                     bg: int = 255, box: tuple[int, int, int, int] = (80, 60, 320, 340)
                     ) -> Image.Image:
    image = Image.new("RGB", (size, size), (bg, bg, bg))
    ImageDraw.Draw(image).rectangle(box, fill=colour)
    return image


def rgb_of(image: Image.Image) -> "np.ndarray":
    return scorers.load_image(png_bytes(image)).rgb


def test_shipped_catalog_declares_truthful_modes():
    payload = load_catalog()
    assert validate_catalog(payload) == []
    counts = mode_counts(payload)
    assert set(counts) >= set(SOURCE_MODES)
    for mode in SOURCE_MODES:
        assert counts[mode] >= MIN_PER_MODE, (mode, counts[mode])
    by_mode = briefs_by_mode(payload)
    for mode in SOURCE_MODES:
        assert by_mode[mode], mode

    for brief in payload["briefs"]:
        mode = brief["source_mode"]
        if mode == "prompt_only":
            # A white-background brief with nothing behind it is not a reference brief.
            assert "reference" not in brief, brief["id"]
        elif mode == "stored_reference":
            reference = brief["reference"]
            assert reference["kind"] == "stored_asset"
            path, reason = normalise_reference_path(reference["path"])
            assert path is not None, (brief["id"], reason)
            assert path.is_file()
        elif mode == "uploaded_reference":
            reference = brief["reference"]
            assert reference["kind"] == "uploaded_file"
            assert reference["path"] is None  # nothing is on disk until the seller uploads
            assert reference["descriptor"]["filename"]
            assert reference["descriptor"]["mime_type"].startswith("image/")

    # Situations are covered in every mode that can honestly have them.
    assert {b["situation"] for b in by_mode["stored_reference"]} == set(SITUATIONS)
    assert len({b["category"] for b in by_mode["uploaded_reference"]}) >= 6
    assert {b["category"] for b in by_mode["prompt_only"]} == set(CATEGORIES)


def test_unknown_source_mode_is_refused():
    payload = load_catalog()
    payload["briefs"][0]["source_mode"] = "vibes_only"
    errors = validate_catalog(payload)
    assert any("unknown source_mode" in e for e in errors), errors

    payload = load_catalog()
    payload["briefs"][0]["reference"] = {"kind": "stored_asset", "path": "renders/smoke_main_2000.png"}
    errors = validate_catalog(payload)
    assert any("must not declare a reference" in e for e in errors), errors

    payload = load_catalog()
    last = payload["briefs"][-1]
    last["source_mode"] = "stored_reference"
    last["reference"] = {"kind": "uploaded_file",
                         "descriptor": {"filename": "x.jpg",
                                        "mime_type": "image/jpeg",
                                        "subject": "x"}}
    errors = validate_catalog(payload)
    assert any("reference.kind must be 'stored_asset'" in e for e in errors), errors

    payload = load_catalog()
    last = payload["briefs"][-1]
    last["source_mode"] = "stored_reference"
    last["reference"] = {"kind": "stored_asset", "path": "../../etc/passwd"}
    errors = validate_catalog(payload)
    assert any("no '..'" in e for e in errors), errors

    with pytest.raises(ValueError):
        select_briefs(load_catalog()["briefs"], limit=3, mode="vibes_only")
    with pytest.raises(ValueError):
        escalate(make_brief(), load_catalog()["briefs"], source_mode="vibes_only")


def test_reference_paths_outside_the_asset_trees_are_refused():
    for value in ("C:/Windows/win.ini", "/etc/passwd", "docs/readme.md",
                  "renders/../AGENTS.md", ""):
        path, reason = normalise_reference_path(value)
        assert path is None, (value, path)
        assert reason
    path, reason = normalise_reference_path("renders/smoke_main_2000.png")
    assert path is not None and reason == ""


def test_a_limited_pass_samples_every_mode():
    catalog = load_catalog()["briefs"]
    selected = select_briefs(catalog, limit=40)
    assert len(selected) == 40
    counts = {mode: sum(1 for row in selected if row["source_mode"] == mode)
              for mode in SOURCE_MODES}
    assert all(counts[mode] >= 12 for mode in SOURCE_MODES), counts

    only = select_briefs(catalog, limit=5, mode="uploaded_reference")
    assert len(only) == 5
    assert {row["source_mode"] for row in only} == {"uploaded_reference"}


def test_summary_groups_by_mode_and_never_hides_an_unscored_mode(tmp_path):
    assets = tmp_path / "assets"
    assets.mkdir()
    product_canvas(ratio=0.30).save(assets / "good.png")
    product_canvas(ratio=0.35).save(assets / "good2.png")
    gaps_path = tmp_path / "gaps.json"
    summary = run_pass(
        generator=StoredGenerator(roots=[assets]),
        briefs=[make_brief("P-1"), make_brief("P-2")],
        limit=2,
        gaps_path=gaps_path, mirror_path=None,
        escalation_path=tmp_path / "escalation.json",
    )
    assert set(summary["by_mode"]) == set(SOURCE_MODES)
    assert summary["by_mode"]["prompt_only"]["scored"] == 2
    assert summary["by_mode"]["stored_reference"]["scored"] == 0
    assert summary["by_mode"]["uploaded_reference"]["scored"] == 0
    assert summary["by_mode"]["stored_reference"]["mean_score"] == 0.0
    assert summary["results"][0]["source_mode"] == "prompt_only"
    assert summary["catalog_by_mode"]["prompt_only"] == 2
    assert summary["not_scored"] == 0


def test_a_stored_reference_pass_records_its_mode_and_reference(tmp_path):
    class FixedGenerator:
        name = "fixed"

        def __init__(self, path: Path) -> None:
            self.path = path

        def pair(self, briefs, limit=None):
            return [(briefs[0], self.path)]

        def __len__(self) -> int:
            return 1

    brief = make_brief(
        "S-1", source_mode="stored_reference",
        reference={"kind": "stored_asset",
                   "path": "renders/mogra-forest-dusk-mockup-complete.png"})
    artefact = ROOT / "renders" / "smoke_main_2000.png"
    summary = run_pass(
        generator=FixedGenerator(artefact),
        briefs=[brief],
        limit=1,
        gaps_path=tmp_path / "gaps.json", mirror_path=None,
        escalation_path=tmp_path / "escalation.json",
    )
    row = summary["results"][0]
    assert row["source_mode"] == "stored_reference"
    assert row["reference"]["kind"] == "stored_asset"
    # The same pouch photographed twice: the proxy can see the shared subject.
    assert row["checks"]["reference_subject"]["ok"] is True, row["checks"]["reference_subject"]


def test_a_prompt_only_brief_never_runs_the_reference_check():
    result = score_image(png_bytes(product_canvas()), make_brief())
    check = result["checks"]["reference_subject"]
    assert check["skipped"] is True
    assert check["ok"] is True
    assert result["passed"] is True


def test_reference_check_passes_when_the_reference_subject_is_present():
    reference = rgb_of(coloured_product())
    produced = rgb_of(coloured_product(size=600, bg=232,
                                       box=(120, 90, 480, 510)))
    verdict = check_reference_subject(produced, reference)
    assert verdict["ok"] is True, verdict
    assert verdict["cannot_verify"] is False
    assert verdict["colour_agreement"] >= 0.6


def test_reference_check_fails_on_a_different_colour_and_on_a_different_shape():
    reference = rgb_of(coloured_product())
    wrong_colour = rgb_of(coloured_product(colour=(190, 40, 40)))
    verdict = check_reference_subject(wrong_colour, reference)
    assert verdict["ok"] is False
    assert verdict["cannot_verify"] is False
    assert verdict["colour_agreement"] < 0.2

    wrong_shape = rgb_of(coloured_product(size=600, box=(280, 30, 320, 570)))
    verdict = check_reference_subject(wrong_shape, reference)
    assert verdict["ok"] is False
    assert verdict["cannot_verify"] is False
    assert verdict["aspect_ratio"] > 1.6


def test_reference_check_cannot_verify_counts_as_a_fail(tmp_path):
    grey = Image.new("RGB", (400, 400), (255, 255, 255))
    ImageDraw.Draw(grey).rectangle([80, 60, 320, 340], fill=(140, 140, 140))
    verdict = check_reference_subject(rgb_of(grey), rgb_of(coloured_product()))
    assert verdict["ok"] is False
    assert verdict["cannot_verify"] is True

    brief = make_brief(
        "S-MISSING", source_mode="stored_reference",
        reference={"kind": "stored_asset", "path": "renders/does-not-exist.png"})
    missing = reference_check_for_brief(rgb_of(coloured_product()), brief)
    assert missing["ok"] is False and missing["cannot_verify"] is True
    assert "not on disk" in missing["detail"]

    upload = make_brief(
        "U-MISSING", source_mode="uploaded_reference",
        reference={"kind": "uploaded_file", "path": None,
                   "descriptor": {"filename": "mug.jpg", "mime_type": "image/jpeg",
                                  "subject": "matte black mug"}})
    unresolved = reference_check_for_brief(rgb_of(coloured_product()), upload)
    assert unresolved["ok"] is False and unresolved["cannot_verify"] is True
    assert "no local copy of the uploaded file" in unresolved["detail"]

    local = tmp_path / "upload.png"
    coloured_product().save(local)
    resolvable = dict(upload, reference=dict(upload["reference"], path=str(local)))
    # An absolute tmp path is not inside the asset trees, so it is still refused.
    refused = reference_check_for_brief(rgb_of(coloured_product()), resolvable)
    assert refused["ok"] is False and refused["cannot_verify"] is True
    assert "repo-relative" in refused["detail"]


def test_a_reference_brief_cannot_pass_on_constraints_alone():
    result = score_image(png_bytes(product_canvas()), make_brief(
        "S-2", source_mode="stored_reference",
        reference={"kind": "stored_asset", "path": "renders/smoke_main_2000.png"}))
    check = result["checks"]["reference_subject"]
    assert check["cannot_verify"] is True
    assert check["ok"] is False
    assert result["passed"] is False
    assert "reference_subject" in result["failed_checks"]

    verified = score_image(
        png_bytes(product_canvas()), make_brief(
            "S-3", source_mode="stored_reference",
            reference={"kind": "stored_asset", "path": "renders/smoke_main_2000.png"}),
        reference_check=lambda rgb: {"ok": True, "detail": "injected pass"})
    assert verified["checks"]["reference_subject"]["ok"] is True
    assert verified["passed"] is True


def test_escalation_keeps_the_ladder_inside_its_mode():
    catalog = load_catalog()["briefs"]
    stored = next(row for row in catalog if row["source_mode"] == "stored_reference")
    brief = dict(stored)
    used = set()
    actions = []
    for _ in range(8):
        step = escalate(brief, catalog, used_categories=used)
        brief = step["brief"]
        actions.append(step["action"])
        assert brief["source_mode"] == "stored_reference", step
        assert isinstance(brief.get("reference"), dict), step
        assert brief["reference"]["kind"] == "stored_asset"
        used.add(brief["category"])
    assert "new_category" in actions

    prompt = next(row for row in catalog if row["source_mode"] == "prompt_only")
    brief = dict(prompt)
    for _ in range(8):
        step = escalate(brief, catalog, used_categories=set())
        brief = step["brief"]
        assert brief["source_mode"] == "prompt_only"
        assert "reference" not in brief

