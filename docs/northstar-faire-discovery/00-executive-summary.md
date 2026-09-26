# 00 — Executive Summary

**Phase:** Faire-to-Amazon wholesale opportunity discovery (research only)
**Date:** 2026-09-24
**Operator:** T2 Holdings LLC
**Status:** DESIGN + INTEGRATION CONTRACT + OFFLINE (MODE 1) implementation. **Stopped at phase gate.**

## Compliance headline (non-negotiable)

**Faire is a PRODUCT AND BRAND DISCOVERY SOURCE ONLY.** Faire's published
retailer guidance states it cannot fulfil orders for Amazon sellers and that
Faire-purchased goods cannot be listed on third-party marketplaces. Therefore:

- No Faire-sourced merchandise is recommended or approved for Amazon resale.
- Faire wholesale pricing is labelled `DISCOVERY_BENCHMARK_ONLY — AMAZON RESALE THROUGH FAIRE NOT AUTHORIZED`.
- A candidate may only advance on a **separate, direct wholesale relationship**
  that explicitly permits Amazon resale and provides compliant invoices.
- No purchase, cart, account creation, application, brand contact, listing, or
  marketplace change is performed by this workflow.

## What was built now (highest stage permitted)

Because the canonical **economics engine (1C-04)**, **job worker (1C-03)**,
**real auth (1C-01)**, **keyword module (1C-07)** and frontend serve are all
still pending (see `docs/northstar-phase1b/16-phase1c-recommendation.md`), the
spec instructs us to **stop at the appropriate gate** and build only what is safe:

| Built now | Not built (gated) |
|---|---|
| `Northstar_backend/faire_research/` — offline research logic (45 tests) | Live provider research (MODE 2/4) — needs 1C-03 worker + approvals |
| TEMPORARY research economics adapter (Decimal, labeled) | Canonical economics engine (1C-04) |
| Identity match + exact-match safety + pack/case normalization | Amazon eligibility/gating lookup (no real source exists) |
| Compliance gate, hard disqualifiers, 0-100 scoring, state machine | Supplier contact / listing / purchase (prohibited this phase) |
| This documentation package (16 docs + 6 schemas) | Frontend research surface (needs 1C-06) |

## Key findings from the offline evidence gathered earlier this session

- Faire catalog+pricing is accessible via an authenticated Faire session; a
  discovery pull of **2,703 products** (27 keyword categories) was normalised;
  **978** passed a small-item heuristic (reviews ≥ 30, case/unit cost \$4–60,
  margin ≥ \$5, no bulky keywords).
- Amazon lookup via the existing Bright Data Web Unlocker adapter produced
  matches, but **match confidence was often low (sim 0.27–0.72)** — confirming
  the need for the exact-match safety gate before any candidate advances.
- Prior Northstar caches hold **~269 enriched Amazon ASINs** (Costco/Kirkland),
  reusable as timestamped evidence but with little overlap to Faire categories.

## The economics and safety rules enforced

- Correct economics is *Amazon price − fees − landed cost*, **never**
  "Faire price − Amazon price".
- `Decimal` for all money; **unknown fee/cost is never zero**; `FEE_UNKNOWN`
  cannot pass.
- Hard disqualifiers run **before** scoring; `SOURCE_READY` needs a verified
  direct supplier; `PURCHASE_READY` additionally needs confirmed eligibility,
  authorization, exact pack match, complete economics and operator approval.

## Required operator next steps

1. Approve 1C-01 (real auth) — sole first blocker.
2. Approve 1C-04 (canonical economics) so the temporary adapter can be retired.
3. Approve the MODE 4 live-verification budget before any further provider calls.
4. Direct-supplier outreach question set (`04`) requires manual operator action.

> Faire was used for product and brand discovery only. No Faire-sourced
> merchandise was approved for Amazon resale.
