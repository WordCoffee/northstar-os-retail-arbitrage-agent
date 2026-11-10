"""Harvest the curated 'awesome' lists: breadth the search API cannot reach.

The GitHub search API is capped at 1000 results per query and 10 requests/min.
Awesome lists are human-curated indexes — one README can name 100-500 projects.
This reads a fixed set of high-signal lists (raw README, no API cost), extracts
`github.com/owner/repo` links, keeps the surrounding text as context, and writes
one JSONL row per unique repository with the list(s) that named it.

    python tools/github_scan_awesome.py
    python tools/github_scan_awesome.py --report

Links are discovery, not approval: stars/licence are enriched later where the
search API already saw the repo. `needs_metadata: true` means exactly that.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "state" / "evidence" / "github_scan_20261104"
OUT = RUN / "awesome_links.jsonl"
SUMMARY = RUN / "awesome_summary.json"

LISTS = [
    # agents / MCP / devtools
    "e2b-dev/awesome-ai-agents",
    "kaushikb11/awesome-llm-agents",
    "punkpeye/awesome-mcp-servers",
    "modelcontextprotocol/servers",
    "jamesmurdza/awesome-ai-devtools",
    "Sourcegraph/awesome-code-ai",
    "stingning/ano-awesome-llm",
    # local / self-hosted
    "janhq/awesome-local-ai",
    "awesome-selfhosted/awesome-selfhosted",
    "ollama/ollama",
    # memory / RAG / knowledge
    "brexhq/prompt-engineering",
    "dair-ai/Prompt-Engineering-Guide",
    "microsoft/RAG_Hack",
    "eosphoros-ai/Awesome-Text2SQL",
    # evaluation / observability / production
    "tensorchord/Awesome-LLMOps",
    "visenger/awesome-mlops",
    "EthicalML/awesome-production-machine-learning",
    "aishwaryanr/awesome-generative-ai-guide",
    # infra / orchestration
    "liyupi/ai-guide",
    "ashishps1/awesome-system-design-resources",
    # guardrails / security
    "guardrails-ai/guardrails",
    "protectai/ai-exploits",
    "corca-ai/awesome-llm-security",
]

HEADERS = {"User-Agent": "northstar-os-scan/1.0"}
LINK_RE = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
SKIP_OWNERS = {"topics", "sponsors", "login", "features", "about", "pricing",
               "marketplace", "collections", "trending", "settings", "apps",
               "orgs", "users", "site", "security", "enterprise", "readme"}
SKIP_REPOS = {"awesome", "awesome-awesomeness"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as response:
        return response.read().decode("utf-8", "replace")


def _readme(list_name: str) -> str:
    for branch in ("main", "master"):
        for name in ("README.md", "readme.md"):
            url = f"https://raw.githubusercontent.com/{list_name}/{branch}/{name}"
            try:
                return _fetch(url)
            except Exception:
                continue
    return ""


def harvest() -> Dict[str, Any]:
    RUN.mkdir(parents=True, exist_ok=True)
    seen: Dict[str, Dict[str, Any]] = {}
    lists_ok = 0
    for list_name in LISTS:
        text = _readme(list_name)
        if not text:
            print(f"[skip] {list_name}: README not reachable", flush=True)
            continue
        lists_ok += 1
        found = 0
        for match in LINK_RE.finditer(text):
            owner, repo = match.group(1), match.group(2)
            repo = repo.rstrip(").,;:'\"`")
            if owner.lower() in SKIP_OWNERS or repo.lower() in SKIP_REPOS:
                continue
            full = f"{owner}/{repo}"
            context = text[max(0, match.start() - 160):match.end() + 160]
            context = " ".join(context.split())[:300]
            row = seen.get(full.lower())
            if row is None:
                row = {"full_name": full, "url": f"https://github.com/{full}",
                       "listed_by": [], "context": context, "needs_metadata": True}
                seen[full.lower()] = row
                found += 1
            if list_name not in row["listed_by"]:
                row["listed_by"].append(list_name)
        print(f"[ok] {list_name}: {found} new links", flush=True)
        time.sleep(0.6)

    with OUT.open("w", encoding="utf-8") as handle:
        for row in seen.values():
            row["harvested_at"] = _now()
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    by_list = {}
    for row in seen.values():
        for name in row["listed_by"]:
            by_list[name] = by_list.get(name, 0) + 1
    summary = {"harvested_at": _now(), "lists_reached": lists_ok,
               "lists_total": len(LISTS), "unique_repos": len(seen),
               "by_list": dict(sorted(by_list.items(), key=lambda kv: -kv[1])[:20])}
    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args(argv)
    if args.report:
        print(SUMMARY.read_text(encoding="utf-8") if SUMMARY.is_file() else "{}")
        return 0
    print(json.dumps(harvest(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
