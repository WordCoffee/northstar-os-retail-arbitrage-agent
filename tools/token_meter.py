"""token_meter - an honest token estimate, so the daily cap has a number.

The autonomy programme enforces a 3,000,000-token daily cap
(``TOKEN_CAP_PER_DAY`` in ``tools/tys_runner.py``), but until now the number it
counted was whatever a worker claimed, and a worker that reported nothing
reported nothing. The cap was therefore unmeasurable, and an unmeasurable cap
cannot be enforced. This module supplies the measurement:

    estimate_text(text)        characters / 4, rounded up -- an estimate, nothing more
    estimate_session(sid)      what the OpenCode store already recorded for a session
    estimate_payload(payload)  the same arithmetic over a JSON result dict

The session store is ``%USERPROFILE%\\.local\\share\\opencode\\opencode.db``
(written by OpenCode itself). It is opened read-only, through a ``mode=ro``
URI, so a meter can never corrupt the thing it measures. Two sources exist
there, in order of preference:

    1. ``session_v2.tokens_input / tokens_output / tokens_reasoning`` -- real
       counters, when the deployment records them;
    2. ``session_message.data`` -- the JSON payloads of every message, summed by
       length / 4, when the counters are absent or null.

Every function is total: none of them raise, and none of them invent a number.
If the store is missing, ``estimate_session`` returns
``{"tokens": None, "source": "unavailable", ...}``. It does **not** return 0,
because 0 reads as "this cycle was free" and silently defeats the cap. A missing
measurement has to be visibly missing.

Documented limits, because the number is used to refuse work:

* chars/4 is an English/code rule of thumb. JSON, prose and diffs all differ;
  expect roughly +/-25%. It is a *ceiling*, not a measurement: it rounds up, so
  the cap errs towards stopping early rather than overrunning.
* ``tokens`` is ``input + output + reasoning``. ``tokens_cache_read`` is
  excluded: it re-reads a prefix already counted as input, and counting it
  twice would make the cap fire on a long conversation rather than on real work.
  It stays visible in the store for anyone who wants the stricter figure.
* A fallback estimate (source ``session_message``) covers prompts, tool
  arguments and results, not the model's hidden reasoning, which the store does
  not keep.

Usage::

    python tools/token_meter.py --json --text "some text"
    python tools/token_meter.py --json --session ses_abc123
    python tools/token_meter.py --json --file reports/ty/handoff.md
    python tools/token_meter.py --session ses_abc123       # human-readable

Exit codes: 0 measured, 2 nothing to measure (missing file / empty invocation).
A JSON body is printed in both cases; ``tokens`` is ``null`` when unavailable.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import quote

CHARS_PER_TOKEN = 4

#: Read-only source of truth for what a session has already spent.
DB_PATH = Path(
    os.environ.get("OPENCODE_DB")
    or Path.home() / ".local" / "share" / "opencode" / "opencode.db"
)

#: How long to wait for a reader lock before giving up on the store.
LOCK_TIMEOUT_S = 5.0

_TOKEN_COLUMNS = ("tokens_input", "tokens_output", "tokens_reasoning")
_TEXT_COLUMNS = ("data", "content", "text")


# --------------------------------------------------------------------- helpers
def _ceil_div(n: int, d: int) -> int:
    return -(-int(n) // int(d))


def _unavailable(session_id: Optional[str], reason: str = "") -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "tokens": None,
        "source": "unavailable",
        "session_id": session_id,
    }
    if reason:
        out["reason"] = reason
    return out


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open the store read-only. Never creates, never migrates, never writes."""
    db_path = Path(db_path)
    if not db_path.is_file():
        raise FileNotFoundError(str(db_path))
    uri = "file:" + quote(db_path.resolve().as_posix(), safe="/:") + "?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=LOCK_TIMEOUT_S)


def _columns(con: sqlite3.Connection, table: str) -> tuple:
    rows = con.execute("PRAGMA table_info(%s)" % table).fetchall()
    return tuple(row[1] for row in rows)


def _table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return bool(row)


def _from_token_counters(
    con: sqlite3.Connection, session_id: Optional[str]
) -> Optional[int]:
    """Sum the real counters, or None when the store cannot answer that way."""
    if not _table_exists(con, "session_v2"):
        return None
    present = [c for c in _TOKEN_COLUMNS if c in _columns(con, "session_v2")]
    if not present:
        return None
    select = ", ".join(present)
    if session_id is None:
        # sqlite has no SUM across a row; sum the columns separately.
        total = 0
        for c in present:
            got = con.execute(
                "SELECT SUM(COALESCE(%s, 0)) FROM session_v2" % c
            ).fetchone()
            total += int(got[0] or 0)
        return total
    row = con.execute(
        "SELECT %s FROM session_v2 WHERE id = ?" % select, (session_id,)
    ).fetchone()
    if row is None:
        return None
    values = row[: len(present)]
    if all(v is None for v in values):
        # counters exist but were never written: fall through to the messages
        return None
    return sum(int(v or 0) for v in values)


