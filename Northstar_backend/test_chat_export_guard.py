"""The chat-export guard: one job, no false alarms.

The five flagged lines in this repository came from pasted transcripts. gitleaks catches those after
the fact; this stops the transcript being committed at all. It must be narrow enough that nobody
disables it: only files whose *name* says "chat export", and only lines that *assign* a token-shaped
value.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import chat_export_guard as G  # noqa: E402

#: A value that is unmistakably a key shape, and obviously not a real credential.
FAKE_KEY = "REMOVED_SYNTHETIC_TEST_TOKEN"
FAKE_PAT = "ghp_" + "abcdefghijklmnop0123"


def test_a_plain_transcript_assignment_is_caught():
    text = f"12: SCAVIO_API_KEY={FAKE_KEY}\n"
    findings = G.scan_text(text)
    assert findings and findings[0]["line"] == 1


def test_a_quoted_assignment_is_caught():
    findings = G.scan_text(f"BRIGHTDATA_API_KEY='{FAKE_KEY}'\n")
    assert findings


def test_a_github_pat_is_caught():
    assert G.scan_text(f"token: {FAKE_PAT}\n")


def test_prose_about_keys_is_not_flagged():
    """The first version blocked '… argues: your API key must be rotated…' — that is how a guard
    gets removed rather than fixed."""
    prose = (
        "The reviewer argues: your API key: it must be rotated before the release.\n"
        "Set the API key to a value the operator supplies, never a literal in the repo.\n"
    )
    assert G.scan_text(prose) == []


def test_a_normal_document_is_not_an_export():
    assert G.is_export("docs/how-to-store-an-api-key.md") is False
    assert G.is_export("FirstNorthstarautomationchat.md") is True
    assert G.is_export("autothink-ui-chat-export.md") is True
    assert G.is_export("reports/chat-export-notes.txt") is True


def test_an_export_without_keys_passes():
    assert G.scan_text("we discussed pricing and nothing else\n") == []


def test_the_five_flagged_lines_in_this_repo_are_all_caught():
    """The regression that matters: these exact lines must never be committable again."""
    export = ROOT / "FirstNorthstarautomationchat.md"
    if not export.is_file():
        return                      # removed after rotation; nothing to check
    findings = G.scan_file(export)
    lines = {finding["line"] for finding in findings}
    assert {1143, 1148, 1291, 1296} <= lines, sorted(lines)


def test_the_pat_line_is_caught_while_the_file_exists():
    export = ROOT / "autothink-ui-chat-export.md"
    if not export.is_file():
        return
    assert any(finding["line"] == 7852 for finding in G.scan_file(export))
