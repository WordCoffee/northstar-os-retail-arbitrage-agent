-- Northstar OS Foundation — 1C-04 durable execution COMPENSATING ROLLBACK
-- Phase: 1C-LC Workstream B (B02/B03)
-- Drops ONLY objects added by 002_jobs_durable.sql. Run only in a controlled
-- rollback (see 11-rollback-runbook.md). DESTROYS DATA written by the durable
-- execution system: take a verified backup first.
-- Reapply-safe ordering is reverse of 002. NOT EXECUTED by any tool.

BEGIN;

ALTER TABLE "job_schedules" DROP CONSTRAINT IF EXISTS "fk_job_schedules_organization_id";
ALTER TABLE "schedule_occurrences" DROP CONSTRAINT IF EXISTS "fk_schedule_occurrences_schedule_id";
ALTER TABLE "job_runs" DROP CONSTRAINT IF EXISTS "fk_job_runs_job_request_id";
ALTER TABLE "job_requests" DROP CONSTRAINT IF EXISTS "fk_job_requests_organization_id";

DROP INDEX IF EXISTS "uq_schedule_occurrences_schedule_key";
DROP INDEX IF EXISTS "uq_job_requests_org_idem";

DROP INDEX IF EXISTS "idx_job_requests__organization_id__created_at";
DROP INDEX IF EXISTS "idx_job_runs__state__priority__created_at";
DROP INDEX IF EXISTS "idx_job_runs__lease_expiration";
DROP INDEX IF EXISTS "idx_job_runs__job_request_id__created_at";
DROP INDEX IF EXISTS "idx_job_state_history__job_id__run_id";
DROP INDEX IF EXISTS "idx_job_state_history__occurred_at";
DROP INDEX IF EXISTS "idx_job_schedules__organization_id__enabled";
DROP INDEX IF EXISTS "idx_job_schedules__next_run_at";
DROP INDEX IF EXISTS "idx_schedule_occurrences__schedule_id__scheduled_for";
DROP INDEX IF EXISTS "idx_audit_events__organization_id__occurred_at";

ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "cancellation_state";
ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "error_summary";
ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "error_code";
ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "output_reference";
ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "correlation_id";
ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "parent_job_id";
ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "idempotency_key";
ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "lease_expiration";
ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "lease_owner";
ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "heartbeat_time";
ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "scheduled_time";
ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "actual_cost";
ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "reserved_cost";
ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "priority";

ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "provenance";
ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "correlation_id";
ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "parent_job_id";
ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "estimated_cost";
ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "budget_class";
ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "provider_class";
ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "approval_id";
ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "payload_schema_version";
ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "payload";
ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "job_type";
ALTER TABLE "organizations" DROP COLUMN IF EXISTS "active";
ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "state";

DROP TABLE IF EXISTS "schedule_occurrences";
DROP TABLE IF EXISTS "job_schedules";
DROP TABLE IF EXISTS "job_state_history";
DROP TABLE IF EXISTS "org_balances";

COMMIT;