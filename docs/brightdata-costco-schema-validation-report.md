# Bright Data Costco — Live Schema-Validation Report (3-item)

- Collector: `gd_mkcbmac44j178pook` ("Costco products — Collect by URL")
- Snapshot id: `sd_mukcmeto8wwhj6ei3`
- Submitted: 2026-09-27T21:46:42Z · final status `ready`
- Network calls made: 9 (1 trigger, 7 polls, 1 download)
- Raw response: `Northstar_backend/data/brightdata-costco/collector-sd_mukcmeto8wwhj6ei3.json`
- Raw SHA-256: `e2ec6874da1d4d433dea4ed122b94dcd841a13b133823fe108ddfc8dea800bd7`

## Delivery

| Input URL | returned? | item_id | errors |
|---|---|---|---|
| `.product.986654.html` | yes | 986654 | none |
| `.product.1884230.html` | yes | 4000315194 | none |
| `.product.1900871.html` | yes | 4000329191 | none |

3 of 3 returned; **0 errors**.

## Item mapping (returned item_id vs local Costco item number)

| local item number | returned item_id | match |
|---|---|---|
| 986654 | 986654 | **yes** |
| 1884230 | 4000315194 | **no** (legacy → canonical id) |
| 1900871 | 4000329191 | **no** (legacy → canonical id) |

**Finding:** the returned `item_id` is the *current canonical* Costco item id; the
local item number is a legacy id. Records were therefore keyed back to local
source products by the **submitted URL** (all 3 matched), not by item number.

## Identifier coverage

| record | gtin | mpn | capture_status | format |
|---|---|---|---|---|
| 986654 (Unitex) | **none** | none | field_not_returned | n/a |
| 4000315194 (VOLT) | `842032131990` | none | captured | 12-digit (valid GTIN-12) |
| 4000329191 (Homedics) | `031262114518` | none | captured | 12-digit, leading zero preserved (string) |

- **GTIN coverage: 2 of 3** (usable). **MPN coverage: 0 of 3.**
- No identifier conflicts. Leading-zero GTIN preserved (returned as string).
- Unitex returned **no** GTIN/MPN.

## Product identity

| record | returned title | brand | variant | price | local price |
|---|---|---|---|---|---|
| Unitex | *(empty)* | none at top level (specifications Brand=Unitex) | none | $22.99 | $22.99 |
| VOLT | "VOLT Premium Solid Brass Outdoor Solar Path Lights, 2-pack" | VOLT | listing_has_variations=false | $99.99 | $99.99 |
| Homedics | "Homedics Infrared & Red Light Pain Therapy Wrap" | Homedics | listing_has_variations=false | $49.99 | $49.99 |

**Findings:** prices match local for all three. `brand` is missing at top level
for Unitex (present only under `specifications` → requires specs parsing). No
variations on any record (`variant_id`/`variants` null).

## Pack interpretation

- Unitex `specifications` includes `Quantity: 52 Count(s)` → **supports** the
  local 52-count pack.
- VOLT title states "2-pack" → **supports** the local 2 Pack(s); `specifications`
  adds `Dimensions: W x D x H = 7.5 in. x 8.7 in. x 16 in.`
- Homedics: no pack count in title/specifications (local 1 Pack(s)).

`specifications` is a `[{title,value}]` list and does carry pack/dimension text
where Costco exposes it, but it is **not normalized**.

## Data quality

- Top-level `brand` null for Unitex (in `specifications` only).
- `title` empty for Unitex.
- `gtin` is a string (safe); no malformed values seen.
- No top-level weight/dimension fields; dimensions appear only inside
  `specifications` (VOLT).
- `item_id` ≠ local item number for 2/3 (expected legacy→canonical redirect).
- Unexpected/extra fields returned: `reviews`, `related_products`,
  `return_policy`, `seller_tos`, `seller_privacy_policy`, `target_countries`,
  `variant_dict`. Harmless; not used.

## Physical data (explicit)

**Weight and package dimensions remain UNAVAILABLE as first-class fields.** This
collector does not return net weight, shipping weight, or package dimensions.
Dimensions appear only incidentally inside `specifications` for some items. Per
policy, **unknown weight is NOT ≤ 3 lb** and **unknown dimensions are NOT
standard-size**; these records **cannot** satisfy the physical requirement from
this source alone.

## Queue impact (after import)

- Eligible records: **181**
- Enrichment records merged: **3** (2 unique item numbers; 1900871 has a duplicate source row)
- Identifier coverage (merged): GTIN **3 records / 2 unique**, MPN 0, any strong identifier **3**
- **identity_ready: 0** (weight still unknown)
- identifier_present_physical_pending: **3**
- **identifier_resolution_required: 178** (down from 181)
- manual-review: unchanged

## Cost

- Free credits before: **3,913** (operator-reported)
- Credits after: **not returned by the API response — operator should confirm in the Bright Data account**
- Estimated usage for 3 delivered records: **≤ 3 × $0.0015 ≈ $0.0045** (well under 25 credits)
- **Paid balance used: 0** (free credits only; no funds added; no auto-recharge)

## Provenance

Collector `gd_mkcbmac44j178pook`; source URLs recorded; collection timestamp
2026-09-27T21:46Z; snapshot `sd_mukcmeto8wwhj6ei3`; raw-response SHA-256 recorded;
each enrichment record carries `provider_name`, `provider_snapshot_id`,
`snapshot_sha256`, `captured_at`, `ingested_at`, `field_capture_status`.

## Not authorized / not performed

No other Costco URLs; no 25-item pilot; no full-catalog run; no
ChromeControl/browser automation; no SellerAmp/SellerSprite; no Amazon.com
navigation; no purchase/account/billing/subscription action.
