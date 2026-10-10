# Design Studio ? Phase Checkpoint

## Phase 0 ? MERGE ? COMPLETE (21/21)
## Phase 1 ? DEEP RESEARCH ? COMPLETE (GATE 1 approved), 169 sources
## Phase 2 ? DESIGN SYSTEM + 9 WORKSPACES ? COMPLETE
## Phase 3 ? AI DISCLOSURE, FIDELITY, FRESHNESS, PERSISTENCE ? COMPLETE

### 1. AI-GENERATED PEOPLE DISCLOSURE (directive item 1, a-h)
New module `studio/engine/disclosure.js`.

(a) **Six classifications, NO DEFAULT.** no-people / real-only /
    real-ai-altered / ai-photoreal (TAG REQUIRED) / non-photoreal /
    expressive-work. An unanswered asset reports `needs-confirmation` and
    export is blocked.
(b) **CONFLICT detection.** If the studio generated the person, an answer of
    "no people" or "expressive-work" is a CONFLICT and export is blocked.
    A tag-required class with the marker switched off is also a conflict.
(c) **Attestation.** user, timestamp, asset version (fingerprint over format,
    size, classification, generation flag, last edit, bytes) and the exact
    statement. ANY edit changes the version and RE-REQUIRES the attestation.
(d) **Real XMP write + read-back.** `buildXmpPacket`, `embedXmpInPng` (iTXt
    chunk with a real CRC32), `embedXmpInJpeg` (APP1 segment), `readXmpFromPng`,
    `readXmpFromJpeg`, and `verifyDisclosureMarker` which reads the EXPORTED
    bytes back and proves the exact keyword survived. 7 export paths declared
    (native, resize, re-encode, format change both ways) and all 7 tested.
    Source: G1881 + the GFXHCHYZRGJRBZA5 announcement.
(e) **Scope labelled honestly.** Listing images / listing videos / A+ basic are
    VERIFIED. Premium A+, Brand Story, Store images and videos, shoppable or
    product video, and ad creative are REPORTED because the GFXHCHYZRGJRBZA5
    page and the Ads page GP6Y2AE2BUM5XWFX are login-gated.
(f) **Ads checklist.** All three documented paths recorded: Amazon displays
    automatically when it created the creative; the advertiser selects
    "Contains synthetic performers" at upload for externally-made creative; the
    advertiser places the disclosure directly in the creative for
    third-party-served formats. The conspicuousness warning states the XMP
    marker is NOT the New York disclosure. Jurisdiction scope is date-sensitive.
(g) **Pre-flight row** "AI-generated people disclosure" reports
    Decided / Needs seller confirmation / Conflict and is never green until
    answered. The UI states plainly that the studio cannot detect AI people
    from pixels.
(h) **Fixtures:** every classification x 7 surfaces, the conflict path, the
    marker surviving all 7 export paths, the negative case (untagged file
    fails), the near-miss keyword failing, and edit re-requirement.

