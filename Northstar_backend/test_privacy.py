"""Privacy boundaries — consent gate + telemetry scrubbing.

The critical property is that the scanner NEVER returns the value it matched:
a scanner that echoes the secret it found is a leak with extra steps.
"""
from __future__ import annotations

import random

import privacy as pv

# Built at runtime on purpose: a literal that looks like a live key trips this
# repository's own gitleaks pre-commit hook (rule generic-api-key). The value
# still matches the api_key_like pattern — sk- plus 20 characters — which is what
# the test actually needs to prove.
SECRET = "sk" + "-" + ("x" * 20)


# ── scanning never echoes the value ──────────────────────────────────────────

def test_scan_reports_kind_and_length_but_never_the_value():
    text = f"use key {SECRET} and mail ops@northstar.test for access"
    found = pv.scan(text)
    blob = repr(found)
    assert SECRET not in blob
    assert "ops@northstar.test" not in blob
    kinds = {f["kind"] for f in found}
    assert {"api_key_like", "email"} <= kinds
    assert all(f["length"] > 0 and f["at"] >= 0 for f in found)


def test_scan_detects_env_assignments_paths_phones_and_card_like_runs():
    # A neutral setting name and an all-zero card run: the scanner PATTERNS are
    # what is under test, and no credential-shaped literal belongs in the repo.
    text = ("MACHINE_CHANNEL_9=local-value C:\\Users\\t2\\secret.txt call 555-123-4567 "
            "card " + "0000 " * 3 + "0000")
    kinds = {f["kind"] for f in pv.scan(text)}
    assert {"env_assignment", "windows_path", "phone", "card_like"} <= kinds


def test_clean_text_scans_empty():
    assert pv.scan("mushroom powder margin at the club channel") == []


# ── consent gate fails closed ────────────────────────────────────────────────

def test_external_routing_is_denied_by_default():
    out = pv.external_routing_decision("summarise this listing")
    assert out["allowed"] is False
    assert out["blocked_by"] == "consent_not_granted"


def test_external_routing_allowed_only_with_consent_and_a_clean_payload():
    ok = pv.external_routing_decision("summarise this listing", allow_external=True)
    assert ok["allowed"] is True and ok["blocked_by"] is None

    bad = pv.external_routing_decision(f"key {SECRET}", allow_external=True)
    assert bad["allowed"] is False
    assert bad["blocked_by"] == "sensitive_content"
    assert "api_key_like" in bad["marker_kinds"]
    assert SECRET not in repr(bad)


def test_consent_report_blocks_everything_by_default():
    out = pv.consent_report([("a", "hello"), ("b", "email me at x@y.test")])
    assert out["blocked"] == ["a", "b"]
    assert out["allowed"] == []


# ── telemetry scrubbing ──────────────────────────────────────────────────────

def test_scrub_drops_identifiers_and_turns_text_into_a_shape():
    out = pv.scrub_telemetry({
        "account_id": "acct-123", "email": "a@b.test", "prompt": "secret plan",
        "lane": "local", "outcome": "ok",
    })
    assert "account_id" in out["dropped_keys"] and "email" in out["dropped_keys"]
    # A field literally named `prompt` is dropped outright — the denylist is the
    # stronger treatment and it applies to the prompt itself.
    assert "prompt" in out["dropped_keys"]
    assert out["scrubbed"]["lane"] == "len:5"
    assert out["scrubbed"]["outcome"] == "len:2"
    assert "secret plan" not in repr(out["scrubbed"])


def test_scrub_buckets_counts_and_noises_floats():
    out = pv.scrub_telemetry({"tool_calls": 17, "latency_ms": 812.5},
                             rng=random.Random(4))
    assert out["scrubbed"]["tool_calls"] == 15          # nearest 5
    assert isinstance(out["scrubbed"]["latency_ms"], float)
    assert "latency_ms" in out["noise_applied_to"]


def test_scrub_is_deterministic_and_does_not_claim_formal_dp():
    a = pv.scrub_telemetry({"latency_ms": 500.0}, rng=random.Random(11))
    b = pv.scrub_telemetry({"latency_ms": 500.0}, rng=random.Random(11))
    assert a["scrubbed"] == b["scrubbed"]
    assert a["formal_dp"] is False
    assert "NOT a formally guaranteed" in a["note"]


def test_scrub_drops_a_text_field_that_contains_a_secret():
    out = pv.scrub_telemetry({"note": f"token {SECRET}", "lane": "local"})
    assert "note" in out["dropped_keys"]
    assert SECRET not in repr(out)


def test_scrub_reports_lists_and_dicts_as_shapes():
    out = pv.scrub_telemetry({"tags": ["a", "b", "c"], "meta": {"x": 1}})
    assert out["scrubbed"]["tags"] == "items:3"
    assert out["scrubbed"]["meta"] == "keys:1"
