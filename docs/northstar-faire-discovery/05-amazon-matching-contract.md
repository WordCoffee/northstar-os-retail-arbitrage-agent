# 05 — Amazon Matching Contract

Machine-readable: `amazon-match-schema.json`. Implementation: `faire_research/matching.py`.

## Match priority (strongest identifier first)

1. Exact GTIN/UPC/EAN.
2. Exact MPN + brand.
3. Exact model + brand.
4. Exact title, size, color, material and package quantity.
5. High-confidence fuzzy → **manual approval required**.

## Match-confidence classes

`EXACT_IDENTIFIER_MATCH`, `EXACT_ATTRIBUTE_MATCH`,
`PROBABLE_MATCH_REVIEW_REQUIRED`, `AMBIGUOUS`, `MISMATCH`, `INSUFFICIENT_DATA`.

Only the first two may advance automatically; exact attribute matches without
GTIN evidence still receive manual review before purchasing.

## Exact-match safety — all must agree

Brand, product identity, model/MPN where applicable, color, size, material where
important, unit count, number of items, pack quantity, included accessories,
manufacturer packaging, and UPC/GTIN or another authoritative identifier.

Reject or require manual review for: similar-looking products, different
sizes/colors/materials/models/generations, different pack quantities, different
included accessories, different country versions, different manufacturer
packaging, repackaged merchandise presented as manufacturer-packaged,
product-page ambiguity, variation misuse.

## Eligibility states

`ELIGIBLE_CONFIRMED`, `APPROVAL_REQUIRED`, `RESTRICTED`, `NOT_ELIGIBLE`,
`ELIGIBILITY_UNKNOWN`, `ELIGIBILITY_CHECK_UNAVAILABLE`.

**Do not** infer a product is ungated because other sellers offer it. **Do not**
infer T2 Holdings LLC may sell without a seller-account eligibility check.

## Evidence captured

ASIN, Amazon URL, marketplace, brand, title, manufacturer, model, MPN, GTIN,
item form, color, size, unit count, number of items, item package quantity,
product/package dimensions, item/package weight, category, selling price,
buy-box price, Amazon seller presence, FBA/FBM/total offer counts, review count,
rating, BSR, estimated monthly sales (approved providers only), price history,
listing age, variations, restricted/hazmat/meltable indicators, gating result,
evidence source, capture timestamp, confidence, staleness.

## Observed limitation (this session)

Automated title search produced matches with similarity 0.27–0.72. Per contract,
only exact-identifier/attribute matches advance; the rest route to `MATCH_REVIEW`.
