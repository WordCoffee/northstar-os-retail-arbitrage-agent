from config import DEFAULTS, coerce, get, load


def test_defaults_are_the_documented_values():
    assert DEFAULTS["max_retries"] == 3
    assert DEFAULTS["timeout_seconds"] == 30
    assert DEFAULTS["read_only"] is True


def test_unknown_key_returns_the_default():
    assert get("no_such_setting") is None
    assert get("no_such_setting", "fallback") == "fallback"


def test_load_without_environ_is_the_defaults():
    assert load() == DEFAULTS
    assert load({}) == DEFAULTS


def test_environ_overrides_and_coerces():
    settings = load({"max_retries": "5", "read_only": "false"})
    assert settings["max_retries"] == 5
    assert settings["read_only"] is False


def test_coerce_shapes():
    assert coerce("6") == 6
    assert coerce("on") is True
    assert coerce("off") is False
    assert coerce("ledger") == "ledger"
