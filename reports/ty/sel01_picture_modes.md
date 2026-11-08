# Seller-Tester: the three input modes (sel-01)

Lane: builder `sel-01`, branch `ty/sel-01`, worktree `state/worktrees/sel-01`, from `staging`.
Owner definition under test (`ty/MANDATE.md`): product pictures in any situation a seller needs,
from exactly three inputs — the prompt alone, stored references from earlier generations, and
references the user uploads. No fourth input.

Before this change the Seller-Tester had 32 briefs and no notion of which input a brief used, so
"pictures from three inputs" was unmeasured. Now every brief declares one, the harness reports per
mode, and the two reference modes are scored against the reference they claim.

---

## 1. Catalog — `ty/seller_briefs.json` (schema_version 2)

56 briefs: **32 prompt_only, 12 stored_reference, 12 uploaded_reference**.

| Mode | Briefs | What the reference is |
| --- | --- | --- |
| `prompt_only` | ST-001…ST-032 | none. All 32 pre-existing briefs. Nothing in the file referenced a stored asset, so none of them was relabelled a reference brief. |
| `stored_reference` | ST-033…ST-044 | real assets: `renders/smoke_main_2000.png` (white-background pack shot), `renders/mogra-forest-dusk-mockup-complete.png` (greenhouse lifestyle), `renders/smoke_cutout_alpha.png` (cutout). All 8 situations covered. |
| `uploaded_reference` | ST-045…ST-056 | the seller's own file, named by descriptor (`filename`, `mime_type`, `subject`), `path: null`. 8 categories, 8 situations. |

Validation now refuses: an unknown `source_mode`; a `prompt_only` brief that carries a `reference`;
a reference mode without one; a `stored_asset` path that is absolute, escapes with `..`, is outside
`renders/`, `generated_images/` or `Northstar_backend/data/studio_generated/`, or is not on disk; an
`uploaded_file` reference without a descriptor; fewer than 12 briefs in any mode. The duplicate rule
is now `(category, situation, difficulty, mode)`, so the same category/situation can appear once per
input without the modes colliding.

**Truthfulness note, stated plainly:** every stored_reference brief is a supplement pouch, because
the Mogra Organic pouch is the only product in this checkout with stored generations. Labelling a
mug brief `stored_reference` would have meant inventing an asset that does not exist, so those
briefs stayed `prompt_only` and the mug/apparel/etc. reference coverage lives in the uploaded mode,
where the input is the seller's own file and no repo asset is implied.

## 2. Harness — per-mode results, selection, summary

* `run_pass` records `source_mode` (and `reference.kind` / `reference.path`) on every result.
* `select_briefs` samples round-robin across the three modes (catalog order inside a mode), so
  `run --limit 40` cannot spend its whole budget on one input. `--mode` restricts a pass to one.
* `by_mode` is always seeded with all three modes, so a mode with no scored output appears as
  `scored: 0` with `mean_score: 0.0` — never absent.
* `selected` / `scored` / `not_scored` make a short generator visible instead of silent, e.g. 40
  briefs selected, 30 scored, 10 not scored because only 30 artefacts exist.
* `catalog_by_mode` records what the catalog declares, next to what actually ran.
* Escalation stays inside the mode (`raise_tier`, `add_constraint`, `new_category`), and the log
  entry records `source_mode`. A new reference brief keeps a reference, reusing the original when
  the catalog has no same-mode template for that category.

## 3. Reference-subject check — `tools/seller_tester/reference_check.py`

Mode-specific check `reference_subject`, weight 0.25, forced into `critical` for both reference
modes. It passes only when **both** hold:

1. **dominant-colour agreement** — chroma-weighted 12-bin hue histogram of the subject pixels
   (pixels differing from the corner-sampled background), histogram intersection ≥ 0.62;
2. **silhouette aspect agreement** — bounding-box aspect of the subject, produced/reference ratio
   ≤ 1.6.

`cannot_verify` (missing reference, no local copy of an upload, unreadable asset, either picture
under 1% chromatic subject pixels) returns `ok: false` and counts as a failure. It is never a pass.

### Measured calibration (this checkout, shipped code, default thresholds)

Every one of the 30 assets under `renders/`, `generated_images/` and
`Northstar_backend/data/studio_generated/`, compared with each of the three reference assets:

| Reference | Same-product renders accepted | Unrelated assets refused |
| --- | --- | --- |
| `renders/smoke_main_2000.png` | 7 / 9 | 20 / 20 (3 `cannot_verify`) |
| `renders/mogra-forest-dusk-mockup-complete.png` | 6 / 9 | 20 / 20 (3 `cannot_verify`) |
| `renders/smoke_cutout_alpha.png` | 6 / 9 | 17 / 20 (3 `cannot_verify`) |

The rejects of family members are the contact-sheet / side-by-side crops whose silhouette aspect
genuinely differs (`ab_realism_side_by_side.png` ratio 2.8, `_ab_full.png` ratio 2.0).

