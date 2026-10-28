# 1.2 — A+ CONTENT GENERATION (TY SERVICE)
## Phase 2 research deliverable — REA program

**Date:** 2026-10-28
**Scope:** turn the A+ *specs* the repo already owns into a layout engine —
story arcs, module sequences, type scale, text budgets, mobile reflow — judged
against how real sellers are taught to build A+.
**Amazon contact:** none. No Amazon page, API or listing was requested by this
run. Amazon-published material appears only as it was surfaced by the search
provider (marked *secondhand*).
**Spend:** 0.

---

## 1. What already exists (and is correct)

`specRegistry.js` + `presets.js` already carry the module sizes with sources and
dates, and `APlus.jsx` already enforces the two rules that matter most:

- **alt text is required** on every image module (`APlus.jsx:20-25`) — and the
  file states plainly that alt text is *accessibility, not a ranking feature*.
- **the documented review rules** are surfaced as blocking/flag notes
  (`APlus.jsx:45-50`): < 2 MB, RGB only, ≥ 72 dpi, no animated GIF, images unique
  to A+, one brand logo max, Basic vs Premium module counts, Premium eligibility
  must be confirmed in A+ Content Manager.
- `IndexingRegister.jsx` keeps *indexing claims* in a separate register from
  layout, which is the right separation: A+ layout does not index.

**What is missing is not compliance. It is composition.** There is no data that
says "for this product type, use these modules in this order, with these text
budgets". `SectionWorkspace.jsx` renders whatever slots the operator picks.

---

## 2. How sellers are actually taught to do it (YouTube + seller sources)

| Source | Taught sequence / claim | Usable? |
|---|---|---|
| *Amazon Brand Story 101 — Why & How to Build an A+ Story* (7,387 views, 2024-02) | walk through the Brand Story modules, look at real examples, then "brand story tips"; claims Brand Story is the gate that unlocks Premium A+ | **yes** for module walkthrough; the Premium-gating claim is **REPORTED**, and the repo already flags eligibility as "confirm in A+ Content Manager, the studio does not assert eligibility" |
| *Premium A+ Content: The Module-by-Module Guide* (9,398 views, 2024-12) | "in 10 minutes you will learn exactly **which modules to use and which to ignore**" | **yes** — the premise is that Premium module inventory is larger than the set worth using |
| *How To Create A+ Content and Brand Story On Amazon in 2026* (2026-03) | step-by-step inside A+ Content Manager: pick content type → add modules → image/text → assign ASINs | **yes** — this is the correct *operator* sequence, and it is already what `SectionWorkspace` mirrors |
| *How To Create A+ Content On Amazon in 2022 | Step By Step* (119K views) | high-volume tutorial; the durable part is the module grid, not the UI clicks | partial |
| Seller-forum module guide | Brand Story has **4 modules**; "the 3 answers together cannot exceed 600 characters"; "should not have more than 2" modules in a Brand Story | **yes** — a concrete text budget and a counter-rule against filling every slot |
| *Complete Guide to A+ Content for Brand Owners* (Amazon-published PDF, **secondhand** via search) | navigation path, module-by-module fill order, "AI Ready" badge modules exist | **yes** for sequence; not re-fetched |

**Cross-source conclusion:** every source teaches *module selection and order*
first and design second. None teaches "fill every slot". The most-quoted failure
is a module set that is technically valid and compositionally wrong.

---

## 3. Arc catalogue (the missing data)

Each arc is an ordered module plan using **only** module ids that exist in
`presets.js`. Text budgets are characters per module.

### A1 — Problem → Solution → Proof (supplement / functional food)
| # | Module id | Size | Job | Text budget |
|---|---|---|---|---|
| 1 | `aplus-overlay-dark` | 970×300 | name the problem in one line | headline ≤ 90 |
| 2 | `aplus-four-text` | 4×200×200 | four benefits, one claim each | 4 × ≤ 90 |
| 3 | `aplus-comparison` | 150×300 | why this one vs the obvious alternative | headline + 3 rows |
| 4 | `aplus-four-highlights` | 4×400×400 | proof: certs, test, ingredient, sourcing | 4 × ≤ 60 |
| 5 | `brand-story-desktop` | 1464×625 | brand continuity | ≤ 600 total across the 3 answers |

### A2 — Hero-led lifestyle (premium only)
| # | Module id | Size | Job |
|---|---|---|---|
| 1 | `aplus-premium-full` | 1464×600 | one hero image, no baked text |
| 2 | `aplus-three-text` | 3×300×300 | three moments of use |
| 3 | `aplus-premium-hotspots` | 1464×600 | click-to-detail on the product |
| 4 | `brand-story-desktop` | 1464×625 | brand continuity |

### A3 — Comparison-led (competitive displacement)
| # | Module id | Size | Job |
|---|---|---|---|
| 1 | `aplus-overlay-light` | 970×300 | category frame |
| 2 | `aplus-premium-cmp2` | 300×225 | the comparison table, ours first |
| 3 | `aplus-four-text` | 4×200×200 | the four axes of difference |
| 4 | `brand-story-desktop` | 1464×625 | brand continuity |

### A4 — Ingredient / transparency-led
| # | Module id | Size | Job |
|---|---|---|---|
| 1 | `aplus-sidebar-main` + `aplus-sidebar-side` | 300×400 + 350×175 | pack shot + panel |
| 2 | `aplus-four-highlights` | 4×400×400 | sourcing / testing / dose / certification |
| 3 | `aplus-comparison` | 150×300 | vs a commodity alternative |
| 4 | `brand-story-desktop` | 1464×625 | brand continuity |

