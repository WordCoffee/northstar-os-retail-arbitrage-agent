# Deliverable Manifest — Mogra Organics Research Folder

**Folder:** `docs/mogra-organics-research-2026-10-02/`
**Date:** 2026-10-02

---

## Review packet (owner-facing)

| File | Purpose | Type | Status | Dependencies |
|---|---|---|---|---|
| `review_packet/Mogra_Organics_Holiday_Amazon_Launch_Blueprint_2026-10-02.pdf` | **Current review presentation** (24 pp = 20 blueprint + 4 landscape decision sheets) | presentation (derivative) | ✅ complete | — |
| `review_packet/Mogra_Organics_Suppliers_Packagers_Shipping_Decision_Sheets.pdf` | **Standalone printable decision sheets** (4 pp landscape: Suppliers, Packagers, Shipping ×2) | presentation (derivative) | ✅ complete | — |
| `review_packet/holiday_launch_blueprint.md` | Editable source of the above | editable source | ✅ complete | — |
| `review_packet/Mogra_Organics_Sourcing_Launch_Working_Blueprint_2026-10-02.pdf` | Prior sourcing/certification presentation (27 pp, retained) | presentation (derivative) | ✅ retained | — |
| `review_packet/working_blueprint.md` | Editable source of prior presentation | editable source | ✅ retained | — |
| `review_packet/completion_and_validation_report.md` | Completion + validation + security audit | report | ✅ complete | — |
| `review_packet/owner_decision_brief.md` | Decision narratives | brief | ✅ complete | owner inputs |
| `review_packet/customs_broker_review_packet.md` | Broker review packet (unsent) | brief | ✅ complete | broker engagement |

## Canonical data tables

| File | Rows | Purpose | Canonical? |
|---|---|---|---|
| `supplier_master.csv` | 51 | commercial suppliers | ✅ canonical |
| `resources_and_directories.csv` | 7 | non-supplier resources | ✅ canonical |
| `supplier_product_matrix.csv` | 49 | supplier × product × form | ✅ canonical |
| `organic_verification.csv` | 60 | certification evidence per form | ✅ canonical |
| `priority_verification_queue.csv` | 15 | open certification checks | ✅ canonical |
| `route_comparison.csv` | 12 | route arrangements | ✅ canonical |
| `pricing_comparison.csv` | 15 | pricing lines | ✅ canonical |
| `evidence_register.csv` | 20 | claim-level evidence | ✅ canonical |
| `risk_register.csv` | 13 | risks | ✅ canonical |
| `decision_register.csv` | 10 | decision register | ✅ canonical |
| `assumptions_register.csv` | 8 | isolated scenario assumptions | ✅ canonical |
| `cost_and_quote_matrix.csv` | 18 | cost lines | ✅ canonical |
| `product_route_readiness.csv` | 12 | product/route readiness | ✅ canonical |
| `search_log.csv` | 27 | discovery log | ✅ canonical |
| **`product_opportunity_ranking.csv`** | **24** | **holiday-launch product scoring** | ✅ canonical (new) |
| **`competitor_observations.csv`** | **20** | **public Amazon observations** | ✅ canonical (new) |
| **`product_supplier_matrix.csv`** | **16** | **product → supplier matches** | ✅ canonical (new) |
| **`economics_scenarios.csv`** | **17** | **cost/price scenario lines** | ✅ canonical (new) |
| **`launch_action_plan.csv`** | **21** | **dated critical path** | ✅ canonical (new) |
| **`source_evidence_register.csv`** | **12** | **sources with dates** | ✅ canonical (new) |
| **`finalist_decision_comparison.csv`** | **6** | **finalist comparison (correction pass)** | ✅ canonical (new) |
| **`hypothetical_economics.csv`** | **26** | **hypothetical economics with formulas** | ✅ canonical (new) |

> Correction pass: `competitor_observations.csv` **rewritten** (ASINs, variation-family ratings context, comparable class). The earlier 27-page presentation is renamed `SUPERSEDED_…pdf` and retained.

## Partner packet tables (added — partner-review pass)

