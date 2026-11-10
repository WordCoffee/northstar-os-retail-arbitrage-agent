-- Northstar OS Foundation — 1C-04 durable execution (additive delta)
-- Phase: 1C-LC Workstream B (B02/B03)
-- PRE-EXISTING DEPLOYMENTS ONLY: this file upgrades a 1C-03-era foundation
-- schema in place. New installs get everything from 001_foundation.sql and do
-- NOT need this file.
-- ADDITIVE ONLY: adds columns/tables/indexes; never drops, renames, or alters
-- existing objects in a non-additive way. Reapply-safe (IF NOT EXISTS / ADD
-- COLUMN IF NOT EXISTS). NOT APPLIED by any tool; apply in a reviewed step per
-- MIGRATION_GUIDE.md / staging-handoff-checklist.md.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. job_requests — durable submission fields (additive)
-- ---------------------------------------------------------------------------
ALTER TABLE "job_requests" ADD COLUMN IF NOT EXISTS "state" TEXT;
ALTER TABLE "job_requests" ADD COLUMN IF NOT EXISTS "job_type" TEXT;
ALTER TABLE "organizations" ADD COLUMN IF NOT EXISTS "active" BOOLEAN;
ALTER TABLE "job_requests" ADD COLUMN IF NOT EXISTS "payload" JSONB;
ALTER TABLE "job_requests" ADD COLUMN IF NOT EXISTS "payload_schema_version" TEXT;
ALTER TABLE "job_requests" ADD COLUMN IF NOT EXISTS "approval_id" TEXT;
ALTER TABLE "job_requests" ADD COLUMN IF NOT EXISTS "provider_class" TEXT;
ALTER TABLE "job_requests" ADD COLUMN IF NOT EXISTS "budget_class" TEXT;
ALTER TABLE "job_requests" ADD COLUMN IF NOT EXISTS "estimated_cost" NUMERIC;
ALTER TABLE "job_requests" ADD COLUMN IF NOT EXISTS "parent_job_id" TEXT;
ALTER TABLE "job_requests" ADD COLUMN IF NOT EXISTS "correlation_id" TEXT;
ALTER TABLE "job_requests" ADD COLUMN IF NOT EXISTS "provenance" JSONB;

-- organization-scoped idempotency (composite unique; additive to the legacy
-- single-column unique index, which is preserved for compatibility).
CREATE UNIQUE INDEX IF NOT EXISTS "uq_job_requests_org_idem"
    ON "job_requests" ("organization_id", "idempotency_key");

-- ---------------------------------------------------------------------------
-- 2. job_runs — lease/heartbeat/cost/output fields (additive)
-- ---------------------------------------------------------------------------
ALTER TABLE "job_runs" ADD COLUMN IF NOT EXISTS "priority" BIGINT;
ALTER TABLE "job_runs" ADD COLUMN IF NOT EXISTS "reserved_cost" NUMERIC;
ALTER TABLE "job_runs" ADD COLUMN IF NOT EXISTS "actual_cost" NUMERIC;
ALTER TABLE "job_runs" ADD COLUMN IF NOT EXISTS "scheduled_time" TIMESTAMPTZ;
ALTER TABLE "job_runs" ADD COLUMN IF NOT EXISTS "heartbeat_time" TIMESTAMPTZ;
ALTER TABLE "job_runs" ADD COLUMN IF NOT EXISTS "lease_owner" TEXT;
ALTER TABLE "job_runs" ADD COLUMN IF NOT EXISTS "lease_expiration" TIMESTAMPTZ;
ALTER TABLE "job_runs" ADD COLUMN IF NOT EXISTS "idempotency_key" TEXT;
ALTER TABLE "job_runs" ADD COLUMN IF NOT EXISTS "parent_job_id" TEXT;
ALTER TABLE "job_runs" ADD COLUMN IF NOT EXISTS "correlation_id" TEXT;
ALTER TABLE "job_runs" ADD COLUMN IF NOT EXISTS "output_reference" TEXT;
ALTER TABLE "job_runs" ADD COLUMN IF NOT EXISTS "error_code" TEXT;
ALTER TABLE "job_runs" ADD COLUMN IF NOT EXISTS "error_summary" TEXT;
ALTER TABLE "job_runs" ADD COLUMN IF NOT EXISTS "cancellation_state" TEXT;

-- ---------------------------------------------------------------------------
-- 3. New tables — transition evidence, schedules, schedule occurrences
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "job_state_history" (
    "id" TEXT,
    "job_id" TEXT,
    "run_id" TEXT,
    "previous_state" TEXT,
    "new_state" TEXT,
    "actor" TEXT,
    "reason" TEXT,
    "correlation_id" TEXT,
    "audit_event_ref" TEXT,
    "occurred_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "job_schedules" (
    "id" TEXT,
    "organization_id" TEXT,
    "owner_user_id" TEXT,
    "job_template" JSONB,
    "timezone" TEXT,
    "cron_expression" TEXT,
    "interval_seconds" BIGINT,
    "enabled" BOOLEAN,
    "next_run_at" TIMESTAMPTZ,
    "last_run_at" TIMESTAMPTZ,
    "concurrency_policy" JSONB,
    "misfire_policy" TEXT,
    "approval_policy" JSONB,
    "budget_policy" JSONB,
    "provider_policy" JSONB,
    "failure_policy" JSONB,
    "version" TEXT,
    "archived" BOOLEAN,
    "created_at" TIMESTAMPTZ,
    "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "schedule_occurrences" (
    "id" TEXT,
    "schedule_id" TEXT,
    "occurrence_key" TEXT,
    "scheduled_for" TIMESTAMPTZ,
    "enqueued_job_request_id" TEXT,
    "state" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id"),
    UNIQUE ("schedule_id", "occurrence_key")
);

