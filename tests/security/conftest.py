"""Phase 1 security test harness.

Every later phase of the Secure Control-Layer build must keep this suite green
(Phase 1 acceptance). All tests here are offline: no network, no secrets, no
writes outside temp dirs.

Run from the repo root:

    python -m pytest tests/security -q
"""
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
