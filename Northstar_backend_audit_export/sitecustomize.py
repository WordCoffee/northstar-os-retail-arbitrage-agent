"""Structural network guard for test runs.

Python imports this at interpreter startup when this directory is the
script's directory (direct ``python test_x.py`` runs). For
``python -m unittest`` runs the CWD is added to sys.path only after
startup, so every test module also imports ``test_network_guard``
explicitly — same patch, guaranteed active under any runner.

When a test run is detected, every real ``requests`` call raises
``NetworkDisabledError`` — so no .env fallback misconfiguration
(SCANNER_SEARCH_FALLBACK, SCANNER_OFFER_ENRICHMENT, live keys) can ever
trigger a real network call that burns credits or leaks secrets from the
suite. Tests must mock HTTP; the guard only blocks the real client.

Set NS_ALLOW_NETWORK=1 to bypass (never in CI; live-check scripts in
``temp/`` are not affected because they are not test runs).
"""

import os
import sys

_TEST_RUN = False
if os.environ.get("NS_ALLOW_NETWORK") != "1":
    arg0 = (sys.argv[0] or "").lower()
    if "unittest" in arg0 or "pytest" in arg0:
        _TEST_RUN = True
    elif os.path.basename(arg0).startswith("test"):
        _TEST_RUN = True

if _TEST_RUN:
    try:
        import requests

        class NetworkDisabledError(RuntimeError):
            pass

        def _blocked(*args, **kwargs):
            raise NetworkDisabledError(
                "Real network calls are disabled during test runs. Mock all "
                "HTTP clients (requests) in tests; check .env fallback "
                "settings (SCANNER_SEARCH_FALLBACK etc.)."
            )

        for _name in ("get", "post", "put", "delete", "patch", "head", "options", "request"):
            setattr(requests.api, _name, _blocked)
        requests.sessions.Session.request = _blocked
    except ImportError:
        pass
