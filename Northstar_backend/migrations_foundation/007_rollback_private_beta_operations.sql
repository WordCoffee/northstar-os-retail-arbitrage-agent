-- Northstar OS Foundation — 1C-06 private beta operations COMPENSATING ROLLBACK
-- Drops ONLY objects added by 007_private_beta_operations.sql.
-- Run only under Tyrone's explicit real-time confirmation.
-- NOT EXECUTED by any tool.

BEGIN;

DROP INDEX IF EXISTS "idx_org_admin_notes__organization_id__created_at";
DROP TABLE IF EXISTS "usage_counters";
DROP INDEX IF EXISTS "idx_support_tickets__reference_id";
DROP INDEX IF EXISTS "idx_support_tickets__organization_id__status";
DROP INDEX IF EXISTS "idx_org_lifecycle_events__organization_id__occurred_at";
DROP TABLE IF EXISTS "onboarding";
DROP TABLE IF EXISTS "support_tickets";
DROP TABLE IF EXISTS "entitlement_overrides";
DROP TABLE IF EXISTS "org_admin_notes";
DROP TABLE IF EXISTS "org_lifecycle_events";
DROP TABLE IF EXISTS "org_lifecycle";

COMMIT;