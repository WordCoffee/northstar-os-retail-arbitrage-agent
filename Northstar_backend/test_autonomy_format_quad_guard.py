from io import BytesIO
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import format_compositors as fc


def _png(img):
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_bottle_and_tube_reject_a_non_quad():
    plate = _png(Image.new("RGB", (400, 500), (205, 180, 150)))
    label = _png(Image.new("RGB", (240, 300), (250, 248, 240)))
    bad = [[80, 100], [320, 100], [320, 400]]
    with pytest.raises(ValueError):
        fc.bottle_composite(plate, label, bad)
    with pytest.raises(ValueError):
        fc.tube_composite(plate, label, bad)
