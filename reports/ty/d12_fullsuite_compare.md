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

Three attempts, all recorded.

1. **First run, started at `d968eacd`.** Reached **24 % with no `F` or `E` in the progress
   output** in about 80 minutes, then stopped: builders merged into `staging` while it ran, so
   it no longer described one commit. A mixed-state result is not evidence.
2. **Second run, `7fd881cc`** — the first run to finish:

```
1 failed, 7066 passed, 117 skipped, 2 xfailed, 17 warnings, 125 subtests passed in 1097.96s (0:18:17)
```

   Against the baseline (`6617 passed, 0 failed, 117 skipped, 125 subtests`): **+449 passed,
   skips unchanged, and one new failure**.

   The failure was `test_gpu_budget.py::test_an_exclusive_role_drains_everything_first`, and it
   was a **test defect, not a product defect**: the test asked the 27B for a lease, and a lease
   left on disk by an earlier run in the same session made the first assertion false. Fixed by
   patching `HEAVY_LEASE_PATH` into `tmp_path` so the test cannot inherit state. Verified both
   ways — 7 passed with no lease, and 7 passed with a deliberately planted stale lease.
3. **Third run, `d2c29a55`** (the fix), writing `reports/ty/_fullsuite_final_20261108.txt`.
   Its tally is appended below.

The 18-minute runtime also settles an earlier question: the suite is not intrinsically slow.
The earlier 24 %-in-80-minutes runs were competing with builders and a resident ComfyUI; on a
quiet machine the whole suite is under twenty minutes.


