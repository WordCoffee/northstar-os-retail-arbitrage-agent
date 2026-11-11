# reference-review-backfill — the depth gap is an image-source limit, measured

Unit `reference-review-backfill`. Status: **blocked on a source**, not on work.
Rollback `rollback/pre-reference-backfill-20261111`.

## The gap

Cycle 20 deepened three categories and corrected its own claim: depth is *reviewed, usable*
images, not rows. After that, five categories held three rows and one or two usable pictures.
This unit took the three that a brief actually needs: `pet_product` 1, `small_appliance` 1,
`tool` 2.

## What was tried, and what the source said

| attempt | result |
|---|---|
| `--fetch --categories pet_product,small_appliance,tool` (default 800 px gate) | **+0 kept, 19 refused**; 29 of the refusals are `small 1024x683` — the short side, not the licence and not the topic |
| same, `--min-side 700` (the gate cycle 6 recorded) | `tool` +4 kept, `pet_product` +0, `small_appliance` +0 |
| same, `--min-side 800` again | `pet_product`/`tool` answered `HTTP 504 Gateway Timeout` |
| `size=large` added to the Openverse query | 504 on two of three categories; the one that answered returned 3466×1705 and 6000×4000 |
| plain query, no `size` | 200 OK, 240 results, dominantly 1024×683 |

**Openverse's free tier answers a product query with 1024×683 crops.** The licence filter is
doing its job (CC0/BY/BY-SA only), the topic gate is doing its job, and the pixel gate is
doing its job — the source simply does not have the pixels on the anonymous tier.

The `size=large` parameter was tried and **reverted**: it turns working queries into 504s, so
shipping it would trade a working fetch for a flaky one.

## The four rows that did get through were looked at, and refused

`tool` gained two rows the topic gate accepted on their tags. Both were opened and rejected:

| title | verdict | why |
|---|---|---|
| *Heating evenly…* | reject | a glassblowing class with a torch; not a hand tool |
| *Glass artwork at Tacoma Museum of Glass* | reject | a museum display case of glass ornaments |

Recorded in `ty/reference_review.json` (38 verdicts: 19 keep, 16 reject, 2 refuse, 1
reclassify). After the reviews, the honest table is unchanged where it matters:
`pet_product` 1, `small_appliance` 1, `tool` 2, and the other categories ≥3.

## What closes it

Either an **Openverse client key** (`OPENVERSE_CLIENT_KEY` in `.env`, free) so the
`size=large` filter is served, or your word that brand storefronts and design galleries may
be scraped as reference sources. Both are one line in `reports/ty/needs_you.md`; neither
blocks the rest of the queue.

## Tests

```
python -m pytest Northstar_backend/test_reference_coverage.py -q  -> 5 passed
python tools/reference_coverage.py --report                      -> regenerated
```
