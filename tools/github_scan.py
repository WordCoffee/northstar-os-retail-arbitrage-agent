"""Scan GitHub for components Northstar OS can actually use.

Three focus areas, because that is where the leverage is:

  bojo    the small local chat/orchestrator model: memory, retrieval, tools,
          voice, structured output, prompt compression, local inference
  tys     the admin automation agent: coding/browser lanes, sandboxes, planning,
          task queues, observability, evaluation, approvals
  brain   the master brain: knowledge/memory stores, policy engines, provenance,
          context engineering, orchestration, guardrails

Search API unauthenticated is 10 requests/minute (measured), so the scan is
resumable and polite: every completed query is recorded, results append to
JSONL, and the process sleeps on the rate-limit reset instead of failing.

    python tools/github_scan.py --wave core      # ~150 requests
    python tools/github_scan.py --wave deep      # ~60 more, narrow gaps
    python tools/github_scan.py --report         # catalog from what is on disk

No credentials, no writes outside `state/evidence/github_scan_<date>/`.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "state" / "evidence" / "github_scan_20261104"
JSONL = RUN / "repos.jsonl"
DONE = RUN / "queries_done.json"
REPORT_DIR = ROOT / "reports" / "github_scan_20261104"

API = "https://api.github.com/search/repositories"
UA = "northstar-os-scan/1.0"

#: Each query: text, focus, pages (100 results per page, max 10), min stars.
#: Broad queries are capped at 5 pages; that still reaches the top 500 by stars
#: and keeps a 30-query wave inside ~15 minutes at 10 req/min.
QUERIES: List[Dict[str, Any]] = [
    # ---- Bojo: local model, memory, retrieval, voice -----------------------
    {"q": "local llm assistant", "focus": "bojo", "pages": 5, "stars": 100},
    {"q": "small language model tool calling", "focus": "bojo", "pages": 4, "stars": 50},
    {"q": "llm memory long-term", "focus": "bojo", "pages": 5, "stars": 100},
    {"q": "conversation memory ai", "focus": "bojo", "pages": 4, "stars": 50},
    {"q": "ollama agent", "focus": "bojo", "pages": 5, "stars": 50},
    {"q": "llama.cpp server", "focus": "bojo", "pages": 4, "stars": 100},
    {"q": "local rag offline", "focus": "bojo", "pages": 4, "stars": 50},
    {"q": "prompt compression llm", "focus": "bojo", "pages": 3, "stars": 30},
    {"q": "structured output llm json schema", "focus": "bojo", "pages": 4, "stars": 50},
    {"q": "text to speech local neural", "focus": "bojo", "pages": 4, "stars": 100},
    {"q": "speech recognition local whisper", "focus": "bojo", "pages": 4, "stars": 200},
    {"q": "embeddings reranker local", "focus": "bojo", "pages": 4, "stars": 100},
    {"q": "speculative decoding inference", "focus": "bojo", "pages": 3, "stars": 50},
    {"q": "llm router model selection", "focus": "bojo", "pages": 4, "stars": 50},
    {"q": "local first ai assistant", "focus": "bojo", "pages": 4, "stars": 50},
    # ---- Tys: agent harness, coding, browser, sandbox, eval ----------------
    {"q": "topic:ai-agents", "focus": "tys", "pages": 5, "stars": 100},
    {"q": "topic:agent", "focus": "tys", "pages": 5, "stars": 200},
    {"q": "coding agent", "focus": "tys", "pages": 5, "stars": 200},
    {"q": "swe-bench agent", "focus": "tys", "pages": 4, "stars": 50},
    {"q": "computer use agent", "focus": "tys", "pages": 4, "stars": 100},
    {"q": "browser automation agent", "focus": "tys", "pages": 4, "stars": 100},
    {"q": "code interpreter sandbox", "focus": "tys", "pages": 3, "stars": 50},
    {"q": "topic:mcp", "focus": "tys", "pages": 5, "stars": 100},
    {"q": "model context protocol server", "focus": "tys", "pages": 4, "stars": 50},
    {"q": "agent framework python", "focus": "tys", "pages": 5, "stars": 500},
    {"q": "multi-agent orchestration", "focus": "tys", "pages": 4, "stars": 200},
    {"q": "human in the loop approval workflow", "focus": "tys", "pages": 3, "stars": 50},
    {"q": "durable workflow engine python", "focus": "tys", "pages": 3, "stars": 200},
    {"q": "llm observability tracing", "focus": "tys", "pages": 4, "stars": 100},
    {"q": "llm evaluation framework", "focus": "tys", "pages": 4, "stars": 200},
    {"q": "repo indexing code search", "focus": "tys", "pages": 4, "stars": 100},
    {"q": "test selection impact analysis", "focus": "tys", "pages": 3, "stars": 30},
    {"q": "browser use playwright agent", "focus": "tys", "pages": 4, "stars": 100},
    {"q": "agent sandbox container", "focus": "tys", "pages": 3, "stars": 100},
    # ---- Master brain: knowledge, policy, context, provenance -------------
    {"q": "agent memory", "focus": "brain", "pages": 5, "stars": 100},
    {"q": "graphrag knowledge graph", "focus": "brain", "pages": 4, "stars": 100},
    {"q": "knowledge graph memory llm", "focus": "brain", "pages": 4, "stars": 100},
    {"q": "topic:knowledge-graph", "focus": "brain", "pages": 4, "stars": 200},
    {"q": "topic:policy-engine", "focus": "brain", "pages": 3, "stars": 100},
    {"q": "guardrails llm", "focus": "brain", "pages": 4, "stars": 100},
    {"q": "prompt management versioning", "focus": "brain", "pages": 3, "stars": 50},
    {"q": "context engineering llm", "focus": "brain", "pages": 3, "stars": 30},
    {"q": "document ingestion pdf", "focus": "brain", "pages": 4, "stars": 200},
    {"q": "embedded vector database", "focus": "brain", "pages": 4, "stars": 200},
    {"q": "sqlite vector search", "focus": "brain", "pages": 3, "stars": 50},
    {"q": "data lineage provenance", "focus": "brain", "pages": 3, "stars": 100},
    {"q": "topic:orchestration", "focus": "brain", "pages": 3, "stars": 100},
    {"q": "topic:state-machine", "focus": "brain", "pages": 3, "stars": 100},
    {"q": "topic:workflow-engine", "focus": "brain", "pages": 3, "stars": 100},
    {"q": "retrieval augmented generation framework", "focus": "brain", "pages": 4, "stars": 200},
    {"q": "semantic cache llm", "focus": "brain", "pages": 3, "stars": 50},
    {"q": "llm gateway proxy", "focus": "brain", "pages": 4, "stars": 200},
    # ---- deep wave: narrower, higher signal -------------------------------
    {"q": "topic:local-llm", "focus": "bojo", "pages": 3, "stars": 30},
    {"q": "topic:llmops", "focus": "tys", "pages": 3, "stars": 100},
    {"q": "topic:ai-evaluation", "focus": "tys", "pages": 3, "stars": 50},
    {"q": "topic:agentic-ai", "focus": "tys", "pages": 3, "stars": 100},
    {"q": "topic:tool-calling", "focus": "bojo", "pages": 3, "stars": 30},
    {"q": "topic:memory-management", "focus": "brain", "pages": 3, "stars": 50},
    {"q": "topic:rag", "focus": "brain", "pages": 3, "stars": 200},
    {"q": "topic:llm-security", "focus": "brain", "pages": 3, "stars": 50},
    {"q": "topic:prompt-engineering", "focus": "brain", "pages": 3, "stars": 200},
    {"q": "topic:model-context-protocol", "focus": "tys", "pages": 3, "stars": 50},
]

WAVES = {
    "core": [i for i, q in enumerate(QUERIES[:35])],
    "deep": [i for i in range(35, len(QUERIES))],
    "all": list(range(len(QUERIES))),
}

#: Commercial-use classification, used to separate local-lane from cloud-lane.
PERMISSIVE = {"MIT", "APACHE-2.0", "BSD-2-CLAUSE", "BSD-3-CLAUSE", "ISC", "MPL-2.0",
              "0BSD", "UNLICENSE", "BSL-1.0", "ZLIB", "POSTGRESQL", "EPL-2.0"}
COPYLEFT = {"GPL-2.0", "GPL-3.0", "AGPL-3.0", "LGPL-2.1", "LGPL-3.0", "EUPL-1.2"}
RESTRICTED_HINTS = ("NC", "NONCOMMERCIAL", "SSPL", "BUSL", "ELASTIC", "COMMONS-CLAUSE")

FOCUS_KEYWORDS = {
    "bojo": ["memory", "rag", "retriev", "embed", "voice", "speech", "tts", "asr",
             "ollama", "llama", "local", "small", "router", "prompt", "chat",
             "conversation", "tool", "function", "structured", "compression"],
    "tys": ["agent", "coding", "code", "browser", "sandbox", "eval", "bench",
            "workflow", "task", "queue", "observab", "trac", "mcp", "plan",
            "patch", "repo", "automat", "computer", "approval", "human"],
    "brain": ["knowledge", "graph", "memory", "policy", "guard", "context",
              "orchestr", "state", "provenance", "lineage", "ingest", "vector",
              "retriev", "prompt", "schema", "govern", "audit", "cache", "gateway"],
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _iso_now_epoch() -> int:
    return int(time.time())


def _request(url: str, *, retries: int = 3) -> Dict[str, Any]:
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={
            "User-Agent": UA, "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"})
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                payload = json.loads(response.read().decode("utf-8"))
                remaining = int(response.headers.get("X-RateLimit-Remaining") or 1)
                if remaining <= 1:
                    reset = int(response.headers.get("X-RateLimit-Reset") or 0)
                    wait = max(5, reset - _iso_now_epoch() + 2)
                    print(f"  rate limit reached; sleeping {wait}s", flush=True)
                    time.sleep(min(wait, 90))
                return payload
        except urllib.error.HTTPError as exc:
            if exc.code in (403, 429):
                reset = int(exc.headers.get("X-RateLimit-Reset") or 0)
                wait = max(5, reset - _iso_now_epoch() + 2)
                print(f"  HTTP {exc.code}; sleeping {wait}s", flush=True)
                time.sleep(min(wait, 90))
                continue
            raise
        except Exception as exc:  # noqa: BLE001 - retry transient network
            if attempt == retries - 1:
                raise
            print(f"  retry {attempt + 1}: {exc}", flush=True)
            time.sleep(5)
    raise RuntimeError("request failed after retries")


def _licence(repo: Dict[str, Any]) -> Dict[str, Any]:
    spdx = ((repo.get("license") or {}).get("spdx_id") or "").upper()
    if not spdx or spdx == "NOASSERTION":
        return {"spdx": "", "class": "unknown", "commercial": None}
    if spdx in PERMISSIVE:
        return {"spdx": spdx, "class": "permissive", "commercial": True}
    if spdx in COPYLEFT:
        return {"spdx": spdx, "class": "copyleft", "commercial": True,
                "note": "local-lane unless the network-copyleft review is done"}
    if any(hint in spdx for hint in RESTRICTED_HINTS):
        return {"spdx": spdx, "class": "restricted", "commercial": False}
    return {"spdx": spdx, "class": "other", "commercial": None}


def _focus_scores(repo: Dict[str, Any]) -> Dict[str, int]:
    text = " ".join([
        repo.get("full_name") or "", repo.get("description") or "",
        " ".join(repo.get("topics") or []),
    ]).lower()
    return {focus: sum(1 for word in words if word in text)
            for focus, words in FOCUS_KEYWORDS.items()}


def _relevance(repo: Dict[str, Any], focus: str) -> float:
    stars = int(repo.get("stargazers_count") or 0)
    pushed = repo.get("pushed_at") or "1970-01-01"
    try:
        year = int(pushed[:4])
        month = int(pushed[5:7])
    except Exception:
        year, month = 1970, 1
    recency = max(0.0, (year - 2023) * 12 + month) / 12.0  # years past 2023
    hits = _focus_scores(repo)[focus]
    return round(hits * 3.0 + math.log10(max(stars, 1)) * 2.0 + recency, 3)


def _row(repo: Dict[str, Any], query: Dict[str, Any]) -> Dict[str, Any]:
    lic = _licence(repo)
    focus = str(query["focus"])
    return {
        "full_name": repo.get("full_name"),
        "url": repo.get("html_url"),
        "description": (repo.get("description") or "").strip()[:400],
        "stars": int(repo.get("stargazers_count") or 0),
        "forks": int(repo.get("forks_count") or 0),
        "language": repo.get("language"),
        "topics": list(repo.get("topics") or [])[:20],
        "pushed_at": repo.get("pushed_at"),
        "created_at": repo.get("created_at"),
        "archived": bool(repo.get("archived")),
        "fork": bool(repo.get("fork")),
        "open_issues": int(repo.get("open_issues_count") or 0),
        "homepage": repo.get("homepage"),
        "default_branch": repo.get("default_branch"),
        "licence": lic,
        "focus": focus,
        "focus_scores": _focus_scores(repo),
        "relevance": _relevance(repo, focus),
        "found_by": query["q"],
        "scanned_at": _now(),
    }


def _read_rows() -> Dict[str, Dict[str, Any]]:
    rows: Dict[str, Dict[str, Any]] = {}
    if not JSONL.is_file():
        return rows
    with JSONL.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = row.get("full_name")
            if not name:
                continue
            old = rows.get(name)
            if old is None or row.get("relevance", 0) > old.get("relevance", 0):
                rows[name] = row
    return rows


def scan(queries: Iterable[Dict[str, Any]], *, pause: float = 6.2,
         max_pages: Optional[int] = None) -> Dict[str, Any]:
    RUN.mkdir(parents=True, exist_ok=True)
    done = set(_load_json(DONE, {"done": []}).get("done") or [])
    added = 0
    requests = 0
    for query in queries:
        key = f"{query['q']}|{query['focus']}"
        if key in done:
            continue
        pages = min(int(query.get("pages") or 3), 10)
        if max_pages:
            pages = min(pages, int(max_pages))
        print(f"[{query['focus']}] {query['q']} ({pages} pages)", flush=True)
        for page in range(1, pages + 1):
            params = urllib.parse.urlencode({
                "q": f"{query['q']} stars:>={int(query.get('stars') or 0)} "
                     f"archived:false fork:false",
                "sort": "stars", "order": "desc",
                "per_page": 100, "page": page,
            })
            payload = _request(f"{API}?{params}")
            requests += 1
            items = payload.get("items") or []
            with JSONL.open("a", encoding="utf-8") as handle:
                for repo in items:
                    if repo.get("archived") or repo.get("fork"):
                        continue
                    if int(repo.get("stargazers_count") or 0) < int(query.get("stars") or 0):
                        continue
                    handle.write(json.dumps(_row(repo, query), ensure_ascii=False) + "\n")
                    added += 1
            print(f"  page {page}: {len(items)} items (total returned "
                  f"{payload.get('total_count')})", flush=True)
            if len(items) < 100:
                break
            time.sleep(pause)
        done.add(key)
        _save_json(DONE, {"done": sorted(done), "updated_at": _now(),
                          "queries": len(done), "requests": requests})
        time.sleep(pause)
    rows = _read_rows()
    summary = {
        "scanned_at": _now(),
        "queries_completed": len(done),
        "queries_total": len(QUERIES),
        "requests": requests,
        "rows_written": added,
        "unique_repos": len(rows),
        "focus_counts": {
            focus: sum(1 for r in rows.values() if r.get("focus") == focus)
            for focus in ("bojo", "tys", "brain")
        },
        "licence_classes": {
            cls: sum(1 for r in rows.values()
                     if (r.get("licence") or {}).get("class") == cls)
            for cls in ("permissive", "copyleft", "restricted", "unknown", "other")
        },
    }
    _save_json(RUN / "summary.json", summary)
    return summary


def report(*, per_focus: int = 40) -> Dict[str, Any]:
    rows = list(_read_rows().values())
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ranked = {focus: sorted((r for r in rows if r.get("focus") == focus),
                            key=lambda r: (r.get("relevance", 0),
                                           math.log10(max(r.get("stars", 1), 1))),
                            reverse=True)[:per_focus]
              for focus in ("bojo", "tys", "brain")}
    lines = ["# GitHub scan — candidates for Bojo, Tys Assistant and the master brain",
             "",
             f"Scanned: **{len(rows)} unique repositories** across "
             f"{len(_load_json(DONE, {}).get('done') or [])} search queries. "
             "Generated by `tools/github_scan.py`; raw records in "
             "`state/evidence/github_scan_20261104/repos.jsonl`.",
             "",
             "Licence classes: permissive = usable in either lane; copyleft = local-lane "
             "unless the network-copyleft review is done; restricted = do not adopt; "
             "unknown = review the licence before use.",
             ""]
    for focus, title in (("bojo", "Bojo — local chat, memory, tools, voice"),
                         ("tys", "Tys Assistant — agents, coding, browser, evaluation"),
                         ("brain", "Master brain — knowledge, policy, context, provenance")):
        lines += [f"## {title}", "",
                  "| repo | stars | licence | pushed | what it is |",
                  "|---|---|---|---|---|"]
        for row in ranked[focus][:per_focus]:
            lic = row.get("licence") or {}
            desc = (row.get("description") or "").replace("|", "/")[:160]
            lines.append(
                f"| [{row['full_name']}]({row['url']}) | {row.get('stars', 0):,} | "
                f"{lic.get('spdx') or 'unknown'} | {(row.get('pushed_at') or '')[:10]} | {desc} |")
        lines.append("")
    (REPORT_DIR / "raw_candidates.md").write_text("\n".join(lines), encoding="utf-8")

    shortlist = {focus: [
        {"full_name": r["full_name"], "url": r["url"], "stars": r["stars"],
         "licence": (r.get("licence") or {}).get("spdx"),
         "licence_class": (r.get("licence") or {}).get("class"),
         "description": r.get("description")}
        for r in ranked[focus][:per_focus]]
        for focus in ranked}
    _save_json(REPORT_DIR / "shortlist.json",
               {"generated_at": _now(), "unique_repos": len(rows), "shortlist": shortlist})
    return {"unique_repos": len(rows), "report": str(REPORT_DIR / "raw_candidates.md"),
            "shortlist": str(REPORT_DIR / "shortlist.json")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wave", choices=sorted(WAVES), default="core")
    ap.add_argument("--max-pages", type=int, default=None)
    ap.add_argument("--pause", type=float, default=6.2)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--per-focus", type=int, default=40)
    args = ap.parse_args(argv)
    if args.report:
        print(json.dumps(report(per_focus=args.per_focus), indent=2))
        return 0
    selected = [QUERIES[i] for i in WAVES[args.wave]]
    summary = scan(selected, pause=args.pause, max_pages=args.max_pages)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
