-- Northstar OS Foundation — 1C-06 master slice COMPENSATING ROLLBACK
-- Drops ONLY objects added by 006_private_beta_readiness.sql.
-- Run only under Tyrone's explicit real-time confirmation.
-- NOT EXECUTED by any tool.

BEGIN;

ALTER TABLE "account_acceptance" DROP COLUMN IF EXISTS "private_beta_addendum_version";
DROP INDEX IF EXISTS "idx_subscriptions__organization_id__status";
DROP INDEX IF EXISTS "idx_invites__organization_id__email";
DROP INDEX IF EXISTS "uq_invites_invite_code";
DROP INDEX IF EXISTS "uq_subscriptions_processor_subscription_id";
DROP INDEX IF EXISTS "uq_billing_events_processor_event_id";
DROP TABLE IF EXISTS "org_entitlements";
DROP TABLE IF EXISTS "invites";
DROP TABLE IF EXISTS "billing_events";
DROP TABLE IF EXISTS "subscriptions";
DROP TABLE IF EXISTS "checkout_sessions";
DROP TABLE IF EXISTS "billing_customers";

COMMIT;