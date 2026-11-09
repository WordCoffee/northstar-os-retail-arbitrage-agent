# Defects found while running the director program

Each entry is a real measurement, the code that causes it, and the smallest fix. Nothing here is
filed against the owner.

## D-001 — `FoundationDB` leaks one temp database per instance (2026-11-09)

**Measured:** `(Get-ChildItem $env:TEMP -Filter 'ns_foundation_*.db').Count` → **9,018** files in
`C:\Users\T2Hol\AppData\Local\Temp`, and 9,812 files in that directory in total. The suite creates a
`FoundationDB` per app fixture, and the default path is:

```python
fd, tmp = tempfile.mkstemp(prefix="ns_foundation_", suffix=".db")
os.close(fd)
path = tmp
```

Nothing removes `tmp`. Every test run adds roughly one file per Foundation-backed app fixture, so the
directory grows without bound. A directory with ~10,000 entries also makes every `mkstemp` slower and
gives an antivirus more work, which is exactly the sort of thing that shows up later as
"the suite is mysteriously slow".

**Not the cause of any failure.** I suspected it of a stall and checked: the suite was progressing
normally (23 % at 6.2 minutes), and a `py-spy dump` caught it momentarily idle inside
`sqlite3.Connection.execute` — a slow I/O instant, not a deadlock.

**Fix (smallest):** when `path is None`, register the created file for removal at interpreter exit,
and remove it in `close()`; never touch a caller-supplied path. Add a test that the auto-created path
is registered and that a supplied path is left alone. Do not delete the 9,018 existing files by hand
— quarantine them in one move (same volume) and let the fix stop the growth.

**Status:** fixed in `fix/f0-tempdb` (commit `3718763d`), 5 tests.

## D-002 — the first held-out run scored every brief against the wrong bar (2026-11-09)

**Measured:** the first held-out composite pass reported **16 of 21 passed, mean 86.2**, and **21 of
21 briefs failed `alpha_matte`** with `border mean 61.0 (>= 249)`. A check that fails on every
single brief is not a result, it is a broken constraint.

**Cause:** `tools/heldout_briefs.py` took **one** brief's constraints (ST-033, a white-background
main image) and reused them for all eight situations. `white_matte` requires a clean near-white
border ring, which only a white-background composition can have — so lifestyle, infographic and
packaging briefs were failed for a rule that was never about them. The scorer was right; the brief
was wrong.

**Fix:** the constraint profile for each situation is copied from the **tuned catalogue's own brief
for that situation**, unmodified. A test asserts each held-out brief's constraints equal the tuned
ones, and a second asserts a white matte is required only where the tuned catalogue requires it.

**Consequence to be honest about:** with the correct bar, four of the eight situations
(`scale_reference`, `bundle_multipack`, `background_swap`, `series_consistency`) legitimately
require a white matte, and the composite route renders a generated scene for them. The tuned
composite proof only ever covered three situations — white-background main, lifestyle and packaging
mockup — all of which are matte-friendly. The held-out numbers are the first measurement of the
other five, and they are lower. That is the finding, not a regression.

**The first run's proof is archived, not deleted:**
`reports/ty/quarantined/heldout_composite_proof_first_run_20261109.json`.

## D-003 — the reference pool held quote cards and a wordmark, not just products (2026-11-09)

**Measured:** the digest contact sheet showed a composite of a **quote card** — "I CARRY MY
CHILDREN NOT JUST IN MY ARMS, BUT IN MY SOUL" — presented as a product output. Checking the pool
visually (`reports/ty/_reference_candidates*.png`) found that of the twelve files copied from the
owner's `pictures for seller umbrella` folder, **only two were the actual box**: the rest are a
dozen social quote cards and the brand wordmark.

**Consequence:** six of the 21 held-out briefs were scored against a quote card rather than a
product. A card is not a product; scoring a seller pipeline on one measures nothing. The two runs
before this fix are superseded, and the earlier claim that 21 briefs covered "14 distinct product
photographs" was wrong — it was 14 files, of which some were cards.

**Fix:** the pool is now seven Word Coffee product images (two on white, five in scene, all showing
the box) and three Mogra photographs — **ten real products over 21 briefs**. A test asserts no
product is tested twice in the same situation, and at least eight distinct products are present.
Non-product files are quarantined at
`reports/ty/quarantined/references_word-coffee_not_products/`.

**Lesson to reuse:** a reference pool has to be looked at, not counted. The file names said "for
mom" and "for women"; only the pixels said "quote card".

**Second pass, after the verifier opened the files:** `wc_women_card_mirror.jpg` turned out to be an
affirmation card on a bathroom mirror with no box in frame, and `wc_women_main_front.jpg` was a
byte-identical copy of `word_coffee_front.jpg`. So the pool is now an explicit **reviewed roster** of
eight photographs (three Mogra, five Word Coffee), and a test hashes them: distinct files must be
distinct photographs, and every path must be on the roster. Names and counts were never the control;
the pixels were.

