"""Analyze the Master Plan V2 sweep: dedupe, license histogram, per-query tops.

Writes sweep_summary.md next to this file and prints the headline counts plus a
priority digest for the report author.
"""
from __future__ import annotations

import collections
import json
import pathlib

BASE = pathlib.Path(__file__).resolve().parent
ROWS = []
raw = (BASE / "github_sweep.jsonl").read_text(encoding="utf-8-sig", errors="replace")
for line in raw.splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        ROWS.append(json.loads(line))
    except json.JSONDecodeError:
        pass


def items_of(rec):
    it = rec.get("items")
    if isinstance(it, dict):
        return [it]
    return it or []


seen = set()
lic = collections.Counter()
fetched = 0
for rec in ROWS:
    for it in items_of(rec):
        seen.add(it.get("full_name"))
        fetched += 1
        lic[(it.get("license") or "NONE")] += 1

out = []
out.append("# Master Plan V2 sweep — GitHub summary")
out.append(f"\n- Query families: {len(ROWS)}")
out.append(f"- Repo records fetched: {fetched}")
out.append(f"- Unique repos surfaced: {len(seen)}")
total_matches = sum(int(r.get("total") or 0) for r in ROWS)
out.append(f"- Sum of per-query match counts (overlapping): {total_matches}")
out.append("\n## License histogram (fetched items)\n")
for k, v in lic.most_common(18):
    out.append(f"- {k}: {v}")
out.append("\n## Per-query top repos\n")
for rec in ROWS:
    its = sorted(items_of(rec), key=lambda x: -(x.get("stars") or 0))[:8]
    out.append(f"\n### {rec.get('q')}  ·  total={rec.get('total')}  ·  fetched={len(items_of(rec))}")
    for it in its:
        desc = (it.get("desc") or "").replace("|", "/")[:110]
        pushed = str(it.get("pushed") or "")[:10]
        out.append(f"- {it.get('full_name')} | ★{it.get('stars')} | {it.get('license') or 'NONE'} | {pushed} | {desc}")
(BASE / "sweep_summary.md").write_text("\n".join(out), encoding="utf-8")

print(f"queries={len(ROWS)} fetched={fetched} unique={len(seen)} matches_sum={total_matches}")
PRIO = ['topic:comfyui', 'topic:mcp-server', 'topic:mcp', 'speculative decoding', 'dspark',
        'faster-whisper streaming', 'whisper.cpp server', 'push-to-talk speech recognition',
        'topic:text-to-speech', 'kokoro tts', 'topic:vector-database', 'knowledge graph extraction llm',
        'a/b testing open source', 'llm evaluation harness', 'infographic generator',
        'social media scheduling self-hosted', 'machine translation offline', 'llm tool registry framework',
        'local llm tool calling agent', 'file watcher hot reload config', 'brand voice analysis',
        'amazon reviews dataset', 'packaging dieline dataset']
for rec in ROWS:
    if rec.get("q") in PRIO:
        tops = sorted(items_of(rec), key=lambda x: -(x.get("stars") or 0))[:5]
        digest = ", ".join(f"{t.get('full_name')}({t.get('stars')},{t.get('license') or 'NONE'})" for t in tops)
        print(f"[{rec.get('q')}] {digest}")
