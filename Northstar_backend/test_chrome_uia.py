"""D8 follow-up: driving Profile 6 through UI Automation, with pixels only as a fallback.

Everything here is testable without touching the owner's Chrome: the window list and the
foreground handle are injected, so the refusal paths run for real.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from vision import chrome_uia, risk  # noqa: E402


def window(hwnd=100, title="Competitor Monitor - Google Chrome", area=1_000_000):
    return {"hwnd": hwnd, "title": title, "area": area, "allowed": True, "reason": ""}


def test_windows_are_sorted_by_area_so_the_real_page_wins(monkeypatch):
    rows = [
        {"hwnd": 1, "title": "Google Chrome", "process": "chrome.exe",
         "width": 10, "height": 10, "rect": [0, 0, 10, 10]},
        {"hwnd": 2, "title": "New Tab - Google Chrome", "process": "chrome.exe",
         "width": 1400, "height": 900, "rect": [0, 0, 1400, 900]},
        {"hwnd": 3, "title": "Amazon - Cart", "process": "chrome.exe",
         "width": 1500, "height": 950, "rect": [0, 0, 1500, 950]},
    ]
    monkeypatch.setattr(chrome_uia.capture, "windows", lambda: rows)
    found = chrome_uia.chrome_windows()
    assert found[0]["hwnd"] == 3          # the biggest, which is the blocked one
    assert found[0]["allowed"] is False    # and it is marked, not silently used


def test_attach_refuses_a_blocked_window(monkeypatch):
    monkeypatch.setattr(chrome_uia, "chrome_windows",
                        lambda: [{"hwnd": 9, "title": "Amazon Seller Central",
                                  "area": 999, "allowed": False,
                                  "reason": "title matches 'amazon'"}])
    result = chrome_uia.ChromeUIA.attach()
    assert result["ok"] is False and result["refused"] is True


def test_attach_picks_the_first_allowed_window(monkeypatch):
    monkeypatch.setattr(chrome_uia, "chrome_windows",
                        lambda: [{"hwnd": 5, "title": "Amazon", "area": 999,
                                  "allowed": False, "reason": "amazon"},
                                 window(7)])
    monkeypatch.setattr(chrome_uia.ChromeUIA, "_resolve", lambda self: object())
    result = chrome_uia.ChromeUIA.attach()
    assert result["ok"] is True and result["page"].hwnd == 7


def test_navigation_to_a_blocked_url_is_refused_before_any_key(monkeypatch):
    page = chrome_uia.ChromeUIA(hwnd=7)
    monkeypatch.setattr(page, "focus", lambda: (_ for _ in ()).throw(
        AssertionError("must not focus for a blocked URL")))
    result = page.open_url("https://www.amazon.com/dp/B0X")
    assert result["ok"] is False and result["refused"] is True
    assert result["risk"] == risk.BLOCKED


def test_keys_are_refused_when_the_foreground_changed(monkeypatch):
    page = chrome_uia.ChromeUIA(hwnd=7, title="New Tab - Google Chrome")
    monkeypatch.setattr(chrome_uia, "foreground_hwnd", lambda: 999)
    result = page._keys("ctrl+t")
    assert result["ok"] is False and result["refused"] is True
    assert "foreground" in result["reason"]


def test_focus_refuses_a_blocked_window_before_calling_setactive(monkeypatch):
    page = chrome_uia.ChromeUIA(hwnd=7)
    monkeypatch.setattr(page, "title_now", lambda: "Amazon.com - Cart")
    result = page.focus()
    assert result["ok"] is False and result["refused"] is True


def test_typing_into_a_password_field_is_refused(monkeypatch):
    page = chrome_uia.ChromeUIA(hwnd=7, title="Sign in - Google Chrome")
    monkeypatch.setattr(chrome_uia, "foreground_hwnd", lambda: 7)
    action = {"kind": "type", "field": "Password"}
    verdict = risk.evaluate(action, url="http://127.0.0.1:8101/ui/sign-in",
                            title="Sign in")
    assert verdict["allow"] is False and verdict["risk"] == risk.BLOCKED


def test_read_text_redacts_credentials(monkeypatch):
    page = chrome_uia.ChromeUIA(hwnd=7, title="New Tab")
    monkeypatch.setattr(page, "elements", lambda: [
        {"role": "TextControl", "name": "api_key=abcdef123456"},
        {"role": "TextControl", "name": "Competitor Monitor"},
        {"role": "EditControl", "name": "Password", "mask": True},
    ])
    result = page.read_text()
    assert result["ok"] is True
    assert "abcdef123456" not in result["text"]
    assert "[redacted]" in result["text"]
    assert "Competitor Monitor" in result["text"]


def test_a_new_tab_is_closed_only_if_this_session_opened_one(monkeypatch):
    page = chrome_uia.ChromeUIA(hwnd=7)
    called = {"n": 0}
    monkeypatch.setattr(page, "_keys", lambda *a, **k: called.__setitem__("n", called["n"] + 1)
                        or {"ok": True})
    assert page.close_tab()["ok"] is True
    assert called["n"] == 0
    page.opened_tab = True
    page.close_tab()
    assert called["n"] == 1


def test_status_reports_the_lock_screen_as_the_foreground(monkeypatch):
    monkeypatch.setattr(chrome_uia, "chrome_windows", lambda: [window(7)])
    monkeypatch.setattr(chrome_uia, "foreground_hwnd", lambda: 424242)
    info = chrome_uia.status()
    assert info["windows"] == 1 and info["foreground"] == 424242
