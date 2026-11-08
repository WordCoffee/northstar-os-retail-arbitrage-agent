"""Seeded still mode for visual capture.

Animations are the single biggest source of visual-regression flake: a card
fading in at 300 ms screenshots differently at 250 ms and at 400 ms. The gate
therefore never captures a "live" scene. It captures a *frozen* one, in three
independent layers, so that no single layer has to be trusted:

1.  **URL contract** — every capture navigates to ``?still=1&seed=<n>``. The UI
    does not honour it yet; when it does, the same URL will also freeze its own
    data and animation clock. Documented in the README and in the D10 report.
2.  **Init script** — this module's :func:`still_init_script`, installed with
    ``page.add_init_script`` so it runs before any application code on every
    document. It pauses every animation, removes every transition, freezes
    ``Date``/``performance.now`` to a fixed instant, and seeds ``Math.random``
    with a mulberry32 generator. It works on an app that has never heard of
    ``still=1``.
3.  **Screenshot options** — Playwright's ``animations="disabled"`` fast-forwards
    finite animations and cancels infinite ones, and ``caret="hide"`` removes
    the text caret.

Layer 2 alone is enough for determinism on a page that renders synchronously;
layer 3 covers entrance animations that only reach their resting state by
finishing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

#: Fixed instant for the frozen clock: 2026-11-08T12:00:00Z.
FROZEN_EPOCH_MS = 1794139200000  # Date.UTC(2026, 10, 8, 12, 0, 0)
FROZEN_EPOCH_ISO = "2026-11-08T12:00:00Z"

#: The seed used when a caller does not name one. Kept non-zero so a stray
#: ``seed=0`` is distinguishable from "no seed".
DEFAULT_SEED = 20261108


@dataclass(frozen=True)
class StillMode:
    """The freeze contract for one view."""

    still: str = "1"
    seed: int = DEFAULT_SEED

    def as_query(self) -> Dict[str, str]:
        return {"still": self.still, "seed": str(self.seed)}


def seed_from_id(view_id: str) -> int:
    """Deterministic seed for a view id.

    crc32, not ``hash()``: Python hash randomisation would change the seed
    between processes and make a "frozen" scene differ run to run.
    """
    import zlib

    return 100_000 + (zlib.crc32(view_id.encode("utf-8")) % 900_000)


def build_still_url(route: str, still: str = "1", seed: int = DEFAULT_SEED) -> str:
    """Add ``still``/``seed`` to a route, preserving its query and fragment.

    ``/beta#support`` must keep its fragment *after* the query string, or the
    browser never scrolls to the anchor::

        >>> build_still_url("/beta#support", seed=7)
        '/beta?still=1&seed=7#support'
    """
    parts = urlsplit(route)
    if not parts.path.startswith("/"):
        raise ValueError(f"route must be absolute: {route!r}")
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["still"] = str(still)
    query["seed"] = str(seed)
    return urlunsplit(("", "", parts.path, urlencode(query), parts.fragment))


def still_init_script(seed: int = DEFAULT_SEED) -> str:
    """JavaScript installed as a Playwright init script (runs before app code).

    The URL seed wins over the injected seed, so a capture of
    ``?seed=42`` renders seed 42 even if the runner passed something else.
    """
    if int(seed) < 0:
        raise ValueError("seed must be non-negative")
    return _INIT_TEMPLATE.replace("__SEED__", str(int(seed))).replace(
        "__FROZEN_MS__", str(FROZEN_EPOCH_MS)
    )


_INIT_TEMPLATE = """(() => {
  'use strict';
  const INJECTED_SEED = __SEED__;
  const FROZEN_MS = __FROZEN_MS__;

  const params = new URLSearchParams(location.search);
  const urlSeed = params.get('seed');
  const seed = urlSeed !== null && /^\\d+$/.test(urlSeed)
    ? (Number(urlSeed) >>> 0)
    : (INJECTED_SEED >>> 0);

  // --- seeded PRNG (mulberry32) -------------------------------------------
  let state = (seed + 0x6D2B79F5) >>> 0;
  const rand = function () {
    state = (state + 0x6D2B79F5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  try { Math.random = rand; } catch (e) { /* frozen property: harmless */ }

  // --- frozen clock --------------------------------------------------------
  const RealDate = Date;
  function FrozenDate(...args) {
    if (args.length === 0) return new RealDate(FROZEN_MS);
    return new RealDate(...args);
  }
  FrozenDate.prototype = RealDate.prototype;
  FrozenDate.now = () => FROZEN_MS;
  FrozenDate.parse = RealDate.parse;
  FrozenDate.UTC = RealDate.UTC;
  try { window.Date = FrozenDate; } catch (e) {}
  try {
    const t0 = FROZEN_MS;
    performance.now = () => 0;
    if (performance.timeOrigin !== undefined) {
      Object.defineProperty(performance, 'timeOrigin', { get: () => t0, configurable: true });
    }
  } catch (e) {}

  // --- paused everything ---------------------------------------------------
  const CSS = `
    *, *::before, *::after {
      animation-play-state: paused !important;
      transition: none !important;
      transition-duration: 0s !important;
      animation-delay: -1ms !important;
      caret-color: transparent !important;
      scroll-behavior: auto !important;
    }
    html { scroll-behavior: auto !important; }
    ::-webkit-scrollbar { display: none !important; }
    html, body { overflow-anchor: none !important; }
  `;
  let styleEl = null;
  function installStyle() {
    const doc = document;
    if (!doc.documentElement) return false;
    if (styleEl && styleEl.isConnected) return true;
    styleEl = doc.createElement('style');
    styleEl.setAttribute('data-ns-still', '1');
    styleEl.textContent = CSS;
    (doc.head || doc.documentElement).appendChild(styleEl);
    return true;
  }
  installStyle();
  document.addEventListener('DOMContentLoaded', installStyle, { once: true });

  const root = document.documentElement;
  if (root) {
    root.setAttribute('data-ns-still', '1');
    root.setAttribute('data-ns-seed', String(seed));
  }
  window.__NS_STILL__ = { still: true, seed, frozenAt: FROZEN_MS, source: 'tools/visual_regression/freeze.py' };
})();
"""
