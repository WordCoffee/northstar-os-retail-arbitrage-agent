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
