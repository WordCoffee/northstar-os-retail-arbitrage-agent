-- Northstar OS Foundation — 1C-04 financial integrity (additive delta)
-- Phase: 1C-LC / owner-prioritized financial-integrity gate.
-- PURPOSE:
--   1. Scope the job-submission idempotency key to (organization_id, job_type,
--      idempotency_key) so the same key with a DIFFERENT request type creates a
--      NEW job (never a wrong replay).
--   2. Add audit_events.correlation_id so every audit record is correlated by
--      request ID (in addition to job ID / actor ID / timestamp).
-- ADDITIVE + reapply-safe for BOTH clean-room (001+002+003) and the
-- already-migrated staging DB. NOT APPLIED by any tool; reviewed step only.

BEGIN;

-- 1. Drop the legacy job_requests idempotency uniques (org-only), which would
--    otherwise reject the same key across job types.
DROP INDEX IF EXISTS "uq_job_requests_org_idem";
ALTER TABLE "job_requests" DROP CONSTRAINT IF EXISTS "job_requests_organization_id_idempotency_key_key";

-- 2. Create the (org, job_type, idempotency_key) unique — the mandatory
--    idempotency gate.
CREATE UNIQUE INDEX IF NOT EXISTS "uq_job_requests_org_type_idem"
    ON "job_requests" ("organization_id", "job_type", "idempotency_key");

-- 3. Audit correlation (request ID) column.
ALTER TABLE "audit_events" ADD COLUMN IF NOT EXISTS "correlation_id" TEXT;

COMMIT;

-- Compensating rollback (controlled rollback only; NOT executed autonomously):
--   ALTER TABLE "audit_events" DROP COLUMN IF EXISTS "correlation_id";
--   DROP INDEX IF EXISTS "uq_job_requests_org_type_idem";