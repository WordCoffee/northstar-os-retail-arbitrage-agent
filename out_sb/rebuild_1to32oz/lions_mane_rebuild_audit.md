# Rebuild audit — old 4.0–32.0 oz rule → new 1.0–32.0 oz rule

- Old rule: `MIN_OZ = 4.0, MAX_OZ = 32.0` in `lions_mane_sb.py` (title gate line 196, text gate line 292, visual gate lines 511/530) and `lions_mane_pull.py` line 50.
- New rule: 1.0–32.0 oz applied ONLY inside the rebuild script (`rebuild_1to32oz.py` sets `MIN_OZ = 1.0` at runtime). Original scripts and raw outputs are unchanged (hash-verified).

## Old verdict → new status (all 676 ASINs)

| old \ new | qualified (clean+flagged) | review required (incl. ambiguous weight) | excluded |
|---|---|---|---|
| PASS | 13 | 0 | 0 |
| REVIEW | 11 | 3 | 0 |
| REJECTED | 35 | 15 | 599 |
| UNKNOWN | 0 | 0 | 0 |

_Note: 'review required' counts here include market rows with review status and the weight-ambiguous row (counted once per ASIN in the union view; the market CSV contains 76 rows, plus 1 weight-only review row = 77 non-excluded ASINs)._

## Records reclassified because the 4 oz floor became 1 oz (26)

| ASIN | old verdict / reason | old size | new status (market / clean) | normalized oz | note |
|---|---|---|---|---|---|
| B00OBRMFBU | REJECTED: size 3.5oz outside 4.0-32.0 | 3.5 | review_required / review_required | 3.5 | title size re-evaluated |
| B01DKZZFCE | REJECTED: size 2.35oz outside 4.0-32.0 | 2.35 | qualified_flagged / excluded | 2.12 | title size re-evaluated |
| B077HH98NC | REJECTED: vision: label mentions extract/mycelium; vision: label weight 2.12oz o | 2.12 | qualified_flagged / excluded | 2.12 | label weight re-evaluated |
| B07K7YZZ1N | REJECTED: vision: label mentions extract/mycelium; vision: label weight 1.76oz o | 1.76 | qualified_flagged / excluded | 1.76 | label weight re-evaluated |
| B07MVRLJ91 | REJECTED: size 3.53oz outside 4.0-32.0 | 3.53 | qualified_flagged / excluded | 3.53 | title size re-evaluated |
| B07YXFTZGW | REJECTED: size 3.53oz outside 4.0-32.0 | 3.53 | qualified_flagged / excluded | 2.12 | title size re-evaluated |
| B089XNB2GS | REJECTED: size 3.5oz outside 4.0-32.0 | 3.5 | review_required / review_required | 3.5 | title size re-evaluated |
| B08HGXP9F3 | REJECTED: size 3.5oz outside 4.0-32.0 | 3.5 | review_required / review_required | 3.5 | title size re-evaluated |
| B08KHR7JMV | REJECTED: size 3.5oz outside 4.0-32.0 | 3.5 | review_required / review_required | 3.5 | title size re-evaluated |
| B08MB3JFR3 | REJECTED: vision: label weight 1.76oz outside 4.0-32.0 | 1.76 | qualified_flagged / excluded | 1.76 | label weight re-evaluated |
| B09C558Q7L | REJECTED: size 3.53oz outside 4.0-32.0 | 3.53 | review_required / review_required | 3.53 | title size re-evaluated |
| B09TFZP99N | REJECTED: size 3.5oz outside 4.0-32.0 | 3.5 | review_required / review_required | 3.5 | title size re-evaluated |
| B0C777FSW9 | REJECTED: vision: label weight 3.17oz outside 4.0-32.0 | 3.17 | qualified_clean / clean_comparable | 3.17 | label weight re-evaluated |
| B0C7LVHYJ5 | REJECTED: size 3.5oz outside 4.0-32.0 | 3.5 | review_required / review_required | 3.5 | title size re-evaluated |
| B0CJT97VB1 | REJECTED: size 3.5oz outside 4.0-32.0 | 3.5 | review_required / review_required | 3.5 | title size re-evaluated |
| B0CQKGG8N4 | REJECTED: vision: label weight 2.12oz outside 4.0-32.0 | 2.12 | qualified_clean / clean_comparable | 2.12 | label weight re-evaluated |
| B0CR6VKLLH | REJECTED: size 2.12oz outside 4.0-32.0 | 2.12 | review_required / review_required | 2.12 | title size re-evaluated |
| B0CS5X16HD | REJECTED: size 2.12oz outside 4.0-32.0 | 2.12 | review_required / review_required | 2.12 | title size re-evaluated |
| B0DM7GF7ZD | REJECTED: size 3.53oz outside 4.0-32.0 | 3.53 | review_required / review_required | 3.53 | title size re-evaluated |
| B0F6M3TD5R | REJECTED: size 3.7oz outside 4.0-32.0 | 3.7 | review_required / review_required | 3.7 | title size re-evaluated |
| B0F84FVWR3 | REJECTED: size 3.17oz outside 4.0-32.0 | 3.17 | review_required / review_required | 3.17 | title size re-evaluated |
| B0FFDQ5KYV | REJECTED: vision: label weight 2.12oz outside 4.0-32.0 | 2.12 | qualified_flagged / excluded | 2.12 | label weight re-evaluated |
| B0FM3R9DFP | REJECTED: size 3.5oz outside 4.0-32.0 | 3.5 | review_required / review_required | 3.5 | title size re-evaluated |
| B0FRLNJHG3 | REJECTED: size 3.5oz outside 4.0-32.0 | 3.5 | review_required / review_required | 7.0 | title size re-evaluated |
| B0FY71CYK8 | REJECTED: size 2.82oz outside 4.0-32.0 | 2.82 | qualified_clean / clean_comparable | 2.82 | title size re-evaluated |
| B0GQ6R43K6 | REJECTED: vision: label weight 2.12oz outside 4.0-32.0 | 2.12 | qualified_clean / clean_comparable | 4.24 | label weight re-evaluated |

## What stayed excluded and why (size changes did not rescue them)
- Records below 1.0 oz by best evidence (e.g. vision label ~0.25–0.88 oz) or above 32 oz remain excluded.
- Records whose only cached evidence fails other rules (not LM, named blends, non-powder form, no organic evidence, pet products, additional label ingredients) remain excluded regardless of size.
- Title-only records with no powder wording (e.g. 'Dried Whole', 'sliced', 'blends') remain excluded with evidence-gap reasons; they could only qualify after enrichment (details + label vision), which was not performed (no paid/provider calls).

## Extracts, mycelium, blends under the widened market lens
- Extract/myc/full-spectrum wording: market-lens includable with explicit flags (`extract_flag`, `mycelium_flag`), clean lens excluded unless resolved.
- Verified additional ingredients on the LABEL (e.g. pterostilbene, collagen) or named multi-species blends remain excluded: these are different products, not LM powder.

## Method notes
- Weight normalization: label net weight (vision) > title/item-weight text; multipacks = label per-unit × unit count; conflicts route to review; serving-size readings never become net weight.
- BSR model formulas were verified present in `lions_mane_sb.py` BSR_MODEL (H&H 5.50/0.70; Grocery 5.45/0.69; default 5.47/0.70) and are labelled estimates in every output.
- Raw evidence read-only; sha256 manifest: `raw_hash_manifest.json`.