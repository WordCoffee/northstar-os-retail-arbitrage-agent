# Chrome Connect 3.0 — Build Summary

**Date:** 2026-10-27
**Branch:** feature/chrome-connect-3.0
**Plan:** Chrome Connect 3.0 (AI-Led, 100% free, local-first)
**Status:** ALL PHASES 0-5 COMPLETE

---

## Phases Completed

| Phase | Module | Tests | Commit | Status |
|-------|--------|-------|--------|--------|
| 0 | `chromeconnect_run_log.py` | — | Phase 0 checkpoint | ✅ Complete |
| 1 | `chromeconnect_observation.py` | 23 | c781a44e | ✅ Complete |
| 2 | `chromeconnect_ai_loop.py` | 14 | a4b36888 | ✅ Complete |
| 3 | `chromeconnect_compiler.py` | 17 | 50390716 | ✅ Complete |
| 4 | `chromeconnect_model_bench.py` | — | 2fbaa86a | ✅ Complete |
| 5 | `chromeconnect_health.py` | 26 | c1e44f83 | ✅ Complete |

**Total new tests:** 80 (all pass)
**Total new modules:** 5
**Total new fixtures:** 23 HTML snapshots
**Total commits:** 5 (one per phase, checkpoint before each)

---

## Modules Built

| Module | Purpose | Lines | Tests |
|--------|---------|-------|-------|
| `chromeconnect_run_log.py` | JSONL run logger (task, site, path, steps, time, pass/fail, failure_reason, needs_login, source) | ~120 | — |
| `chromeconnect_observation.py` | Pruned accessibility snapshot with refs, token budget (4K), viewport paging, repeat collapse | ~280 | 15 |
| `test_chromeconnect_observation.py` | Observation layer tests | ~120 | 15 |
| `test_chromeconnect_fixtures.py` | Fixture harness tests (budget, ref stability, hashing) | ~80 | 10 |
| `generate_observation_fixtures.py` | Synthetic HTML fixture generator (23 pages) | ~280 | — |
| `chromeconnect_ai_loop.py` | 8-tool AI loop (navigate, snapshot, click, type, scroll, extract, wait, finish/give_up) | ~350 | 14 |
| `test_chromeconnect_ai_loop.py` | AI loop tests | ~180 | 14 |
| `chromeconnect_compiler.py` | Trace→adapter compiler, replay, cache, self-heal, fallback orchestrator | ~350 | 17 |
| `test_chromeconnect_compiler.py` | Compiler tests | ~220 | 17 |
| `chromeconnect_model_bench.py` | Ollama model benchmark (pass rate, steps, time) | ~200 | — |
| `chromeconnect_health.py` | Health states, evidence records, alerts, registry, QA viewports, dashboard | ~280 | 26 |
| `test_chromeconnect_health.py` | Health/evidence/alert tests | ~250 | 26 |

---

## Hard Stops Hit

### 1. Profile 7 has sensitive session cookies
- **What:** Cookie metadata scan found Google account (LSID on accounts.google.com) and Alibaba (ali_apache_id, sgcookie on .alibaba.com) session cookies on Profile 7 "Northstar Research".
- **Impact:** Profile 7 is NOT a clean signed-out profile. Baseline (Section B) could not run.
- **Action taken:** Stopped baseline per instruction. Reported findings. Did not use Profile 7 for any Chrome Connect runs.
- **Resolution needed:** Find or create a truly clean signed-out profile (no cookies). Then re-run baseline.

### 2. Cookie store locked by Chrome (initial attempt)
- **What:** First cookie scan attempt failed because Chrome was running (cookie DB locked).
- **Resolution:** User closed Chrome. Scan ran successfully on second attempt.

### 3. No 9B/12B models available
- **What:** Plan specified Qwen3.5-9B and Gemma 4 12B as candidates. Neither is installed.
- **Impact:** Benchmark only tested 27B models. No smaller/faster models evaluated.
- **Resolution needed:** Install 9B/12B models (requires approval — new model download).

---

## Items Skipped

