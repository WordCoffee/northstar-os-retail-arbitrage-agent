# Amendment Report — Mogra Final Commercial Correction Pass

**Date:** 2026-10-02
**Scope:** corrections only — no research restart, no competing blueprint.
**Canonical presentation:** `Mogra_Organics_Holiday_Amazon_Launch_Blueprint_2026-10-02.pdf` (**16 pages**, updated).

---

## 1. What changed, item by item

### 1.1 Timing — corrected
- **Withdrawn:** "Nov 15 cannot be Prime-ready for Black Friday."
- **Replaced with:** published arrival guidance **establishes readiness risk, not impossibility**. The dates govern **event/Prime-badge readiness**, not whether a later shipment can be received and become buyable.
- **Four stages now kept separate:** published holiday arrival guidance · supplier production timing · delivery to Amazon · receiving and buyable inventory · actual event/program eligibility.
- **Explicit statement added:** no guarantee is made for November 15, Black Friday, Cyber Monday or December availability.

### 1.2 Route claims — corrected
- **Withdrawn:** "fastest" and "best long-term margin."
- **Replaced with:** **"potentially fastest"** (Routes A and C, marked UNPROVEN) and **"cost hypothesis"** (Route B). A visible "Withdrawn claims" callout states that no route is proven cheapest or fastest.

### 1.3 Product recommendations — made visible and provisional
- New table **`finalist_decision_comparison.csv`** (6 finalists) compares: demand evidence · seasonal timing · new-brand accessibility · comparable competitor observations · price/pack opportunity · differentiation · supply timing · confidence · missing evidence · decision · why-vs-alternatives.
- Both primary recommendations (ground Ceylon cinnamon, whole black pepper) are labelled **PROVISIONAL**.
- **Why each wins** is stated explicitly (premium band vs commodity price war; whole/refill format vs private-label floor).
- Where evidence did not support the original ranking (cinnamon sticks, baking-spice set), the recommendation is **downgraded** rather than defended.
- Additional public research was conducted **only** to close finalist gaps: cinnamon sticks and nutmeg competitor observations (with ASINs).

### 1.4 Competitor claims — corrected
- **`competitor_observations.csv` rewritten** to record ASIN, brand, product, form, net qty, pack count, price, price/oz, rating, **ratings context**, category/list, rank note, **comparable class**, date, source, limitations.
- **Ratings-context correction:** the **34,526** counts appears on **three** Simply Organic Ceylon variants (B00ZK8YIXW, B0GVVQV4S7, B07BRPCK32) → it is a **variation-family** count, **not** one child ASIN's reviews. Micro Ingredients 4,639 likewise spans sizes.
- **Commodity vs premium separated** via `comparable_class` so low-priced private-label items are not compared with premium Ceylon.
- Gaps stated: the premium whole-pepper ASIN and the private-label ASINs were **not captured** and are marked as such.

### 1.5 Cinnamon positioning — separated
New section splits three things that were previously blurred:
1. **Food-safety and lot-verification** — requirement: a **lot** COA, not a generic one.
2. **Proposed consumer differentiation** — species-verified Ceylon + lot-level testing transparency (PROPOSED, not a claim).
3. **Evidence of willingness to pay** — observed premium band only.

**Claim discipline callout:** do **not** use "lead-free," "safer," or competitor-superiority language without substantiation; **a generic COA is not equivalent to testing the supplied lot.**

### 1.6 Economics — hypotheticals added, nulls preserved
- All unknown costs remain **null** (never zero).
- New **`hypothetical_economics.csv`** (26 lines) with formulas: max acceptable finished-unit cost · contribution before advertising · break-even ACOS.
- **Clearly-labelled HYPOTHETICAL illustration** (every input assumed): cinnamon 2 oz → $3.54/unit, break-even ACOS 27.3%; pepper 3 oz → $3.19/unit, 26.6%.
- **No supplier quote, CPC, sales forecast or owner budget invented.** Initial inventory (500 units) marked PROPOSED illustrative.
- Fee-source limitation stated (referral assumed 15%; FBA fee unavailable → hypothetical input).

### 1.7 Pricing-lines reconciliation (54 → 15)
- **Cause of the error:** an earlier **malformed intermediate CSV** whose unquoted commas inside address/notes fields split rows into extra fields, inflating a naive line count.
- **Reconciled figure:** **15** genuine pricing lines — because **most suppliers publish no price**.
- **Distinction enforced:** pricing lines (**15**) ≠ economics lines (**17**) + hypothetical economics (**26**). They measure different things and are not conflated.

### 1.8 Owner-review output
- **Front-page decision brief added** (products recommended/provisional · why · confidence · supply/timing feasibility · economic conditions that must hold · decisions and supplier responses needed next).
- Canonical PDF **and** editable source both updated.
- The earlier 27-page presentation is marked **SUPERSEDED** (renamed with a `SUPERSEDED_` prefix; retained, not deleted) with a `SUPERSEDED_marker.md` listing which of its claims are withdrawn.

---

## 2. New / updated files

| File | Change |
|---|---|
| `review_packet/Mogra_Organics_Holiday_Amazon_Launch_Blueprint_2026-10-02.pdf` | **Updated** — 16 pages, corrections applied |
| `review_packet/holiday_launch_blueprint.md` | **Rewritten** — corrected canonical source |
| `review_packet/SUPERSEDED_Mogra_Organics_Sourcing_Launch_Working_Blueprint_2026-10-02.pdf` | **Renamed** (marked superseded, retained) |
| `review_packet/SUPERSEDED_marker.md` | **New** |
| `review_packet/amendment_report.md` | **New** (this file) |
| `competitor_observations.csv` | **Rewritten** — ASINs, variation context, comparable class |
| `finalist_decision_comparison.csv` | **New** — 6 finalists |
| `hypothetical_economics.csv` | **New** — 26 lines |

---

## 3. Validation

| Check | Result |
|---|---|
| Updated PDF exists / non-empty | ✅ 241,724 bytes |
| Pages | ✅ 16 |
| Blank pages | ✅ none |
| "potentially fastest" present | ✅ |
| "cost hypothesis" present | ✅ |
| "readiness risk" (qualified timing) present | ✅ |
| Ratings variation-family context present | ✅ |
| HYPOTHETICAL illustration + break-even ACOS present | ✅ |
| Withdrawn phrases removed ("cannot be Prime-ready", "Fastest, no import", "Strong margin potential") | ✅ none present |
| Front-page decision brief present | ✅ |
| CSV column integrity (all tables) | ✅ zero mismatches |
| Unknowns preserved as null | ✅ |

---

## 4. Side-effect audit

| Item | Result |
|---|---|
| Production database | **UNCHANGED** — SHA256 `A4684F36…D0AD` identical before and after |
| Production code / config | **NONE modified** |
| RFQs sent / suppliers contacted | **NONE** |
| Accounts created / money spent | **NONE** |
| Commits | **NONE** |
| Writes confined to research folder | **YES** |
| Public Amazon access | bounded public-page fetches only; no login, no CAPTCHA bypass |

---

## 5. Remaining visible uncertainties (not resolved, by design)

- Supplier lead times, MOQ and prices — **unknown**.
- FBA fee and landed unit cost — **unknown**; contribution cannot be validated.
- Duty / AD-CVD — **cinnamon** HTS and scope unresolved; broker review pending.
- Ceylon **lot** COA with heavy-metal results — **not obtained**; the differentiation claim depends on it.
- Whether Pearl can pack finished units organically — **unconfirmed**.
- Whether Mogra itself must certify — **unconfirmed**.
