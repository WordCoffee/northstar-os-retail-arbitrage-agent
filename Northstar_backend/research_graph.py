"""Deep-research graph over the LOCAL corpus (Thorn v5.0 §Autonomous Deep Web Search).

Builds the multi-node research tree the plan describes — deconstruct, traverse,
cross-validate, synthesise with conflicts — but against the **local corpus lane**
(`corpus_drift.vector_search` / `corpus_router.search`). Live web crawling is
operator-gated through Chrome Connect / REA and is deliberately NOT triggered
from here, so this module makes no outbound call of any kind.

Honesty contract
----------------
* A node reports exactly the sources it retrieved. Zero results is a valid,
  reported outcome ("no corpus evidence"), never a silent empty answer.
* Cross-source validation is a *counting* method: a statement found in one source
  is labelled `single_source`, not "verified". Two sources disagreeing on the same
  number are reported as a `conflict` — never averaged away into a fake consensus.
* The searcher is injectable, so the graph is testable with no corpus and no
  embedding model loaded.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Sequence

MAX_NODES = 6

AXES: Sequence[Dict[str, str]] = (
    {"id": "concept", "label": "Core concepts", "lead": "what"},
    {"id": "edge_case", "label": "Edge cases", "lead": "fails when"},
    {"id": "history", "label": "Historical context", "lead": "history of"},
)

_NUM = re.compile(r"(?<![\w.])(\d[\d,]*\.?\d*)\s?([a-z%]{0,8})", re.I)
_STOP = {"the", "and", "for", "with", "that", "this", "from", "into", "your", "are",
         "was", "were", "its", "it's", "has", "have", "not", "but", "any", "all"}


def _terms(query: str) -> List[str]:
    return [w for w in re.findall(r"[A-Za-z][A-Za-z0-9'-]+", query or "")
            if len(w) > 2 and w.lower() not in _STOP]


def deconstruct(query: str) -> List[Dict[str, str]]:
    """Query matrix: one search string per axis, built from the query's own terms."""
    core = " ".join(_terms(query)[:6]) or (query or "").strip()
    return [{"id": a["id"], "label": a["label"],
             "query": f"{core} {a['lead']}".strip()} for a in AXES]


def _default_search(text: str, limit: int) -> List[Dict[str, Any]]:
    """Local corpus lane. Returns [] when the corpus lane is unavailable."""
    try:
        import corpus_router  # local import: keeps this module importable standalone
    except Exception:  # noqa: BLE001 - reported as no evidence, never fatal
        return []
    try:
        rows = corpus_router.search(text, limit=limit)
    except Exception:  # noqa: BLE001
        return []
    out: List[Dict[str, Any]] = []
    for r in rows or []:
        out.append({
            "source_id": r.get("source_id") or r.get("id") or "",
            "source": r.get("source") or r.get("source_id") or "corpus",
            "text": r.get("content") or r.get("text") or "",
            "score": r.get("score"),
        })
    return out


def traverse(query: str, *, limit_per_node: int = 4,
             search: Optional[Callable[[str, int], List[Dict[str, Any]]]] = None) -> Dict[str, Any]:
    """Run the query matrix. `search` is injectable for offline testing."""
    fn = search or _default_search
    nodes = []
    for spec in deconstruct(query)[:MAX_NODES]:
        try:
            hits = fn(spec["query"], limit_per_node) or []
        except Exception as exc:  # noqa: BLE001 - a failed node is reported, not hidden
            nodes.append({**spec, "results": [], "error": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        nodes.append({**spec, "results": hits,
                      "sources": sorted({h.get("source") or h.get("source_id") or "?" for h in hits})})
    return {
        "query": query,
        "nodes": nodes,
        "sources": sorted({s for n in nodes for s in n.get("sources", [])}),
        "node_count": len(nodes),
        "hit_count": sum(len(n.get("results", [])) for n in nodes),
    }


def validate(graph: Dict[str, Any], query: str) -> Dict[str, Any]:
    """Cross-source validation: single-source claims and numeric conflicts."""
    terms = [t.lower() for t in _terms(query)]
    numbers: Dict[str, Dict[str, List[str]]] = {}      # term -> value -> [source]
    claim_sources: Dict[str, set] = {}                 # sentence -> {source}

    for node in graph.get("nodes", []):
        for hit in node.get("results", []):
            source = hit.get("source") or hit.get("source_id") or "?"
            text = str(hit.get("text") or "")
            for sentence in re.split(r"(?<=[.!?])\s+", text):
                low = sentence.lower()
                if not any(t in low for t in terms):
                    continue
                claim_sources.setdefault(sentence.strip()[:200], set()).add(source)
                for value, unit in _NUM.findall(sentence):
                    key = f"{value}{(' ' + unit) if unit else ''}".strip()
                    for t in terms:
                        if t in low:
                            numbers.setdefault(t, {}).setdefault(key, []).append(source)
                            break

    single = [{"claim": c, "source": sorted(s)[0]}
              for c, s in claim_sources.items() if len(s) == 1]
    conflicts = []
    for term, values in numbers.items():
        distinct = {k: sorted(set(v)) for k, v in values.items() if k}
        if len(distinct) > 1:
            conflicts.append({"term": term, "values": distinct})

    return {
        "claimed_sentences": len(claim_sources),
        "single_source": sorted(single, key=lambda x: x["claim"])[:10],
        "conflicts": sorted(conflicts, key=lambda x: x["term"])[:10],
        "multi_source_count": sum(1 for s in claim_sources.values() if len(s) > 1),
    }


def research(query: str, *, limit_per_node: int = 4,
             search: Optional[Callable[[str, int], List[Dict[str, Any]]]] = None) -> Dict[str, Any]:
    """The whole tree: deconstruct → traverse → validate → synthesise."""
    graph = traverse(query, limit_per_node=limit_per_node, search=search)
    check = validate(graph, query)
    ran = [n for n in graph["nodes"] if n.get("results")]
    empty = [n["id"] for n in graph["nodes"] if not n.get("results")]
    errored = [n["id"] for n in graph["nodes"] if n.get("error")]

    if graph["node_count"] == 0:
        headline = "Nothing to research: the query produced no search matrix."
    elif graph["hit_count"] == 0:
        headline = ("No corpus evidence for any node — the local corpus lane returned "
                    "nothing. That is a real result, not an answer.")
    else:
        headline = (f"{graph['hit_count']} passage(s) across {len(graph['sources'])} source(s) "
                    f"from {len(ran)}/{graph['node_count']} node(s); "
                    f"{check['multi_source_count']} claim(s) corroborated, "
                    f"{len(check['single_source'])} single-source, "
                    f"{len(check['conflicts'])} numeric conflict(s).")

    return {
        "ok": True,
        "query": query,
        "summary": headline,
        "method": ("Local corpus retrieval over an axis-decomposed query matrix, then "
                   "source counting per claimed sentence and per numeric value. No web "
                   "crawl: live sources require an operator window with Chrome Connect."),
        "caveats": [
            "Cross-source validation here means 'more than one local source says it', "
            "which is corroboration, not verification.",
            "A single-source claim is reported as such and is never presented as fact.",
            "Numeric disagreement is surfaced as a conflict; nothing is averaged away.",
        ],
        "nodes": graph["nodes"],
        "sources": graph["sources"],
        "empty_nodes": empty,
        "errored_nodes": errored,
        "validation": check,
    }
