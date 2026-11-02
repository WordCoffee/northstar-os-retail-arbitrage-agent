"""Discovery queue: propose, dedupe, never install and never guess a licence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import discovery_queue as dq  # noqa: E402


def _rel(tag="v1.2.3", prerelease=False):
    """GitHub's own field names - the parser must read tag_name, not tag."""
    return {"tag_name": tag, "name": f"release {tag}",
            "published_at": "2026-11-01T00:00:00Z",
            "html_url": f"https://github.com/x/y/releases/{tag}",
            "prerelease": prerelease}


def _cand(tag="v1.2.3", prerelease=False, repo="a/b"):
    return {"repo": repo, "tag": tag, "name": f"release {tag}",
            "published_at": "2026-11-01T00:00:00Z",
            "url": f"https://github.com/{repo}/releases/{tag}",
            "prerelease": prerelease}


def test_fetch_parses_a_release_list():
    def getter(url):
        assert "api.github.com" in url
        return [_rel("v1.0.0"), _rel("v1.0.1", prerelease=True)]

    rels = dq.fetch_releases("a/b", getter=getter)
    assert [r["tag"] for r in rels] == ["v1.0.0", "v1.0.1"]
    assert rels[1]["prerelease"] is True
    assert rels[0]["repo"] == "a/b"


def test_fetch_rejects_an_unexpected_payload():
    with pytest.raises(ValueError) as caught:
        dq.fetch_releases("a/b", getter=lambda url: {"message": "rate limited"})
    assert "discovery_unexpected_payload" in str(caught.value)


def test_an_unknown_licence_is_ineligible():
    record = dq.propose(_cand(), licence="unverified", why="test")
    assert record["licence_known"] is False
    assert record["eligible"] is False
    assert "licence must be recorded" in record["next_step"]


def test_a_known_licence_is_eligible_but_still_only_proposed():
    record = dq.propose(_cand(), licence="MIT", why="test", vram_mb=4096)
    assert record["eligible"] is True
    assert record["status"] == "proposed"
    assert record["lane"] == "local-lane"
    assert record["vram_mb"] == 4096


def test_a_prerelease_is_never_eligible():
    record = dq.propose(_cand(prerelease=True), licence="MIT", why="test")
    assert record["eligible"] is False
    assert "benchmark" in record["next_step"]


def test_proposals_dedupe_and_never_overwrite(tmp_path):
    first = dq.write_proposals([dq.propose(_cand("v1"), licence="MIT", why="a")], tmp_path)
    assert len(first["written"]) == 1
    second = dq.write_proposals([dq.propose(_cand("v1"), licence="MIT", why="a")], tmp_path)
    assert second["written"] == [] and second["skipped"] == ["a/b@v1"]
    assert len(list(Path(tmp_path).glob("*.json"))) == 1


def test_run_reports_a_failing_source_without_stopping(tmp_path):
    def getter(url):
        if "bad" in url:
            raise OSError("connection reset")
        return [_rel("v2")]

    out = dq.run(sources=[{"repo": "good/one", "why": "x"},
                          {"repo": "bad/one", "why": "y"}],
                 getter=getter, licences={"good/one": "Apache-2.0"}, folder=tmp_path)
    assert out["candidates"] == 1
    assert out["errors"] and "bad/one" in out["errors"][0]["repo"]
    written = json.loads((Path(tmp_path) / "good_one_v2.json").read_text(encoding="utf-8"))
    assert written["licence"] == "Apache-2.0"
    assert written["status"] == "proposed"


def test_the_queue_carries_no_installer():
    source = Path(dq.__file__).read_text(encoding="utf-8")
    for forbidden in ("subprocess", "pip install", "git clone", "os.system"):
        assert forbidden not in source, f"the queue must not install anything ({forbidden})"
