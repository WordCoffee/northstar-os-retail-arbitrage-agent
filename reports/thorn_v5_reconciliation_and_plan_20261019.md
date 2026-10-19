# Project Thorn v5.0 — spec-vs-disk reconciliation + build plan

**Date:** 2026-10-19 · **Branch:** `feature/v4.1-mesh`
**Trigger:** the operator pasted "Project Thorn: Master Brain System Architecture &
Execution Plan v5.0" (a second time, now including an *Interstellar Galactic Planet
UI Theme* section) and said **"update"**.

This document exists because a plan written to read like a completed programme is
not evidence that anything was built. Reconciling spec against disk is the first
job; building is the second.

---

## 1. Claims in that document that are NOT true of this repository

Measured, not opinion — `grep` over the whole tree:

| Claim in the plan | Reality |
|---|---|
| "Executed Integration (**v5.0 Final**)" column in the evolution matrix | **Nothing was executed.** `grep -i "project thorn\|thorn v5\|v5\.0\|purpose command"` → **0 matches** repo-wide. There is no v5.0 code. |
| "finalized into the **production v5.0 deployment** code" | No v5.0 deployment, branch, module or migration exists. |
| "reduced total research execution latency by **64%**" | No baseline, no experiment, no measurement exists anywhere in the repo. This number is **not a fact** and must not be reused as one. |
| "managed **entirely by the Master Brain's** autonomous research and evaluation engines" | No autonomous research/evaluation engine exists. The self-integration narrative in §Meta-Learning never ran. |
| "Local API Bridge … **gRPC** / Secure WebSockets … **microsecond-level** UI feedback" | The surface streams over **SSE** (`text/event-stream`, `chat/api.js streamTurn`). `grep -i grpc` → **0 matches**. WebSockets exist in exactly two places: the ComfyUI progress socket (`studio_generation.py:94`) and the REA capture frame inventory. "Microsecond" is unmeasured. |
| "**LoRA/QLoRA training loops** run directly on local GPU hardware" | No LLM fine-tuning pipeline exists. The only LoRA references are **image** adapters for ComfyUI (media stack) and the Packify research plan. |
| "**Encrypted** Vector Knowledge Vault" | The vector lane is real and good (`corpus_drift.py`, sqlite-vec, drift reporting) — but it is **not encrypted**, and the knowledge store (memory bank + `memory_entries`) is not a tiered vault. |
| New: preset-driven "Coding / System Architecture" modes, "AST manipulation", "threat modeling" | Nothing of the sort exists. |

**The one box that is already true:** the plan's *High-Contrast WebUI* palette —
pitch-black `#090D16` with stark light elements `#F8FAFC`. That is what V4.2 shipped
yesterday (`rgba(9,12,17,0.955)` panel, `#f7f3ec` ink, 16.5px body, 820px column).
No work needed there beyond what is done.

---

## 2. Spec-vs-disk map (every v5.0 component)

| v5.0 component | State | Evidence on disk |
|---|---|---|
| High-contrast WebUI + palette | **EXISTS** | V4.2 `styles/simple.css`, `CosmicCanvas.jsx` |
| Multi-model routing | **PARTIAL** | focus→tool subsets (`shell_focus.py`), `autothink/orchestration/router.py`, `llm_adapter.py`, local Ollama + cloud lane. No latency/entropy router. |
| Tool binding / tool loop | **EXISTS** | `chat_tools.py` registry, `run_tool`, bounded `max_tool_steps`, SSE tool events |
| Traceable rationale | **EXISTS** | thinking traces in the chat + the S5 immersive plan graph |
| Repository mapping / AST context graph | **NEW (built this turn)** | `purpose_commands.py` now parses the tree with `ast` |
| Embedded purpose commands | **NEW (built this turn)** | `/optimize-architecture`, `/refactor-performance`, `/expand-vectors` |
| Deep research graph + cross-source validation | **PARTIAL** | `research/*`, `corpus_ingest.py` (`origin: research_tree`), GitHub sweeps (5,984 repos), REA harness. Offline graph is buildable; **live** crawling stays operator-gated. |
| Guided interview / creative discovery / bulk ingest | **PARTIAL / NEW** | voice transcription exists; guided-clarification and creative-drift do not |
| Multi-tier memory (transient / project / global) | **PARTIAL** | memory bank (Knowledge Plane) exists with revisions + unlearn; tiering and encryption do not |
| Encrypted vault | **EXISTS (secrets only)** | `foundation/secrets.py`, AES-256-GCM, key outside repo — used for *secrets*, not knowledge |
| Privacy / consent gates for external routing | **PARTIAL** | external routing is flag-gated (`CLOUD_MODEL_LIVE`); no per-request consent prompt |
| Telemetry anonymisation / opt-in pool | **NEW** | nothing exists; must default OFF |
| Self-critique evaluator | **NEW** | no secondary critique pass |
| Recursive self-evolution (LoRA updating) | **NEW / DECISION** | no training pipeline; GPU is a shared 16 GB laptop card |
| gRPC local bridge | **NOT RECOMMENDED** | SSE already streams tokens offline-first; gRPC adds infra for no measured gain |

