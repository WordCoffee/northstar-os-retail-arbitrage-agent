# Block 1 — prompt-only, measured from the artefacts on disk

Artefacts: `renders/heldout_prompt_only8`. Scored with the current instrument (`tools/seller_tester/scorers.py`). **No bar and no weight was changed.**

**n 12 · pass 12 · mean 98.3** (per-mode row; not a blended headline).

## Per-check table

`P` pass · `F` fail · `–` not applicable to this brief (recorded as skipped, with a reason)

| brief | situation | score | passed | dimensions | aspect | background | subject_fill | alpha_matte | file_size | text_free | reference_subject |
|---|---|---|---|---|---|---|---|---|---|---|---|
| PO-001 | white_background_main | 100.0 | yes | P | P | P | P | P | P | P | – |
| PO-002 | lifestyle | 100.0 | yes | P | P | – | – | – | P | – | – |
| PO-003 | scale_reference | 100.0 | yes | P | P | P | P | P | P | P | – |
| PO-004 | bundle_multipack | 100.0 | yes | P | P | P | P | P | P | P | – |
| PO-005 | background_swap | 100.0 | yes | P | P | P | P | P | P | P | – |
| PO-006 | series_consistency | 100.0 | yes | P | P | P | P | P | P | P | – |
| PO-007 | infographic | 100.0 | yes | P | P | – | – | – | P | P | – |
| PO-008 | packaging_mockup | 100.0 | yes | P | P | – | – | – | P | – | – |
| PO-009 | white_background_main | 100.0 | yes | P | P | P | P | P | P | P | – |
| PO-010 | lifestyle | 100.0 | yes | P | P | – | – | – | P | – | – |
| PO-011 | scale_reference | 100.0 | yes | P | P | P | P | P | P | P | – |
| PO-012 | bundle_multipack | 80.0 | yes | P | P | P | F | P | P | P | – |

## Which checks fail, and on how many briefs

| check | briefs failing |
|---|---|
| `dimensions` | 0 |
| `aspect` | 0 |
| `background` | 0 |
| `subject_fill` | 1 |
| `alpha_matte` | 0 |
| `file_size` | 0 |
| `text_free` | 0 |
| `reference_subject` | 0 |

## Details for every non-passing cell

| brief | check | measurement |
|---|---|---|
| PO-012 | `subject_fill` | subject fill 24.8% vs 25.0-85.0% (distance > 20) |

· = check not run for this brief (a composite-only check on a full generation). – = recorded as not applicable.

