# Adoption plan — what to take from the scan, in order

The scan is discovery; this page is the engineering judgement. Twelve candidates, ordered by
return on effort, each tied to a file that already exists. Everything here is local-first and
compatible with the standing gates.

**Licence lanes (from AGENTS.md):** permissive = either lane; copyleft = local-lane unless the
network-copyleft review is done; "other/NOASSERTION" = read the licence before use. No candidate
here requires a paid service, an Amazon request, or a cloud call.

---

## Tier 0 — adopt now (no new runtime, or a small install)

### 1. Real embeddings in the memory index
**`asg017/sqlite-vec`** (8.2k, Apache-2.0) + the already-installed `qwen3-embedding:0.6b`.
`Northstar_backend/tys_ops/memory.py` embeds with a 256-dimension hashed bag-of-words and scans
cosine in Python. The corpus lane already proves the better pattern
(`corpus_drift.py`: Ollama embeddings, 1024-d, `vec0` virtual table). Port that pattern into
`MemoryIndex`: same API, real semantic recall, KNN in SQLite. Keep the hashed embedding as the
deterministic fallback when Ollama is down.
**Why now:** zero downloads, existing model, one file, measurable with a retrieval eval.

### 2. Constrained JSON for the tool protocol
**`dottxt-ai/outlines`** (16k, Apache-2.0) — or GBNF at the llama.cpp layer.
`agent_kernel/tool_protocol.py` parses "exactly one JSON object" out of free text and rejects the
rest. Bojo is 1.9B; parse failures are a model-capability tax. Constrain the sampler to the action
schema (`{"tool": ..., "args": ...}`) instead of hoping. Start with a GBNF grammar on the local
llama.cpp lane (no Python dependency), fall back to Outlines for the Ollama path.
**Why now:** direct reliability gain on every Tys step, no architecture change.

### 3. Structural code intelligence for the coding lane
**`ast-grep/ast-grep`** (16.4k, MIT) + **`tirth8205/code-review-graph`** (32.6k, MIT) + **`yamadashy/repomix`** (29k, MIT).
`agent_kernel/ast_edit.py` and `coding_tools.py` do Python-AST edits and grep; ast-grep adds
multi-language structural search/rewrite with a single binary. code-review-graph builds a persistent
local map of the repository (symbols, call edges, docs) exposed over MCP — the missing index behind
"which file owns this?". repomix packs a repository into a token-budgeted context file when a task
genuinely needs the whole tree.
**Why now:** fewer wrong-file edits and less context waste in every coding task.

### 4. A standard tool surface (MCP)
**`modelcontextprotocol/python-sdk`** (24.8k, MIT).
Northstar's tools are bespoke Python callables. Expose a read-only subset (state, knowledge, jobs,
render manifests) as an MCP server, and consume MCP servers (git, filesystem, fetch) where they are
better tested than our wrappers. Keeps the kernel in charge: MCP is transport, not authority.
**Why now:** 4,600+ MCP servers in the scan are immediately reachable; the controller policy still
decides what may run.

### 5. Trace every agent step
**OpenTelemetry (Apache-2.0)** — with `langfuse/langfuse` (NOASSERTION, MIT core + EE) optional.
There is no trace of a Tys run today beyond JSONL journals. Emit one span per model call, tool call
and verification with a run id; the journal already has the ids. OTel is the safe substrate; a UI
can come later.

---

## Tier 1 — next 30 days (patterns and integrations)

### 6. Memory consolidation, not just storage
**`mem0ai/mem0`** (68.4k, Apache-2.0).
Northstar stores facts and supersedes them (`memory_bank.py`, `tys_ops/memory.py`). Mem0's pipeline
— extract candidate facts, dedupe, update/delete on conflict, scope by user/session — is the missing
half. Borrow the pipeline and schema; keep SQLite. Do not adopt the hosted service.

### 7. Graph retrieval for the knowledge plane
**`HKUDS/LightRAG`** (40.5k, MIT) and **`getzep/graphiti`** (32.5k, Apache-2.0); **`topoteretes/cognee`** (33.1k, Apache-2.0) and **`memvid/memvid`** (17.4k, Apache-2.0) are the lighter alternatives.
LightRAG runs a local graph over documents without a database server; Graphiti has the better
temporal edge model but wants Neo4j/FalkorDB (too much for 16 GB). Cognee is the closest full memory
platform; memvid stores memory as a single file. Start with LightRAG's entity/relation extraction
over `knowledge/`, store edges in SQLite; revisit the others only if the graph outgrows it.

