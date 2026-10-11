# RESEARCH SUMMARY — updated 2026-10-11

**This summary supersedes the 2026-10-08 summary for anything marked "changed
since". Everything else is carried forward verbatim from
`../design_studio_deep_research_20261008/RESEARCH_SUMMARY.md`.**

## Evidence ledger (as of the 2026-10-08 research run — carried forward)

| Metric | Value |
| --- | --- |
| Sources registered in `SOURCES.csv` | **224** (the register file carries 325 rows including later additions) |
| … labelled VERIFIED (directly observed) | 175 |
| … labelled REPORTED (vendor/third-party claim) | 46 |
| … labelled UNKNOWN (not confirmed) | 3 |
| Malformed rows / duplicate ids / unresolved references | **0 / 0 / 0** |
| Competitors in `COMPETITOR_MATRIX.csv` | 18 |
| Competitor-matrix cells honestly marked UNKNOWN | 58 |
| Workflows mapped end-to-end in `WORKFLOWS.md` | 8 |
| Amazon spec rows in `AMAZON_REQUIREMENTS.md` | ~60, all `date_sensitive: yes` |
| Seller pain-point themes (with sample sizes) | 5 |
| Differentiated feature concepts in `OPPORTUNITIES.md` | 22, all PROPOSED |

These are counts of the 2026-10-08 deliverables as published there. This folder
did not re-count them; the register file is the source of truth.

## The three findings that still shape the build (unchanged)

1. **Amazon's own AI creative tools are free.** NorthstarOS cannot win on "AI
   image generation for Amazon"; value must sit in the seller's own photography,
   cross-surface consistency, compliance gating, claims governance, and the
   loop.
2. **The keyword→creative loop is structurally unbuilt.** Search-term reports
   aggregate at campaign / ad-group / keyword level with no creative identifier,
   so creative-level attribution cannot be derived automatically. The product
   records which variant was live in which window and lets the operator
   attribute — it never infers it.
3. **On-image text is not indexed by Amazon search.** On-image copy is a
   comprehension and conversion feature, never an SEO claim.

## What changed since 2026-10-08

| Change | Date | Status |
| --- | --- | --- |
| File-only Amazon architecture adopted (no sign-in, no API, no credentials; seller uploads files, uploads the change file back manually) | 2026-10-11 | DECIDED (owner D32–D35) |
| Title rules verified against an owner capture; enforced as FLAGS in every writer | 2026-10-11 | VERIFIED |
| Item Highlights flat-file/API column | — | UNKNOWN (Amazon has not published it; nothing maps or emits one) |
| A+ output = asset pack, not an uploadable module file; ASIN bulk-upload limit | — | UNKNOWN (sources conflict) |
| Self-hosted fonts; zero third-party requests from the UI | 2026-10-11 | VERIFIED (build + scan) |

## Coverage limits and NOT-inspected items

Carried forward verbatim from the 2026-10-08 summary (§6) and restated in this
folder's `README.md`. The short form: **no logged-in surface was reached**;
Seller Central help is JS-gated; G2/Capterra/Trustpilot/Product Hunt returned
403; no YouTube comment text; `pacvue.com` 403; generation never run; the
"A+ alt-text removed" claim is unconfirmed; Ads API v1 report shapes not
fetched; Canva / Firefly / Packify / AdCreative.ai pricing UNKNOWN.

## How this folder is meant to be used

- Build decisions cite a file here, not a memory.
- When a claim is acted on, re-check its `date_sensitive` flag first — Amazon
  specs in `AMAZON_REQUIREMENTS.md` are all marked date-sensitive.
- Anything still UNKNOWN stays UNKNOWN in the product until an official source
  is read; the studio renders "UNKNOWN", never a guess and never a zero.
