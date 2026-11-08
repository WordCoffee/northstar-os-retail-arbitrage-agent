"""A single key is pressed, a chord is hotkeyed — the bug that typed "enter" into a URL."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from vision import chrome_uia  # noqa: E402


class FakePyAutoGUI:
    def __init__(self):
        self.calls = []
        self.PAUSE = 0

    def hotkey(self, *keys):
        self.calls.append(("hotkey", keys))

    def press(self, key):
        self.calls.append(("press", key))

    def write(self, text, interval=0.0):
        self.calls.append(("write", text))


def _page(monkeypatch, fake):
    page = chrome_uia.ChromeUIA(hwnd=7, title="New Tab - Google Chrome")
    monkeypatch.setitem(sys.modules, "pyautogui", fake)
    monkeypatch.setattr(chrome_uia, "foreground_hwnd", lambda: 7)
    monkeypatch.setattr(chrome_uia.privacy, "classify",
                        lambda **kwargs: {"allow": True, "reason": ""})
    monkeypatch.setattr(page, "title_now", lambda: "New Tab - Google Chrome")
    return page


def test_a_single_key_is_pressed_not_typed(monkeypatch):
    fake = FakePyAutoGUI()
    page = _page(monkeypatch, fake)
    result = page._keys("enter")
    assert result["ok"] is True
    assert fake.calls == [("press", "enter")]


def test_a_chord_is_still_a_hotkey(monkeypatch):
    fake = FakePyAutoGUI()
    page = _page(monkeypatch, fake)
    page._keys("ctrl+t")
    assert fake.calls == [("hotkey", ("ctrl", "t"))]


def test_no_single_key_is_ever_expanded_into_letters(monkeypatch):
    fake = FakePyAutoGUI()
    page = _page(monkeypatch, fake)
    for key in ("enter", "pagedown", "escape", "tab"):
        page._keys(key)
    for kind, payload in fake.calls:
        assert kind == "press"
        assert isinstance(payload, str)
