STATUS: PENDING

# BATCH 06 — Master Brain Gateway Groundwork (Offline, Additive Only)

Prerequisite: Batches 01–05 complete and approved. This batch does NOT build a live
executor — structure and classification only.

## Step 1 — Confirm or create the shared constitution scaffold
- Check whether `shared/master-brain/` already exists from a prior session. If not,
  create it with: `constitution.json` (universal, product-neutral rules — no T2/Kirkland
  specifics), and a `packs/` directory for domain-specific context packs
  (`t2-holdings-operations.json`, `northstar-os-commerce.json`, `northstar-provider.json`,
  `autothink-engineering.json`, `platform-admin.json`).
- Do not duplicate T2-specific rules already correctly embedded in
  `Northstar_backend`/`AGENTS.md` — reference them instead of restating.

## Step 2 — Deterministic task classifier (no LLM calls)
- Add or confirm a simple, rules-based function that labels an incoming task string
  into one of: `AUTOTHINK_RESEARCH`, `AUTOTHINK_CODE`, `AUTOTHINK_COMPUTER`,
  `NORTHSTAR_OS_COMMERCE`, `NORTHSTAR_OS_PROVIDER`, `T2_OPERATIONS`, `PLATFORM_ADMIN`.
- Keyword/pattern-based only — no model call, no network call.

## Step 3 — Append-only audit log stub
- Add a minimal audit logger (JSONL, append-only) recording: timestamp, classified
  track, files touched (if any), whether a live action was requested, and approval
  status. This batch does not trigger any live action — it just proves the logging
  mechanism works.

## Step 4 — Offline tests
- Add tests for the classifier (a handful of representative strings per track) and for
  the audit-log writer (confirm it appends correctly and never overwrites prior
  entries).

## Step 5 — Run and report
- Run the new test file(s) plus the full suite.
- Confirm zero live calls, zero secret exposure, and no protected file changes.

## End of batch
Update `00_STATE.json`: move this batch to `completed_batches`, set `next_batch` to
`07_docs_and_runbook.md`, append history, stop for approval.
