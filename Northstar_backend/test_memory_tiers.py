"""Memory tiers — extends the existing memory bank; isolated on a temp database.

The fixture mirrors the real `memory_entries` schema (data_layer.py:344) on a
throwaway SQLite file and points `memory_bank._db` at it, so these tests never
touch `data/northstar.db`.
"""
from __future__ import annotations

import sqlite3

import pytest

import memory_bank
import memory_tiers as mt

# Mirrors data_layer.py:344-356. Kept in sync deliberately: this is the contract
# module under test reads and writes through memory_bank.
DDL = """
CREATE TABLE IF NOT EXISTS memory_entries (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    entry_type TEXT,
    content TEXT NOT NULL,
    source TEXT,
    confidence REAL DEFAULT 0.8,
    tags TEXT,
    provenance TEXT,
    retired_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
"""


@pytest.fixture()
def bank(tmp_path, monkeypatch):
    conn = sqlite3.connect(str(tmp_path / "northstar.db"))
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL)
    conn.commit()
    monkeypatch.setattr(memory_bank, "_db", lambda: conn)
    yield conn
    conn.close()


# ── writing by tier ──────────────────────────────────────────────────────────

def test_remember_defaults_to_project(bank):
    out = mt.remember("The operator prefers matte kraft for premium pouches")
    assert out["ok"] is True and out["tier"] == "project"
    rows = mt.list_tier("project")
    assert [r["id"] for r in rows] == [out["id"]]
    assert mt.tier_of(rows[0]) == "project"


def test_transient_requires_a_session_so_it_can_be_flushed(bank):
    out = mt.remember("scratch thought", tier="transient")
    assert out["ok"] is False
    assert "session_id" in out["error"]


def test_global_cannot_be_written_directly(bank):
    out = mt.remember("a lesson", tier="global")
    assert out["ok"] is False
    assert "promote_to_global" in out["error"]


def test_unknown_tier_and_empty_content_are_refused(bank):
    assert mt.remember("x", tier="eternal")["ok"] is False
    assert mt.remember("   ")["ok"] is False


def test_transient_buffer_flushes_at_session_end(bank):
    mt.remember("mid-session note", tier="transient", session_id="s1")
    mt.remember("other session note", tier="transient", session_id="s2")
    mt.remember("durable project fact")
    assert len(mt.list_tier("transient")) == 2

    out = mt.flush_transient(session_id="s1")
    assert out["retired"] == 1
    left = mt.list_tier("transient")
    assert len(left) == 1 and "other session" in left[0]["content"]
    assert len(mt.list_tier("project")) == 1          # project rows untouched


# ── promotion sanitises instead of copying ───────────────────────────────────

def test_promote_to_global_strips_identifiers_and_keeps_the_lesson(bank):
    eid = mt.remember(
        "For club sourcing, unit cost lands near \"9.94\" at https://samsclub.com/x "
        "and the margin lesson is: never trust a single price scrape "
        "contact buyer@club.test ref 123456789",
    )["id"]

    out = mt.promote_to_global(eid)
    assert out["ok"] is True
    assert out["stripped"]["url"] >= 1
    assert out["stripped"]["email"] >= 1
    assert out["stripped"]["long_number"] >= 1
    body = out["content"]
    assert "https://" not in body and "@" not in body and "123456789" not in body
    assert "never trust a single price scrape" in body
    assert mt.tier_of(mt.list_tier("global")[0]) == "global"
    # the evidence-bearing project row is untouched
    assert any(r["id"] == eid for r in mt.list_tier("project"))


def test_promote_refuses_unknown_ids_and_other_accounts(bank):
    assert mt.promote_to_global("nope")["ok"] is False
    eid = mt.remember("a lesson about pricing at the club channel",
                      account_id="acct-a")["id"]
    denied = mt.promote_to_global(eid, account_id="acct-b")
    assert denied["ok"] is False and "different account" in denied["error"]


def test_promote_refuses_when_stripping_leaves_no_lesson(bank):
    eid = mt.remember("https://example.com/a/b/c 123456789 buyer@x.test")["id"]
    out = mt.promote_to_global(eid)
    assert out["ok"] is False
    assert "too little remains" in out["error"]
    assert out["stripped"]["url"] == 1 and out["stripped"]["email"] == 1
    assert len(mt.list_tier("global")) == 0


# ── reporting ────────────────────────────────────────────────────────────────

def test_tiers_counts_each_tier_and_carries_the_honest_boundary(bank):
    mt.remember("project one")
    mt.remember("project two")
    mt.remember("session note", tier="transient", session_id="s1")
    out = mt.tiers()
    assert out["counts"]["project"] == 2
    assert out["counts"]["transient"] == 1
    assert out["total"] == 3
    assert out["boundary"]["knowledge_store_encrypted"] is False


def test_encryption_status_does_not_claim_encryption(bank):
    status = mt.encryption_status()
    assert status["knowledge_store_encrypted"] is False
    assert "NOT encrypted" in status["gap"]
    assert "D3" in status["gap"]
    assert status["encrypted_elsewhere"]["module"] == "foundation/secrets.py"
