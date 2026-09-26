# Faire-to-Amazon Discovery — Completion Report
**Date:** 2026-09-24T09:17Z
**Operator:** T2 Holdings LLC
**Branch:** `main` (no commit, no push)
**Verdict:** DESIGN + INTEGRATION CONTRACT + OFFLINE (MODE 1) layer built. **Stopped at phase gate.** No live research run was authorized; no purchases, listings, supplier contacts, or marketplace writes occurred.

---

## 1. Files added

**Offline research package (`Northstar_backend/faire_research/`)**
- `__init__.py` — public API, gate + compliance header
- `enums.py` — provenance, match-confidence, eligibility, brand-risk, fee-confidence, pack, opportunity states, research modes
- `economics.py` — **TEMPORARY** Decimal economics adapter (landed cost, contribution profit, ROI, margin, downside)
- `matching.py` — identity matching, exact-match safety, pack/case-break logic
- `qualification.py` — hard disqualifiers, 0–100 scoring, state machine, compliance gate
- `tests/test_economics.py`, `tests/test_matching_packs.py`, `tests/test_qualification.py` — 45 offline tests

**Documentation + schemas (`docs/northstar-faire-discovery/`)**
- `00`–`15` (16 markdown documents)
- `faire-discovery-schema.json`, `amazon-match-schema.json`, `pack-normalization-schema.json`, `opportunity-score-contract.json`, `research-batch-contract.json`, `risk-register.json`

**Offline research artifacts (session evidence; not code)**
- `Northstar_backend/data/faire/faire_candidates.csv`, `faire_small_candidates.csv`, `faire_amazon_screened.json`, `faire_amazon_final.json`
- `.playwright-mcp/faire-products-batch1.json`, `batch2.json`

## 2. Files modified
None. No existing file, AGENTS.md, constitution, or safety control was changed. `.env` was not touched in this phase.

## 3. Data sources used
Faire discovery (authenticated, operator-authorized browser session; discovery fields only); existing Northstar Amazon caches (`data/seller-offer-cache.json` 247 ASINs, `data/enriched-offer-cache.json` 263 ASINs); Bright Data Web Unlocker via existing `amazon_search`/`bright_data_client` adapters. No new provider integrations were built.

## 4. External calls made
- Faire discovery API reads (2 pages × 30 keyword categories) during prior discovery — authenticated, read-only, no account mutation.
- Amazon via Bright Data Web Unlocker: **84 requests** in the bounded screen (60 search + 24 product-detail), within the operator-approved 100-request budget.
- No external calls were made by the `faire_research` package itself (fully offline).

## 5. Batches run
Only partial Batch 1–3-style discovery occurred (exploratory, before the compliance spec): a 2,703-product discovery pull and an 84-request Amazon screen. **No batched research run was executed under the new batch contract.** Batches 1–4 remain contractual; each requires operator approval and the clearing of gates 1C-01/1C-03/1C-04/1C-07.

## 6. Faire brands reviewed
Discovery captured brand tokens across ~30 keyword categories; not classified for marketplace policy (Batch 1 requires authorization). **0 brands classified.**

## 7. Products reviewed
2,703 Faire products normalized; 978 passed a small-item heuristic; 60 searched on Amazon; 24 detailed. These are **discovery-benchmark records only**, not sourcing candidates.

## 8. Amazon candidates matched
60 searched; matches classified by the new exact-match safety gate. Match similarity was frequently low (0.27–0.72).

## 9. Exact matches
**0** classified `EXACT_IDENTIFIER_MATCH` / `EXACT_ATTRIBUTE_MATCH` (GTIN/MPN not available for the discovery items). All title-only matches route to `MATCH_REVIEW`/`AMBIGUOUS`; none advance automatically.

## 10. Ambiguous matches
The majority of the 24 detailed matches are `PROBABLE_MATCH_REVIEW_REQUIRED`/`AMBIGUOUS` (title-only, no GTIN). No candidate is reported here as sellable.

## 11. Direct suppliers identified
**0** (Batch 4 work; not authorized this phase).

## 12. Brands permitting Amazon
**0 confirmed.** Authorization is `UNKNOWN` by default; a Faire brand never implies Amazon permission.

## 13. Products with complete economics
**0** — no record reached `ESTIMATED_FROM_COMPLETE_INPUTS`+ with verified landed cost and full fees. The temporary adapter computes correctly when given complete inputs (proven in tests) but no real candidate had complete inputs.

## 14. Qualified opportunities
**0** `QUALIFIED_FOR_MANUAL_REVIEW`; **0** `SOURCE_READY`; **0** `PURCHASE_READY`.

## 15. Rejected opportunities by reason
- `faire_is_only_sourcing_route` — applies to every discovery item by definition (no direct route established): all.
- `exact_match_failed` — title-only matches: all detailed items.
- `invoice_path_absent` — all.
- `required_cost_or_fee_missing` — no complete fee/cost data: all.
No item was rejected for lack of a real price spread; they were rejected for **lack of authorization, invoice path, exact match, and complete economics** — as required.

## 16. Tests run and results
```
cd Northstar_backend && python -m pytest faire_research/tests -q
→ 45 passed
```
Covers IDENTITY, PACKS, ECONOMICS, COMPLIANCE (per `12-testing-report.md`). DATA/SECURITY families are contract-only here and rely on the existing `foundation` security tests.

## 17. Security findings
- No credentials handled by the new package (offline; no `.env`).
- No secret printed, logged, or committed.
- Org-scoping/provenance/confidence/staleness are required fields by contract; enforcement lands with the foundation-auth gate (1C-01).
- Ordinary GET routes are contract-bound to make zero provider calls (not yet implemented).

## 18. Policy findings
- Confirmed and encoded: **Faire is discovery-only**; Faire wholesale pricing is `DISCOVERY_BENCHMARK_ONLY — AMAZON RESALE THROUGH FAIRE NOT AUTHORIZED`.
- "Not on Amazon" is treated as a policy **risk**, not an opportunity.
- Faire-only sourcing is a **hard disqualifier**.

## 19. Known gaps
See `14-known-gaps.md`. Principally: canonical economics (1C-04), job worker (1C-03), real auth (1C-01), keyword module (1C-07), frontend serve (1C-06); no per-ASIN eligibility source; no Amazon dimensions source; Faire packaged weight not exposed.

## 20. Git status
```
?? Northstar_backend/faire_research/
?? docs/northstar-faire-discovery/
```
Branch `main` (protected). **No commit, no push.** Files are untracked pending operator review.

## 21. Confirmation
- No purchases: **0**
- No listings created: **0**
- No supplier contacts: **0**
- No marketplace writes: **0**
- No cart/account/application actions: **0**

## 22. Honesty note
The offline research layer, contracts, schemas and tests were implemented and
verified. A compliant **live** research run was **not** executed, because the
phase gates (1C-01/1C-03/1C-04/1C-07) are not cleared. No candidate is reported
without its evidence state, and no price spread alone was treated as
Amazon-sellable.

---

Faire was used for product and brand discovery only. No Faire-sourced merchandise was approved for Amazon resale. Candidates require a separate authorized wholesale path, verified Amazon eligibility, exact pack matching, complete economics, and operator approval before purchasing.
