# Spec — Amazon Image & A+ agent

**Status: spec only (agent not built).** Platform rules below are **VERIFIED**; module-layout
claims are **UNVERIFIED**.

## 1. Inputs

| Field | Status |
|---|---|
| `product` | required — name + Brand Kit entry |
| `shot_list` | required — which images to produce (main / lifestyle / infographic / size chart / comparison) |
| `plate_asset_id` | optional — an approved photo to edit rather than a synthetic render |
| `brand_key`, `keywords` | optional — binds copy and claims to the brand |

## 2. Platform rules — VERIFIED

Cite: `research/ecommerce-image-skills/capability-map.md` →
`xianyu110/ecommerce-image-skills`, `skills/amazon-white-background/SKILL.md`.
Enforced in code by `Northstar_backend/specialists/image_rules.py` (9 tests).

| Rule | Value |
|---|---|
| Background (main) | pure white #FFFFFF |
| Product coverage | ≥ 85 % of the frame |
| Longest side | ≥ 1000 px (zoom); 1600–2000 px recommended; max 10,000 |
| Format | JPEG preferred, sRGB |
| Content | product only — no text, badges, borders, watermarks, props |
| Presentation | whole product visible, in focus, true colour |

**Not enforced, therefore reported as `not_measured`:**
added text/badges/watermark (needs OCR), sRGB (needs an ICC read), sharpness/focus.

## 3. Product identity lock

Adopted from the same source, independently corroborating the Brand Kit:

```
PRODUCT IDENTITY LOCK (do not change):
- Shape & proportions
- Colour & finish
- Logo & printed text (exact spelling, position)
- Parts & details
- Must NOT appear
```

Unknown spec ⇒ ask or omit. Never invent a size, capacity, material or certification.

## 4. Shot list (the 12 studied skills → our deliverables)

| Our output | Studied counterpart |
|---|---|
| main image (white) | `amazon-white-background` |
| lifestyle scene | `lifestyle-scene` |
| selling-point infographic | `selling-point-infographic` |
| size chart | `size-chart` |
| multi-angle set | `multi-angle-set` |
| A+ module set | `amazon-a-plus` |
| ad/sale banner | `sale-banner` |

## 5. Workflow

```
shot list + identity lock      (never generate without both)
  → generate_image per shot    (local ComfyUI; no provider key)
  → check_main_image()         (main image only; other shots use custom checks)
  → report violations by rule  → regenerate or hand back to the operator
```

## 6. A+ content — UNVERIFIED

Module types and character limits were **not studied this pass** (no `amazon-a-plus/SKILL.md`
read, no Amazon documentation checked). The A+ package therefore remains spec-only until that
study is done. This is the largest remaining gap in the creative agents.

## 7. Validation and acceptance

- main image: `image_rules.check_main_image` returns `ok: true`
- every claim in an infographic traces to the Brand Kit (no invented certification)
- A+ modules: **cannot be accepted** until the module contract is studied

## 8. Improvement over the studied skill

The validator runs as part of acceptance, not as an optional script — a failing image is reported
with the exact rule it broke instead of being shipped with a caveat.
