# 15 — OfferChisel Specification

Evidence states: STATICALLY_CONFIRMED (S) / RUNTIME_CONFIRMED (R) / INFERRED (I). Specification only.

## 1. Primary user job

Generate new listings and optimize existing listings with verified product facts, shared SEO intelligence, brand voice, compliance, and evidence-backed output.

## 2. Entry points

- `/offerchisel` (workspace).
- From a product record (`/prospector/:productId` → "Write listing").
- From Golden Goose opportunity → "Draft listing".
- Deep link `/offerchisel/:productId`, `/offerchisel/:productId/versions`.

## 3. Workflow

1. **Resolve product** — accept ASIN/UPC/URL/SKU/supplier record/product name; resolve via canonical product identity; refuse generation on ambiguous/unknown product.
2. **Verify facts** — gather product facts from canonical record (pack, brand, attributes) + evidence; never invent attributes.
3. **Import existing listing** — when authorized (Amazon listing read, if scoped permission granted); otherwise user paste.
4. **Audit** — title/bullets/description/backend terms/images/A+/attributes/compliance; list issues.
5. **Research keywords** — shared keyword graph (Search Term intelligence); no parallel keyword universe (Phase 0 R2).
6. **Generate draft** — title/bullets/description/backend terms; brand voice from shared store; compliance screening; SEO scoring; source evidence + confidence.
7. **Review** — versioning, comparison, approval, export.
8. **Publish** — gated external write (requires approval; owner decision `00`).

## 4. Main workspace

- Left: input/context (product, brand voice, keywords). Center: generated draft (editable). Right: evidence + confidence panel + compliance check.

## 5. Detail view (`/offerchisel/:productId`)

- Listing record + versions timeline; audit results; keyword associations; SEO score history; approval state.

## 6. Actions

| Action | Gate |
|---|---|
| Generate draft | local LLM (free local) or cloud (gated provider) |
| Regenerate section | same |
| Audit listing | reads (gated import if Amazon) |
| Version compare | none |
| Approve draft | approval flow |
| Export | none |
| Publish | **external write — requires scoped approval** |

## 7. Approval points

- Publish (Amazon listing write) — scoped permission + diff preview + audit.
- Cloud model usage above budget.

## 8. States

- Empty: "Select a product or paste a URL".
- Partial data: missing facts shown unknown; generation flagged low-confidence where facts missing.
- Stale: keyword data as-of timestamp.
- Provider failure: local engine down → banner "engine unavailable"; template fallback only with explicit label (Phase 0 finding: silent template fallback must be labeled).
- Permission denied: publish/import require role/grant.

## 9. Responsive

Three-pane → stacked panes on mobile; editor full-width.

## 10. Tour steps

1. Resolve a product.
2. Review facts + evidence.
3. Generate a draft.
4. Check compliance + keywords.
5. Compare versions / request approval.

## 11. Events

Emits: `listing.drafted`, `listing.version.created`, `listing.approved`, `listing.published`, `listing.audited`. Consumes: `keyword.observed`, `product.updated`, `brand.voice` (shared store), `economics.computed`.

## 12. Downstream

- Auctioneer (keyword/share), Town Crier (brand voice), RankLedger (keyword associations), Hub (listings-needing-attention), SEO graph (listing performance feed-back).
