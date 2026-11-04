# GitHub scan 2026-11-04 — Bojo, Tys Assistant, the master brain

**Question:** what exists on GitHub that Northstar OS can actually use to become substantially
better, with the leverage in Bojo, Tys Assistant and the master brain?

**Answer in one line:** the scan found a large universe (MCP servers, agent runtimes, memory and
retrieval stacks, eval and observability tools); the engineering judgement is in
[`ADOPTION_PLAN.md`](ADOPTION_PLAN.md) — twelve candidates, each tied to a file that exists.

---

## 1. Method (reproducible)

| Component | What it did |
|---|---|
| `tools/github_scan.py` | 62 targeted GitHub search queries (agents, MCP, memory, RAG, evals, voice, local inference, policy, provenance), paginated to the top 300–500 per query, `archived:false fork:false`, per-query star floor. Resumable; sleeps on the 10 req/min unauthenticated limit. |
| `tools/github_scan_awesome.py` | Reads 23 curated lists (awesome-mcp-servers, awesome-ai-agents, awesome-llmops, awesome-local-ai, awesome-selfhosted, llm-security, …) and extracts every `github.com/owner/repo` link with its context. |
| `tools/github_scan_enrich.py` | Fetches stars/licence/push date for a curated set the search queries missed (core API, 60/hour). |
| `tools/github_scan_merge.py` | Merges both corpora, classifies discovery-only rows into the three focus areas, writes the catalog. |

Raw data:

* `state/evidence/github_scan_20261104/repos.jsonl` — enriched rows (stars, licence, push date)
* `state/evidence/github_scan_20261104/awesome_links.jsonl` — discovery-only rows with list context
* `state/evidence/github_scan_20261104/merged.jsonl` — the merged universe
* `state/evidence/github_scan_20261104/summary.json`, `merged_summary.json` — counts
* `reports/github_scan_20261104/merged_catalog.md` — the generated tables

## 2. Scale

**12,135 unique repositories discovered** — 5,414 enriched with stars, licence and last-push
metadata; 6,721 discovery-only from curated lists. 62 search queries (108 API requests, resumable
under the unauthenticated 10/min limit) plus 23 curated lists. Breakdown by focus: Bojo 969,
Tys Assistant 7,515, master brain 3,651. Licence classes: 3,911 permissive, 395 copyleft, 71 other,
7,758 unknown (mostly discovery-only rows — unknown until the licence file is read).

Counts are written by `tools/github_scan_merge.py` to
`state/evidence/github_scan_20261104/merged_summary.json`.

Discovery-only rows are not recommendations: a name in an awesome list is a lead, and its licence
is unknown until read. The catalog marks those `needs_metadata: true`.

## 3. What the scan actually surfaced

The unfamiliar, high-signal finds — not the famous projects everyone already knows:

| Repo | Stars | Licence | Why it matters here |
|---|---|---|---|
| `builderz-labs/mission-control` | 6,445 | MIT | Self-hosted control plane for agents: dispatch, review runs, spend, approvals. Tys has the data but no operator surface. |
| `langwatch/langwatch` | 5,011 | Apache-2.0 | Agent observability + evals, self-hosted. |
| `trycua/cua` | 31,729 | MIT | Computer-use drivers, cross-OS sandboxes and benchmarks — the browser/desktop lane's missing test rig. |
| `steel-dev/steel-browser` | 7,921 | Apache-2.0 | Browser API built for agents; reference for the session/lease model. |
| `agent-sandbox/agent-sandbox` | 229 | Apache-2.0 | Sandbox platform for agent code execution. |
| `abshkbh/arrakis` | 893 | AGPL-3.0 | Self-hosted sandbox; local-lane only. |
| `VeraTools/vera` | 123 | MIT | Local code search: BM25 + vector + cross-encoder rerank. |
| `remete618/widemem-ai` | 50 | Apache-2.0 | Local-first memory layer on Ollama. |
| `benmaster82/Kwipu` | 612 | MIT | Fully local Graph RAG over Markdown notes. |
| `RoyalCities/RC-Home-Assistant-Low-VRAM` | 253 | MIT | Local voice stack with persistent memory on low VRAM. |
| `sqliteai/adam` | 124 | MIT | Embeddable C agent library (tool calling, local/cloud LLMs). |
| `darrenhinde/OpenAgentsControl` | 4,966 | MIT | Plan-first workflow with approval-based execution. |
| `spec-kitty/spec-kitty` | 1,713 | MIT | Spec-driven development with organisational governance. |
| `UiPath/coder_eval` | 156 | Apache-2.0 | "Playwright for coding agents": tests skills, MCP servers and CLIs actually work. |
| `getagentseal/codeburn` | 11,682 | MIT | Local token/cost tracking across coding agents. |
| `bytedance/deer-flow` | 84,983 | MIT | Long-horizon superagent harness (research/code/create). |
| `tirth8205/code-review-graph` | 32,589 | MIT | Local persistent map of a repository (symbols, call edges, docs) over MCP. |
| `open-multi-agent/open-multi-agent` | 7,047 | MIT | Durable approvals and verifiable run records for agent fleets. |
| `OthmanAdi/planning-with-files` | 27,882 | MIT | File-based planning that survives crashes — the pattern Tys already uses. |
| `cobusgreyling/loop-engineering` | 11,693 | MIT | Patterns for the loop (verification, stop conditions, budgets) Northstar runs nightly. |
| `trustgraph-ai/trustgraph` | 2,886 | Apache-2.0 | Governance platform tying policy, knowledge and provenance into one graph. |
| `topoteretes/cognee` | 33,061 | Apache-2.0 | Open memory platform for agents (graph + vector). |
| `memvid/memvid` | 17,365 | Apache-2.0 | Serverless memory layer in a single file. |

The full ranked tables are in `merged_catalog.md` (top 40 enriched + top 40 discovery-only per
focus). The catalogue is deliberately not padded: 4,600+ of the discoveries are MCP servers, and
most are thin wrappers. The plan picks the ones with a real integration point.

## 4. Limitations (read before quoting a number)

1. **Stars are not quality, and 2026 star curves are inflated.** A 100k-star repo can be a landing
   page; a 50-star repo can be the right 300 lines. Several repos in this scan were created in 2026
   and carry six-figure stars (`paperclipai/paperclip` 111k, `Graphify-Labs/graphify` 142k,
   `DeusData/codebase-memory-mcp` 48k). The plan picks on integration fit and licence, not stars;
   treat the star counts as reach, not proof.
2. **Licences are metadata, not legal advice.** `NOASSERTION` means the file needs a read
   (Langfuse, Phoenix, LiteLLM all have enterprise folders). `daytonaio/daytona` has **no licence**
   and is rejected.
3. **Search is rate-limited.** Unauthenticated: 10 requests/minute. The scan is resumable; a rerun
   with a token would be faster and deeper.
4. **Discovery-only rows have no stars/licence.** They are leads, not candidates.
5. **The MCP list dominates the raw count.** 4,629 servers ≠ 4,629 useful tools; the kernel's policy
   still decides what may run.
6. **No candidate was installed in this pass.** Adoption is the next unit; the plan names the
   measurement that would justify each one.

## 5. Rerun

```powershell
python tools/github_scan.py --wave core      # ~150 requests, ~15 min
python tools/github_scan.py --wave deep      # narrow gap queries
python tools/github_scan_awesome.py
python tools/github_scan_enrich.py
python tools/github_scan_merge.py --top 40
```

No credentials, no Amazon request, no spend. Everything is written under
`state/evidence/github_scan_20261104/` and `reports/github_scan_20261104/`.
