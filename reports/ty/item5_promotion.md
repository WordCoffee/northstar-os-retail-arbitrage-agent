# Promotion record — 2026-11-09

Two promotions today, and one deliberate refusal. This file is the record the owner reads instead of
a chat log.

## Promoted to `main` (code only, all three gates green)

Candidate: `staging-candidate/20261109-1811` at `3f002e0c`.
Full suite on that candidate: **7329 passed, 0 failed, 117 skipped, 2 xfailed** in 17 m 51 s
(`reports/ty/_fullsuite_candidate8_20261109.txt`).
Verifier gate: 20 agree, 0 FAILED, 1 BLOCKED (V3, locked desktop) — `reports/ty/d15_verification.md`.

| slice | paths | main after |
|---|---|---|
| `tools-seller_tester` | 18 | `d5badc5f` |
| `tools-root` | 252 | `4650f024` |
| `tools-vision` | 24 | `20392bb5` |
| `Northstar_backend-tests` | 5 | `82097ac1` |

Each promotion wrote a `promote/20261109-<slice>-3f002e0c` tag and a `rollback/20261109-<sha>`
tag, so any one of them can be undone without touching the others.

`main` therefore now carries the deterministic layout stages, the grounding benchmark runners, the
held-out tooling, the JSX checker fix and their tests. It does **not** yet carry the UI work.

## Refused, on purpose: the bundle

`python tools/promote_staging.py --check --candidate staging-candidate/20261109-1811` →
**REFUSED — gate `bundle`**: 271 visual/creative paths under `northstar-os-ui/src/` need human eyes.
That refusal is the rule working, not an error.

## Waiting on you (visual slices, 18 of them)

`reports/ty/staging_review_20261109.md` is the review pack. The ones that carry today's work:

| slice | paths | what changed |
|---|---|---|
| `ui-shell` | 27 | ux-06 shell chrome on every authed route; ux-07 workspace tabs with state kept across switching |
| `ui-pages` | 74 | the earlier room pages (unchanged today, still pending) |
| `ui-assets`, `ui-galactic`, `ui-studio`, `ui-styles`, ... | 13 more | earlier visual work, unchanged today |

The honest caveat on ux-07: the tab summary reaches the DOM, a global and an event, but
`src/chat/ChatSurface.jsx:624` forwards only `summary.canvas`, so **Bojo still is not told which tab
is open**. That is queued as `ux-07b-tab-context-to-bojo` and is one field plus a test, not a
redesign.

## To undo

```
python tools/promote_staging.py --revert rollback/20261109-20392bb5
```

One command per slice, in reverse order, if any of the four turns out to be wrong.
