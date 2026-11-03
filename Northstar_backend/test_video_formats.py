"""Video placement contracts and the duration planner.

A still needs a canvas; a video also needs a duration window, a frame rate, a
container, a size cap and the safe areas the platform's own UI covers. Without
those the lane renders a 2-second 16 fps WEBM and calls it a TikTok - which is
exactly what the route used to allow.

The other half of these tests is honesty: an unverified preset (Amazon's, because
reading Amazon specs is a standing gate) must be renderable but must report
`compliance.verified = False`, so no surface can claim a compliance it never
checked.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import video_formats as vf  # noqa: E402


def test_every_platform_has_the_fields_a_render_needs():
    for row in vf.describe():
        for key in ("id", "label", "aspect", "width", "height", "fps",
                    "min_seconds", "max_seconds", "container", "max_bytes",
                    "safe_zones", "source", "verified"):
            assert key in row, (row.get("id"), key)
        assert row["width"] % 2 == 0 and row["height"] % 2 == 0


def test_plan_rounds_frames_to_the_wan_step_and_covers_the_window():
    p = vf.plan("shorts", 4)
    assert (p["frames_per_clip"] - 1) % vf.FRAME_STEP == 0
    # the PLAN covers the window once the clips are stitched together
    assert p["total_frames"] / p["fps"] >= 4 - (1 / p["fps"])


def test_a_window_longer_than_one_sampler_call_plans_stitching():
    p = vf.plan("shorts", 30)
    assert p["clips"] > 1 and p["stitch_required"] is True
    assert p["frames_per_clip"] <= p["max_frames_per_clip"]
    assert p["total_frames"] >= 30 * p["fps"] - p["fps"]


def test_a_short_window_is_one_clip():
    p = vf.plan("shorts", 2)
    assert p["clips"] == 1 and p["stitch_required"] is False


def test_out_of_window_durations_are_refused_with_a_reason():
    with pytest.raises(ValueError) as err:
        vf.plan("shorts", 600)
    assert "video_duration_out_of_range" in str(err.value)
    with pytest.raises(ValueError) as err2:
        vf.plan("tiktok", 1)
    assert "video_duration_out_of_range" in str(err2.value)


def test_unknown_platform_is_refused():
    with pytest.raises(ValueError) as err:
        vf.plan("myspace", 10)
    assert "video_format_unknown" in str(err.value)


def test_a_canvas_that_contradicts_the_platform_is_refused():
    with pytest.raises(ValueError) as err:
        vf.plan("tiktok", 10, width=1920, height=1080)
    assert "video_canvas_conflict" in str(err.value)


def test_amazon_presets_are_renderable_but_never_claim_compliance():
    p = vf.plan("amazon-ad-16x9", 15)
    assert p["compliance"]["verified"] is False
    assert "gate" in p["compliance"]["source"].lower()
    # and a mainstream platform, which WAS checked, says so
    assert vf.plan("shorts", 15)["compliance"]["verified"] is True


def test_ad_lengths_follow_the_platform_window():
    assert vf.ad_lengths("amazon-ad-16x9") == [15, 30]
    assert vf.ad_lengths("shorts") == [15, 30]