| File | Rows | Purpose |
|---|---|---|
| `partner_decision_packet.csv` | 8 | providers on same spec/basis; QUOTE REQUIRED unknowns; customer-ingredient + label-application questions; outreach priority |
| `launch_schedule.csv` | 23 | dated Oct 5–Dec 1 plan; 3 workstreams; role, dependencies, evidence, status, delay consequence, backup |
| `decision_gates.csv` | 7 | G1–G7 gates for assortment/provider/fulfilment changes |
| `rfq_drafts/RFQ_ADDENDUM_labels_and_customer_ingredients.md` | — | label-application + customer-supplied-ingredient questions appended to provider RFQs |

## Decision-sheet tables (added — printable supplier/packager/shipping addendum)

| File | Rows | Purpose |
|---|---|---|
| `supplier_decision_sheets.csv` | 9 | ingredient suppliers separated from turnkey providers; contact, forms, evidence + gaps, MOQ/price, stock/sample/lead/dispatch/arrival, priority |
| `packager_decision_sheets.csv` | 6 | co-packer / turnkey / sealed-unit-FBA-prep classes; customer-ingredient acceptance, whole vs powder, containers, fill/seal/code/label, organic evidence, run/charges/slot, FBA prep, distance, priority |
| `shipping_options_comparison.csv` | 10 | options A–G + comparison platform; mode, coverage, customs brokerage, food/organic acceptance questions, published transit, delivered estimate (QUOTE REQUIRED), cost coverage, suitability, next quote request |
| `shipping_input_checklist.csv` | 14 | apples-to-apples quote inputs, why each is needed, owner, status, what it blocks |
| `route_speed_ranking.csv` | 5 | complete-route ranking R1–R5 with route labels and source-confirmed vs planning separation |

> **Route labels used:** TARGET SUPPORTED · POTENTIALLY FEASIBLE · TIMING RISK · LONGER-TERM OPTION · UNRANKED / CONFIRMATION REQUIRED.
> Every provider timing field is currently UNCONFIRMED because no provider has been contacted; no lead time, dispatch date or arrival date is asserted.
> No freight rate, delivery date or cheapest-route claim exists anywhere in this addendum.
> `Freightos` is recorded as a **comparison platform**, not as the carrier performing pickup.

## RFQ drafts (all UNSENT)| File | Target |
|---|---|
| `rfq_drafts/rfq_pearl_bulk_organic.md` | Pearl — bulk organic |
| `rfq_drafts/rfq_pearl_finished_private_label.md` | Pearl — finished/private label |
| `rfq_drafts/rfq_pearl_launch_cinnamon_pepper.md` | Pearl — launch-specific (new) |
| `rfq_drafts/rfq_copacker_spices_inc.md` | Spices Inc — packing-only + turnkey |
| `rfq_drafts/rfq_copacker_specialty_food.md` | Specialty Food Co-Packers |
| `rfq_drafts/rfq_copacker_organic_spices_inc.md` | Organic Spices Inc |

## Supporting

| Path | Purpose |
|---|---|
| `pearl_evidence_packet.md` | Pearl verification trail |
| `shortlist.md` | corrected supplier shortlist |
| `duty_and_import_review.md` | duty / AD-CVD status |
| `supplier_questions.md` | master question list |
| `rfq_template.md` | generic RFQ template |
| `_raw/amazon_bsr_spices.json`, `_raw/amazon_search_obs.json` | raw public observations |
| `_scripts/` | reproducible build scripts (CSV + PDF generators) |

## Canonical vs derivative

- **Canonical:** all `.csv` tables — single source of truth.
- **Derivative:** both PDFs and `working_blueprint.md` / `holiday_launch_blueprint.md` — generated from the canonical tables. The PDFs render counts directly from the CSVs, so figures cannot drift.

## Outstanding dependencies

| Dependency | Blocks |
|---|---|
| T2 Holdings LLC exact legal spelling | All 6 RFQs |
| Owner origin + US-packer ZIP codes | Any arrival estimate; packager "nearby" screening |
| Carton count, weight, dimensions, declared value | All freight quotes |
| Incoterm and named place agreed | Cost split across shipping legs |
| Amazon FBA destination fixed | Final Amazon inbound leg quote |
| Owner SKU decision | Quote collection |
| Supplier responses (6 RFQs) | Economics |
| Customs-broker review | Landed cost, import routes |
| Ceylon cinnamon lot COA | Product differentiation claim |
| Co-packer NOP certification | Route B/C |
