# 03 — Faire Discovery Contract

Machine-readable: `faire-discovery-schema.json`.

## Purpose

Normalise Faire-discovered brands and products into an org-scoped,
provenance-carrying research record. Faire is discovery only; wholesale values
are benchmark-only.

## Brand fields

name, Faire brand URL, website, legal/trading name, location, description,
categories, brand values/tags, "Not on Amazon" designation, marketplace
restrictions, resale restrictions, MAP policy, territory restrictions, minimum
advertised price, direct-wholesale availability, contact/wholesale-application
URL, evidence URL, capture timestamp.

## Product fields

title, Faire product URL, brand, SKU, MPN, UPC/EAN/GTIN, variant, color, size,
material, description, wholesale case price, wholesale unit price, case
quantity, inner-pack quantity, MOQ, opening-order minimum, reorder minimum,
suggested retail, shipping estimate, lead time, inventory status, product
weight, packaged shipping weight, product dimensions, packaged dimensions,
country of origin, compliance claims, fragility, hazmat indicators, expiration
indicators, manufacturer-created pack status, image URLs, evidence URL, capture
timestamp, provenance class.

## Rules

- **Do not** infer wholesale unit cost from a case price unless case quantity is verified.
- If wholesale price is visible only in an authenticated account, label
  `AUTHENTICATED_FAIRE_REFERENCE` and preserve the access timestamp.
- Never present Faire wholesale pricing as a compliant Amazon sourcing price — label
  `DISCOVERY_BENCHMARK_ONLY — AMAZON RESALE THROUGH FAIRE NOT AUTHORIZED`.
- `Not on Amazon` is captured but mapped to marketplace-policy **risk**, never opportunity.

## Discovery heuristics (configurable, not universal truths)

Small, lightweight, non-powered, low-risk compact goods: kitchen tools/gadgets,
organizers, cleaning/reusable accessories, small stationery/office, simple home
accessories. Heavily penalise/exclude: electrical, battery, liquids, aerosols,
flammables, chemicals, meltables, food, supplements, cosmetics, topicals,
medical, children's safety, baby feeding, sharp, glass/ceramic, regulated
claims, expiration-tracked, certification-heavy, counterfeitable. Never exclude
"because it is inconvenient" — record the reason and risk class.
