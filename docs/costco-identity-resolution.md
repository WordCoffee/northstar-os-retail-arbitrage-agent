# Costco Identity Resolution

## What a Costco item number is (and is not)

- **Costco item number** — Costco's internal source/catalog identifier. Stable
  for source lineage and refresh. **It is NOT a UPC, EAN, GTIN, MPN, or ASIN.**
- **UPC / EAN / GTIN** — the consumer product / retail-ready sellable-unit
  identifier. The strongest exact Amazon identity join.
- **MPN / manufacturer model** — the manufacturer's model/part number. Strong
  alternative when no UPC/GTIN is available (MPN + brand).
- **Amazon ASIN** — the Amazon listing identifier.

These identifiers are **not interchangeable**. The pipeline never treats the
Costco item number as a UPC/GTIN/MPN/ASIN.

## Identifier hierarchy

1. UPC / EAN / GTIN exact
2. MPN + brand
3. Brand + normalized title + exact pack/unit
4. Title/brand candidate only → manual review (never exact)

## Why identifiers are required

Broad title-based provider searches (SellerAmp) produce *leads*,
not resellable matches. Without a UPC/GTIN or MPN+brand, a Costco record cannot
be joined to an Amazon listing with enough certainty to compute defensible
economics. The first 17-candidate batch proved this: 0 exact matches, 0
qualified, because the Costco side lacked identifiers, weight, and dimensions.

## Tri-state / null-first rules

- Unknown UPC/GTIN/MPN **is not** an identifier.
- Unknown weight **is not** ≤ 3 lb.
- Unknown dimensions **are not** standard-size.
- Unknown split-pack status **is not** `approved_split`.
- Unknown pack count **is not** an exact pack match.
- Unknown brand **is not** automatically non-Kirkland.
- Missing enrichment data **is not** an error-free field.

## Identity readiness

A record is `identity_ready_for_provider_research` only when: non-Kirkland and
not disallowed; known brand; usable source cost + observed timestamp; exact
source pack/unit configuration; at least one strong identifier (UPC/EAN/GTIN OR
MPN+brand); weight/dimensions sufficient for the size rule (or an explicit
enrichment request obtains them); no unresolved product/variation conflict; and
split status is `intact_only` or `approved_split`.

Records without an identifier are routed to the **`identifier_resolution_required`**
queue (never guessed). A limited `probable_match_research` path exists only if
the operator explicitly enables it, and such candidates are never auto-qualified,
never purchase-authorized, never called exact, and remain `manual_review_required`.

## Commands

```
python -m costco_non_kirkland.cli audit-source-identity --run-id <id>
python -m costco_non_kirkland.cli identifier-resolution-queue --run-id <id> --build
python -m costco_non_kirkland.cli export-identity-readiness --run-id <id> --format csv --out ids.csv
```

## Sourcing disclaimer

Costco retail/online discovery does **not** establish invoice-ready sourcing.
No automatic purchase authorization exists. No direct Amazon browsing is used.
