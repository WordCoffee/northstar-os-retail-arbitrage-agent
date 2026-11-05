"""The research lane: refusals come first, results are journaled, licences are read.

No test here makes a network call. The Amazon guard is asserted *before* any
transport is touched, which is the property that matters: a denylist that is
checked after the request is not a denylist.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import web_research as wr  # noqa: E402


@pytest.mark.parametrize("url", [
    "https://www.amazon.com/dp/B01FYY3M38",
    "https://amazon.co.uk/gp/product/x",
    "https://smile.amazon.com/",
    "https://amzn.to/3xyz",
    "https://media-amazon.com/images/I/x.jpg",
    "https://www.amazon.com.evil.test/dp/x",
])
def test_amazon_hosts_are_refused(url):
    with pytest.raises(wr.Refused) as exc:
        wr.guard(url)
    assert "amazon_refused" in str(exc.value)


def test_amazon_is_refused_without_any_transport():
    """A refusal must not depend on the network being up (or being tried)."""
    def explode(*_a, **_k):
        raise AssertionError("transport was attempted for a refused host")

    original = wr.urllib.request.urlopen
    wr.urllib.request.urlopen = explode
    try:
        with pytest.raises(wr.Refused):
            wr.fetch_page("https://www.amazon.com/dp/B01FYY3M38")
    finally:
        wr.urllib.request.urlopen = original


@pytest.mark.parametrize("url", [
    "https://github.com/block/goose",
    "https://huggingface.co/black-forest-labs/FLUX.2-klein",
    "https://raw.githubusercontent.com/block/goose/HEAD/README.md",
])
def test_non_amazon_hosts_pass_the_guard(url):
    assert wr.guard(url) == url


def test_relative_and_exotic_schemes_are_refused():
    for url in ("", "github.com/block/goose", "file:///C:/secret.txt",
                "ftp://example.com/x"):
        with pytest.raises(wr.Refused):
            wr.guard(url)


def test_amazon_lookalike_inside_a_path_is_not_a_block():
    """Blocking is by host, not by substring, so a query param cannot trip it."""
    assert wr.guard("https://github.com/search?q=amazon.com") == \
        "https://github.com/search?q=amazon.com"


def test_a_different_domain_that_merely_contains_the_word_is_allowed():
    """Over-blocking is its own failure: notamazon.com.evil.test is not Amazon."""
    assert wr.guard("https://notamazon.com.evil.test/") == \
        "https://notamazon.com.evil.test/"


def test_audit_log_records_a_request(tmp_path, monkeypatch):
    log = tmp_path / "web_research.jsonl"
    monkeypatch.setattr(wr, "AUDIT_LOG", log)
    wr._log({"action": "http", "url": "https://github.com/x", "status": 200})
    rows = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert rows[0]["url"] == "https://github.com/x"
    assert rows[0]["status"] == 200
    assert rows[0]["at"]


def test_license_classification_reads_the_text():
    assert wr.classify_license("MIT License\n\nPermission is hereby granted, "
                               "free of charge") == "MIT"
    assert wr.classify_license("Apache License\nVersion 2.0, January 2004") == "Apache-2.0"
    assert wr.classify_license("GNU AFFERO GENERAL PUBLIC LICENSE") == "AGPL-3.0"
    assert wr.classify_license("FLUX.1 [dev] Non-Commercial License") == "NON-COMMERCIAL"
    assert wr.classify_license("all rights reserved by me") == "unclassified"


def test_provenance_refuses_a_guessed_licence(tmp_path, monkeypatch):
    target = tmp_path / "provenance.csv"
    monkeypatch.setattr(wr, "PROVENANCE", target)
    with pytest.raises(ValueError):
        wr.log_provenance("thing", source="https://x", license_="unknown")
    wr.log_provenance("thing", source="https://x", license_="MIT", notes="ok")
    rows = list(csv.DictReader(target.read_text(encoding="utf-8").splitlines()))
    assert rows[0]["component"] == "thing"
    assert rows[0]["license"] == "MIT"
