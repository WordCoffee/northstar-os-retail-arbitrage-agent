# Seller-Tester (D9)

A harness that behaves like a seller using Northstar OS through Bojo: it takes a
product-picture brief, obtains an image from an injectable generator, scores the
image with deterministic code, files every failure as a gap, and escalates the
brief after a pass.

Everything is offline by default. No Amazon host is contacted, nothing is spent,
and no pixels are sent to a cloud model.

## The three inputs

The product-picture service takes exactly three inputs, and every brief declares
which one it starts from (`source_mode`):

| `source_mode` | Input | `reference` |
| --- | --- | --- |
| `prompt_only` | the seller's prompt alone | must be absent |
| `stored_reference` | a stored asset from an earlier generation under `renders/`, `generated_images/` or `Northstar_backend/data/studio_generated/` | `{kind: "stored_asset", path}` |
| `uploaded_reference` | a file the seller uploads | `{kind: "uploaded_file", descriptor: {filename, mime_type, subject}}` |

There is no fourth input. A brief that forgets its mode is bucketed as
`unclassified` (and fails scoring) instead of being folded into `prompt_only`.

## Layout

| Module | Job |
| --- | --- |
| `briefs.py` | Load + validate `ty/seller_briefs.json` (56 briefs, 3 input modes, 8 situations, 8 categories, tiers 1-3) |
| `scorers.py` | Pure PIL+numpy checks and the 0-100 subscore |
| `reference_check.py` | Reference fidelity: printed text (OCR), embedding agreement, colour as a diagnostic only |
| `judge.py` | Optional vision adapter (local Ollama verifier only; OFF by default) |
| `services.py` | The four non-image service paths, scored: listing, PPC, Golden Goose, research |
| `service_briefs.json` | The offline fixtures those four paths run against |
| `stray_report.py` | D-019: stray marks measured with code, plus the composed-page control |
| `generators.py` | `stored` replay, documented local `comfy` adapter, and the `composite` path |
| `scene_render.py` | Scene generation through a fresh `tools/comfy_lane.py` instance (SDXL / SD1.5 / FLUX 3) |
| `editor_bench.py` | Measures cutout methods on the Mogra uploads and writes the `editors` leaderboard row |
| `mogra_briefs.json` | The three real-upload briefs used by the composite proof |
| `escalate.py` | Tier -> constraint -> new-category ladder + history, inside one mode |
| `gaps.py` | Gap records in `ty/seller_gaps.json`, mirrored to `state/seller/gaps.json` |
| `harness.py` | `run_pass` orchestration, mode-balanced selection and summary |
| `cli.py` | `python -m tools.seller_tester ...` |

## Programmatic checks (no model)

| Check | What it measures |
| --- | --- |
| `dimensions` | exact or min/max width/height |
| `aspect` | width/height against the brief ratio, relative tolerance |
| `background` | median RGB of four corner patches vs the brief value (or skipped when `mode: free`) |
| `subject_fill` | share of pixels farther than `distance` from the corner-derived background |
| `alpha_matte` | real alpha cutout coverage, or a flat near-white border ring with low std |
| `file_size` | byte bounds plus a minimum bytes-per-pixel sanity floor |
| `text_free` | margin-ink heuristic (dark/saturated pixels in the outer 10% band) for `no_text` / `text_expected` |
| `reference_subject` | printed-text match (OCR both pictures, fuzzy token recall >= 0.60); embedding agreement when there is no text; colour agreement reported as a diagnostic, never a gate |

`text_free` is a heuristic, not OCR: it detects overlay ink in the margin, so a
product that bleeds into the margin can be flagged. A vision judge is the
semantic second opinion, and it is never required for a score.

`reference_subject` decides on evidence, in order: printed text (local ONNX OCR,
fuzzy token match), then an embedding agreement between the local vision model's
descriptions, and never colour (the 0.60 colour agreement is measured and
reported as a diagnostic only — a genuine pouch scored 0.603 while three
dark-green UI screenshots scored 0.637). It cannot verify when the reference is
missing, when the upload has no local copy, or when neither text nor a
description can be measured — and `cannot_verify` counts as a **failure**, never
a pass.

Score = weighted mean of the non-skipped checks (weights live in
`scorers.DEFAULT_WEIGHTS`, override per brief). A result passes when the score
meets `pass_score` and every `critical` check passes (default: dimensions,
aspect, background). For the two reference modes, `reference_subject` is forced
into `critical`, so good geometry cannot carry a picture that does not contain
the reference subject.

## Vision judge

Contract: `judge(image_bytes, rubric) -> {"pass": bool, "score": float, "reasons": [...]}`.

`local_judge` imports `Northstar_backend/agent_kernel/vision_verify.py` and asks
the local Ollama model one yes/no question. It is used only when
`NORTHSTAR_SELLER_JUDGE=1` (or `--judge`) is set, and it returns
`available: false` for any non-loopback `NORTHSTAR_VISION_URL`. Unavailable is a
skip, never a pass. Tests inject `FakeJudge`.

## Generators

* `stored` (default) — deterministic replay of existing artefacts under
  `renders/`, `generated_images/` and `Northstar_backend/data/studio_generated/`.
  Brief *i* is paired with artefact *i*, so one pass covers the catalog axis.
  It does **not** edit a reference and does not generate: a reference-mode brief
  replayed against an unrelated artefact is expected to fail the
  `reference_subject` check, and the summary says so.
