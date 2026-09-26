# 06 — Pack and Case Normalization

Machine-readable: `pack-normalization-schema.json`. Implementation:
`faire_research/matching.py` (`pack_configuration`, `case_break_allowed`).

## Classification

`WHOLESALE_SHIPPING_CASE`, `MANUFACTURER_SINGLE_UNITS_INSIDE_CASE`,
`MANUFACTURER_MULTIPACK`, `SELLER_CREATED_MULTIPACK`,
`BUNDLE_OF_DIFFERENT_PRODUCTS`, `DISPLAY_PACK`, `INNER_PACK`,
`PACK_CONFIGURATION_UNKNOWN`.

Unresolved pack configuration is a hard disqualifier (`pack_mismatch_unresolved`).

## Case-break single opportunity — only if ALL hold

Each interior unit is complete/retail-ready; corresponds exactly to the Amazon
single-unit ASIN; carries correct consumer-facing label and identity; has
required warnings/instructions; is not marked "not for individual sale"; does
not violate supplier/brand terms; needs no sealed outer packaging for compliance;
is not damaged/materially altered by separation; meets Amazon condition/packaging
requirements; and the direct supplier permits Amazon resale.

`case_break_allowed(...)` returns `(allowed, failed_conditions)`.

## Multipack opportunity

Only when it matches an existing Amazon multipack ASIN exactly, **or** a
compliant new multipack can be created with an appropriate unique identifier and
all current Amazon requirements, **and** the brand permits the configuration,
**and** packaging accurately represents quantity, **and** the detail page states
pack quantity.

- Do **not** use a single-unit UPC to identify a multipack.
- Do **not** match a case of 12 to an Amazon pack of 6 without proving two
  independently compliant packs of 6.
- Do **not** assume seller-created multipacks are permitted for every brand.
- Do **not** auto-recommend creating a new ASIN.

## Captured

supplier case quantity, inner quantity, retail-ready unit count, Amazon unit
count, Amazon item package quantity, wholesale cost per case, landed cost per
case, landed cost per retail-ready unit, Amazon sale price per sellable unit,
sellable units obtainable per case, residual/unusable units, repackaging and
labeling requirements, new UPC required, brand permission required, case-break
status, pack-match status, manual review reason.
