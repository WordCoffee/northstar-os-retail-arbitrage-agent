# Spec — Listing Optimizer

**REBUILT.** No third-party code read or copied. Thresholds flagged **UNVERIFIED** where they are
conventional rather than confirmed.

## 1. Why it exists

Operator report: *"Listing optimization is weak. Bojo does not optimize an uploaded listing
properly, especially for SEO. It lacks required inputs and a scoring rubric."*

Northstar already had a *checker* (`listing_audit`) and a *scorer* (`seo_score`). It had no
optimizer: nothing rewrote the listing, and nothing enforced the backend byte limit.

## 2. Inputs

| Field | Status | Note |
|---|---|---|
| `keywords` | **required** | the only legitimate source of target terms; the agent refuses without them |
| `title` | required | current copy |
| `bullets` | required | up to 5 |
| `backend_terms` | optional | current backend field |
| `description` | optional | carried through, not rewritten |

## 3. Rubric (explicit, deterministic, 100 points)

Weights and character limits are **VERIFIED** against `nexscope-ai/Amazon-Skills`
(MIT, commit `0f3b13f`); citations in `research/amazon-skills/evidence.md`.

| Dimension | Weight | Measured by us? |
|---|---|---|
| title | 15 | **yes** |
| bullets | 15 | **yes** |
| images | 15 | no — needs an image set |
| A+ content | 10 | no — needs the A+ package |
| description | 10 | partial (carried, not scored) |
| pricing | 10 | no — needs a price/competitor read |
| reviews | 15 | no — needs review data |
| SEO coverage | 10 | **yes** |

The agent reports **all eight** and scores only the three it can actually measure from an upload,
reporting the rest as `not_measured` with the data each needs. Scoring a dimension we cannot see
would be the exact "graded an assertion" failure the studied skill has.

Hard limits enforced (not advisory): title ≤ 200 chars, each bullet ≤ **500** chars, description
≤ 2000, backend search terms ≤ **250 bytes** UTF-8.

## 4. Workflow

```
validate keywords        → refuse without them
audit before             → issues + coverage + score
rewrite                  → primary keyword leads the title; promo stripped; uncovered keywords
                           attached to bullets
clean_backend_terms      → drop words already visible, fit 250 bytes UTF-8
audit after              → issues + coverage + score
change log               → field, before, after, why
```

## 5. Byte-limit behaviour

Words are added in the operator's order; a word that would cross the limit is dropped and listed
in `dropped`. Words already present in the title or bullets are never repeated (they cost bytes and
buy nothing).

## 6. Edge cases

| Case | Behaviour |
|---|---|
| no keywords | `needs_input`, asks — never invents |
| empty title | flagged as an issue, not silently fixed |
| more than 5 bullets | truncated to 5 and reported |
| 200 candidate backend words | fitted, dropped list returned |

## 7. Known limits

- ~~The 200-char title / 250-byte backend values are conventional~~ — **verified** against
  Amazon-Skills, commit `0f3b13f` (see `research/amazon-skills/evidence.md`). The remaining
  conventions in this agent are the promo-word list and the "≤ 3 commas" title rule; those are
  ours, not Amazon's, and should be re-checked against current Amazon guidance before being
  presented as policy.
- No competitor-listing comparison yet (input accepted, not used).
- No image/A+ scoring in this agent; that belongs to the A+ agent.
