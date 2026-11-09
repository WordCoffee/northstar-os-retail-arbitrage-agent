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

