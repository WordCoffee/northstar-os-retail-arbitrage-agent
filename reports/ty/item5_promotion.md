# Promotion record — 2026-11-09

Two promotion passes, one refusal that is the interesting part, and a clear statement of what is
blocking the rest.

## Green, and what that means

| candidate | sha | suite |
|---|---|---|
| `staging-candidate/20261109-2135` | `6658f7c2` | 7333 passed, 0 failed, 19 m 11 s |
| `staging-candidate/20261109-2142` | `ac52736b` | **7346 passed, 0 failed**, 19 m 09 s |

The second candidate is the one that matters: it contains ux-07b (chat turn body carries the open
tab), ux-08 (one scene per shell, unloaded on switch, static/reduced fallbacks), ux-09 (pixel-space
snap, 100 % zoom), and sel-03 (A+ built on the deterministic layout stages).

## Promoted to `main`

`main` went `ecef24a7` → **`b4792612`**, in three groups:

1. `tools-seller_tester`, `tools-root`, `tools-vision`, `Northstar_backend-tests` (from candidate
   `20261109-1811`);
2. `Northstar_backend-adapters`, `-agent_kernel`, `-agents`, `-assets`, `-bojo_tools`, `-costco_*`,
   `-costco_non_kirkland`, `-costco_client_live`, `-design_studio`, `-foundation`, `-jobs`, `-kpis`,
   `-ledger`, `-pricing`, `-seller_*`, `-specialists` (from candidate `20261109-2135`);
3. each with a `promote/20261109-<slice>-<sha>` tag and a `rollback/20261109-<main-sha>` tag.

**20 of 169 code slices are on main. 149 are not.**

## Why 149 slices are not on main — this is the finding

```
REFUSED slice_commit_failed: pre-commit BLOCKED: gitleaks found potential secrets in staged changes.
Fix or remove them; for reviewed false positives add an allowlist entry to .gitleaks.toml.
```

Three slices are refused, with **24 findings** between them:

| slice | paths | why it matters |
|---|---|---|
| `Northstar_backend-root` | 586 | holds `ui_serving.py` — without it main cannot collect 8 test modules |
| `Northstar_backend-data` | 262 | data files the suite reads |
| `Northstar_backend-static` | 2 | static assets |

This is the same leak class as **DIR-1** in `needs_you.md` (credentials already committed in chat
exports). Bypassing the hook would be a policy bypass, so it is not done.

**Consequence, measured:** the full suite cannot run on main.
- at `82097ac1`: 4 collection errors, `ModuleNotFoundError: adapters.reasoning_provider`;
- at `b4792612`: 8 collection errors, `ModuleNotFoundError: Northstar_backend.ui_serving`.

By test name, from `tools/main_vs_candidate.py`: of the candidate's **7,452** test ids, **3,601**
(214 modules) have their module on main and **3,851** (316 modules) do not. The missing modules are
listed in `reports/ty/main_vs_candidate_by_name.json`; the narrative is in
`reports/ty/main_vs_candidate.md`.

## Refused on purpose: the visual bundle

`python tools/promote_staging.py --check` still returns **REFUSED — gate `bundle`** with 271 visual
paths under `northstar-os-ui/src/` (and `renders/`). Review pack:
`reports/ty/staging_review_20261109.md`. The slices carrying today's UI work are `ui-shell`
(ux-06/07/07b/08) and `ui-studio`, `ui-pages` (ux-09).

## To undo

```
python tools/promote_staging.py --revert rollback/20261109-<sha>
```

One command per promotion, in reverse order.
