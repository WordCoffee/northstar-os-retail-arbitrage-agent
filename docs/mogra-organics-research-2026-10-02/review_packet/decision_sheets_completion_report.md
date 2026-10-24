# Completion Report — Printable Supplier, Packager and Shipping Decision Sheets

**Project:** Mogra Organics (T2 Holdings LLC) — herbs/spices holiday Amazon launch
**Date:** 2026-10-02
**Scope of this pass:** addendum only. No research restarted, no external requests sent.

---

## 1. Deliverables

| Deliverable | Absolute path | Size |
|---|---|---|
| Standalone printable sheets (new) | `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\docs\mogra-organics-research-2026-10-02\review_packet\Mogra_Organics_Suppliers_Packagers_Shipping_Decision_Sheets.pdf` | 4 pp landscape |
| Canonical partner-review packet (updated in place) | `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\docs\mogra-organics-research-2026-10-02\review_packet\Mogra_Organics_Holiday_Amazon_Launch_Blueprint_2026-10-02.pdf` | 24 pp (20 portrait + 4 landscape) |

Canonical packet = original 20 blueprint pages unchanged, plus the same 4 decision-sheet pages
appended (PDF pages 21–24). Pages were merged with `pypdf`, so per-page orientation is preserved.

### Supporting appendix tables (new)

