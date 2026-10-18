# V3 S7 §5.2 / §5.3 — Listing revisions + the ListingForge SEO hook

**Date:** 2026-10-18 · **Branch:** `feature/v3-simple-view` · **Status:** BUILT, tests green, local commit.

## What this closes

The V3 S7 Brand SEO Engine grew two pieces the plan already named:

- **§5.2 Listing revisions** — the newest revision of a listing is the only object
  SEO work targets; prior revisions stay read-only.
- **§5.3 ListingForge hook** — a listing's copy is scored against the brand's
  canonical SEO profile, deterministically.

It also closes a real gap: `shell_focus` advertised a `seo_check` tool in the
**Grow** focus, but no such tool existed. `tools_for_focus` silently filtered the
unknown name out, so the Grow prompt told the model to use a tool it could never
call. That name now resolves to a real, registered tool.

## Design rules honoured

- **Deterministic, never fabricated.** `seo_score.score_listing` computes plain
  keyword coverage of the profile's clusters across the listing's
  title / bullets / backend terms / description. It reports what it can prove:
  which terms matched and where, which are missing, prohibited-claim hits, and
  competitor-name mentions. It makes **no rank or volume claims**.
- **Honest absence.** If the profile has no keyword clusters there is no
  denominator, so the score is `None` — not a fake `0`.
- **Append-only.** A listing build/update APPENDS a revision; the revision number
  is monotonic per `(account_id, listing_key)`. Prior revisions are never
  mutated. `ds_listing_records` is left untouched — linkage is a new additive
  table, exactly as the plan required.
- **Tenant-scoped.** Every read and write is scoped to the account; a foreign
  listing/profile reports 404, never a leak.

## Pieces

| Piece | Where | What |
|---|---|---|
| Schema | `seo_schema.py` (`SEO_TABLES_SQL`) | Additive `ds_listing_revisions` with a unique `(account_id, listing_key, revision)` index. |
| Store | `data_layer.py` `DsListingRevisionsDB` (on `SeoContainer.revisions`) | `add_revision` (append-only, next number), `get`, `get_latest`, `list_revisions` (newest first), `list_latest` (one row per key). |
| Scoring | `seo_score.py` `score_listing` | Weighted coverage (head 3.0 / body 1.5); matched/where, missing, violations, competitor mentions, caveats. |
| Service | `seo_router.py` `/api/seo/listings*` | `GET /listings`, `GET/POST /listings/{key}/revisions`, `GET /listings/{key}/revisions/{v}`, `GET /listings/{key}` (latest). |
| Shell hook | `chat_tools.py` `seo_check` (Grow focus) | Scores the latest stored revision (`listing_key`/`asin`) or inline copy; returns an AG-UI card (score, matched/total, missing head terms, prohibited claims, competitor mentions). Honest errors when there is no profile or listing. |

## Evidence

```
python -m py_compile seo_router.py seo_score.py chat_tools.py data_layer.py   → PY OK
python -m pytest test_seo_listing.py                                          → 19 passed
python -m pytest test_seo_listing test_seo_profiles test_shell_modes \
                  test_chat_fork test_tool_gateway test_voicestudio_adapter    → 93 passed
seo_router.routes → /api/seo/listings · /listings/{key} ·
                    /listings/{key}/revisions (GET,POST) ·
                    /listings/{key}/revisions/{revision}
```

New suite `test_seo_listing.py` (19) covers: full/partial coverage, violations,
competitor mentions, `None` score without clusters, term placement; revision
monotonicity + immutability, JSON bullets round-trip, newest-first listing,
one-row-per-key `list_latest`, missing-key `ValueError`, tenant scoping; the
`seo_check` tool (latest revision, inline copy, and the three honest-error
paths); and that `seo_check` is now registered and present in the Grow focus.
Router tests cover append/read, `list_latest`, and 404 on a missing listing.

## Honest limits / what's next

- Scoring is coverage of **operator-authored** profile keywords. It cannot and
  does not predict rank, traffic, or volume.
- Remaining S7: the other cross-service hooks (Creative Studio / AdPilot /
  SocialPulse / SourceScout) and §5.4 (file-import measurement + proposed
  profile learning).
- Nothing was pushed; all work is local on `feature/v3-simple-view`.