* `comfy` — probes `http://127.0.0.1:8188/system_stats` with a short timeout and
  refuses cleanly (`GeneratorUnavailable`) when ComfyUI is not up. It refuses
  non-loopback hosts at construction. It has no armed workflow: wiring one is a
  separate, operator-visible step. Nothing is retried or downloaded.
* `composite` — the real-product path. `fidelity` decides: `exact` (and every
  reference brief that does not say otherwise) cuts the product out of the
  reference and composites it into a generated scene; `tolerant` and every
  `prompt_only` brief are fully generated. The scene comes from a fresh
  `tools/comfy_lane.py` instance that stops and proves it stopped; BiRefNet runs
  inside that same lane. A refused lane is `GeneratorUnavailable` — no artefact,
  no replayed image, and a synthetic backdrop (when explicitly requested) is
  `cannot_verify`, never a pass.

## Selection and summary

`select_briefs` samples round-robin across `prompt_only`, `stored_reference` and
`uploaded_reference` (catalog order within a mode), so `run --limit 40` cannot
score one input mode and report it as coverage. `--mode` restricts a pass to one
input.

The summary carries `source_mode` on every result, `by_mode` grouped counts (all
three modes always present, `scored: 0` when a mode had no outputs),
`catalog_by_mode` declared counts, and `selected` / `scored` / `not_scored` so a
generator with fewer artefacts than the pass selected is visible rather than
silent.

## Escalation ladder

After a pass: difficulty 1 -> 2 -> 3 (tighter fill/background, higher
`pass_score`), then one added hard constraint (`tight_background`,
`narrow_fill`, `file_size_cap_4mb`, `strict_text_free`), then a fresh brief in a
category the loop has not used. The ladder stays inside the brief's input mode:
a `stored_reference` brief never escalates into a prompt-only brief, and a new
reference brief keeps a reference. `escalate()` always returns a brief; the step
is recorded in `EscalationLog` (`state/seller/escalation.json` at runtime) and in
the run summary.

## Beyond images: the four service paths

A seller does not only buy pictures. `services` walks the four non-image paths a seller
actually uses, each against a real code path and a local fixture, and scores each one with
named checks (the share of graded checks that passed; a skip is never a pass):

| path | the path it exercises | what is checked |
| --- | --- | --- |
| `listing` | `bojo_tools.publishing.compose_listing` -> `reasoning_tasks.listing_proposal`, the function behind `POST /api/v1/reasoning/listing-proposal` | title ≤ 200, 3-5 bullets ≤ 500, description ≤ 2000, no prohibited phrase, copy audit clear, no invented number, reasons + provenance recorded, never applied |
| `ppc` | the bulksheet API: upload -> propose -> approve -> write -> download | kind/rows parsed, sheet detected, before/after bid, unblocked, approved, v1 written, round-trip ok, a second write is a new v2 file, the download hashes to the written checksum, the original is untouched |
| `golden_goose` | `bojo_tools.sourcing.golden_goose_scan` (real fee stack + real scorer) | every candidate evaluated, REJECT dropped, descending rank, filters reported, economics present, "why" recorded, thresholds echoed |
| `research` | `research_graph.research` (deconstruct -> traverse -> cross-validate) | three axes, evidence returned, distinct sources, corroboration counted, single-source claims labelled, a numeric disagreement surfaced as a conflict, headline leads with the count, no web crawl claimed |

The listing path's model answer is a **recorded fixture**: a live reasoning call is a paid
action. Every deterministic step applied to it — the limits, the prohibited-phrase list, the
copy audit, the provenance record — is the app's own. The other three paths are real end to
end, and none of them contacts a network.

```powershell
python -m tools.seller_tester services
python -m tools.seller_tester services --only ppc,golden_goose
```

`--only` takes a comma list from `listing,ppc,golden_goose,research`; an unknown name is
refused by name. The proof lands in `state/seller/services_proof.json`, per-path artefacts
in `state/seller/services/<path>/`, and every refusal is recorded with its reason.

## Stray marks (D-019)

`check_stray_marks` measures "is the picture free of stray marks" the way a seller means
it — a small, detached, stroke-like object on or beside the product — and it asks it of the
right population:

* a **photograph** is measured on the frame, against the product's recorded silhouette;
* a **composed page** (`infographic`, `packaging_mockup`, laid out by
  `deterministic.infographic`) is measured **inside its photo panel**, because its accent
  rule, headings, callout chips, leader lines and anchor dots are the layout, not strays.

It is skipped — never passed — when no silhouette was recorded, or when the background is
not a field (a gradient scene cannot separate a mark from the scene). It is recorded as a
**diagnostic** (`stray_marks`) and has no weight, so no published score moves for it.

```powershell
python -m tools.seller_tester.stray_report            # the twelve prompt-only artefacts
python -m tools.seller_tester.stray_report --json --out state/seller/d019.json
```

## Commands

```powershell
python -m tools.seller_tester catalog
python -m tools.seller_tester run --limit 40            # all three input modes
python -m tools.seller_tester run --limit 12 --mode stored_reference
python -m tools.seller_tester run --limit 5 --judge     # local vision only
python -m tools.seller_tester escalate --brief ST-034 --steps 6
python -m tools.seller_tester composite --limit 3   # real cutout + generated scene
python -m tools.seller_tester services               # the four non-image paths
python -m tools.seller_tester.stray_report           # D-019, measured with code
python -m tools.seller_tester editor_bench --with-lane   # cutout leaderboard
python -m pytest Northstar_backend/test_seller_tester.py \
    Northstar_backend/test_seller_tester_composite.py -q
```

`run` writes the full summary to `state/seller/last_run.json` (gitignored).
