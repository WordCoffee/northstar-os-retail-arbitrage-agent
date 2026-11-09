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



