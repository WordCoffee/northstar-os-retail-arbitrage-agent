# Held-out run — independent verification

Verifier: separate session from the author of the held-out run. Repo root
`C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent`, 2026-11-09. Nothing was fixed; the
only files written are `reports/ty/verifier_heldout.{json,md}` and (in step 4) the two stale rows of
`reports/ty/d15_verification.md` and `reports/ty/verifier_findings.json`.

## Verdict: AGREE

21 scored, 13 passed, mean 86.2 — reproduced exactly from the rows on disk, not from the summary block.
The bar is the tuned catalogue's own bar for every situation (no D-002 repeat).

## What I ran, in order, and the real output

### 1. Status first — the pass was already finished, so I did not re-run it

```
> python tools/heldout_composite.py --status
{
  "total": 21,
  "done": 21,
  "remaining": [],
  "passed": 13,
  "mean": 86.2
}
```

`done: 21` means re-running `--run` would have overwritten the artefact under audit, so per the task
I verified the existing proof instead. No composite render was performed in this session.

### 2. The briefs on disk regenerate byte-identically

```
> python tools/heldout_briefs.py --write
{
  "held_out": 21,
  "declared_unscorable": 3,
  "lines": ["lions-mane", "word-coffee"],
  "scorable": 21
}
> (Get-FileHash ty\seller_briefs_heldout.json -Algorithm SHA256).Hash
2E0CCB6980B397F7207AC004D1B850F1D98F5FB777789748BDD72F03D5AC658F   (identical before and after)
```

`ty/seller_briefs.json` was not touched (sha256 still `151854D7…`).

### 3. The bar check (D-002 regression) — passes

```
> python -m pytest -q Northstar_backend/test_heldout_set.py
.........                                                                [100%]
9 passed in 0.22s
```

The task file's own snippet, run independently of the test suite:

```
> python $env:TEMP\opencode\bar_check.py
BAR_OK briefs= 21 situations= 8
```

All 21 runnable briefs carry the tuned catalogue's constraints for their situation, across 8
situations. No white matte is demanded on lifestyle/infographic. **No D-002 repeat.**

### 4. Mean recomputed from the result rows

```
> python $env:TEMP\opencode\recheck.py
rows 21 scored 21 passed 13
mean 86.2
lions-mane scored 10 passed 7 mean 91.3
word-coffee scored 11 passed 6 mean 81.6
cannot_verify rows 0
artefact problems: none
summary block says: 21 13 86.2
```

`passed` here counts `passed == true and not cannot_verify`; it agrees with the proof. Mean is
`round(sum(score)/count(scored), 1)`, not the file's `summary.mean`, and the two happen to agree.

### 5. Report table vs proof rows

```
> python $env:TEMP\opencode\tablecheck.py
report rows vs proof mismatches: none
```

Score, pass flag and situation all agree for all 21 briefs.

### 6. Re-deriving the report changed nothing

```
> python tools/heldout_run.py --write
{ "held_out_briefs": 21, "scored": 21, "passed": 13, "mean": 86.2,
  "by_line": { "lions-mane": {"scored": 10, "passed": 7, "mean": 91.3},
               "word-coffee": {"scored": 11, "passed": 6, "mean": 81.6} } }
> Get-FileHash state\seller\heldout_proof.json
BCBD26965C56DBF9C2A9F70A519F33B839DB6BB8C3F49A92FF673BC2E20F31BA   (unchanged)
REPORT_BYTE_IDENTICAL
```

### 7. Artefacts

All 21 `artefact_path` values exist; every one is a real PNG (`89 50 4E 47 0D 0A 1A 0A`); the
smallest is 130,720 B (`HO-014.png`), well over 20 KB. 42 PNGs in the directory = 21 artefacts plus
21 cutouts.

### 8. Digest pairs

`reports/ty/digest_composites_2026-11-09.png` (1,483,828 B) is six rows, each labelled `source`
(left) and `composite` (right). Six distinct source files, taken one pair per source by
`tools/ty_digest.py:146-157`. Rows 1–3 are the same Mogra lion's mane + shiitake pouch pair from
three different source photographs (white sweep, greenhouse, dark studio); rows 4–5 are the two
different Word Coffee boxes; row 6 is the Word Coffee poster. So: source-left/output-right holds,
and no pair is duplicated — but "six distinct products" is really six distinct *sources*, three of
which are one product pair.

## Findings that do not change the numbers

1. **`HO-014.png` and `HO-018.png` are byte-identical.** Both briefs take
   `renders/references/word-coffee/word_coffee_logo.png` as their "product photograph" — it is a
   wordmark, not a product — and both composite onto an indistinguishable near-white field. Both
   fail anyway (83.3 and 70.0), so the pass count is not inflated; those two briefs simply test less
   than a product image would.
2. Three pairs of cutouts are also byte-identical where the reference repeats
   (`HO-011/015/019` on `moms_front`, `HO-016/020` on `women_front`, `HO-013/021` on `moms_20`).
   That is expected from a shared reference; the artefacts themselves differ where the situation
   differs, except case 1.

## Reproduce my numbers

```powershell
python tools/heldout_composite.py --status          # done 21 -> verify, do not re-run
python tools/heldout_briefs.py --write
python -m pytest -q Northstar_backend/test_heldout_set.py
# then: recompute mean from state/seller/heldout_proof.json results[]
```
