# Live text-lane baseline runs

**Label:** **live text-lane baseline** — the local 27B wrote each node's text and
the harness persisted it. **Not a quality claim.**

| Folder | What it is |
|---|---|
| `20261029T000152Z` | pilot, 1 brief (p01) |
| `20261029T000208Z` | aborted at 46 calls (8K + MTP); 6/20 |
| `20261029T000510Z` | aborted at 49 calls (8K + MTP); 8/20 |
| `20261029T000806Z` | stable pilot, 5 briefs (8K, no MTP) |
| `20261029T000941Z` | baseline run 1; fenced nodes rerun; tool lane |
| `20261029T012552Z` | baseline run 2 |
| `20261029T013245Z` | baseline run 3 |
| `20261029T051911Z` | aborted enforced attempt (server exit at 51 calls) |
| `20261029T052440Z` | **enforced-validator run** (5 restarts, 17/20 text lane) |
| `spread.json` | 3-run spread and latency thresholds |

**Pinned settings:** 8K context, q8_0 KV, **MTP off**. MTP aborted at 46 and 49
calls; no-MTP completed all 60.

**Fence policy:** Markdown fences are **stripped at persistence** and recorded in
the node's model call. The 13 fenced artifacts in run 1 were rerun; none remain.

**Run-to-run spread (3 runs, file existence):** completion 20/20 each; p50 6.27,
4.82, 6.11 s; p95 11.17, 14.08, 11.97 s; format 0.90; content 0.85.

**Enforced validators (run `052440Z`):** completion **17/20**, evidence **0.95**,
p50 5.08 s, p95 12.90 s. Failures: p11, p13, p14 — structural text-lane limits.

**Tool lane:** p11 (real PNG; OCR + prepress), p13 (`presets.js` canvases) and p14
(12 s 1080×1920 MP4 with audio) all valid. Tool-lane content **20/20 (1.00)**.

**Ty-as-is:** `reports/rea_probe/proj_bench_tys/20261029T053555Z` — Ty's
orchestrator + coding lane is **0/20 content-valid** because the lane has no tools
and no context; see `reports/tys_as_is_baseline_20261029.md`.

The human report is `reports/ns_proj_20_live_baseline_20261029.md`.
