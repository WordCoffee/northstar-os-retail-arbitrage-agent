"""Phase 1 — end-to-end wiring check: ``logging_config`` emits redacted logs.

Verifies that ``Northstar_backend/logging_config.py`` wraps its formatter and
adds the redaction filter, for both the dev and json formats.
"""
from __future__ import annotations

import importlib
import logging

import pytest

from northstar.security.redaction import (
    REDACTED,
    RedactionFilter,
    RedactingFormatter,
)

FAKE_KEY = "sk-FAKEFAKEFAKEFAKE123456"


@pytest.fixture()
def restore_root_logger():
    root = logging.getLogger()
    handlers = list(root.handlers)
    level = root.level
    yield root
    root.handlers[:] = handlers
    root.setLevel(level)


@pytest.mark.parametrize("log_format", ["dev", "json"])
def test_setup_logging_redacts_secrets(
    monkeypatch, capsys, restore_root_logger, log_format
):
    monkeypatch.setenv("LOG_FORMAT", log_format)
    logging_config = importlib.import_module("Northstar_backend.logging_config")
    logging_config.setup_logging()

    root = restore_root_logger
    assert len(root.handlers) == 1, "setup_logging installs exactly one handler"
    handler = root.handlers[0]
    assert isinstance(handler.formatter, RedactingFormatter)
    assert any(isinstance(f, RedactionFilter) for f in handler.filters)

    logging.getLogger("phase1.wiring.test").error("Authorization: Bearer %s", FAKE_KEY)

    output = capsys.readouterr().out
    assert FAKE_KEY not in output
    assert REDACTED in output
