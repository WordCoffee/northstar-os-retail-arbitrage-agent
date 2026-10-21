# Printables Playbook — How to Actually Make and Sell Them

**Date:** 2026-10-21
**Scope:** Creating fixed-format digital printables for Etsy. No inventory, no shipping, ~95% margin.

---

## 1. What a printable is (and the three kinds)

A **printable** is a digital file the buyer prints at home. Etsy delivers it automatically; you upload once.

| Kind | What the buyer gets | Difficulty | Best for |
|---|---|---|---|
| **Fixed PDF** | A designed file, ready to print | Easy | Planners, checklists, trackers, wall art, games |
| **Editable template** | A Canva link they customize | Medium | Invitations, resumes, business cards |
| **Cut file** | SVG/PNG for Cricut | Medium | Crafters — different buyer, needs a machine |

**Start with fixed PDFs.** No third-party platform dependency, no licensing trap, and the buyer experience is one click.

---

## 2. The spec sheet — the numbers that actually matter

Get these right once and every future product is easy.

| Item | Value | Why |
|---|---|---|
| **Page size** | US Letter 8.5 × 11 in (216 × 279 mm) | 95% of US buyers. Add A4 as a second file for EU/UK. |
| **Resolution** | 300 DPI | 2550 × 3300 px if you work raster |
| **Color** | RGB | Home printers are RGB. CMYK only if you market to print shops. |
| **Safe margin** | 0.5 in | Nothing important within 0.25 in of the edge |
| **Bleed** | 0.125 in, only for full-bleed designs | Otherwise skip it |
| **Fonts** | Embedded in the PDF | A missing font destroys the page |
| **File size** | **20 MB max per file, 5 files max per listing** | Etsy hard limit |
| **Filename** | ≤70 characters | Etsy shows the buyer your filename — no `final_v3.pdf` |

**Etsy digital limits (verified):** 5 files per listing, 20 MB each, 100 MB total. ZIP counts as one file. No variations allowed on digital listings.

---

## 3. Three ways to build — pick by volume

### Path A — Canva (fastest, least control)
Blank design → US Letter → build → **Share → Download → PDF Print**.
- Free elements: you can sell the PDF.
- **Pro elements: you may only sell the design as a Canva template link, never as a PDF.** This is the single most common licensing mistake.
- Good for testing an idea in 2 hours. Bad for a catalog.

### Path B — Affinity Publisher (best quality per hour)
- Real master pages, text styles, PDF/X export.
- One-time purchase, no subscription.
- Export: PDF (press-ready), fonts embedded, no crop marks in the buyer file.
- Best for hero products and anything with lots of typography.

### Path C — your own pipeline (most leverage)
You already have this in the repo:

| Function | File | What it does |
|---|---|---|
| `render_pdf(build)` | `Northstar_backend/design_studio_print.py` | Native vector PDF via reportlab, no cairo dependency |
| `render_svg(build)` | same | Vector SVG from the same build spec |
| `prepress_check()` | same | Preflight: size, bleed, color checks |
| `build_from_template()` | same | Parametric layouts from a template catalog |
| `mockup_compositor.py` | same folder | Composite preview scenes for listing images |

A printable becomes a **JSON build spec** — rects, text, lines, ellipses — rendered to vector PDF. That is how you go from 5 SKUs to 50 without hand-placing each one.

**Recommendation:** Path C for the catalog, Path B for hero designs, Path A only to test demand fast.

---

## 4. Build your first product in half a day

**Step 1 — Write the promise in one sentence.**
Bad: "Garden planner printable."
Good: *"A 12-page seed-starting planner for zone 6 gardeners — what to sow, when, and where."*
One buyer, one job, one moment. Everything else follows from this.

**Step 2 — Outline the pages before you design anything.**

```
p1  Cover
p2  How to use this (1 page, short)
p3  Zone map / quick reference
p4  Seed inventory table
p5  Sowing calendar (12 months)
p6  Germination tracker
p7  Transplant schedule
p8  Spacing & depth cheat sheet
p9  Shopping list
p10 Harvest log
p11 Notes
p12 Bonus: seed packet labels
```

**Step 3 — Layout rules.** Three fonts maximum. Two colors plus black. One grid. Repeat the header, footer and page number on every page — consistency reads as quality and takes 10 minutes with master pages.

**Step 4 — QA before export.**

- [ ] Text is selectable (vector), not rasterized
- [ ] Fonts embedded
- [ ] Prints correctly at 100% / "actual size" — not "fit to page"
- [ ] Every page same orientation and size
- [ ] No placeholder text, no lorem ipsum
- [ ] Spell check
- [ ] Page numbers correct
- [ ] Test-printed on your own printer
- [ ] Opened in two viewers (Acrobat + Chrome)

**Step 5 — Package.**

```
your-product-README.pdf        ← how to print, license terms, thank you
your-product-US-Letter.pdf     ← the product
your-product-A4.pdf            ← EU/UK
your-product-Bonus.zip         ← extras (labels, stickers, spreadsheet)
```

That is 4 of your 5 allowed files.

---

## 5. Listing mechanics

1. **What type of item is it?** → Digital files → **Instant download**.
2. Upload files **at creation** — Etsy does not let you rename them afterward. Name them before you upload.
3. Add the **buyer note** (appears on their Downloads page).
4. **No shipping profile.** No variations — Etsy doesn't offer them on digital listings.
5. **Listing images: your own.** Etsy requires your own photos, not stock imagery. Lifestyle mockups are fine as *secondary* images; the first image must show what the buyer actually gets. 10 images is the standard.
6. **Price:** $7–19 for a single product, $19–29 for a bundle. Below $5 the fixed fees eat you; above $25 you need a strong brand story.

---

## 6. The legal and policy lines

| Rule | What it means for you |
|---|---|
| **Your design, not stock** | You can't resell a Canva template or a clipart set as-is. Combine elements into an original layout. |
| **Canva Pro content** | Template link only — **never** a flattened PDF. |
| **AI disclosure** | Etsy requires you to disclose AI-created or AI-assisted content in the listing. One plain sentence near the top. |
| **Trademarks** | No characters, logos, team names, song lyrics, or "inspired by" a brand. Instant takedown and a strike. |
| **Fonts** | Check the license allows embedding and commercial use. Many free fonts don't. |
| **PLR / resale rights** | Don't claim them unless you actually own and grant them. |

---

## 7. What sells vs. what drowns

**Sells:**
- A narrow job-to-be-done ("wedding seating chart for a 60-guest backyard wedding")
- Printable + editable versions of the same product, sold together
- Seasonal timing — list 6–8 weeks before the season, not during it
- Bundles of 3–5 related products at $19–29

**Drowns:**
- Generic "planner" or "wall art"
- Motivational quote prints
- "10,000 printables" mega-bundles
- AI output with no niche and no review pass

---

## 8. First week

| Day | Task |
|---|---|
| 1 | Pick the niche, write the one-sentence promise, outline pages |
| 2 | Build the product |
| 3 | Export, run the QA checklist, test print |
| 4 | Photography — flat lay on a desk, plus 3 mockup scenes |
| 5 | List 3 variations (colorways / sizes / bundle) |
| 6–7 | Build toward 10–15 listings; start Pinterest the same week |

Etsy's algorithm needs surface area. Three listings is invisible; fifteen is a shop.

---

*Specs verified against Etsy Help (digital listing limits, 5 files / 20 MB) and Canva's Content License Agreement. Layout and pricing guidance is from observed Etsy market data.*
