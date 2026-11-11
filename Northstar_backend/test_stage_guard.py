"""A pipeline stage may decline. It may not crash quietly.

Two bugs in one day had this shape: an `except Exception` turned a programmer error into a "stage
refused" record, and the run carried on with a degraded artefact that scored as if nothing had
happened. A missing `import numpy` looked like a layout that declined to run, through two scoring
rounds.

2026-11-11: the rule was tightened. Tolerance by exception *type* is how a bug gets a refusal's
clothing — a numpy shape error is a `ValueError`, and a `KeyError` wrapped in a `RuntimeError` looked
like a refusal. The guard now recognises exactly one type, `StageRefused`; everything else, including
`ValueError` and `RuntimeError`, aborts. A step that legitimately signals "cannot" with those two is
converted at a **named call** with `declined()`.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
for _extra in (str(ROOT), str(ROOT / "tools")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

from seller_tester.stage_guard import (  # noqa: E402
    StageFailed,
    StageRefused,
    declined,
    stage,
)


# ---------------------------------------------------------------- the guard itself
def test_a_typed_refusal_is_recorded_and_the_run_continues():
    record = {}
    with stage("layout", record) as mark:
        raise StageRefused("the cutout is empty")
    assert mark["refused"] is True
    assert record["layout"]["refused"] is True
    assert record["layout"]["kind"] == "refused"
    assert "cutout is empty" in record["layout"]["reason"]


def test_a_value_error_is_now_a_bug_not_a_refusal():
    """The change: a bare ValueError used to be swallowed. It is not a declared refusal."""
    record = {}
    with pytest.raises(StageFailed) as caught:
        with stage("layout", record):
            raise ValueError("could not broadcast input array")
    assert "ValueError" in str(caught.value)
    assert "bug in the pipeline" in str(caught.value)
    assert record["layout"]["refused"] is False
    assert "error" in record["layout"]


def test_a_runtime_error_is_now_a_bug_too():
    record = {}
    with pytest.raises(StageFailed):
        with stage("render", record):
            raise RuntimeError("the lane stopped")
    assert record["render"]["kind"] == "error"


@pytest.mark.parametrize("error", [NameError("np is not defined"),
                                   TypeError("bad argument"),
                                   AttributeError("no attribute"),
                                   ImportError("no module"),
                                   KeyError("missing")])
def test_any_unexpected_exception_aborts_the_run_loudly(error):
    record = {}
    with pytest.raises(StageFailed) as caught:
        with stage("compose", record):
            raise error
    message = str(caught.value)
    assert "compose" in message
    assert type(error).__name__ in message
    assert "bug in the pipeline" in message
    # and the record says error, not refused: the artefact is not publishable
    assert record["compose"]["refused"] is False
    assert "error" in record["compose"]


def test_a_stage_that_succeeds_leaves_no_refusal():
    record = {}
    with stage("layout", record) as mark:
        mark["callouts"] = 3
    assert record["layout"]["refused"] is False
    assert "error" not in record["layout"]


# ---------------------------------------------------------------- the conversion helper
def test_declined_turns_a_value_error_into_a_named_refusal():
    def fit_aspect():
        raise ValueError("degenerate product box")

    with pytest.raises(StageRefused) as caught:
        declined("fit_aspect", fit_aspect)
    assert "fit_aspect declined" in str(caught.value)
    assert "ValueError" in str(caught.value)
    assert isinstance(caught.value.__cause__, ValueError)


def test_declined_turns_a_runtime_error_into_a_refusal_too():
    with pytest.raises(StageRefused):
        declined("panel_warp", lambda: (_ for _ in ()).throw(RuntimeError("quad has no area")))


def test_declined_passes_a_successful_call_straight_through():
    assert declined("add", lambda a, b=0: a + b, 2, b=3) == 5


def test_declined_does_not_swallow_an_unexpected_error():
    def broken():
        raise KeyError("missing")

    with pytest.raises(KeyError):
        declined("broken", broken)


# ---------------------------------------------------------------- the generators honour it
def test_the_generator_turns_an_unexpected_compose_error_into_a_stop():
    """The regression: a NameError inside the compose step must stop the run, not fall back."""
    import inspect

    from seller_tester import generators

    source = inspect.getsource(generators.CompositeGenerator._generate_cut_and_compose)
    assert "StageFailed" in source, "the compose stage must raise loud on a bug"
    assert "except Exception" in source
    # the only refusal it may record is the typed one
    assert "except StageRefused" in source
    assert "except (ValueError, RuntimeError)" not in source


def test_the_layout_stage_turns_an_unexpected_error_into_a_stop():
    import inspect

    from seller_tester import generators

    source = inspect.getsource(generators.CompositeGenerator._layout_stage)
    assert "StageFailed" in source
    assert "except StageRefused" in source
    assert "except (ValueError, RuntimeError)" not in source
    # the steps allowed to say "cannot" are named at the call, not caught by type
    assert 'declined("fit_aspect"' in source


# ---------------------------------------------------------------- behaviour, not just source
def _scene_bytes(size=(320, 320), colour=(214, 208, 196)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, colour).save(buffer, format="PNG")
    return buffer.getvalue()


def _alpha_from_fill(rgb):
    """A cutout that claims the whole frame, so the compose path has a subject."""
    import numpy as np

    class Cut:
        pass

    cut = Cut()
    height, width = rgb.shape[:2]
    cut.rgb = np.asarray(rgb).copy()
    cut.alpha = np.full((height, width), 255, dtype=np.uint8)
    return cut


def _tolerant_brief(brief_id: str = "GUARD-1") -> dict:
    return {
        "id": brief_id,
        "category": "supplement_pouch",
        "situation": "lifestyle",
        "difficulty": 1,
        "source_mode": "prompt_only",
        "fidelity": "tolerant",
        "placement": {"scale": 0.6, "anchor": [0.5, 0.6]},
        "constraints": {
            "dimensions": {"min_width": 200, "min_height": 200},
            "aspect": {"ratio": 1.0, "tolerance": 0.02},
            "background": {"value": 255, "tolerance": 6, "mode": "free"},
            "fill_pct": {"min": 5, "max": 95},
            "text_rule": "allowed",
            "matte": {"mode": "any"},
            "file_size": {"min_bytes": 100, "max_bytes": 12000000},
        },
    }


def _generator(tmp_path: Path, **kwargs):
    from seller_tester.generators import CompositeGenerator

    return CompositeGenerator(
        renderer=lambda b, m="scene", inside_lane=None: {
            "bytes": _scene_bytes(), "source": "generated", "prompt": "full",
            "image_path": None, "lane": {"stopped": {"ok": True}}},
        out_dir=tmp_path / "out", repo_root=tmp_path, **kwargs)


def test_a_value_error_from_an_undeclared_step_aborts_the_run(tmp_path: Path):
    """`_resize_png` is not a declared step. A ValueError from it is a bug, not a refusal."""
    from seller_tester import generators

    brief = _tolerant_brief()
    generator = _generator(tmp_path, cutout_fn=_alpha_from_fill)

    def boom(*_args, **_kwargs):
        raise ValueError("could not broadcast input array from shape (320,320,3)")

    original = generators._resize_png
    generators._resize_png = boom
    try:
        with pytest.raises(StageFailed) as caught:
            generator.generate(brief)
    finally:
        generators._resize_png = original
    assert "ValueError" in str(caught.value)


def test_a_declared_cutout_refusal_is_recorded_and_the_plate_is_kept(tmp_path: Path):
    """A cutout that cannot run is a business outcome: typed, recorded, and not an abort."""
    brief = _tolerant_brief("GUARD-2")

    def refuse_cut(_rgb, method=None):
        raise ValueError("the cutout is empty")

    generator = _generator(tmp_path, cutout_fn=refuse_cut)
    path = generator.generate(brief)
    record = generator.record_for(brief["id"])
    assert path.is_file()
    assert record["cut_from_generation"]["method"] == "refused"
    assert "cutout is empty" in record["cut_from_generation"]["reason"]
