# D9 — Seller-Tester harness

Date: 2026-11-08
Worktree: `state/worktrees/builder-d9` (branch `ty/builder-d9`, from staging)
Scope: `tools/seller_tester/**`, `Northstar_backend/test_seller_tester.py`,
`ty/seller_briefs.json`, `ty/seller_gaps.json`, this report.

No Amazon host was contacted. No model was called. No money or credits were spent.

## What was built

A harness that acts like a seller using Northstar OS through Bojo: it takes a
product-picture brief, obtains an image from an injectable generator, scores the
image with deterministic code, files every failure as a gap, and escalates the
brief after a pass.

| File | Purpose |
| --- | --- |
| `ty/seller_briefs.json` | 32 briefs: 8 situations x 8 categories x tiers 1-3 |
| `tools/seller_tester/briefs.py` | catalog loading + structural validation |
| `tools/seller_tester/scorers.py` | PIL+numpy checks, 0-100 subscore |
| `tools/seller_tester/judge.py` | injectable vision adapter, local-only, OFF by default |
| `tools/seller_tester/generators.py` | `stored` replay and documented `comfy` adapter |
| `tools/seller_tester/escalate.py` | tier -> constraint -> new-category ladder + history |
| `tools/seller_tester/gaps.py` | gap records + atomic write + mirror |
| `tools/seller_tester/harness.py` | `run_pass` orchestration and summary |
| `tools/seller_tester/cli.py` | `python -m tools.seller_tester ...` |
| `tools/seller_tester/README.md` | operating notes |
| `Northstar_backend/test_seller_tester.py` | 28 offline tests |

### Brief catalog

32 briefs (`ST-001`..`ST-032`), four rounds of the eight situations, with the
category rotated each round so every category appears four times:

- situations: `white_background_main`, `lifestyle`, `infographic`,
  `scale_reference`, `bundle_multipack`, `packaging_mockup`, `background_swap`,
  `series_consistency`
- categories: `supplement_pouch`, `ceramic_mug`, `apparel`, `skincare_bottle`,
  `small_appliance`, `pet_product`, `tool`, `food_jar`
- every brief carries dimensions, aspect ratio, background value/tolerance
  (uniform or explicitly free), fill % band, text rule (`no_text` / `allowed` /
  `text_expected`), matte rule and file-size bounds
- difficulty distribution: 8 x tier 1, 8 x tier 2, 16 x tier 3

Validated by both the CLI and a test: `python -m tools.seller_tester catalog`
returns `"valid": true`, `"errors": []`.

### Programmatic scorers (no model)

`score_image(bytes, brief)` loads the image once and runs:

| Check | Method |
| --- | --- |
| `dimensions` | exact-with-tolerance or min/max width/height |
| `aspect` | width/height vs brief ratio, relative tolerance |
| `background` | median RGB of four 24px corner patches vs brief value; also corner spread; skipped when `mode: free` |
| `subject_fill` | % of pixels farther than `distance` from the corner-derived background |
| `alpha_matte` | alpha cutout coverage, or flat near-white outer ring (mean + std) |
| `file_size` | byte bounds and a minimum bytes-per-pixel sanity floor |
| `text_free` | margin-ink heuristic: dark/saturated pixel share in the outer 10% band, for `no_text` and `text_expected` |

The text check is explicitly a heuristic, not OCR; the README and docstring say
so. Score is the weighted mean of non-skipped checks; a pass requires
`pass_score` (default 70) and all `critical` checks (dimensions, aspect,
background). Every check returns `ok`, `skipped`, `detail` and its measurements.

### Vision judge

`judge(image_bytes, rubric) -> {"pass": bool, "score": float, "reasons": [...]}`.
`local_judge` wraps `Northstar_backend/agent_kernel/vision_verify.py` (local
Ollama). It is returned by `get_judge()` only when `NORTHSTAR_SELLER_JUDGE=1`;
otherwise the harness scores without it. A non-loopback `NORTHSTAR_VISION_URL`
is refused with `available: false` (asserted by a test). Tests inject
`FakeJudge`. No cloud model is reachable from this adapter.

