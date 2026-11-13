"""While PAUSE exists, exactly one kind of browsing may happen: headless Playwright on loopback.

The rule comes from a measured incident, not a preference. On 2026-11-11 at 09:14–09:16Z and
09:36–09:38Z the unlock watcher ran `ty_unlock_checks` → `registry.vision_walk` →
`vision.chrome_uia`, which typed a route list into **whatever Chrome window held focus** — Profile 1
and then Profile 4 — and the owner wrote `state/vision/PAUSE` at 03:48 local. Every step refused the
wrong *page*; none of them checked the *profile*.

So these tests pin the guard that closes it, and the one exemption that keeps the test lane alive.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _extra in (str(ROOT), str(ROOT / "tools")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

from tools.vision import browse_guard  # noqa: E402
from tools.vision.browse_guard import (  # noqa: E402
    CDP,
    PLAYWRIGHT_HEADED,
    PLAYWRIGHT_HEADLESS,
    UIA,
    ToolRefused,
    may_browse,
    playwright_guard,
)


@pytest.fixture()
def pause(tmp_path, monkeypatch):
    path = tmp_path / "PAUSE"
    monkeypatch.setattr(browse_guard, "PAUSE", path, raising=False)
    return path


def test_without_a_pause_every_kind_is_allowed(pause):
    for kind in (UIA, CDP, PLAYWRIGHT_HEADED, PLAYWRIGHT_HEADLESS):
        allowed, reason = may_browse(kind, "https://example.com")
        assert allowed, kind
        assert reason == ""


def test_with_a_pause_uia_on_a_real_chrome_window_is_refused(pause):
    pause.write_text("owner paused browser work", encoding="utf-8")
    allowed, reason = may_browse(UIA, "http://127.0.0.1:8101/ui/")
    # even loopback: UIA types into whichever profile is focused, which is how Profiles 1 and 4
    # were opened. The URL is not the danger; the window is.
    assert allowed is False
    assert "PAUSE" in reason


def test_with_a_pause_cdp_and_headed_playwright_are_refused(pause):
    pause.write_text("x", encoding="utf-8")
    assert may_browse(CDP, "http://127.0.0.1:8101/ui/")[0] is False
    assert may_browse(PLAYWRIGHT_HEADED, "http://127.0.0.1:8101/ui/")[0] is False


def test_headless_playwright_on_loopback_is_the_one_exemption(pause):
    pause.write_text("x", encoding="utf-8")
    for url in ("http://127.0.0.1:8101/ui/", "http://localhost:8000/health", "http://[::1]:8101/"):
        allowed, reason = may_browse(PLAYWRIGHT_HEADLESS, url)
        assert allowed, (url, reason)


def test_headless_playwright_off_loopback_is_refused_and_names_only_the_host(pause):
    pause.write_text("x", encoding="utf-8")
    allowed, reason = may_browse(PLAYWRIGHT_HEADLESS, "https://example.com/secret?token=abc")
    assert allowed is False
    assert "example.com" in reason
    assert "token" not in reason  # the message never echoes a query string


def test_the_playwright_fixture_guard_refuses_a_headed_or_remote_run(pause, monkeypatch):
    pause.write_text("x", encoding="utf-8")
    monkeypatch.setenv("PWDEBUG", "1")
    with pytest.raises(ToolRefused):
        playwright_guard()
    monkeypatch.delenv("PWDEBUG")
    monkeypatch.setenv("PLAYWRIGHT_BASE_URL", "https://northstar.example")
    with pytest.raises(ToolRefused):
        playwright_guard()
    monkeypatch.setenv("PLAYWRIGHT_BASE_URL", "http://127.0.0.1:8101")
    playwright_guard()  # loopback is the permitted lane


def test_chrome_uia_refuses_before_it_touches_a_window(pause):
    """The wiring, not just the helper: `open_url` must return a refusal, not navigate."""
    from tools.vision.chrome_uia import ChromeUIA

    pause.write_text("x", encoding="utf-8")
    window = ChromeUIA.__new__(ChromeUIA)  # no window resolution, no UIA
    window.hwnd = 0
    result = window.open_url("http://127.0.0.1:8101/ui/")
    assert result["ok"] is False
    assert result["refused"] is True
    assert "PAUSE" in result["reason"]


def test_the_route_walk_refuses_by_name_and_touches_nothing(pause, tmp_path, monkeypatch):
    import tools.registry.vision_walk as walk

    pause.write_text("x", encoding="utf-8")

    def explode(*_args, **_kwargs):  # pragma: no cover - must never be reached
        raise AssertionError("the walk must not start while PAUSE exists")

    monkeypatch.setattr(walk, "walk", explode)
    out = tmp_path / "vision_live.json"
    code = walk.main(["--out", str(out)])
    assert code == 3
    payload = out.read_text(encoding="utf-8")
    assert "refused" in payload
    assert "PAUSE" in payload
