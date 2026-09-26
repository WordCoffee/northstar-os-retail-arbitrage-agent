-- Northstar OS Foundation — 1C-05 keyword & SEO intelligence (additive delta)
-- Phase: 1C-LC Workstream C (C01)
-- PRE-EXISTING DEPLOYMENTS ONLY. New installs get everything from 001.
-- ADDITIVE ONLY and reapply-safe (IF NOT EXISTS / DO-block FKs).
-- NOT APPLIED by any tool; apply in a reviewed step.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Keyword & SEO tables
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS "keywords" (
    "id" TEXT,
    "organization_id" TEXT,
    "normalized_phrase" TEXT,
    "original_phrase" TEXT,
    "marketplace" TEXT,
    "language" TEXT,
    "match_type" TEXT,
    "brand_terms" JSONB,
    "confidence" DOUBLE PRECISION,
    "freshness_state" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id"),
    UNIQUE ("organization_id", "normalized_phrase", "match_type", "marketplace")
);

CREATE TABLE IF NOT EXISTS "search_terms" (
    "id" TEXT,
    "organization_id" TEXT,
    "raw_term" TEXT,
    "normalized_term" TEXT,
    "marketplace" TEXT,
    "search_volume" BIGINT,
    "observed_volume" BIGINT,
    "impressions" BIGINT,
    "clicks" BIGINT,
    "spend" NUMERIC,
    "orders" BIGINT,
    "revenue" NUMERIC,
    "source" TEXT,
    "observed_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id"),
    UNIQUE ("organization_id", "normalized_term", "marketplace")
);

