# Chrome Connect Model Benchmark Report

Date: 2026-10-26T20:23:15.957291
Tasks: 3
Models tested: 1

## Summary

| Model | Pass Rate | Avg Steps | Avg Tokens | Avg Time (s) | Total Time (s) |
|-------|-----------|-----------|------------|--------------|----------------|
| northstaros-qwen3.8:27b | 0.0 | 1.33 | 0.0 | 24.358 | 73.073 |

## northstaros-qwen3.8:27b

| Task | Fixture | Success | Steps | Tokens | Time (s) | Gave Up Reason |
|------|---------|---------|-------|--------|----------|----------------|
| extract title and price from this page | costco_product_page | False | 1 | 0 | 33.913 | repeat loop detected, replan exhausted |
| extract product names and prices from se | costco_search_results | False | 1 | 0 | 13.798 | repeat loop detected, replan exhausted |
| extract ASIN, title, price, and BSR from | sellersprite_dashboard | False | 2 | 0 | 25.363 | post-condition failed for extract: no page loaded |

## Recommendation

**Best model:** northstaros-qwen3.8:27b (pass_rate=0.0, avg_time=24.358s)

Note: Only 27B models are available on this machine. 9B and 12B candidates from the plan are not installed.