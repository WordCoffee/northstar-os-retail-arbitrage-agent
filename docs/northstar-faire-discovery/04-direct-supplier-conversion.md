# 04 — Direct Supplier Conversion

For every promising Faire-discovered brand, research whether a **separate direct
wholesale route** exists. This is the only path by which a Faire-discovered
product may become a sourcing candidate.

## Capture per brand

Official website, direct-wholesale application, authorized distributor,
wholesale portal, Faire-only status, marketplace policy, Amazon permitted
(YES/NO/CONDITIONAL/UNKNOWN), written authorization required, invoice
availability, MOQ, opening minimum, payment terms, case quantities, direct price
availability, distributor price availability, supplier legitimacy evidence,
contact required, last verified date.

## Operator review question set (no auto-contact)

The workflow creates an operator-review task; it **never** contacts brands.

- Do you authorize approved wholesale accounts to resell your products on Amazon.com?
- Can you provide written marketplace authorization?
- Do you sell directly, or through an authorized distributor?
- Will invoices show your legal business identity, our business identity, product descriptions, and quantities?
- Are any products or ASINs excluded?
- Do you enforce MAP?
- Do you already have an exclusive Amazon seller?
- Are seller-created multipacks or bundles permitted?
- Are product images, trademarks, and listing content authorized for seller use?
- What are opening and reorder minimums, lead times and replenishment limits?

## Gate

No candidate can become `SOURCE_READY` until these questions are resolved with
evidence. `can_be_source_ready()` requires `direct_supplier_verified` and no
hard disqualifiers; `can_be_purchase_ready()` additionally requires
`eligibility == ELIGIBLE_CONFIRMED` and `brand_permission == YES`.
