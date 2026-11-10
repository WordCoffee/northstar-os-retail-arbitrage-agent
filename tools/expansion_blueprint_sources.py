"""Resolve exact source coordinates for the Component Adaptation Blueprints.

For each candidate: licence, default branch, HEAD commit sha, and the paths that
match the extraction target. One metadata request, one commit request and one
tree request per repo (core API, 60/hour unauthenticated). No file contents are
copied; this only records coordinates.
"""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent")
OUT = ROOT / "state/evidence/expansion_20261104/blueprint_sources.json"
HEADERS = {"User-Agent": "northstar-expansion/1.0",
           "Accept": "application/vnd.github+json"}

REPOS = {
    "ggml-org/llama.cpp": ["grammar", "gbnf", "json"],
    "dottxt-ai/outlines": ["fsm", "json_schema", "generate"],
    "docling-project/docling": ["layout", "pipeline", "ocr"],
    "PaddlePaddle/PaddleOCR": ["ppstructure", "layout", "table"],
    "lllyasviel/IC-Light": ["iclight", "pipeline", "relight"],
    "VAST-AI-Research/TripoSR": ["system", "models", "render"],
    "getzep/graphiti": ["edges", "nodes", "driver"],
    "browser-use/browser-use": ["controller", "agent", "dom"],
    "UKGovernmentBEIS/inspect_ai": ["eval", "scorer", "solver"],
    "mem0ai/mem0": ["memory", "graph", "main"],
}


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    out = {}
    for repo, keywords in REPOS.items():
        try:
            meta = get(f"https://api.github.com/repos/{repo}")
            branch = meta.get("default_branch") or "main"
            commit = get(f"https://api.github.com/repos/{repo}/commits/{branch}")
            sha = commit.get("sha")
            tree = get(f"https://api.github.com/repos/{repo}/git/trees/{sha}?recursive=1")
            paths = [item["path"] for item in tree.get("tree") or []
                     if item.get("type") == "blob"]
            wanted = [p for p in paths
                      if any(k in p.lower() for k in keywords)
                      and p.lower().endswith((".py", ".cpp", ".h", ".md", ".json", ".txt"))]
            licence = (meta.get("license") or {}).get("spdx_id") or ""
            out[repo] = {
                "repo": repo,
                "url": meta.get("html_url"),
                "licence": licence,
                "licence_name": (meta.get("license") or {}).get("name"),
                "default_branch": branch,
                "commit": sha,
                "commit_url": f"https://github.com/{repo}/commit/{sha}",
                "pushed_at": meta.get("pushed_at"),
                "stars": meta.get("stargazers_count"),
                "paths": wanted[:40],
                "path_count": len(wanted),
            }
            print(f"[ok] {repo} {sha[:10]} {licence} paths={len(wanted)}", flush=True)
        except urllib.error.HTTPError as exc:
            out[repo] = {"repo": repo, "error": f"HTTP {exc.code}"}
            print(f"[{exc.code}] {repo}", flush=True)
        except Exception as exc:  # noqa: BLE001
            out[repo] = {"repo": repo, "error": str(exc)}
            print(f"[err] {repo}: {exc}", flush=True)
        time.sleep(1.0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
