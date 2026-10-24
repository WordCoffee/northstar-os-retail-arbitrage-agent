"""Bojo vs Autothink boundary.

Autothink is a PREMIUM service (Perplexity-Computer class). The rule under test is
not "does Bojo route engineering to Autothink" but "does Bojo STOP and OFFER,
with a token estimate, and never send anything on its own".
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from specialists import router  # noqa: E402


def test_a_small_utility_is_built_by_bojo_with_no_handoff():
    d = router.scope("make me a quick tip calculator")
    assert d["scope"] == "bojo"
    assert d["kind"] == "utility"
    assert not d.get("offer_handoff")


def test_engineering_work_is_offered_not_sent():
    d = router.scope("refactor the listings service to async and add unit tests")
    assert d["scope"] == "bojo", "Bojo keeps ownership until the operator says otherwise"
    assert d["offer_handoff"] is True
    assert d["requires_user_approval"] is True
    assert d["handoff"]["target"] == "autothink"


def test_the_offer_states_the_token_usage_up_front():
    d = router.scope("migrate the database schema and update the orm models")
    handoff = d["handoff"]
    assert handoff["estimated_tokens"] is not None
    assert handoff["estimated_tokens"] > 0
    # priced on the CLOUD lane: a premium handoff must not read as free
    assert handoff["priced_on"] == "cloud lane"
    assert handoff["estimated_charge_usd"] > 0
    assert "Nothing has been sent" in handoff["note"]


def test_the_offer_never_claims_the_work_started():
    d = router.scope("set up a ci pipeline")
    text = str(d)
    assert "sent" in text.lower()
    assert d["requires_user_approval"] is True


def test_engineering_signals_are_recognised():
    for text in ("fix the memory leak in the worker pool", "open a pull request",
                 "rewrite the listing importer as a queue worker with tests"):
        assert router.scope(text)["offer_handoff"] is True, text


def test_a_packaging_request_is_plain_bojo_work():
    d = router.scope("build the package for Lion's Mane 6 oz pouch")
    assert d["scope"] == "bojo" and not d.get("offer_handoff")


def test_a_quoted_engineering_example_does_not_trigger_an_offer():
    d = router.scope('Our developer said "refactor the service" but I just need a '
                     "product photo brief")
    assert not d.get("offer_handoff")


def test_the_offer_keeps_the_operators_words():
    words = "rewrite the listing importer as a queue worker with tests"
    d = router.scope(words)
    assert words.split()[0] in d["handoff"]["request"]
