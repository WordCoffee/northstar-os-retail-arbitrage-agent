---
name: competitor-profiling
description: Turn a competitor listing or product page into evidence, not impressions. Separates what was observed from what was inferred.
triggers: competitor, competition, compare, teardown, benchmark, pricing, reviews, market, category
---

# Competitor profiling

Read `product-marketing` first so the comparison is against our real positioning.

## Evidence ladder

Every statement you return is tagged:

| Tag | Meaning |
|---|---|
| `observed` | Literally on the page/listing we were given |
| `derived` | Arithmetic or direct consequence of observed values (price per oz, unit cost) |
| `inferred` | A judgement — positioning, target buyer, likely supplier strategy |
| `unknown` | The input did not contain it |

Never promote `inferred` to `observed` in a later sentence. That is how a guess becomes a "fact".

## What to extract

- Title structure: keyword order, differentiator, size/count placement.
- Price architecture: list price, coupon, subscribe-and-save, multipack ladder, price per unit.
- Bullet strategy: benefit labels used, proof types (specs vs testimonials vs badges).
- Image set: how many, what the first image proves, whether lifestyle or packshot leads.
- Review signal: rating, count, and the recurring complaint themes (not single reviews).
- Claims: certifications and health claims — flag any we cannot match with a document.

## What not to do

- Do not scrape behind a login, and do not use any browser path other than the approved
  controller.
- Do not mirror a competitor's copy. Extract the structure, write our own words.
- Do not treat a competitor's claim as true just because it is published.

## Output

One table of `field | competitor | us | gap | tag`, then at most three recommended moves, each
tied to an observed field. No essay.
