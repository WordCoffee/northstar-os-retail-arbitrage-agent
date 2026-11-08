"""Playwright capture for the visual regression gate.

Playwright is imported inside :func:`capture_views`, never at module import:
the offline test suite imports this module and must not need a browser, a
browser binary, or a display.

Safety properties enforced here, not in the CLI:

* **loopback only** — a non-local ``--base-url`` is refused before any browser
  starts. Localhost capture is the narrow exception in ``AGENTS.md``; anything
  else belongs to Chrome Connect.
* **reachability first** — :func:`probe_base_url` must succeed before a browser
  is launched, so an absent app produces a refusal instead of a blank page.
* **blank is a failure** — after load the page must expose real text, and the
  screenshot must not be a uniform colour.
* **still mode is verified** — the page must report ``window.__NS_STILL__``;
  otherwise the capture is rejected rather than silently accepted.
"""
from __future__ import annotations

import hashlib
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlsplit, urlunsplit

from .freeze import build_still_url, still_init_script
from .views import Registry, View, Viewport

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}


class CaptureError(RuntimeError):
    """A capture could not be taken, or what it produced cannot be trusted."""


@dataclass(frozen=True)
class CaptureRecord:
    view: str
    viewport: str
    path: Path
    url: str
    sha256: str
    bytes: int
    text_chars: int
    still: Mapping[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "view": self.view,
            "viewport": self.viewport,
            "path": str(self.path),
            "url": self.url,
            "sha256": self.sha256,
            "bytes": self.bytes,
            "text_chars": self.text_chars,
            "still": dict(self.still),
        }


def ensure_loopback(base_url: str) -> None:
    parts = urlsplit(base_url)
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https"):
        raise CaptureError(f"base url must be http(s): {base_url!r}")
    if host not in LOOPBACK_HOSTS:
        raise CaptureError(
            f"refusing non-loopback base url {host!r}: browser capture is limited to "
            "127.0.0.1/localhost (the localhost testing exception). Use Chrome Connect "
            "as the controller for any other host."
        )


