# Live NS-PROJ-20 runs

**Label:** live lane baseline — the local 27B wrote each node's text and the
harness persisted it. **Not a quality claim.**

| Folder | What it is |
|---|---|
| `20261029T000152Z` | pilot, 1 brief (p01) |
| `20261029T000208Z` | aborted at 46 calls (8K + MTP); 6/20 |
| `20261029T000510Z` | aborted at 49 calls (8K + MTP); 8/20 |
| `20261029T000806Z` | stable pilot, 5 briefs (8K, no MTP) |
| `20261029T000941Z` | **final baseline**, 20/20, 60 calls, 8K, no MTP |

The aborted folders are kept as evidence of the server instability, not as
results. The final result is in `20261029T000941Z/summary.json`; the human report
is `reports/ns_proj_20_live_baseline_20261029.md`.

Thresholds set from the final run: completion 1.00, evidence 1.00, p50 ≤ 8 s,
p95 ≤ 15 s, format validity ≥ 0.90. Quality thresholds are **not set**; machine
content validators do not exist yet.
