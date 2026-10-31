"""Hardware guardrail arithmetic (Phase II telemetry enforcement)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hardware_guard import decide_batch, snapshot, DEFAULT_MAX_VRAM_RATIO, DEFAULT_MAX_TEMP_C


def test_comfortable_headroom_runs_the_full_batch():
    batch, reason = decide_batch(4, 0.40, 55.0)
    assert batch == 4
    assert "4 of 4" in reason


def test_unknown_vram_refuses_rather_than_guesses():
    batch, reason = decide_batch(4, None, 55.0)
    assert batch == 0
    assert reason == "vram_unknown"


def test_exhausted_vram_refuses():
    batch, reason = decide_batch(4, 1.0, 55.0)
    assert batch == 0
    assert reason.startswith("vram_exhausted")


def test_thermal_ceiling_refuses():
    batch, reason = decide_batch(4, 0.40, DEFAULT_MAX_TEMP_C)
    assert batch == 0
    assert reason.startswith("thermal_stop")


def test_batch_steps_down_as_the_budget_tightens():
    # 0.86 ratio: 0.86 + 4*0.01 = 0.90 (over), 0.86 + 1*0.01 = 0.87 (under)
    batch, reason = decide_batch(4, 0.86, 60.0)
    assert batch == 1
    assert "of 4" in reason


def test_over_the_line_degrades_to_a_single_item():
    batch, reason = decide_batch(4, 0.90, 60.0)
    assert batch == 1
    assert "single item" in reason


def test_near_thermal_ceiling_is_reported_but_allowed():
    batch, reason = decide_batch(2, 0.30, DEFAULT_MAX_TEMP_C - 1)
    assert batch == 2
    assert "near thermal ceiling" in reason


def test_zero_request_is_zero():
    assert decide_batch(0, 0.2, 40.0)[0] == 0


def test_threshold_is_the_agreed_number():
    assert DEFAULT_MAX_VRAM_RATIO == 0.88


def test_snapshot_never_raises_and_reports_ratio():
    hw = snapshot()
    # Either a real reading, or an honest failure - never an exception.
    assert hw.ok in (True, False)
    if hw.ok:
        assert 0.0 <= hw.ratio <= 1.0
        assert hw.temp_c is not None
    else:
        assert hw.reason


@pytest.mark.parametrize("desired,ratio,temp", [(1, 0.1, 40.0), (8, 0.5, 70.0), (3, 0.87, 84.0)])
def test_decisions_are_total(desired, ratio, temp):
    batch, reason = decide_batch(desired, ratio, temp)
    assert isinstance(batch, int)
    assert 0 <= batch <= desired
    assert isinstance(reason, str) and reason