### Generators

- `stored` replays real artefacts under `renders/`, `generated_images/`,
  `Northstar_backend/data/studio_generated/`; brief *i* pairs with artefact *i*
  so one pass covers the catalog axis. Deterministic sorted discovery.
- `comfy` probes `http://127.0.0.1:8188/system_stats` and raises
  `GeneratorUnavailable` when the server is down. It refuses non-loopback hosts
  at construction, has no armed workflow, never retries and never downloads.

### Escalation

Each pass calls `escalate()`: difficulty 1 -> 2 -> 3 (tighter fill and background,
`pass_score` +5), then one added hard constraint (`tight_background`,
`narrow_fill`, `file_size_cap_4mb`, `strict_text_free`), then a fresh brief in an
unused category. A 40-step test proves the ladder always returns a brief. Steps
are recorded in `EscalationLog` and mirrored to `state/seller/escalation.json`.

### Gaps

Record shape is exactly `{id, brief_id, score, failed_checks, artefact_path, at}`.
`id` is deterministic in (brief, artefact), so a re-run updates rather than
duplicates. Writes are atomic; the tracked file is `ty/seller_gaps.json` and the
same rows are mirrored to `state/seller/gaps.json` (gitignored).

## Tests

Command, from the worktree root:

```powershell
python -m pytest Northstar_backend/test_seller_tester.py -q
```

Tail:

```
............................                                             [100%]
28 passed in 0.97s
```

Coverage: catalog validity and tamper detection; every scorer on synthetic
pass/fail images (dimensions, aspect, corner background, fill, white matte,
alpha, file size, both text rules); score aggregation; garbage bytes; judge
injection, judge-off default, and non-loopback refusal; escalation
tier/constraint/new-category and a 40-step dry-proof; escalation log
persistence; gap shape, dedupe, mirror, incomplete-record rejection; stored
generator discovery/limits/empty; ComfyUI clean refusal (closed loopback port
and non-loopback host); two full `run_pass` runs using `tmp_path` only, one of
which exercises the fake judge.

All test writes are under `tmp_path`. A grep of the test file shows no path
outside it.

## Real pass

Command:

```powershell
python -m tools.seller_tester run --limit 30
```

Output (real, unedited):

```json
{
  "generated_at": "2026-11-08T08:46:40+00:00",
  "generator": "stored",
  "judge_enabled": false,
  "scored": 30,
  "passed": 1,
  "failed": 29,
  "pass_rate": 3.3,
  "mean_score": 23.4,
  "gaps_filed": 29,
  "gaps_in_file": 29,
  "gaps_path": "ty/seller_gaps.json",
  "mirror_path": "state/seller/gaps.json",
  "escalations": 1
}
summary: ...\state\seller\last_run.json
```

### What the 30 artefacts actually are

Everything the stored generator found in the three replay roots was scored; the
generator does not filter by apparent content:

| Origin | Count | Product-picture relevance |
| --- | --- | --- |
| `renders/` | 10 | product renders (real) |
| `generated_images/branding_*` | 7 | brand logos (not product pictures) |
| `generated_images/screenshots/` | 13 | UI screenshots (not product pictures) |

So 30 real artefacts were scored, of which **10 are product renders**. There is
no 20th product render in the repo's replay roots; the other 20 are stored
artefacts that fail the product-picture checks by construction. Their gap records
are true measurements, not synthetic failures, but they are not evidence about
Northstar's product renderer. Product-render subset: mean 25.5, 1 pass, 9 fails.

The one pass is `renders/smoke_main_2000.png` (2000x2000, white background,
centered subject) against `ST-010` (`lifestyle`, 2000x2000, fill 15-85%, text
allowed, background free). It is a legitimate lifestyle/secondary-image
requirement, not a relaxed white-main check; it scored 100 on the four checks
that brief grades.

### Per-brief scores (real)

