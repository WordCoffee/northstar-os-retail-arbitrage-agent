# ASSUMPTIONS LOG

Conservative defaults and decision mappings logged per the Northstar OS
constitution (Section on assumptions). Unknown stays UNKNOWN; these are not
legal advice. Each entry records the decision, the reason/evidence basis, and
the owning blocker (typically OA-7).

---

## 2026-09-30 — P4-T3b data-rights wiring (Golden Goose / customer boundary)

### A-01 Golden Goose items are internal derived records, NOT raw third-party rows
- **Decision:** Do not globally block Golden Goose (or Product Finder) merely
  because a record carries `source: "import"` or lacks a registered source key.
- **Reason:** Those records are internally produced, org-scoped opportunity
  records. Blocking them wholesale would break the product and misclassify
  them as raw third-party data. Policy #5.
- **Status:** `explicit_source_key()` returns None for unproven labels
  (`import`, `wordsample`, etc.); no CUSTOMER_OK label is inferred.

### A-02 Registered provenance only when present literally
- **Decision:** A registered source key is attached only when a row/payload
  literally carries one of `source` / `source_key` / `provenance_source`
  equal to a registered key (SellerSprite, Amazon catalog records, Costco
  discovery, PalletFly, manual observed capture, or another registered key).
  Never invented from URL evidence or arbitrary labels. Policy #2.
- **Status:** enforced in `data_rights.explicit_source_key()`.

### A-03 Raw embedded payload is never returned to customer-facing callers
- **Decision:** GG item API responses expose derived scalar columns only;
  the raw `payload_json` blob (which may embed restricted third-party source
  fields such as `source_url`, deep observations) is dropped via
  `golden_goose_store.project_item()`. Policy #5.
- **Status:** wired into golden-goose queue + GET routes; verified by tests.

### A-04 INTERNAL_ONLY / PROHIBITED / UNKNOWN rows are blocked from customer display
- **Decision:** Registered INTERNAL_ONLY/PROHIBITED/UNKNOWN sources are not
  displayed to customer roles, not exported, not aggregated cross-tenant, and
  not sent to external AI/providers. `customer_display_allowed`, `export_allowed`,
  `assert_customer_display`, `assert_export`, `assert_external_ai`, and
  `customer_safe_rows` / `export_safe_rows` enforce this. Policy #3.
- **Status:** helpers existed; this slice added the provenance extraction used
  to route rows to the correct filter for GG payloads. Export/cross-tenant/AI
  surfaces do not yet serve third-party data (none exist), so those boundaries
  remain armed-but-untested until such a surface lands.

### A-05 manual_observed_capture (CUSTOMER_OK) retained subject to role controls
- **Decision:** Explicit `manual_observed_capture` rows may remain available to
  customers/export subject to normal org/role controls. Policy #4.
- **Status:** register asserts CUSTOMER_OK for display/export.

### A-06 OA-7 remains the owner/legal blocker
- **Decision:** All third-party customer/export/redistribution/AI use hinges on
  OA-7 (written permission or counsel note). This slice enforces conservative
  defaults (block nothing that is unproven, block all registered
  INTERNAL_ONLY/UNKNOWN third-party data) but does not grant any additional
  rights beyond the register. Not legal advice.
- **Status:** OPEN blocking card OA-7.

---

## 2026-09-30 — Item 3: Golden Goose Top-5 scheduler / snapshot evidence-based scope

### A-07 Scheduler core IS implemented and green; the monthly schedule is NOT auto-created
- **Decision:** The persisted scheduler (`jobs_scheduler.py`) is fully
  implemented (enqueue-only, atomic occurrence claim, idempotent, concurrency
  policy, misfire window, org-suspended/owner-revoked guards, org isolation,
  GET-never-ticks, and it NEVER executes jobs or calls providers). Verified
  41/0 (jobs + scheduler + worker) plus the new evidence-backed
  `test_monthly_top5_operator_schedule_path` (top5 suite now 6/0).
- **Decision (scope):** No default monthly cron cadence is invented or seeded.
  A `golden_goose.monthly_top5` schedule is only created when an operator
  explicitly opts in via the scheduler API with an explicit cron/interval and
  `enabled=true` (provider-backed schedules default disabled). There is no
  spec/schema/test that mandates a particular cadence, so we do not invent one.
- **Status:** `golden_goose.monthly_top5` handler registered (deterministic,
  local, free, idempotent, requires explicit `candidates`). Scheduler = PARTIAL
  relative to a "fully auto-tuned monthly recap" — the engine + handler are
  done; a turnkey out-of-the-box monthly schedule and real
  candidate-source wiring (depends on P4-T1 coverage) are UNKNOWN/not implemented.

### A-08 Snapshot "payloads"/retention/deletion are NOT invented
- **Decision:** What is evidenced as a snapshot-with-version mechanism is the
  org-scoped `golden_goose_decisions` table (persists `decision_state`,
  `purchase_ready`, `scorer_version`, `inputs_hash`, `payload_json`). No
  additional snapshot schema, retention window, or deletion policy is added,
  because none is specified in requirements/schema/tests. Marking those as
  UNKNOWN; logged as a blocker if a turnkey snapshot product is expected.
- **Status:** Store unchanged in this slice (only `project_item`/derived view
  added under P4-T3b).

### A-09 Candidate source depends on P4-T1 coverage
- **Decision:** `select_top5` requires an explicit `candidates` list in the
  payload. Automatic candidate population from live source pipelines is not
  implemented and is out of Item 3 scope (depends on P4-T1 coverage).
- **Status:** documented; not stubbed with fabricated sources.

