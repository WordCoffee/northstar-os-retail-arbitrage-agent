# 16 — Town Crier Specification

Evidence states: STATICALLY_CONFIRMED (S) / INFERRED (I). Specification only.

## 1. Primary user job

Plan, create, approve, and (with scoped permission) publish social content with a consistent brand voice and shared intelligence.

## 2. Entry points

- `/towncrier` (overview/calendar), `/towncrier/studio`, `/towncrier/assets`, `/towncrier/calendar`.

## 3. Main workspace

| Section | Content |
|---|---|
| Brand Voice | shared voice profile (single store — resolves Phase 0 triplication), rules per brand |
| Calendar | content calendar: drafts, approved, scheduled, published |
| Content Studio | canvas-style: template selection, style/platform/audience/objective/theme/ratio/duration/tone controls |
| Assets | media library (images/video) |
| Campaigns | campaign groupings |
| Review queue | draft/review/approval states |

## 4. Studio workflow

1. Choose template (ad/organic/story/carousel/presentation/etc.) — template-first, not long-prompt-first.
2. Set controls: platform, style, audience, objective, theme, ratio, duration, tone.
3. Generate copy with brand voice + shared keyword/SEO intelligence (no parallel keyword universe).
4. Generate/attach media (image/video providers — gated).
5. Review (compliance + voice scoring; ethical safeguards + disclosure controls).
6. Approve → schedule → publish (gated external write).

## 5. Actions

| Action | Gate |
|---|---|
| Generate caption | local LLM (free) or cloud (gated) |
| Generate media | provider-gated (image/video) |
| Approve | approval flow |
| Schedule | draft row (no external write) |
| Publish | **external write — scoped approval** |

## 6. States

- Empty: "Connect a channel and set brand voice first".
- Provider failure: media/caption engine down → banner + last content; no fabricated assets.
- Permission denied: publish/approve require role/grant.

## 7. Responsive

Calendar → list on mobile; studio → single column.

## 8. Tour steps

1. Set brand voice.
2. Open studio, pick a template.
3. Generate a caption.
4. Review + approve.
5. Schedule.

## 9. Events

Emits: `social.drafted`, `social.approved`, `social.scheduled`, `social.published`, `social.asset.uploaded`. Consumes: `brand.voice`, `keyword.observed`, `brain.step_completed`.

## 10. Downstream

- Hub (social schedule widget), Account (connections), approvals module, notification on publish.