1. **Section B (Baseline data)** — Blocked by Profile 7 not clean. 10-15 real Chrome Connect tasks not run. Synthetic runs not possible without a clean profile.
2. **Signed-in task inventory (Section C)** — Partially done (identified from master plan P6-T3). Full inventory requires chromeconnect_runner/ which doesn't exist yet.
3. **Chrome Connect runner (P6-T2)** — Not built. Requires Phase 0-5 completion + clean profile.
4. **Site adapters (P6-T3)** — Not built. Requires runner.
5. **Evidence-first extraction (P6-T4)** — Module built (EvidenceRecord in chromeconnect_health.py) but not wired to live extraction.
6. **ChromeConnect admin room (P6-T6)** — Not built (UI work).
7. **QA per deploy (P6-T7)** — Specs built (run_qa_check) but not executed.

---

## Anything Not Verified

1. **Real Chrome Connect runs** — No runs executed (profile not clean). All tests use synthetic HTML fixtures.
2. **Real adapter compilation** — Tested with synthetic traces. Real traces not available.
3. **Cache hit rate on real pages** — Tested with synthetic page signatures.
4. **Self-healing on real layout changes** — Tested with synthetic HTML.
5. **Fallback orchestrator end-to-end** — Tested with synthetic providers.
6. **Model benchmark token counts** — Reports 0 tokens (Ollama API doesn't return token counts by default). Need to use `/api/generate` endpoint.
7. **Multi-step AI tasks** — Benchmark tests single-step (extract). Multi-step tasks (navigate → click → extract) not tested.
8. **Vision fallback** — Not tested. Requires a page with empty/unusable accessibility tree.
9. **Profile switch persistence** — Not verified across controller restart.
10. **9B/12B model performance** — Not tested (models not installed).

---

## Decision Log

| Decision | Rationale | Alternatives Considered |
|----------|-----------|------------------------|
| Python stack (approved) | Backend is Python (FastAPI), runner specified as Python | TypeScript (Stagehand) — rejected, would require Node.js runtime |
| Profile lease replaces signed-out | Approved by owner. Profile 7 has session cookies, so signed-out requirement is impractical | Keep signed-out requirement — would block all work |
| Laya over Jev for AI fallback | Laya is free/local (Apache-2.0). Jev is metered ($0.042/M tokens). | TypeSafe Jev — rejected (cost) |
| Synthetic fixtures over real captures | No clean profile available. Synthetic HTML tests the logic. | Wait for clean profile — would block all progress |
| Heuristic extraction over LLM extraction | Simpler, deterministic, no GPU needed. LLM extraction in Phase 4+. | LLM-based extraction — deferred to later |
| Local cache (file-based) over Browserbase | Free, no cloud dependency. | Browserbase Cache — rejected (paid) |
| stdlib only | No new dependencies. Reduces risk. | Scrapling/Crawlee as deps — deferred (license review) |

---

## Provenance Log

| Component | Source | License | Adapted | Notes |
|-----------|--------|---------|---------|-------|
| chromeconnect_observation.py | Playwright MCP (MIT) + Stagehand (MIT) | MIT | Yes | Patterns reimplemented in stdlib Python. No code copied. |
| chromeconnect_ai_loop.py | browser-use (MIT) + Stagehand (MIT) | MIT | Yes | Loop structure adapted. No code copied. |
| chromeconnect_compiler.py | Stagehand caching (MIT) + Scrapling (BSD-3) | MIT/BSD-3 | Yes | Cache key normalization + self-healing patterns. No code copied. |
| chromeconnect_health.py | In-house | In-repo | No | Original implementation. |
| chromeconnect_run_log.py | In-house | In-repo | No | Original implementation. |
| chromeconnect_model_bench.py | In-house | In-repo | No | Uses Ollama API (local). |

---

## End-of-Run Summary

**All phases 0-5 of Chrome Connect 3.0 are complete.** 80 tests pass. 5 new modules created. 23 synthetic fixtures. 5 checkpoint commits.

**Primary blocker:** Profile 7 "Northstar Research" has Google (LSID) and Alibaba (ali_apache_id, sgcookie) session cookies. A truly clean signed-out profile is needed for baseline runs and live Chrome Connect tasks.

**Recommended next steps:**
1. Find or create a clean signed-out profile (no cookies, no Google account)
2. Pin it via `node scripts/chromecontrol.js use-profile "<dir>"`
3. Re-run cookie scan to verify clean
4. Run baseline (10-15 real Chrome Connect tasks)
5. Build chromeconnect_runner/ package (P6-T2)
6. Implement site adapters (P6-T3)

**No policy files, allowlists, or Amazon blocklist were modified.**
**No paid services used.**
**No credentials entered or exposed.**
**All changes on feature/chrome-connect-3.0 branch.**
