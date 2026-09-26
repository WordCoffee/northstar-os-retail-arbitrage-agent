-- Northstar OS Foundation — canonical schema (PostgreSQL)
-- ADDITIVE ONLY. NOT APPLIED. Apply per MIGRATION_GUIDE.md in a reviewed step.
-- GENERATED from foundation/db.py SCHEMA (single source of truth). Do not edit
-- by hand; regenerate with tools/foundation_generate_sql.py.
-- Logical-type mapping: id->TEXT, text->TEXT, int->BIGINT, real->DOUBLE PRECISION,
-- money->NUMERIC, bool->BOOLEAN, json->JSONB, ts->TIMESTAMPTZ
-- (SQLite: TEXT/INTEGER/REAL/REAL/INTEGER/TEXT/TEXT).


CREATE TABLE IF NOT EXISTS "organizations" (
    "id" TEXT,
    "name" TEXT,
    "slug" TEXT,
    "environment" TEXT,
    "active" BOOLEAN,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "users" (
    "id" TEXT,
    "email" TEXT,
    "display_name" TEXT,
    "active" BOOLEAN,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "memberships" (
    "id" TEXT,
    "organization_id" TEXT,
    "user_id" TEXT,
    "role" TEXT,
    "status" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "marketplaces" (
    "id" TEXT,
    "code" TEXT,
    "country" TEXT,
    "currency" TEXT,
    "domain" TEXT,
    "active" BOOLEAN,
    PRIMARY KEY ("id"),
    UNIQUE ("code")
);

CREATE TABLE IF NOT EXISTS "catalog_products" (
    "id" TEXT,
    "marketplace_id" TEXT,
    "asin" TEXT,
    "brand" TEXT,
    "canonical_title" TEXT,
    "pack_config_id" TEXT,
    "variation_family_id" TEXT,
    "created_at" TIMESTAMPTZ,
    "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "product_identifiers" (
    "id" TEXT,
    "product_id" TEXT,
    "kind" TEXT,
    "raw_value" TEXT,
    "normalized_value" TEXT,
    "marketplace_id" TEXT,
    "verification_state" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "pack_configs" (
    "id" TEXT,
    "product_id" TEXT,
    "count" BIGINT,
    "unit" TEXT,
    "unit_type" TEXT,
    "is_multipack" BOOLEAN,
    "is_bundle" BOOLEAN,
    "verification_state" TEXT,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "variation_relationships" (
    "id" TEXT,
    "family_id" TEXT,
    "child_product_id" TEXT,
    "axis" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "product_aliases" (
    "id" TEXT,
    "product_id" TEXT,
    "alias_value" TEXT,
    "reason" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "unresolved_candidates" (
    "id" TEXT,
    "raw_asin" TEXT,
    "raw_title" TEXT,
    "raw_identifier" TEXT,
    "reason" TEXT,
    "source" TEXT,
    "source_identifier" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "identity_conflicts" (
    "id" TEXT,
    "conflict_type" TEXT,
    "candidate_id" TEXT,
    "product_id" TEXT,
    "detail" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "observations" (
    "id" TEXT,
    "product_id" TEXT,
    "candidate_id" TEXT,
    "marketplace_id" TEXT,
    "provider" TEXT,
    "provider_record_id" TEXT,
    "observation_type" TEXT,
    "observed_value" JSONB,
    "currency" TEXT,
    "unit" TEXT,
    "captured_at" TIMESTAMPTZ,
    "effective_at" TIMESTAMPTZ,
    "expires_at" TIMESTAMPTZ,
    "confidence" DOUBLE PRECISION,
    "verification_state" TEXT,
    "provenance_class" TEXT,
    "raw_source_ref" TEXT,
    "transformation_version" TEXT,
    "job_run_id" TEXT,
    "environment" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "providers" (
    "id" TEXT,
    "provider_key" TEXT,
    "name" TEXT,
    "category" TEXT,
    "adapter_module" TEXT,
    "read_capable" BOOLEAN,
    "write_capable" BOOLEAN,
    "sandbox_supported" BOOLEAN,
    "credential_ref_names" JSONB,
    "rate_limit_rpm" BIGINT,
    "timeout_seconds" BIGINT,
    "cost_model" JSONB,
    "health" TEXT,
    "enabled" BOOLEAN,
    PRIMARY KEY ("id"),
    UNIQUE ("provider_key")
);

CREATE TABLE IF NOT EXISTS "job_requests" (
    "id" TEXT,
    "organization_id" TEXT,
    "user_id" TEXT,
    "service" TEXT,
    "scope_type" TEXT,
    "scope_id" TEXT,
    "data_types" JSONB,
    "provider_policy" TEXT,
    "max_estimated_cost" DOUBLE PRECISION,
    "currency" TEXT,
    "environment" TEXT,
    "idempotency_key" TEXT,
    "requires_approval" BOOLEAN,
    "reason" TEXT,
    "priority" BIGINT,
    "created_at" TIMESTAMPTZ,
    "state" TEXT,
    "job_type" TEXT,
    "payload" JSONB,
    "payload_schema_version" TEXT,
    "approval_id" TEXT,
    "provider_class" TEXT,
    "budget_class" TEXT,
    "estimated_cost" NUMERIC,
    "parent_job_id" TEXT,
    "correlation_id" TEXT,
    "provenance" JSONB,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "job_runs" (
    "id" TEXT,
    "job_request_id" TEXT,
    "state" TEXT,
    "run_id" TEXT,
    "attempts" BIGINT,
    "max_attempts" BIGINT,
    "failure_class" TEXT,
    "error_message" TEXT,
    "started_at" TIMESTAMPTZ,
    "finished_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ,
    "priority" BIGINT,
    "reserved_cost" NUMERIC,
    "actual_cost" NUMERIC,
    "scheduled_time" TIMESTAMPTZ,
    "heartbeat_time" TIMESTAMPTZ,
    "lease_owner" TEXT,
    "lease_expiration" TIMESTAMPTZ,
    "idempotency_key" TEXT,
    "parent_job_id" TEXT,
    "correlation_id" TEXT,
    "output_reference" TEXT,
    "error_code" TEXT,
    "error_summary" TEXT,
    "cancellation_state" TEXT,
    PRIMARY KEY ("id")
);

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

CREATE TABLE IF NOT EXISTS "org_balances" (
    "organization_id" TEXT,
    "granted" NUMERIC,
    "reserved" NUMERIC,
    "consumed" NUMERIC,
    "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("organization_id")
);

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
    "private_beta_addendum_version" TEXT,
    "business_attested" BOOLEAN,
    "age_18_attested" BOOLEAN,
    "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("id"),
    UNIQUE ("organization_id", "user_id")
);

CREATE TABLE IF NOT EXISTS "billing_customers" (
    "id" TEXT,
    "organization_id" TEXT,
    "processor" TEXT,
    "processor_customer_id" TEXT,
    "created_at" TIMESTAMPTZ,
    "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "checkout_sessions" (
    "id" TEXT,
    "organization_id" TEXT,
    "price_id" TEXT,
    "tier" TEXT,
    "status" TEXT,
    "expires_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "subscriptions" (
    "id" TEXT,
    "organization_id" TEXT,
    "billing_customer_id" TEXT,
    "processor_subscription_id" TEXT,
    "price_id" TEXT,
    "tier" TEXT,
    "status" TEXT,
    "current_period_end" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ,
    "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("id"),
    UNIQUE ("processor_subscription_id")
);

CREATE TABLE IF NOT EXISTS "billing_events" (
    "id" TEXT,
    "processor_event_id" TEXT,
    "event_type" TEXT,
    "payload_hash" TEXT,
    "status" TEXT,
    "processed_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id"),
    UNIQUE ("processor_event_id")
);

CREATE TABLE IF NOT EXISTS "invites" (
    "id" TEXT,
    "organization_id" TEXT,
    "invite_code" TEXT,
    "email" TEXT,
    "role" TEXT,
    "status" TEXT,
    "created_by" TEXT,
    "expires_at" TIMESTAMPTZ,
    "used_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id"),
    UNIQUE ("invite_code")
);

CREATE TABLE IF NOT EXISTS "org_entitlements" (
    "organization_id" TEXT,
    "tier" TEXT,
    "max_jobs_per_month" BIGINT,
    "export_enabled" BOOLEAN,
    "advanced_reports" BOOLEAN,
    "seat_limit" BIGINT,
    "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("organization_id")
);

CREATE TABLE IF NOT EXISTS "org_lifecycle" (
    "organization_id" TEXT,
    "state" TEXT,
    "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("organization_id")
);

CREATE TABLE IF NOT EXISTS "org_lifecycle_events" (
    "id" TEXT,
    "organization_id" TEXT,
    "actor_user_id" TEXT,
    "previous_state" TEXT,
    "new_state" TEXT,
    "reason" TEXT,
    "correlation_id" TEXT,
    "occurred_at" TIMESTAMPTZ,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "org_admin_notes" (
    "id" TEXT,
    "organization_id" TEXT,
    "author_user_id" TEXT,
    "note" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "entitlement_overrides" (
    "id" TEXT,
    "organization_id" TEXT,
    "feature" TEXT,
    "value_text" TEXT,
    "value_int" BIGINT,
    "reason" TEXT,
    "created_by" TEXT,
    "scope" TEXT,
    "expires_at" TIMESTAMPTZ,
    "permanent" BOOLEAN,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "support_tickets" (
    "id" TEXT,
    "organization_id" TEXT,
    "reference_id" TEXT,
    "reporter_user_id" TEXT,
    "category" TEXT,
    "severity" TEXT,
    "subject" TEXT,
    "description" TEXT,
    "status" TEXT,
    "assignee_user_id" TEXT,
    "internal_note" TEXT,
    "tester_visible_note" TEXT,
    "created_at" TIMESTAMPTZ,
    "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("id"),
    UNIQUE ("reference_id")
);

CREATE TABLE IF NOT EXISTS "onboarding" (
    "organization_id" TEXT,
    "checklist" JSONB,
    "completed" BOOLEAN,
    "completed_at" TIMESTAMPTZ,
    "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("organization_id")
);

CREATE TABLE IF NOT EXISTS "usage_counters" (
    "organization_id" TEXT,
    "period" TEXT,
    "monthly_jobs_used" BIGINT,
    "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("organization_id")
);

CREATE TABLE IF NOT EXISTS "usage_events" (
    "id" TEXT,
    "organization_id" TEXT,
    "user_id" TEXT,
    "service" TEXT,
    "workflow_run_id" TEXT,
    "provider" TEXT,
    "model_or_endpoint" TEXT,
    "input_units" BIGINT,
    "output_units" BIGINT,
    "provider_reported_cost" DOUBLE PRECISION,
    "estimated_cost" DOUBLE PRECISION,
    "credits_debited_shadow" DOUBLE PRECISION,
    "cost_kind" TEXT,
    "status" TEXT,
    "idempotency_key" TEXT,
    "reversal_ref" TEXT,
    "environment" TEXT,
    "occurred_at" TIMESTAMPTZ,
    "provenance" JSONB,
    PRIMARY KEY ("id"),
    UNIQUE ("idempotency_key")
);

CREATE TABLE IF NOT EXISTS "pricing_policies" (
    "version" TEXT,
    "platform_markup" DOUBLE PRECISION,
    "minimum_charge" DOUBLE PRECISION,
    "service_multipliers" JSONB,
    "free_local_execution" BOOLEAN,
    "failed_run_charge" BOOLEAN,
    PRIMARY KEY ("version")
);

CREATE TABLE IF NOT EXISTS "audit_events" (
    "id" TEXT,
    "actor_user_id" TEXT,
    "actor_role" TEXT,
    "organization_id" TEXT,
    "target_organization_id" TEXT,
    "target_user_id" TEXT,
    "action" TEXT,
    "resource_type" TEXT,
    "resource_id" TEXT,
    "before_meta" JSONB,
    "after_meta" JSONB,
    "environment" TEXT,
    "view_context" TEXT,
    "approval_ref" TEXT,
    "job_run_ref" TEXT,
    "result" TEXT,
    "failure_class" TEXT,
    "correlation_id" TEXT,
    "occurred_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "approval_requests" (
    "id" TEXT,
    "organization_id" TEXT,
    "requested_by_user_id" TEXT,
    "capability" TEXT,
    "safety_class" TEXT,
    "resource_type" TEXT,
    "resource_id" TEXT,
    "change_preview" JSONB,
    "risk_level" TEXT,
    "cost_estimate" DOUBLE PRECISION,
    "currency" TEXT,
    "state" TEXT,
    "required_approver_role" TEXT,
    "expires_at" TIMESTAMPTZ,
    "idempotency_key" TEXT,
    "execution_ref" TEXT,
    "environment" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id"),
    UNIQUE ("idempotency_key")
);

CREATE TABLE IF NOT EXISTS "approval_decisions" (
    "id" TEXT,
    "approval_request_id" TEXT,
    "decided_by_user_id" TEXT,
    "decided_by_role" TEXT,
    "decision" TEXT,
    "note" TEXT,
    "decided_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "preview_sessions" (
    "id" TEXT,
    "actor_user_id" TEXT,
    "target_organization_id" TEXT,
    "target_role" TEXT,
    "started_at" TIMESTAMPTZ,
    "ended_at" TIMESTAMPTZ,
    "reason" TEXT,
    "read_only" BOOLEAN,
    "active" BOOLEAN,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "sessions" (
    "jti" TEXT,
    "user_id" TEXT,
    "organization_id" TEXT,
    "issued_at" TIMESTAMPTZ,
    "expires_at" TIMESTAMPTZ,
    "revoked_at" TIMESTAMPTZ,
    "revoked_reason" TEXT,
    PRIMARY KEY ("jti")
);

CREATE TABLE IF NOT EXISTS "suppliers" (
    "id" TEXT,
    "name" TEXT,
    "supplier_class" TEXT,
    "public_catalog_url" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "supplier_documentation" (
    "id" TEXT,
    "supplier_id" TEXT,
    "product_id" TEXT,
    "supply_state" TEXT,
    "documentation_state" TEXT,
    "note" TEXT,
    "created_at" TIMESTAMPTZ,
    PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "ui_preferences" (
    "user_id" TEXT,
    "organization_id" TEXT,
    "key" TEXT,
    "value" JSONB,
    "updated_at" TIMESTAMPTZ,
    PRIMARY KEY ("user_id", "organization_id", "key")
);

DO $$
BEGIN
    ALTER TABLE "job_requests" ADD CONSTRAINT "fk_job_requests_organization_id" FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


DO $$
BEGIN
    ALTER TABLE "job_runs" ADD CONSTRAINT "fk_job_runs_job_request_id" FOREIGN KEY ("job_request_id") REFERENCES "job_requests" ("id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


DO $$
BEGIN
    ALTER TABLE "job_schedules" ADD CONSTRAINT "fk_job_schedules_organization_id" FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


DO $$
BEGIN
    ALTER TABLE "schedule_occurrences" ADD CONSTRAINT "fk_schedule_occurrences_schedule_id" FOREIGN KEY ("schedule_id") REFERENCES "job_schedules" ("id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


DO $$
BEGIN
    ALTER TABLE "keywords" ADD CONSTRAINT "fk_keywords_organization_id" FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


DO $$
BEGIN
    ALTER TABLE "search_terms" ADD CONSTRAINT "fk_search_terms_organization_id" FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


DO $$
BEGIN
    ALTER TABLE "targets" ADD CONSTRAINT "fk_targets_keyword_id" FOREIGN KEY ("keyword_id") REFERENCES "keywords" ("id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


DO $$
BEGIN
    ALTER TABLE "keyword_links" ADD CONSTRAINT "fk_keyword_links_keyword_id" FOREIGN KEY ("keyword_id") REFERENCES "keywords" ("id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


DO $$
BEGIN
    ALTER TABLE "source_files" ADD CONSTRAINT "fk_source_files_organization_id" FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


DO $$
BEGIN
    ALTER TABLE "import_batches" ADD CONSTRAINT "fk_import_batches_organization_id" FOREIGN KEY ("organization_id") REFERENCES "organizations" ("id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


DO $$
BEGIN
    ALTER TABLE "import_batches" ADD CONSTRAINT "fk_import_batches_source_file_id" FOREIGN KEY ("source_file_id") REFERENCES "source_files" ("id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


DO $$
BEGIN
    ALTER TABLE "rejected_rows" ADD CONSTRAINT "fk_rejected_rows_import_batch_id" FOREIGN KEY ("import_batch_id") REFERENCES "import_batches" ("id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


DO $$
BEGIN
    ALTER TABLE "rank_observations" ADD CONSTRAINT "fk_rank_observations_keyword_id" FOREIGN KEY ("keyword_id") REFERENCES "keywords" ("id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


DO $$
BEGIN
    ALTER TABLE "ad_performance_observations" ADD CONSTRAINT "fk_ad_performance_observations_search_term_id" FOREIGN KEY ("search_term_id") REFERENCES "search_terms" ("id");
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;


CREATE INDEX IF NOT EXISTS "idx_job_requests__organization_id__created_at" ON "job_requests" ("organization_id", "created_at");

CREATE INDEX IF NOT EXISTS "idx_job_runs__state__priority__created_at" ON "job_runs" ("state", "priority", "created_at");

CREATE INDEX IF NOT EXISTS "idx_job_runs__lease_expiration" ON "job_runs" ("lease_expiration");

CREATE INDEX IF NOT EXISTS "idx_job_runs__job_request_id__created_at" ON "job_runs" ("job_request_id", "created_at");

CREATE INDEX IF NOT EXISTS "idx_job_state_history__job_id__run_id" ON "job_state_history" ("job_id", "run_id");

CREATE INDEX IF NOT EXISTS "idx_job_state_history__occurred_at" ON "job_state_history" ("occurred_at");

CREATE INDEX IF NOT EXISTS "idx_job_schedules__organization_id__enabled" ON "job_schedules" ("organization_id", "enabled");

CREATE INDEX IF NOT EXISTS "idx_job_schedules__next_run_at" ON "job_schedules" ("next_run_at");

CREATE INDEX IF NOT EXISTS "idx_schedule_occurrences__schedule_id__scheduled_for" ON "schedule_occurrences" ("schedule_id", "scheduled_for");

CREATE INDEX IF NOT EXISTS "idx_audit_events__organization_id__occurred_at" ON "audit_events" ("organization_id", "occurred_at");

CREATE INDEX IF NOT EXISTS "idx_acceptance_events__organization_id__user_id__accepted_at" ON "acceptance_events" ("organization_id", "user_id", "accepted_at");

CREATE INDEX IF NOT EXISTS "idx_legal_documents__doc_type__version" ON "legal_documents" ("doc_type", "version");

CREATE INDEX IF NOT EXISTS "idx_invites__organization_id__email" ON "invites" ("organization_id", "email");

CREATE INDEX IF NOT EXISTS "idx_subscriptions__organization_id__status" ON "subscriptions" ("organization_id", "status");

CREATE INDEX IF NOT EXISTS "idx_org_lifecycle_events__organization_id__occurred_at" ON "org_lifecycle_events" ("organization_id", "occurred_at");

CREATE INDEX IF NOT EXISTS "idx_support_tickets__organization_id__status" ON "support_tickets" ("organization_id", "status");

CREATE INDEX IF NOT EXISTS "idx_support_tickets__reference_id" ON "support_tickets" ("reference_id");

CREATE INDEX IF NOT EXISTS "idx_org_admin_notes__organization_id__created_at" ON "org_admin_notes" ("organization_id", "created_at");