import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from print_prep import face_pixels


def test_degenerate_quad_is_refused():
    with pytest.raises(ValueError):
        face_pixels([[1, 1], [1, 1], [1, 1], [1, 1]])
