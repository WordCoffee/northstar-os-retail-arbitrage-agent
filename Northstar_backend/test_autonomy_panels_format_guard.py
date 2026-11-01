import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from specialists.panels import validate_panels


def test_an_unknown_package_format_is_not_print_ready():
    out = validate_panels({
        "title": "Test product", "weight": "NET WT 1 OZ",
        "ingredients": ["one ingredient"], "company": "Test Co",
        "address": "1 Test Way", "country_of_origin": "USA",
        "format": "sachet",
    })
    assert out["ready_for_print"] is False
    assert any("format" in w for w in out["warnings"])