### 2. MAIN IMAGE + ALL IMAGE RULES (directive item 2) ? all "needs artwork"
Added 10 rules: main-entire-product (cropped), main-shown-once (same asset
twice), main-single-unit, main-no-props, main-no-packaging, main-no-mannequins,
main-no-amazon-marks (Amazon's Choice / Best Seller), all-no-review-imagery,
all-no-pricing, all-no-seller-info (URL / email / phone / handle).
The pre-existing main-white-bg and main-fill plus 85% and the overlay set remain.

### 3. IMAGE TECHNICAL RULES (directive item 3)
Added dpi-min-72, color-space-rgb, and filename-pattern (ID.VARIANT.ext).
raster-range (500-10,000) and raster-zoom (1,000+) already existed; the accepted
formats (JPEG/TIFF/PNG/non-animated GIF) are enforced by format-accepted.

### 4. ISOLATION NEGATIVE TESTS (directive item 4)
New `GET /api/design-studio/search` and `GET /api/design-studio/projects/{id}/
export-manifest`, both account-scoped. Tests added for list (all three stores,
both directions), search (a shared token returns exactly one hit per tenant),
and export (a foreign project is refused), plus a router-discipline check that
now resolves 26 scoped call sites with zero unscoped DAO calls.

### 5. MIGRATION END-TO-END (directive item 5)
`tools/test-migration-e2e.cjs` seeds 7 realistic legacy keys into a real
browser, runs the real migration, and asserts the import, idempotency, the
lossless preservation of unmapped fields, and that the store returns to 0/0/0.
**It found four real bugs, all fixed:**
 1. `_existing_legacy_keys` only scanned PROJECTS, so assets and jobs were
    re-created on every run ? the advertised idempotency did not hold.
 2. `ds_jobs` had no `metadata` column, so a migrated job had nowhere to record
    its legacy key. Added via an idempotent ALTER.
 3. The CLIENT mapped only a handful of named fields, so unmapped legacy data
    (objective, deliverables, purpose, tier) never reached the server at all.
 4. The client cleared a key whose content it could NOT represent. A malformed
    or unrepresentable key is now KEPT and reported, and the done flag is
    withheld so the operator can retry it.

### 6. FIDELITY TRACK (directive item 6)
New module `studio/engine/fidelity.js`. Reference lock + real-photo
compositing with a pure `regionDiff()` (mean per-channel difference against a
6% threshold, plus a 45% worst-pixel tripwire, transparent pixels skipped) and
a browser `verifyFidelity()` that reads the exported region and blocks beyond
the threshold. Three fidelity modes: locked (enforceable), placed (UNVERIFIED,
reported as such), generated (BLOCKING ? the product is never generated).
A compositing contract documents the required order.

### 7. SAMPLE SIZE BESIDE EVERY WORKFLOW CLAIM (directive item 7)
`claim()` refuses to make a claim with no sample size rather than softening the
wording; `sampleLabel()` labels a zero sample as "no sample". The 60-transcript
target is NOT claimed anywhere ? the corpus holds one transcript.

### 8. POLICY FRESHNESS REGISTER (directive item 8)
Every source carries a re-check cadence by tier (critical 30d / high 60d /
normal 180d / slow 365d) with a stated reason. `freshnessOf`, `freshnessReport`
and `ruleFreshness` return current / due-soon / stale / unregistered. Every rule
result carries a freshness verdict, and an UNREGISTERED source is never "current".
Two bugs found by the test: an empty reason, and `ruleFreshness` reporting
`current` for an unknown source.

### Verification ? 7 harnesses, full output, FATAL counted
| # | Harness | Result | Exit |
|---|---|---|---|
| 1 | `test-compliance-rules.mjs` | **98 passed, 0 failed**; 47/47 rules, 13/13 groups, 48 specs sourced, 0 unsourced | 0 |
| 2 | `test-disclosure.mjs` | **39 passed, 0 failed** | 0 |
| 3 | `test-fidelity-freshness.mjs` | **34 passed, 0 failed** | 0 |
| 4 | `test_design_studio_isolation.py` | **25 passed, 0 failed** | 0 |
| 5 | `test_login_throttle_bypass.py` | **16 passed, 0 failed** | 0 |
| 6 | `check-jsx-imports.py` | 94 files, 0 undefined, 0 unguarded | 0 |
| 7a | `verify-design-studio.cjs` | **67 passed, 0 failed, 0 FATAL** | 0 |
| 7b | `test-migration-e2e.cjs` | **12 passed, 0 failed, 0 FATAL** | 0 |
| 7c | `verify-operator-smoke.cjs` | **11 passed, 0 failed**, 21/21 rail | 0 |

### Generation status
**UNARMED.** No live or paid call. No cron. No on-load provider request.

### Files touched
- `studio/engine/disclosure.js` (new), `fidelity.js` (new)
- `studio/engine/specRegistry.js` (9 new sources, freshness register)
- `studio/engine/compliance.js` (13 new rules, freshness on every result)
- `studio/engine/migrate.js` (lossless client, keep-unimportable)
- `pages/internal/design-studio/SectionWorkspace.jsx` (shared fields + rules)
- `Northstar_backend/design_studio_api.py` (search, export-manifest, migrate fix)
- `Northstar_backend/data_layer.py` (ds_jobs.metadata + migration)
- `tools/{test-disclosure,test-fidelity-freshness,test-migration-e2e}.*` (new)

## Resume at
Phase 3 remainder: the sections still hold no artwork (they render the format,
safe zones, shared fields and the pre-flight). Next: arm the local ComfyUI
pipeline behind explicit Run + cost preview, and give the canvas a real
compositing surface so the fidelity check has an export to measure.
