"""Single reusable network guard for offline test runs.

Consolidates the ad hoc ``requests``-blocking patches that previously lived
in ``test_network_guard.py`` and ``test_brain_orchestrator.py`` into ONE
module exposing ONE typed exception (:class:`NetworkGuardViolation`) so no
test run can silently drift into two incompatible guard behaviors.

How to use
----------
* Any offline test module that must block the real ``requests`` client can
  ``import network_guard`` and either:

  - call :func:`install` once (module level) to permanently patch the real
    client for the process, or
  - wrap a scoped block with :func:`block_network` (context manager) when the
    guard should apply to a narrow slice of code only.

* ``test_network_guard`` imports this module and calls :func:`install` at
  import time so the existing ``import test_network_guard`` contract used by
  the rest of the suite keeps working unchanged.

Design guarantees
-----------------
* ``NS_ALLOW_NETWORK=1`` bypasses the guard entirely (never set in CI; used by
  live-check scripts under ``temp/`` that are not test runs).
* The guard blocks 100% of real outbound ``requests`` calls — ``api.*`` and
  ``sessions.Session.request`` — because any unmocked call raises
  ``NetworkGuardViolation``.
* Tests must mock HTTP anyway; the guard only blocks the *real* client.
"""

import os
from contextlib import contextmanager

import requests

__all__ = [
    "NetworkGuardViolation",
    "install",
    "uninstall",
    "block_network",
]

_BLOCK_MESSAGE = (
    "Real network calls are disabled during test runs. Mock all "
    "HTTP clients (requests) in tests; check .env fallback "
    "settings (SCANNER_SEARCH_FALLBACK etc.)."
)

_HTTP_METHODS = ("get", "post", "put", "delete", "patch", "head", "options", "request")


class NetworkGuardViolation(RuntimeError):
    """Raised when real outbound HTTP is attempted during an offline test.

    A ``RuntimeError`` subclass so existing ``assertRaises(RuntimeError)``
    checks keep working; raising one typed exception means callers can rely
    on a single guard instead of matching several ad hoc error types.
    """


def _blocked(*args, **kwargs):
    raise NetworkGuardViolation(_BLOCK_MESSAGE)


# State: the original request entrypoints we patched, so uninstall() can
# restore the real client exactly.
_installed = False
_original_api = {}
_original_session_request = None


def install():
    """Patch ``requests`` so any unmocked call raises NetworkGuardViolation.

    Idempotent: calling more than once is a no-op. Restore the real client
    with :func:`uninstall`.
    """
    global _installed, _original_session_request
    if _installed:
        return
    for _name in _HTTP_METHODS:
        _original_api[_name] = getattr(requests.api, _name, None)
        setattr(requests.api, _name, _blocked)
    _original_session_request = requests.sessions.Session.request
    requests.sessions.Session.request = _blocked
    _installed = True


def uninstall():
    """Restore the real ``requests`` client (undo :func:`install`)."""
    global _installed
    if not _installed:
        return
    for _name, _original in _original_api.items():
        if _original is not None:
            setattr(requests.api, _name, _original)
    if _original_session_request is not None:
        requests.sessions.Session.request = _original_session_request
    _original_api.clear()
    _installed = False


@contextmanager
def block_network():
    """Context manager: block all real outbound requests inside the block.

    Installs the guard on entry; on exit the previous guard state is
    restored. If a process-wide guard was already active before the block
    (e.g. sitecustomize or a module import installed it), it is left in
    place — only guards installed by this block are torn down.
    """
    was_installed = _installed
    install()
    try:
        yield
    finally:
        if not was_installed:
            uninstall()


# Auto-install for test processes (import-time), matching the historical
# behavior of test_network_guard and sitecustomize: ``python -m unittest``
# adds CWD to sys.path only after startup, so importing the guard explicitly
# from each offline test module is what guarantees the patch is active.
if os.environ.get("NS_ALLOW_NETWORK") != "1":
    install()