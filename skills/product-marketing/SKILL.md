---
name: product-marketing
description: Read this first for any listing, ad, packaging copy or brand task. It defines the only facts Northstar may claim and how to handle missing ones.
triggers: brand, product, listing, title, bullets, description, ad, campaign, packaging, label, claim, positioning, audience, tone
always: true
---

# Product marketing — the base skill

Every other skill reads this one first. It exists so that copy, images and ads all agree about
what the product **is**, and so that no step invents a fact to fill a gap.

## 1. Facts come from the operator, not from you

| Fact class | Source of truth | If missing |
|---|---|---|
| Brand name, legal entity | operator / brand record | ask, do not guess |
| Product name, variant, size, count | operator / SKU record | ask |
| Ingredients, materials, specs | operator / supplier document | ask, never infer from a similar product |
| Certifications (organic, kosher, FDA, non-GMO) | certificate on file | **omit** — an unverified certification is a legal exposure |
| Price, availability, shipping claims | live system of record | omit |
| Claims about health, safety, performance | approved claims list | omit and flag |

A gap is a legitimate output. `missing_evidence` is a better answer than a confident invention.

## 2. Audience and positioning

Before writing, state in one line: **who buys this, what job it does, what they compare it to.**
If the operator has not supplied that, derive it from the product category — and say that you
derived it. Never silently swap a premium positioning for a value one, or vice versa.

## 3. Claims discipline

- Describe what the product **is** and **does** in observable terms. Avoid superlatives that
  cannot be evidenced ("best", "#1", "guaranteed", "miracle", "cure").
- No medical, therapeutic or safety claims unless the approved claims list contains them
  verbatim.
- No comparative claims against a named competitor.
- No urgency or scarcity that the operator has not confirmed is real.
- When a claim is borderline, keep the copy and add a warning rather than deleting the value.

## 4. Voice

Match the operator's stated brand voice. When none is stated, default to plain, specific and
concrete: short sentences, real nouns, no stacked adjectives. The same voice applies across
listing copy, ad copy and packaging text — inconsistency between them reads as a different brand.

## 5. Output discipline

- Return exactly the structure the calling task asked for. No preamble, no markdown fences
  unless requested.
- Never present a draft as published, live, approved or uploaded.
- When you used a skill, say which one in a single short line at the end of the response.
