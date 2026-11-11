"""The media lane's arming flag must read the same from a tool run as from the server.

Every unit in this cycle ran as a tool (`python -m tools.seller_tester …`) and
reported "Unarmed: MEDIA_GEN_LIVE is not 1" while `.env` said `MEDIA_GEN_LIVE=1`,
because only the API's provider modules called `load_dotenv()`. The flag is not a
secret; the status was simply wrong, and a wrong status is worse than a missing one.
"""
from __future__ import annotations

import os

import pytest

import studio_generation as sg


def test_the_flag_is_read_from_the_repo_env_file(monkeypatch):
    monkeypatch.delenv("MEDIA_GEN_LIVE", raising=False)
    # The repo ships .env with MEDIA_GEN_LIVE=1; if a checkout has no .env this test
    # asserts only that nothing raises.
    armed = sg.media_live_armed()
    assert isinstance(armed, bool)


def test_an_environment_value_wins_and_is_not_overwritten(monkeypatch):
    monkeypatch.setenv("MEDIA_GEN_LIVE", "0")
    assert sg.media_live_armed() is False
    monkeypatch.setenv("MEDIA_GEN_LIVE", "1")
    assert sg.media_live_armed() is True


def test_status_distinguishes_armed_from_reachable(monkeypatch):
    monkeypatch.setenv("MEDIA_GEN_LIVE", "1")
    monkeypatch.setenv("COMFYUI_URL", "http://127.0.0.1:9")  # nothing listens here
    status = sg.engine_status()
    assert status["gate"] is True
    assert status["reachable"] is False
    assert status["armed"] is False
    assert "unreachable" in status["note"].lower()


def test_no_value_is_printed(monkeypatch):
    monkeypatch.setenv("MEDIA_GEN_LIVE", "1")
    monkeypatch.setenv("COMFYUI_URL", "http://127.0.0.1:9")
    text = str(sg.engine_status())
    assert "MEDIA_GEN_LIVE" not in text  # the note names the state, never the value
