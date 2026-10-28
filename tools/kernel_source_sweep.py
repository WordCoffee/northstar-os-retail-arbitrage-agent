"""Kernel source sweep — 1,500 scored sources, with an honest provenance row.

Lanes:
  * GitHub search (15 query families, 100 per page) — metadata only.
  * The existing local corpus index (northstar.db) filtered to agent/kernel
    records, so work already on disk is reused rather than re-fetched.

No bundle analysis, no decompilation, no login. Every row records its URL,
licence and how it was obtained. The 100 read targets fetch a public README; the
12 deep reads are written by hand in DEEP_12.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research/assistant_intelligence_20261028"
DB = ROOT / "Northstar_backend/data/northstar.db"
UA = "NorthstarOS-KernelSweep/1.0 (local research; public metadata only)"

QUERIES = [
    "agent harness in:name,description,readme stars:>100",
    "coding agent in:name,description,readme stars:>100",
    "computer use agent in:name,description,readme stars:>50",
    "browser agent in:name,description,readme stars:>100",
    "plan mode agent in:name,description,readme stars:>20",
    "subagent in:name,description,readme stars:>20",
    "checkpoint agent in:name,description,readme stars:>20",
    "agent memory in:name,description,readme stars:>50",
    "repo map in:name,description,readme stars:>20",
    "agent eval benchmark in:name,description,readme stars:>100",
    "human in the loop agent in:name,description,readme stars:>20",
    "MCP agent framework in:name,description,readme stars:>50",
    "commerce copilot in:name,description,readme stars:>20",
    "seller assistant in:name,description,readme stars:>20",
    "voice agent in:name,description,readme stars:>100",
    "autonomous agent in:name,description,readme stars:>1000",
    "llm agent framework in:name,description,readme stars:>500",
    "workflow automation agent in:name,description,readme stars:>100",
    "agent toolkit in:name,description,readme stars:>100",
    "ai assistant desktop in:name,description,readme stars:>100",
]

CAPS = {
    "plan": ["plan mode", "planner", "planning", "todo", "task list", "steps"],
    "dag": ["dag", "directed acyclic", "workflow graph", "task graph", "pipeline"],
    "subagent": ["subagent", "sub-agent", "multi-agent", "delegation", "orchestrator"],
    "context": ["context window", "compaction", "repo map", "retrieval", "rag"],
    "memory": ["memory", "knowledge base", "persistent context", "claude.md"],
    "checkpoint": ["checkpoint", "rewind", "snapshot", "resume", "rollback"],
    "policy": ["permission", "sandbox", "guardrail", "approval", "human in the loop",
               "hitl", "policy"],
    "diff": ["diff", "code review", "patch", "hunk"],
    "verify": ["test", "eval", "verifier", "benchmark", "swe-bench", "assertion"],
    "skills": ["skill", "recipe", "procedure", "playbook"],
    "budget": ["budget", "cost", "token limit", "timeout", "rate limit"],
    "journal": ["journal", "replay", "trace", "telemetry", "observability"],
    "commerce": ["commerce", "shopify", "amazon", "seller", "listing", "ecommerce",
                 "product"],
    "voice": ["voice", "speech", "tts", "realtime", "audio"],
    "artifact": ["artifact", "canvas", "document", "editor", "design"],
}

PERMISSIVE = {"mit", "apache-2.0", "bsd-2-clause", "bsd-3-clause", "isc",
              "mpl-2.0", "cc0-1.0", "unlicense", "wtfpl"}
COPYLEFT = {"gpl-3.0", "gpl-2.0", "agpl-3.0", "lgpl-3.0", "lgpl-2.1"}


def _get(url: str, *, timeout: int = 30) -> tuple[int, Dict[str, str], bytes]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def github_search(query: str, per_page: int = 100) -> List[dict]:
    url = ("https://api.github.com/search/repositories?q="
           + urllib.parse.quote(query) + f"&per_page={per_page}&sort=stars")
    for attempt in range(3):
        code, headers, body = _get(url)
        if code == 200:
            return json.loads(body).get("items") or []
        if code in (403, 429):
            reset = int(headers.get("X-RateLimit-Reset") or 0)
            wait = max(5, reset - int(time.time()) + 2)
            print(f"  rate limit; sleeping {wait}s", flush=True)
            time.sleep(min(wait, 120))
            continue
        print(f"  HTTP {code}: {body[:120]}", flush=True)
        time.sleep(2)
    return []


def licence_of(item: dict) -> str:
    lic = item.get("license") or {}
    return str(lic.get("spdx_id") or "NONE").lower()


def caps_of(text: str) -> List[str]:
    low = text.lower()
    return [name for name, words in CAPS.items() if any(w in low for w in words)]


def score(row: dict) -> None:
    caps = set(row["capabilities"].split(";")) if row["capabilities"] else set()
    stars = int(row.get("stars") or 0)
    base = math.log10(stars + 1)
    ty = (3 * ("plan" in caps) + 2 * ("dag" in caps) + 3 * ("subagent" in caps)
          + 2 * ("context" in caps) + 2 * ("memory" in caps)
          + 2 * ("checkpoint" in caps) + 3 * ("policy" in caps)
          + 1 * ("diff" in caps) + 2 * ("verify" in caps)
          + 1 * ("skills" in caps) + 1 * ("budget" in caps)
          + 1 * ("journal" in caps) + base)
    bojo = (3 * ("commerce" in caps) + 2 * ("voice" in caps)
            + 2 * ("artifact" in caps) + 2 * ("memory" in caps)
            + 1 * ("plan" in caps) + 1 * ("policy" in caps) + base)
    row["ty_score"] = round(ty, 2)
    row["bojo_score"] = round(bojo, 2)
    lic = row["licence"]
    if lic in PERMISSIVE:
        row["rea_feasibility"] = "read/adapt"
    elif lic in COPYLEFT:
        row["rea_feasibility"] = "read-only (copyleft)"
    else:
        row["rea_feasibility"] = "observe only (no licence)"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=1500)
    ap.add_argument("--per-query", type=int, default=100)
    ap.add_argument("--fetch-readmes", action="store_true")
    ap.add_argument("--readme-limit", type=int, default=100)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    rows: Dict[str, dict] = {}

    print(f"GitHub: {len(QUERIES)} query families", flush=True)
    for i, q in enumerate(QUERIES, 1):
        items = github_search(q, args.per_query)
        print(f"  [{i}/{len(QUERIES)}] {q[:48]} -> {len(items)}", flush=True)
        for it in items:
            name = it.get("full_name") or ""
            if not name or name in rows:
                continue
            desc = it.get("description") or ""
            topics = " ".join(it.get("topics") or [])
            rows[name] = {
                "type": "github", "name": name,
                "url": it.get("html_url") or "",
                "licence": licence_of(it),
                "stars": int(it.get("stargazers_count") or 0),
                "pushed_at": str(it.get("pushed_at") or "")[:10],
                "description": desc.replace("\n", " ")[:400],
                "capabilities": ";".join(caps_of(f"{name} {desc} {topics}")),
                "source": "github_search",
                "homepage": it.get("homepage") or "",
            }
        if i < len(QUERIES):
            time.sleep(7)

    # Existing local corpus, filtered to agent/kernel material.
    if DB.is_file():
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        words = ["agent", "plan", "checkpoint", "subagent", "memory", "browser",
                 "harness", "workflow", "tool use", "human in the loop"]
        like = " OR ".join(["lower(title) LIKE ? OR lower(summary) LIKE ?"] * len(words))
        params = [f"%{w}%" for w in words for _ in (0, 1)]
        cur = con.execute(
            f"SELECT source_id, title, url, license, summary FROM corpus_records "
            f"WHERE source IN ('github','hf') AND ({like}) LIMIT 1500", params)
        for r in cur:
            key = "corpus:" + str(r["source_id"])
            if key in rows:
                continue
            desc = (r["summary"] or "")[:400].replace("\n", " ")
            rows[key] = {
                "type": "corpus", "name": r["title"] or r["source_id"],
                "url": r["url"] or "", "licence": (r["license"] or "none").lower(),
                "stars": 0, "pushed_at": "", "description": desc,
                "capabilities": ";".join(caps_of(f"{r['title']} {desc}")),
                "source": "local_corpus", "homepage": "",
            }
        con.close()

    scored = list(rows.values())
    for r in scored:
        score(r)
    scored.sort(key=lambda r: (-r["ty_score"], -r["stars"], r["name"]))
    scored = scored[: args.limit]

    # 100 read targets: round-robin across capabilities, then fill by score.
    by_cap: Dict[str, List[dict]] = {c: [] for c in CAPS}
    for r in scored:
        for c in (r["capabilities"].split(";") if r["capabilities"] else []):
            if c in by_cap:
                by_cap[c].append(r)
    read: List[dict] = []
    seen = set()
    for c in CAPS:
        for r in by_cap.get(c, [])[:9]:
            if id(r) not in seen:
                seen.add(id(r)); read.append(r)
            if len(read) >= args.readme_limit:
                break
        if len(read) >= args.readme_limit:
            break
    for r in scored:
        if len(read) >= args.readme_limit:
            break
        if id(r) not in seen:
            seen.add(id(r)); read.append(r)
    for r in scored:
        r["read_target"] = "yes" if id(r) in seen else ""

    # README fetch for the read targets (public raw content only).
    if args.fetch_readmes:
        rd = OUT / "readmes"
        rd.mkdir(parents=True, exist_ok=True)
        for i, r in enumerate(read, 1):
            if r["type"] != "github":
                continue
            name = r["name"]
            for branch in ("main", "master"):
                url = f"https://raw.githubusercontent.com/{name}/{branch}/README.md"
                code, _, body = _get(url)
                if code == 200:
                    text = body.decode("utf-8", errors="replace")[:20000]
                    (rd / (name.replace("/", "__") + ".md")).write_text(
                        text, encoding="utf-8")
                    r["read_note"] = text.replace("\n", " ")[:300]
                    break
            if i % 20 == 0:
                print(f"  readme {i}/{len(read)}", flush=True)
            time.sleep(0.2)

    fields = ["type", "name", "url", "licence", "stars", "pushed_at",
              "description", "capabilities", "ty_score", "bojo_score",
              "rea_feasibility", "read_target", "source", "homepage", "read_note"]
    csv_path = OUT / "SOURCES_1500.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in scored:
            w.writerow({k: r.get(k, "") for k in fields})

    lic_hist: Dict[str, int] = {}
    cap_hist: Dict[str, int] = {}
    for r in scored:
        lic_hist[r["licence"]] = lic_hist.get(r["licence"], 0) + 1
        for c in (r["capabilities"].split(";") if r["capabilities"] else []):
            cap_hist[c] = cap_hist.get(c, 0) + 1
    triage = [
        "# Kernel source triage", "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        f"Scored: **{len(scored)}** (cap {args.limit}) · read targets: **{len(read)}** · "
        f"deep: **12** (manual, see DEEP_12.md)", "",
        "## Method", "",
        "- GitHub search metadata (15 query families, 100/page, public API).",
        "- Existing local corpus rows filtered to agent/kernel terms.",
        "- Deterministic capability tags + stars; no model judgement at this scale.",
        "- READMEs for the 100 read targets are stored under `readmes/`.",
        "- No bundle analysis, no decompilation, no login, no paid source.", "",
        "## Licence histogram", "", "| licence | count |", "|---|---|",
    ]
    for k, v in sorted(lic_hist.items(), key=lambda kv: -kv[1]):
        triage.append(f"| {k or 'none'} | {v} |")
    triage += ["", "## Capability coverage", "", "| capability | sources |", "|---|---|"]
    for k, v in sorted(cap_hist.items(), key=lambda kv: -kv[1]):
        triage.append(f"| {k} | {v} |")
    triage += ["", "## Honest limits", "",
               "- Metadata scoring identifies *candidates*; it does not prove quality.",
               "- The 100 read targets are README-level reads, not full source reviews.",
               "- The 12 deep reads are the only sources whose behaviour is specified "
               "in `KERNEL_SPEC.md`.", ""]
    (OUT / "TRIAGE.md").write_text("\n".join(triage), encoding="utf-8")
    print(json.dumps({"scored": len(scored), "read": len(read),
                      "csv": str(csv_path.relative_to(ROOT)),
                      "licences": lic_hist}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
