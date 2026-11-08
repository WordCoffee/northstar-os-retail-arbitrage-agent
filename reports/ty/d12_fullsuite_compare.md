# Full suite on staging — name comparison against the 6,617 baseline

Owner instruction: *run the full suite serialized on staging and compare by name against
6,617.*

## Collection (fast, complete)

```
python -m pytest --collect-only -q
7135 tests collected in 10.42s
```

| | count |
|---|---|
| baseline id list (`reports/ty/_idlist_20261107.txt`) | 6,736 collected, **6,617 passed** |
| collected now (`reports/ty/_collected_20261108.txt`) | **7,186** |
| **added by name** | **451** |
| **removed by name** | **1** |

Machine-readable diff: `reports/ty/d12_names_diff.json`.

### The 451 added names

They are the units built since the baseline: `test_chrome_uia`, `test_vision_control`,
`test_vision_browser`, `test_vision_parity`, `test_vision_live`, `test_vision_computer`,
`test_vision_dogfood`, `test_comfy_lane`, `test_ty_digest`, `test_measured`,
`test_seller_scores`, `test_seller_tester`, `test_visual_regression`, `test_scout_intel`,
`test_model_scout`, `test_tool_bakeoff`, `test_prospector`, `test_product_finder`,
`test_sourcing`, `test_monitor`, `test_rank`, `test_competitor`, `test_rival`,
`test_bojo_sourcing_tools`, `test_bojo_ops_tools`, `test_bojo_tools_registry`,
`test_chat_tools_domain`.

### The 1 removed name, by name

```
- agents/golden_goose_finder/test_single_match.py::test_import_has_no_side_effects
```

That file does not exist on disk and git has no history of it (`agents/golden_goose_finder`
does not exist). It was collected into the baseline from an **untracked** directory that has
since gone. So it is not a test that was deleted from the repository; it is a baseline entry
with no file behind it. It is the only name from 6,736 that cannot be found.

## Pass/fail

Two attempts, both recorded rather than hidden:

1. **First run, started at commit `d968eacd`.** Reached **24 % with no `F` or `E` in the
   progress output** (dots and skips only) in about 80 minutes, then was stopped: the gap-loop
   builders merged into `staging` while it ran, so the run no longer described one commit.
   A mixed-state result is not evidence.
2. **Second run, started at commit `7fd881cc`** (after the Bojo tool wiring and the seller
   applicability correction), writing to `reports/ty/_fullsuite_20261108.txt`. It is slow on
   this machine — roughly 1 % per 5–6 minutes with the process mostly idle in waits.

**Status: in progress at the time this file was written.** The name comparison above is
complete and does not depend on it; the pass/fail tally is appended when the run finishes, and
a partial tally is recorded rather than guessed at. The first run's 24 %-clean is real
evidence about that commit, not about this one.

