# Live text-lane baseline runs

**Label:** **live text-lane baseline** — the local 27B wrote each node's text and
the harness persisted it. **Not a quality claim.**

| Folder | What it is |
|---|---|
| `20261029T000152Z` | pilot, 1 brief (p01) |
| `20261029T000208Z` | aborted at 46 calls (8K + MTP); 6/20 |
| `20261029T000510Z` | aborted at 49 calls (8K + MTP); 8/20 |
| `20261029T000806Z` | stable pilot, 5 briefs (8K, no MTP) |
| `20261029T000941Z` | baseline run 1; fenced nodes rerun; tool lane rerun |
| `20261029T012552Z` | baseline run 2 |
| `20261029T013245Z` | baseline run 3 |
| `spread.json` | run-to-run spread and thresholds |

**Pinned settings:** 8K context, q8_0 KV, **MTP off**. The 64K + MTP launcher
aborted twice at 46 and 49 calls; the no-MTP configuration completed every run.

**Fence policy:** Markdown fences are **stripped at persistence** and the event is
recorded in the node's model call. The 13 fenced artifacts in run 1 were rerun;
none are fenced now.

**Run-to-run spread (3 runs):**

| Metric | Values | Threshold |
|---|---|---|
| Completion | 20, 20, 20 | ≥ 1.00 |
| p50 | 6.27, 4.82, 6.11 s | ≤ 7.5 s |
| p95 | 11.17, 14.08, 11.97 s | ≤ 16.9 s |
| Format valid | 0.90, 0.90, 0.90 | ≥ 0.90 |
| Content valid (text lane) | 0.85, 0.85, 0.85 | ≥ 0.85 |

**Tool lane (run 1):** p11 now valid (real PNG; OCR + prepress), p14 now valid
(12 s 1080×1920 MP4 with audio), p13 still invalid. Tool-lane content: **19/20
(0.95)**; text-lane content remains **17/20 (0.85)**.

The human report is `reports/ns_proj_20_live_baseline_20261029.md`.
