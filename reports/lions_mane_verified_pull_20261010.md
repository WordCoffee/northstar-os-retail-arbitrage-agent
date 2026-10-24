# Verified Lion's Mane Powder Pull — final report (2026-10-10)

Task: verified Top-N pull of ORGANIC LION'S MANE MUSHROOM POWDER, 4-32 oz, Amazon US,
applying every stated filter strictly, with a visual gate on the actual product images.

## Result

- **PASS: 13** (fully verified, every filter; list is complete, NOT padded)
- **REVIEW: 14** (specific doubts documented per row — see below)
- **REJECTED: 649** (stage + reason logged in `rejected.csv`)
- Target of 100 was NOT reachable under the stated filters because the largest exclusion
  bucket is "anything labeled 'extract'": most Amazon lion's mane "powder" listings are
  marketed as extracts (4:1, 8:1, 10:1, 20:1, dual/hot-water extracts), and the filters
  allow them only when the label clearly says "100% fruiting body powder".

## Files (all in `out_sb/`)

- `out_sb/pass.csv` — the verified list (rank, ASIN, title, brand, price, size_oz, $/oz,
  rating, reviews, bought-past-month, BSR, BSR-estimated monthly sales, URL, image,
  vision form / label weight / confidence / evidence)
- `out_sb/review.csv` — 14 rows with documented doubts
- `out_sb/rejected.csv` — 649 rows with stage + reasons
- `out_sb/summary.md` — counts, size-bucket table, demand signals, analysis, audit result
- `out_sb/audit_report.md`, `out_sb/audit_results.json` — independent audit
- `out_sb/vision_verdicts.json` — per-ASIN vision readings of the images
- `out_sb/credit_ledger.json` — every provider request + cost
- `out_sb/funnel.json` — discovered → title → text → visual → verdict counts

## Funnel

| stage | count |
|---|---|
| unique ASINs discovered (9 keywords × 6 result pages + probes) | 676 |
| survive title gate | 109 |
| product details fetched | 115 |
| survive strict text gate | 47 |
| survive vision + structured visual gate | 21 |
| PASS (after review-flag demotions) | 13 |

## Size buckets (PASS rows only)

| size bucket (oz) | n | median price | median $/oz | median reviews | median recent-sales | median BSR-est. monthly sales |
|---|---|---|---|---|---|---|
| 4–8 | 3 | $19.97 | $3.77 | 208 | 250 | 142 |
| 8–12 | 3 | $22.95 | $2.61 | 345 | 50 | 131 |
| 12–16 | 1 | $32.26 | $2.51 | 145 | 50 | 84 |
| 16–24 | 5 | $38.90 | $2.43 | 50 | 100 | 109 |
| 24–32 | 1 | $33.99 | $1.06 | 50 | n/a | 109 |

## Audit (independent second pass)

- Every PASS row re-checked with fresh single-question prompts on its images
  (form / net weight / organic / lion's mane) using the local Qwen2.5-VL model.
- **Result: 13/13 verified.** 12 clean confirmations; 1 row (B0BWJW3SCZ, Food to Live 8 oz)
  had one image reading "16 OZ" from shared brand imagery while its primary label image and
  structured data both confirm "8 oz (227 g)" — resolved as correct for the 8 oz SKU.
- 10 random REJECTED rows re-checked: 5 reconfirmed by fresh text-gate run; 5 were rejected
  on visual evidence (extract label, label weight out of range, collagen/coffee blend) and
  remain correct. **No wrongly rejected rows found.** The audit also caught and fixed a
  negation-handling bug (row B0CTJ18VH2: "no mycelium" was misread as mycelium content).

## Why the PASS list is 13, not 50+

Strict application of the operator's own filters. The dominant exclusions among 676
discovered ASINs: capsules/tablets/liquids/gummies (≈240 title-level), multi-mushroom
blends (≈180 mentions across titles), non-organic (23 rejected in text gate), mycelium
products (37 across text+visual), extract-labeled products (34 across text+visual),
out-of-range sizes (105 title-level + 8 label-level). The REVIEW bucket contains the 14
closest calls — mostly products whose *bullets* use the word "extract" while their labels
show plain powder (NutraChamps, WELLNESS LABSRX, Naturejam, Herb To Body) and three
multi-packs whose per-unit size is confirmed but the unit is smaller than the listing
total (Terrasoul 2×5.5 oz / 4×5.5 oz, Eleven TLC 3/4-packs). Any of these can be promoted
by operator decision; they are not silently counted as PASS.

## Provider notes (cost + tooling)

- **Bright Data datasets API: dead in this environment** — `BRIGHTDATA_API_KEY` returns
  401 "Invalid credentials"; `BD_DATASET_SEARCH` / `BD_DATASET_PRODUCT` were never set.
- **Chocodata: 402 out of credits.** Rainforest: usable but only ~38 credits remained;
  not used for this final pull (kept in reserve).
- **ScrapingBee (used): 820 / 985 credits** (5 credits per search/product request,
  170 requests; full log in `credit_ledger.json`).
- **Vision gate:** no `VISION_*` endpoint configured; local Ollama used instead.
  Pulled `moondream`, `qwen2.5vl:3b`, `minicpm-v` into the WSL Ollama store and ran the
  Windows-store `qwen2.5vl:7b` on port 11435 for the main pass (it is the most accurate of
  the available models; qwen2.5vl:3b is unreliable — emits "?" on some images).
- BSR-based monthly sales uses the documented estimate
  `units/month = 10^(5.50 − 0.70 × log10(BSR))` on the primary category rank and is
  labelled an ESTIMATE everywhere (user-requested addition, present on every CSV row
  via `bsr_est_monthly_sales` / `bsr_est_note`).

## Reproduce

```
python lions_mane_sb.py discover --page 1     # ScrapingBee search per keyword
python lions_mane_sb.py title-gate            # cheap hard-fail pass
python lions_mane_sb.py details               # product endpoint per survivor
python lions_mane_sb.py text-gate             # strict text gates
python run_vision_sb.py qwen2.5vl:7b          # image readings (needs ollama :11435)
python lions_mane_sb.py visual                # merge vision + structured evidence
python lions_mane_sb.py finalize              # pass/review/rejected CSVs
python lions_mane_sb.py summarize && python lions_mane_sb.py analyze
python audit_sb.py                            # independent audit
```
