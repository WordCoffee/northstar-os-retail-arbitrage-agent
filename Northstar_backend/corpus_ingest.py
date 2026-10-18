"""Curated corpus ingest (V3 S8) — local, pre-aggregated index files only.

No scraping, no network, no paid services. The ingest reads files the operator
already has on disk (the `research/**` tree, GitHub/HF sweeps, source registries)
and writes one provenance-labelled record per item into the local corpus index.

Honesty rules:
  • Every record carries its `source`, its `license` **as reported by the sweep**,
    and a `provenance` blob (query, stars, byte counts, origin file). The engine
    reports what the file says; it never upgrades an unknown license or invents a
    field.
  • Ingest is idempotent (content hash): re-running a source skips unchanged
    records. Each run records honest counts and any per-record errors.
  • Files are read tolerantly (UTF-8 BOM, mojibake) but a broken line is skipped
    and counted — never silently dropped without a count.
"""

from __future__ import annotations

import csv
import json
import os
from typing import Any, Dict, List, Optional

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Known, local corpus sources. `path` is relative to the repo root. No source
#: accepts an arbitrary path — the ingest surface offers these names only.
SOURCES: Dict[str, Dict[str, str]] = {
    "github_sweep": {"path": "research/master_plan_v2_sweep_20261016/github_sweep.jsonl",
                     "loader": "github_sweep"},
    "github_csv": {"path": "research/packify_quality_deep_dive_20261016/SOURCES_GITHUB.csv",
                   "loader": "github_csv"},
    "hf_datasets": {"path": "research/master_plan_v2_sweep_20261016/hf_datasets.json",
                    "loader": "hf_datasets"},
    "docs": {"path": "research", "loader": "docs"},
    "design_sources": {"path": "research/design_studio_deep_research_20261008/SOURCES.csv",
                       "loader": "sources_csv"},
    "stack_sources": {"path": "research/production_stack_scan_20261016/SOURCES.csv",
                      "loader": "sources_csv"},
}


def _clean(value: Any, limit: int = 2000) -> str:
    if value is None:
        return ""
    s = " ".join(str(value).replace("|", " ").split())
    return s[:limit]


def _first_heading(text: str) -> str:
    for line in (text or "").splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()[:160]
    return ""


def _split_topics(value: Any) -> List[str]:
    if not value:
        return []
    return [t.strip() for t in str(value).replace(";", ",").split(",") if t.strip()]


# ── Loaders ─────────────────────────────────────────────────────────────────

