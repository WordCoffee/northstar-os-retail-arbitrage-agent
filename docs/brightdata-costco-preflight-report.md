# Bright Data Costco Enrichment — Preflight Report

_Offline preflight. Zero network calls. No credentials read or printed._

## Preflight summary

- Provider: **brightdata**
- Result: **provider_not_configured** (no source/scraper id set in the environment)
- Enabled: **false**
- Source/scraper id configured: **false** (checked names only:
  `NORTHSTAR_BRIGHTDATA_SOURCE_ID`, `BRIGHTDATA_COSTCO_SOURCE_ID`,
  `BRIGHTDATA_UNLOCKER_ZONE`)
- Credential env names checked (set/unset only; never values):
  `BRIGHTDATA_UNLOCKER_API_KEY`, `BRIGHTDATA_API_KEY`
- Sample size: **25**
- Known cost: **cost unknown; operator must confirm in Bright Data account**
- Network calls made: **0**

### Unsatisfied approval gates
- approved flag (`--approved`)
- `NORTHSTAR_ENRICHMENT_APPROVED=1`
- `NORTHSTAR_BRIGHT_DATA_ENABLED=1`
- source/scraper id configured
- `--max-items` set
- `--spend-cap` set
- manifest id present

The live command `run-brightdata-enrichment` fails closed (`requires_explicit_approval`)
unless every gate is satisfied. This preflight never invokes it.

## Why UPC/GTIN/MPN is the critical blocker

The 181 eligible Costco records have **zero** UPC/EAN/GTIN/MPN values. Without a
product identifier there is **no exact join** to an Amazon listing; the Costco
item number is an internal source key and is NOT an identifier. Every identity
decision therefore falls back to title similarity, which cannot establish exact
identity.

## Why title-only SellerAmp matching cannot create exact identity

The 17-candidate batch produced 17 plausible ASIN *leads* and **0** exact
matches: titles match, but pack counts, sizes, and variations differ and cannot
be proven equivalent. Title-only results must remain `manual_review_required`;
they can never be auto-qualified or purchase-authorized.

## Why unknown weight/dimensions cannot pass the 3 lb / non-bulky policy

Weight coverage is **1 of 181**; dimensions are **0 of 181**. Per the null-first
rule, **unknown weight is not ≤ 3 lb** and **unknown dimensions are not
standard-size**. With no verified physical data, no candidate can pass the size
rule, so the correct result is 0 identity-ready products.

## Why a 25-item pilot is lower risk than a full-catalog run

A 25-item schema-validation pilot answers the only question that matters first —
*does Bright Data actually return GTIN/MPN/weight/dimensions for our Costco
records?* — at a bounded, known cost, before spending on the remaining 156
records. A full-catalog run would be a blind spend against unverified field
coverage.

## Requested fields

costco item number, brand, title, description, category, price, availability,
UPC/EAN/GTIN, MPN/model, pack/count, net weight, shipping weight, dimensions,
specifications, images, observed timestamp, source URL/reference.

### Mandatory fields by purpose
- **identifier_resolution**: upc, ean, gtin, mpn, brand
- **weight_size_validation**: net_weight, shipping_weight, package_length, package_width, package_height
- **pack_validation**: outer_pack_count, inner_unit_count, unit_count, unit_measure
- **exact_provider_match**: brand, upc/ean/gtin, mpn, title
- **economics**: costco_price, shipping_weight, unit_count

### Optional fields
description, category_path, manufacturer, manufacturer_model, availability,
image_reference, specification_reference, observed_at, source_url

### Unknown / untested fields
**All requested fields** — the Bright Data schema has not been tested against
this account/source. Field availability is a marketing claim until proven on an
approved sample.

## Marketing claims vs proven coverage

Bright Data's Costco scraper marketing lists URL, Item id, Variant id, GTIN,
MPN, title, description, category, and other structured data. **This is not
proof** that this account's configured source returns those fields for these
items, in this country, at this scraper version. Coverage is **unknown** until a
validated sample is imported as `provider_reported`.

## Local fixtures

Any historical Bright Data / Costco fixtures found in `data/costco-discovery-runs`
are **historical references, not current live evidence**.

## Bright Data account details the operator must verify manually

1. Whether a Costco product-data scraper/dataset is enabled.
2. Its exact source/scraper/dataset ID.
3. The output fields available for a Costco product-detail request.
4. Whether UPC, EAN, GTIN, MPN/model, net weight, shipping weight, dimensions,
   pack/count, brand, specifications, and Costco item number are actually returned.
5. Expected cost/credits for 25 product-detail records, including any minimum job cost.
6. The spend cap you authorize for the pilot.

## Reconciliation note (count deltas)

- Earlier provisional result: **254 eligible / 72 clear-pack / 20 provisional-batch**
  (looser: eligibility = non-Kirkland + non-disallowed; provisional = brand + cost + pack).
- Current identity-readiness audit: **181 eligible** (same eligibility rule, after
  the tightened disallowed filter re-run) with **17 clear-pack** and **0 identity-ready**
  under the **stricter identity-readiness definition** (requires a strong
  identifier + physical data + observed timestamp, not just brand/cost/pack).
- The delta is the stronger identity requirement plus the expanded disallowed-class
  keyword set — not a data loss.

## Disclaimer

Costco retail discovery does not establish invoice-ready sourcing. Imported
snapshots are not live source truth. No automatic purchase authorization exists.
No direct Amazon browsing is used. No browser automation is used in this phase.
