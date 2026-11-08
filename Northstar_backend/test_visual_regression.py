"""D10 — visual regression gate, offline tests.

Fast, deterministic, no network and no browser. Everything here runs against
synthetic fixtures in ``tools/visual_regression/fixtures``; browser capture is
exercised only through the CLI when a real server is present.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.visual_regression import baseline as vbaseline  # noqa: E402
from tools.visual_regression import build_registry as vbuild  # noqa: E402
from tools.visual_regression import capture as vcapture  # noqa: E402
from tools.visual_regression import diff as vdiff  # noqa: E402
from tools.visual_regression import freeze as vfreeze  # noqa: E402
from tools.visual_regression import gate as vgate  # noqa: E402
from tools.visual_regression import views as vviews  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "tools" / "visual_regression" / "fixtures"
FIXTURE_MANIFEST = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
FIXTURE_ITEMS = FIXTURE_MANIFEST["fixtures"]


@pytest.fixture(scope="module")
def registry() -> vviews.Registry:
    return vviews.load_registry()


# --- registry -------------------------------------------------------------


def test_registry_covers_every_service_route(registry):
    service_routes = set(vviews.service_routes())
    registered = {v.route for v in registry.views}
    assert service_routes <= registered
    assert {"/", "/home"} <= registered
    assert len(registry.views) == len(service_routes) + 2
    assert registry.schema == "northstar.visual_views.v1"


def test_registry_validates_clean(registry):
    assert vviews.validate(registry) == []


def test_every_view_declares_required_fields(registry):
    for view in registry.views:
        assert view.id, "view id"
        assert view.route.startswith("/"), view.id
        assert view.viewports, view.id
        assert set(view.viewports) == {"desktop", "iphone12-webkit"}, view.id
        assert view.ready_selector or view.ready.get("wait_until"), view.id
        assert view.freeze["still"] == "1", view.id
        assert int(view.freeze["seed"]) > 0, view.id


def test_viewports_match_the_brief(registry):
    desktop = registry.viewports["desktop"]
    iphone = registry.viewports["iphone12-webkit"]
    assert desktop.size == (1440, 900) and desktop.browser == "chromium"
    assert iphone.size == (390, 844) and iphone.browser == "webkit"
    assert iphone.is_mobile and iphone.has_touch


def test_registry_file_matches_the_service_catalogue():
    expected = vbuild.render(vbuild.build())
    on_disk = vviews.REGISTRY_PATH.read_text(encoding="utf-8")
    assert on_disk == expected, "ty/visual_views.json is stale; run python -m tools.visual_regression.build_registry"


def test_seeds_are_deterministic_and_positive(registry):
    assert vfreeze.seed_from_id("hub") == vfreeze.seed_from_id("hub")
    assert vfreeze.seed_from_id("hub") != vfreeze.seed_from_id("ledger")
    seeds = [v.seed for v in registry.views]
    assert all(seed > 0 for seed in seeds)
    assert len(set(seeds)) == len(seeds), "a duplicated seed would freeze two views with the same randomness"


# --- still mode -----------------------------------------------------------


def test_still_url_preserves_query_and_fragment():
    assert vfreeze.build_still_url("/hub", seed=7) == "/hub?still=1&seed=7"
    assert (
        vfreeze.build_still_url("/beta#support", seed=7)
        == "/beta?still=1&seed=7#support"
    )
    assert (
        vfreeze.build_still_url("/listings?tab=guardian#top", seed=9)
        == "/listings?tab=guardian&still=1&seed=9#top"
    )


def test_still_url_rejects_relative_routes():
    with pytest.raises(ValueError):
        vfreeze.build_still_url("hub")


def test_still_init_script_contains_the_contract():
    script = vfreeze.still_init_script(seed=4242)
    assert "4242" in script
    assert "animation-play-state: paused !important" in script
    assert "transition: none !important" in script
    assert "window.__NS_STILL__" in script
    assert "performance.now = () => 0" in script
    assert str(vfreeze.FROZEN_EPOCH_MS) in script
    assert "mulberry32" in script or "Math.imul" in script


def test_frozen_clock_constant_is_2026_11_08T12Z():
    from datetime import datetime, timezone

    expected = int(datetime(2026, 11, 8, 12, tzinfo=timezone.utc).timestamp() * 1000)
    assert vfreeze.FROZEN_EPOCH_MS == expected
    assert vfreeze.FROZEN_EPOCH_ISO == "2026-11-08T12:00:00Z"


def test_every_view_builds_a_frozen_url(registry):
    for view in registry.views:
        url = vfreeze.build_still_url(view.route, view.still, view.seed)
        assert "still=1" in url and f"seed={view.seed}" in url
        assert vcapture.absolute_url("http://127.0.0.1:8101", url).startswith(
            "http://127.0.0.1:8101/"
        )


# --- diff: fixture proof ---------------------------------------------------


@pytest.mark.parametrize("item", FIXTURE_ITEMS, ids=[i["pair"] for i in FIXTURE_ITEMS])
def test_fixture_pair_classified_as_expected(item):
    result = vdiff.compare_files(
        FIXTURES / item["baseline"], FIXTURES / item["candidate"]
    )
    assert result.verdict == item["expected"], (
        f"{item['pair']}: expected {item['expected']}, got {result.verdict} "
        f"({result.pixel_diff_ratio:.4%} pixels, cluster {result.cluster_pixels})"
    )


def test_identical_images_pass():
    image = Image.new("RGB", (320, 200), (246, 243, 236))
    result = vdiff.compare_images(image, image.copy())
    assert result.passed
    assert result.changed_pixels == 0
    assert result.reason == "unchanged"


def test_moved_element_is_flagged_with_a_location():
    result = vdiff.compare_files(
        FIXTURES / "moved" / "baseline.png", FIXTURES / "moved" / "candidate.png"
    )
    assert result.verdict == "fail"
    assert result.reason == "structural_change"
    assert result.cluster_pixels > 1000
    assert result.bbox is not None and result.bbox[2] > 0 and result.bbox[3] > 0


def test_colour_change_is_flagged():
    result = vdiff.compare_files(
        FIXTURES / "recolour" / "baseline.png", FIXTURES / "recolour" / "candidate.png"
    )
    assert result.verdict == "fail"
    assert result.pixel_diff_ratio > vdiff.DEFAULT_CONFIG.max_pixel_ratio


def test_text_change_is_flagged_even_though_the_area_is_tiny():
    result = vdiff.compare_files(
        FIXTURES / "text" / "baseline.png", FIXTURES / "text" / "candidate.png"
    )
    assert result.verdict == "fail"
    assert result.pixel_diff_ratio < 0.01, "a text change must not need a big pixel ratio"
    assert result.cluster_pixels >= vdiff.DEFAULT_CONFIG.min_region_px


def test_half_pixel_antialias_drift_is_tolerated():
    result = vdiff.compare_files(
        FIXTURES / "antialias" / "baseline.png",
        FIXTURES / "antialias" / "candidate.png",
    )
    assert result.passed
    assert result.cluster_pixels < vdiff.DEFAULT_CONFIG.min_region_px


def test_size_mismatch_fails():
    a = Image.new("RGB", (100, 80), (255, 255, 255))
    b = Image.new("RGB", (120, 80), (255, 255, 255))
    result = vdiff.compare_images(a, b)
    assert result.verdict == "fail"
    assert result.reason == "size_mismatch"


def test_diff_is_deterministic():
    first = vdiff.compare_files(
        FIXTURES / "moved" / "baseline.png", FIXTURES / "moved" / "candidate.png"
    )
    second = vdiff.compare_files(
        FIXTURES / "moved" / "baseline.png", FIXTURES / "moved" / "candidate.png"
    )
    assert first.as_dict() == second.as_dict()


def test_self_test_classifies_every_fixture():
    ok, rows = vgate.run_self_test()
    assert ok, [r["pair"] for r in rows if not r["matched"]]
    assert len(rows) == 6
    assert {r["expected"] for r in rows} == {"pass", "fail"}


# --- baseline protocol ----------------------------------------------------


def _artifact(path: Path, view: str = "hub", viewport: str = "desktop") -> dict:
    return {"view": view, "viewport": viewport, "path": str(path)}


def test_update_without_scorecard_flag_is_refused(tmp_path):
    src = tmp_path / "capture.png"
    src.write_bytes((FIXTURES / "moved" / "baseline.png").read_bytes())
    with pytest.raises(vbaseline.BaselineRefused):
        vbaseline.update_baselines(
            [_artifact(src)], scorecard_passed=False, commit="abc123", root=tmp_path / "baselines"
        )
    assert not (tmp_path / "baselines" / "hub" / "desktop.png").exists()
    assert not (tmp_path / "baselines" / vbaseline.CHANGELOG_NAME).exists()


def test_update_with_scorecard_flag_writes_baseline_and_changelog(tmp_path):
    src = tmp_path / "capture.png"
    src.write_bytes((FIXTURES / "text" / "baseline.png").read_bytes())
    root = tmp_path / "baselines"
    entries = vbaseline.update_baselines(
        [_artifact(src)],
        scorecard_passed=True,
        commit="deadbeef",
        root=root,
        timestamp="2026-11-08T12:00:00Z",
    )
    assert len(entries) == 1
    entry = entries[0]
    for key in ("ts", "view", "viewport", "commit", "scorecard"):
        assert key in entry
    assert entry["view"] == "hub" and entry["viewport"] == "desktop"
    assert entry["commit"] == "deadbeef"
    assert entry["scorecard"]["passed"] is True
    assert vbaseline.baseline_path("hub", "desktop", root).is_file()
    changelog = json.loads((root / vbaseline.CHANGELOG_NAME).read_text(encoding="utf-8"))
    assert changelog["entries"][0]["baseline_sha256"] == entry["baseline_sha256"]


def test_update_records_the_baseline_it_replaced(tmp_path):
    root = tmp_path / "baselines"
    first = tmp_path / "v1.png"
    first.write_bytes((FIXTURES / "text" / "baseline.png").read_bytes())
    vbaseline.update_baselines(
        [_artifact(first)], scorecard_passed=True, commit="c1", root=root
    )
    first_sha = vbaseline.sha256_file(root / "hub" / "desktop.png")

    second = tmp_path / "v2.png"
    second.write_bytes((FIXTURES / "text" / "candidate.png").read_bytes())
    entries = vbaseline.update_baselines(
        [_artifact(second)],
        scorecard_passed=True,
        commit="c2",
        root=root,
        prior_verdicts={("hub", "desktop"): "fail"},
    )
    assert entries[0]["previous_baseline_sha256"] == first_sha
    assert entries[0]["prior_verdict"] == "fail"
    changelog = json.loads((root / vbaseline.CHANGELOG_NAME).read_text(encoding="utf-8"))
    assert len(changelog["entries"]) == 2


def test_update_without_artifacts_is_refused(tmp_path):
    with pytest.raises(vbaseline.BaselineRefused):
        vbaseline.update_baselines([], scorecard_passed=True, commit="c1", root=tmp_path)


def test_scorecard_file_reporting_failure_is_refused(tmp_path):
    src = tmp_path / "capture.png"
    src.write_bytes((FIXTURES / "text" / "baseline.png").read_bytes())
    with pytest.raises(vbaseline.BaselineRefused):
        vbaseline.update_baselines(
            [_artifact(src)],
            scorecard_passed=True,
            scorecard={"passed": False, "at_bar": "12/20"},
            commit="c1",
            root=tmp_path / "baselines",
        )


# --- capture refusals (no browser is ever launched here) -------------------


def test_playwright_is_not_imported_by_the_offline_surface():
    vcapture.ensure_loopback("http://127.0.0.1:8101")
    assert "playwright.sync_api" not in sys.modules


def test_non_loopback_base_url_is_refused():
    with pytest.raises(vcapture.CaptureError):
        vcapture.ensure_loopback("https://northstar.example.com")


def test_absolute_url_keeps_base_path_query_and_fragment():
    assert (
        vcapture.absolute_url("http://127.0.0.1:8101/ui/", "/hub?still=1&seed=5#top")
        == "http://127.0.0.1:8101/ui/hub?still=1&seed=5#top"
    )


def test_gate_refuses_without_base_url(capsys):
    assert vgate.run([]) == vgate.EXIT_REFUSED
    assert "--base-url is required" in capsys.readouterr().err


def test_gate_refuses_unreachable_app_without_launching_a_browser(monkeypatch, capsys, tmp_path):
    def _boom(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("a browser must not be launched for an unreachable app")

    monkeypatch.setattr(vgate, "probe_base_url", lambda *a, **k: (False, "ConnectionRefusedError: refused"))
    monkeypatch.setattr(vgate, "capture_views", _boom)
    code = vgate.run(["--base-url", "http://127.0.0.1:9", "--out", str(tmp_path)])
    assert code == vgate.EXIT_REFUSED
    assert "not reachable" in capsys.readouterr().err


def test_gate_refuses_non_loopback_before_probing(monkeypatch, capsys):
    def _boom(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("no probe for a non-local host")

    monkeypatch.setattr(vgate, "probe_base_url", _boom)
    code = vgate.run(["--base-url", "https://example.com"])
    assert code == vgate.EXIT_REFUSED
    assert "non-loopback" in capsys.readouterr().err


def test_uniform_screenshot_is_rejected(tmp_path):
    blank = tmp_path / "blank.png"
    Image.new("RGB", (64, 64), (255, 255, 255)).save(blank)
    ok, why = vcapture._screenshot_ok(blank)
    assert not ok and "uniform" in why


def _fake_capture(tmp_path: Path, view: str = "hub", viewport: str = "desktop"):
    shot = tmp_path / "artifacts" / view / f"{viewport}.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    shot.write_bytes((FIXTURES / "identical" / "baseline.png").read_bytes())
    return [
        vcapture.CaptureRecord(
            view=view,
            viewport=viewport,
            path=shot,
            url=f"http://127.0.0.1:8101/{view}?still=1&seed=1",
            sha256=vbaseline.sha256_file(shot),
            bytes=shot.stat().st_size,
            text_chars=420,
            still={"still": True, "seed": 1, "frozenAt": vfreeze.FROZEN_EPOCH_MS},
        )
    ]


def test_gate_cli_refuses_update_baseline_without_scorecard_flag(monkeypatch, capsys, tmp_path):
    """The wiring is tested end-to-end with the browser replaced by a fixture."""
    monkeypatch.setattr(vgate, "probe_base_url", lambda *a, **k: (True, "HTTP 200"))
    monkeypatch.setattr(
        vgate, "capture_views", lambda *a, **k: _fake_capture(tmp_path)
    )
    code = vgate.run(
        [
            "--base-url",
            "http://127.0.0.1:8101",
            "--views",
            "hub",
            "--viewports",
            "desktop",
            "--out",
            str(tmp_path / "artifacts"),
            "--baselines",
            str(tmp_path / "baselines"),
            "--update-baseline",
        ]
    )
    assert code == vgate.EXIT_REFUSED
    assert "--scorecard-passed is required" in capsys.readouterr().err
    assert not (tmp_path / "baselines" / "hub" / "desktop.png").exists()
    assert not (tmp_path / "baselines" / vbaseline.CHANGELOG_NAME).exists()


def test_gate_cli_update_with_both_flags_promotes_and_logs(monkeypatch, tmp_path):
    monkeypatch.setattr(vgate, "probe_base_url", lambda *a, **k: (True, "HTTP 200"))
    monkeypatch.setattr(
        vgate, "capture_views", lambda *a, **k: _fake_capture(tmp_path)
    )
    code = vgate.run(
        [
            "--base-url",
            "http://127.0.0.1:8101",
            "--views",
            "hub",
            "--viewports",
            "desktop",
            "--out",
            str(tmp_path / "artifacts"),
            "--baselines",
            str(tmp_path / "baselines"),
            "--update-baseline",
            "--scorecard-passed",
        ]
    )
    assert code == vgate.EXIT_PASS
    baseline_file = tmp_path / "baselines" / "hub" / "desktop.png"
    assert baseline_file.is_file()
    changelog = json.loads(
        (tmp_path / "baselines" / vbaseline.CHANGELOG_NAME).read_text(encoding="utf-8")
    )
    assert changelog["entries"][-1]["scorecard"]["passed"] is True
    assert changelog["entries"][-1]["viewport"] == "desktop"
    assert changelog["entries"][-1]["commit"] == vgate.git_commit()


# --- evaluation / exit codes ----------------------------------------------


def test_missing_baseline_is_not_a_pass(tmp_path):
    src = tmp_path / "capture.png"
    src.write_bytes((FIXTURES / "text" / "baseline.png").read_bytes())
    results = vgate.evaluate_artifacts([_artifact(src)], baselines_root=tmp_path / "empty")
    assert [r.verdict for r in results] == ["no_baseline"]
    assert vgate.summarise(results)["verdict"] == "no_baseline"


def test_matching_baseline_passes_and_changed_baseline_fails(tmp_path):
    root = tmp_path / "baselines"
    baseline_file = vbaseline.baseline_path("hub", "desktop", root)
    baseline_file.parent.mkdir(parents=True)
    baseline_file.write_bytes((FIXTURES / "identical" / "baseline.png").read_bytes())

    same = tmp_path / "same.png"
    same.write_bytes((FIXTURES / "identical" / "candidate.png").read_bytes())
    assert vgate.evaluate_artifacts([_artifact(same)], baselines_root=root)[0].verdict == "pass"

    changed = tmp_path / "changed.png"
    changed.write_bytes((FIXTURES / "text" / "candidate.png").read_bytes())
    result = vgate.evaluate_artifacts([_artifact(changed)], baselines_root=root)[0]
    assert result.verdict == "fail"
    assert result.metrics["bbox"] is not None