### A5 — Proof-first (reviews / third-party tests)
| # | Module id | Size | Job |
|---|---|---|---|
| 1 | `aplus-overlay-dark` | 970×300 | the claim, stated plainly |
| 2 | `aplus-four-text` | 4×200×200 | the four measurements behind it |
| 3 | `aplus-premium-cmp1` | 200×225 | specification table |
| 4 | `aplus-premium-carousel` | 1464×600 | rotate the evidence |
| 5 | `brand-story-desktop` | 1464×625 | brand continuity |

**Counter-rules built into the catalogue** (from §2): a Basic set is 4–5
modules, never the maximum the platform allows; Brand Story carries ≤ 2
modules; no arc opens with a comparison table (it presumes interest the reader
has not expressed yet).

---

## 4. Type scale and image treatment (implementable in SVG/PDF)

`design_studio_print.py` renders SVG + native PDF, and `SectionWorkspace` lays
out on the registry canvas. The rules below are therefore expressed as
**ratios of module width**, so one rule holds at every module size.

| Element | Rule | Why |
|---|---|---|
| Headline cap height | **3.0–4.5 % of module width** (970 px → 29–44 px) | survives the mobile reflow arithmetic in §5 |
| Body cap height | **1.6–2.2 % of module width** (970 px → 16–21 px) | ≥ 2× the 10 px OCR floor measured in 1.1 §6 |
| Baked-text floor | **≥ 2.5 % of module width** (any text drawn into the image) | see §5: anything smaller is unreadable after reflow |
| Measures | headline ≤ 2 lines, body ≤ 4 lines per module | a 5th line is a different module's job |
| Contrast | ≥ 4.5:1 for body, ≥ 3:1 for headline over an image, measured against the worst-case area under the text | WCAG 2.2 AA |
| Logo count | exactly 1 per set | repo rule already (`APlus.jsx:47`) |
| Image uniqueness | no image reused from the listing gallery | repo rule already (`APlus.jsx:47`) |
| Colour | one accent + neutral type; no gradient behind body text | gradient under text is the most common legibility failure in generated sets |
| Text-in-image | **avoid**; if unavoidable, the string must also exist as alt text and in the module body | keeps the set readable by screen readers and by the review |

---

## 5. Mobile reflow: the arithmetic nobody writes down

Amazon reflows a 1464 px premium module into a phone-width container. The exact
container width is **not published** (`UNVERIFIED`), so the rule must be
expressed as a ratio, not a pixel value:

- Assume the module is displayed at ~25 % of its native width on a phone
  (1464 px → ~366 px, a 4:1 downscale).
- A headline drawn at 3.0 % of module width (44 px) displays at **11 px**.
- A body line at 1.6 % (23 px) displays at **5.8 px** — below the 10 px OCR floor
  measured in 1.1 §6, i.e. below the floor at which even a perfect OCR engine
  reads it.
- Therefore: **text baked into an image must be ≥ 2.5 % of module width to clear
  the OCR floor after reflow; live text (rendered by the document, not the
  image) has no such constraint.**

That last line is the actual design decision: **put copy in text, not in the
image.** It also happens to be the accessibility decision, and the review-safety
decision.

`UNVERIFIED`: the 25 % figure is an assumption stated as an assumption. The
build step should replace it with the measured container width from a real
mobile render before hard-coding any threshold.

---

## 6. Review-failure modes (documented vs observed)

| Documented (repo already enforces) | Reported by sellers | Status |
|---|---|---|
| image < 2 MB, RGB, ≥ 72 dpi | — | enforced |
| alt text required | — | enforced |
| images unique to A+, 1 logo max | — | enforced |
| animated GIF prohibited | — | enforced |
| Basic vs Premium module counts | Premium eligibility requires Brand Story on all brand listings | **REPORTED** — repo already refuses to assert eligibility |
| — | "filling all 4 Brand Story modules looks ridiculous" | reported, adopted as a counter-rule (§3) |
| — | 3 Brand Story answers ≤ 600 chars total | reported, adopted as a budget (§3) |
| — | text baked into images fails legibility on mobile | **measured arithmetic**, §5 |

---

## 7. BUILD CANDIDATES

| id | component | change | evidence (report §) | effort | risk | gate |
|---|---|---|---|---|---|---|
| A1 | new `studio/engine/aplusArcs.js` | encode the 5 arcs as ordered module plans with per-module text budgets | §3 | 2 h | low | none |
| A2 | `SectionWorkspace.jsx` | offer arcs as a starting point ("compose this arc") instead of an empty slot grid | §2 conclusion | 3 h | medium; UI change in a shipped surface | none |
| A3 | type-scale tokens | headline 3.0–4.5 %, body 1.6–2.2 %, baked-text floor 2.5 % of module width | §4, §5 | 2 h | low | none |
| A4 | new lint in `compliance.js` | block baked text below 2.5 % of module width; warn on > 2-line headline; warn on > 1 logo | §5 | 2 h | low; needs font metrics from the renderer | none |
| A5 | `outputPacks` | emit the chosen arc + budgets with the set so a rebuild is reproducible | §3 | 1 h | low | none |
| A6 | `IndexingRegister` | add the "A+ layout does not index" note to the generated pack | existing repo stance | 30 min | none | none |

**Rejected:** scraping Amazon A+ pages for a corpus (gated, and §3's arcs are
already derivable from published seller teaching); asserting Premium A+
eligibility in the UI (repo already refuses, correctly).

## 8. UNVERIFIED

- The exact mobile container width used by Amazon's A+ reflow (§5 assumption).
- Premium A+ eligibility rules beyond "Brand Story published + approved content"
  — reported by sellers, not confirmed against an Amazon page in this run.
- The Amazon-published PDF's module list was seen **secondhand** through the
  search provider; it was not fetched. Treat its contents as corroboration only.
- No A+ set was rendered in this run. The arc catalogue is untested against a
  real render; A2 must be built behind a preview before it becomes the default.
