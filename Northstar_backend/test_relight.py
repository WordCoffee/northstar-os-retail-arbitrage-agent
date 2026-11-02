"""Relight lane: the graph is data, and a noise decode is refused, not shipped."""
from __future__ import annotations

import io
import random
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import relight  # noqa: E402


def _smooth() -> bytes:
    im = Image.new("RGB", (128, 128))
    for y in range(128):
        for x in range(128):
            im.putpixel((x, y), (x * 2 % 255, y * 2 % 255, 120))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _noise() -> bytes:
    rnd = random.Random(7)
    im = Image.new("RGB", (128, 128))
    for y in range(128):
        for x in range(128):
            im.putpixel((x, y), (rnd.randrange(256), rnd.randrange(256), rnd.randrange(256)))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def test_the_graph_feeds_the_reference_into_ic_light_and_samples_its_latent():
    graph = relight.build_graph("src.png", width=768, height=768)
    assert graph["4"]["inputs"]["unet_name"] == relight.IC_MODEL
    assert graph["5"]["inputs"]["clip_name"] == relight.CLIP_FILE
    assert graph["8"]["inputs"]["ic_model"] == ["4", 0]
    assert graph["8"]["inputs"]["c_concat"] == ["3", 0]
    assert graph["9"]["inputs"]["latent_image"] == ["3", 0]
    assert graph["10"]["inputs"]["vae_name"] == relight.VAE_FILE


def test_the_noise_metric_separates_a_render_from_garbage():
    assert relight.noise_metric(_smooth()) < relight.NOISE_LIMIT
    assert relight.noise_metric(_noise()) > relight.NOISE_LIMIT


def test_a_noise_decode_is_refused_with_the_reason():
    with pytest.raises(relight.RelightUnavailable) as caught:
        relight.assert_usable(_noise())
    assert "relight_output_is_noise" in str(caught.value)


def test_a_real_looking_output_passes_the_guard():
    assert relight.assert_usable(_smooth()) < relight.NOISE_LIMIT