### 8. Document ingestion that preserves structure
**`docling-project/docling`** (70.1k, MIT).
`knowledge/` is Markdown atoms; PDFs/DOCX/HTML lose their tables and headings today. Docling is the
best local converter with layout and table structure. Install size is the only question — check
against the 10 GB disk floor before adding it to the base image.

### 9. Evaluation that can fail a build
**`promptfoo/promptfoo`** (26.8k, MIT) + **`UKGovernmentBEIS/inspect_ai`** (3.2k, MIT).
`tools/tys_kernel_bench.py` measures the coding lane; there is no regression harness for Bojo's
answers, tool selection, or the master brain's retrieval. Promptfoo covers prompt/model assertions;
Inspect gives reproducible logs for agent transcripts. Wire both to the existing JSONL evidence.

### 10. A control plane for runs, spend and approvals
**`builderz-labs/mission-control`** (6.4k, MIT).
Tys has work orders, campaigns, journals and HITL records but no operator surface that shows them
together. Mission-control's shape — dispatch, review runs, spend, approvals — is the missing admin
view. Adopt the information architecture; the data already exists in `state/`.

### 11. Declarative policy for the two standing gates
**`cedar-policy/cedar`** (1.8k, Apache-2.0) or **`open-policy-agent/opa`** (12.4k, Apache-2.0);
**`trustgraph-ai/trustgraph`** (2.9k, Apache-2.0) is the reference for policy + provenance in one graph.
`_touches_owner_gate`, `lane_policy.py` and the Chrome Connect guardrails are Python conditionals.
A declarative rule set (spend, Amazon, credential entry, external state change) with a decision log
is auditable in a way code comments are not. Cedar is embeddable and small; OPA has the richer
tooling. Pick one, not both.

### 12. Schema-validated outputs with retry
**`567-labs/instructor`** (14.1k, MIT) / **`pydantic/pydantic-ai`** (21k, MIT).
Pydantic is already the contract language here. Instructor adds validation-error feedback and
bounded retries around structured outputs — useful for Bojo and for every JSON manifest. Adopt the
retry pattern; do not move the kernel onto an agent framework.

---

## Tier 2 — reference architecture, not dependencies

| Candidate | Why not now |
|---|---|
| `browser-use/browser-use` (120k, MIT), `browserbase/stagehand` (25.9k, MIT) | Chrome Connect is the controller by charter. Read their action space and DOM/vision fallback; do not replace the controller. |
| `OpenHands/OpenHands` (92.6k, MIT), `SWE-agent/SWE-agent` (20.7k, MIT) | Runtime/event-stream designs worth copying; the kernel already has the same shape. No wholesale adoption. |
| `agent-sandbox/agent-sandbox` (Apache-2.0), `abshkbh/arrakis` (AGPL-3.0) | Sandboxing is a real gap, but Windows + 16 GB makes containers a project. Arrakis is local-lane only (AGPL). |
| `temporalio/sdk-python` (MIT), `PrefectHQ/prefect` (Apache-2.0) | The continuous loop already checkpoints and resumes. Add idempotency keys and an outbox before adding a workflow server. |
| `qdrant/qdrant` (35.4k, Apache-2.0), `chroma-core/chroma` | Overkill: `sqlite-vec` is already in the stack and the corpus is small. |
| `langfuse/langfuse`, `Arize-ai/phoenix`, `BerriAI/litellm` | Licence is "Other" (EE folders / custom). Fine to evaluate, not to bake in without a licence read. |
| `paperclipai/paperclip` (111k, MIT) | Star curve is implausible for its age; verify before trusting the signal. |

---

## Explicit rejects

* **`daytonaio/daytona`** — no licence in the repository metadata; cannot be adopted.
* **AGPL/SSPL network-copyleft** in the cloud lane — local-lane only, and only with the review.
* **Hosted/paid APIs** (any candidate whose value depends on a cloud key) — the two standing gates
  and the local-first rule make them out of scope for this pass.

---

## What "better" should be measured by

1. Bojo: tool-call parse failure rate (before/after constrained decoding), retrieval recall@5 on a
   20-question set drawn from `knowledge/`, and median answer latency.
2. Tys: first-pass acceptance on the 20-brief kernel benchmark, wrong-file edit rate, and mean
   steps to green.
3. Master brain: retrieval precision on a fixed question set, memory conflict resolution count, and
   the number of policy decisions with an auditable rule id.

No candidate above is a quality claim until one of those numbers moves.
