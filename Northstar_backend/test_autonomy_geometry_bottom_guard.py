import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geometry_profiles import bottle


def test_label_cannot_run_past_the_bottom_seam():
    with pytest.raises(ValueError):
        bottle(diameter=60, height=200, label_height=10, label_top_offset=190)
