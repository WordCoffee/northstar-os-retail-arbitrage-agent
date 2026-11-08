> **SUPERSEDED (2026-11-07).** These numbers were measured while Ollama was pinned to the CPU (`OLLAMA_LLM_LIBRARY=cpu`, `OLLAMA_NUM_GPU=0`). The GPU baseline is `reports/ty/local_bench_gpu_20261107.md`. The 27B now runs on `llama-server` at `-ngl 99` and its browser-task re-run belongs to D8. The numbers below are kept as the CPU-era record, not as current performance.

# Chrome Connect Model Benchmark Report

Date: 2026-10-26T20:43:12.555462
Tasks: 3
Models tested: 1

## Summary

| Model | Pass Rate | Avg Steps | Avg Tokens | Avg Time (s) | Total Time (s) |
|-------|-----------|-----------|------------|--------------|----------------|
| northstaros-qwen3.8:27b-ctx64k-orig | 0.6667 | 1.33 | 0.0 | 15.803 | 47.408 |

## northstaros-qwen3.8:27b-ctx64k-orig

| Task | Fixture | Success | Steps | Tokens | Time (s) | Gave Up Reason |
|------|---------|---------|-------|--------|----------|----------------|
| extract title and price from this page | costco_product_page | True | 2 | 0 | 21.933 | None |
| extract product names and prices from se | costco_search_results | False | 0 | 0 | 7.18 | decision function returned no action |
| extract ASIN, title, price, and BSR from | sellersprite_dashboard | True | 2 | 0 | 18.296 | None |

## Recommendation

**Best model:** northstaros-qwen3.8:27b-ctx64k-orig (pass_rate=0.6667, avg_time=15.803s)

Note: Only 27B models are available on this machine. 9B and 12B candidates from the plan are not installed.
