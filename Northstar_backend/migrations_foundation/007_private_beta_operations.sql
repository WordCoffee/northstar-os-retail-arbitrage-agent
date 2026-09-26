-- Northstar OS Foundation — 1C-06 private beta operations (additive delta)
-- Phase: 1C-LC / owner-prioritized operations & subscriber rules.
-- PURPOSE:
--   org_lifecycle + events: tester-org lifecycle state machine (append-only).
--   org_admin_notes: INTERNAL admin annotations (never exposed to testers).
--   entitlement_overrides: temporary entitlement overrides (reason/actor/expiry).
--   support_tickets: org-scoped support queue with tester-visible vs internal
--     note separation.
--   onboarding: onboarding checklist state per org.
-- ADDITIVE + reapply-safe. NOT APPLIED by any tool; reviewed step only.

BEGIN;

CREATE TABLE IF NOT EXISTS "org_lifecycle" (
    "organization_id" TEXT, "state" TEXT, "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("organization_id")
);

CREATE TABLE IF NOT EXISTS "org_lifecycle_events" (
    "id" TEXT, "organization_id" TEXT, "actor_user_id" TEXT,
    "previous_state" TEXT, "new_state" TEXT, "reason" TEXT,
    "correlation_id" TEXT, "occurred_at" TIMESTAMPTZ, "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "org_admin_notes" (
    "id" TEXT, "organization_id" TEXT, "author_user_id" TEXT, "note" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "entitlement_overrides" (
    "id" TEXT, "organization_id" TEXT, "feature" TEXT,
    "value_text" TEXT, "value_int" BIGINT, "reason" TEXT, "created_by" TEXT,
    "scope" TEXT, "expires_at" TIMESTAMPTZ, "permanent" BOOLEAN,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "support_tickets" (
    "id" TEXT, "organization_id" TEXT, "reference_id" TEXT,
    "reporter_user_id" TEXT, "category" TEXT, "severity" TEXT,
    "subject" TEXT, "description" TEXT, "status" TEXT, "assignee_user_id" TEXT,
    "internal_note" TEXT, "tester_visible_note" TEXT,
    "created_at" TIMESTAMPTZ, "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("id"),
    UNIQUE ("reference_id")
);

CREATE TABLE IF NOT EXISTS "onboarding" (
    "organization_id" TEXT, "checklist" JSONB, "completed" BOOLEAN,
    "completed_at" TIMESTAMPTZ, "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("organization_id")
);

CREATE TABLE IF NOT EXISTS "usage_counters" (
    "organization_id" TEXT, "period" TEXT, "monthly_jobs_used" BIGINT,
    "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("organization_id")
);

CREATE INDEX IF NOT EXISTS "idx_org_lifecycle_events__organization_id__occurred_at"
    ON "org_lifecycle_events" ("organization_id", "occurred_at");
CREATE INDEX IF NOT EXISTS "idx_support_tickets__organization_id__status"
    ON "support_tickets" ("organization_id", "status");
CREATE INDEX IF NOT EXISTS "idx_support_tickets__reference_id"
    ON "support_tickets" ("reference_id");
CREATE INDEX IF NOT EXISTS "idx_org_admin_notes__organization_id__created_at"
    ON "org_admin_notes" ("organization_id", "created_at");

COMMIT;

-- Compensating rollback (controlled rollback only; NOT executed autonomously):
--   DROP INDEX IF EXISTS "idx_org_admin_notes__organization_id__created_at";
--   DROP INDEX IF EXISTS "idx_support_tickets__reference_id";
--   DROP INDEX IF EXISTS "idx_support_tickets__organization_id__status";
--   DROP INDEX IF EXISTS "idx_org_lifecycle_events__organization_id__occurred_at";
--   DROP TABLE IF EXISTS "onboarding";
--   DROP TABLE IF EXISTS "support_tickets";
--   DROP TABLE IF EXISTS "entitlement_overrides";
--   DROP TABLE IF EXISTS "org_admin_notes";
--   DROP TABLE IF EXISTS "org_lifecycle_events";
--   DROP TABLE IF EXISTS "org_lifecycle";