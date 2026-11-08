# Seller-Tester (D9)

A harness that behaves like a seller using Northstar OS through Bojo: it takes a
product-picture brief, obtains an image from an injectable generator, scores the
image with deterministic code, files every failure as a gap, and escalates the
brief after a pass.

Everything is offline by default. No Amazon host is contacted, nothing is spent,
and no pixels are sent to a cloud model.

## Layout

| Module | Job |
| --- | --- |
| `briefs.py` | Load + validate `ty/seller_briefs.json` (32 briefs, 8 situations, 8 categories, tiers 1-3) |
| `scorers.py` | Pure PIL+numpy checks and the 0-100 subscore |
| `judge.py` | Optional vision adapter (local Ollama verifier only; OFF by default) |
| `generators.py` | `stored` replay adapter and documented local `comfy` adapter |
| `escalate.py` | Tier -> constraint -> new-category ladder + history |
| `gaps.py` | Gap records in `ty/seller_gaps.json`, mirrored to `state/seller/gaps.json` |
| `harness.py` | `run_pass` orchestration and summary |
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

`text_free` is a heuristic, not OCR: it detects overlay ink in the margin, so a
product that bleeds into the margin can be flagged. A vision judge is the
semantic second opinion, and it is never required for a score.

Score = weighted mean of the non-skipped checks (weights live in
`scorers.DEFAULT_WEIGHTS`, override per brief). A result passes when the score
meets `pass_score` and every `critical` check passes (default: dimensions,
aspect, background).

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
* `comfy` — probes `http://127.0.0.1:8188/system_stats` with a short timeout and
  refuses cleanly (`GeneratorUnavailable`) when ComfyUI is not up. It refuses
  non-loopback hosts at construction. It has no armed workflow: wiring one is a
  separate, operator-visible step. Nothing is retried or downloaded.

## Escalation ladder

After a pass: difficulty 1 -> 2 -> 3 (tighter fill/background, higher
`pass_score`), then one added hard constraint (`tight_background`,
`narrow_fill`, `file_size_cap_4mb`, `strict_text_free`), then a fresh brief in a
category the loop has not used. `escalate()` always returns a brief; the step is
recorded in `EscalationLog` (`state/seller/escalation.json` at runtime) and in
the run summary.

## Commands

```powershell
python -m tools.seller_tester catalog
python -m tools.seller_tester run --limit 30
python -m tools.seller_tester run --limit 5 --judge   # local vision only
python -m tools.seller_tester escalate --brief ST-010 --steps 6
python -m pytest Northstar_backend/test_seller_tester.py -q
```

`run` writes the full summary to `state/seller/last_run.json` (gitignored).
