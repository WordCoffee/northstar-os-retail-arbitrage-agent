"""Deterministic sizing tests for the local render engine.

These encode the two acceptance failures of 2026-10-27/28:

* T3 (Amazon MAIN, 2000x2000) and T5 (A+ Premium banner, 1464x600) were
  impossible because ``_fit_box`` hard-capped the long edge at 1216 px.
* T7 (5 second clip) was impossible because ``generate_video`` hardcoded 49/97
  frames (2.04 s / 4.04 s) with no duration input.

No ComfyUI, no GPU and no network is touched here: the sizing maths is pure.
"""

from __future__ import annotations

import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image  # noqa: E402

import studio_generation as sg  # noqa: E402


class FitBoxTests(unittest.TestCase):
    def test_amazon_main_2000_is_not_downscaled(self):
        self.assertEqual(sg._fit_box(2000, 2000), (2000, 2000))

    def test_a_plus_banner_keeps_its_aspect_and_only_snaps_to_the_grid(self):
        w, h = sg._fit_box(1464, 600)
        self.assertEqual((w, h), (1472, 608))
        self.assertLessEqual(abs(w - 1464), 16)
        self.assertLessEqual(abs(h - 600), 16)

    def test_portrait_product_shot_is_untouched(self):
        self.assertEqual(sg._fit_box(896, 1216), (896, 1216))

    def test_oversize_request_is_scaled_on_one_factor(self):
        w, h = sg._fit_box(4000, 2000)
        self.assertEqual(max(w, h), sg.MAX_EDGE_PX)
        self.assertAlmostEqual(w / h, 2.0, places=2)

    def test_max_edge_is_configurable_and_reported(self):
        self.assertGreaterEqual(sg.MAX_EDGE_PX, 2000,
                                "the ceiling must allow a 2000 px MAIN image")

    def test_rounding_never_breaks_the_cap(self):
        w, h = sg._fit_box(4096, 4096)
        self.assertLessEqual(max(w, h), sg.MAX_EDGE_PX)


class ExactSizeTests(unittest.TestCase):
    def _png(self, w, h):
        buf = io.BytesIO()
        Image.new("RGB", (w, h), (240, 240, 240)).save(buf, format="PNG")
        return buf.getvalue()

    def test_exact_size_pass_delivers_the_spec_dimensions(self):
        data = sg._exact_size_png(self._png(1472, 608), 1464, 600)
        with Image.open(io.BytesIO(data)) as im:
            self.assertEqual(im.size, (1464, 600))

    def test_exact_size_pass_is_a_no_op_when_already_exact(self):
        original = self._png(2000, 2000)
        self.assertIs(sg._exact_size_png(original, 2000, 2000), original)


class VideoDurationTests(unittest.TestCase):
    def test_five_seconds_is_reachable(self):
        frames = sg._frames_for_duration(5.0, 49)
        self.assertEqual((frames - 1) % 4, 0, "Wan latent needs 4n+1 frames")
        self.assertGreaterEqual(frames / 24.0, 5.0)
        self.assertEqual(frames, 121)

    def test_no_duration_keeps_the_tier_default(self):
        self.assertEqual(sg._frames_for_duration(None, 49), 49)
        self.assertEqual(sg._frames_for_duration(None, 97), 97)
        self.assertEqual(sg._frames_for_duration("", 49), 49)

    def test_zero_or_negative_duration_is_refused(self):
        with self.assertRaises(ValueError):
            sg._frames_for_duration(0, 49)
        with self.assertRaises(ValueError):
            sg._frames_for_duration(-2, 49)


if __name__ == "__main__":
    unittest.main()
