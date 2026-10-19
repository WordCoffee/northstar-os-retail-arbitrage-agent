"""Deep-research graph — deconstruct, traverse, cross-validate, synthesise.

The searcher is injected in every test, so the graph is exercised with no corpus,
no embeddings and no network. The tests pin the honesty rules: a node with no
evidence says so, a single-source claim is labelled single-source, and numeric
disagreement is surfaced as a conflict instead of being averaged away.
"""
from __future__ import annotations

import research_graph as rg


def fake_search(store):
    def _fn(text, limit):
        return store.get(text, [])[:limit]
    return _fn


# ── deconstruction ───────────────────────────────────────────────────────────

def test_deconstruct_builds_one_query_per_axis_from_the_query_terms():
    nodes = rg.deconstruct("mushroom supplement margin sourcing")
    assert len(nodes) == len(rg.AXES)
    assert [n["id"] for n in nodes] == [a["id"] for a in rg.AXES]
    assert all("mushroom" in n["query"] for n in nodes)
    assert len({n["query"] for n in nodes}) == len(nodes)   # axes are distinct


# ── traversal ────────────────────────────────────────────────────────────────

def test_traverse_reports_sources_per_node():
    store = {f"mushroom margin {a['lead']}".strip(): [
        {"source": "docs", "text": f"margin was 22% for {a['id']}"},
        {"source": "github_csv", "text": f"another note for {a['id']}"},
    ] for a in rg.AXES}
    graph = rg.traverse("mushroom margin", search=fake_search(store))
    assert graph["hit_count"] == 6
    assert graph["sources"] == ["docs", "github_csv"]
    for node in graph["nodes"]:
        assert node["results"] and node["sources"]


def test_a_failing_search_is_reported_per_node_not_raised():
    def boom(text, limit):
        raise RuntimeError("corpus offline")

    graph = rg.traverse("mushroom margin", search=boom)
    assert graph["node_count"] == len(rg.AXES)
    assert all("corpus offline" in n["error"] for n in graph["nodes"])
    assert graph["hit_count"] == 0


def test_empty_corpus_is_an_explicit_result():
    graph = rg.traverse("nothing here", search=fake_search({}))
    out = rg.research("nothing here", search=fake_search({}))
    assert graph["hit_count"] == 0
    assert "not an answer" in out["summary"]
    assert out["empty_nodes"] == [a["id"] for a in rg.AXES]


# ── cross-source validation ──────────────────────────────────────────────────

def test_validation_counts_sources_and_flags_conflicting_numbers():
    store = {
        "acl margin what": [
            {"source": "docs", "text": "The mushroom margin was 22% in the club channel."},
            {"source": "stack_sources", "text": "Our mushroom margin was 31% last quarter."},
        ],
        "acl margin fails when": [
            {"source": "docs", "text": "A single note about mushroom margin only here."},
        ],
        "acl margin history of": [],
    }
    from collections import defaultdict
    # map by the deconstructed query strings
    mapping = {n["query"]: v for n, v in zip(rg.deconstruct("acl margin"), store.values())}
    out = rg.research("acl margin", search=fake_search(mapping))

    conf_terms = {c["term"] for c in out["validation"]["conflicts"]}
    assert "margin" in conf_terms, out["validation"]
    vals = next(c["values"] for c in out["validation"]["conflicts"] if c["term"] == "margin")
    assert len(vals) == 2 and all(len(v) >= 1 for v in vals.values())
    assert out["validation"]["single_source"], "the one-source claim was not flagged"
    assert all(s["source"] for s in out["validation"]["single_source"])


def test_no_conflict_when_sources_agree():
    def agree(text, limit):
        return [{"source": "a", "text": "margin is 22%"},
                {"source": "b", "text": "margin is 22%"}]

    out = rg.research("margin", search=agree)
    assert out["validation"]["conflicts"] == []
    assert out["validation"]["multi_source_count"] >= 1


# ── the report is honest about what it is ────────────────────────────────────

def test_report_states_it_is_corpus_only_and_not_verification():
    out = rg.research("mushroom margin", search=fake_search({
        "mushroom margin what": [{"source": "docs", "text": "margin 22%"}]}))
    assert out["ok"] is True
    blob = " ".join(out["caveats"]).lower()
    assert "not verification" in blob
    assert "chrome connect" in out["method"].lower()
    assert "no web crawl" in blob or "no web crawl" in out["method"].lower()