| brief | situation | category | score | verdict | artefact | failed checks |
| --- | --- | --- | --- | --- | --- | --- |
| ST-001 | white_background_main | supplement_pouch | 25.0 | fail | `renders/_ab_crop.png` | dimensions, aspect, background, alpha_matte, text_free |
| ST-002 | lifestyle | ceramic_mug | 9.1 | fail | `renders/_ab_full.png` | dimensions, aspect, subject_fill |
| ST-003 | infographic | apparel | 57.1 | fail | `renders/ab_realism_crop.png` | dimensions, aspect |
| ST-004 | scale_reference | skincare_bottle | 15.0 | fail | `renders/ab_realism_flat.png` | dimensions, background, subject_fill, alpha_matte, text_free |
| ST-005 | bundle_multipack | small_appliance | 15.0 | fail | `renders/ab_realism_real.png` | dimensions, background, subject_fill, alpha_matte, text_free |
| ST-006 | packaging_mockup | pet_product | 9.1 | fail | `renders/ab_realism_side_by_side.png` | dimensions, aspect, subject_fill |
| ST-007 | background_swap | tool | 5.0 | fail | `renders/mogra-forest-dusk-mockup-complete-v1.png` | dimensions, aspect, background, subject_fill, alpha_matte, text_free |
| ST-008 | series_consistency | food_jar | 5.0 | fail | `renders/mogra-forest-dusk-mockup-complete.png` | dimensions, aspect, background, subject_fill, alpha_matte, text_free |
| ST-009 | white_background_main | ceramic_mug | 15.0 | fail | `renders/smoke_cutout_alpha.png` | dimensions, background, subject_fill, alpha_matte, text_free |
| ST-010 | lifestyle | apparel | 100.0 | PASS | `renders/smoke_main_2000.png` | - |
| ST-011 | infographic | skincare_bottle | 57.1 | fail | `generated_images/branding_logo-beacon-tower.jpg` | dimensions, aspect |
| ST-012 | scale_reference | small_appliance | 15.0 | fail | `generated_images/branding_logo-compass-diamond.jpg` | dimensions, background, subject_fill, alpha_matte, text_free |
| ST-013 | bundle_multipack | pet_product | 35.0 | fail | `generated_images/branding_logo-monogram-n.jpg` | dimensions, background, alpha_matte, text_free |
| ST-014 | packaging_mockup | tool | 45.5 | fail | `generated_images/branding_logo-pathway-nodes.jpg` | dimensions, aspect |
| ST-015 | background_swap | food_jar | 15.0 | fail | `generated_images/branding_logo-peak-summit.jpg` | dimensions, background, subject_fill, alpha_matte, text_free |
| ST-016 | series_consistency | supplement_pouch | 15.0 | fail | `generated_images/branding_northstar-logo.jpg` | dimensions, background, subject_fill, alpha_matte, text_free |
| ST-017 | white_background_main | apparel | 20.0 | fail | `generated_images/screenshots/cloudflare_signup_20260911_132624.png` | dimensions, aspect, subject_fill, alpha_matte, file_size, text_free |
| ST-018 | lifestyle | skincare_bottle | 9.1 | fail | `generated_images/screenshots/costco_sourcescout_20260912_154633.png` | dimensions, aspect, subject_fill |
| ST-019 | infographic | small_appliance | 28.6 | fail | `generated_images/screenshots/costco_trash bags_20260911_212920.png` | dimensions, aspect, subject_fill |
| ST-020 | scale_reference | pet_product | 5.0 | fail | `generated_images/screenshots/costco_trash bags_20260912_062013.png` | dimensions, aspect, background, subject_fill, alpha_matte, text_free |
| ST-021 | bundle_multipack | tool | 5.0 | fail | `generated_images/screenshots/costco_trash bags_20260912_062051.png` | dimensions, aspect, background, subject_fill, alpha_matte, text_free |
| ST-022 | packaging_mockup | food_jar | 0.0 | fail | `generated_images/screenshots/screenshot_20260911_130830.png` | dimensions, aspect, subject_fill, file_size |
| ST-023 | background_swap | supplement_pouch | 25.0 | fail | `generated_images/screenshots/screenshot_20260911_170506.png` | dimensions, aspect, background, subject_fill, file_size |
| ST-024 | series_consistency | ceramic_mug | 25.0 | fail | `generated_images/screenshots/screenshot_20260911_171420.png` | dimensions, aspect, background, subject_fill, file_size |
| ST-025 | white_background_main | skincare_bottle | 15.0 | fail | `generated_images/screenshots/screenshot_20260912_061836.png` | dimensions, aspect, background, subject_fill, alpha_matte, file_size |
| ST-026 | lifestyle | small_appliance | 45.5 | fail | `generated_images/screenshots/screenshot_20260912_183730.png` | dimensions, aspect |
| ST-027 | infographic | pet_product | 57.1 | fail | `generated_images/screenshots/sourcescout_proof_20260912_164237.png` | dimensions, aspect |
| ST-028 | scale_reference | tool | 25.0 | fail | `generated_images/screenshots/sourcescout_proof_20260912_170901.png` | dimensions, aspect, background, alpha_matte, text_free |
| ST-029 | bundle_multipack | food_jar | 5.0 | fail | `generated_images/screenshots/sourcescout_proof_20260912_183753.png` | dimensions, aspect, background, subject_fill, alpha_matte, text_free |
| ST-030 | packaging_mockup | supplement_pouch | 0.0 | fail | `generated_images/screenshots/test_chrome_signup.png` | dimensions, aspect, subject_fill, file_size |

