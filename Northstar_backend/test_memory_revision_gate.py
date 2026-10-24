"""Memory revision gate: agent changes stay PROPOSED until the operator approves."""

from __future__ import annotations

import pytest

import memory_bank as mb


@pytest.fixture()
def entry_id():
    eid = mb.ingest("BirdRock home is BirdRock Home verified supplier", entry_type="fact",
                    source="operator")
    yield eid
    mb.retire(eid)


def test_proposal_leaves_the_approved_entry_untouched(entry_id):
    before = mb.search("BirdRock")[0]
    mb.propose_revision(entry_id, content="agent-hallucinated rewrite")
    after = mb.search("BirdRock")[0]
    assert after["content"] == before["content"]


def test_pending_queue_lists_only_proposals(entry_id):
    rev = mb.propose_revision(entry_id, confidence=0.99, note="confidence raise")
    rows = mb.pending_revisions(entry_id)
    assert [r["id"] for r in rows] == [rev]
    assert rows[0]["status"] == mb.REV_PENDING


def test_approve_applies_values_and_ends_the_pending_state(entry_id):
    rev = mb.propose_revision(entry_id, content="Approved rewrite: verified 2026-10", tags=["verified"])
    out = mb.approve_revision(rev)
    assert out["approved"] is True
    after = mb.search("Approved rewrite")[0]
    assert after["id"] == entry_id
    assert after["tags"] == ["verified"]
    assert mb.pending_revisions(entry_id) == []


def test_reject_keeps_approved_content_exactly(entry_id):
    rev = mb.propose_revision(entry_id, content="bad rewrite")
    out = mb.reject_revision(rev, "overwrites an operator-verified fact")
    assert out["rejected"] is True
    assert mb.search("BirdRock")[0]["content"].startswith("BirdRock")


def test_a_revision_cannot_be_reviewed_twice(entry_id):
    rev = mb.propose_revision(entry_id, content="once only")
    mb.approve_revision(rev)
    second = mb.approve_revision(rev)
    assert second["approved"] is False
    assert second["reason"] == "already approved"


def test_unknown_revision_refuses_cleanly():
    assert mb.approve_revision("00000000-0000-0000-0000-000000000000")["approved"] is False


def test_retrieval_serves_approved_content_while_a_proposal_is_open(entry_id):
    mb.propose_revision(entry_id, content="pending phantom content")
    context = mb.retrieve_context("BirdRock", account_id="default")
    assert "BirdRock" in context and "phantom" not in context
