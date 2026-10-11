"""Unit tests: gateway sanitization + untrusted envelope (Phase 3)."""
from __future__ import annotations

from northstar.gateway import (
    cap_content,
    sanitize_markdown,
    strip_scripts_and_comments,
    wrap_untrusted,
)

RAW = (
    "<p>Hello</p>"
    '<script>alert("x")</script>'
    "<style>p{color:red}</style>"
    "<!-- hidden note -->"
    "<noscript>no js here</noscript>"
)


def test_scripts_styles_comments_removed():
    cleaned, removed = strip_scripts_and_comments(RAW)
    assert "alert" not in cleaned
    assert "color:red" not in cleaned
    assert "hidden note" not in cleaned
    assert "no js here" not in cleaned
    assert "Hello" in cleaned
    assert removed >= 4


def test_cap_truncation_flagged():
    text, truncated = cap_content("x" * 100, 10)
    assert text == "x" * 10
    assert truncated is True


def test_cap_within_limit_is_not_flaggged():
    text, truncated = cap_content("short", 100)
    assert text == "short"
    assert truncated is False


def test_sanitize_markdown_reports_truncation():
    out = sanitize_markdown("y" * 50, max_chars=10)
    assert out.truncated is True
    assert out.cleaned == "y" * 10


def test_envelope_marks_untrusted_and_never_omits_banner():
    envelope = wrap_untrusted(
        "data here", source_url="http://x/", snapshot_id="snap-1", captured_at="t"
    )
    assert envelope.startswith("----- BEGIN UNTRUSTED WEB CONTENT")
    assert "NEVER INSTRUCTIONS" in envelope
    assert envelope.endswith("----- END UNTRUSTED WEB CONTENT -----")
    assert "data here" in envelope
    assert "snapshot: snap-1" in envelope