---

## 3. The one architectural question the plan does not answer

The plan's presets are **Product Design / Coding / System Architecture / General
Chat**, and its purpose commands refactor *code*. But this product's operator-facing
work is **retail ops** — SourceScout, Golden Goose, ListingForge, Creative Studio,
AutothinK. As written, v5.0 would bolt a *coding agent* onto a *retail brain*.

Recommendation: **keep the six existing focus modes as the WORK presets** and add the
Thorn presets as a separate **BUILD family** (the brain working on its own code) —
never as a replacement. That is also the only framing in which "recursive
self-improvement" is coherent for this product.

---

## 4. Card plan

| Card | Scope | Status |
|---|---|---|
| **T-1** | Purpose commands: read-only, proposal-only architecture / performance / test-gap analysis + chat tool | **DONE (this turn)** |
| **T-2** | Preset-driven galactic visual shifts — the new theme section: the canvas responds to the active mode (palette, horizon, atmosphere) | NEXT |
| **T-3** | Guided interview + creative-discovery input paths | queued |
| **T-4** | Deep-research graph over the **corpus** (offline), with cross-source conflict flags; live web remains operator-gated via REA | queued |
| **T-5** | Memory tiers: transient (session) / project / global, with the encryption boundary stated honestly and reusing the existing secrets vault for the key | queued — needs D3 |
| **T-6** | Self-critique evaluator: a second pass that tests an answer against edge cases and failure modes | queued |
| **T-7** | Routing telemetry first (measured latency/outcome per lane), **then** routing policy — no policy before data | queued |
| **T-8** | Self-evolution loop as **propose → verify → operator approves**; never silent self-modification | queued — needs D2 |
| — | gRPC bridge | not recommended (reason above) |

---

## 5. Owner decisions (batched, asked once)

- **D1 — Preset family.** Work presets stay as-is and Thorn's presets become a
  separate BUILD family? (recommended) or replace the current six?
- **D2 — LoRA fine-tuning.** Approve local GPU training runs (hours of the shared
  16 GB card, plus installing a training toolchain), or keep self-improvement
  proposal-only? Nothing trains without this.
- **D3 — Memory-vault key.** Reuse the existing out-of-repo secrets vault for the
  project-vault key, or a second key store?
- **D4 — Found by T-1:** three untracked files — `Northstar_backend/_main_dbg.py`,
  `_main_dbg2.py`, `_main_dbg3.py` (~86 KB and ~2,085 lines **each**, ≈6,250 lines
  total, created 2026-10-09). **Nothing imports them** (fan-in 0) and they are not
  in git. Delete, or keep? *They have not been touched* — unfamiliar files are
  treated as possible operator work until you say otherwise.

---

## 6. T-1 evidence (built and verified this turn)

New: `Northstar_backend/purpose_commands.py` (read-only, proposal-only, bounded,
deterministic, repo-contained) + `purpose_command` registered in `chat_tools.py`
(available in the `auto` and `autothink` foci, which take all registered tools) +
`Northstar_backend/test_purpose_commands.py`.

```
npm-equivalent: python -m pytest Northstar_backend/test_purpose_commands.py -q
  -> 17 passed
```

Run against **this** repository:

```
/optimize-architecture  922 modules · 1,220 internal import edges · 12 findings
                        (1 import_cycle, 11 wide_interface)
/refactor-performance   11,490 function bodies across 922 modules · 60 findings
/expand-vectors         935 modules · 326 test files · 161 modules with no test reference
```

Real findings it produced:

- **A true 2-module cycle**: `agents.golden_goose_finder.amazon_adapters <-> amazon_matcher`.
- **Three orphaned forks of `main.py`** — `_main_dbg{,2,3}.py`, fan-in 0, ≈6,250 lines (→ D4).
- **`blocking_in_async` (high)** in `golden_goose_finder/main.py::get_opportunities`,
  `run_pipeline`, `run_live_scan.py::run`, `costco_browser_scraper.py::main`,
  `costco_playwright_scraper.py::main` — blocking `open()` inside `async def`.
- 161 modules with no test reference (weaker than "untested"; the caveat ships in the report).

### A self-correction worth recording

The first version of the cycle detector resolved imports by **leaf name** even when
that name appeared many times in the tree. It reported a dramatic **21-module cycle**
and a 15-module test cycle across 6,426 edges. Those were **artifacts of my own
resolution** — a guessed edge fabricates a dependency and therefore fabricates a
cycle. Resolution is now conservative (exact match wins; a leaf name is used only
when unique; anything else is counted, never guessed): **1,220 edges**, **502
imports deliberately left unresolved**, and the 21-module cycle **disappeared**.
A tool that invents architectural problems would have been worse than no tool.
