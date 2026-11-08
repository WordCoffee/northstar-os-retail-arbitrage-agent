> **SUPERSEDED (2026-11-07).** These numbers were measured while Ollama was pinned to the CPU (`OLLAMA_LLM_LIBRARY=cpu`, `OLLAMA_NUM_GPU=0`). The GPU baseline is `reports/ty/local_bench_gpu_20261107.md`. The 27B now runs on `llama-server` at `-ngl 99` and its browser-task re-run belongs to D8. The numbers below are kept as the CPU-era record, not as current performance.

# Chrome Connect Model Benchmark Report

Date: 2026-10-26T20:38:49.866494
Tasks: 5
Models tested: 1

## Summary

| Model | Pass Rate | Avg Steps | Avg Tokens | Avg Time (s) | Total Time (s) |
|-------|-----------|-----------|------------|--------------|----------------|
| northstaros-qwen3.8:27b | 0.6 | 1.8 | 0.0 | 19.28 | 96.402 |

## northstaros-qwen3.8:27b

| Task | Fixture | Success | Steps | Tokens | Time (s) | Gave Up Reason |
|------|---------|---------|-------|--------|----------|----------------|
| extract title and price from this page | costco_product_page | True | 2 | 0 | 9.784 | None |
| extract product names and prices from se | costco_search_results | True | 2 | 0 | 19.97 | None |
| extract ASIN, title, price, and BSR from | sellersprite_dashboard | True | 2 | 0 | 17.071 | None |
| extract buy box price, fees, net profit, | selleramp_analysis | False | 2 | 0 | 41.404 | Missing required ASIN in goal to enter into the analysis form |
| find and click the search button | sellersprite_dashboard | False | 1 | 0 | 8.172 | repeat loop detected, replan exhausted |

## Recommendation

**Best model:** northstaros-qwen3.8:27b (pass_rate=0.6, avg_time=19.28s)

Note: Only 27B models are available on this machine. 9B and 12B candidates from the plan are not installed.