## D-005 — test modules share one environment, so the suite was order-dependent in both directions
(2026-11-09)

**Measured, twice, in opposite directions.** With `test_costco_api_client.py` ahead of it, the
contract test's product-finder returned a count instead of rows, because that module had left
`SCANNER_SEARCH_CACHE_PATH` pointing at a temp directory that no longer existed. With
`test_coverage_report.py` ahead of `test_product_analysis.py`, the latter read **89 cached
candidates** instead of the one its mocks return, because coverage_report sets
`SCANNER_OFFER_ENRICHMENT=OFF` at import and an unset value means OFF too.

**Three attempts, two of them wrong, and the wrong ones are the useful part:**

1. Restoring these names to their **session baseline** after every test turned 16 green tests into
   `KeyError`s: three modules configure the paths at **import** time and read them with
   `os.environ[...]` inside their tests.
2. Diffing **every** environment name across each module's import and resetting the rest was too
   broad: **67 tests failed**, because modules legitimately configure things for themselves and
   expect that configuration to outlive a single test.
3. What ships: a **narrow watched list** of ten names (the eight scanner paths plus
   `SCANNER_OFFER_ENRICHMENT` and `SCANNER_LIVE_ALLOWED`), restored per test to the value they had
   at that test's start, plus the two modules that need specific values now declaring them in
   `setUpModule`/`tearDownModule` instead of relying on an import side effect.

Verified by pairing the modules that used to interfere, in the order the suite runs them: 48 passed.

**A wrong turn worth recording:** fixing the same symptom by changing
`product_analysis._candidates_for_mode` (fall back to the cache only when the fresh search returned
nothing) made the *product* better, but `product_analysis.py` is a **protected artefact** with a
recorded hash — `test_proof_batch_run` refused it, correctly. The change was reverted rather than
re-baselined: a protected file is not a place to fix a test-environment problem.

## D-006 — the JSX crash checker read comments as code (2026-11-09)

**Measured:** `python tools/check-jsx-imports.py` reported `shell/WorkspacePanels.jsx: <Outlet>`
after the ux-07 merge, failing `test_shell_role_contract.py`. The file never uses `<Outlet>`; a
**comment** explains that the shell renders each tab's page itself "instead of letting the shared
`<Outlet/>` swap pages out".

**Cause:** the checker scanned raw source for JSX tags, so a component name inside a comment counted
as a reference. A checker that flags correct code blocks a correct build — and the next person
"fixes" it by deleting an accurate explanation.

**Fix:** `strip_comments()` removes `/* … */` and `// …` before the tag scan, with a look-behind so
`https://` inside a string survives. Two tests: comments are ignored, URLs are not.

## D-007 — the contract test depended on another module having populated the cache (2026-11-09)

**Measured:** `test_end_to_end_contract_run_on_a_fresh_backend` failed with
`assert "row(s) under 'evaluated'" in '6 measured field(s) (…)'` whenever it ran without a prior test
that had written candidates. Alone it passed; after `test_coverage_report.py` it failed.

**Cause:** `test_network_guard.py` — imported by every module — points `SCANNER_SEARCH_CACHE_PATH` at
an **empty** temp file on purpose (hermetic cache). The contract test's product-finder therefore
returned `evaluated: 0`, a count instead of rows, unless an earlier test had left candidates behind.
Passing was luck, not measurement.

**Fix:** the test seeds a one-candidate cache in its own `tmp_path` and points the environment at it.
It now measures the endpoint rather than the test order. Verified in the pair that used to fail: 24
passed.



## D-004 — a killed render wedged the GPU lane (2026-11-09)

**Measured:** after a composite pass was stopped, the next run refused with
`generator unavailable: gpu locked by {'role': 'seller_composite', 'pid': 11448, ...}` — and pid
11448 no longer existed. `state/gpu/lock.json` had no notion of a stale holder, so the lane stayed
closed until someone noticed and unlocked it by hand.

**Cause:** `tools/gpu_budget.lock()` refused whenever a lock file was younger than the TTL and named
a different pid, without asking whether that pid was still running.

**Fix:** a lock whose pid is **provably gone** (`psutil.pid_exists`, falling back to `os.kill(pid,
0)`) is reclaimed, and the new lock records the reclaim (`reclaimed: {role, pid, at, why}`) so it is
visible rather than silent. A lock held by a **live** process is still refused, which is the property
that matters. A probe that errors counts as alive: stealing a lock because `psutil` is missing would
be worse than refusing. Six tests in `test_gpu_lock.py`.



