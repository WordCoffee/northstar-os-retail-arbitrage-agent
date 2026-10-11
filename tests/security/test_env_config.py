"""Phase 1 tests — environment-only config loader.

All values here are OBVIOUSLY FAKE. No real credential appears in this file.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from northstar.security.env_config import (
    BACKENDS,
    MissingSecretError,
    get_secret,
    redacted_summary,
    require_secret,
    secret_presence,
)

FAKE_VALUE = "FAKEtopsecret12345"


class TestContract:
    def test_env_is_the_only_backend_today(self):
        assert BACKENDS == ("env",)

    def test_source_never_reads_dotenv(self):
        # Regression guard: the loader must stay env-only. AST check (not a
        # text grep) so the module's own docstring may mention dotenv.
        src = (
            Path(__file__).resolve().parents[2]
            / "northstar"
            / "security"
            / "env_config.py"
        )
        tree = ast.parse(src.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "dotenv" not in alias.name
            elif isinstance(node, ast.ImportFrom):
                assert "dotenv" not in (node.module or "")
            elif isinstance(node, ast.Call):
                func = node.func
                called = getattr(func, "id", None) or getattr(func, "attr", None)
                assert called != "load_dotenv"


class TestGetSecret:
    def test_reads_process_env(self, monkeypatch):
        monkeypatch.setenv("NS_TEST_SECRET", FAKE_VALUE)
        assert get_secret("NS_TEST_SECRET") == FAKE_VALUE

    def test_missing_returns_none_and_default(self, monkeypatch):
        monkeypatch.delenv("NS_TEST_SECRET", raising=False)
        assert get_secret("NS_TEST_SECRET") is None
        assert get_secret("NS_TEST_SECRET", default="fallback") == "fallback"

    def test_required_raises_when_missing(self, monkeypatch):
        monkeypatch.delenv("NS_TEST_SECRET", raising=False)
        with pytest.raises(MissingSecretError):
            require_secret("NS_TEST_SECRET")

    def test_whitespace_only_counts_as_missing(self, monkeypatch):
        monkeypatch.setenv("NS_TEST_SECRET", "   ")
        assert get_secret("NS_TEST_SECRET") is None
        with pytest.raises(MissingSecretError):
            require_secret("NS_TEST_SECRET")

    def test_value_is_trimmed(self, monkeypatch):
        monkeypatch.setenv("NS_TEST_SECRET", f"  {FAKE_VALUE}\n")
        assert get_secret("NS_TEST_SECRET") == FAKE_VALUE

    def test_invalid_names_are_rejected(self):
        with pytest.raises(ValueError):
            get_secret("BAD NAME!")
        with pytest.raises(ValueError):
            secret_presence(["BAD-NAME"])


class TestPresenceReporting:
    def test_presence_map_and_summary_never_leak_values(self, monkeypatch):
        monkeypatch.setenv("NS_TEST_SECRET", FAKE_VALUE)
        monkeypatch.delenv("NS_TEST_MISSING", raising=False)

        presence = secret_presence(["NS_TEST_SECRET", "NS_TEST_MISSING"])
        assert presence == {"NS_TEST_SECRET": True, "NS_TEST_MISSING": False}

        summary = redacted_summary(["NS_TEST_SECRET", "NS_TEST_MISSING"])
        assert "NS_TEST_SECRET=SET" in summary
        assert "NS_TEST_MISSING=MISSING" in summary
        assert FAKE_VALUE not in summary
