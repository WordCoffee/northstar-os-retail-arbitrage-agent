"""Module hygiene: a second definition must not silently override the first.

`studio_generation.py` carried five duplicated Phase R functions; the later copy
overrode the first, so a hardened `system_ram_free_mb`/`stop_for_render` was not
the code that ran, and an unconditional `import psutil` defeated the file's own
optional-psutil fallback. A merge that repeats a block is invisible at runtime -
the module imports and the tests that never touch the old copy pass. This test
reads the AST, which is the only place the override is visible.
"""
from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent
GUARDED = (
    "studio_generation.py",
    "mockup_compositor.py",
    "product_picture.py",
    "mogra_label_art.py",
    "mockup_quality.py",
    "conftest.py",
    "design_studio_api.py",
)


@pytest.mark.parametrize("name", GUARDED)
def test_no_duplicate_top_level_functions(name):
    tree = ast.parse((BACKEND / name).read_text(encoding="utf-8"))
    seen = defaultdict(list)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            seen[node.name].append(node.lineno)
    duplicates = {k: v for k, v in seen.items() if len(v) > 1}
    assert not duplicates, (
        f"{name} defines the same top-level name more than once; the later copy "
        f"silently wins: {duplicates}")


def test_studio_generation_keeps_the_optional_psutil_fallback():
    src = (BACKEND / "studio_generation.py").read_text(encoding="utf-8")
    assert "_psutil = None" in src, "the optional-psutil fallback was removed"
    assert src.count("import psutil as _psutil") == 1, (
        "a second unconditional psutil import would defeat the fallback")


def test_the_conftest_collection_hook_does_both_jobs(monkeypatch):
    """A duplicate pytest hook silently replaced the credential scrub."""
    import conftest  # the live plugin module pytest loaded

    calls = []
    monkeypatch.setattr(conftest, "_scrub_credential_env",
                        lambda: calls.append("scrub") or {})
    monkeypatch.setattr(conftest, "_restore_generated",
                        lambda: calls.append("restore"))
    conftest.pytest_collection_finish(None)
    assert calls == ["scrub", "restore"]