def _from_message_lengths(
    con: sqlite3.Connection, session_id: Optional[str]
) -> Optional[int]:
    """chars/4 over stored message payloads, or None when nothing is stored."""
    if not _table_exists(con, "session_message"):
        return None
    cols = _columns(con, "session_message")
    text_col = next((c for c in _TEXT_COLUMNS if c in cols), None)
    if text_col is None:
        return None
    if session_id is None:
        row = con.execute(
            "SELECT COALESCE(SUM(LENGTH(%s)), 0) FROM session_message" % text_col
        ).fetchone()
    else:
        row = con.execute(
            "SELECT COALESCE(SUM(LENGTH(%s)), 0) FROM session_message WHERE session_id = ?"
            % text_col,
            (session_id,),
        ).fetchone()
    chars = int(row[0] or 0) if row else 0
    if chars <= 0:
        return None
    return _ceil_div(chars, CHARS_PER_TOKEN)


# ----------------------------------------------------------------------- API
def estimate_text(text: Any) -> int:
    """Estimate tokens in ``text`` as characters / 4, rounded up.

    The divisor is the usual English-and-code rule of thumb, not a tokeniser.
    Rounding up is deliberate: an underestimate is the error that defeats a cap.
    """
    if text is None:
        return 0
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    elif not isinstance(text, str):
        text = str(text)
    return _ceil_div(len(text), CHARS_PER_TOKEN)


def estimate_session(session_id: Optional[str] = None, db_path: Optional[Path] = None) -> Dict[str, Any]:
    """Estimate what a session has spent, from the store. Never raises.

    ``session_id=None`` totals every session in the store. That is a lifetime
    figure, not a daily one: it is useful as a diagnostic and must not be fed to
    the daily cap as-is -- filter by ``time_created``/``time_updated`` when the
    launcher is wired to it.

    Returns ``{"tokens": int|None, "source": str, "session_id": str|None}``
    where ``source`` is one of ``session_v2``, ``session_message`` or
    ``unavailable``. ``tokens`` is None -- never 0 -- when nothing could be
    measured, because 0 is indistinguishable from "free".
    """
    sid = session_id
    path = Path(db_path) if db_path is not None else DB_PATH
    try:
        con = _connect(path)
    except Exception as exc:  # absent, unreadable, bad path: all the same answer
        return _unavailable(sid, "store_absent: %s" % exc)

    try:
        counters = _from_token_counters(con, sid)
        if counters is not None:
            return {
                "tokens": int(counters),
                "source": "session_v2",
                "session_id": sid,
            }
        messages = _from_message_lengths(con, sid)
        if messages is not None:
            return {
                "tokens": int(messages),
                "source": "session_message",
                "session_id": sid,
            }
        return _unavailable(sid, "no_rows")
    except Exception as exc:  # locked, malformed schema, truncated file
        return _unavailable(sid, "read_failed: %s" % exc)
    finally:
        try:
            con.close()
        except Exception:
            pass


def _payload_chars(payload: Any) -> int:
    """Count the characters a JSON-shaped result occupies, keys included."""
    if payload is None:
        return 0
    if isinstance(payload, dict):
        chars = 0
        for key, value in payload.items():
            chars += len(key if isinstance(key, str) else str(key))
            chars += _payload_chars(value)
        return chars
    if isinstance(payload, (list, tuple, set)):
        return sum(_payload_chars(item) for item in payload)
    if isinstance(payload, bytes):
        return len(payload.decode("utf-8", "replace"))
    if isinstance(payload, str):
        return len(payload)
    return len(str(payload))


def estimate_payload(payload: Any) -> int:
    """Estimate tokens for a JSON-shaped result: keys, values, nesting included.

    Dict keys are counted as well as values, because a result is serialised as
    JSON and its keys occupy the same stream as everything else.
    """
    return _ceil_div(_payload_chars(payload), CHARS_PER_TOKEN)


def estimate_file(path: Any) -> Dict[str, Any]:
    """Estimate a file's text. Missing/unreadable -> unavailable, never 0."""
    try:
        p = Path(path)
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return {
            "tokens": None,
            "source": "unavailable",
            "path": str(path),
            "reason": "unreadable: %s" % exc,
        }
    return {
        "tokens": estimate_text(text),
        "source": "file_estimate",
        "path": str(path),
        "chars": len(text),
    }


# ----------------------------------------------------------------------- CLI
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="token_meter",
        description="Honest token estimates for the daily cap (chars/4).",
    )
    p.add_argument("--json", action="store_true", help="print the estimate as JSON")
    p.add_argument("--text", help="estimate a literal string")
    p.add_argument("--session", help="estimate a stored OpenCode session id")
    p.add_argument("--file", help="estimate a text file")
    p.add_argument("--db", help="override the session store path")
    return p


def main(argv: Optional[list] = None) -> int:
    args = _build_parser().parse_args(argv)
    db_path = Path(args.db) if args.db else None

    if args.session is not None:
        result = estimate_session(args.session, db_path=db_path)
    elif args.text is not None:
        result = {
            "tokens": estimate_text(args.text),
            "source": "text_estimate",
            "chars": len(args.text),
        }
    elif args.file is not None:
        result = estimate_file(args.file)
    else:
        result = {
            "tokens": None,
            "source": "unavailable",
            "reason": "nothing to measure: pass --text, --session or --file",
        }
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("token_meter: pass --text, --session or --file", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        tokens = result.get("tokens")
        shown = "unavailable" if tokens is None else tokens
        print("%s tokens (%s)" % (shown, result.get("source")))
    return 0 if result.get("tokens") is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())