def load_github_sweep(path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            query = obj.get("q")
            items = obj.get("items") or []
            if isinstance(items, dict):
                items = list(items.values())
            for it in items:
                if not isinstance(it, dict):
                    continue
                full = str(it.get("full_name") or "").strip()
                if not full:
                    continue
                out.append({
                    "source": "github", "source_id": full, "kind": "repo",
                    "title": full, "url": f"https://github.com/{full}",
                    "license": it.get("license"),
                    "summary": _clean(it.get("desc")),
                    "tags": it.get("topics") or [],
                    "provenance": {"query": query, "stars": it.get("stars"),
                                   "lang": it.get("lang"), "pushed": it.get("pushed"),
                                   "origin": "master_plan_v2_sweep_20261016/github_sweep.jsonl"},
                })
    return out


def load_github_csv(path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh):
            full = str(row.get("full_name") or "").strip()
            if not full:
                continue
            out.append({
                "source": "github", "source_id": full, "kind": "repo",
                "title": full, "url": row.get("url") or f"https://github.com/{full}",
                "license": None, "summary": _clean(row.get("description")),
                "tags": _split_topics(row.get("topics")),
                "provenance": {"stars": row.get("stars"), "lang": row.get("language"),
                               "pushed": row.get("pushed_at"), "query": row.get("query"),
                               "origin": "packify_quality_deep_dive_20261016/SOURCES_GITHUB.csv"},
            })
    return out


def load_hf_datasets(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
        data = json.load(fh)
    out: List[Dict[str, Any]] = []
    for group in data if isinstance(data, list) else []:
        term = group.get("term")
        for it in (group.get("items") or []):
            did = str(it.get("id") or "").strip()
            if not did:
                continue
            tags = it.get("tags") or []
            out.append({
                "source": "hf", "source_id": did, "kind": "dataset", "title": did,
                "url": f"https://huggingface.co/datasets/{did}",
                "summary": ", ".join(str(t) for t in tags),
                "tags": tags,
                "provenance": {"term": term, "downloads": it.get("downloads"),
                               "likes": it.get("likes"),
                               "origin": "master_plan_v2_sweep_20261016/hf_datasets.json"},
            })
    return out


def load_sources_csv(path: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8-sig", errors="replace", newline="") as fh:
        for row in csv.DictReader(fh):
            sid = str(row.get("source_id") or row.get("id") or row.get("url") or "").strip()
            if not sid:
                continue
            out.append({
                "source": "registry", "source_id": sid, "kind": "source_row",
                "title": _clean(row.get("label") or row.get("publisher")
                                or row.get("repo") or sid, 160),
                "url": row.get("url"), "license": row.get("license"),
                "summary": _clean(row.get("notes") or row.get("summary") or row.get("label")),
                "tags": [row.get("publisher")] if row.get("publisher") else [],
                "provenance": {"row": {k: v for k, v in row.items() if v},
                               "origin": os.path.basename(os.path.dirname(path)) + "/"
                               + os.path.basename(path)},
            })
    return out


def load_docs(root: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for dirpath, _dirs, files in os.walk(root):
        for fn in files:
            if not fn.lower().endswith((".md", ".txt")):
                continue
            full_path = os.path.join(dirpath, fn)
            rel = os.path.relpath(full_path, _REPO_ROOT).replace("\\", "/")
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except OSError:
                continue
            out.append({
                "source": "doc", "source_id": rel, "kind": "doc",
                "title": _first_heading(text) or fn, "url": None, "license": None,
                "summary": _clean(text[:400]),
                "content": text[:200000],
                "provenance": {"path": rel, "bytes": len(text), "origin": "research_tree"},
            })
    return out


LOADERS = {
    "github_sweep": load_github_sweep,
    "github_csv": load_github_csv,
    "hf_datasets": load_hf_datasets,
    "sources_csv": load_sources_csv,
    "docs": load_docs,
}


# ── Drivers ─────────────────────────────────────────────────────────────────

def ingest_records(db, source: str, records: List[Dict[str, Any]],
                   source_path: str = "", *, run_id: Optional[str] = None) -> Dict[str, Any]:
    """Upsert records under one run; return honest counts + capped errors."""
    counts = {"records": 0, "inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
    errors: List[str] = []
    rid = run_id or db.corpus.start_run(source, source_path)
    try:
        for rec in records:
            counts["records"] += 1
            try:
                status = db.corpus.upsert(rec)
                counts[status] = counts.get(status, 0) + 1
            except Exception as exc:  # noqa: BLE001 - one bad record must not stop the run
                counts["errors"] += 1
                if len(errors) < 20:
                    errors.append(f"{rec.get('source_id')}: {exc}")
        db.corpus.finish_run(rid, "done", counts=counts, errors=errors)
        status = "done"
    except Exception as exc:  # noqa: BLE001
        errors.append(str(exc)[:300])
        db.corpus.finish_run(rid, "error", counts=counts, errors=errors)
        status = "error"
    return {"run_id": rid, "source": source, "status": status,
            "counts": counts, "errors": errors}


def ingest_source(db, name: str, *, repo_root: Optional[str] = None) -> Dict[str, Any]:
    """Resolve a known source to its local path and ingest it. Never a raw path."""
    spec = SOURCES.get(name)
    if not spec:
        raise ValueError(f"unknown corpus source '{name}' (known: {sorted(SOURCES)})")
    path = os.path.join(repo_root or _REPO_ROOT, spec["path"])
    rid = db.corpus.start_run(name, spec["path"])
    if not os.path.exists(path):
        db.corpus.finish_run(rid, "error", counts={"records": 0},
                             errors=[f"missing path: {spec['path']}"])
        return {"run_id": rid, "source": name, "status": "error",
                "counts": {"records": 0}, "errors": [f"missing path: {spec['path']}"]}
    records = LOADERS[spec["loader"]](path)
    return ingest_records(db, name, records, spec["path"], run_id=rid)


def ingest_all(db, *, repo_root: Optional[str] = None) -> List[Dict[str, Any]]:
    return [ingest_source(db, name, repo_root=repo_root) for name in SOURCES]
