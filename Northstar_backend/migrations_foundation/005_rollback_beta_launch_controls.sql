-- Northstar OS Foundation — 1C-06 beta launch controls COMPENSATING ROLLBACK
-- Drops ONLY objects added by 005_beta_launch_controls.sql.
-- Run only under Tyrone's explicit real-time confirmation.
-- NOT EXECUTED by any tool.

BEGIN;

DROP INDEX IF EXISTS "idx_legal_documents__doc_type__version";
DROP INDEX IF EXISTS "idx_acceptance_events__organization_id__user_id__accepted_at";
DROP INDEX IF EXISTS "uq_account_acceptance_org_user";
DROP TABLE IF EXISTS "account_acceptance";
DROP TABLE IF EXISTS "acceptance_events";
DROP TABLE IF EXISTS "legal_documents";

COMMIT;