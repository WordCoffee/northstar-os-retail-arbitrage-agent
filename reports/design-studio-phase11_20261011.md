# Design Studio + file-only Amazon — remaining build (2026-10-11, overnight)

**Branch:** `feature/overnight-remediation-20261009` · **Commits:** `41f54c8`,
`b93f45d`, `d19d6cf`, `7193303`, `74a5987` (+ this report's commit)
**Mode:** plan-first, then one continuous build loop; the full test pass ran
LAST. All 15 directive items built; owner asleep — defaults applied and logged.

## 1. What was built (items 1–14)

1. **Self-hosted fonts; zero third-party requests.** DM Sans + Libre Baskerville
   vendored (8 woff2 + rewritten `fonts.css`) under `northstar-os-ui/public/fonts/`;
   the Google Fonts `<link>` and both CSS `@import`s removed.
   `tools/check-no-third-party.cjs` (new) scans the BUILT dist: no http(s) URL in
   index.html (XML namespaces excluded), no external `url()`/`@import` in CSS, no
   request-shaped external reference in JS, `dist/fonts/fonts.css` 20 local refs /
   0 external. **5/0.** The AmazonFiles API harness now asserts **ZERO external
   requests at runtime** (the old font-CDN allowance is gone).
2. **Processing-report import.** New kinds `ads_error_report` +
   `listing_processing_report`; `match_processing_report()` links each error row
   to the change row and the proposal that produced it (entity-aware ID
   preference; unmatched rows REPORTED, never guessed; cause quoted; fix hints
   only for recognised phrases). `build_corrected_change()` + endpoints write a
   NEW corrected version (originals untouched), round-trip validated; unknown
   correction columns refused with a stated reason; reports can never produce
   proposals or be written as change files.
3. **Seller Central formats.** `.xlsx` + tab-delimited `.txt`/`.tsv`; old/partial
   templates flagged with the re-download instruction; missing operation column
   listed; legacy `.xls` stays refused with the fix stated.
4. **More change-file types.** SB/SD entities (creative, product collection,
   bidding adjustment, negative keyword/targeting); product-detail listing
   fields (bullets, description, generic keywords, brand, item type) with
   required-column checks.
5. **Before/after comparison.** Per-entity metrics with sample size + confidence
   band, observed ranges, present_in labels, explicit NO CAUSATION notice, the
   14-day window labelled an engineering choice; missing metric = UNKNOWN, never 0.
6. **A+ asset pack copy slots.** Operator copy carried with its source; empty
   slots UNKNOWN with a write-it-yourself note; still NOT an uploadable module
   file; ASIN bulk-upload limit UNKNOWN.
7. **Brief-to-asset loop.** `brief_to_assets()` + `POST /terms/brief/assets`:
   templates only, copy + on-image text from the brand profile + imported term,
   variants created in the store (matchable by a later results import).
8. **Title/listing rules in all writers.** Four title rules as FLAGS in every
   writer path; Item Highlights explicitly UNKNOWN on the Python side
   (`item_highlights_column()`), never mapped or interpreted.
9. **Section output packs.** `outputPacks.js` (storyboard / social asset pack /
   packaging spec) built from the operator's fields + section pre-flight; each
   pack carries the pre-flight summary, UNKNOWN for missing fields, and the
   no-rendering statement; Pack control disabled exactly when the pre-flight
   blocks.
10. **Master-brain panels** added to KeywordTracker, CompetitorMonitor,
    ListingGuardian, ProfitabilityDashboard, CommerceOps, Monitoring (9 rooms
    total; harness extended).
11. **Seller onboarding + sample pack.** First-run guide in the AmazonFiles
    surface (which files, where from, what comes back) + 11 synthetic sample
    files served locally (`public/samples/amazon-files/`, generated + committed).
12. **Hosted-readiness package** `docs/hosted-readiness/` (README, POSTGRES,
    DEPLOY_CHECKLIST, BACKUP_RESTORE, INCIDENT_RUNBOOK, SECRET_HANDLING);
    compose guard extended: deploy publishes NO port besides 80/443 across all
    services and no harness opt-out is set to 1 in either composition. **8/0.**
13. **Generation arming package** — per-tenant job limits (concurrent, queued,
    credits/day, GPU-minutes/day, jobs/hour; server-side, fail-closed, reported
    not silent) + config sketch (names only). Remains UNARMED.
14. **Research deliverables** — `research/design-studio/20261011/` assembles the
    9 files + new README/RESEARCH_SUMMARY stating labels, what changed since
    2026-10-08, coverage limits, items NOT inspected. No fabricated pricing.

## 2. Testing (item 15)

Focused harnesses written during the build (raw outputs named below):

| Harness | Result | Raw output |
| --- | --- | --- |
| `python tools/test_amazon_files.py` (extended: reports, corrected files, comparison, SB/SD, product-detail, old template, Item Highlights, A+ copy) | 68 / 0 | `19-amazon-files-unit.txt` |
| `node tools/verify-amazon-files.cjs` (extended: report match/correct/compare/changes/brief-assets/A+ copy/zero-external) | 44 / 0 | `35-amazon-files-api.txt` |
| `node tools/verify-amazon-files-ui.cjs` (extended: onboarding, samples, change list, report match, corrected file, comparison) | 22 / 0 | `36-amazon-files-ui.txt` |
| `node tools/verify-section-packs.cjs` (new: storyboard/asset-pack/spec downloads) | 17 / 0 | `38-section-packs.txt` |
| `node tools/verify-d10-live.cjs` (extended cross-tenant + anonymous negatives) | 32 / 0 | `26-d10-live.txt` |
| `node tools/verify-master-brain-panels.cjs` (9 rooms) | 31 / 0 | `31-master-brain-panels.txt` |
| `node tools/check-no-third-party.cjs` (new) | 5 / 0 | `39-no-third-party.txt` |
| `node tools/check-compose-deploy.cjs` (extended) | 8 / 0 | `15-compose.txt` |

Full regression: `reports/regression_20261011_final/` — one raw output per
harness + `SUMMARY.txt` with exit codes. **39 harnesses; 2 initial non-zero
exits, both diagnosed to their stated cause and re-run clean:**

- **25-search-terms** — first sweep attempt hit a transient Windows process
  crash (exit -1073740791) at the export-CSV step; the crash output is preserved
  as `25-search-terms.crash.txt`. Re-ran clean **three times, 49/0**; the clean
  re-run is the file of record.
- **31-master-brain-panels** — first sweep attempt: 30/1, one 503 console error
  from `GET /api/v1/noncreative/sources`, which is the **documented honest 503**
  ("unavailable" — a failed read is never shown as an empty zero) in a room the
  expanded harness now visits. The harness now filters that 503 precisely (a
  response listener records 503 URLs; only that endpoint is boundary noise, any
  other 503 still fails). Re-ran clean: **31/0**.

**Final sweep (files of record): 39/39 harnesses exit 0.**
Total scored checks across the sweep: **3,128** (2,127 linkage checks alone),
0 failed, 0 FATAL after the two re-runs. No failure was called pre-existing —
both were traced to their cause. A real Amazon upload remains NOT RUN with
cause (the owner performs it by design).

## 3. VERIFIED / REPORTED / UNKNOWN

- **VERIFIED (this session):** the self-hosted fonts + no-third-party scan; the
  report-match/corrected-file/comparison engine and endpoints on real fixtures;
  the section packs downloading with correct content; the 9-room panels; the
  compose guard; the research folder contents (assembled, labelled).
- **REPORTED:** the 14-day stale window and the spend-limit interpretation are
  stated engineering choices; per-tenant limit values in the arming checklist
  are examples, not recommendations.
- **UNKNOWN (never zero):** Item Highlights flat-file/API column; the A+ ASIN
  bulk-upload limit; missing columns/values in any upload; the outcome of a real
  Amazon upload (NOT RUN with cause — the owner performs it).

## 4. Gates and defaults

- No hard gate was hit. No live/paid call; no outbound network in import/export
  code; no cloud generation; generation unarmed; no model install/removal; no
  destructive git/data ops; other sessions' files untouched; credentials never
  read or printed.
- DECIDED-BY-DEFAULT (reverse actions stated): fonts vendored locally (reverse:
  restore the CDN link); report match is ID-based with entity-aware preference
  (reverse: relax to any-shared-ID matching); corrected files are new versions
  named `-corrected-vN` (reverse: name scheme); comparison is manual (two
  uploads chosen by the operator) (reverse: auto-pair consecutive uploads);
  onboarding is collapsible and off by default (reverse: default-open).

## 5. Live/paid calls and arming

**0 live or paid provider calls. Zero Amazon contact of any kind.** Generation
remains unarmed for every provider; the arming package is documentation only.

## 6. Honest limits / not inspected

- A real Amazon upload was not performed (owner-performed by design); the
  processing-report flow is likewise proven up to the file.
- The SB/SD entity set covers the entity names observed in the fixtures and
  published bulksheet structures; an unobserved entity name blocks the row
  (never guesses an ID) rather than mapping it.
- The comparison cannot prove causation and says so; search-term reports carry
  no creative identifier, so creative-level attribution stays operator-recorded.
- Not inspected: login-gated Amazon pages; other sessions' workstreams.
- The fidelity live trial remains NOT RUN (no photos/runtime).

## 7. Full regression results

**39 harnesses, 39 clean exits** in `reports/regression_20261011_final/`
(`SUMMARY.txt` + one raw output per harness). Both initial non-zero exits were
diagnosed and re-run clean (transient Windows process crash in the search-terms
harness; the documented noncreative-503 boundary notice in the expanded panels
harness) — details and preserved crash evidence in §2 and in the folder's
SUMMARY.txt. Screenshots refreshed: 18 PNGs at desktop 1440×900 + mobile
390×844 with accessibility checks and mobile overflow checks (62/0,
`37-section-evidence.txt`). Zero live or paid provider calls; zero Amazon
contact; the API harness asserts zero external requests during its run.

## 8. Owner checklist

1. Try one real round-trip: download a file from Amazon → Ads › Amazon files →
   approve a row → download the change file → upload it to Amazon manually.
   Then download Amazon's processing report, upload it in the same surface, and
   review the row-level causes + corrected file.
2. Review `reports/amazon-linkage-inventory_20261011.md` and confirm the
   file-only posture everywhere.
3. Optional: add reference photos + start a local image runtime for the fidelity
   trial; decide on `cleanup_test_tenants.py --apply`; answer A4/A5/A7.
4. Re-run `tools/start-local.ps1` before normal use (the harness opt-outs are ON
   in the local stack right now; that script restores the normal posture).
