import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
ROOT = Path(__file__).resolve().parents[1]


def _imported(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[-1] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(a.name for a in node.names)
    return names


def test_new_creative_modules_do_not_import_unused_names():
    assert "Sequence" not in _imported(ROOT / "Northstar_backend" / "package_art.py")
    assert "Tuple" not in _imported(ROOT / "Northstar_backend" / "package_art.py")
    assert "uuid" not in _imported(ROOT / "Northstar_backend" / "package_pipeline.py")
