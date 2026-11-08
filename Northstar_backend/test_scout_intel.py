"""Offline tests for the D11 discovery lane (A18–A21).

Everything here runs with no socket:

* connector parsing is replayed from recorded fixtures,
* ranking/licence/vetting are pure functions,
* the dry run must never call the network and must never write,
* the Amazon guard is proven to fire *before* transport.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.scout import (  # noqa: E402
    collect, config, connectors, evidence, http, licence, normalize, rank, vet, verify,
)
from tools.scout.connectors.base import now, raw_hit  # noqa: E402
from tools.web_research import Refused  # noqa: E402

FIXTURES = config.FIXTURES
SOURCES = ("github", "huggingface", "pypi", "npm", "arxiv")


# --------------------------------------------------------------------- helpers
def fixture_for(source: str) -> dict:
    paths = sorted(FIXTURES.glob(f"{source}_*.json"))
    assert paths, f"no recorded fixture for {source}"
    return json.loads(paths[0].read_text(encoding="utf-8"))


def make_raw(**overrides) -> dict:
    values = {
        "source": "github",
        "identity": "acme/widget",
        "url": "https://github.com/acme/widget",
        "title": "acme/widget",
        "licence": "MIT",
        "description": "retail arbitrage sourcing and product research",
        "stars": 120,
    }
    values.update(overrides)
    return raw_hit(**values)


def prepared(**overrides) -> dict:
    """A normalised finding with vet + evidence, ready for ranking."""
    finding = normalize.normalise(make_raw(**overrides))
    finding["vet"] = {"checked": False, "verdict": "not_applicable"}
    finding["evidence"] = evidence.build(finding)
    return finding


# ------------------------------------------------------------------ connectors
@pytest.mark.parametrize("source", SOURCES)
def test_connector_parses_recorded_fixture(source):
    fixture = fixture_for(source)
    hits = connectors.get(source).parse(fixture["payload"], query=fixture["query"])
    assert hits, f"{source} fixture produced no hits"
    for hit in hits:
        for key in ("source", "url", "title", "licence", "fetched_at"):
            assert hit.get(key), f"{source} hit missing {key}"
        assert hit["source"] == source
        assert hit["url"].startswith("http")
        assert hit["licence"]
        assert hit["fetched_at"]


def test_github_missing_licence_is_unknown_not_permissive():
    payload = {"items": [
        {"full_name": "a/b", "html_url": "https://github.com/a/b",
         "license": None, "stargazers_count": 5},
        {"full_name": "c/d", "html_url": "https://github.com/c/d",
         "license": {"spdx_id": "NOASSERTION"}, "stargazers_count": 7},
    ]}
    hits = connectors.get("github").parse(payload)
    assert [hit["licence"] for hit in hits] == ["unknown", "unknown"]


def test_pypi_licence_falls_back_to_classifiers():
    payload = {"projects": [{"info": {
        "name": "demo", "version": "1.2.3", "license": "",
        "classifiers": ["License :: OSI Approved :: MIT License"],
        "package_url": "https://pypi.org/project/demo/",
    }}]}
    hit = connectors.get("pypi").parse(payload)[0]
    assert hit["licence"] == "MIT"
    assert hit["version"] == "1.2.3"
    assert hit["ecosystem"] == "PyPI"


def test_arxiv_hits_are_papers_with_unknown_licence_and_versions():
    fixture = fixture_for("arxiv")
    hits = connectors.get("arxiv").parse(fixture["payload"])
    assert hits
    assert all(hit["kind"] == "paper" for hit in hits)
    assert all(hit["licence"] == "unknown" for hit in hits)
    assert all(hit["url"].startswith("https://arxiv.org/abs/") for hit in hits)


# --------------------------------------------------------------------- licence
@pytest.mark.parametrize("raw,expected", [
    ("MIT", "MIT"),
    ("mit", "MIT"),
    ("Apache 2.0", "Apache-2.0"),
    ("Apache License, Version 2.0", "Apache-2.0"),
    ("BSD 3-Clause", "BSD-3-Clause"),
    ("GPL-3.0-only", "GPL-3.0"),
    ("AGPL-3.0", "AGPL-3.0"),
    ("GNU GENERAL PUBLIC LICENSE Version 3", "GPL-3.0"),
    ("GNU AFFERO GENERAL PUBLIC LICENSE", "AGPL-3.0"),
    ("CC-BY-NC-4.0", "CC-BY-NC-4.0"),
    ("non-commercial research only", "noncommercial"),
    ("NOASSERTION", "unknown"),
    ("none", "unknown"),
    ("", "unknown"),
    (None, "unknown"),
])
def test_licence_normalisation(raw, expected):
    assert licence.normalise(raw) == expected


def test_licence_classes_and_commercial_use():
    assert licence.classify("MIT") == "permissive"
    assert licence.classify("Unlicense") == "public-domain"
    assert licence.classify("MPL-2.0") == "weak-copyleft"
    assert licence.classify("AGPL-3.0") == "copyleft"
    assert licence.classify("CC-BY-NC-4.0") == "noncommercial"
    assert licence.classify("unknown") == "unknown"
    assert licence.commercial_ok("permissive") is True
    assert licence.commercial_ok("noncommercial") is False
    assert licence.is_adoptable_licence("MIT") is True
    assert licence.is_adoptable_licence("AGPL-3.0") is False
    assert licence.is_adoptable_licence("unknown") is False


# ---------------------------------------------------------------- vetting policy
@pytest.mark.parametrize("licence_id", ["unknown", "CC-BY-NC-4.0", "noncommercial"])
@pytest.mark.parametrize("verdict", ["clear", "not_applicable", "check_incomplete"])
def test_unknown_and_noncommercial_are_never_adopted(licence_id, verdict):
    canonical = licence.normalise(licence_id)
    status = vet.decide_status(
        licence=canonical,
        licence_class=licence.classify(canonical),
        vet={"verdict": verdict},
        relevance=1.0,
        kind="package",
    )
    assert status == "replace_later"
    assert vet.adopt_eligible(status) is False


def test_copyleft_is_review_not_adopt():
    status = vet.decide_status(licence="AGPL-3.0", licence_class="copyleft",
                               vet={"verdict": "clear"}, relevance=1.0)
    assert status == "review"


def test_malicious_package_is_rejected_even_with_clean_licence():
    status = vet.decide_status(licence="MIT", licence_class="permissive",
                               vet={"verdict": "malicious"}, relevance=1.0)
    assert status == "reject"


def test_incomplete_vet_is_never_adopt():
    status = vet.decide_status(licence="MIT", licence_class="permissive",
                               vet={"verdict": "check_incomplete"}, relevance=1.0)
    assert status == "review"


def test_papers_are_watch_never_adopt():
    status = vet.decide_status(licence="MIT", licence_class="permissive",
                               vet={"verdict": "not_applicable"},
                               relevance=1.0, kind="paper")
    assert status == "watch"


def test_vet_hit_records_transport_failure_as_incomplete():
    def failing(name, ecosystem, version):
        raise RuntimeError("osv_unreachable: timeout")

    result = vet.vet_hit({"title": "x", "ecosystem": "PyPI", "version": "1"}, vet_fn=failing)
    assert result["verdict"] == "check_incomplete"
    assert result["checked"] is False


def test_vet_hit_skips_non_packages():
    result = vet.vet_hit({"title": "a/b", "ecosystem": None, "source": "github"})
    assert result["verdict"] == "not_applicable"


# -------------------------------------------------------------------- ranking
def test_service_mapping_uses_keyword_evidence():
    services = config.load_services()
    hit = {"title": "x", "description": "product photography and background removal studio"}
    service_id, relevance, _ = rank.match_services(hit, services)
    assert service_id == "design-studio"
    assert relevance >= 0.3

    arbitrage = {"title": "y", "description": "retail arbitrage opportunity scanner for resale"}
    service_id, relevance, _ = rank.match_services(arbitrage, services)
    assert service_id in ("prospector", "goldengoose", "golden-goose")
    assert relevance >= 0.3


def test_ranking_prefers_gap_where_it_exists():
    services = config.load_services()
    # design-studio is at its bar (gap 0), thewatch is not (gap 50).
    design = prepared(identity="a/design", url="https://github.com/a/design",
                      description="background removal product photography studio",
                      stars=5000)
    watch = prepared(identity="b/watch", url="https://github.com/b/watch",
                     description="website change detection and monitoring alerts",
                     stars=40)
    ranked, dropped = rank.rank([design, watch], services,
                                gaps={"design-studio": 0.0, "thewatch": 50.0})
    assert not dropped and len(ranked) == 2
    assert [row["rank"] for row in ranked] == [1, 2]
    assert ranked[0]["service"] == "thewatch"
    assert ranked[0]["estimated_lift"] > ranked[1]["estimated_lift"]
    for row in ranked:
        assert row["estimated_lift"] <= float(row["gap_remaining"])


def test_off_domain_hit_is_dropped():
    services = config.load_services()
    crypto = prepared(identity="c/crypto", url="https://github.com/c/crypto",
                      description="real-time crypto price tracker for bitcoin", licence="MIT")
    ranked, dropped = rank.rank([crypto], services, gaps={})
    assert not ranked
    assert dropped[0]["drop_reason"].startswith("off_domain")


def test_gap_hypothesis_is_falsifiable_and_cited():
    services = config.load_services()
    finding = prepared(description="retail arbitrage opportunity scanner", stars=900)
    ranked, _ = rank.rank([finding], services, gaps={"prospector": 63.0})
    rows = rank.gaps_from(ranked, services)
    assert rows
    hypothesis = rows[0]["hypothesis"]
    assert "expect up to" in hypothesis and "pts" in hypothesis
    assert rows[0]["yield_score"] <= 63.0


# --------------------------------------------------------------------- dedupe
def test_dedupe_identical_hits_counts_duplicates():
    raw = [make_raw(), make_raw()]
    unique, report = normalize.dedupe(raw)
    assert len(unique) == 1
    assert report["duplicates"] == 1
    assert report["revisions"] == 0


def test_dedupe_different_content_is_a_revision_not_a_duplicate():
    first = make_raw(description="first description")
    second = make_raw(description="second description",
                      fetched_at="2030-01-01T00:00:00+00:00")
    unique, report = normalize.dedupe([first, second])
    assert len(unique) == 1
    assert report["duplicates"] == 0
    assert report["revisions"] == 1
    assert unique[0]["revisions"] == 2
    assert unique[0]["description"] == "second description"


# ---------------------------------------------------------------------- write
def test_atomic_write_leaves_no_temp_file(tmp_path):
    target = tmp_path / "gaps.json"
    collect.write_atomic(target, {"ok": True})
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}
    assert list(tmp_path.glob("*.tmp")) == []


def test_atomic_write_uses_replace(monkeypatch, tmp_path):
    replaced = []
    real_replace = collect.os.replace

    def spy(src, dst):
        replaced.append((str(src), str(dst)))
        return real_replace(src, dst)

    monkeypatch.setattr(collect.os, "replace", spy)
    collect.write_atomic(tmp_path / "x.json", {"n": 1})
    assert replaced and replaced[0][1].endswith("x.json")


def test_refusal_vocabulary_is_closed(tmp_path):
    with pytest.raises(ValueError):
        collect.log_refusal("not_a_rule", path=tmp_path / "refusals.jsonl")
    row = collect.log_refusal("amazon_host_blocked", source="github",
                              url="https://www.amazon.com/dp/B01FYY3M38",
                              path=tmp_path / "refusals.jsonl")
    assert row["rule_id"] == "amazon_host_blocked"
    lines = (tmp_path / "refusals.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[-1])["rule"]


# ------------------------------------------------------------------ guardrails
def test_amazon_is_refused_before_transport(monkeypatch):
    calls = []

    def boom(*args, **kwargs):
        calls.append(1)
        raise AssertionError("transport was reached for an Amazon URL")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    with pytest.raises(Refused):
        http.request("https://www.amazon.com/dp/B01FYY3M38")
    assert calls == []


# ---------------------------------------------------------------- verification
def test_verify_falls_back_to_authoritative_api(monkeypatch):
    def fake(url, *, timeout, prefer_get=False):
        status = 200 if "api.github.com" in url else 504
        return {"ok": status == 200, "status": status, "method": "GET"}

    monkeypatch.setattr(verify, "_direct", fake)
    finding = {"source": "github", "url": "https://github.com/acme/widget",
               "identity": "acme/widget"}
    result = verify.verify_finding(finding)
    assert result["ok"] is True
    assert result["status"] == 504          # the public URL's real answer
    assert result["via"] == "api"
    assert result["via_status"] == 200
    assert result["via_url"] == "https://api.github.com/repos/acme/widget"


def test_verify_reports_dead_link_without_raising(monkeypatch):
    def fake(url, *, timeout, prefer_get=False):
        return {"ok": False, "status": 404, "method": "GET"}

    monkeypatch.setattr(verify, "_direct", fake)
    result = verify.verify_finding({"source": "pypi", "url": "https://pypi.org/project/gone/",
                                    "title": "gone"})
    assert result["ok"] is False
    assert result["status"] == 404


# -------------------------------------------------------------------- dry run
def test_dry_run_writes_nothing_and_never_hits_network(monkeypatch, tmp_path):
    def no_network(*args, **kwargs):
        raise AssertionError("dry run attempted a network call")

    monkeypatch.setattr(http, "request", no_network)
    out = tmp_path / "gaps.json"
    mirror = tmp_path / "mirror.json"
    doc = collect.run(dry_run=True, out_path=out, mirror_path=mirror)
    assert doc["run"]["dry_run"] is True
    assert doc["run"]["findings"] >= 12
    assert doc["run"]["fixtures"], "dry run must have used recorded fixtures"
    assert not out.exists() and not mirror.exists()
    for source in SOURCES:
        assert doc["sources"][source]["queries"] >= 1


def test_dry_run_output_contract(tmp_path):
    doc = collect.run(dry_run=True, out_path=tmp_path / "unused.json",
                      mirror_path=tmp_path / "unused2.json")
    required = ("id", "what", "where", "licence", "service", "estimated_lift",
                "evidence", "source", "fetched_at", "status")
    for finding in doc["findings"]:
        for key in required:
            assert key in finding, f"finding missing {key}"
        assert finding["where"].startswith("http")
        assert finding["licence"]
        assert finding["service"]
        assert finding["status"] in vet.STATUSES
        assert isinstance(finding["evidence"], dict) and finding["evidence"]
        assert float(finding["estimated_lift"]) >= 0.0
        assert finding["url_status"] is None  # offline: nothing was verified
    ids = [finding["id"] for finding in doc["findings"]]
    assert len(ids) == len(set(ids)), "finding ids must be unique"


def test_dry_run_never_adopts_unknown_or_noncommercial():
    doc = collect.run(dry_run=True)
    for finding in doc["findings"]:
        if finding["licence_class"] in ("unknown", "noncommercial", "proprietary"):
            assert finding["status"] != "adopt"
            assert finding["adopt_eligible"] is False