All in `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\docs\mogra-organics-research-2026-10-02\`

| File | Rows | Cols |
|---|---|---|
| `supplier_decision_sheets.csv` | 9 | 18 |
| `packager_decision_sheets.csv` | 6 | 22 |
| `shipping_options_comparison.csv` | 10 | 15 |
| `shipping_input_checklist.csv` | 14 | 6 |
| `route_speed_ranking.csv` | 5 | 9 |

### Also updated

- `review_packet/holiday_launch_blueprint.md` — new section 21 documenting the addendum.
- `review_packet/deliverable_manifest.md` — new PDFs, new tables, route-label legend,
  five new outstanding dependencies, entity-spelling correction.
- `_scripts/build_decision_sheets.py` — CSV generator (validates its own column counts).
- `_scripts/decision_sheet_pages.py` — shared page builder (single source for both PDFs).
- `_scripts/build_decision_sheets_pdf.py`, `_scripts/merge_decision_sheets.py` — reproducible build.
- `_scripts/validate_decision_sheets.py`, `_scripts/validate_identifiers.py` — validation.

---

## 2. Requirements coverage

### 2.1 Projects kept distinct

The sheets cover **herbs/spices only**: buyable target 25 Nov 2026, latest acceptable 1 Dec 2026,
product budget $1,500–$2,500, 2–4 SKUs if MOQ and economics permit. Lion's Mane is named once,
explicitly marked separate, and its ~500 bags at the owner's home are described as already
located — no international sourcing implied. No budget or inventory figure is shared.

### 2.2 Suppliers page

Eight-provider shortlist, split into **turnkey finished-product (6)** and **ingredient-only (3)**
tables. Columns: company, country, public contact, products and exact forms, supply-only vs
turnkey capability, evidence status, documentation gaps, MOQ, price, stock, sample dispatch,
production/packing lead, earliest dispatch, estimated US arrival, outreach priority, reason.

Ranking rule printed on the page: **order-size and target-date fit first, not air-freight
availability.** Explicit statement that an overseas provider is not treated as fast merely
because air freight exists, with production readiness and export documentation as separate gates.

### 2.3 Packagers page

Three classes separated: **food co-packer/filler**, **turnkey ingredient-and-packing**,
**sealed-unit label/FBA-prep**. Columns: company, location, public contact, customer-supplied
ingredients (confirmed or unknown), whole-spice and powder capability, stock jars/pouches,
filling, sealing, lot/date coding, label application, organic-handling capability with evidence,
minimum run, setup charges, receiving/storage charges, earliest production slot,
finished-goods-ready, FBA prep and carrier pickup, distance, priority.

**FBA prep centres are explicitly not presented as authorised to open, reseal or repack food** —
stated as label application and poly-bagging of already-sealed units only, with repacking named
as a qualified-packer task.

**"Nearby" is not asserted.** Every packager distance cell reads
`OWNER_INPUT_REQUIRED — no pickup/delivery ZIP provided`. No ZIP was guessed.

### 2.4 Shipping options page

Options A–G plus a comparison platform row: factory/supplier-arranged; buyer-arranged
international express; independent air-freight forwarding; ocean LCL (flagged not suitable for
this launch order); domestic parcel/LTL supplier→packer; domestic packer→Amazon; Amazon Partner
Carrier; and Freightos-type marketplaces.

Grounded public research performed on DHL Express, FedEx International Priority, UPS Worldwide
Expedited/Saver, DHL Global Forwarding air and ocean LCL. Published transit indications are
attributed and kept **separate** from the quote-required delivered estimate.

Per option: official contact/quote link, origin pickup coverage, transport mode,
door-to-door vs terminal-only, customs brokerage included vs separate, food/organic acceptance
questions, required shipment information, published transit indication, quote-required actual
delivery estimate, cost coverage and exclusions, suitability for a small initial order, and the
recommended next quote request.

**Marketplace discipline:** Freightos is labelled a comparison platform, not the carrier
performing pickup; the decision box repeats this.

### 2.5 Apples-to-apples comparison

Fourteen required inputs in a dedicated block — exact pickup address, delivery ZIP, commodity and
product form, origin country, carton count, gross weight, pallet information, declared value,
ready-for-pickup date, import documents, Incoterm and named place, plus ZIP for proximity
screening, FBA destination and the Amazon placement-fee schedule. Each carries a reason, an owner,
a status and what it blocks.

Charge-line separation printed on the page: origin pickup and export · main transport · insurance
· customs brokerage · duties and import charges · destination handling · final delivery ·
storage/detention and exclusions · **Amazon inbound transportation and placement charges
(separate)**. Explicit instruction that an airport-only quote must not be compared with a
delivered quote without adding the remaining charges, and that the same endpoint must be compared.

The Amazon FBA destination is unresolved, so the US leg uses a provisional receiving point and the
Amazon leg is flagged as unresolved.

### 2.6 Speed-first prioritisation

Complete routes ranked R1–R5 in the required order: supplier ready → origin pickup →
international transit → customs release → packer receiving → packing queue and production →
finished-unit inspection → domestic dispatch → Amazon receiving → buyable inventory.

Ranking priority applied: (1) product/order-size fit and required documentation, (2) earliest
credible finished-unit availability, (3) fully delivered cost, (4) coordination complexity and
cash exposure.

Labels used: **POTENTIALLY FEASIBLE**, **TIMING RISK**, **LONGER-TERM OPTION**, and
**UNRANKED / CONFIRMATION REQUIRED**. Source-confirmed dates are held separate from planning
allowances — the `source_confirmed_vs_planning` column carries
`PLANNING ALLOWANCE ONLY` on every ranked row, because no supplier has responded.

**No route is labelled TARGET SUPPORTED** — no evidence currently supports a target. No route is
described as cheapest or fastest.

---

## 3. Evidence and assumption discipline

| Legend term | Meaning | Applied |
|---|---|---|
| VERIFIED | independently corroborated | Pearl ingredient organic status (USDA OID 2026-10-02) only |
| SUPPLIER-CLAIMED | provider assertion | all other organic claims |
| QUOTE REQUIRED | no price exists | every price and MOQ without a published figure |
| UNCONFIRMED | not yet established | **all** timing fields |
| OWNER_INPUT_REQUIRED | needs owner record | all packager distances; ZIPs; FBA destination |
| PLANNING ALLOWANCE | internal estimate, not a commitment | route timing |

**Nothing invented.** No stock level, sample time, production lead time, dispatch date, arrival
date, freight rate, delivered price, or delivery guarantee appears in either PDF. Unknowns are
marked unknown rather than zero or estimated favourably.

**Claim discipline verified programmatically.** The validator scans both PDFs for
`lead-free`, `safer than`, `FDA-approved`, `clinically proven`, disease/-treatment language,
`best supplier`, `cheapest route` and `guaranteed delivery`. Result: **zero uses as claims.**
The only occurrence of `lead-free` is inside the packet's explicit prohibition sentence
("Do NOT use 'lead-free', 'safer', or competitor-superiority language without appropriate
substantiation"), which the validator recognises as prohibition context.

**No outreach, no purchases, no accounts, no production changes.** Nothing was sent, quoted or
purchased. All writes are confined to `docs/mogra-organics-research-2026-10-02/`. No commit made.

---

## 4. Validation evidence

| Check | Result |
|---|---|
| CSV column integrity, all 30 tables | **0 mismatches, 541 data rows** |
| New tables: 9 / 6 / 10 / 14 / 5 rows | all column-aligned |
| Standalone PDF | 4 pages, all landscape 792×612, 15,950 chars, **0 near-blank pages** |
| Canonical PDF | 24 pages — 20 portrait + 4 landscape (21–24), 55,867 chars, **0 near-blank pages** |
| Required-content check, standalone | **41 / 41 present** |
| Forbidden claims used as claims | **none**, both PDFs |
| Provider and carrier identifier integrity | **15 / 15 intact** — no truncated names |
| Original blueprint content retained in canonical | **yes** — dates, budget, SKU count, entity |
| Mid-word break scan | no broken words |
| Production DB SHA256 | `A4684F36…C99D0AD` — **identical to pre-work baseline** |

Entity spelling corrected in the canonical packet from `T2Holdings LLC` to `T2 Holdings LLC`
(owner-supplied form; still **unverified against business records**).

---

## 5. Deviations and judgement calls

1. **The shipping sheet is two landscape pages, not one.** Ten service options across nine
   comparison fields, fourteen quote inputs and five routes cannot fit one landscape page at
   readable type. The brief forbids shrinking text to fit, so the sheet runs to two pages and
   says so on its face. Sheets 1 and 2 each hold exactly one page. Total: 4 pages, not 3.
2. **Collapsed identical cells.** Where every provider's stock, sample, lead, dispatch and arrival
   field carries the same unknown, the page shows one "all UNCONFIRMED" cell instead of repeating
   the same unknown nine times per row. Full per-field detail is in the CSVs, which serve as the
   supporting appendix the brief calls for.
3. **Merging rather than mixed-orientation templating.** Appending landscape pages inside the
   portrait blueprint produced 9.8-inch tables rendered into a narrower frame, inflating the
   packet to 44 pages. The pages are now generated once and merged with `pypdf`, which preserves
   per-page size and keeps the packet at 24.
4. **No TARGET SUPPORTED label issued.** With zero provider responses, no evidence supports a
   target date; issuing that label would have been an unsupported claim.

---

## 6. Blocked — unchanged by this pass

- All supplier economics. No quote exists, so contribution and ACOS remain non-computable.
- All timing. Stock, lead, dispatch and arrival stay UNCONFIRMED until providers respond.
- Origin and US-packer ZIP codes, carton count, weight, dimensions, declared value, Incoterm.
- Amazon FBA destination, which gates the final inbound leg.
- Duty and AD-CVD — customs-broker review still required; no rate asserted.
- Lion's Mane lab identity, panel, inventory facts and shelf-life — OWNER_INPUT_REQUIRED.
- USDA OID automation for ~13 remaining suppliers — tooling limitation, manual lookups queued.

## 7. Next owner actions

1. Supply origin and US-packer ZIP codes — this is the single input that unblocks arrival estimates
   and packager proximity screening.
2. Supply carton count, gross weight, dimensions and declared value.
3. Agree an Incoterm and named place.
4. Fix the Amazon FBA destination.
5. Confirm the entity legal spelling, then approve and send the 6 herb/spice RFQs plus addendum.
6. Commission the customs-broker review (`review_packet/customs_broker_review_packet.md`).