from pathlib import Path
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import surface_measure as sm


def test_wrap_fraction_outside_the_visible_arc_is_refused():
    with pytest.raises(ValueError):
        sm.measure_surface(Image.new("RGB", (128, 128), (230, 230, 230)),
                           "bottle", wrap_fraction=0)
    with pytest.raises(ValueError):
        sm.measure_surface(Image.new("RGB", (128, 128), (230, 230, 230)),
                           "bottle", wrap_fraction=1.5)
