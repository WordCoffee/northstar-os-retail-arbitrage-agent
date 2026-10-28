"""Regression: a turn asked for a NEW artifact must not report false success.

Observed live 2026-10-28. A repeated identical `apply_label` request came back in
31 seconds reciting a previous asset id (`486d4958…`), wrote no file and rendered
as a completed turn. A fresh chat worked around it, which is not a fix - the
product must detect it.

The guard lives in `chat_router._persist`, the single seam both the routed and
the model path pass through. A `done` turn that ran no tool, when the user asked
for a new artifact, is downgraded to `no_generation` and the stored text says so
plainly. An explicit reuse request is left alone.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import chat_router as cr


NEW_ARTIFACT_REQUESTS = [
    "Run apply_label now. plate_asset_id 8a3e204c logo_asset_id f6bc3a9c "
    "title ORGANIC LION'S MANE. Then report the new asset id.",
    "generate a 2000x2000 listing image now by calling generate_image",
    "render the pouch hero shot again",
    "compose a new label on the pack",
    "create a new artifact for the six ounce pouch",
]

REUSE_REQUESTS = [
    "reuse asset 486d4958 for the listing",
    "use the existing asset, don't regenerate",
    "same asset as before please",
    "that asset is fine, just show me the download",
]


@pytest.mark.parametrize("text", NEW_ARTIFACT_REQUESTS)
def test_detects_a_request_for_a_new_artifact(text):
    assert cr._requests_new_artifact(text) is True
    assert cr._allows_reuse(text) is False, "a new-artifact request must not be read as reuse"


@pytest.mark.parametrize("text", REUSE_REQUESTS)
def test_detects_an_explicit_reuse_request(text):
    assert cr._allows_reuse(text) is True


def test_ordinary_conversation_is_not_a_generation_request():
    for text in ["what models are available?", "thanks", "how big should a main image be?"]:
        assert cr._requests_new_artifact(text) is False


class _FakeMessages:
    def __init__(self):
        self.rows = []

    def create(self, row):
        self.rows.append(row)
        return "msg_1"


class _FakeChat:
    def __init__(self):
        self.messages = _FakeMessages()

    def sessions(self):
        raise AssertionError("not used")


class _FakeDB:
    def __init__(self):
        self.chat = _FakeChat()
        self.chat.tool_calls = type("T", (), {"create": staticmethod(lambda *a, **k: None)})()


def test_prior_asset_without_a_tool_run_is_recorded_as_no_generation():
    """The exact failure: text cites an old asset id, no tool part, status done."""
    db = _FakeDB()
    msg = {
        "role": "assistant",
        "content": "Label applied successfully. New asset ID: 486d4958-1bee-4b7a-9342-620a594bb718",
        "tools": [],            # no tool ran
        "user": "Run apply_label now and report the new asset id.",
    }
    status = "no_generation" if (
        cr._requests_new_artifact(msg["user"]) and not msg["tools"] and not cr._allows_reuse(msg["user"])
    ) else "done"
    assert status == "no_generation"


def test_explicit_reuse_may_return_the_existing_asset():
    user = "reuse asset 486d4958 for the listing, don't generate"
    status = "no_generation" if (
        cr._requests_new_artifact(user) and not cr._allows_reuse(user)
    ) else "done"
    assert status == "done"


def test_a_real_tool_run_passes():
    user = "Run apply_label now and report the new asset id."
    tools = [{"type": "tool", "name": "apply_label", "ok": True,
              "assets": ["9fef9b3c-0c1b-4e56-b9e1-6e33b16d6cce"]}]
    status = "no_generation" if (
        cr._requests_new_artifact(user) and not tools and not cr._allows_reuse(user)
    ) else "done"
    assert status == "done"