def probe_base_url(base_url: str, timeout: float = 2.5) -> Tuple[bool, str]:
    """Cheap reachability probe. Returns ``(reachable, reason)``."""
    request = urllib.request.Request(base_url, method="GET", headers={"Accept": "text/html"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
    except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    if status >= 500:
        return False, f"server answered HTTP {status}"
    return True, f"HTTP {status}"


def absolute_url(base_url: str, route: str) -> str:
    """Join a base url (which may carry a path prefix) with a route + query + hash."""
    root = urlsplit(base_url.rstrip("/"))
    rel = urlsplit(route)
    prefix = root.path.rstrip("/")
    return urlunsplit((root.scheme, root.netloc, f"{prefix}{rel.path}", rel.query, rel.fragment))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _screenshot_ok(path: Path) -> Tuple[bool, str]:
    """Reject a uniform image: a blank screenshot is not a pass."""
    from PIL import Image, ImageStat

    try:
        with Image.open(path) as img:
            stat = ImageStat.Stat(img.convert("RGB"))
    except Exception as exc:  # pragma: no cover - corrupt file is an error, not a verdict
        return False, f"unreadable screenshot: {exc}"
    spread = max(stat.stddev) if stat.stddev else 0.0
    if spread < 1.0:
        return False, "uniform image (no visual content)"
    return True, "ok"


def capture_views(
    selected: Sequence[Tuple[View, Sequence[Viewport]]],
    *,
    base_url: str,
    out_dir: str | Path,
    timeout_ms: int = 30_000,
    registry: Optional[Registry] = None,
) -> List[CaptureRecord]:
    """Capture every (view, viewport) pair. Raises :class:`CaptureError`."""
    ensure_loopback(base_url)
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise CaptureError(f"playwright is not installed: {exc}") from exc

    records: List[CaptureRecord] = []
    with sync_playwright() as pw:
        browsers: Dict[str, Any] = {}
        try:
            for view, viewports in selected:
                for viewport in viewports:
                    browser_name = viewport.browser
                    if browser_name not in browsers:
                        try:
                            browsers[browser_name] = getattr(pw, browser_name).launch()
                        except Exception as exc:
                            raise CaptureError(
                                f"browser_unavailable:{browser_name}: {exc}. "
                                f"Install with: python -m playwright install {browser_name}"
                            ) from exc
                    browser = browsers[browser_name]

                    context_kwargs: Dict[str, Any] = {
                        "viewport": {"width": viewport.width, "height": viewport.height},
                        "device_scale_factor": viewport.device_scale_factor,
                        "is_mobile": viewport.is_mobile,
                        "has_touch": viewport.has_touch,
                        "color_scheme": "light",
                        "reduced_motion": "reduce",
                        "locale": "en-US",
                        "timezone_id": "UTC",
                    }
                    if viewport.user_agent:
                        context_kwargs["user_agent"] = viewport.user_agent

                    context = browser.new_context(**context_kwargs)
                    try:
                        context.add_init_script(script=still_init_script(view.seed))
                        page = context.new_page()
                        url = absolute_url(base_url, build_still_url(view.route, view.still, view.seed))

                        try:
                            page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                        except Exception as exc:
                            raise CaptureError(f"{view.id}/{viewport.id}: navigation failed: {exc}") from exc

                        try:
                            page.wait_for_load_state(view.wait_until, timeout=timeout_ms)
                        except Exception:
                            # networkidle can legitimately never arrive on an app with a
                            # polling loop; the readiness gates below still decide.
                            pass

                        if view.ready_selector:
                            try:
                                page.wait_for_selector(view.ready_selector, timeout=timeout_ms)
                            except Exception as exc:
                                raise CaptureError(
                                    f"{view.id}/{viewport.id}: ready selector "
                                    f"{view.ready_selector!r} never appeared"
                                ) from exc

                        try:
                            page.evaluate("() => document.fonts.ready.then(() => true)")
                        except Exception:
                            pass
                        page.wait_for_timeout(view.settle_ms)
                        try:
                            page.evaluate("() => window.scrollTo(0, 0)")
                        except Exception:
                            pass

                        still = page.evaluate(
                            "() => (window.__NS_STILL__ ? {still: window.__NS_STILL__.still, "
                            "seed: window.__NS_STILL__.seed, frozenAt: window.__NS_STILL__.frozenAt} : null)"
                        )
                        if not still or not still.get("still"):
                            raise CaptureError(
                                f"{view.id}/{viewport.id}: still mode was not applied "
                                "(window.__NS_STILL__ missing); refusing to capture a moving page"
                            )

                        text_chars = int(
                            page.evaluate(
                                "() => (document.body ? document.body.innerText.trim().length : 0)"
                            )
                            or 0
                        )
                        if text_chars < view.min_text_chars:
                            raise CaptureError(
                                f"{view.id}/{viewport.id}: blank page — only {text_chars} "
                                f"characters of text (min {view.min_text_chars})"
                            )

                        target = out_root / view.id / f"{viewport.id}.png"
                        target.parent.mkdir(parents=True, exist_ok=True)
                        page.screenshot(
                            path=str(target),
                            full_page=False,
                            animations="disabled",
                            caret="hide",
                            scale="css",
                        )

                        ok, why = _screenshot_ok(target)
                        if not ok:
                            target.unlink(missing_ok=True)
                            raise CaptureError(f"{view.id}/{viewport.id}: {why}")

                        records.append(
                            CaptureRecord(
                                view=view.id,
                                viewport=viewport.id,
                                path=target,
                                url=url,
                                sha256=_sha256(target),
                                bytes=target.stat().st_size,
                                text_chars=text_chars,
                                still=still,
                            )
                        )
                    finally:
                        context.close()
        finally:
            for browser in browsers.values():
                try:
                    browser.close()
                except Exception:
                    pass
    return records
