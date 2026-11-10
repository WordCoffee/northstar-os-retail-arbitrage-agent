"""Merge the API scan and the awesome-list harvest into one catalog.

API rows are enriched (stars, licence, push date). Awesome-list rows are
discovery-only: a name, the list(s) that named it, and the surrounding text.
The merge keeps the enriched row when both exist, and classifies discovery rows
into the three focus areas from their name, context and source list.

    python tools/github_scan_merge.py
    python tools/github_scan_merge.py --top 60
"""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "state" / "evidence" / "github_scan_20261104"
REPORT = ROOT / "reports" / "github_scan_20261104"

BOJO_WORDS = ["memory", "chat", "voice", "tts", "asr", "whisper", "embed", "rag",
              "retriev", "ollama", "llama", "local", "small", "prompt", "compress",
              "rerank", "tokeniz", "gguf", "quant", "router", "instruct", "persona"]
TYS_WORDS = ["agent", "coding", "code", "browser", "playwright", "sandbox", "mcp",
             "server", "tool", "eval", "bench", "workflow", "task", "queue",
             "trace", "observ", "plan", "patch", "repo", "automat", "computer",
             "approval", "human", "scrap", "crawl"]
BRAIN_WORDS = ["knowledge", "graph", "memory", "policy", "guard", "context",
               "orchestr", "state", "provenance", "lineage", "ingest", "docling",
               "vector", "database", "cache", "gateway", "schema", "audit",
               "govern", "security", "prompt", "retriev", "eval"]