By situation (from the summary):

| situation | scored | passed | mean score |
| --- | --- | --- | --- |
| background_swap | 3 | 0 | 15.0 |
| bundle_multipack | 4 | 0 | 15.0 |
| infographic | 4 | 0 | 50.0 |
| lifestyle | 4 | 1 | 40.9 |
| packaging_mockup | 4 | 0 | 13.7 |
| scale_reference | 4 | 0 | 15.0 |
| series_consistency | 3 | 0 | 15.0 |
| white_background_main | 4 | 0 | 18.8 |

### Gaps filed

29 records in `ty/seller_gaps.json`, mirrored byte-identically to
`state/seller/gaps.json`. First record (real):

```json
{
  "id": "gap-99117887cd80",
  "brief_id": "ST-001",
  "score": 25.0,
  "failed_checks": ["dimensions", "aspect", "background", "alpha_matte", "text_free"],
  "artefact_path": "renders/_ab_crop.png",
  "at": "2026-11-08T08:46:37+00:00"
}
```

### Escalation recorded

One pass, one step:

```json
{
  "at": "2026-11-08T08:46:38+00:00",
  "from_brief_id": "ST-010",
  "from_difficulty": 2,
  "action": "raise_tier",
  "detail": "difficulty 2 -> 3",
  "to_brief_id": "ST-010",
  "to_difficulty": 3,
  "score": 100.0,
  "artefact_path": "renders/smoke_main_2000.png"
}
```

## Limitations / what was not done

- **No live generation.** `comfy` is implemented and refuses cleanly; no ComfyUI
  workflow is armed in this repo, and none was fabricated. The real pass used
  `stored`, as specified.
- **The vision judge was never run against a live model.** It is off by default
  (env-gated), documented, and its non-loopback refusal is tested. Exercising it
  would need a local Ollama vision model; that was not required and not done.
- **The text check is a margin-ink heuristic, not OCR.** It cannot read text or
  prove its absence inside the product area; a real OCR pass is a follow-up.
- **Stored pairing is positional, not semantic.** Brief *i* gets artefact *i*.
  With 20 of the 30 stored artefacts being logos/screenshots, most pairs are
  mismatched by subject. This is inherent to replaying a folder with no labels;
  a metadata sidecar would fix it and is not present.
- **No product render meets a full white-background main brief** in this repo
  today: the 2000x2000 `smoke_main_2000.png` is the only product render at the
  required canvas, and it was paired with a lifestyle brief. That is a real
  finding for the picture lane, not a harness defect.
