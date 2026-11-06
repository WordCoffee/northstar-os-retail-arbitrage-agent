"""The token meter has to be honest, because a dishonest number disables a cap.

The daily cap is 3,000,000 tokens and was unenforceable while nothing measured
it. The failure mode that matters here is not a wrong number by 20% -- it is a
*zero* or an exception standing in for "unknown", because a cap that reads 0
never stops anything.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import token_meter as m  # noqa: E402


# --------------------------------------------------------------- text estimate
def test_text_estimate_is_deterministic():
    text = "the same input must always give the same number"
    assert m.estimate_text(text) == m.estimate_text(text)
    assert m.estimate_text(text) == m.estimate_text(str(text))


def test_text_estimate_is_chars_over_four_rounded_up():
    # 8 chars -> exactly 2 tokens; 9 chars -> 3 (rounded up, never down)
    assert m.estimate_text("abcdefgh") == 2
    assert m.estimate_text("abcdefghi") == 3
    assert m.estimate_text("") == 0
    assert m.estimate_text(None) == 0
    long_text = "x" * 4_000
    assert m.estimate_text(long_text) == 1_000
    # monotone: more text never estimates fewer tokens
    assert m.estimate_text("x" * 4) <= m.estimate_text(long_text)


# ------------------------------------------------------- missing store honesty
def test_a_missing_store_is_unavailable_never_zero(tmp_path, monkeypatch):
    missing = tmp_path / "nope" / "opencode.db"
    monkeypatch.setattr(m, "DB_PATH", missing)

    got = m.estimate_session("ses_does_not_exist")

    assert got["tokens"] is None, "0 would silently defeat the cap"
    assert got["tokens"] != 0
    assert got["source"] == "unavailable"
    assert got["session_id"] == "ses_does_not_exist"
    # a read-only meter must not create the store it measures
    assert not missing.exists()


def test_an_unreadable_store_path_does_not_raise(tmp_path, monkeypatch):
    # a directory where a file is expected: still an answer, not a traceback
    bogus = tmp_path / "store.db"
    bogus.mkdir()
    monkeypatch.setattr(m, "DB_PATH", bogus)
    got = m.estimate_session("ses_x")
    assert got["tokens"] is None
    assert got["source"] == "unavailable"


# -------------------------------------------------------- real counters source
@pytest.fixture()
def store(tmp_path, monkeypatch):
    path = tmp_path / "opencode.db"
    con = sqlite3.connect(path)
    con.execute(
        "CREATE TABLE session_v2 (id TEXT PRIMARY KEY, tokens_input INTEGER, "
        "tokens_output INTEGER, tokens_reasoning INTEGER, tokens_cache_read INTEGER)"
    )
    con.execute(
        "CREATE TABLE session_message (id TEXT PRIMARY KEY, session_id TEXT, data TEXT)"
    )
    con.commit()
    con.close()
    monkeypatch.setattr(m, "DB_PATH", path)
    return path


def test_a_session_v2_row_is_read_from_the_store(store):
    con = sqlite3.connect(store)
    con.execute(
        "INSERT INTO session_v2 (id, tokens_input, tokens_output, tokens_reasoning, "
        "tokens_cache_read) VALUES (?,?,?,?,?)",
        ("ses_abc", 1200, 300, 100, 999_999),
    )
    con.commit()
    con.close()

    got = m.estimate_session("ses_abc")

    assert got == {"tokens": 1600, "source": "session_v2", "session_id": "ses_abc"}


def test_cache_reads_are_not_double_counted(store):
    con = sqlite3.connect(store)
    con.execute(
        "INSERT INTO session_v2 (id, tokens_input, tokens_output, tokens_reasoning, "
        "tokens_cache_read) VALUES ('ses_c', 10, 20, 30, 5000000)"
    )
    con.commit()
    con.close()

    assert m.estimate_session("ses_c")["tokens"] == 60


def test_a_null_counter_row_falls_back_to_message_lengths(store):
    data = json.dumps({"text": "y" * 400})
    con = sqlite3.connect(store)
    con.execute(
        "INSERT INTO session_v2 (id, tokens_input, tokens_output, tokens_reasoning) "
        "VALUES ('ses_n', NULL, NULL, NULL)"
    )
    con.execute(
        "INSERT INTO session_message (id, session_id, data) VALUES ('m1','ses_n',?)",
        (data,),
    )
    con.commit()
    con.close()

    got = m.estimate_session("ses_n")
    assert got["source"] == "session_message"
    assert got["tokens"] == -(-len(data) // 4)


def test_without_token_columns_the_message_table_is_used(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE session_v2 (id TEXT PRIMARY KEY)")
    con.execute(
        "CREATE TABLE session_message (id TEXT PRIMARY KEY, session_id TEXT, data TEXT)"
    )
    con.executemany(
        "INSERT INTO session_message (id, session_id, data) VALUES (?,?,?)",
        [("m1", "ses_old", "a" * 400), ("m2", "ses_old", "b" * 400)],
    )
    con.commit()
    con.close()
    monkeypatch.setattr(m, "DB_PATH", path)

    got = m.estimate_session("ses_old")
    assert got["source"] == "session_message"
    assert got["tokens"] == 200  # 800 chars / 4


def test_an_unknown_session_in_a_real_store_is_unavailable(store):
    con = sqlite3.connect(store)
    con.execute("INSERT INTO session_v2 (id, tokens_input) VALUES ('ses_other', 5)")
    con.commit()
    con.close()

    got = m.estimate_session("ses_absent")
    assert got["tokens"] is None
    assert got["source"] == "unavailable"


def test_the_store_is_opened_read_only(store):
    """A meter that can write is a meter that can lose the history it measures."""
    con = sqlite3.connect(store)
    con.execute("INSERT INTO session_v2 (id, tokens_input) VALUES ('ses_ro', 1)")
    con.commit()
    con.close()

    m.estimate_session("ses_ro")  # must not fail, must not modify

    check = sqlite3.connect(store)
    tables = [
        r[0]
        for r in check.execute("SELECT name FROM sqlite_master WHERE type='table'")
    ]
    check.close()
    assert "session_v2" in tables
    assert "session_message" in tables


# ------------------------------------------------------------ payload estimate
def test_estimate_payload_handles_nested_dicts():
    payload = {
        "ok": True,
        "count": 3,
        "result": {
            "findings": ["a" * 40, "b" * 40],
            "meta": {"source": "c" * 40},
        },
    }
    # independent arithmetic: every key and every leaf string counts once
    expected_chars = (
        len("ok") + len(str(True))
        + len("count") + len(str(3))
        + len("result")
        + len("findings") + 40 + 40
        + len("meta") + len("source") + 40
    )
    assert m.estimate_payload(payload) == -(-expected_chars // 4)


def test_estimate_payload_is_zero_for_empty_shapes():
    assert m.estimate_payload({}) == 0
    assert m.estimate_payload(None) == 0
    assert m.estimate_payload([]) == 0


def test_estimate_payload_grows_with_nesting():
    shallow = {"a": "1" * 100}
    deep = {"a": "1" * 100, "b": {"c": "2" * 100}}
    assert m.estimate_payload(deep) > m.estimate_payload(shallow)


# ----------------------------------------------------------------------- CLI
def test_cli_json_text(capsys):
    assert m.main(["--json", "--text", "abcdefghij"]) == 0
    body = json.loads(capsys.readouterr().out)
    assert body["tokens"] == 3
    assert body["chars"] == 10


def test_cli_json_session_unavailable_exits_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(m, "DB_PATH", tmp_path / "absent.db")
    assert m.main(["--json", "--session", "ses_missing"]) == 2
    body = json.loads(capsys.readouterr().out)
    assert body["tokens"] is None
    assert body["source"] == "unavailable"


def test_cli_json_file(tmp_path, capsys):
    f = tmp_path / "note.txt"
    f.write_text("z" * 100, encoding="utf-8")
    assert m.main(["--json", "--file", str(f)]) == 0
    body = json.loads(capsys.readouterr().out)
    assert body["tokens"] == 25
    assert body["source"] == "file_estimate"


def test_cli_without_a_target_measures_nothing(capsys):
    assert m.main(["--json"]) == 2
    body = json.loads(capsys.readouterr().out)
    assert body["tokens"] is None