CREATE TABLE IF NOT EXISTS "targets" (
    "id" TEXT,
    "organization_id" TEXT,
    "keyword_id" TEXT,
    "campaign_id" TEXT,
    "ad_group_id" TEXT,
    "match_type" TEXT,
    "bid" NUMERIC,
    "status" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "keyword_links" (
    "id" TEXT,
    "organization_id" TEXT,
    "keyword_id" TEXT,
    "link_kind" TEXT,
    "target_ref" TEXT,
    "asin" TEXT,
    "product_id" TEXT,
    "note" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "import_batches" (
    "id" TEXT,
    "organization_id" TEXT,
    "source_file_id" TEXT,
    "status" TEXT,
    "submitted_by" TEXT,
    "submitted_at" TIMESTAMPTZ,
    "started_at" TIMESTAMPTZ,
    "completed_at" TIMESTAMPTZ,
    "summary" JSONB,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "source_files" (
    "id" TEXT,
    "organization_id" TEXT,
    "file_name" TEXT,
    "file_sha256" TEXT,
    "file_size" BIGINT,
    "marketplace" TEXT,
    "currency" TEXT,
    "report_type" TEXT,
    "date_from" TIMESTAMPTZ,
    "date_to" TIMESTAMPTZ,
    "status" TEXT,
    "registered_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id"),
    UNIQUE ("organization_id", "file_sha256")
);

CREATE TABLE IF NOT EXISTS "source_rows" (
    "id" TEXT,
    "organization_id" TEXT,
    "import_batch_id" TEXT,
    "source_file_id" TEXT,
    "row_index" BIGINT,
    "row_json" JSONB,
    "status" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "rejected_rows" (
    "id" TEXT,
    "organization_id" TEXT,
    "import_batch_id" TEXT,
    "source_file_id" TEXT,
    "row_index" BIGINT,
    "row_json" JSONB,
    "rejection_reason" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "normalization_decisions" (
    "id" TEXT,
    "organization_id" TEXT,
    "original_phrase" TEXT,
    "normalized_phrase" TEXT,
    "rule" JSONB,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "rank_observations" (
    "id" TEXT,
    "organization_id" TEXT,
    "keyword_id" TEXT,
    "asin" TEXT,
    "rank" BIGINT,
    "placement" TEXT,
    "observed_at" TIMESTAMPTZ,
    "source" TEXT,
    "confidence" DOUBLE PRECISION,
    "freshness_state" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "ad_performance_observations" (
    "id" TEXT,
    "organization_id" TEXT,
    "search_term_id" TEXT,
    "campaign_id" TEXT,
    "ad_group_id" TEXT,
    "impressions" BIGINT,
    "clicks" BIGINT,
    "spend" NUMERIC,
    "orders" BIGINT,
    "revenue" NUMERIC,
    "ctr" DOUBLE PRECISION,
    "cvr" DOUBLE PRECISION,
    "observed_at" TIMESTAMPTZ,
    "source" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "keyword_conflicts" (
    "id" TEXT,
    "organization_id" TEXT,
    "keyword_id_a" TEXT,
    "keyword_id_b" TEXT,
    "conflict_type" TEXT,
    "detail" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

-- ---------------------------------------------------------------------------
-- 2. Organization-scoped uniqueness
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS "uq_keywords_org_phrase_match_mp"
    ON "keywords" ("organization_id", "normalized_phrase", "match_type", "marketplace");
CREATE UNIQUE INDEX IF NOT EXISTS "uq_source_files_org_sha"
    ON "source_files" ("organization_id", "file_sha256");
CREATE UNIQUE INDEX IF NOT EXISTS "uq_search_terms_org_term_mp"
    ON "search_terms" ("organization_id", "normalized_term", "marketplace");

-- ---------------------------------------------------------------------------
-- 3. Foreign keys (additive, idempotent)
-- ---------------------------------------------------------------------------
DO $$ BEGIN
    ALTER TABLE "keywords" ADD CONSTRAINT "fk_keywords_organization_id"
        FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id");
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE "search_terms" ADD CONSTRAINT "fk_search_terms_organization_id"
        FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id");
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE "targets" ADD CONSTRAINT "fk_targets_keyword_id"
        FOREIGN KEY ("keyword_id") REFERENCES "keywords" ("id");
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE "keyword_links" ADD CONSTRAINT "fk_keyword_links_keyword_id"
        FOREIGN KEY ("keyword_id") REFERENCES "keywords" ("id");
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE "source_files" ADD CONSTRAINT "fk_source_files_organization_id"
        FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id");
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE "import_batches" ADD CONSTRAINT "fk_import_batches_organization_id"
        FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id");
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE "import_batches" ADD CONSTRAINT "fk_import_batches_source_file_id"
        FOREIGN KEY ("source_file_id") REFERENCES "source_files" ("id");
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE "rejected_rows" ADD CONSTRAINT "fk_rejected_rows_import_batch_id"
        FOREIGN KEY ("import_batch_id") REFERENCES "import_batches" ("id");
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE "rank_observations" ADD CONSTRAINT "fk_rank_observations_keyword_id"
        FOREIGN KEY ("keyword_id") REFERENCES "keywords" ("id");
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE "ad_performance_observations" ADD CONSTRAINT
        "fk_ad_performance_observations_search_term_id"
        FOREIGN KEY ("search_term_id") REFERENCES "search_terms" ("id");
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

COMMIT;

-- Compensating rollback (controlled rollback only; destroys imported data):
--   DO $$ BEGIN ALTER TABLE "ad_performance_observations" DROP CONSTRAINT IF EXISTS
--       "fk_ad_perf_observations_search_term_id"; END $$;  (etc. for each FK)
--   DROP INDEX IF EXISTS "uq_search_terms_org_term_mp";
--   DROP INDEX IF EXISTS "uq_source_files_org_sha";
--   DROP INDEX IF EXISTS "uq_keywords_org_phrase_match_mp";
--   DROP TABLE IF EXISTS "keyword_conflicts";
--   DROP TABLE IF EXISTS "ad_performance_observations";
--   DROP TABLE IF EXISTS "rank_observations";
--   DROP TABLE IF EXISTS "normalization_decisions";
--   DROP TABLE IF EXISTS "rejected_rows";
--   DROP TABLE IF EXISTS "source_rows";
--   DROP TABLE IF EXISTS "source_files";
--   DROP TABLE IF EXISTS "import_batches";
--   DROP TABLE IF EXISTS "keyword_links";
--   DROP TABLE IF EXISTS "targets";
--   DROP TABLE IF EXISTS "search_terms";
--   DROP TABLE IF EXISTS "keywords";