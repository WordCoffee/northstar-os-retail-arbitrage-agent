-- Northstar OS Foundation — 1C-05 keyword & SEO COMPENSATING ROLLBACK
-- Phase: 1C-LC Workstream C (C01)
-- Drops ONLY objects added by 003_keyword_intel.sql. Run only in a controlled
-- rollback. DESTROYS imported keyword data: take a verified backup first.
-- Reapply-safe ordering is reverse of 003. NOT EXECUTED by any tool.

BEGIN;

DO $$ BEGIN
    ALTER TABLE "ad_performance_observations" DROP CONSTRAINT IF EXISTS
        "fk_ad_performance_observations_search_term_id";
EXCEPTION WHEN undefined_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE "rank_observations" DROP CONSTRAINT IF EXISTS
        "fk_rank_observations_keyword_id";
EXCEPTION WHEN undefined_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE "rejected_rows" DROP CONSTRAINT IF EXISTS
        "fk_rejected_rows_import_batch_id";
EXCEPTION WHEN undefined_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE "import_batches" DROP CONSTRAINT IF EXISTS
        "fk_import_batches_source_file_id";
EXCEPTION WHEN undefined_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE "import_batches" DROP CONSTRAINT IF EXISTS
        "fk_import_batches_organization_id";
EXCEPTION WHEN undefined_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE "source_files" DROP CONSTRAINT IF EXISTS
        "fk_source_files_organization_id";
EXCEPTION WHEN undefined_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE "keyword_links" DROP CONSTRAINT IF EXISTS
        "fk_keyword_links_keyword_id";
EXCEPTION WHEN undefined_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE "targets" DROP CONSTRAINT IF EXISTS
        "fk_targets_keyword_id";
EXCEPTION WHEN undefined_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE "search_terms" DROP CONSTRAINT IF EXISTS
        "fk_search_terms_organization_id";
EXCEPTION WHEN undefined_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE "keywords" DROP CONSTRAINT IF EXISTS
        "fk_keywords_organization_id";
EXCEPTION WHEN undefined_object THEN NULL; END $$;

DROP INDEX IF EXISTS "uq_search_terms_org_term_mp";
DROP INDEX IF EXISTS "uq_source_files_org_sha";
DROP INDEX IF EXISTS "uq_keywords_org_phrase_match_mp";

DROP TABLE IF EXISTS "keyword_conflicts";
DROP TABLE IF EXISTS "ad_performance_observations";
DROP TABLE IF EXISTS "rank_observations";
DROP TABLE IF EXISTS "normalization_decisions";
DROP TABLE IF EXISTS "rejected_rows";
DROP TABLE IF EXISTS "source_rows";
DROP TABLE IF EXISTS "source_files";
DROP TABLE IF EXISTS "import_batches";
DROP TABLE IF EXISTS "keyword_links";
DROP TABLE IF EXISTS "targets";
DROP TABLE IF EXISTS "search_terms";
DROP TABLE IF EXISTS "keywords";

COMMIT;