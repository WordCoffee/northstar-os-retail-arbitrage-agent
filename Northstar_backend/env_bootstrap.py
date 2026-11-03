"""Authoritative ``.env`` loading for provider modules.

Why this exists
---------------
The repo-root ``.env`` is the file the operator edits. ``python-dotenv``'s bare
``load_dotenv()`` resolves from the *calling file's* directory, so every module
under ``Northstar_backend/`` actually reads ``Northstar_backend/.env`` — a
separate, older copy. When only the root file is updated, a standalone script
(``python bright_data_costco.py``, a probe, a cron lane) keeps using the stale
backend value and the freshly rotated key looks broken or missing.

This was logged as known issue ``dual_dotenv_divergence_backend_shadowing`` and
resolved in favour of "repo-root .env is authoritative; backend modules pin the
root file by explicit path". ``main.py`` already does that for the API process;
this helper gives every provider module the same behaviour.

Load order (``override=False`` everywhere, so a real process env always wins):

1. ``<repo>/.env``               — authoritative
2. ``<repo>/Northstar_backend/.env`` — only fills keys the root file omits

Credential hygiene: this module loads *values* into ``os.environ`` for the
process that needs them; it never reads, prints, returns or logs them.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List

BACKEND_DIR = Path(__file__).resolve().parent
REPO_ROOT = BACKEND_DIR.parent
ROOT_ENV = REPO_ROOT / ".env"
BACKEND_ENV = BACKEND_DIR / ".env"

_loaded: List[str] = []


def load_project_env() -> List[str]:
    """Load the project ``.env`` files in authoritative order.

    Safe to call repeatedly and from any module import — subsequent calls are
    no-ops. Missing files or a missing ``python-dotenv`` are tolerated (the
    app must never fail to start over an optional file). Returns the paths that
    were loaded on the first successful call (empty list on later calls).
    """
    if _loaded:
        return []

    try:
        from dotenv import load_dotenv
    except Exception:  # noqa: BLE001 - dotenv is optional at runtime
        return []

    for path in (ROOT_ENV, BACKEND_ENV):
        try:
            if path.exists():
                load_dotenv(path, override=False)
                _loaded.append(str(path))
        except Exception:  # noqa: BLE001 - never block import on a bad file
            continue

    return list(_loaded)


def env_source_report(names) -> dict:
    """Report which file each named variable came from, without values.

    Diagnostics only: compares the value in ``os.environ`` against the value in
    each ``.env`` file and returns ``{name: "root"|"backend"|"process"|"unset"}``.
    Values are compared in memory and never returned.
    """
    try:
        from dotenv import dotenv_values
    except Exception:  # noqa: BLE001
        return {name: "unknown" for name in names}

    root = dotenv_values(ROOT_ENV) if ROOT_ENV.exists() else {}
    backend = dotenv_values(BACKEND_ENV) if BACKEND_ENV.exists() else {}

    report = {}
    for name in names:
        current = os.environ.get(name, "")
        if not current:
            report[name] = "unset"
        elif root.get(name) and root.get(name) == current:
            report[name] = "root"
        elif backend.get(name) and backend.get(name) == current:
            report[name] = "backend"
        else:
            report[name] = "process"
    return report
