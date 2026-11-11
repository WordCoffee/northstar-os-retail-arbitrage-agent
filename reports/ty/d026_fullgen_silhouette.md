# D-026 — the residue instrument can no longer pass a picture by masking it

Unit `fix-fullgen-silhouette`. Tag `ty-dir-d026-silhouette`. Rollback point
`rollback/pre-d026-20261111`.

## What was owed

`check_matte_residue` measures every pixel outside the **recorded** silhouette. On the
generation route that silhouette is the cutout's alpha, and a colour cut keeps a shadow that
is attached and opaque — so the shadow is *inside* the silhouette, "outside" is empty, and
the check returned **0.00 %, pass** on PO-001 at seed 2747063199 while the picture carried
590 541 px of grey smear. D-022's audit found it; D-025 proved it with a control plate.

## What changed

| file | change |
|---|---|
| `tools/seller_tester/scorers.py` | new `COLOUR_CUT_METHODS` (`grabcut`, `background_distance`, `otsu_lab`) and a `silhouette_source=` parameter on `check_matte_residue` / `_run_checks` / `score_image`. A colour-cut silhouette is **skipped with words** — *"the silhouette came from a colour cut (grabcut) … this picture is UNVERIFIED for residue — not clean"* — never reported as a number. A matte silhouette is measured exactly as before; an undeclared source keeps the old behaviour, so no existing caller is silently downgraded |
| `tools/seller_tester/harness.py` | the live pass now passes `generation.cutout_matte.method` into the scorer, so the guard fires on real passes, not only on hand-built tests |
| `Northstar_backend/test_fullgen_silhouette.py` | six checks written first: every colour-cut method is unverified; a matte silhouette still measures 0.00 % clean and fails a dirty one; an undeclared source is unchanged; `score_image` carries the declared source into the check |
| `Northstar_backend/test_fullgen_matte_cutout.py` | the D-025 control now asserts the new contract (768 band px kept **and** the residue verdict refuses to call it clean) |

## Measured on the real artefacts (no render, re-score only)

| artefact | cutout | residue check | score |
|---|---|---|---|
| `renders/d025/PO-001.png` (D-025, real matte, seed 2747063199) | BiRefNet | **0.00 %**, 0 px | **100.0**, passed |
| `renders/d022_pinned/PO-001.png` (grabcut, same seed) | grabcut | **14.76 %**, 590 541 px, 587 151 neutral | **90.0**, `matte_residue` failed |

`reports/ty/d026_rescore_matte.json`, `reports/ty/d026_rescore_grabcut.json`
(`python tools/rerender_prompt_only.py … --rescore-only`). The 14.76 % reproduces D-022's
audit number exactly, so the two instruments agree on the same artefact.

On a live pass the same rule is stricter, not looser: a pass that records
`cutout_matte.method = "grabcut"` reports the residue property as **unverified** instead of
clean, which is the honest reading — an instrument cannot police the mask it is calibrated
against.

## Tests

```
python -m pytest Northstar_backend/test_fullgen_silhouette.py \
  Northstar_backend/test_fullgen_matte_cutout.py \
  Northstar_backend/test_matte_residue.py -q
-> 19 passed, 1 skipped
```

## Not claimed

The silhouette is still *one* mask. A matte that includes a shadow would pass this check the
same way grabcut did; what is now true is that a route which only has a colour cut can no
longer report a clean number. The seller-visible output is unchanged by this unit — it is an
instrument fix, and the photo that exposed it (`renders/d022_pinned/PO-001.png`) is still a
picture with a smear until it is re-rendered through the matte (D-025 already does that:
`renders/d025/PO-001.png`).
