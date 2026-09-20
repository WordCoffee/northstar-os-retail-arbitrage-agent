# LEGAL REVIEW PACKAGE — Phase E4

**Date:** 2026-09-20 · **Baseline:** E3 · **Nature:** **INDEX ONLY** — this
document assembles existing material for counsel; it is **not new legal
analysis** and contains no binding language. All binding-language gaps remain
marked `[LEGAL REVIEW REQUIRED]`.

---

## 1. Purpose & how to use

Give counsel this document plus the referenced files, in the order listed.
Nothing here should be treated as agreed/enforceable until counsel signs off;
the operator (T2 Holdings LLC, Texas) is the contracting party.

## 2. Document index (read in order)

| # | Document | What it is | Counsel action |
|---|---|---|---|
| 1 | `docs/legal/TERMS_OF_SERVICE.md` | ToS draft (alpha, sized to current feature set) | Fill `[LEGAL REVIEW REQUIRED]` clauses (§10) |
| 2 | `docs/legal/PRIVACY_POLICY.md` | Privacy draft (local-first posture) | Set retention + breach-timeline wording |
| 3 | `docs/legal/REFUND_CANCELLATION.md` | Refund/cancellation draft (billing not live) | Set refund window / unused-credit formula |
| 4 | `docs/legal/README.md` | Placeholder registry (all `[LEGAL REVIEW REQUIRED]` markers) | Resolve each marker |
| 5 | `docs/contracts/DISCLAIMER_EMBED_v1.md` | Disclaimer slot contract + canonical copy | Confirm FTC alignment of copy |
| 6 | `PROMO_COMPLIANCE.md` (D2) | Per-module sourcing/ToS posture + L1/L2 copy items | Confirm scrape-path authorization wording |
| 7 | `docs/BUILD_RECORD.md` | Independent-development / provenance record (Phases A–D) | Evidence of independent build (market vocabulary only) |
| 8 | `docs/contracts/SECURITY_BOUNDARIES_v1.md` | No-leak + least-privilege admin (D12 IP protection) | Confirm no-leak as IP safeguard |
| 9 | `HANDOFF.md` | Architecture + deferred items | Context |

## 3. Canonical disclaimer text (as shipped)

**Standard block (footers / auth / onboarding):**
> Dashboards show estimates from available data — not guarantees, not a
> recommendation to buy, and not an approval to resell. Plans never flip live
> gates; live actions require a fresh named operator approval.

**Result-view copy:** per-tool honesty notes (Scout/calculators) + Golden Goose
"Not a purchase authorization" + "estimates on fixture/report data".
**Export copy:** "Estimates only. Not a recommendation to buy or an approval to resell."
(Full slot registry: `docs/contracts/DISCLAIMER_EMBED_v1.md`.)

## 4. Resale / ToS exposure notes (from D2)

- **API-keyed sourcing paths** (OpenWebNinja/Unwrangle/Bright Data/Firecrawl/
  Scrape.do/EasyParser/RapidAPI) → PASS under their API terms.
- **HTML-scrape paths** (`costco_playwright_scraper.py`,
  `costco_browser_scraper.py`, Web Unlocker on Amazon/Costco pages) →
  **REVIEW REQUIRED**: Amazon.com and Costco.com ToS restrict unlicensed
  automated access; resale of scraped marketplace data carries ToS risk.
- **Supplier directory** (`data/us_suppliers.csv`) → public catalog metadata, no
  violation found.
- **Item L1 (required copy):** add an authorization line on scrape-enabled
  surfaces: "Data is sourced under current provider terms; automated
  wholesale/retail access may require permission." → `[LEGAL REVIEW REQUIRED]`.

## 5. IP safeguard rules (already enforced technically)

- **No-leak (blueprint D12):** Master Brain, providers, routing, prompts,
  scoring, and cost formulas stay server-side; enforced by the BFF no-leak
  allowlist, Functions `_envelope.js`, and `export_manifest.assert_no_export_leakage`.
- **Independent development:** competitor names appear only as market-reference
  vocabulary; `docs/BUILD_RECORD.md` is the dated provenance record.
- **Least-privilege admin:** admin sees basic account fields only (no tenant IP).
- **Gap to flag:** a dedicated `docs/INDEPENDENT_DEVELOPMENT.md` (proposed in
  Alpha Blueprint A7) was not produced; `docs/BUILD_RECORD.md` serves the
  provenance purpose. Counsel may request a formal independent-development
  statement — **flagged**.

## 6. Consolidated `[LEGAL REVIEW REQUIRED]` register

Arbitration/dispute forum · limitation-of-liability & caps by jurisdiction ·
governing-law/venue specificity · indemnification & severability ·
recurring-billing/auto-renewal/tax/price-change wording · data-retention
schedules · cross-border transfers/sub-processors · deletion-request SLA ·
**data-breach notification timeline** · minors terms · policy-change notice ·
refund window / pro-rata · unused-credit formula & expiry · chargebacks ·
**scrape-path authorization statement (L1)** · **STT (transcribe) deferral
wording (E3)**. (Source of record: `docs/legal/README.md` + D2 + E3.)

## 7. Questions for counsel

1. Which jurisdiction's consumer-protection rules govern refund/auto-renewal at launch?
2. Acceptable breach-notification timeline (state + any applicable federal)?
3. Is an "estimates only, not investment advice" framing sufficient for the arbitrage guidance surfaces?
4. Required wording for automated wholesale/retail access (L1)?
5. Entity timing: sole-proprietor → Texas LLC trigger (Alpha Blueprint D7).

## 8. Out of scope

No new legal analysis, no drafting of binding clauses, no jurisdiction-specific
conclusions were produced here. Counsel engagement is the D8 trigger ($10K MRR
OR 25–50 paying customers OR 6 weeks live).