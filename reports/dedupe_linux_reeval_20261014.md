# dedupe Linux re-eval — record (Phase-3 open item 1) — 2026-10-14/15

- **Standing line:** 0 new / 0 known-active / 231 allowlisted. Owner-approved re-eval ("low-stakes — splink is the working path").
- **What was probed:** can `dedupe==3.0.3` install and run on Linux (the library kept failing to build on the Windows host), and what does it take?

## Observed (in order)
1. **Windows host: install-blocked** — no prebuilt wheels across py3.11 / py3.12 / py3.14; source builds fail (`dedupe-levenshtein-search`, `affinegap`) without a build toolchain. (Known from Phase-3 unit 5.)
2. **Linux `python:3.12-slim` + `gcc g++ python3-dev`: installs OK.** First full-spike run then exposed two real issues:
   - `AttributeError: 'BTrees.IFBTree.IFBucket' object has no attribute 'byValue'` → **fixed by pinning `BTrees<6`** (verified in-container: `byValue: True`).
   - `dedupe.mark_pairs` in this version expects `{"distinct": [...], "match": [...]}` **with record-dict pairs** (not id tuples / not a flat dict) — the probe and spike scripts were adapted accordingly (found by iterating through the raised errors).
3. **numpy-2 conflict (the structural one):** with the above fixed, dedupe's internal scoring raised `UFuncTypeError` (float vs str under numpy 2). `numpy<2` fixes dedupe but **breaks splink 5 / pyarrow (requires numpy>=2)** → **dedupe requires a dedicated environment**, separate from splink. Recipe (encoded in the probe):
   `python -m venv /dv && /dv/bin/pip install 'dedupe==3.0.3' 'BTrees<6' 'numpy<2'` (+ system build tools).
4. **End-to-end isolated-venv run: NOT OBSERVED yet** — the final validation attempts stalled on container infrastructure on this machine: two `docker run` calls hung (image pull / apt mirror), and Docker Desktop subsequently became unresponsive even to `docker ps`. That is an environment problem, not a code finding; the probe is ready to run the moment the Docker host is healthy (or in CI).

## Deliverables (committed)
- `scripts/spikes/dedupe_linux_probe.py` — synthetic train/partition smoke test using the exact recipe above (no real data, no runtime network, no writes).
- `.github/workflows/advisory-dedupe-eval.yml` — **manual** (`workflow_dispatch`) advisory job: creates the dedicated venv with the pinned trio and runs the probe on a Linux runner (compilers + network present). Run it once from the Actions tab to close the remaining "train OK / partition OK" observation.

## Verdict
- dedupe is **installable and viable on Linux with pinned legacy deps**; it must live in its **own venv** (numpy<2 vs splink's numpy>=2). End-to-end train/partition verification is deferred to the CI job. **splink remains the working production path**; nothing was wired anywhere (no prod wiring, per directive).

## Housekeeping note (open)
- Two probe runs were killed mid-flight; once the Docker host is responsive, confirm no stray containers remain (expected: only `northstar-lightpanda`) and remove leftovers if present. Docker Desktop may need an operator restart.
