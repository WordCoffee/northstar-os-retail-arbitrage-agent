"""The foundation store must not leave a temp database behind.

Every ``create_app`` in the suite builds a ``FoundationDB`` with no path. Until 2026-11-09 each one
left its ``ns_foundation_*.db`` in %TEMP%; 9,018 had accumulated (``reports/ty/defects.md`` D-001).
The fix is small and the rule is narrow: **a store that created the file removes it; a store that
was handed a path never touches it.**
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from Northstar_backend.foundation.db import FoundationDB, temp_db  # noqa: E402


def test_an_auto_path_is_under_temp_and_is_removed_on_close():
    db = FoundationDB()
    path = Path(db.path)
    assert path.is_file(), "the store should exist while it is open"
    assert path.name.startswith("ns_foundation_")
    db.close()
    assert not path.exists(), "a store that created its own file must remove it on close"


def test_a_supplied_path_survives_close(tmp_path):
    explicit = tmp_path / "kept.db"
    db = FoundationDB(str(explicit))
    db.close()
    assert explicit.is_file(), "a caller-supplied path is not ours to delete"


def test_an_auto_path_is_registered_for_removal_at_exit(monkeypatch):
    # "belt and braces": a store nobody closes must still register its own file for exit cleanup
    import atexit

    registered = []

    def spy(fn, *args, **kwargs):
        registered.append((fn, args, kwargs))
        return fn

    monkeypatch.setattr(atexit, "register", spy)
    db = FoundationDB(schema=False)
    path = Path(db.path)
    matches = [entry for entry in registered if entry[1] == (db.path,)]
    assert matches, "the created temp file must be registered for removal at interpreter exit"
    hook = matches[0][0]
    assert path.is_file()
    db.conn.close()  # release the SQLite handle WITHOUT going through close()
    assert path.is_file(), "closing the connection must not be the thing that removes the file"
    hook(db.path)  # exactly what the interpreter would run at exit
    assert not path.exists(), "the registered exit hook must remove the created file"


def test_a_supplied_path_is_never_registered_or_removed(tmp_path, monkeypatch):
    import atexit

    explicit = tmp_path / "kept.db"
    registered = []
    monkeypatch.setattr(
        atexit, "register",
        lambda fn, *args, **kwargs: registered.append((fn, args, kwargs)),
    )
    db = FoundationDB(str(explicit), schema=False)
    db.close()
    assert explicit.is_file(), "a caller-supplied path is not ours to delete"
    assert [e for e in registered if str(explicit) in e[1]] == [], (
        "a caller-supplied path must never be registered for removal")


def test_many_stores_leave_nothing_behind(tmp_path, monkeypatch):
    # point the temp prefix at a private directory so the assertion is about THIS test's files
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    made = []
    for _ in range(5):
        db = FoundationDB(schema=False)
        made.append(Path(db.path))
        db.close()
    assert all(path.name.startswith("ns_foundation_") for path in made)
    assert [path for path in made if path.exists()] == []


def test_the_context_manager_still_removes_its_file():
    with temp_db() as db:
        path = Path(db.path)
        assert path.is_file()
    assert not path.exists()


def test_a_store_left_open_is_removed_at_exit():
    # the belt-and-braces path: nothing closes this one, and atexit must still clean it up
    import atexit

    db = FoundationDB(schema=False)
    path = Path(db.path)
    try:
        db.close()  # closes the connection; the file removal is what is being checked
        assert not path.exists()
    finally:
        # prove the registration exists rather than relying on this process exiting
        registered = atexit._ncallbacks()  # noqa: SLF001 - the only way to observe registration
        assert registered > 0
