-- Northstar OS Foundation — 1C-06 Lean B2B beta launch controls (additive delta)
-- Phase: 1C-LC / owner-prioritized beta controls.
-- PURPOSE:
--   1. legal_documents: versioned, published beta documents (Privacy Notice,
--      Terms of Service, Acceptable Use Policy).
--   2. acceptance_events: APPEND-ONLY acceptance records (doc type, version,
--      content hash, business-use + 18+ attestations, IP handling, request/
--      correlation id, timestamps).
--   3. account_acceptance: current acceptance pointer per (organization, user)
--      for fast deny-until-accepted checks (append-only events remain truth).
-- ADDITIVE + reapply-safe. NOT APPLIED by any tool; reviewed step only.

BEGIN;

CREATE TABLE IF NOT EXISTS "legal_documents" (
    "id" TEXT,
    "doc_type" TEXT,
    "version" TEXT,
    "title" TEXT,
    "content_hash" TEXT,
    "status" TEXT,
    "published_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "acceptance_events" (
    "id" TEXT,
    "organization_id" TEXT,
    "user_id" TEXT,
    "doc_type" TEXT,
    "doc_version" TEXT,
    "content_hash" TEXT,
    "business_use_attested" BOOLEAN,
    "age_18_attested" BOOLEAN,
    "ip_handling" TEXT,
    "request_id" TEXT,
    "correlation_id" TEXT,
    "accepted_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "account_acceptance" (
    "id" TEXT,
    "organization_id" TEXT,
    "user_id" TEXT,
    "privacy_notice_version" TEXT,
    "terms_of_service_version" TEXT,
    "acceptable_use_policy_version" TEXT,
    "business_attested" BOOLEAN,
    "age_18_attested" BOOLEAN,
    "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("id"),
    UNIQUE ("organization_id", "user_id")
);

CREATE UNIQUE INDEX IF NOT EXISTS "uq_account_acceptance_org_user"
    ON "account_acceptance" ("organization_id", "user_id");
CREATE INDEX IF NOT EXISTS "idx_acceptance_events__organization_id__user_id__accepted_at"
    ON "acceptance_events" ("organization_id", "user_id", "accepted_at");
CREATE INDEX IF NOT EXISTS "idx_legal_documents__doc_type__version"
    ON "legal_documents" ("doc_type", "version");

COMMIT;

-- Compensating rollback (controlled rollback only; NOT executed autonomously):
--   DROP INDEX IF EXISTS "idx_legal_documents__doc_type__version";
--   DROP INDEX IF EXISTS "idx_acceptance_events__organization_id__user_id__accepted_at";
--   DROP INDEX IF EXISTS "uq_account_acceptance_org_user";
--   DROP TABLE IF EXISTS "account_acceptance";
--   DROP TABLE IF EXISTS "acceptance_events";
--   DROP TABLE IF EXISTS "legal_documents";