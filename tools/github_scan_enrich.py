"""Enrich hand-picked discovery names with GitHub metadata (stars, licence, push).

The search scan only sees what its queries returned; the awesome lists named
thousands more, without metadata. This fetches the metadata for a curated set of
high-signal names via `GET /repos/{owner}/{name}` (core API, 60/hour
unauthenticated), skipping anything already enriched. It stops cleanly on the
rate limit and is resumable.

    python tools/github_scan_enrich.py
    python tools/github_scan_enrich.py --list        # show the set
"""
from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "state" / "evidence" / "github_scan_20261104"
JSONL = RUN / "repos.jsonl"
DONE = RUN / "enriched_done.json"
UA = "northstar-os-scan/1.0"

#: Curated: the projects most likely to move Bojo, Tys or the brain, chosen from
#: the awesome harvest and the current stack's known gaps. Not a popularity list.
ENRICH: List[Dict[str, str]] = [
    # Bojo
    {"name": "mem0ai/mem0", "focus": "bojo"},
    {"name": "letta-ai/letta", "focus": "bojo"},
    {"name": "supermemoryai/supermemory", "focus": "bojo"},
    {"name": "qdrant/fastembed", "focus": "bojo"},
    {"name": "AnswerDotAI/rerankers", "focus": "bojo"},
    {"name": "dottxt-ai/outlines", "focus": "bojo"},
    {"name": "guidance-ai/guidance", "focus": "bojo"},
    {"name": "stanfordnlp/dspy", "focus": "bojo"},
    {"name": "simonw/llm", "focus": "bojo"},
    {"name": "ggml-org/llama.cpp", "focus": "bojo"},
    {"name": "ollama/ollama", "focus": "bojo"},
    {"name": "oobabooga/text-generation-webui", "focus": "bojo"},
    {"name": "LostRuins/koboldcpp", "focus": "bojo"},
    {"name": "rhasspy/piper", "focus": "bojo"},
    {"name": "SYSTRAN/faster-whisper", "focus": "bojo"},
    {"name": "Vaibhavs10/insanely-fast-whisper", "focus": "bojo"},
    {"name": "BerriAI/litellm", "focus": "bojo"},
    {"name": "pydantic/pydantic-ai", "focus": "bojo"},
    # Tys
    {"name": "All-Hands-AI/OpenHands", "focus": "tys"},
    {"name": "SWE-agent/SWE-agent", "focus": "tys"},
    {"name": "Aider-AI/aider", "focus": "tys"},
    {"name": "browser-use/browser-use", "focus": "tys"},
    {"name": "browserbase/stagehand", "focus": "tys"},
    {"name": "microsoft/playwright-mcp", "focus": "tys"},
    {"name": "e2b-dev/E2B", "focus": "tys"},
    {"name": "daytonaio/daytona", "focus": "tys"},
    {"name": "humanlayer/humanlayer", "focus": "tys"},
    {"name": "langfuse/langfuse", "focus": "tys"},
    {"name": "Arize-ai/phoenix", "focus": "tys"},
    {"name": "promptfoo/promptfoo", "focus": "tys"},
    {"name": "confident-ai/deepeval", "focus": "tys"},
    {"name": "explodinggradients/ragas", "focus": "tys"},
    {"name": "ast-grep/ast-grep", "focus": "tys"},
    {"name": "yamadashy/repomix", "focus": "tys"},
    {"name": "langchain-ai/langgraph", "focus": "tys"},
    {"name": "modelcontextprotocol/python-sdk", "focus": "tys"},
    {"name": "openai/openai-agents-python", "focus": "tys"},
    {"name": "google/adk-python", "focus": "tys"},
    # Brain
    {"name": "getzep/graphiti", "focus": "brain"},
    {"name": "microsoft/graphrag", "focus": "brain"},
    {"name": "HKUDS/LightRAG", "focus": "brain"},
    {"name": "infiniflow/ragflow", "focus": "brain"},
    {"name": "docling-project/docling", "focus": "brain"},
    {"name": "Unstructured-IO/unstructured", "focus": "brain"},
    {"name": "qdrant/qdrant", "focus": "brain"},
    {"name": "chroma-core/chroma", "focus": "brain"},
    {"name": "asg017/sqlite-vec", "focus": "brain"},
    {"name": "open-policy-agent/opa", "focus": "brain"},
    {"name": "cedar-policy/cedar", "focus": "brain"},
    {"name": "guardrails-ai/guardrails", "focus": "brain"},
    {"name": "NVIDIA/NeMo-Guardrails", "focus": "brain"},
    {"name": "567-labs/instructor", "focus": "brain"},
    {"name": "Portkey-AI/gateway", "focus": "brain"},
    {"name": "OpenLineage/OpenLineage", "focus": "brain"},
    {"name": "iterative/dvc", "focus": "brain"},
    {"name": "EleutherAI/lm-evaluation-harness", "focus": "brain"},
    {"name": "UKGovernmentBEIS/inspect_ai", "focus": "brain"},
    {"name": "temporalio/sdk-python", "focus": "brain"},
    {"name": "PrefectHQ/prefect", "focus": "brain"},
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _names_on_disk() -> set:
    names = set()
    if not JSONL.is_file():
        return names
    with JSONL.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("full_name"):
                names.add(row["full_name"].lower())
    return names


def _get(url: str) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _row(repo: Dict[str, Any], focus: str) -> Dict[str, Any]:
    spdx = ((repo.get("license") or {}).get("spdx_id") or "").upper()
    cls = "unknown"
    if spdx in {"MIT", "APACHE-2.0", "BSD-2-CLAUSE", "BSD-3-CLAUSE", "ISC",
                "MPL-2.0", "UNLICENSE", "0BSD"}:
        cls = "permissive"
    elif spdx in {"GPL-2.0", "GPL-3.0", "AGPL-3.0", "LGPL-2.1", "LGPL-3.0"}:
        cls = "copyleft"
    elif spdx and "NC" in spdx:
        cls = "restricted"
    stars = int(repo.get("stargazers_count") or 0)
    return {
        "full_name": repo.get("full_name"), "url": repo.get("html_url"),
        "description": (repo.get("description") or "").strip()[:400],
        "stars": stars, "forks": int(repo.get("forks_count") or 0),
        "language": repo.get("language"), "topics": list(repo.get("topics") or [])[:20],
        "pushed_at": repo.get("pushed_at"), "created_at": repo.get("created_at"),
        "archived": bool(repo.get("archived")), "fork": bool(repo.get("fork")),
        "open_issues": int(repo.get("open_issues_count") or 0),
        "homepage": repo.get("homepage"), "default_branch": repo.get("default_branch"),
        "licence": {"spdx": spdx, "class": cls,
                    "commercial": cls in ("permissive", "copyleft") if spdx else None},
        "focus": focus, "focus_scores": {focus: 1},
        "relevance": round(3.0 + math.log10(max(stars, 1)) * 2.0, 3),
        "found_by": "curated-enrich", "source": "search", "scanned_at": _now(),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--pause", type=float, default=1.0)
    args = ap.parse_args(argv)
    if args.list:
        for item in ENRICH:
            print(f"{item['focus']:6} {item['name']}")
        return 0
    RUN.mkdir(parents=True, exist_ok=True)
    on_disk = _names_on_disk()
    done = set(_load(DONE, {"done": []}).get("done") or [])
    added = skipped = failed = 0
    for item in ENRICH:
        name = item["name"]
        if name.lower() in on_disk or name.lower() in done:
            skipped += 1
            continue
        try:
            repo = _get(f"https://api.github.com/repos/{name}")
        except urllib.error.HTTPError as exc:
            print(f"[{exc.code}] {name}", flush=True)
            failed += 1
            if exc.code in (403, 429):
                break
            continue
        except Exception as exc:  # noqa: BLE001
            print(f"[error] {name}: {exc}", flush=True)
            failed += 1
            continue
        with JSONL.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(_row(repo, item["focus"]), ensure_ascii=False) + "\n")
        done.add(name.lower())
        added += 1
        print(f"[ok] {name} ({repo.get('stargazers_count', 0):,} stars)", flush=True)
        time.sleep(args.pause)
    DONE.write_text(json.dumps({"done": sorted(done), "updated_at": _now()},
                               indent=2), encoding="utf-8")
    print(json.dumps({"added": added, "skipped": skipped, "failed": failed,
                      "unique_on_disk": len(_names_on_disk())}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