**The honest weakness, with numbers:** the colour score does not cleanly separate every case. Against
the `CUTOUT` reference, three dark-green SourceScout UI screenshots score 0.6362–0.6368 and are
accepted, while a genuine pouch crop (`ab_realism_crop.png`, reference `DUSK`) scores 0.6031 and is
rejected. The overlap band is 0.603–0.637, so no single threshold accepts every real same-product
render and rejects every unrelated screenshot. This check is a proxy that fails conservatively; a
semantic gate (the local vision judge, which remains OFF by default) is what actually decides
"contains the reference subject" when the stakes are high. The per-brief
`reference.check.min_colour_agreement` knob exists so a brief can be tightened where the proxy is
known to be loose.

## 4. The real pass — `python -m tools.seller_tester run --limit 40` (stored generator)

```
{
  "generated_at": "2026-11-08T21:42:39+00:00",
  "generator": "stored",
  "judge_enabled": false,
  "mode_filter": null,
  "selected": 40,
  "scored": 30,
  "not_scored": 10,
  "passed": 1,
  "failed": 29,
  "pass_rate": 3.3,
  "mean_score": 26.3,
  "gaps_filed": 29,
  "catalog_by_mode": {"prompt_only": 32, "stored_reference": 12, "uploaded_reference": 12},
  "by_mode": {
    "prompt_only":       {"scored": 10, "passed": 1, "mean_score": 35.7},
    "stored_reference":  {"scored": 10, "passed": 0, "mean_score": 21.7},
    "uploaded_reference":{"scored": 10, "passed": 0, "mean_score": 21.5}
  },
  "escalations": 1
}
```

Per-mode counts are 10 / 10 / 10 scored. The selection is mode-balanced; the ceiling of 30 scored is
the 30 image files on disk, not the brief count. 29 gaps were filed (57 pre-existing records, one
deduplicated update, 85 in the working file at run time); `ty/seller_gaps.json` is outside this
lane's write scope, so it was restored after capturing the evidence.

What those numbers actually mean:

| Mode | Scored | Passed | Reference verdicts |
| --- | --- | --- | --- |
| `prompt_only` | 10 | 1 (ST-004 → `renders/smoke_main_2000.png`, score 85.0) | skipped by design |
| `stored_reference` | 10 | 0 | 2 pass (ST-034 against `ab_realism_real.png`, 0.874; ST-035 against the dusk render, 0.658 — both genuinely the same pouch), 7 fail (logos/screenshots, colour 0.001–0.537), 1 `cannot_verify` (achromatic screenshot) |
| `uploaded_reference` | 10 | 0 | 10 × `cannot_verify`: no local copy of the named upload exists in this checkout |

So the pass measures the *harness*, not the picture service. **No mode is "covered" in the sense of
pictures produced from its input:** the `stored` generator replays artefacts and cannot edit a
reference; `uploaded_reference` has no upload to replay at all. The one prompt-only pass is a real
render of a real product (`smoke_main_2000.png`) meeting a real brief — that is the only genuine
pass in the run, and it is genuine because nothing had to be derived from an input.

## 5. Tests

`python -m pytest Northstar_backend/test_seller_tester.py Northstar_backend/test_seller_scores.py -q`

```
...............................................                          [100%]
47 passed in 1.73s
```

Added (all with `tmp_path` where they write): shipped-catalog mode truthfulness and coverage;
unknown mode refused (catalog validation, `select_briefs`, `escalate`); reference paths outside the
asset trees refused; a limited pass samples every mode; summary groups by mode and shows `scored: 0`
for an unscored mode; a stored-reference pass records its mode and reference; the reference check
passing on the same subject, failing on a different colour and on a different shape, and
`cannot_verify` counting as a fail (missing asset, missing upload, absolute path); a reference brief
unable to pass on constraints alone, and passing when verification is injected; escalation holding
its mode for 8 steps in both reference and prompt modes.

Note: `Northstar_backend/test_seller_tester.py` is not in this lane's listed write scope, but the
required evidence command names it and requirement 6 asks for these tests, so it was edited
deliberately rather than stubbed elsewhere. No other file outside the scope was changed;
`ty/seller_gaps.json` was restored.

## 6. What is honestly not covered

1. **No generator produces from an input.** The stored lane replays unrelated artefacts; 1/30 pass
   and 0/10 in each reference mode. A real result for the reference modes needs a generator that
   edits the declared reference (ComfyUI adapter has no armed workflow).
2. **`uploaded_reference` has never been verified against a real upload.** All 12 briefs name files
   that do not exist here, so the check is `cannot_verify` by construction. The mode is measurable,
   not measured.
3. **Stored references exist for one product only** (Mogra Organic pouch, 3 assets, 12 briefs).
   Cross-category stored-reference coverage is impossible without new renders, and inventing assets
   was not an option.
4. **The reference proxy has a measured overlap band** (0.603 genuine reject vs 0.637 screenshot
   accept, section 3). It cannot be the sole acceptance gate.
5. **Briefs carry constraints, not verbatim prompts.** "Prompt alone" is therefore represented by a
   structured request (category, situation, tiers, constraints), not by the sentence a seller types.
6. **`--limit 40` scores 30** because 30 images exist; 10 selected briefs are reported as
   `not_scored`, not silently dropped.
