-- Northstar OS Foundation — 1C-04 financial integrity COMPENSATING ROLLBACK
-- Drops ONLY objects added by 004_financial_integrity.sql.
-- Run only under Tyrone's explicit real-time confirmation (sole rollback authority).
-- NOT EXECUTED by any tool.

BEGIN;

ALTER TABLE "audit_events" DROP COLUMN IF EXISTS "correlation_id";
DROP INDEX IF EXISTS "uq_job_requests_org_type_idem";

COMMIT;