CREATE UNIQUE INDEX IF NOT EXISTS "uq_schedule_occurrences_schedule_key"
    ON "schedule_occurrences" ("schedule_id", "occurrence_key");

CREATE TABLE IF NOT EXISTS "org_balances" (
    "organization_id" TEXT,
    "granted" NUMERIC,
    "reserved" NUMERIC,
    "consumed" NUMERIC,
    "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("organization_id")
);

-- ---------------------------------------------------------------------------
-- 4. Foreign keys (additive; parents always created before children).
--    Wrapped in idempotent DO blocks so reapply is a safe no-op.
-- ---------------------------------------------------------------------------
DO $$
BEGIN
    ALTER TABLE "job_requests" ADD CONSTRAINT "fk_job_requests_organization_id"
        FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE "job_runs" ADD CONSTRAINT "fk_job_runs_job_request_id"
        FOREIGN KEY ("job_request_id") REFERENCES "job_requests" ("id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE "job_schedules" ADD CONSTRAINT "fk_job_schedules_organization_id"
        FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE "schedule_occurrences" ADD CONSTRAINT "fk_schedule_occurrences_schedule_id"
        FOREIGN KEY ("schedule_id") REFERENCES "job_schedules" ("id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ---------------------------------------------------------------------------
-- 5. Query indexes — queue/claim, lease recovery, history, schedules, audit
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS "idx_job_requests__organization_id__created_at"
    ON "job_requests" ("organization_id", "created_at");
CREATE INDEX IF NOT EXISTS "idx_job_runs__state__priority__created_at"
    ON "job_runs" ("state", "priority", "created_at");
CREATE INDEX IF NOT EXISTS "idx_job_runs__lease_expiration"
    ON "job_runs" ("lease_expiration");
CREATE INDEX IF NOT EXISTS "idx_job_runs__job_request_id__created_at"
    ON "job_runs" ("job_request_id", "created_at");
CREATE INDEX IF NOT EXISTS "idx_job_state_history__job_id__run_id"
    ON "job_state_history" ("job_id", "run_id");
CREATE INDEX IF NOT EXISTS "idx_job_state_history__occurred_at"
    ON "job_state_history" ("occurred_at");
CREATE INDEX IF NOT EXISTS "idx_job_schedules__organization_id__enabled"
    ON "job_schedules" ("organization_id", "enabled");
CREATE INDEX IF NOT EXISTS "idx_job_schedules__next_run_at"
    ON "job_schedules" ("next_run_at");
CREATE INDEX IF NOT EXISTS "idx_schedule_occurrences__schedule_id__scheduled_for"
    ON "schedule_occurrences" ("schedule_id", "scheduled_for");
CREATE INDEX IF NOT EXISTS "idx_audit_events__organization_id__occurred_at"
    ON "audit_events" ("organization_id", "occurred_at");

COMMIT;

-- Compensating rollback (run only in a controlled rollback; drops ONLY objects
-- added by THIS migration):
--   ALTER TABLE "job_schedules" DROP CONSTRAINT IF EXISTS "fk_job_schedules_organization_id";
--   ALTER TABLE "schedule_occurrences" DROP CONSTRAINT IF EXISTS "fk_schedule_occurrences_schedule_id";
--   ALTER TABLE "job_runs" DROP CONSTRAINT IF EXISTS "fk_job_runs_job_request_id";
--   ALTER TABLE "job_requests" DROP CONSTRAINT IF EXISTS "fk_job_requests_organization_id";
--   DROP INDEX IF EXISTS "uq_schedule_occurrences_schedule_key";
--   DROP INDEX IF EXISTS "uq_job_requests_org_idem";
--   DROP INDEX IF EXISTS "idx_job_requests__organization_id__created_at";
--   DROP INDEX IF EXISTS "idx_job_runs__state__priority__created_at";
--   DROP INDEX IF EXISTS "idx_job_runs__lease_expiration";
--   DROP INDEX IF EXISTS "idx_job_runs__job_request_id__created_at";
--   DROP INDEX IF EXISTS "idx_job_state_history__job_id__run_id";
--   DROP INDEX IF EXISTS "idx_job_state_history__occurred_at";
--   DROP INDEX IF EXISTS "idx_job_schedules__organization_id__enabled";
--   DROP INDEX IF EXISTS "idx_job_schedules__next_run_at";
--   DROP INDEX IF EXISTS "idx_schedule_occurrences__schedule_id__scheduled_for";
--   DROP INDEX IF EXISTS "idx_audit_events__organization_id__occurred_at";
--   ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "cancellation_state";
--   ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "error_summary";
--   ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "error_code";
--   ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "output_reference";
--   ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "correlation_id";
--   ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "parent_job_id";
--   ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "idempotency_key";
--   ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "lease_expiration";
--   ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "lease_owner";
--   ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "heartbeat_time";
--   ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "scheduled_time";
--   ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "actual_cost";
--   ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "reserved_cost";
--   ALTER TABLE "job_runs" DROP COLUMN IF EXISTS "priority";
--   ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "provenance";
--   ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "correlation_id";
--   ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "parent_job_id";
--   ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "estimated_cost";
--   ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "budget_class";
--   ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "provider_class";
--   ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "approval_id";
--   ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "payload_schema_version";
--   ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "payload";
--   ALTER TABLE "job_requests" DROP COLUMN IF EXISTS "job_type";
--   DROP TABLE IF EXISTS "schedule_occurrences";
--   DROP TABLE IF EXISTS "job_schedules";
--   DROP TABLE IF EXISTS "job_state_history";
-- WARNING: rollback destroys data written by the new system; take a backup
-- first and follow 11-rollback-runbook.md.