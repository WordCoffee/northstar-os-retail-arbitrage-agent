"""Phase 1 tests — environment-only config loader.

All values here are OBVIOUSLY FAKE. No real credential appears in this file.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from northstar.security.env_config import (
    BACKENDS,
    ENV_FILE_VAR,
    EnvFileMissingError,
    EnvFileNotConfiguredError,
    MissingSecretError,
    env_file_path,
    get_secret,
    redacted_summary,
    require_env_file,
    require_secret,
    secret_presence,
)

FAKE_VALUE = "FAKE-TEST-secret-12345"


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


class TestEnvFileSource:
    """NORTHSTAR_ENV_FILE: path-var-driven, fail-closed, names-only checks."""

    def test_env_file_var_drives_the_path(self, tmp_path, monkeypatch):
        env_file = tmp_path / "secrets.env"
        env_file.write_text("", encoding="utf-8")
        monkeypatch.setenv(ENV_FILE_VAR, str(env_file))
        assert env_file_path() == env_file

    def test_require_env_file_raises_clearly_when_unset(self, monkeypatch):
        monkeypatch.delenv(ENV_FILE_VAR, raising=False)
        with pytest.raises(EnvFileNotConfiguredError) as excinfo:
            require_env_file()
        message = str(excinfo.value)
        assert ENV_FILE_VAR in message
        assert FAKE_VALUE not in message

    def test_require_env_file_raises_clearly_when_missing(self, tmp_path, monkeypatch):
        missing = tmp_path / "not-here.env"
        monkeypatch.setenv(ENV_FILE_VAR, str(missing))
        with pytest.raises(EnvFileMissingError) as excinfo:
            require_env_file()
        message = str(excinfo.value)
        assert ENV_FILE_VAR in message
        assert str(missing) not in message  # the path is never echoed
        assert FAKE_VALUE not in message

    def test_file_backed_lookup_and_env_precedence(self, tmp_path, monkeypatch):
        env_file = tmp_path / "secrets.env"
        env_file.write_text(
            "# comment\n"
            "\n"
            f"NS_FILE_SECRET={FAKE_VALUE}\n"
            "QUOTED='quotedfake123'\n"
            "export NS_EXPORTED=exportedfake99\n",
            encoding="utf-8",
        )
        monkeypatch.setenv(ENV_FILE_VAR, str(env_file))
        monkeypatch.delenv("NS_FILE_SECRET", raising=False)
        assert get_secret("NS_FILE_SECRET") == FAKE_VALUE
        assert get_secret("QUOTED") == "quotedfake123"
        assert get_secret("NS_EXPORTED") == "exportedfake99"
        monkeypatch.setenv("NS_FILE_SECRET", "FAKE-TEST-env-wins")
        assert get_secret("NS_FILE_SECRET") == "FAKE-TEST-env-wins"

    def test_presence_boolean_considers_file_and_never_values(
        self, tmp_path, monkeypatch
    ):
        env_file = tmp_path / "secrets.env"
        env_file.write_text(f"NS_FILE_ONLY={FAKE_VALUE}\n", encoding="utf-8")
        monkeypatch.setenv(ENV_FILE_VAR, str(env_file))
        monkeypatch.delenv("NS_FILE_ONLY", raising=False)
        presence = secret_presence(["NS_FILE_ONLY", "NS_ABSENT_ONE"])
        assert presence == {"NS_FILE_ONLY": True, "NS_ABSENT_ONE": False}
        summary = redacted_summary(["NS_FILE_ONLY"])
        assert FAKE_VALUE not in summary

    def test_missing_file_does_not_break_lookups_and_required_still_fails_closed(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv(ENV_FILE_VAR, str(tmp_path / "gone.env"))
        monkeypatch.delenv("NS_OPTIONAL", raising=False)
        assert get_secret("NS_OPTIONAL") is None
        with pytest.raises(MissingSecretError):
            require_secret("NS_OPTIONAL")

    def test_require_env_file_returns_parsed_values(self, tmp_path, monkeypatch):
        env_file = tmp_path / "secrets.env"
        env_file.write_text(f"NS_PARSE_ONE={FAKE_VALUE}\n", encoding="utf-8")
        monkeypatch.setenv(ENV_FILE_VAR, str(env_file))
        parsed = require_env_file()
        assert parsed.get("NS_PARSE_ONE") == FAKE_VALUE