LIST_DEFAULT = {
    "punkpeye/awesome-mcp-servers": "tys",
    "modelcontextprotocol/servers": "tys",
    "e2b-dev/awesome-ai-agents": "tys",
    "kaushikb11/awesome-llm-agents": "tys",
    "jamesmurdza/awesome-ai-devtools": "tys",
    "Sourcegraph/awesome-code-ai": "tys",
    "janhq/awesome-local-ai": "bojo",
    "ollama/ollama": "bojo",
    "tensorchord/Awesome-LLMOps": "brain",
    "visenger/awesome-mlops": "brain",
    "EthicalML/awesome-production-machine-learning": "brain",
    "corca-ai/awesome-llm-security": "brain",
    "protectai/ai-exploits": "brain",
    "awesome-selfhosted/awesome-selfhosted": "brain",
    "brexhq/prompt-engineering": "brain",
    "dair-ai/Prompt-Engineering-Guide": "brain",
    "guardrails-ai/guardrails": "brain",
    "microsoft/RAG_Hack": "brain",
    "aishwaryanr/awesome-generative-ai-guide": "brain",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _score(text: str, words: List[str]) -> int:
    text = text.lower()
    return sum(1 for word in words if word in text)


def _classify_discovery(row: Dict[str, Any]) -> Dict[str, Any]:
    name = (row.get("full_name") or "").split("/")[-1].lower()
    context = (row.get("context") or "").lower()
    text = f"{name} {context}"
    scores = {"bojo": _score(text, BOJO_WORDS),
              "tys": _score(text, TYS_WORDS),
              "brain": _score(text, BRAIN_WORDS)}
    votes = Counter()
    for listed in row.get("listed_by") or []:
        default = LIST_DEFAULT.get(listed)
        if default:
            votes[default] += 1
    for focus, score in scores.items():
        votes[focus] += score
    focus = votes.most_common(1)[0][0] if votes else "brain"
    return {"focus": focus, "focus_scores": scores,
            "list_votes": dict(votes)}


def merge(top: int = 40) -> Dict[str, Any]:
    enriched = list(_read_jsonl(RUN / "repos.jsonl"))
    discovered = list(_read_jsonl(RUN / "awesome_links.jsonl"))
    by_name: Dict[str, Dict[str, Any]] = {}
    for row in enriched:
        by_name[(row.get("full_name") or "").lower()] = {**row, "source": "search"}
    added = 0
    for row in discovered:
        key = (row.get("full_name") or "").lower()
        if not key or key in by_name:
            continue
        cls = _classify_discovery(row)
        by_name[key] = {**row, "source": "awesome", "stars": 0,
                        "licence": {"spdx": "", "class": "unknown", "commercial": None},
                        "needs_metadata": True, **cls,
                        "relevance": round(cls["focus_scores"].get(cls["focus"], 0), 3)}
        added += 1

    rows = list(by_name.values())
    RUN.mkdir(parents=True, exist_ok=True)
    with (RUN / "merged.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    counts = {
        "api": sum(1 for r in rows if r.get("source") == "search"),
        "awesome_only": sum(1 for r in rows if r.get("source") == "awesome"),
        "unique_total": len(rows),
    }
    focus = {f: sum(1 for r in rows if r.get("focus") == f) for f in ("bojo", "tys", "brain")}
    licences = Counter((r.get("licence") or {}).get("class", "unknown") for r in rows)
    summary = {"generated_at": _now(), "counts": counts, "focus": focus,
               "licence_classes": dict(licences)}
    (RUN / "merged_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    REPORT.mkdir(parents=True, exist_ok=True)
    lines = [
        "# GitHub scan — merged catalog",
        "",
        f"**{counts['unique_total']:,} unique repositories.** "
        f"{counts['api']:,} enriched via the search API; "
        f"{counts['awesome_only']:,} discovery-only from curated lists.",
        "",
        f"Focus: Bojo {focus['bojo']:,} · Tys {focus['tys']:,} · brain {focus['brain']:,}",
        "",
        f"Licence classes: {dict(licences)}",
        "",
    ]
    for f, title in (("bojo", "Bojo"), ("tys", "Tys Assistant"), ("brain", "Master brain")):
        subset = [r for r in rows if r.get("focus") == f]
        enriched_subset = sorted(
            (r for r in subset if r.get("source") == "search"),
            key=lambda r: (r.get("relevance", 0), math.log10(max(r.get("stars", 1), 1))),
            reverse=True)[:top]
        discovery = sorted(
            (r for r in subset if r.get("source") == "awesome"),
            key=lambda r: (r.get("relevance", 0),
                           len(r.get("listed_by") or [])), reverse=True)[:top]
        lines += [f"## {title} — enriched top {len(enriched_subset)}", "",
                  "| repo | stars | licence | pushed | description |",
                  "|---|---|---|---|---|"]
        for r in enriched_subset:
            lic = r.get("licence") or {}
            desc = (r.get("description") or "").replace("|", "/")[:150]
            lines.append(f"| [{r['full_name']}]({r['url']}) | {r.get('stars', 0):,} | "
                         f"{lic.get('spdx') or 'unknown'} | {(r.get('pushed_at') or '')[:10]} | {desc} |")
        lines += ["", f"### {title} — discovery-only top {len(discovery)}", "",
                  "| repo | listed by | context |", "|---|---|---|"]
        for r in discovery:
            context = (r.get("context") or "").replace("|", "/")[:140]
            lines.append(f"| [{r['full_name']}]({r['url']}) | "
                         f"{', '.join((r.get('listed_by') or [])[:2])} | {context} |")
        lines.append("")
    (REPORT / "merged_catalog.md").write_text("\n".join(lines), encoding="utf-8")

    shortlist: Dict[str, List[Dict[str, Any]]] = {}
    for f in ("bojo", "tys", "brain"):
        subset = [r for r in rows if r.get("focus") == f]
        subset.sort(key=lambda r: (r.get("source") == "search",
                                   r.get("relevance", 0),
                                   math.log10(max(r.get("stars", 1), 1))),
                    reverse=True)
        shortlist[f] = [{
            "full_name": r.get("full_name"), "url": r.get("url"),
            "source": r.get("source"), "stars": r.get("stars", 0),
            "licence": (r.get("licence") or {}).get("spdx"),
            "licence_class": (r.get("licence") or {}).get("class"),
            "pushed_at": r.get("pushed_at"),
            "description": r.get("description"),
            "listed_by": r.get("listed_by"),
        } for r in subset[:top]]
    (REPORT / "shortlist.json").write_text(json.dumps(
        {"generated_at": _now(), "unique_total": len(rows), "per_focus": top,
         "shortlist": shortlist}, indent=2), encoding="utf-8")

    summary["catalog"] = str(REPORT / "merged_catalog.md")
    summary["shortlist"] = str(REPORT / "shortlist.json")
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top", type=int, default=40)
    args = ap.parse_args(argv)
    print(json.dumps(merge(top=args.top), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
