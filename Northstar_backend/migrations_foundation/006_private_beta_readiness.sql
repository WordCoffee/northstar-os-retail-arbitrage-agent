-- Northstar OS Foundation — 1C-06 master slice: private beta readiness (additive delta)
-- Phase: 1C-LC / owner-prioritized private beta (test-mode billing, tiers &
-- entitlements, invite-gated access).
-- PURPOSE:
--   billing_customers/checkout_sessions/subscriptions/billing_events: TEST-MODE
--     billing — processor IDs + status only (never card data); exactly-once
--     webhook settlement keyed on processor event id.
--   invites: admin-managed invite/approved-email allowlist (default closed).
--   org_entitlements: materialized per-org tier flags for centralized checks.
-- ADDITIVE + reapply-safe. NOT APPLIED by any tool; reviewed step only.

BEGIN;

-- account_acceptance gains the private-beta-addendum acceptance pointer
-- (additive; 005 created the table).
ALTER TABLE "account_acceptance" ADD COLUMN IF NOT EXISTS "private_beta_addendum_version" TEXT;

CREATE TABLE IF NOT EXISTS "billing_customers" (
    "id" TEXT, "organization_id" TEXT, "processor" TEXT,
    "processor_customer_id" TEXT, "created_at" TIMESTAMPTZ, "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "checkout_sessions" (
    "id" TEXT, "organization_id" TEXT, "price_id" TEXT, "tier" TEXT,
    "status" TEXT, "expires_at" TIMESTAMPTZ, "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "subscriptions" (
    "id" TEXT, "organization_id" TEXT, "billing_customer_id" TEXT,
    "processor_subscription_id" TEXT, "price_id" TEXT, "tier" TEXT,
    "status" TEXT, "current_period_end" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ, "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("id"),
    UNIQUE ("processor_subscription_id")
);

CREATE TABLE IF NOT EXISTS "billing_events" (
    "id" TEXT, "processor_event_id" TEXT, "event_type" TEXT,
    "payload_hash" TEXT, "status" TEXT, "processed_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id"),
    UNIQUE ("processor_event_id")
);

CREATE TABLE IF NOT EXISTS "invites" (
    "id" TEXT, "organization_id" TEXT, "invite_code" TEXT, "email" TEXT,
    "role" TEXT, "status" TEXT, "created_by" TEXT, "expires_at" TIMESTAMPTZ,
    "used_at" TIMESTAMPTZ, "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id"),
    UNIQUE ("invite_code")
);

CREATE TABLE IF NOT EXISTS "org_entitlements" (
    "organization_id" TEXT, "tier" TEXT, "max_jobs_per_month" BIGINT,
    "export_enabled" BOOLEAN, "advanced_reports" BOOLEAN, "seat_limit" BIGINT,
    "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("organization_id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "uq_billing_events_processor_event_id"
    ON "billing_events" ("processor_event_id");
CREATE UNIQUE INDEX IF NOT EXISTS "uq_subscriptions_processor_subscription_id"
    ON "subscriptions" ("processor_subscription_id");
CREATE UNIQUE INDEX IF NOT EXISTS "uq_invites_invite_code"
    ON "invites" ("invite_code");
CREATE INDEX IF NOT EXISTS "idx_invites__organization_id__email"
    ON "invites" ("organization_id", "email");
CREATE INDEX IF NOT EXISTS "idx_subscriptions__organization_id__status"
    ON "subscriptions" ("organization_id", "status");

COMMIT;

-- Compensating rollback (controlled rollback only; NOT executed autonomously):
--   DROP INDEX IF EXISTS "idx_subscriptions__organization_id__status";
--   DROP INDEX IF EXISTS "idx_invites__organization_id__email";
--   DROP INDEX IF EXISTS "uq_invites_invite_code";
--   DROP INDEX IF EXISTS "uq_subscriptions_processor_subscription_id";
--   DROP INDEX IF EXISTS "uq_billing_events_processor_event_id";
--   DROP TABLE IF EXISTS "org_entitlements";
--   DROP TABLE IF EXISTS "invites";
--   DROP TABLE IF EXISTS "billing_events";
--   DROP TABLE IF EXISTS "subscriptions";
--   DROP TABLE IF EXISTS "checkout_sessions";
--   DROP TABLE IF EXISTS "billing_customers";