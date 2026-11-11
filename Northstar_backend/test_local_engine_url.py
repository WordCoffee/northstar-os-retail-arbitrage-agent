"""Tests for the shared Ollama host normaliser.

Regression origin: `OLLAMA_HOST=0.0.0.0:11434` is a bind address, so the raw
value is not a URL. `/api/v1/models` caught the resulting UnsupportedProtocol
and reported `installed: []` while Ollama was up with 14 tags — the AutothinK
page rendered "no models detected" next to a live engine.
"""

import pytest

import local_engine_url as leu


@pytest.mark.parametrize("raw,expected", [
    # Ollama's documented server-side value: bare host:port
    ("0.0.0.0:11434", "http://127.0.0.1:11434"),
    ("127.0.0.1:11434", "http://127.0.0.1:11434"),
    ("localhost:11434", "http://localhost:11434"),
    # IPv6 wildcard is a bind address too
    ("[::]:11434", "http://127.0.0.1:11434"),
    # a real URL is passed through (trailing slash trimmed)
    ("http://127.0.0.1:11434/", "http://127.0.0.1:11434"),
    ("http://0.0.0.0:11434", "http://127.0.0.1:11434"),
    # whitespace around the value
    ("  0.0.0.0:11434  ", "http://127.0.0.1:11434"),
    # non-default port is kept
    ("0.0.0.0:8080", "http://127.0.0.1:8080"),
])
def test_host_is_normalised_to_a_client_url(raw, expected):
    assert leu.normalise_host(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_empty_value_means_default_engine(raw):
    assert leu.normalise_host(raw) == leu.DEFAULT_BASE_URL == "http://127.0.0.1:11434"


def test_a_bind_address_never_survives_as_the_destination():
    """The exact failure: httpx refused the URL because it had no scheme."""
    url = leu.normalise_host("0.0.0.0:11434")
    assert "://" in url
    assert "0.0.0.0" not in url


def test_env_precedence_and_blank_skipping():
    env = {"OLLAMA_BASE_URL": "  ", "TY_OLLAMA_URL": "0.0.0.0:8080",
           "OLLAMA_HOST": "127.0.0.1:11434"}
    assert leu.ollama_base_url(env) == "http://127.0.0.1:8080"


def test_first_configured_env_wins():
    env = {"OLLAMA_BASE_URL": "http://10.0.0.5:11434", "OLLAMA_HOST": "0.0.0.0:11434"}
    assert leu.ollama_base_url(env) == "http://10.0.0.5:11434"


def test_no_env_at_all_falls_back_to_loopback():
    assert leu.ollama_base_url({}) == "http://127.0.0.1:11434"
