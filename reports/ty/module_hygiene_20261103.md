# Module hygiene: four duplicate definitions, one of them a disabled guard

**Date:** 2026-11-03 · **Commits:** `beffb826`, `0f07957a`, `72edcb35`, `824e4284` · **Tests:** 33 + 103 passed in the focused runs.

A merge can duplicate a block without any visible symptom: Python imports the module, the later definition silently wins, and every test that never touches the dead copy passes. A repo-wide AST scan found four such duplicates in code this loop owns. Three were harmless aliases; one had switched a documented guard off.

| File | Duplicate | Consequence | Fix |
|---|---|---|---|
| `Northstar_backend/studio_generation.py` | `system_ram_free_mb`, `_is_stop_candidate`, `stop_for_render`, `restore_after_render`, `ensure_system_ram` defined twice | the later copy won; an unconditional `import psutil` defeated the file's own optional-psutil fallback, and `stop_for_render` would raise instead of no-op without psutil | removed the duplicate block; `stop_for_render` returns `[]` when psutil is absent |
| `Northstar_backend/conftest.py` | `pytest_collection_finish` defined twice (credential scrub, then generated-cache restore) | **the post-collection credential scrub never ran** — the second hook replaced the first | one hook does both, scrub first |
| `Northstar_backend/design_studio_api.py` | `ListingRecordIn` defined twice (bulk model without `source`, single-create model with it) | a bulk import silently dropped `source`; the same resource accepted different fields per route | one model for both routes; `source` accepted and persisted on either path |
| `Northstar_backend/asset_rubric.py` | `score_hero` implemented, then redefined as an alias to `score_listing` | the dead body looked authoritative; the alias was what ran | removed the dead body; pinned the alias (`class: listing`) |
| `Northstar_backend/foundation/jobs_durable.py` | `_now_iso` twice, identical | none at runtime; noise for the next reader | removed one |

A stale test was also corrected: `test_generation_guards.py` still expected the removed FLUX 2 edit lane to reach the cache guard. It now asserts `edit_lane_removed` for the edit lane and keeps the video lane's `comfyui_cache_none_required` assertion — the guard is still tested; the removed lane is named honestly.

## Evidence

```
python -m pytest Northstar_backend/test_module_hygiene.py ... -> 9 passed
python -m pytest ... test_generation_guards ...              -> 60 passed
python -m pytest test_design_studio_re_ext test_design_studio_openapi
                 test_module_hygiene test_listing_records_schema
                 test_asset_rubric                            -> 33 passed
python -X utf8 -c "import main"                              -> app import OK, 125 routes
```

`test_module_hygiene.py` reads the AST of the guarded modules and fails on any duplicate top-level
function or class, and additionally checks the optional-psutil fallback and that the merged conftest
hook actually calls both helpers in order.

## Honest limit

The AST scan is scoped to the modules this loop touched (`GUARDED`), not the whole tree. A wider scan
also reports duplicates in vendor environments; a production-wide scan needs an ignore list for
`venv*` and third-party packages, which is a separate, low-risk task. The four real-source duplicates
found outside the guarded set were fixed here; no other non-vendor duplicate was reported.
