# Bulk improvement pass — 2026-10-22

## First, the honest number

**10,000 verified improvements cannot be fabricated in one pass.** A knowledge
atom is a claim with a source and a date; inventing thousands would poison the
pack and make Bojo confidently wrong. So this pass delivered the machine that
compounds toward that number, plus the largest honest increment available today.

| what | count |
|---|---|
| knowledge atoms installed | **96** (56 new this pass) |
| concrete improvements queued | **1,353** |
| golden checks | **118** (96 knowledge-covered) |
| rollback point | `snapshot/pre-bulk` @ `eb3a3e2` |

## Installed now

56 new atoms, 7 per domain, imported through the same linter the loop uses:

| domain | atoms |
|---|---|
| listing | 23 |
| ads-amazon | 19 |
| aplus | 11 |
| ads-google-bing | 9 |
| brand-store | 9 |
| creative | 9 |
| creator-connections | 8 |
| reseller | 8 |
| **total** | **96** |

Examples of what landed:
- `ads-amazon.budget.scale-one-lever` — raise budget first when capped; never
  change bid and budget together.
- `aplus.images.text-size` — keep image text readable on a phone; never bake body
  copy into an image.
- `reseller.hazmat.precheck` — check restrictions before buying; restricted goods
  get stranded at the warehouse.
- `creative.label.composite` — composite label text as a layer; never let the
  image model render it.

Every atom keeps its source, effective date, confidence and a paired **don't**,
and is marked `needs_verification: true` until checked against Seller Central.
Coverage is unchanged at **96/96 = 100 %**.

## Found now — 1,353 queued improvements

| source | items |
|---|---|
| 500-item register | 500 |
| Bojo 100-item register | 100 |
| repository scan | 753 |
| **total** | **1,353** |

The scan is high-signal only, one finding per line:

| finding | count |
|---|---|
| TODO / FIXME / HACK | 253 |
| silenced exceptions (`except …: pass`) | 222 |
| `raise NotImplementedError` | 241 |
| skipped / xfail tests | 17 |
| hardcoded loopback URLs in the UI | 20 |

Queue: `state/improvement/product_queue.jsonl` (regenerable, git-ignored), each
row `{id, source, area, title, priority, status}`.

## Machinery shipped

| tool | job |
|---|---|
| `tools/import_facts.py` | pipe-delimited facts → validated, deduped atoms (`--dry-run`) |
| `tools/seed_improvement_queue.py` | the two registers → prioritised queue |
| `tools/mine_improvements.py` | repository scan → queue |

All three are idempotent and safe to re-run; the importer rejects duplicates and
near-duplicates (≥ 0.9 similarity) rather than inflating the count.

## How this reaches ten thousand

- **Knowledge:** the nightly cycle takes up to 5 gaps and promotes only what
  closes one. At 3 promotions a night that is ~1,000 atoms a year, each with
  evidence.
- **Product:** 1,353 queued items, worked top-down in build sessions.
- The queue never runs dry: the scanner re-runs, the registers grow, and operator
  ratings add gaps every day.

## Rollback

- Snapshot `snapshot/pre-bulk` (commit `eb3a3e2`), with both databases copied to
  `backups/rollback/pre-bulk`.
- Every atom lives in `knowledge/<domain>/atoms.json`; reverting one pass is
  `git checkout -- knowledge/`.
- The queue is a separate ignored file — deleting it changes nothing else.

## Gates

- 25 tests green for the importer + engine (`test_import_facts`, `test_cie`).
- Coverage 100 %, zero gaps after import.
- UI and API left running from the launch pass.
