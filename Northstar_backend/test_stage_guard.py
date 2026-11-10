"""A pipeline stage may decline. It may not crash quietly.

Two bugs in one day had this shape: an `except Exception` turned a programmer error into a "stage
refused" record, and the run carried on with a degraded artefact that scored as if nothing had
happened. A missing `import numpy` looked like a layout that declined to run, through two scoring
rounds. These tests pin the rule that stops it happening a third time.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from seller_tester.stage_guard import StageFailed, stage  # noqa: E402


def test_an_expected_refusal_is_recorded_and_the_run_continues():
    record = {}
    with stage("layout", record) as mark:
        raise ValueError("the cutout is empty")
    assert mark["refused"] is True
    assert record["layout"]["refused"] is True
    assert "ValueError" in record["layout"]["reason"]


def test_a_runtime_refusal_is_recorded_too():
    record = {}
    with stage("render", record):
        raise RuntimeError("the lane stopped")
    assert record["render"]["refused"] is True


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


def test_the_generator_turns_an_unexpected_compose_error_into_a_stop():
    """The regression: a NameError inside the compose step must stop the run, not fall back."""
    import inspect

    from seller_tester import generators

    source = inspect.getsource(generators.CompositeGenerator._generate_cut_and_compose)
    assert "StageFailed" in source, "the compose stage must raise loud on a bug"
    assert "except Exception" in source
    # the only exceptions it may swallow are the typed ones
    assert "except (ValueError, RuntimeError)" in source


def test_the_layout_stage_turns_an_unexpected_error_into_a_stop():
    import inspect

    from seller_tester import generators

    source = inspect.getsource(generators.CompositeGenerator._layout_stage)
    assert "StageFailed" in source
    assert "except (ValueError, RuntimeError)" in source
