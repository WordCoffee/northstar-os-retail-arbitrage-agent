# Golden Goose Finder — 50 Proactive Fixes & Improvements

## Reliability & Robustness (1-10)

1. **Retry with exponential backoff for all external APIs** — Chocodata 502s, Bright Data timeouts, network flakes
2. **Circuit breaker pattern** — Stop calling failing providers after N consecutive failures; auto-recover after cooldown
3. **Idempotency keys for all live calls** — Prevent duplicate charges on retries; deduplicate in ledger
4. **Dead letter queue for failed enrichments** — Capture ASINs that failed seller enrichment; retry next scan
5. **Health check endpoint per provider** — `/api/golden-goose/health/providers` returns live status, latency, error rates
6. **Graceful degradation** — If seller enrichment fails entirely, still return opportunities with `seller_identity: UNKNOWN` tier
7. **Scan timeout budget** — Hard limit (e.g., 5 min); return partial results with `scan_complete: false` flag
8. **Costco catalog staleness alert** — Flag if last successful catalog refresh > 7 days
9. **Provider quota exhaustion detection** — Pre-check ledger before scan; warn if < 20% credits remain
10. **Atomic report writes** — Write to temp file + atomic rename; never partial JSON on disk

## Data Quality & Accuracy (11-20)

11. **Seller verification timestamp persistence** — Ensure `seller_verified_at` survives match→economics→scored→JSON serialization
12. **ASIN validation** — Reject mock-pattern ASINs (`^B0[a-f0-9]{8}$`) before sending to Bright Data/Chocodata
13. **Price sanity checks** — Flag if Amazon price < Costco unit_cogs * 0.5 or > unit_cogs * 50
14. **Pack count cross-validation** — Verify `amazon_match.implied_count <= wholesale_pack_count` before accepting match
15. **Brand normalization** — Fuzzy match wholesale brand to Amazon brand (handle "Nutramax" vs "Nutramax Laboratories")
16. **Duplicate ASIN deduplication** — Same ASIN matched to multiple Costco products → keep highest margin
17. **BSR freshness check** — Reject Chocodata results with BSR > 1M (likely stale/phantom listings)
18. **Review count plausibility** — Flag if reviews > 100K but BSR > 100K (inconsistent signals)
19. **Weight/size validation** — Reject items > 5 lbs or > 18x14x8 in (FBA oversize thresholds)
20. **ROI floor enforcement at match stage** — Drop matches where `unit_cogs * (1 + roi_floor/100) > amazon_price` early

## Error Handling & Observability (21-30)

21. **Structured error codes** — Every failure: `PROVIDER_ERROR|AUTH|RATE_LIMIT|PARSE|VALIDATION|TIMEOUT`
22. **Per-ASIN audit trail** — Log every API call per ASIN: provider, latency, status, credits, error
23. **Scan manifest** — `scan_manifest.json` per run: inputs, provider versions, env flags, git SHA
24. **Metrics emission** — Push scan duration, opp count, tier distribution, credit spend to local metrics file
25. **Alert on tier regression** — If HIGH count drops > 50% vs last scan, notify operator
26. **Provider latency percentiles** — Track p50/p95/p99 per provider; auto-deprioritize slow providers <!-- DUPLICATE #26 (see second 26 below) — flag only, renumber in a future pass -->
26. **Error budget tracking** — Monthly error budget per provider; pause if exceeded <!-- DUPLICATE #26 — this file numbers two entries as #26 (latency percentiles above + error budget here); subsequent items 27-50 continue from this second #26. Renumbering deferred to a future doc pass; do not renumber in Phase A. -->
27. **Structured logging** — JSON logs with `scan_id`, `asin`, `provider`, `stage` for correlation
28. **Debug mode flag** — `GOLDEN_GOOSE_DEBUG=1` dumps raw HTML, API responses to `data/debug/`
29. **Replay capability** — Save raw provider responses; `python -m replay_scan --from-file X` for debugging

## Performance & Cost Control (30-40)

30. **Parallel seller enrichment** — Enrich top 10 matches concurrently (asyncio.gather with semaphore)
31. **Batch Chocodata queries** — Combine similar product queries; deduplicate before API call
32. **Smart provider routing** — Route high-value ASINs (high margin) to best provider; low-value to cheapest
33. **Credit-aware scan planning** — Estimate credits needed; skip low-ROI products if budget tight
34. **Cache Chocodata search results** — 1-hour TTL for identical queries across products
35. **Lazy seller enrichment** — Only enrich seller data for opportunities passing economics filter
36. **Compress debug artifacts** — Gzip raw HTML/JSON in `data/debug/`; auto-purge > 7 days
37. **Streaming report generation** — Write opportunities incrementally; don't hold full list in memory
38. **Async Costco catalog fetch** — Fire all category queries in parallel; don't sequential
39. **Provider cost tracking per scan** — Report: "Scan used 234 credits ($0.00); Bright Data 180, Chocodata 54"
40. **Free tier quota projection** — Project remaining scans this month based on current spend rate

## User Experience & Workflow (41-50)

41. **Interactive scan CLI** — `--interactive` pauses after each phase: "Continue to matching? [Y/n]"
42. **Scan diff report** — Compare latest scan to previous: new opps, dropped opps, tier changes
43. **Export to Scout format** — One-click CSV for Scout panel with all required columns
44. **Config profiles** — `profiles/aggressive.yaml`, `profiles/conservative.yaml` for different risk appetites
45. **Schedule manager** — `golden-goose schedule --cron "0 6 * * *"` for automated daily scans
46. **Webhook on HIGH tier** — POST to configured URL when new HIGH tier opportunity found
47. **Opportunity annotations** — Operator can tag opps: `golden-goose tag B00W8BUKV8 --note "verified 9/17"`
48. **Rollback scan** — `golden-goose rollback --to-scan goose_scan_20260915` to revert report state
49. **Dry-run mode** — `--dry-run` shows estimated credits, time, opp count without API calls
50. **Documentation auto-gen** — `golden-goose docs` generates current API schema, provider matrix, CLI help

---

## Priority Implementation Order

### Phase 1: Critical Reliability (Week 1)
1. Seller verification timestamp persistence (fix #11)
2. ASIN validation / mock filtering (fix #12)
3. Structured error codes (fix #21)
4. Atomic report writes (fix #10)
5. Scan timeout budget (fix #7)

### Phase 2: Data Quality (Week 2)
6. Price sanity checks (fix #13)
7. Pack count cross-validation (fix #14)
8. Brand normalization (fix #15)
9. Duplicate ASIN deduplication (fix #16)
10. ROI floor at match stage (fix #20)

### Phase 3: Observability (Week 3)
11. Per-ASIN audit trail (fix #22)
12. Scan manifest (fix #23)
13. Metrics emission (fix #24)
14. Provider latency tracking (fix #26)
15. Debug mode + replay (fix #28-29)

### Phase 4: Performance (Week 4)
16. Parallel seller enrichment (fix #30)
17. Credit-aware planning (fix #33)
18. Lazy seller enrichment (fix #35)
19. Async Costco fetch (fix #38)
20. Free tier projection (fix #40)

### Phase 5: UX (Ongoing)
21. Scan diff report (fix #42)
22. Config profiles (fix #44)
23. Dry-run mode (fix #49)
24. Docs auto-gen (fix #50)

---

## Quick Wins to Implement Now

Let me start with the top 5 critical fixes: