# Chrome Connect Model Benchmark Report

Date: 2026-10-26T20:27:29.661616
Tasks: 3
Models tested: 1

## Summary

| Model | Pass Rate | Avg Steps | Avg Tokens | Avg Time (s) | Total Time (s) |
|-------|-----------|-----------|------------|--------------|----------------|
| northstaros-qwen3.8:27b | 0.0 | 1.67 | 0.0 | 28.006 | 84.017 |

## northstaros-qwen3.8:27b

| Task | Fixture | Success | Steps | Tokens | Time (s) | Gave Up Reason |
|------|---------|---------|-------|--------|----------|----------------|
| extract title and price from this page | costco_product_page | False | 2 | 0 | 19.695 | post-condition failed for extract: no page loaded |
| extract product names and prices from se | costco_search_results | False | 1 | 0 | 24.216 | decision function returned no action |
| extract ASIN, title, price, and BSR from | sellersprite_dashboard | False | 2 | 0 | 40.106 | post-condition failed for extract: no page loaded |

## Recommendation

**Best model:** northstaros-qwen3.8:27b (pass_rate=0.0, avg_time=28.006s)

Note: Only 27B models are available on this machine. 9B and 12B candidates from the plan are not installed.