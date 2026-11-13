"""One recorded Chrome window, and a decoy that must be refused.

The 2026-11-11 incident was a keystroke that landed in a Chrome window nobody had chosen. A guard
that compares process names cannot tell a decoy from the real thing, and a guard that compares
titles is reading the thing we refuse to record. So the identity is the **HWND**: launched with the
quoted profile argument, recorded once, and compared twice — the window being typed into, and the
foreground at the moment of typing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _extra in (str(ROOT), str(ROOT / "tools")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

from tools.vision import chrome_uia, profile6  # noqa: E402

RECORDED = 111
DECOY = 222


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    from tools.vision import browse_guard

    state = tmp_path / "profile6_window.json"
    monkeypatch.setattr(profile6, "STATE", state, raising=False)
    monkeypatch.setattr(profile6, "PAUSE", tmp_path / "PAUSE", raising=False)
    # the browse guard and the control gate have their own PAUSE constants
    monkeypatch.setattr(browse_guard, "PAUSE", tmp_path / "PAUSE", raising=False)
    monkeypatch.setattr(chrome_uia.control, "PAUSE", tmp_path / "PAUSE", raising=False)
    return tmp_path


def _record(hwnd: int = RECORDED) -> dict:
    return profile6.record_window(hwnd, pid=4242, argv=["chrome", profile6.PROFILE_ARG, "url"])


def _window(hwnd: int, pause: Path | None = None) -> "chrome_uia.ChromeUIA":
    window = chrome_uia.ChromeUIA.__new__(chrome_uia.ChromeUIA)  # no UIA, no window resolution
    window.hwnd = hwnd
    window._window = None
    # the controller holds its own pause path, bound at construction; bind it to the test's
    window.control_layer = chrome_uia.control.Control(
        pause=(pause or ROOT / "state" / "vision" / "PAUSE"))
    return window


def test_the_profile_argument_is_quoted_as_the_owner_requires():
    assert profile6.PROFILE_ARG == '--profile-directory="Profile 6"'


def test_a_recorded_window_is_required_before_any_key(isolated, monkeypatch):
    """No record yet: a keystroke must be refused rather than sent to whatever has focus."""
    monkeypatch.setattr(chrome_uia, "foreground_hwnd", lambda: RECORDED)
    monkeypatch.setattr(chrome_uia.privacy, "classify", lambda **_: {"allow": True})
    result = _window(RECORDED, isolated / "PAUSE")._keys("ctrl+t")
    assert result["ok"] is False and result["refused"] is True
    assert "no Profile 6 window has been recorded" in result["reason"]


def test_the_foreground_must_be_the_recorded_window(isolated, monkeypatch):
    _record(RECORDED)
    monkeypatch.setattr(chrome_uia, "foreground_hwnd", lambda: DECOY)
    allowed, reason = profile6.check_foreground(RECORDED, foreground=DECOY)
    assert allowed is False
    assert str(RECORDED) in reason and str(DECOY) in reason


def test_a_decoy_chrome_window_is_refused_by_hwnd(isolated, monkeypatch):
    """Same process name, same look, different handle: refused before a keystroke."""
    _record(RECORDED)
    monkeypatch.setattr(chrome_uia, "foreground_hwnd", lambda: DECOY)
    decoy = _window(DECOY, isolated / "PAUSE")
    result = decoy._keys("ctrl+t")
    assert result["ok"] is False
    assert result["refused"] is True
    assert "not the recorded Profile 6 window" in result["reason"]


def test_the_recorded_window_passes_both_checks(isolated, monkeypatch):
    _record(RECORDED)
    allowed, reason = profile6.check_foreground(RECORDED, foreground=RECORDED)
    assert allowed is True and reason == ""
    monkeypatch.setattr(chrome_uia, "foreground_hwnd", lambda: RECORDED)
    monkeypatch.setattr(chrome_uia.privacy, "classify",
                        lambda **_: {"allow": True, "reason": ""})
    typed = {}
    monkeypatch.setitem(sys.modules, "pyautogui", _FakePyAutoGUI(typed))
    result = _window(RECORDED, isolated / "PAUSE")._keys("ctrl+t")
    assert result["ok"] is True, result


def test_the_launch_refuses_while_paused(isolated):
    profile6.PAUSE.write_text("paused", encoding="utf-8")
    result = profile6.launch("http://127.0.0.1:8101/ui/")
    assert result["ok"] is False and result["refused"] is True
    assert "PAUSE" in result["reason"]


def test_the_record_names_the_profile_and_never_a_title(isolated):
    record = _record()
    blob = json.dumps(record)
    assert record["profile"] == "Profile 6"
    assert record["profile_arg"] == profile6.PROFILE_ARG
    assert record["hwnd"] == RECORDED
    assert "title" not in blob.lower()


class _FakePyAutoGUI:
    PAUSE = 0.0

    def __init__(self, sink: dict):
        self.sink = sink

    def hotkey(self, *keys):
        self.sink["hotkey"] = keys

    def press(self, key):
        self.sink["press"] = key
