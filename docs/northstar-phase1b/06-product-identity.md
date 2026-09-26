# 06 — Product Identity (implemented)

## Canonical model (owner decision 2)

- `product_id` — immutable UUID, the only durable product key.
- Amazon uniqueness — `(marketplace_id, asin)`, enforced by resolution logic (multiple
  matches → `identity_conflict`, never merged).
- Identifiers: ASIN (uppercase, `^[0-9A-Z]{10}$`), UPC/EAN/GTIN (digit-normalized),
  MPN (raw). Raw + normalized both stored.
- Pack config, variation relationships, aliases, unresolved candidates, identity
  conflicts all modeled (`foundation/models.py`).

## Resolution service (`foundation/identity.py:IdentityResolver.submit`)

Returns exactly one of the owner-specified outcomes:

| Outcome | Trigger |
|---|---|
| `existing_product` | one product matches `(marketplace_id, asin)` |
| `new_product` | valid ASIN, no match, no ambiguity |
| `unresolved_candidate` | invalid ASIN, or no ASIN provided |
| `identity_conflict` | >1 product shares `(marketplace_id, asin)` |
| `possible_duplicate` | new ASIN shares a UPC/EAN/GTIN with an existing product |
| `pack_review_required` | `pack_ambiguous=true` |
| `variation_review_required` | `variation_family_ref` present |

**Ambiguous identities are never silently merged** — every ambiguity produces a
candidate or conflict row (verified by tests: `test_cross_identifier_duplicate_is_possible_duplicate_not_merge`,
`test_ambiguous_pack_requires_review_not_merge`).

## Catalog ownership (owner decision 2)

- Provider adapters do NOT create canonical products. They submit `IdentitySubmission`
  (candidate identifiers/observations); the Catalog resolver decides.
- Providers may submit candidate identifiers, observations, source records, and identity
  resolution requests.

## Migration mapping

The four existing stores map onto this model per `03-product-identity-and-migration.md`
of the Phase 1A package; the Phase 1B dry-run tool reports the reconciliation (see `14`).

## Evidence

- `foundation/identity.py`
- `foundation/tests/test_identity.py` (9 tests)