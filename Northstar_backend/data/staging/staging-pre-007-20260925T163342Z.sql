--
-- PostgreSQL database dump
--

\restrict XdDe0Q4tCf10NpGx7kW1SdaKiImBshyZndqw5fL5acrUSUVgdVfRwSQnuBqRKBN

-- Dumped from database version 15.19 (Debian 15.19-1.pgdg13+2)
-- Dumped by pg_dump version 15.19 (Debian 15.19-1.pgdg13+2)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: acceptance_events; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.acceptance_events (
    id text NOT NULL,
    organization_id text,
    user_id text,
    doc_type text,
    doc_version text,
    content_hash text,
    business_use_attested boolean,
    age_18_attested boolean,
    ip_handling text,
    request_id text,
    correlation_id text,
    accepted_at timestamp with time zone,
    created_at timestamp with time zone
);


ALTER TABLE public.acceptance_events OWNER TO northstar_staging_owner;

--
-- Name: account_acceptance; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.account_acceptance (
    id text NOT NULL,
    organization_id text,
    user_id text,
    privacy_notice_version text,
    terms_of_service_version text,
    acceptable_use_policy_version text,
    business_attested boolean,
    age_18_attested boolean,
    updated_at timestamp with time zone,
    private_beta_addendum_version text
);


ALTER TABLE public.account_acceptance OWNER TO northstar_staging_owner;

--
-- Name: ad_performance_observations; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.ad_performance_observations (
    id text NOT NULL,
    organization_id text,
    search_term_id text,
    campaign_id text,
    ad_group_id text,
    impressions bigint,
    clicks bigint,
    spend numeric,
    orders bigint,
    revenue numeric,
    ctr double precision,
    cvr double precision,
    observed_at timestamp with time zone,
    source text,
    created_at timestamp with time zone
);


ALTER TABLE public.ad_performance_observations OWNER TO northstar_staging_owner;

--
-- Name: approval_decisions; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.approval_decisions (
    id text NOT NULL,
    approval_request_id text,
    decided_by_user_id text,
    decided_by_role text,
    decision text,
    note text,
    decided_at timestamp with time zone
);


ALTER TABLE public.approval_decisions OWNER TO northstar_staging_owner;

--
-- Name: approval_requests; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.approval_requests (
    id text NOT NULL,
    organization_id text,
    requested_by_user_id text,
    capability text,
    safety_class text,
    resource_type text,
    resource_id text,
    change_preview jsonb,
    risk_level text,
    cost_estimate double precision,
    currency text,
    state text,
    required_approver_role text,
    expires_at timestamp with time zone,
    idempotency_key text,
    execution_ref text,
    environment text,
    created_at timestamp with time zone
);


ALTER TABLE public.approval_requests OWNER TO northstar_staging_owner;

--
-- Name: audit_events; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.audit_events (
    id text NOT NULL,
    actor_user_id text,
    actor_role text,
    organization_id text,
    target_organization_id text,
    target_user_id text,
    action text,
    resource_type text,
    resource_id text,
    before_meta jsonb,
    after_meta jsonb,
    environment text,
    view_context text,
    approval_ref text,
    job_run_ref text,
    result text,
    failure_class text,
    occurred_at timestamp with time zone,
    correlation_id text
);


ALTER TABLE public.audit_events OWNER TO northstar_staging_owner;

--
-- Name: billing_customers; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.billing_customers (
    id text NOT NULL,
    organization_id text,
    processor text,
    processor_customer_id text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


ALTER TABLE public.billing_customers OWNER TO northstar_staging_owner;

--
-- Name: billing_events; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.billing_events (
    id text NOT NULL,
    processor_event_id text,
    event_type text,
    payload_hash text,
    status text,
    processed_at timestamp with time zone,
    created_at timestamp with time zone
);


ALTER TABLE public.billing_events OWNER TO northstar_staging_owner;

--
-- Name: catalog_products; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.catalog_products (
    id text NOT NULL,
    marketplace_id text,
    asin text,
    brand text,
    canonical_title text,
    pack_config_id text,
    variation_family_id text,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


ALTER TABLE public.catalog_products OWNER TO northstar_staging_owner;

--
-- Name: checkout_sessions; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.checkout_sessions (
    id text NOT NULL,
    organization_id text,
    price_id text,
    tier text,
    status text,
    expires_at timestamp with time zone,
    created_at timestamp with time zone
);


ALTER TABLE public.checkout_sessions OWNER TO northstar_staging_owner;

--
-- Name: identity_conflicts; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.identity_conflicts (
    id text NOT NULL,
    conflict_type text,
    candidate_id text,
    product_id text,
    detail text,
    created_at timestamp with time zone
);


ALTER TABLE public.identity_conflicts OWNER TO northstar_staging_owner;

--
-- Name: import_batches; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.import_batches (
    id text NOT NULL,
    organization_id text,
    source_file_id text,
    status text,
    submitted_by text,
    submitted_at timestamp with time zone,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    summary jsonb,
    created_at timestamp with time zone
);


ALTER TABLE public.import_batches OWNER TO northstar_staging_owner;

--
-- Name: invites; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.invites (
    id text NOT NULL,
    organization_id text,
    invite_code text,
    email text,
    role text,
    status text,
    created_by text,
    expires_at timestamp with time zone,
    used_at timestamp with time zone,
    created_at timestamp with time zone
);


ALTER TABLE public.invites OWNER TO northstar_staging_owner;

--
-- Name: job_requests; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.job_requests (
    id text NOT NULL,
    organization_id text,
    user_id text,
    service text,
    scope_type text,
    scope_id text,
    data_types jsonb,
    provider_policy text,
    max_estimated_cost double precision,
    currency text,
    environment text,
    idempotency_key text,
    requires_approval boolean,
    reason text,
    priority bigint,
    created_at timestamp with time zone,
    state text,
    job_type text,
    payload jsonb,
    payload_schema_version text,
    approval_id text,
    provider_class text,
    budget_class text,
    estimated_cost numeric,
    parent_job_id text,
    correlation_id text,
    provenance jsonb
);


ALTER TABLE public.job_requests OWNER TO northstar_staging_owner;

--
-- Name: job_runs; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.job_runs (
    id text NOT NULL,
    job_request_id text,
    state text,
    run_id text,
    attempts bigint,
    max_attempts bigint,
    failure_class text,
    error_message text,
    started_at timestamp with time zone,
    finished_at timestamp with time zone,
    created_at timestamp with time zone,
    priority bigint,
    reserved_cost numeric,
    actual_cost numeric,
    scheduled_time timestamp with time zone,
    heartbeat_time timestamp with time zone,
    lease_owner text,
    lease_expiration timestamp with time zone,
    idempotency_key text,
    parent_job_id text,
    correlation_id text,
    output_reference text,
    error_code text,
    error_summary text,
    cancellation_state text
);


ALTER TABLE public.job_runs OWNER TO northstar_staging_owner;

--
-- Name: job_schedules; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.job_schedules (
    id text NOT NULL,
    organization_id text,
    owner_user_id text,
    job_template jsonb,
    timezone text,
    cron_expression text,
    interval_seconds bigint,
    enabled boolean,
    next_run_at timestamp with time zone,
    last_run_at timestamp with time zone,
    concurrency_policy jsonb,
    misfire_policy text,
    approval_policy jsonb,
    budget_policy jsonb,
    provider_policy jsonb,
    failure_policy jsonb,
    version text,
    archived boolean,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


ALTER TABLE public.job_schedules OWNER TO northstar_staging_owner;

--
-- Name: job_state_history; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.job_state_history (
    id text NOT NULL,
    job_id text,
    run_id text,
    previous_state text,
    new_state text,
    actor text,
    reason text,
    correlation_id text,
    audit_event_ref text,
    occurred_at timestamp with time zone
);


ALTER TABLE public.job_state_history OWNER TO northstar_staging_owner;

--
-- Name: keyword_conflicts; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.keyword_conflicts (
    id text NOT NULL,
    organization_id text,
    keyword_id_a text,
    keyword_id_b text,
    conflict_type text,
    detail text,
    created_at timestamp with time zone
);


ALTER TABLE public.keyword_conflicts OWNER TO northstar_staging_owner;

--
-- Name: keyword_links; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.keyword_links (
    id text NOT NULL,
    organization_id text,
    keyword_id text,
    link_kind text,
    target_ref text,
    asin text,
    product_id text,
    note text,
    created_at timestamp with time zone
);


ALTER TABLE public.keyword_links OWNER TO northstar_staging_owner;

--
-- Name: keywords; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.keywords (
    id text NOT NULL,
    organization_id text,
    normalized_phrase text,
    original_phrase text,
    marketplace text,
    language text,
    match_type text,
    brand_terms jsonb,
    confidence double precision,
    freshness_state text,
    created_at timestamp with time zone
);


ALTER TABLE public.keywords OWNER TO northstar_staging_owner;

--
-- Name: legal_documents; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.legal_documents (
    id text NOT NULL,
    doc_type text,
    version text,
    title text,
    content_hash text,
    status text,
    published_at timestamp with time zone,
    created_at timestamp with time zone
);


ALTER TABLE public.legal_documents OWNER TO northstar_staging_owner;

--
-- Name: marketplaces; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.marketplaces (
    id text NOT NULL,
    code text,
    country text,
    currency text,
    domain text,
    active boolean
);


ALTER TABLE public.marketplaces OWNER TO northstar_staging_owner;

--
-- Name: memberships; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.memberships (
    id text NOT NULL,
    organization_id text,
    user_id text,
    role text,
    status text,
    created_at timestamp with time zone
);


ALTER TABLE public.memberships OWNER TO northstar_staging_owner;

--
-- Name: normalization_decisions; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.normalization_decisions (
    id text NOT NULL,
    organization_id text,
    original_phrase text,
    normalized_phrase text,
    rule jsonb,
    created_at timestamp with time zone
);


ALTER TABLE public.normalization_decisions OWNER TO northstar_staging_owner;

--
-- Name: observations; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.observations (
    id text NOT NULL,
    product_id text,
    candidate_id text,
    marketplace_id text,
    provider text,
    provider_record_id text,
    observation_type text,
    observed_value jsonb,
    currency text,
    unit text,
    captured_at timestamp with time zone,
    effective_at timestamp with time zone,
    expires_at timestamp with time zone,
    confidence double precision,
    verification_state text,
    provenance_class text,
    raw_source_ref text,
    transformation_version text,
    job_run_id text,
    environment text,
    created_at timestamp with time zone
);


ALTER TABLE public.observations OWNER TO northstar_staging_owner;

--
-- Name: org_balances; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.org_balances (
    organization_id text NOT NULL,
    granted numeric,
    reserved numeric,
    consumed numeric,
    updated_at timestamp with time zone
);


ALTER TABLE public.org_balances OWNER TO northstar_staging_owner;

--
-- Name: org_entitlements; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.org_entitlements (
    organization_id text NOT NULL,
    tier text,
    max_jobs_per_month bigint,
    export_enabled boolean,
    advanced_reports boolean,
    seat_limit bigint,
    updated_at timestamp with time zone
);


ALTER TABLE public.org_entitlements OWNER TO northstar_staging_owner;

--
-- Name: organizations; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.organizations (
    id text NOT NULL,
    name text,
    slug text,
    environment text,
    active boolean,
    created_at timestamp with time zone
);


ALTER TABLE public.organizations OWNER TO northstar_staging_owner;

--
-- Name: pack_configs; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.pack_configs (
    id text NOT NULL,
    product_id text,
    count bigint,
    unit text,
    unit_type text,
    is_multipack boolean,
    is_bundle boolean,
    verification_state text
);


ALTER TABLE public.pack_configs OWNER TO northstar_staging_owner;

--
-- Name: preview_sessions; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.preview_sessions (
    id text NOT NULL,
    actor_user_id text,
    target_organization_id text,
    target_role text,
    started_at timestamp with time zone,
    ended_at timestamp with time zone,
    reason text,
    read_only boolean,
    active boolean
);


ALTER TABLE public.preview_sessions OWNER TO northstar_staging_owner;

--
-- Name: pricing_policies; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.pricing_policies (
    version text NOT NULL,
    platform_markup double precision,
    minimum_charge double precision,
    service_multipliers jsonb,
    free_local_execution boolean,
    failed_run_charge boolean
);


ALTER TABLE public.pricing_policies OWNER TO northstar_staging_owner;

--
-- Name: product_aliases; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.product_aliases (
    id text NOT NULL,
    product_id text,
    alias_value text,
    reason text,
    created_at timestamp with time zone
);


ALTER TABLE public.product_aliases OWNER TO northstar_staging_owner;

--
-- Name: product_identifiers; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.product_identifiers (
    id text NOT NULL,
    product_id text,
    kind text,
    raw_value text,
    normalized_value text,
    marketplace_id text,
    verification_state text,
    created_at timestamp with time zone
);


ALTER TABLE public.product_identifiers OWNER TO northstar_staging_owner;

--
-- Name: providers; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.providers (
    id text NOT NULL,
    provider_key text,
    name text,
    category text,
    adapter_module text,
    read_capable boolean,
    write_capable boolean,
    sandbox_supported boolean,
    credential_ref_names jsonb,
    rate_limit_rpm bigint,
    timeout_seconds bigint,
    cost_model jsonb,
    health text,
    enabled boolean
);


ALTER TABLE public.providers OWNER TO northstar_staging_owner;

--
-- Name: rank_observations; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.rank_observations (
    id text NOT NULL,
    organization_id text,
    keyword_id text,
    asin text,
    rank bigint,
    placement text,
    observed_at timestamp with time zone,
    source text,
    confidence double precision,
    freshness_state text,
    created_at timestamp with time zone
);


ALTER TABLE public.rank_observations OWNER TO northstar_staging_owner;

--
-- Name: rejected_rows; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.rejected_rows (
    id text NOT NULL,
    organization_id text,
    import_batch_id text,
    source_file_id text,
    row_index bigint,
    row_json jsonb,
    rejection_reason text,
    created_at timestamp with time zone
);


ALTER TABLE public.rejected_rows OWNER TO northstar_staging_owner;

--
-- Name: schedule_occurrences; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.schedule_occurrences (
    id text NOT NULL,
    schedule_id text,
    occurrence_key text,
    scheduled_for timestamp with time zone,
    enqueued_job_request_id text,
    state text,
    created_at timestamp with time zone
);


ALTER TABLE public.schedule_occurrences OWNER TO northstar_staging_owner;

--
-- Name: search_terms; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.search_terms (
    id text NOT NULL,
    organization_id text,
    raw_term text,
    normalized_term text,
    marketplace text,
    search_volume bigint,
    observed_volume bigint,
    impressions bigint,
    clicks bigint,
    spend numeric,
    orders bigint,
    revenue numeric,
    source text,
    observed_at timestamp with time zone,
    created_at timestamp with time zone
);


ALTER TABLE public.search_terms OWNER TO northstar_staging_owner;

--
-- Name: sessions; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.sessions (
    jti text NOT NULL,
    user_id text,
    organization_id text,
    issued_at timestamp with time zone,
    expires_at timestamp with time zone,
    revoked_at timestamp with time zone,
    revoked_reason text
);


ALTER TABLE public.sessions OWNER TO northstar_staging_owner;

--
-- Name: source_files; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.source_files (
    id text NOT NULL,
    organization_id text,
    file_name text,
    file_sha256 text,
    file_size bigint,
    marketplace text,
    currency text,
    report_type text,
    date_from timestamp with time zone,
    date_to timestamp with time zone,
    status text,
    registered_at timestamp with time zone,
    created_at timestamp with time zone
);


ALTER TABLE public.source_files OWNER TO northstar_staging_owner;

--
-- Name: source_rows; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.source_rows (
    id text NOT NULL,
    organization_id text,
    import_batch_id text,
    source_file_id text,
    row_index bigint,
    row_json jsonb,
    status text,
    created_at timestamp with time zone
);


ALTER TABLE public.source_rows OWNER TO northstar_staging_owner;

--
-- Name: subscriptions; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.subscriptions (
    id text NOT NULL,
    organization_id text,
    billing_customer_id text,
    processor_subscription_id text,
    price_id text,
    tier text,
    status text,
    current_period_end timestamp with time zone,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


ALTER TABLE public.subscriptions OWNER TO northstar_staging_owner;

--
-- Name: supplier_documentation; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.supplier_documentation (
    id text NOT NULL,
    supplier_id text,
    product_id text,
    supply_state text,
    documentation_state text,
    note text,
    created_at timestamp with time zone
);


ALTER TABLE public.supplier_documentation OWNER TO northstar_staging_owner;

--
-- Name: suppliers; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.suppliers (
    id text NOT NULL,
    name text,
    supplier_class text,
    public_catalog_url text,
    created_at timestamp with time zone
);


ALTER TABLE public.suppliers OWNER TO northstar_staging_owner;

--
-- Name: targets; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.targets (
    id text NOT NULL,
    organization_id text,
    keyword_id text,
    campaign_id text,
    ad_group_id text,
    match_type text,
    bid numeric,
    status text,
    created_at timestamp with time zone
);


ALTER TABLE public.targets OWNER TO northstar_staging_owner;

--
-- Name: ui_preferences; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.ui_preferences (
    user_id text NOT NULL,
    organization_id text NOT NULL,
    key text NOT NULL,
    value jsonb,
    updated_at timestamp with time zone
);


ALTER TABLE public.ui_preferences OWNER TO northstar_staging_owner;

--
-- Name: unresolved_candidates; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.unresolved_candidates (
    id text NOT NULL,
    raw_asin text,
    raw_title text,
    raw_identifier text,
    reason text,
    source text,
    source_identifier text,
    created_at timestamp with time zone
);


ALTER TABLE public.unresolved_candidates OWNER TO northstar_staging_owner;

--
-- Name: usage_events; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.usage_events (
    id text NOT NULL,
    organization_id text,
    user_id text,
    service text,
    workflow_run_id text,
    provider text,
    model_or_endpoint text,
    input_units bigint,
    output_units bigint,
    provider_reported_cost double precision,
    estimated_cost double precision,
    credits_debited_shadow double precision,
    cost_kind text,
    status text,
    idempotency_key text,
    reversal_ref text,
    environment text,
    occurred_at timestamp with time zone,
    provenance jsonb
);


ALTER TABLE public.usage_events OWNER TO northstar_staging_owner;

--
-- Name: users; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.users (
    id text NOT NULL,
    email text,
    display_name text,
    active boolean,
    created_at timestamp with time zone
);


ALTER TABLE public.users OWNER TO northstar_staging_owner;

--
-- Name: variation_relationships; Type: TABLE; Schema: public; Owner: northstar_staging_owner
--

CREATE TABLE public.variation_relationships (
    id text NOT NULL,
    family_id text,
    child_product_id text,
    axis text,
    created_at timestamp with time zone
);


ALTER TABLE public.variation_relationships OWNER TO northstar_staging_owner;

--
-- Data for Name: acceptance_events; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.acceptance_events (id, organization_id, user_id, doc_type, doc_version, content_hash, business_use_attested, age_18_attested, ip_handling, request_id, correlation_id, accepted_at, created_at) FROM stdin;
bb8ee7c9-4fbc-4f9f-b2d8-f8d9605df9ee	1cd446b8-a2b4-43d9-8adb-869d5e854ffc	8809ba90-55dd-48d0-a895-665fc5872741	acceptable_use_policy	1.0	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	t	t	not_stored	dc6ccfba-2029-4523-ac8f-3078de96b935	dc6ccfba-2029-4523-ac8f-3078de96b935	2026-09-25 14:51:12.825434+00	2026-09-25 14:51:12.825435+00
06168b8e-dbef-4d45-a711-ce56e366356d	1cd446b8-a2b4-43d9-8adb-869d5e854ffc	8809ba90-55dd-48d0-a895-665fc5872741	terms_of_service	1.0	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	t	t	not_stored	dc6ccfba-2029-4523-ac8f-3078de96b935	dc6ccfba-2029-4523-ac8f-3078de96b935	2026-09-25 14:51:12.829773+00	2026-09-25 14:51:12.829774+00
ee08aa9e-2891-4322-bc7d-0d8fcff98494	1cd446b8-a2b4-43d9-8adb-869d5e854ffc	8809ba90-55dd-48d0-a895-665fc5872741	privacy_notice	1.0	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	t	t	not_stored	dc6ccfba-2029-4523-ac8f-3078de96b935	dc6ccfba-2029-4523-ac8f-3078de96b935	2026-09-25 14:51:12.833485+00	2026-09-25 14:51:12.833486+00
d7b560ff-8b36-4bf4-b531-772053a9530c	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	acceptable_use_policy	1.0	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	t	t	not_stored	staging-smoke-boot	\N	2026-09-25 14:53:52.520767+00	2026-09-25 14:53:52.520768+00
3b9b9776-5907-4cb0-81d5-4deeb6abe338	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	terms_of_service	1.0	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	t	t	not_stored	staging-smoke-boot	\N	2026-09-25 14:53:52.525709+00	2026-09-25 14:53:52.52571+00
ad9513c8-fa24-4cda-b84b-9f684dddb44c	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	privacy_notice	1.0	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	t	t	not_stored	staging-smoke-boot	\N	2026-09-25 14:53:52.52877+00	2026-09-25 14:53:52.528771+00
47fd6284-1e2e-4ead-bf6d-1c3102672c61	c7bdbe56-d353-42b2-aed6-eb7e9ebe2c0e	2bc09d54-2de2-4d09-bd0c-db716530fe25	acceptable_use_policy	1.0	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 14:53:53.219347+00	2026-09-25 14:53:53.219348+00
f4e8b19b-206e-4576-8cfd-ccb3b5ca14cb	c7bdbe56-d353-42b2-aed6-eb7e9ebe2c0e	2bc09d54-2de2-4d09-bd0c-db716530fe25	terms_of_service	1.0	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 14:53:53.222217+00	2026-09-25 14:53:53.222218+00
0d1a2ed4-b12b-4a1b-af4c-b0fa90f10344	c7bdbe56-d353-42b2-aed6-eb7e9ebe2c0e	2bc09d54-2de2-4d09-bd0c-db716530fe25	privacy_notice	1.0	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 14:53:53.225372+00	2026-09-25 14:53:53.225373+00
3b8b6b16-d979-4412-9c04-c6a9cfba061b	1c30d9ed-d52a-42ed-a4b9-e0bd0f1090eb	4aaa159d-cfe8-41f6-8c52-d2f2d9c214c4	acceptable_use_policy	1.0	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	t	t	not_stored	474753c5-7f67-4470-9a35-83e20b89c2f3	474753c5-7f67-4470-9a35-83e20b89c2f3	2026-09-25 14:53:53.31762+00	2026-09-25 14:53:53.317621+00
18b8d9cb-da21-4567-bd95-f266753a54e3	1c30d9ed-d52a-42ed-a4b9-e0bd0f1090eb	4aaa159d-cfe8-41f6-8c52-d2f2d9c214c4	terms_of_service	1.0	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	t	t	not_stored	474753c5-7f67-4470-9a35-83e20b89c2f3	474753c5-7f67-4470-9a35-83e20b89c2f3	2026-09-25 14:53:53.320571+00	2026-09-25 14:53:53.320571+00
9685c36e-6c87-42c9-8107-36c3c52a3293	1c30d9ed-d52a-42ed-a4b9-e0bd0f1090eb	4aaa159d-cfe8-41f6-8c52-d2f2d9c214c4	privacy_notice	1.0	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	t	t	not_stored	474753c5-7f67-4470-9a35-83e20b89c2f3	474753c5-7f67-4470-9a35-83e20b89c2f3	2026-09-25 14:53:53.32327+00	2026-09-25 14:53:53.323271+00
3ef24de6-b12e-4ea6-8189-53f2ee4f6bde	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	private_beta_addendum	1.0	00c72e991638fc7495f88dc3afc86c6e33ca8487aa267c3fb65f2e382f514339	t	t	not_stored	staging-smoke-boot	\N	2026-09-25 15:37:31.389671+00	2026-09-25 15:37:31.389672+00
c7daf0c3-bb81-4c48-8adf-19a0bd480013	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	acceptable_use_policy	1.0	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	t	t	not_stored	staging-smoke-boot	\N	2026-09-25 15:37:31.393078+00	2026-09-25 15:37:31.393078+00
51846453-163e-43aa-ab11-c9f77f5e7473	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	terms_of_service	1.0	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	t	t	not_stored	staging-smoke-boot	\N	2026-09-25 15:37:31.395905+00	2026-09-25 15:37:31.395906+00
ae0a5c6e-3187-4537-8fcd-29837e6a2fc5	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	privacy_notice	1.0	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	t	t	not_stored	staging-smoke-boot	\N	2026-09-25 15:37:31.398724+00	2026-09-25 15:37:31.398725+00
2f07f400-0bb4-41e9-9c7c-1df980bb00cc	41f1bdb5-5143-4fc1-804e-45c1d0ad024f	8d23329e-c826-4cf3-9351-e8675d2c55c5	private_beta_addendum	1.0	00c72e991638fc7495f88dc3afc86c6e33ca8487aa267c3fb65f2e382f514339	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 15:37:32.149821+00	2026-09-25 15:37:32.149822+00
c4b9dc39-eb46-429d-b069-de26d7166641	41f1bdb5-5143-4fc1-804e-45c1d0ad024f	8d23329e-c826-4cf3-9351-e8675d2c55c5	acceptable_use_policy	1.0	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 15:37:32.153301+00	2026-09-25 15:37:32.153302+00
fa6b4f9b-4185-45b3-88ae-2f96b96836f8	41f1bdb5-5143-4fc1-804e-45c1d0ad024f	8d23329e-c826-4cf3-9351-e8675d2c55c5	terms_of_service	1.0	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 15:37:32.157179+00	2026-09-25 15:37:32.15718+00
ddaea716-e4bf-42f2-a40b-72488a696494	41f1bdb5-5143-4fc1-804e-45c1d0ad024f	8d23329e-c826-4cf3-9351-e8675d2c55c5	privacy_notice	1.0	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 15:37:32.159871+00	2026-09-25 15:37:32.159872+00
d3ecab6b-b199-49a2-989a-e6f401a3aa1f	8856d797-5714-421e-9b68-21977321152b	f8970e4e-f2bc-46e5-b1e2-6de99e823130	private_beta_addendum	1.0	00c72e991638fc7495f88dc3afc86c6e33ca8487aa267c3fb65f2e382f514339	t	t	not_stored	9b0428e1-635f-471a-9af3-d138786dee4b	9b0428e1-635f-471a-9af3-d138786dee4b	2026-09-25 15:37:32.278174+00	2026-09-25 15:37:32.278175+00
33ae8b26-cb0a-40b1-9708-4b87cca015b2	8856d797-5714-421e-9b68-21977321152b	f8970e4e-f2bc-46e5-b1e2-6de99e823130	acceptable_use_policy	1.0	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	t	t	not_stored	9b0428e1-635f-471a-9af3-d138786dee4b	9b0428e1-635f-471a-9af3-d138786dee4b	2026-09-25 15:37:32.281228+00	2026-09-25 15:37:32.281229+00
bf5fe5a1-19e5-49c4-a9da-888191d32ccb	8856d797-5714-421e-9b68-21977321152b	f8970e4e-f2bc-46e5-b1e2-6de99e823130	terms_of_service	1.0	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	t	t	not_stored	9b0428e1-635f-471a-9af3-d138786dee4b	9b0428e1-635f-471a-9af3-d138786dee4b	2026-09-25 15:37:32.284119+00	2026-09-25 15:37:32.284119+00
ed53682b-bde0-489f-9a8d-d949606c2a6a	8856d797-5714-421e-9b68-21977321152b	f8970e4e-f2bc-46e5-b1e2-6de99e823130	privacy_notice	1.0	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	t	t	not_stored	9b0428e1-635f-471a-9af3-d138786dee4b	9b0428e1-635f-471a-9af3-d138786dee4b	2026-09-25 15:37:32.28699+00	2026-09-25 15:37:32.28699+00
84685994-8c7e-45f3-8d24-6e76ffa196d0	a5dec5ab-0b73-43e7-b488-fa4b5dcbd340	2e02cc0b-0696-4647-b1b9-a8187761767e	private_beta_addendum	1.0	00c72e991638fc7495f88dc3afc86c6e33ca8487aa267c3fb65f2e382f514339	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 15:38:04.585847+00	2026-09-25 15:38:04.585848+00
fe8e6f94-6bc9-4663-86a7-383158914d24	a5dec5ab-0b73-43e7-b488-fa4b5dcbd340	2e02cc0b-0696-4647-b1b9-a8187761767e	acceptable_use_policy	1.0	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 15:38:04.589954+00	2026-09-25 15:38:04.589955+00
ccfdb836-3306-4e02-97c9-f81747a898ce	a5dec5ab-0b73-43e7-b488-fa4b5dcbd340	2e02cc0b-0696-4647-b1b9-a8187761767e	terms_of_service	1.0	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 15:38:04.592864+00	2026-09-25 15:38:04.592865+00
4a08e850-06a0-45c6-804d-eeb076199b2f	a5dec5ab-0b73-43e7-b488-fa4b5dcbd340	2e02cc0b-0696-4647-b1b9-a8187761767e	privacy_notice	1.0	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 15:38:04.595708+00	2026-09-25 15:38:04.595709+00
fb698a25-e677-4c45-813e-3e4ed1ed8873	9b6e00cd-d3cc-49f2-ab24-e45c50d89b55	189e1da9-2344-4468-aa4c-41235f9bd9c0	private_beta_addendum	1.0	00c72e991638fc7495f88dc3afc86c6e33ca8487aa267c3fb65f2e382f514339	t	t	not_stored	7be3e2a1-7951-42a0-aec7-93fdfb51aee7	7be3e2a1-7951-42a0-aec7-93fdfb51aee7	2026-09-25 15:38:04.697422+00	2026-09-25 15:38:04.697423+00
ce988243-a9b1-4dce-a14b-d432dfe2a8fa	9b6e00cd-d3cc-49f2-ab24-e45c50d89b55	189e1da9-2344-4468-aa4c-41235f9bd9c0	acceptable_use_policy	1.0	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	t	t	not_stored	7be3e2a1-7951-42a0-aec7-93fdfb51aee7	7be3e2a1-7951-42a0-aec7-93fdfb51aee7	2026-09-25 15:38:04.700805+00	2026-09-25 15:38:04.700805+00
5b9a1eea-20e2-40ba-b7f5-d9cd58d8a9e0	9b6e00cd-d3cc-49f2-ab24-e45c50d89b55	189e1da9-2344-4468-aa4c-41235f9bd9c0	terms_of_service	1.0	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	t	t	not_stored	7be3e2a1-7951-42a0-aec7-93fdfb51aee7	7be3e2a1-7951-42a0-aec7-93fdfb51aee7	2026-09-25 15:38:04.704083+00	2026-09-25 15:38:04.704084+00
519ba8e6-7287-4c7e-bbf6-8c3366d44e21	9b6e00cd-d3cc-49f2-ab24-e45c50d89b55	189e1da9-2344-4468-aa4c-41235f9bd9c0	privacy_notice	1.0	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	t	t	not_stored	7be3e2a1-7951-42a0-aec7-93fdfb51aee7	7be3e2a1-7951-42a0-aec7-93fdfb51aee7	2026-09-25 15:38:04.706764+00	2026-09-25 15:38:04.706765+00
4cf77d96-f250-4d8a-9f69-4715348c2618	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	d16118e8-09c3-45f9-becf-772303be6bda	private_beta_addendum	1.0	00c72e991638fc7495f88dc3afc86c6e33ca8487aa267c3fb65f2e382f514339	t	t	not_stored	9942a6dc-1a72-4c91-8624-d9cff1f7532c	9942a6dc-1a72-4c91-8624-d9cff1f7532c	2026-09-25 15:38:04.793356+00	2026-09-25 15:38:04.793357+00
4e3ed938-ff7b-4664-9933-cfc12045fec4	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	d16118e8-09c3-45f9-becf-772303be6bda	acceptable_use_policy	1.0	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	t	t	not_stored	9942a6dc-1a72-4c91-8624-d9cff1f7532c	9942a6dc-1a72-4c91-8624-d9cff1f7532c	2026-09-25 15:38:04.796576+00	2026-09-25 15:38:04.796577+00
942712de-949e-4495-ba1d-987228fc3f5b	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	d16118e8-09c3-45f9-becf-772303be6bda	terms_of_service	1.0	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	t	t	not_stored	9942a6dc-1a72-4c91-8624-d9cff1f7532c	9942a6dc-1a72-4c91-8624-d9cff1f7532c	2026-09-25 15:38:04.799584+00	2026-09-25 15:38:04.799585+00
2de033cf-26bc-44c0-be9d-7613213afcfd	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	d16118e8-09c3-45f9-becf-772303be6bda	privacy_notice	1.0	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	t	t	not_stored	9942a6dc-1a72-4c91-8624-d9cff1f7532c	9942a6dc-1a72-4c91-8624-d9cff1f7532c	2026-09-25 15:38:04.802332+00	2026-09-25 15:38:04.802333+00
19d4e071-1d7c-43f3-921f-249a860e0880	b93d2fc7-f156-4553-b08c-c91232e68197	a647b2b4-57a1-4ac0-9ae1-de5e30a866e5	private_beta_addendum	1.0	00c72e991638fc7495f88dc3afc86c6e33ca8487aa267c3fb65f2e382f514339	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 15:39:15.772938+00	2026-09-25 15:39:15.772939+00
173a547b-a7d9-4934-ace9-a4ff3763d02f	b93d2fc7-f156-4553-b08c-c91232e68197	a647b2b4-57a1-4ac0-9ae1-de5e30a866e5	acceptable_use_policy	1.0	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 15:39:15.775976+00	2026-09-25 15:39:15.775977+00
119aed5b-54fb-4739-b4ca-479743383de5	b93d2fc7-f156-4553-b08c-c91232e68197	a647b2b4-57a1-4ac0-9ae1-de5e30a866e5	terms_of_service	1.0	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 15:39:15.778848+00	2026-09-25 15:39:15.778848+00
6fb6d172-f056-451a-99dd-1e5a98cc290f	b93d2fc7-f156-4553-b08c-c91232e68197	a647b2b4-57a1-4ac0-9ae1-de5e30a866e5	privacy_notice	1.0	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 15:39:15.781769+00	2026-09-25 15:39:15.78177+00
c5758cd0-84c9-4cec-b187-471fec9eec2f	8f3d00ce-4706-4049-88b1-f080bbb33ffc	4862db1a-85f3-49c1-bed2-1def9d383dbe	private_beta_addendum	1.0	00c72e991638fc7495f88dc3afc86c6e33ca8487aa267c3fb65f2e382f514339	t	t	not_stored	e46484e4-90ca-4807-87e2-5c7258aec0f5	e46484e4-90ca-4807-87e2-5c7258aec0f5	2026-09-25 15:39:15.881883+00	2026-09-25 15:39:15.881884+00
554bcc6a-2cae-40ce-b02a-9c3bd9017adc	8f3d00ce-4706-4049-88b1-f080bbb33ffc	4862db1a-85f3-49c1-bed2-1def9d383dbe	acceptable_use_policy	1.0	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	t	t	not_stored	e46484e4-90ca-4807-87e2-5c7258aec0f5	e46484e4-90ca-4807-87e2-5c7258aec0f5	2026-09-25 15:39:15.885192+00	2026-09-25 15:39:15.885193+00
0efae625-df00-4a25-a4be-9e8c4ba506bd	8f3d00ce-4706-4049-88b1-f080bbb33ffc	4862db1a-85f3-49c1-bed2-1def9d383dbe	terms_of_service	1.0	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	t	t	not_stored	e46484e4-90ca-4807-87e2-5c7258aec0f5	e46484e4-90ca-4807-87e2-5c7258aec0f5	2026-09-25 15:39:15.8889+00	2026-09-25 15:39:15.888901+00
a2c02861-a8d5-474d-9d04-90b7e4554aff	8f3d00ce-4706-4049-88b1-f080bbb33ffc	4862db1a-85f3-49c1-bed2-1def9d383dbe	privacy_notice	1.0	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	t	t	not_stored	e46484e4-90ca-4807-87e2-5c7258aec0f5	e46484e4-90ca-4807-87e2-5c7258aec0f5	2026-09-25 15:39:15.89182+00	2026-09-25 15:39:15.891821+00
e6bce9f2-5251-4526-a80a-9d40fa48fe4c	993df0b6-4bdb-43ea-9e50-715141765180	c46f4c20-58bb-4669-8d5f-1cb18ff0b94a	private_beta_addendum	1.0	00c72e991638fc7495f88dc3afc86c6e33ca8487aa267c3fb65f2e382f514339	t	t	not_stored	e2e-admin-accept	\N	2026-09-25 15:39:15.949644+00	2026-09-25 15:39:15.949644+00
df078218-bae0-4d90-8c48-ee70cc2f5b9c	993df0b6-4bdb-43ea-9e50-715141765180	c46f4c20-58bb-4669-8d5f-1cb18ff0b94a	acceptable_use_policy	1.0	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	t	t	not_stored	e2e-admin-accept	\N	2026-09-25 15:39:15.952686+00	2026-09-25 15:39:15.952687+00
db4e4013-d8cd-452a-85d5-d2febc21b76e	993df0b6-4bdb-43ea-9e50-715141765180	c46f4c20-58bb-4669-8d5f-1cb18ff0b94a	terms_of_service	1.0	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	t	t	not_stored	e2e-admin-accept	\N	2026-09-25 15:39:15.956674+00	2026-09-25 15:39:15.956675+00
92ea8c6e-dd0f-4d58-98f3-f41381da79d4	993df0b6-4bdb-43ea-9e50-715141765180	c46f4c20-58bb-4669-8d5f-1cb18ff0b94a	privacy_notice	1.0	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	t	t	not_stored	e2e-admin-accept	\N	2026-09-25 15:39:15.960797+00	2026-09-25 15:39:15.960798+00
c753bd5e-b2e0-4105-aafb-5340c8668e64	993df0b6-4bdb-43ea-9e50-715141765180	b0e01231-2313-441a-9bc8-f12449d3d249	private_beta_addendum	1.0	00c72e991638fc7495f88dc3afc86c6e33ca8487aa267c3fb65f2e382f514339	t	t	not_stored	ebca4939-f3ec-474b-b784-88b70424218b	ebca4939-f3ec-474b-b784-88b70424218b	2026-09-25 15:39:16.016755+00	2026-09-25 15:39:16.016755+00
9bcd5567-61c4-4f0f-895d-ef58c51ee822	993df0b6-4bdb-43ea-9e50-715141765180	b0e01231-2313-441a-9bc8-f12449d3d249	acceptable_use_policy	1.0	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	t	t	not_stored	ebca4939-f3ec-474b-b784-88b70424218b	ebca4939-f3ec-474b-b784-88b70424218b	2026-09-25 15:39:16.01952+00	2026-09-25 15:39:16.019521+00
ccb4123c-573a-4519-a105-75fc8aaaf989	993df0b6-4bdb-43ea-9e50-715141765180	b0e01231-2313-441a-9bc8-f12449d3d249	terms_of_service	1.0	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	t	t	not_stored	ebca4939-f3ec-474b-b784-88b70424218b	ebca4939-f3ec-474b-b784-88b70424218b	2026-09-25 15:39:16.022284+00	2026-09-25 15:39:16.022285+00
980812ce-34e5-4397-9d22-ef474aaa4c6d	993df0b6-4bdb-43ea-9e50-715141765180	b0e01231-2313-441a-9bc8-f12449d3d249	privacy_notice	1.0	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	t	t	not_stored	ebca4939-f3ec-474b-b784-88b70424218b	ebca4939-f3ec-474b-b784-88b70424218b	2026-09-25 15:39:16.02509+00	2026-09-25 15:39:16.025091+00
1ad730bd-1b65-483f-8a34-e5fd8c572d9d	5c20de09-2a06-431d-baf3-ac644f4fec9d	ab799989-4af7-44f5-8fe8-c85147cc9d5d	private_beta_addendum	1.0	00c72e991638fc7495f88dc3afc86c6e33ca8487aa267c3fb65f2e382f514339	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 15:39:50.704998+00	2026-09-25 15:39:50.704999+00
c240dfcd-7761-48a5-99eb-cf4ba42ff5e2	5c20de09-2a06-431d-baf3-ac644f4fec9d	ab799989-4af7-44f5-8fe8-c85147cc9d5d	acceptable_use_policy	1.0	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 15:39:50.707961+00	2026-09-25 15:39:50.707962+00
439f4dc4-5028-4b93-8ea1-f1bd0e655456	5c20de09-2a06-431d-baf3-ac644f4fec9d	ab799989-4af7-44f5-8fe8-c85147cc9d5d	terms_of_service	1.0	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 15:39:50.710786+00	2026-09-25 15:39:50.710787+00
72ef560b-09e1-4ef9-8faa-621dd2c71f8d	5c20de09-2a06-431d-baf3-ac644f4fec9d	ab799989-4af7-44f5-8fe8-c85147cc9d5d	privacy_notice	1.0	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	t	t	not_stored	staging-smoke-authz-viewer	\N	2026-09-25 15:39:50.713713+00	2026-09-25 15:39:50.713714+00
c95f4765-2a3e-4360-ade2-fce43adb4b86	0d9868c5-1b93-4b0c-b8d6-8a97cb21594e	99d0d2b9-2ad9-4e96-bf2f-d0e2d89a7ff5	private_beta_addendum	1.0	00c72e991638fc7495f88dc3afc86c6e33ca8487aa267c3fb65f2e382f514339	t	t	not_stored	1b85e5a8-d475-40a3-805e-2d1d27528157	1b85e5a8-d475-40a3-805e-2d1d27528157	2026-09-25 15:39:50.81107+00	2026-09-25 15:39:50.811071+00
5b499420-e3d2-4096-b804-dd78c4e96288	0d9868c5-1b93-4b0c-b8d6-8a97cb21594e	99d0d2b9-2ad9-4e96-bf2f-d0e2d89a7ff5	acceptable_use_policy	1.0	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	t	t	not_stored	1b85e5a8-d475-40a3-805e-2d1d27528157	1b85e5a8-d475-40a3-805e-2d1d27528157	2026-09-25 15:39:50.814432+00	2026-09-25 15:39:50.814433+00
b481abc4-ea57-44d5-9aa3-125eca189987	0d9868c5-1b93-4b0c-b8d6-8a97cb21594e	99d0d2b9-2ad9-4e96-bf2f-d0e2d89a7ff5	terms_of_service	1.0	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	t	t	not_stored	1b85e5a8-d475-40a3-805e-2d1d27528157	1b85e5a8-d475-40a3-805e-2d1d27528157	2026-09-25 15:39:50.817893+00	2026-09-25 15:39:50.817893+00
bdf7fcd8-1965-48c3-99c2-a3daa2401fba	0d9868c5-1b93-4b0c-b8d6-8a97cb21594e	99d0d2b9-2ad9-4e96-bf2f-d0e2d89a7ff5	privacy_notice	1.0	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	t	t	not_stored	1b85e5a8-d475-40a3-805e-2d1d27528157	1b85e5a8-d475-40a3-805e-2d1d27528157	2026-09-25 15:39:50.820649+00	2026-09-25 15:39:50.82065+00
b97a1d8b-09c1-4906-8521-1f372d45387b	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	16d2ec3e-5c6c-4f5e-ae69-a9a3c058b69e	private_beta_addendum	1.0	00c72e991638fc7495f88dc3afc86c6e33ca8487aa267c3fb65f2e382f514339	t	t	not_stored	e2e-admin-accept	\N	2026-09-25 15:39:50.876655+00	2026-09-25 15:39:50.876656+00
ac00bf40-6913-47b6-b32f-1f9a967fb5ca	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	16d2ec3e-5c6c-4f5e-ae69-a9a3c058b69e	acceptable_use_policy	1.0	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	t	t	not_stored	e2e-admin-accept	\N	2026-09-25 15:39:50.879422+00	2026-09-25 15:39:50.879423+00
7741cfbf-0d38-44a2-853d-0f7f6dbf22cd	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	16d2ec3e-5c6c-4f5e-ae69-a9a3c058b69e	terms_of_service	1.0	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	t	t	not_stored	e2e-admin-accept	\N	2026-09-25 15:39:50.882178+00	2026-09-25 15:39:50.882179+00
ee9a5260-e182-4a9c-a086-f81c96f9d2bd	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	16d2ec3e-5c6c-4f5e-ae69-a9a3c058b69e	privacy_notice	1.0	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	t	t	not_stored	e2e-admin-accept	\N	2026-09-25 15:39:50.88508+00	2026-09-25 15:39:50.885081+00
43902828-2284-4a58-a4ec-249f3387c944	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	private_beta_addendum	1.0	00c72e991638fc7495f88dc3afc86c6e33ca8487aa267c3fb65f2e382f514339	t	t	not_stored	a3c4943b-5daa-4e26-ae22-3730d27d3e25	a3c4943b-5daa-4e26-ae22-3730d27d3e25	2026-09-25 15:39:50.937077+00	2026-09-25 15:39:50.937077+00
6bf3bfde-76c4-4924-ab8d-96ad681f9998	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	acceptable_use_policy	1.0	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	t	t	not_stored	a3c4943b-5daa-4e26-ae22-3730d27d3e25	a3c4943b-5daa-4e26-ae22-3730d27d3e25	2026-09-25 15:39:50.94008+00	2026-09-25 15:39:50.94008+00
9a6a704f-9877-4f3a-87f1-0fa47f904283	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	terms_of_service	1.0	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	t	t	not_stored	a3c4943b-5daa-4e26-ae22-3730d27d3e25	a3c4943b-5daa-4e26-ae22-3730d27d3e25	2026-09-25 15:39:50.942725+00	2026-09-25 15:39:50.942726+00
0ce5e526-e04f-4330-acf3-9d328cca8380	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	privacy_notice	1.0	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	t	t	not_stored	a3c4943b-5daa-4e26-ae22-3730d27d3e25	a3c4943b-5daa-4e26-ae22-3730d27d3e25	2026-09-25 15:39:50.945366+00	2026-09-25 15:39:50.945366+00
\.


--
-- Data for Name: account_acceptance; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.account_acceptance (id, organization_id, user_id, privacy_notice_version, terms_of_service_version, acceptable_use_policy_version, business_attested, age_18_attested, updated_at, private_beta_addendum_version) FROM stdin;
2bc39c9275ec4c18a47b4a7358662c39	1cd446b8-a2b4-43d9-8adb-869d5e854ffc	8809ba90-55dd-48d0-a895-665fc5872741	1.0	1.0	1.0	t	t	2026-09-25 14:51:12.836776+00	\N
6004dc20636c4da0a83ca83bf9f26b81	c7bdbe56-d353-42b2-aed6-eb7e9ebe2c0e	2bc09d54-2de2-4d09-bd0c-db716530fe25	1.0	1.0	1.0	t	t	2026-09-25 14:53:53.228675+00	\N
9105630160d846dba9f107349243149c	1c30d9ed-d52a-42ed-a4b9-e0bd0f1090eb	4aaa159d-cfe8-41f6-8c52-d2f2d9c214c4	1.0	1.0	1.0	t	t	2026-09-25 14:53:53.325744+00	\N
6b98ab1322a64ef5b89d8430484d380c	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	1.0	1.0	1.0	t	t	2026-09-25 15:37:31.401647+00	1.0
fa1f0a08b2794799abd1bc246fdd8100	41f1bdb5-5143-4fc1-804e-45c1d0ad024f	8d23329e-c826-4cf3-9351-e8675d2c55c5	1.0	1.0	1.0	t	t	2026-09-25 15:37:32.162137+00	1.0
819a9d88db15478a83b187a7108d39cf	8856d797-5714-421e-9b68-21977321152b	f8970e4e-f2bc-46e5-b1e2-6de99e823130	1.0	1.0	1.0	t	t	2026-09-25 15:37:32.28929+00	1.0
15789f9a6d014c6087065abb52b26ae9	a5dec5ab-0b73-43e7-b488-fa4b5dcbd340	2e02cc0b-0696-4647-b1b9-a8187761767e	1.0	1.0	1.0	t	t	2026-09-25 15:38:04.598087+00	1.0
490eeb87b435443f942aed8a274c04b1	9b6e00cd-d3cc-49f2-ab24-e45c50d89b55	189e1da9-2344-4468-aa4c-41235f9bd9c0	1.0	1.0	1.0	t	t	2026-09-25 15:38:04.70904+00	1.0
2ae1d0b52ef54eb48dfe113d2cbf4ec0	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	d16118e8-09c3-45f9-becf-772303be6bda	1.0	1.0	1.0	t	t	2026-09-25 15:38:04.804674+00	1.0
af8220ad28774bda854776c47b818f9f	b93d2fc7-f156-4553-b08c-c91232e68197	a647b2b4-57a1-4ac0-9ae1-de5e30a866e5	1.0	1.0	1.0	t	t	2026-09-25 15:39:15.784452+00	1.0
6495b1ca06bb4ee68ee5b381349c2081	8f3d00ce-4706-4049-88b1-f080bbb33ffc	4862db1a-85f3-49c1-bed2-1def9d383dbe	1.0	1.0	1.0	t	t	2026-09-25 15:39:15.894126+00	1.0
98f6dada81a348019bd16ab14f1f78ae	993df0b6-4bdb-43ea-9e50-715141765180	c46f4c20-58bb-4669-8d5f-1cb18ff0b94a	1.0	1.0	1.0	t	t	2026-09-25 15:39:15.964354+00	1.0
1eaf8db247644de38c3958b992fa3130	993df0b6-4bdb-43ea-9e50-715141765180	b0e01231-2313-441a-9bc8-f12449d3d249	1.0	1.0	1.0	t	t	2026-09-25 15:39:16.02746+00	1.0
fa4d755fb0034b7f8b0d538bf92a90d9	5c20de09-2a06-431d-baf3-ac644f4fec9d	ab799989-4af7-44f5-8fe8-c85147cc9d5d	1.0	1.0	1.0	t	t	2026-09-25 15:39:50.716045+00	1.0
684faa7e40444f328a5275113cc4dc8a	0d9868c5-1b93-4b0c-b8d6-8a97cb21594e	99d0d2b9-2ad9-4e96-bf2f-d0e2d89a7ff5	1.0	1.0	1.0	t	t	2026-09-25 15:39:50.82319+00	1.0
5d4ccf188da647d898adb238745a0eb0	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	16d2ec3e-5c6c-4f5e-ae69-a9a3c058b69e	1.0	1.0	1.0	t	t	2026-09-25 15:39:50.887354+00	1.0
09b067535bde4fff9941237455f57869	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	1.0	1.0	1.0	t	t	2026-09-25 15:39:50.947702+00	1.0
\.


--
-- Data for Name: ad_performance_observations; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.ad_performance_observations (id, organization_id, search_term_id, campaign_id, ad_group_id, impressions, clicks, spend, orders, revenue, ctr, cvr, observed_at, source, created_at) FROM stdin;
00877145-f1c5-4cc9-8033-f87732d81777	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	550c0a76-d1c7-46f5-ac2e-c77706afd705	KW Launch	Dog Leads	1200	45	22.50	3	89.97	0.0375	0.066667	\N	import	2026-09-25 12:47:41.440956+00
b1561dfc-8727-46bd-aa87-1bc3f8f4b0bd	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	34d0090e-fff9-42e3-b0c4-00603c5bb5b9	KW Launch	Dog Leads	340	12	6.00	1	29.99	0.035294	0.083333	\N	import	2026-09-25 12:47:41.456477+00
bc92cc86-e621-40dc-981e-4c7681898c02	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	49247626-9c2e-4d6f-9114-a2fb22fd7bab	KW Launch	Dog Leads	810	33	16.50	2	59.98	0.040741	0.060606	\N	import	2026-09-25 12:47:41.471029+00
a25e30b6-069f-4be8-b492-b3d5b063134c	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	21e21fb5-cd9a-4bc7-bf78-396174fcc065	KW Launch	Chews	95	4	2.00	0	\N	0.042105	\N	\N	import	2026-09-25 12:47:41.485181+00
\.


--
-- Data for Name: approval_decisions; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.approval_decisions (id, approval_request_id, decided_by_user_id, decided_by_role, decision, note, decided_at) FROM stdin;
\.


--
-- Data for Name: approval_requests; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.approval_requests (id, organization_id, requested_by_user_id, capability, safety_class, resource_type, resource_id, change_preview, risk_level, cost_estimate, currency, state, required_approver_role, expires_at, idempotency_key, execution_ref, environment, created_at) FROM stdin;
\.


--
-- Data for Name: audit_events; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.audit_events (id, actor_user_id, actor_role, organization_id, target_organization_id, target_user_id, action, resource_type, resource_id, before_meta, after_meta, environment, view_context, approval_ref, job_run_ref, result, failure_class, occurred_at, correlation_id) FROM stdin;
509e61d7-d0ee-4dfe-8271-75e3b4a85886	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": true, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 12:46:53.524849+00	\N
1741b8b4-59b2-4383-abb1-e01c95b3d30f	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	session.revoke	session	staging-revoke-1	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 12:46:53.678852+00	\N
b07d23ee-ef69-4e49-9f8c-8c448d4068a2	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	preview.start	preview_session	73ffa11e-e1b4-49f4-9286-678ff87055cf	\N	{"reason": "staging smoke", "target_role": null}	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 12:46:53.69063+00	\N
02a0232b-dc62-4877-a4cd-3b87efe35074	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": false, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 12:47:40.908612+00	\N
18f390ba-5ab6-4ef3-a796-c52603a9bebb	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	preview.start	preview_session	c4335540-0bea-41c4-a3b1-29c3ae2c8d2d	\N	{"reason": "staging smoke", "target_role": null}	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 12:47:41.06491+00	\N
7bbcb6a8-9544-4247-a4e1-6a0a14cc4886	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	preview.end	preview_session	c4335540-0bea-41c4-a3b1-29c3ae2c8d2d	\N	\N	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 12:47:41.084263+00	\N
4247fdef-7845-4b3a-8de8-bfd8a8414ea8	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	2d56906f-32ab-438b-a817-f8baef2559f0	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	221d84bc-4761-4991-a5aa-acbe38c1e303	success	\N	2026-09-25 12:47:41.13251+00	\N
43ca1a06-7433-47f5-b0c0-95546a93416a	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	2d56906f-32ab-438b-a817-f8baef2559f0	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 12:47:41.137442+00	\N
18aa9de4-ee85-40a4-be24-6b4ffcb10ae4	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	2d56906f-32ab-438b-a817-f8baef2559f0	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	221d84bc-4761-4991-a5aa-acbe38c1e303	success	\N	2026-09-25 12:47:41.152615+00	\N
edd12928-8516-4cf5-a2a3-3d8b5a287c56	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	2d56906f-32ab-438b-a817-f8baef2559f0	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	221d84bc-4761-4991-a5aa-acbe38c1e303	success	\N	2026-09-25 12:47:41.172251+00	\N
e9e4570c-13e6-43b3-a74e-e6cc225d6839	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	2d56906f-32ab-438b-a817-f8baef2559f0	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	221d84bc-4761-4991-a5aa-acbe38c1e303	success	\N	2026-09-25 12:47:41.19748+00	\N
8ad1f3d3-5d95-43c4-b4c2-413e6c56408a	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	1faed168-4681-4d21-9407-62ac9f955cda	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	e921643e-db91-4827-969e-ed3ef02faf92	success	\N	2026-09-25 12:47:41.229983+00	\N
3547bea8-cee6-4bc8-8569-af4af31015a8	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	1faed168-4681-4d21-9407-62ac9f955cda	\N	{"state": "queued", "job_type": "transient_failure", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 12:47:41.234735+00	\N
3e614159-9654-4ed0-8111-7cad9a5808c3	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	1faed168-4681-4d21-9407-62ac9f955cda	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	e921643e-db91-4827-969e-ed3ef02faf92	success	\N	2026-09-25 12:47:41.249791+00	\N
99ce140d-4abc-4e0e-8ff3-4c925c826f89	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	1faed168-4681-4d21-9407-62ac9f955cda	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	e921643e-db91-4827-969e-ed3ef02faf92	success	\N	2026-09-25 12:47:41.265686+00	\N
6daca6be-4441-4f18-9c86-ab2cf4da4ac2	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.retry_wait	job_request	1faed168-4681-4d21-9407-62ac9f955cda	{"actor": "worker", "state": "running"}	{"state": "retry_wait", "reason": "retryable transient_error", "correlation_id": null}	production	normal	\N	e921643e-db91-4827-969e-ed3ef02faf92	success	\N	2026-09-25 12:47:41.289038+00	\N
a132d13c-c027-41d2-afba-93455fed1cda	818d3840-1a16-40b6-9757-9e5a67af68f8	scheduler	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	1faed168-4681-4d21-9407-62ac9f955cda	{"actor": "scheduler", "state": "retry_wait"}	{"state": "queued", "reason": "backoff elapsed", "correlation_id": null}	production	normal	\N	e921643e-db91-4827-969e-ed3ef02faf92	success	\N	2026-09-25 12:47:41.309557+00	\N
36620faa-dba7-414c-98cd-a96b3087b4dc	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	1faed168-4681-4d21-9407-62ac9f955cda	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	e921643e-db91-4827-969e-ed3ef02faf92	success	\N	2026-09-25 12:47:41.3227+00	\N
38f44dcf-6a31-42b2-9c97-e400f7762959	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	1faed168-4681-4d21-9407-62ac9f955cda	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	e921643e-db91-4827-969e-ed3ef02faf92	success	\N	2026-09-25 12:47:41.337893+00	\N
cdff6b3b-914c-4b89-b429-7e2d32d7039e	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	1faed168-4681-4d21-9407-62ac9f955cda	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	e921643e-db91-4827-969e-ed3ef02faf92	success	\N	2026-09-25 12:47:41.35884+00	\N
c80d3e86-1136-4764-8fc2-70401902fd14	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.create	job_schedule	a25e0083-a2f2-4347-8cc3-297c6b6c3bc7	\N	{"enabled": true, "job_type": "immediate_success"}	production	normal	\N	\N	success	\N	2026-09-25 12:47:41.374052+00	\N
0f6e2670-0e48-413c-b5f6-85697a765e3a	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	bb7b2f11-44e3-44ca-8749-c6a56ee4051d	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T12:47:36.370345+00:00"}	production	normal	\N	870cad35-bcfe-42cc-ad93-accbc0ee6838	success	\N	2026-09-25 12:47:41.398695+00	\N
bce345aa-a5ea-41e9-aa81-76b7bcf37edd	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	bb7b2f11-44e3-44ca-8749-c6a56ee4051d	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 12:47:41.404317+00	\N
a5877f71-8d2f-4550-bdb3-05ba3a419f67	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	a25e0083-a2f2-4347-8cc3-297c6b6c3bc7	\N	{"job_id": "bb7b2f11-44e3-44ca-8749-c6a56ee4051d", "occurrence": "2026-09-25T12:47:36.370345+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 12:47:41.40953+00	\N
ab506eaf-7699-418c-b85a-e086e6a6e059	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	keyword.import	import_batch	7b10eb3c-df22-4bbc-99a9-b6495ee08aed	\N	{"via_job": false, "accepted": 4, "rejected": 1, "report_type": "search_term", "source_file": "search_term_report_sample.csv", "overlap_detected": []}	production	normal	\N	\N	success	\N	2026-09-25 12:47:41.495106+00	\N
59bf488b-c8fe-41f1-91cc-897ccbe7facf	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": false, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 12:48:04.863104+00	\N
00d3eb52-3d01-434b-8c24-28ae3424f30f	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	session.revoke	session	staging-revoke-1790340484999	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 12:48:05.015983+00	\N
094651c5-70d2-47f1-b22f-27d4bb0e6a2b	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	preview.start	preview_session	1f7dd4d2-bdfa-4846-b79e-58a65433425f	\N	{"reason": "staging smoke", "target_role": null}	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 12:48:05.027906+00	\N
c3d0eecf-77f0-49d1-8d2e-9aca12bc161a	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	preview.end	preview_session	1f7dd4d2-bdfa-4846-b79e-58a65433425f	\N	\N	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 12:48:05.04167+00	\N
d3554f3e-85d8-4d94-8278-6f23b6a3fa68	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	3cee773e-9b1c-484f-8538-4bc9d37773d5	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	f1475883-1c5b-4903-aaaf-b5749f2bbbf6	success	\N	2026-09-25 12:48:05.086649+00	\N
311e59d4-c06f-4e82-b82a-11e457329acb	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	3cee773e-9b1c-484f-8538-4bc9d37773d5	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 12:48:05.091418+00	\N
2e235d7e-566d-46d6-9fa5-d48803e5e8b7	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	bb7b2f11-44e3-44ca-8749-c6a56ee4051d	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T12:47:36.370345+00:00"}	production	normal	\N	870cad35-bcfe-42cc-ad93-accbc0ee6838	success	\N	2026-09-25 12:48:05.104536+00	\N
da2fd708-40bb-4421-97e1-b495160ef17a	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	bb7b2f11-44e3-44ca-8749-c6a56ee4051d	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T12:47:36.370345+00:00"}	production	normal	\N	870cad35-bcfe-42cc-ad93-accbc0ee6838	success	\N	2026-09-25 12:48:05.118317+00	\N
5becec8f-51d8-4168-accd-cf6f8e03d142	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	bb7b2f11-44e3-44ca-8749-c6a56ee4051d	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T12:47:36.370345+00:00"}	production	normal	\N	870cad35-bcfe-42cc-ad93-accbc0ee6838	success	\N	2026-09-25 12:48:05.138164+00	\N
218f81e9-2f23-4e52-875d-4fdaac771e2a	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	3cee773e-9b1c-484f-8538-4bc9d37773d5	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	f1475883-1c5b-4903-aaaf-b5749f2bbbf6	success	\N	2026-09-25 12:48:05.152498+00	\N
0310e97c-9205-476d-9cc3-42e31369bfba	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	3cee773e-9b1c-484f-8538-4bc9d37773d5	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	f1475883-1c5b-4903-aaaf-b5749f2bbbf6	success	\N	2026-09-25 12:48:05.167573+00	\N
5525c6c0-5276-4c60-9c81-4a574e04016f	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	3cee773e-9b1c-484f-8538-4bc9d37773d5	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	f1475883-1c5b-4903-aaaf-b5749f2bbbf6	success	\N	2026-09-25 12:48:05.186967+00	\N
af2992ee-82e3-446d-b597-b6d04f0ddc06	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	95d4a73e-2173-489d-ab2c-9857472049de	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	63dcf6f3-2062-4538-80ce-d6b57683b3e8	success	\N	2026-09-25 12:48:05.215924+00	\N
0fbde57f-9767-4c2e-8bdc-e79fbcdf3a03	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	95d4a73e-2173-489d-ab2c-9857472049de	\N	{"state": "queued", "job_type": "transient_failure", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 12:48:05.220381+00	\N
0f19f210-7a57-4ea8-9153-ef0e34698691	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	95d4a73e-2173-489d-ab2c-9857472049de	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	63dcf6f3-2062-4538-80ce-d6b57683b3e8	success	\N	2026-09-25 12:48:05.233989+00	\N
3d46d539-087d-4e43-be98-c12e665689f4	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	95d4a73e-2173-489d-ab2c-9857472049de	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	63dcf6f3-2062-4538-80ce-d6b57683b3e8	success	\N	2026-09-25 12:48:05.249399+00	\N
becb5bd2-019f-452f-a202-4f3a2e89460f	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.misfire	job_schedule	a25e0083-a2f2-4347-8cc3-297c6b6c3bc7	\N	{"policy": "skip", "scheduled_for": "2026-09-25T13:47:36.370345+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 14:11:43.994131+00	\N
1f4deb3e-2dd2-4bab-96ba-da2bab806275	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.retry_wait	job_request	95d4a73e-2173-489d-ab2c-9857472049de	{"actor": "worker", "state": "running"}	{"state": "retry_wait", "reason": "retryable transient_error", "correlation_id": null}	production	normal	\N	63dcf6f3-2062-4538-80ce-d6b57683b3e8	success	\N	2026-09-25 12:48:05.272236+00	\N
efbcf485-813c-4bf3-96cb-e246616c8bb4	818d3840-1a16-40b6-9757-9e5a67af68f8	scheduler	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	95d4a73e-2173-489d-ab2c-9857472049de	{"actor": "scheduler", "state": "retry_wait"}	{"state": "queued", "reason": "backoff elapsed", "correlation_id": null}	production	normal	\N	63dcf6f3-2062-4538-80ce-d6b57683b3e8	success	\N	2026-09-25 12:48:05.291933+00	\N
d93ef76f-79b9-43c8-99af-241cdb2f419d	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	95d4a73e-2173-489d-ab2c-9857472049de	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	63dcf6f3-2062-4538-80ce-d6b57683b3e8	success	\N	2026-09-25 12:48:05.306455+00	\N
7cfed139-0c5e-4c9f-a958-8ca2e4955045	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	95d4a73e-2173-489d-ab2c-9857472049de	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	63dcf6f3-2062-4538-80ce-d6b57683b3e8	success	\N	2026-09-25 12:48:05.321301+00	\N
ed594459-e45f-40e9-84fd-1a455c0f6404	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	95d4a73e-2173-489d-ab2c-9857472049de	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	63dcf6f3-2062-4538-80ce-d6b57683b3e8	success	\N	2026-09-25 12:48:05.338806+00	\N
635955b9-c90f-46b8-99aa-8c509f1e691e	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.create	job_schedule	6415cb76-6249-46ad-9649-30d1025ba72c	\N	{"enabled": true, "job_type": "immediate_success"}	production	normal	\N	\N	success	\N	2026-09-25 12:48:05.352319+00	\N
952828f9-8361-4011-94d3-6cca4f2ee97b	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	a9ee27a7-5545-4d87-a365-1474d10a102b	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T12:48:00.349508+00:00"}	production	normal	\N	85f3b973-6cdd-4c00-8f18-b09d72226c07	success	\N	2026-09-25 12:48:05.373857+00	\N
f37a6a50-31bc-4535-b638-9d6d76375cc1	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	a9ee27a7-5545-4d87-a365-1474d10a102b	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 12:48:05.378054+00	\N
f35de974-ab2e-44af-b046-76c28ba84526	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	6415cb76-6249-46ad-9649-30d1025ba72c	\N	{"job_id": "a9ee27a7-5545-4d87-a365-1474d10a102b", "occurrence": "2026-09-25T12:48:00.349508+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 12:48:05.383035+00	\N
d0b85947-a0e9-4175-8952-2aaad3156026	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": false, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 13:42:39.804212+00	\N
739d173d-c0f3-4d4b-a0ae-2f148ec276b2	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	session.revoke	session	staging-revoke-1790343759932	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 13:42:39.947103+00	\N
26e3b43f-3eb8-4426-a2f4-1a3387918c19	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	preview.start	preview_session	ba86900d-807f-48b4-998f-1ced08a4973d	\N	{"reason": "staging smoke", "target_role": null}	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 13:42:39.959298+00	\N
6e82ca7c-9db5-446d-ab19-9ae631caeceb	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	preview.end	preview_session	ba86900d-807f-48b4-998f-1ced08a4973d	\N	\N	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 13:42:39.973724+00	\N
3f088773-de62-42e6-8672-10be1298c3a8	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	cc39a661-801a-42f2-9ccc-b0ef2f10137e	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	bcb65321-4548-465f-983f-9cd42242069b	success	\N	2026-09-25 13:42:40.024236+00	\N
b0b0c100-3abf-4cce-9671-6460f8b6dc0a	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	cc39a661-801a-42f2-9ccc-b0ef2f10137e	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 13:42:40.028844+00	\N
0ef6aa9c-031c-4f95-aa95-4ab609a8a315	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	a9ee27a7-5545-4d87-a365-1474d10a102b	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T12:48:00.349508+00:00"}	production	normal	\N	85f3b973-6cdd-4c00-8f18-b09d72226c07	success	\N	2026-09-25 13:42:40.043439+00	2026-09-25T12:48:00.349508+00:00
3697c2df-8716-463b-be4f-879a26d94ccb	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	a9ee27a7-5545-4d87-a365-1474d10a102b	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T12:48:00.349508+00:00"}	production	normal	\N	85f3b973-6cdd-4c00-8f18-b09d72226c07	success	\N	2026-09-25 13:42:40.058159+00	2026-09-25T12:48:00.349508+00:00
11672b73-b3ff-4d6a-a4e2-e91ca78588fa	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	a9ee27a7-5545-4d87-a365-1474d10a102b	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T12:48:00.349508+00:00"}	production	normal	\N	85f3b973-6cdd-4c00-8f18-b09d72226c07	success	\N	2026-09-25 13:42:40.082837+00	2026-09-25T12:48:00.349508+00:00
8f9655ac-a867-48bc-a258-01553f8427f2	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	cc39a661-801a-42f2-9ccc-b0ef2f10137e	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	bcb65321-4548-465f-983f-9cd42242069b	success	\N	2026-09-25 13:42:40.097642+00	\N
eb6d1704-4584-49aa-9c34-8bf24e49dbeb	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	cc39a661-801a-42f2-9ccc-b0ef2f10137e	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	bcb65321-4548-465f-983f-9cd42242069b	success	\N	2026-09-25 13:42:40.113468+00	\N
fde7b0b4-629f-42af-abc4-b2ce14a87936	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	cc39a661-801a-42f2-9ccc-b0ef2f10137e	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	bcb65321-4548-465f-983f-9cd42242069b	success	\N	2026-09-25 13:42:40.133052+00	\N
8f30c6d1-01a4-44a8-b05f-8c6c9c4966e5	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	dee8ad4e-8fe6-40e3-885f-d83b287d400d	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	028df412-3cd1-4027-9484-8e2677da0df2	success	\N	2026-09-25 13:42:40.164506+00	\N
7bf64a1c-02db-468b-9b4c-478c4f51485f	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	dee8ad4e-8fe6-40e3-885f-d83b287d400d	\N	{"state": "queued", "job_type": "transient_failure", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 13:42:40.169257+00	\N
fc3709b0-5ac4-4e02-a827-07bd1c9a0daf	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	dee8ad4e-8fe6-40e3-885f-d83b287d400d	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	028df412-3cd1-4027-9484-8e2677da0df2	success	\N	2026-09-25 13:42:40.184199+00	\N
143e1962-a217-474b-9f85-46f96e42b917	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	dee8ad4e-8fe6-40e3-885f-d83b287d400d	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	028df412-3cd1-4027-9484-8e2677da0df2	success	\N	2026-09-25 13:42:40.199322+00	\N
2bb491cb-fa91-4deb-ad80-049303f80474	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.retry_wait	job_request	dee8ad4e-8fe6-40e3-885f-d83b287d400d	{"actor": "worker", "state": "running"}	{"state": "retry_wait", "reason": "retryable transient_error", "correlation_id": null}	production	normal	\N	028df412-3cd1-4027-9484-8e2677da0df2	success	\N	2026-09-25 13:42:40.216238+00	\N
9f8079eb-fd6b-4b60-8792-813162539e74	818d3840-1a16-40b6-9757-9e5a67af68f8	scheduler	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	dee8ad4e-8fe6-40e3-885f-d83b287d400d	{"actor": "scheduler", "state": "retry_wait"}	{"state": "queued", "reason": "backoff elapsed", "correlation_id": null}	production	normal	\N	028df412-3cd1-4027-9484-8e2677da0df2	success	\N	2026-09-25 13:42:40.238197+00	\N
eef15844-711d-47a8-9292-bece232a3437	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	dee8ad4e-8fe6-40e3-885f-d83b287d400d	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	028df412-3cd1-4027-9484-8e2677da0df2	success	\N	2026-09-25 13:42:40.250665+00	\N
107bfd72-dd19-48cc-a371-49f335463858	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	dee8ad4e-8fe6-40e3-885f-d83b287d400d	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	028df412-3cd1-4027-9484-8e2677da0df2	success	\N	2026-09-25 13:42:40.264257+00	\N
dc854957-0a98-4b94-9fcc-428d74b88c1d	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	dee8ad4e-8fe6-40e3-885f-d83b287d400d	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	028df412-3cd1-4027-9484-8e2677da0df2	success	\N	2026-09-25 13:42:40.281563+00	\N
875fec92-bc5e-4708-be0b-ae17ba12202f	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.create	job_schedule	40b37ae5-1596-4a99-8859-76e7c022769f	\N	{"enabled": true, "job_type": "immediate_success"}	production	normal	\N	\N	success	\N	2026-09-25 13:42:40.296732+00	\N
8e863da3-2429-4646-83af-edc6fa9e0561	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	04619a31-fada-4f30-8428-e85428a36d62	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T13:42:35.292807+00:00"}	production	normal	\N	013e1cd7-ca06-4dd8-85be-8475bde12d48	success	\N	2026-09-25 13:42:40.32105+00	2026-09-25T13:42:35.292807+00:00
7f43893d-ecc8-4182-b05a-60016232471c	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	04619a31-fada-4f30-8428-e85428a36d62	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 13:42:40.326362+00	2026-09-25T13:42:35.292807+00:00
88f81d09-f8c1-4e5a-a8a4-ee877e03569c	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	40b37ae5-1596-4a99-8859-76e7c022769f	\N	{"job_id": "04619a31-fada-4f30-8428-e85428a36d62", "occurrence": "2026-09-25T13:42:35.292807+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 13:42:40.331998+00	\N
153fedb6-e99f-4143-be43-d1efa630b11c	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": false, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 13:42:56.949132+00	\N
33c4ecb6-4cc5-40dc-acff-63431932ee1f	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	session.revoke	session	staging-revoke-1790343777083	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 13:42:57.105687+00	\N
fd5755af-7243-4ef9-a932-a6d7b28893d7	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	preview.start	preview_session	633bf211-32a7-4741-b50e-069da58a7b3f	\N	{"reason": "staging smoke", "target_role": null}	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 13:42:57.118539+00	\N
b7e6b4a3-5b2e-451e-86f6-cf7ac46fea7b	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	preview.end	preview_session	633bf211-32a7-4741-b50e-069da58a7b3f	\N	\N	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 13:42:57.132187+00	\N
eb8913b7-768f-4554-a2c4-f1cd5d413215	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	cfaf79d9-8e96-4764-a652-19f2f2179004	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	94137786-91d3-4086-8634-5da9968bd6c7	success	\N	2026-09-25 13:42:57.172621+00	\N
3acf3041-5991-425a-ab18-0aa53191a9c6	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	cfaf79d9-8e96-4764-a652-19f2f2179004	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 13:42:57.177268+00	\N
9c3c2c8e-bceb-4114-8309-0ef8bd6ccdc6	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	ece8ac3a-1061-486c-a849-7574c872926d	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "staging-req-chain-1"}	production	normal	\N	189021bf-e92f-456e-933d-577fb90e6ae2	success	\N	2026-09-25 13:42:57.563452+00	staging-req-chain-1
509b3717-8713-4757-a438-7d55d3bdc6fa	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	04619a31-fada-4f30-8428-e85428a36d62	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T13:42:35.292807+00:00"}	production	normal	\N	013e1cd7-ca06-4dd8-85be-8475bde12d48	success	\N	2026-09-25 13:42:57.190857+00	2026-09-25T13:42:35.292807+00:00
c79a8a27-f1f0-4a1f-a3f1-ea28a5303e30	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	04619a31-fada-4f30-8428-e85428a36d62	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T13:42:35.292807+00:00"}	production	normal	\N	013e1cd7-ca06-4dd8-85be-8475bde12d48	success	\N	2026-09-25 13:42:57.20561+00	2026-09-25T13:42:35.292807+00:00
ebed6c91-4496-448e-81ea-fa0a74b6037d	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	04619a31-fada-4f30-8428-e85428a36d62	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T13:42:35.292807+00:00"}	production	normal	\N	013e1cd7-ca06-4dd8-85be-8475bde12d48	success	\N	2026-09-25 13:42:57.224309+00	2026-09-25T13:42:35.292807+00:00
d30ee745-d657-46ba-b183-7428bccf928d	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	cfaf79d9-8e96-4764-a652-19f2f2179004	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	94137786-91d3-4086-8634-5da9968bd6c7	success	\N	2026-09-25 13:42:57.238256+00	\N
0c3667fa-ca8f-4ea1-a3f6-a564bfbacb07	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	cfaf79d9-8e96-4764-a652-19f2f2179004	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	94137786-91d3-4086-8634-5da9968bd6c7	success	\N	2026-09-25 13:42:57.253114+00	\N
64e6b135-dce2-498b-947a-91935c3b1866	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	cfaf79d9-8e96-4764-a652-19f2f2179004	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	94137786-91d3-4086-8634-5da9968bd6c7	success	\N	2026-09-25 13:42:57.272105+00	\N
68dd6758-f5a9-42b4-9603-f44dc967163c	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	7a353e29-dc66-4086-9aa8-64174efe554d	success	\N	2026-09-25 13:42:57.302108+00	\N
41864798-4a7f-4b68-92c8-b8ffec79e846	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	\N	{"state": "queued", "job_type": "transient_failure", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 13:42:57.306711+00	\N
f296de71-a9fd-498e-8626-a8663ce3eced	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	7a353e29-dc66-4086-9aa8-64174efe554d	success	\N	2026-09-25 13:42:57.319626+00	\N
73f546d8-5dc9-4012-97fa-42d2964bd766	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	7a353e29-dc66-4086-9aa8-64174efe554d	success	\N	2026-09-25 13:42:57.334125+00	\N
bd8cdfe1-dd0f-47d7-a1fc-d28ec083d53e	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.retry_wait	job_request	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	{"actor": "worker", "state": "running"}	{"state": "retry_wait", "reason": "retryable transient_error", "correlation_id": null}	production	normal	\N	7a353e29-dc66-4086-9aa8-64174efe554d	success	\N	2026-09-25 13:42:57.35095+00	\N
2a1f6838-214b-421b-a409-6f60435e6fc2	818d3840-1a16-40b6-9757-9e5a67af68f8	scheduler	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	{"actor": "scheduler", "state": "retry_wait"}	{"state": "queued", "reason": "backoff elapsed", "correlation_id": null}	production	normal	\N	7a353e29-dc66-4086-9aa8-64174efe554d	success	\N	2026-09-25 13:42:57.370621+00	\N
9abc7ad1-6617-4e7a-a609-3de11e82e419	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	7a353e29-dc66-4086-9aa8-64174efe554d	success	\N	2026-09-25 13:42:57.382904+00	\N
9b201cd6-6d15-474e-9d29-883375c8a881	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	7a353e29-dc66-4086-9aa8-64174efe554d	success	\N	2026-09-25 13:42:57.397147+00	\N
0ca8227e-740c-46e7-82a3-e2780fb669c8	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	7a353e29-dc66-4086-9aa8-64174efe554d	success	\N	2026-09-25 13:42:57.415715+00	\N
1a66ff32-2c7f-49f8-9657-0d437888ae18	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.create	job_schedule	eb43ac8b-9092-41cd-916e-7029f677874d	\N	{"enabled": true, "job_type": "immediate_success"}	production	normal	\N	\N	success	\N	2026-09-25 13:42:57.43058+00	\N
f3e6c5f6-9afb-442f-ba5e-4537db50f62a	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	74e79cff-759d-4806-b22c-c13f230ff015	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T13:42:52.427134+00:00"}	production	normal	\N	891c1282-c650-4b2f-9b9c-4e4bec3eb150	success	\N	2026-09-25 13:42:57.452803+00	2026-09-25T13:42:52.427134+00:00
2c302d47-5b31-4bc5-9dc0-f3bad067ac54	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	74e79cff-759d-4806-b22c-c13f230ff015	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 13:42:57.457235+00	2026-09-25T13:42:52.427134+00:00
fe7ed902-f72b-4a57-ab90-ae895a52ef78	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	eb43ac8b-9092-41cd-916e-7029f677874d	\N	{"job_id": "74e79cff-759d-4806-b22c-c13f230ff015", "occurrence": "2026-09-25T13:42:52.427134+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 13:42:57.462994+00	\N
87979a99-ef38-43f4-8b2d-89f88922301a	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	ece8ac3a-1061-486c-a849-7574c872926d	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 13:42:57.567905+00	staging-req-chain-1
f2fddf15-3c4e-414e-b335-52c424fac30a	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	74e79cff-759d-4806-b22c-c13f230ff015	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T13:42:52.427134+00:00"}	production	normal	\N	891c1282-c650-4b2f-9b9c-4e4bec3eb150	success	\N	2026-09-25 13:42:57.579244+00	2026-09-25T13:42:52.427134+00:00
efde55b3-c579-4ff9-a22d-26e4548927e1	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	74e79cff-759d-4806-b22c-c13f230ff015	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T13:42:52.427134+00:00"}	production	normal	\N	891c1282-c650-4b2f-9b9c-4e4bec3eb150	success	\N	2026-09-25 13:42:57.593599+00	2026-09-25T13:42:52.427134+00:00
eb9084ed-0c95-40cb-972c-5099fad07579	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	74e79cff-759d-4806-b22c-c13f230ff015	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T13:42:52.427134+00:00"}	production	normal	\N	891c1282-c650-4b2f-9b9c-4e4bec3eb150	success	\N	2026-09-25 13:42:57.612731+00	2026-09-25T13:42:52.427134+00:00
d222023d-567f-4180-8d30-cd4bdadfdd17	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	ece8ac3a-1061-486c-a849-7574c872926d	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "staging-req-chain-1"}	production	normal	\N	189021bf-e92f-456e-933d-577fb90e6ae2	success	\N	2026-09-25 13:42:57.627375+00	staging-req-chain-1
247e37ed-0145-434f-911e-3a8f5c5a55bb	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	ece8ac3a-1061-486c-a849-7574c872926d	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "staging-req-chain-1"}	production	normal	\N	189021bf-e92f-456e-933d-577fb90e6ae2	success	\N	2026-09-25 13:42:57.643119+00	staging-req-chain-1
1af5550d-0ee9-4f5f-b712-41f9a8ac1465	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	ece8ac3a-1061-486c-a849-7574c872926d	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "staging-req-chain-1"}	production	normal	\N	189021bf-e92f-456e-933d-577fb90e6ae2	success	\N	2026-09-25 13:42:57.663199+00	staging-req-chain-1
c8763225-9b4d-4e54-93ab-a4dec64e8d84	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": false, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 13:43:27.732538+00	\N
8085c5db-e084-4843-a937-b27a07b11194	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	session.revoke	session	staging-revoke-1790343807854	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 13:43:27.87391+00	\N
6055dc0d-6c64-441a-b398-76d2f988f2c8	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	preview.start	preview_session	848d8517-6ce9-4f2e-915c-845739356e16	\N	{"reason": "staging smoke", "target_role": null}	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 13:43:27.886364+00	\N
fbfc2676-f7d1-4032-a500-a2fa3a522c2f	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	preview.end	preview_session	848d8517-6ce9-4f2e-915c-845739356e16	\N	\N	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 13:43:27.902986+00	\N
964915b9-75a4-4a60-9229-3889c8fcafcb	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	6ce89210-9d7b-4ef2-a460-7936e37861e9	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	2ed07a3f-a742-484d-9f51-295bf3c16c52	success	\N	2026-09-25 13:43:27.939827+00	\N
fa1c4474-3d26-4d50-9dca-0859221b0eee	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	6ce89210-9d7b-4ef2-a460-7936e37861e9	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 13:43:27.944164+00	\N
7da5166b-0a2a-4280-9392-6e2324f54fe5	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	6ce89210-9d7b-4ef2-a460-7936e37861e9	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	2ed07a3f-a742-484d-9f51-295bf3c16c52	success	\N	2026-09-25 13:43:27.957951+00	\N
2e6f53ce-2715-47fa-8d26-90afb48f6c1f	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	6ce89210-9d7b-4ef2-a460-7936e37861e9	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	2ed07a3f-a742-484d-9f51-295bf3c16c52	success	\N	2026-09-25 13:43:27.972717+00	\N
073a2299-91ef-47fe-9041-02393d719f0d	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	6ce89210-9d7b-4ef2-a460-7936e37861e9	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	2ed07a3f-a742-484d-9f51-295bf3c16c52	success	\N	2026-09-25 13:43:27.990857+00	\N
7840faed-fb44-4dfc-89d1-69c124051363	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	dde1681c-6f4e-4219-97c2-06d1154c7067	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	6f656618-35bd-4f97-952b-1a5c832d1f8b	success	\N	2026-09-25 13:43:28.026975+00	\N
56f15444-eee5-4fa5-a405-723acc24a725	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	dde1681c-6f4e-4219-97c2-06d1154c7067	\N	{"state": "queued", "job_type": "transient_failure", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 13:43:28.032759+00	\N
9d1e1627-a098-42d3-b6bd-ff9d1bdef395	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	dde1681c-6f4e-4219-97c2-06d1154c7067	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	6f656618-35bd-4f97-952b-1a5c832d1f8b	success	\N	2026-09-25 13:43:28.046759+00	\N
bd2dbff1-1f91-4de7-ad62-77a6ec3276de	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	dde1681c-6f4e-4219-97c2-06d1154c7067	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	6f656618-35bd-4f97-952b-1a5c832d1f8b	success	\N	2026-09-25 13:43:28.062012+00	\N
329da63f-babc-441e-8194-ed4bd2675a15	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.retry_wait	job_request	dde1681c-6f4e-4219-97c2-06d1154c7067	{"actor": "worker", "state": "running"}	{"state": "retry_wait", "reason": "retryable transient_error", "correlation_id": null}	production	normal	\N	6f656618-35bd-4f97-952b-1a5c832d1f8b	success	\N	2026-09-25 13:43:28.087976+00	\N
93b95f2e-62ab-4a24-810d-ce45993116a0	818d3840-1a16-40b6-9757-9e5a67af68f8	scheduler	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	dde1681c-6f4e-4219-97c2-06d1154c7067	{"actor": "scheduler", "state": "retry_wait"}	{"state": "queued", "reason": "backoff elapsed", "correlation_id": null}	production	normal	\N	6f656618-35bd-4f97-952b-1a5c832d1f8b	success	\N	2026-09-25 13:43:28.122484+00	\N
aacefea9-9579-4124-8f7d-905d5e3637e5	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	dde1681c-6f4e-4219-97c2-06d1154c7067	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	6f656618-35bd-4f97-952b-1a5c832d1f8b	success	\N	2026-09-25 13:43:28.147437+00	\N
98db70af-d307-41cf-80ee-1e3f2bde9bd8	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	dde1681c-6f4e-4219-97c2-06d1154c7067	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	6f656618-35bd-4f97-952b-1a5c832d1f8b	success	\N	2026-09-25 13:43:28.165954+00	\N
24af19ef-c439-4232-a7a4-397cdd4a6d57	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	dde1681c-6f4e-4219-97c2-06d1154c7067	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	6f656618-35bd-4f97-952b-1a5c832d1f8b	success	\N	2026-09-25 13:43:28.185729+00	\N
9f63e3a6-4766-4a0b-9fdc-1f4503473142	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.create	job_schedule	6c5ed8fa-7912-4a20-8cc0-952cd2522db7	\N	{"enabled": true, "job_type": "immediate_success"}	production	normal	\N	\N	success	\N	2026-09-25 13:43:28.203781+00	\N
4f09e674-1209-4733-97fc-9646e6723eec	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	947d35bd-7f5e-4967-800c-e78b630cd423	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T13:43:23.199997+00:00"}	production	normal	\N	c235be5f-e80d-4af6-983a-76c3d2a8df68	success	\N	2026-09-25 13:43:28.231917+00	2026-09-25T13:43:23.199997+00:00
021d8611-1fef-4dec-9def-e7300af44acc	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	947d35bd-7f5e-4967-800c-e78b630cd423	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 13:43:28.237728+00	2026-09-25T13:43:23.199997+00:00
0cb7a684-0b56-43d4-b2a8-66c2d3c049ae	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	6c5ed8fa-7912-4a20-8cc0-952cd2522db7	\N	{"job_id": "947d35bd-7f5e-4967-800c-e78b630cd423", "occurrence": "2026-09-25T13:43:23.199997+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 13:43:28.243713+00	\N
1ec1a319-d980-44e3-98bf-290f763339f9	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	ece8ac3a-1061-486c-a849-7574c872926d	\N	{"job_type": "immediate_success", "idempotent_replay": true}	production	normal	\N	\N	success	\N	2026-09-25 13:43:28.320889+00	staging-req-chain-1
7306581d-fee6-4bc7-8e1f-d06eafa92bf4	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	947d35bd-7f5e-4967-800c-e78b630cd423	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T13:43:23.199997+00:00"}	production	normal	\N	c235be5f-e80d-4af6-983a-76c3d2a8df68	success	\N	2026-09-25 13:43:28.333422+00	2026-09-25T13:43:23.199997+00:00
6b2fd8d3-891b-452b-9948-5ddbca895186	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	947d35bd-7f5e-4967-800c-e78b630cd423	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T13:43:23.199997+00:00"}	production	normal	\N	c235be5f-e80d-4af6-983a-76c3d2a8df68	success	\N	2026-09-25 13:43:28.348443+00	2026-09-25T13:43:23.199997+00:00
78c8699f-5ca7-4bde-9a5b-b0f85fea4ca4	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	947d35bd-7f5e-4967-800c-e78b630cd423	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T13:43:23.199997+00:00"}	production	normal	\N	c235be5f-e80d-4af6-983a-76c3d2a8df68	success	\N	2026-09-25 13:43:28.367773+00	2026-09-25T13:43:23.199997+00:00
7214b679-8154-4797-a98b-62aa2841efc0	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": false, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 13:43:43.807853+00	\N
b2efe8b2-8069-4f0e-8abd-0605138d2db6	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	session.revoke	session	staging-revoke-1790343823940	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 13:43:43.954941+00	\N
4296279a-1ddc-48f5-a6e9-bd0bd04a3cef	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	preview.start	preview_session	cd7eb473-9fb7-4bb9-9c2e-acdd644e8232	\N	{"reason": "staging smoke", "target_role": null}	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 13:43:43.967963+00	\N
1eb4aebd-7f93-4692-a4cc-f17b32748d44	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	preview.end	preview_session	cd7eb473-9fb7-4bb9-9c2e-acdd644e8232	\N	\N	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 13:43:43.981327+00	\N
c1aea68c-8364-4b82-84c2-6a71976cb163	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	40a0cbf9-f619-4bb5-a7eb-5cd23cf9dee1	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	8060967c-9d03-475f-a8ba-ecd05f59fa15	success	\N	2026-09-25 13:43:44.053452+00	\N
13225f80-c8e5-482b-898b-14d8ecce529c	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	40a0cbf9-f619-4bb5-a7eb-5cd23cf9dee1	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 13:43:44.059062+00	\N
ee9ee080-18d2-4067-8d4f-3e2daa74bc2b	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	40a0cbf9-f619-4bb5-a7eb-5cd23cf9dee1	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	8060967c-9d03-475f-a8ba-ecd05f59fa15	success	\N	2026-09-25 13:43:44.073663+00	\N
348e0bbe-6f2d-4c0b-a12b-d82dca8cc509	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	40a0cbf9-f619-4bb5-a7eb-5cd23cf9dee1	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	8060967c-9d03-475f-a8ba-ecd05f59fa15	success	\N	2026-09-25 13:43:44.08902+00	\N
2b405508-6ff3-4ca1-a50b-f058f0db138a	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	40a0cbf9-f619-4bb5-a7eb-5cd23cf9dee1	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	8060967c-9d03-475f-a8ba-ecd05f59fa15	success	\N	2026-09-25 13:43:44.109531+00	\N
f9f9bb79-b8a9-4b6f-859b-93a52cf1bf78	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	ecf21bd2-46ad-402b-9329-8c5cae2291e9	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	success	\N	2026-09-25 13:43:44.141438+00	\N
13375d6a-9dcc-463d-8d54-6dd14d7824cd	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	ecf21bd2-46ad-402b-9329-8c5cae2291e9	\N	{"state": "queued", "job_type": "transient_failure", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 13:43:44.146232+00	\N
03ae59fb-126c-4976-a840-2a014e661230	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	ecf21bd2-46ad-402b-9329-8c5cae2291e9	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	success	\N	2026-09-25 13:43:44.159852+00	\N
dbbece5d-c3b3-48bb-84e9-d56c6a882745	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	ecf21bd2-46ad-402b-9329-8c5cae2291e9	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	success	\N	2026-09-25 13:43:44.174254+00	\N
c4af66b0-9dab-4f71-b8cf-9309f13e21a0	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.retry_wait	job_request	ecf21bd2-46ad-402b-9329-8c5cae2291e9	{"actor": "worker", "state": "running"}	{"state": "retry_wait", "reason": "retryable transient_error", "correlation_id": null}	production	normal	\N	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	success	\N	2026-09-25 13:43:44.191804+00	\N
ffce3f19-32d8-49d9-85f3-08a47782681a	818d3840-1a16-40b6-9757-9e5a67af68f8	scheduler	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	ecf21bd2-46ad-402b-9329-8c5cae2291e9	{"actor": "scheduler", "state": "retry_wait"}	{"state": "queued", "reason": "backoff elapsed", "correlation_id": null}	production	normal	\N	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	success	\N	2026-09-25 13:43:44.213154+00	\N
6353c145-f350-432a-9cfa-6d403d6bfe39	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	ecf21bd2-46ad-402b-9329-8c5cae2291e9	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	success	\N	2026-09-25 13:43:44.225923+00	\N
aa878488-7f3f-4c9e-bebf-0a0e76c1b8bf	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	ecf21bd2-46ad-402b-9329-8c5cae2291e9	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	success	\N	2026-09-25 13:43:44.241743+00	\N
abf9a387-055b-43d1-b4bb-d8982c021ae7	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	ecf21bd2-46ad-402b-9329-8c5cae2291e9	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	success	\N	2026-09-25 13:43:44.260832+00	\N
271101d7-f142-427d-bb31-0ca40c411e7e	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.create	job_schedule	8615ca91-de1c-49ea-85ea-74bede8ae9b8	\N	{"enabled": true, "job_type": "immediate_success"}	production	normal	\N	\N	success	\N	2026-09-25 13:43:44.278655+00	\N
cbeff72c-e6bf-4c8a-a8a4-e89c92fa61d8	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	c9ed2300-a06c-420f-b8fa-b45f0bd28d6b	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T13:43:39.275532+00:00"}	production	normal	\N	980f46bb-1cda-4078-bb7f-a3d73c7b40d8	success	\N	2026-09-25 13:43:44.302057+00	2026-09-25T13:43:39.275532+00:00
cad1b186-0aab-4261-bba1-6b531252f90c	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	c9ed2300-a06c-420f-b8fa-b45f0bd28d6b	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 13:43:44.306621+00	2026-09-25T13:43:39.275532+00:00
7d094dc6-0586-4ec2-b085-1eb03e18c2d9	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	8615ca91-de1c-49ea-85ea-74bede8ae9b8	\N	{"job_id": "c9ed2300-a06c-420f-b8fa-b45f0bd28d6b", "occurrence": "2026-09-25T13:43:39.275532+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 13:43:44.311977+00	\N
c1a1dbd3-a7c9-4ed5-ae03-04ab6376da4f	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	ece8ac3a-1061-486c-a849-7574c872926d	\N	{"job_type": "immediate_success", "idempotent_replay": true}	production	normal	\N	\N	success	\N	2026-09-25 13:43:44.386185+00	staging-req-chain-1
497c43fd-135a-4e4b-ac0c-4baa5a5eb94f	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	c9ed2300-a06c-420f-b8fa-b45f0bd28d6b	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T13:43:39.275532+00:00"}	production	normal	\N	980f46bb-1cda-4078-bb7f-a3d73c7b40d8	success	\N	2026-09-25 13:43:44.401744+00	2026-09-25T13:43:39.275532+00:00
1ee6064e-5196-439c-add4-c72a02f40ebb	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	c9ed2300-a06c-420f-b8fa-b45f0bd28d6b	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T13:43:39.275532+00:00"}	production	normal	\N	980f46bb-1cda-4078-bb7f-a3d73c7b40d8	success	\N	2026-09-25 13:43:44.415126+00	2026-09-25T13:43:39.275532+00:00
bf71b19e-4114-426b-b290-7e6d282c3976	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	c9ed2300-a06c-420f-b8fa-b45f0bd28d6b	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T13:43:39.275532+00:00"}	production	normal	\N	980f46bb-1cda-4078-bb7f-a3d73c7b40d8	success	\N	2026-09-25 13:43:44.433753+00	2026-09-25T13:43:39.275532+00:00
2ce2c085-4195-40f5-8d14-16e11e728867	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": false, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 14:11:43.553871+00	\N
45817f44-639a-46dc-8a68-8a32b862078b	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 401}	production	normal	\N	\N	denied	\N	2026-09-25 14:11:43.6521+00	\N
571c9496-11d8-4c64-ad27-6bae095b5e5a	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 14:11:43.671815+00	\N
f4c23f14-0b15-4284-822a-e6fe676385a0	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	session.revoke	session	staging-revoke-1790345503675	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 14:11:43.691375+00	\N
305d7b27-1cdb-412d-82bc-ad828c82fa6f	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 401}	production	normal	\N	\N	denied	\N	2026-09-25 14:11:43.698768+00	\N
0af884ec-1f17-4045-ab52-b155ce90043f	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	preview.start	preview_session	1c675d9f-e454-46b3-85c7-c19e029e8857	\N	{"reason": "staging smoke", "target_role": null}	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 14:11:43.709418+00	\N
bad326f7-c0f4-41f5-a2d9-f4657b9ddf81	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	preview.end	preview_session	1c675d9f-e454-46b3-85c7-c19e029e8857	\N	\N	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 14:11:43.725626+00	\N
021e232c-772c-4335-8b75-57f59ea42bfe	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	de0a429b-9bcf-4d1d-9198-e1727b230d19	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	73e7f174-54ac-4d37-9f65-33c1608a6c2b	success	\N	2026-09-25 14:11:43.774683+00	\N
2ce2c804-1d82-4d59-bc18-a513099f6eec	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	de0a429b-9bcf-4d1d-9198-e1727b230d19	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 14:11:43.77899+00	\N
5208c384-d23f-473a-b7cc-1ff33883a170	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	de0a429b-9bcf-4d1d-9198-e1727b230d19	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	73e7f174-54ac-4d37-9f65-33c1608a6c2b	success	\N	2026-09-25 14:11:43.794636+00	\N
3ed000b5-7780-42e0-9015-7455c7ee75a3	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	de0a429b-9bcf-4d1d-9198-e1727b230d19	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	73e7f174-54ac-4d37-9f65-33c1608a6c2b	success	\N	2026-09-25 14:11:43.809958+00	\N
08e83a4e-c52a-4414-b655-ace8f45f6506	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	de0a429b-9bcf-4d1d-9198-e1727b230d19	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	73e7f174-54ac-4d37-9f65-33c1608a6c2b	success	\N	2026-09-25 14:11:43.829268+00	\N
fce94794-0b4d-4967-8ff9-9bb95a48a00c	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	d942173e-b6cf-4f51-a3d3-996f6f083813	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	888e1f7b-6639-4463-b86f-c32ff1af4cc3	success	\N	2026-09-25 14:11:43.857752+00	\N
eae19801-c444-4ff9-8d28-97b18e5290c2	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	d942173e-b6cf-4f51-a3d3-996f6f083813	\N	{"state": "queued", "job_type": "transient_failure", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 14:11:43.861948+00	\N
f58cd622-8cc6-479c-8770-3db80935b7a1	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	d942173e-b6cf-4f51-a3d3-996f6f083813	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	888e1f7b-6639-4463-b86f-c32ff1af4cc3	success	\N	2026-09-25 14:11:43.875059+00	\N
77fdcd3f-95a2-4bd2-b0e7-fdd6c0089e68	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	d942173e-b6cf-4f51-a3d3-996f6f083813	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	888e1f7b-6639-4463-b86f-c32ff1af4cc3	success	\N	2026-09-25 14:11:43.889396+00	\N
5e9a16e8-e535-4091-8d80-f5d9c4f59519	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.retry_wait	job_request	d942173e-b6cf-4f51-a3d3-996f6f083813	{"actor": "worker", "state": "running"}	{"state": "retry_wait", "reason": "retryable transient_error", "correlation_id": null}	production	normal	\N	888e1f7b-6639-4463-b86f-c32ff1af4cc3	success	\N	2026-09-25 14:11:43.907015+00	\N
76662b07-1009-4c8c-bca4-ebc2c4ea4932	818d3840-1a16-40b6-9757-9e5a67af68f8	scheduler	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	d942173e-b6cf-4f51-a3d3-996f6f083813	{"actor": "scheduler", "state": "retry_wait"}	{"state": "queued", "reason": "backoff elapsed", "correlation_id": null}	production	normal	\N	888e1f7b-6639-4463-b86f-c32ff1af4cc3	success	\N	2026-09-25 14:11:43.927117+00	\N
33022903-9f20-413a-8908-8a81947b62c6	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	d942173e-b6cf-4f51-a3d3-996f6f083813	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	888e1f7b-6639-4463-b86f-c32ff1af4cc3	success	\N	2026-09-25 14:11:43.939101+00	\N
94bf3ef9-13d2-47a2-a8f1-e768ee37f472	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	d942173e-b6cf-4f51-a3d3-996f6f083813	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	888e1f7b-6639-4463-b86f-c32ff1af4cc3	success	\N	2026-09-25 14:11:43.95311+00	\N
b21168e3-6efa-43c7-a364-1e6a6b0299ba	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	d942173e-b6cf-4f51-a3d3-996f6f083813	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	888e1f7b-6639-4463-b86f-c32ff1af4cc3	success	\N	2026-09-25 14:11:43.970687+00	\N
2d64d649-126a-4c47-b6a1-94ebde5d4577	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.create	job_schedule	9e1827ad-dcba-457c-bc05-5168a0f220c8	\N	{"enabled": true, "job_type": "immediate_success"}	production	normal	\N	\N	success	\N	2026-09-25 14:11:43.985487+00	\N
5e72569a-6122-4f4f-9b1a-55cf59293ac6	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.misfire	job_schedule	6415cb76-6249-46ad-9649-30d1025ba72c	\N	{"policy": "skip", "scheduled_for": "2026-09-25T13:48:00.349508+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 14:11:44.003359+00	\N
2b443e6b-c3ef-4db6-ba79-7d274e16f5fb	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	a9c8bbb2-aded-4aaa-abaa-3ff70acbee4f	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T14:11:38.982073+00:00"}	production	normal	\N	b7142c7b-501f-4b67-a1af-6bd40e5de64c	success	\N	2026-09-25 14:11:44.025956+00	2026-09-25T14:11:38.982073+00:00
73af0723-c806-40f9-b8a4-c0e27c94a63b	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	a9c8bbb2-aded-4aaa-abaa-3ff70acbee4f	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 14:11:44.030269+00	2026-09-25T14:11:38.982073+00:00
172ec47f-fadc-4db2-9767-79b539f4dbbf	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	9e1827ad-dcba-457c-bc05-5168a0f220c8	\N	{"job_id": "a9c8bbb2-aded-4aaa-abaa-3ff70acbee4f", "occurrence": "2026-09-25T14:11:38.982073+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 14:11:44.035483+00	\N
c3d358c5-c7fa-4601-915e-e0275578e44b	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	ece8ac3a-1061-486c-a849-7574c872926d	\N	{"job_type": "immediate_success", "idempotent_replay": true}	production	normal	\N	\N	success	\N	2026-09-25 14:11:44.116648+00	staging-req-chain-1
e4f8cd62-c5cc-425c-9214-06693bea1c4e	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	a9c8bbb2-aded-4aaa-abaa-3ff70acbee4f	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T14:11:38.982073+00:00"}	production	normal	\N	b7142c7b-501f-4b67-a1af-6bd40e5de64c	success	\N	2026-09-25 14:11:44.128708+00	2026-09-25T14:11:38.982073+00:00
e43651b1-b1bd-40d0-9951-df0c469e2d41	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	a9c8bbb2-aded-4aaa-abaa-3ff70acbee4f	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T14:11:38.982073+00:00"}	production	normal	\N	b7142c7b-501f-4b67-a1af-6bd40e5de64c	success	\N	2026-09-25 14:11:44.144321+00	2026-09-25T14:11:38.982073+00:00
f2d77204-ef99-4902-89c4-6cb85958de8d	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	a9c8bbb2-aded-4aaa-abaa-3ff70acbee4f	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T14:11:38.982073+00:00"}	production	normal	\N	b7142c7b-501f-4b67-a1af-6bd40e5de64c	success	\N	2026-09-25 14:11:44.166382+00	2026-09-25T14:11:38.982073+00:00
79cd5c40-e488-47f6-8379-d66d70a4eb9f	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	2de868d1-6a42-4874-b6c4-08a6f521ee4e	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	18511b1c-101e-43aa-9811-2a3f0cac75e9	success	\N	2026-09-25 14:11:44.219101+00	\N
42cbb15e-1992-495e-ab9b-74da61d1a96e	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	2de868d1-6a42-4874-b6c4-08a6f521ee4e	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 14:11:44.223711+00	\N
7b7d3a11-48ab-4ada-bdf5-1e3932ffa6d3	7013f362-8338-48a2-a3f0-0b65d6216a2c	viewer	cd933802-95dc-4ce6-a8b7-15b1879ba1cc	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/usage/summary", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 14:11:44.241205+00	\N
e89d25f6-15bd-414e-a585-151e9b0eccdf	7013f362-8338-48a2-a3f0-0b65d6216a2c	viewer	cd933802-95dc-4ce6-a8b7-15b1879ba1cc	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/providers", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 14:11:44.247972+00	\N
00c59687-1c58-4d7b-8ea6-943fb75b8711	7013f362-8338-48a2-a3f0-0b65d6216a2c	viewer	cd933802-95dc-4ce6-a8b7-15b1879ba1cc	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable", "method": "POST", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 14:11:44.255882+00	\N
9e631037-6bc2-4585-b6f7-50c3d5634097	7013f362-8338-48a2-a3f0-0b65d6216a2c	viewer	cd933802-95dc-4ce6-a8b7-15b1879ba1cc	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable/d942173e-b6cf-4f51-a3d3-996f6f083813", "method": "GET", "status": 404}	production	normal	\N	\N	denied	\N	2026-09-25 14:11:44.263967+00	\N
ace663ad-da62-45c7-ae2c-8aaf3c57776d	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": false, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 14:51:11.438747+00	\N
c3ea122d-7694-44fa-bfe0-403fb4da0f2e	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 401}	production	normal	\N	\N	denied	\N	2026-09-25 14:51:11.617184+00	\N
7d5842f8-f079-4ec5-ab63-fcb85184539c	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 14:51:11.636543+00	\N
e6fe7c88-dd4c-49ab-a542-6558f3088871	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	session.revoke	session	staging-revoke-1790347871640	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 14:51:11.655142+00	\N
817dc72d-2821-4d1c-98c2-41c077650bb8	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 401}	production	normal	\N	\N	denied	\N	2026-09-25 14:51:11.66049+00	\N
50046854-b7c5-443d-beda-a37ae43d5e04	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	preview.start	preview_session	6310af0e-cd5d-4130-9cb1-f5f8831533e2	\N	{"reason": "staging smoke", "target_role": null}	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 14:51:11.673832+00	\N
5b3de1fd-a7cd-43f2-ae5b-c3d448b4dfb7	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	preview.end	preview_session	6310af0e-cd5d-4130-9cb1-f5f8831533e2	\N	\N	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 14:51:11.690216+00	\N
e4c645ec-a923-40e9-8bb6-54e0e0c6a98f	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	a83672ad-6e70-4814-bd20-a28b34c34421	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	c6c4e85b-c433-4539-8baf-0b39ca813496	success	\N	2026-09-25 14:51:11.737556+00	\N
70b3e35a-48cf-4d83-89c9-cfbc514f18f3	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	a83672ad-6e70-4814-bd20-a28b34c34421	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 14:51:11.742425+00	\N
f7b1fa0e-ac31-4338-8c31-7207da5a21a9	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	2de868d1-6a42-4874-b6c4-08a6f521ee4e	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	18511b1c-101e-43aa-9811-2a3f0cac75e9	success	\N	2026-09-25 14:51:11.755312+00	\N
a2b60184-980e-4dee-8cda-a288c084f459	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	2de868d1-6a42-4874-b6c4-08a6f521ee4e	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	18511b1c-101e-43aa-9811-2a3f0cac75e9	success	\N	2026-09-25 14:51:11.771089+00	\N
cdb5bbd7-0bb3-4fb9-93e6-221d77423592	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	2de868d1-6a42-4874-b6c4-08a6f521ee4e	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	18511b1c-101e-43aa-9811-2a3f0cac75e9	success	\N	2026-09-25 14:51:11.791501+00	\N
bbd084e3-55bb-466b-9011-5cb5fef628b4	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	a83672ad-6e70-4814-bd20-a28b34c34421	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	c6c4e85b-c433-4539-8baf-0b39ca813496	success	\N	2026-09-25 14:51:11.805933+00	\N
294d5e68-b4bc-4fa6-b11c-9c7de9759555	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	a83672ad-6e70-4814-bd20-a28b34c34421	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	c6c4e85b-c433-4539-8baf-0b39ca813496	success	\N	2026-09-25 14:51:11.828337+00	\N
ca86f2a4-0b2f-40c9-b4f5-ac7f01294291	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	a83672ad-6e70-4814-bd20-a28b34c34421	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	c6c4e85b-c433-4539-8baf-0b39ca813496	success	\N	2026-09-25 14:51:11.848004+00	\N
63ecfced-605b-422c-b26a-4f9bc374dba0	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	33a7e677-b29a-4895-87f4-1a8b43a1e374	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	success	\N	2026-09-25 14:51:11.880998+00	\N
5ac7ecfd-0c04-472f-b01d-ffa52fe01936	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	33a7e677-b29a-4895-87f4-1a8b43a1e374	\N	{"state": "queued", "job_type": "transient_failure", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 14:51:11.885598+00	\N
bfe3c59e-c8b9-4d32-9050-7318d0294417	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	33a7e677-b29a-4895-87f4-1a8b43a1e374	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	success	\N	2026-09-25 14:51:11.898435+00	\N
9970c203-e8e9-4fcf-b6dd-c54c55db05dd	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	33a7e677-b29a-4895-87f4-1a8b43a1e374	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	success	\N	2026-09-25 14:51:11.912621+00	\N
856a2e2d-fdbf-4158-b4ac-5078f057d9c9	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.retry_wait	job_request	33a7e677-b29a-4895-87f4-1a8b43a1e374	{"actor": "worker", "state": "running"}	{"state": "retry_wait", "reason": "retryable transient_error", "correlation_id": null}	production	normal	\N	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	success	\N	2026-09-25 14:51:11.929744+00	\N
01f3e904-3600-414c-8446-140ffc42031d	818d3840-1a16-40b6-9757-9e5a67af68f8	scheduler	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	33a7e677-b29a-4895-87f4-1a8b43a1e374	{"actor": "scheduler", "state": "retry_wait"}	{"state": "queued", "reason": "backoff elapsed", "correlation_id": null}	production	normal	\N	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	success	\N	2026-09-25 14:51:11.950146+00	\N
ed335e47-257b-4cdc-97c9-cdeb58a7802e	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	33a7e677-b29a-4895-87f4-1a8b43a1e374	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	success	\N	2026-09-25 14:51:11.962305+00	\N
f59ed9ab-5585-4477-bc31-961063e2b55b	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	33a7e677-b29a-4895-87f4-1a8b43a1e374	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	success	\N	2026-09-25 14:51:11.975902+00	\N
1f227281-4ede-49ae-9c95-6482257d3b69	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	33a7e677-b29a-4895-87f4-1a8b43a1e374	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	success	\N	2026-09-25 14:51:11.994625+00	\N
bb26aecd-9fe3-4066-8da0-2dc6ac7774e5	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.create	job_schedule	71f8100f-4b51-4cca-8006-1c767079361e	\N	{"enabled": true, "job_type": "immediate_success"}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.011264+00	\N
72a8fbe6-9403-4fcc-b9fa-6a012df5a26a	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	df75213d-9b26-4a9f-bd32-4cf32de0e372	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T14:42:35.292807+00:00"}	production	normal	\N	ed8d2c75-d737-438a-bb53-4e457d4b096b	success	\N	2026-09-25 14:51:12.035522+00	2026-09-25T14:42:35.292807+00:00
a4af45ba-6cd0-41c6-a07d-5313888b228d	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	df75213d-9b26-4a9f-bd32-4cf32de0e372	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.040322+00	2026-09-25T14:42:35.292807+00:00
a41f719d-db64-406a-adf0-8332e08fe9d2	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	40b37ae5-1596-4a99-8859-76e7c022769f	\N	{"job_id": "df75213d-9b26-4a9f-bd32-4cf32de0e372", "occurrence": "2026-09-25T14:42:35.292807+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.046336+00	\N
74098d3e-9e76-4a02-afa6-9b7886ec02e6	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": false, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 14:53:52.491107+00	\N
53f6d7fb-6c69-4ea2-9085-5a4c1918bae6	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	41f26384-a34f-4fc6-987c-087a046cf42c	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T14:42:52.427134+00:00"}	production	normal	\N	3a5821b2-e29b-4355-b128-a97ddd6c4b8d	success	\N	2026-09-25 14:51:12.070905+00	2026-09-25T14:42:52.427134+00:00
a00b736a-800a-4b9b-b2bf-5a1f4f7692c6	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	41f26384-a34f-4fc6-987c-087a046cf42c	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.075417+00	2026-09-25T14:42:52.427134+00:00
d0d4066e-960f-4126-8df5-b7aa737ac491	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	eb43ac8b-9092-41cd-916e-7029f677874d	\N	{"job_id": "41f26384-a34f-4fc6-987c-087a046cf42c", "occurrence": "2026-09-25T14:42:52.427134+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.081043+00	\N
4771b753-bce2-4c14-a050-7286fc8f2274	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	8368c245-aeb2-4758-b4c8-ba91d8aec34e	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T14:43:23.199997+00:00"}	production	normal	\N	60873eaa-b945-465d-ac58-8761ed134713	success	\N	2026-09-25 14:51:12.105373+00	2026-09-25T14:43:23.199997+00:00
7dba343a-bf6e-40a1-8780-14f4345498c8	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	8368c245-aeb2-4758-b4c8-ba91d8aec34e	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.109958+00	2026-09-25T14:43:23.199997+00:00
95e583d8-4250-4b3a-ba20-3bf24bc06cc5	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	6c5ed8fa-7912-4a20-8cc0-952cd2522db7	\N	{"job_id": "8368c245-aeb2-4758-b4c8-ba91d8aec34e", "occurrence": "2026-09-25T14:43:23.199997+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.115302+00	\N
20c3ffe3-73d3-4dba-92d6-3d1985bee693	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	3013ce28-c3cc-4798-be62-1f1df2b99f45	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T14:43:39.275532+00:00"}	production	normal	\N	7d07bd89-d711-4209-a0de-7eade8fb8d17	success	\N	2026-09-25 14:51:12.138293+00	2026-09-25T14:43:39.275532+00:00
1e1035ea-5513-4b98-a164-702d324c3365	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	3013ce28-c3cc-4798-be62-1f1df2b99f45	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.14266+00	2026-09-25T14:43:39.275532+00:00
5febb7dc-845c-4e01-9775-28a864320af9	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	8615ca91-de1c-49ea-85ea-74bede8ae9b8	\N	{"job_id": "3013ce28-c3cc-4798-be62-1f1df2b99f45", "occurrence": "2026-09-25T14:43:39.275532+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.14776+00	\N
28a44329-fca2-4ae8-9ef9-e66dbfcdf1e4	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	d1b04528-b5f3-4cd7-a5d8-6534f355e04b	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T14:47:36.370345+00:00"}	production	normal	\N	8fd371e8-fff7-4585-a4ec-440107ec8af6	success	\N	2026-09-25 14:51:12.169379+00	2026-09-25T14:47:36.370345+00:00
44e38a47-fde8-4047-9d13-01da63788a5e	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	d1b04528-b5f3-4cd7-a5d8-6534f355e04b	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.173522+00	2026-09-25T14:47:36.370345+00:00
bd3421ca-6b07-4941-a4a4-3cd44d3bf079	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	a25e0083-a2f2-4347-8cc3-297c6b6c3bc7	\N	{"job_id": "d1b04528-b5f3-4cd7-a5d8-6534f355e04b", "occurrence": "2026-09-25T14:47:36.370345+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.178763+00	\N
139565d7-f955-45fe-8733-58a2e3fa76eb	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	55e5d9d2-4d45-4d32-a5cb-6566ea148cd6	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T14:48:00.349508+00:00"}	production	normal	\N	4e84497f-7ed5-4d89-9335-8c4138ab1de8	success	\N	2026-09-25 14:51:12.201747+00	2026-09-25T14:48:00.349508+00:00
ed3d52ae-73ae-46b2-ac58-8fa403413619	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	55e5d9d2-4d45-4d32-a5cb-6566ea148cd6	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.206022+00	2026-09-25T14:48:00.349508+00:00
2c9eedc7-929c-4261-baba-f2a020c46717	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	6415cb76-6249-46ad-9649-30d1025ba72c	\N	{"job_id": "55e5d9d2-4d45-4d32-a5cb-6566ea148cd6", "occurrence": "2026-09-25T14:48:00.349508+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.211202+00	\N
36015b7d-4111-412a-ab23-0ed827ff2bcf	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	f0a2b5a5-b0d5-4316-8cd4-1e095e241060	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T14:51:07.007024+00:00"}	production	normal	\N	862b2b82-ae8f-4668-b58a-596f73e32533	success	\N	2026-09-25 14:51:12.233163+00	2026-09-25T14:51:07.007024+00:00
0045a0a0-9cd7-453a-bb8a-d3fe33cf05db	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	f0a2b5a5-b0d5-4316-8cd4-1e095e241060	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.237468+00	2026-09-25T14:51:07.007024+00:00
0b9654a0-fe06-4f74-985f-4a0569766ef9	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	71f8100f-4b51-4cca-8006-1c767079361e	\N	{"job_id": "f0a2b5a5-b0d5-4316-8cd4-1e095e241060", "occurrence": "2026-09-25T14:51:07.007024+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.242502+00	\N
bdf00510-c66b-4ef8-bc17-c3be17bb962d	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	ece8ac3a-1061-486c-a849-7574c872926d	\N	{"job_type": "immediate_success", "idempotent_replay": true}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.324705+00	staging-req-chain-1
394ccc4d-4a71-46a3-9ee3-4acf70fb58cf	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	df75213d-9b26-4a9f-bd32-4cf32de0e372	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T14:42:35.292807+00:00"}	production	normal	\N	ed8d2c75-d737-438a-bb53-4e457d4b096b	success	\N	2026-09-25 14:51:12.338979+00	2026-09-25T14:42:35.292807+00:00
9769259c-9512-4991-ba9e-baf33245b174	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	df75213d-9b26-4a9f-bd32-4cf32de0e372	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T14:42:35.292807+00:00"}	production	normal	\N	ed8d2c75-d737-438a-bb53-4e457d4b096b	success	\N	2026-09-25 14:51:12.353659+00	2026-09-25T14:42:35.292807+00:00
952b480f-6fff-4e16-be5e-5c256475933d	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	df75213d-9b26-4a9f-bd32-4cf32de0e372	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T14:42:35.292807+00:00"}	production	normal	\N	ed8d2c75-d737-438a-bb53-4e457d4b096b	success	\N	2026-09-25 14:51:12.372749+00	2026-09-25T14:42:35.292807+00:00
6e73bb9d-1659-4c0c-af1b-a4aec57ef05c	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	41f26384-a34f-4fc6-987c-087a046cf42c	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T14:42:52.427134+00:00"}	production	normal	\N	3a5821b2-e29b-4355-b128-a97ddd6c4b8d	success	\N	2026-09-25 14:51:12.396363+00	2026-09-25T14:42:52.427134+00:00
ee6e4b13-b671-4f16-9af3-4b663329456f	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	41f26384-a34f-4fc6-987c-087a046cf42c	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T14:42:52.427134+00:00"}	production	normal	\N	3a5821b2-e29b-4355-b128-a97ddd6c4b8d	success	\N	2026-09-25 14:51:12.411292+00	2026-09-25T14:42:52.427134+00:00
cbe7f7e1-f49d-4781-9177-3e96e9afb965	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	41f26384-a34f-4fc6-987c-087a046cf42c	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T14:42:52.427134+00:00"}	production	normal	\N	3a5821b2-e29b-4355-b128-a97ddd6c4b8d	success	\N	2026-09-25 14:51:12.430006+00	2026-09-25T14:42:52.427134+00:00
b3538086-8f2c-489c-80a2-30decf78d602	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	8368c245-aeb2-4758-b4c8-ba91d8aec34e	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T14:43:23.199997+00:00"}	production	normal	\N	60873eaa-b945-465d-ac58-8761ed134713	success	\N	2026-09-25 14:51:12.460014+00	2026-09-25T14:43:23.199997+00:00
ff2109d0-d74a-4522-a922-8125db79c2b5	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	8368c245-aeb2-4758-b4c8-ba91d8aec34e	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T14:43:23.199997+00:00"}	production	normal	\N	60873eaa-b945-465d-ac58-8761ed134713	success	\N	2026-09-25 14:51:12.473564+00	2026-09-25T14:43:23.199997+00:00
8f5ea4f0-de62-4d69-895c-0333828c20ca	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	8368c245-aeb2-4758-b4c8-ba91d8aec34e	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T14:43:23.199997+00:00"}	production	normal	\N	60873eaa-b945-465d-ac58-8761ed134713	success	\N	2026-09-25 14:51:12.493188+00	2026-09-25T14:43:23.199997+00:00
116799a6-9953-4b99-ae69-a353d411c43c	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	3013ce28-c3cc-4798-be62-1f1df2b99f45	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T14:43:39.275532+00:00"}	production	normal	\N	7d07bd89-d711-4209-a0de-7eade8fb8d17	success	\N	2026-09-25 14:51:12.50733+00	2026-09-25T14:43:39.275532+00:00
20727a47-7edd-47fa-ab90-490546ce6a5b	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	3013ce28-c3cc-4798-be62-1f1df2b99f45	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T14:43:39.275532+00:00"}	production	normal	\N	7d07bd89-d711-4209-a0de-7eade8fb8d17	success	\N	2026-09-25 14:51:12.521921+00	2026-09-25T14:43:39.275532+00:00
6ade6495-80fb-4e29-9024-0fa61609c5a8	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	3013ce28-c3cc-4798-be62-1f1df2b99f45	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T14:43:39.275532+00:00"}	production	normal	\N	7d07bd89-d711-4209-a0de-7eade8fb8d17	success	\N	2026-09-25 14:51:12.541187+00	2026-09-25T14:43:39.275532+00:00
97f4608b-aae1-4ce4-ba89-9803024e101d	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	d1b04528-b5f3-4cd7-a5d8-6534f355e04b	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T14:47:36.370345+00:00"}	production	normal	\N	8fd371e8-fff7-4585-a4ec-440107ec8af6	success	\N	2026-09-25 14:51:12.554489+00	2026-09-25T14:47:36.370345+00:00
3481cbea-6f9b-45f8-8a46-0ebe2559d9db	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	d1b04528-b5f3-4cd7-a5d8-6534f355e04b	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T14:47:36.370345+00:00"}	production	normal	\N	8fd371e8-fff7-4585-a4ec-440107ec8af6	success	\N	2026-09-25 14:51:12.567653+00	2026-09-25T14:47:36.370345+00:00
2b66550d-5a27-47be-b33a-dad92e8eaffe	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	d1b04528-b5f3-4cd7-a5d8-6534f355e04b	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T14:47:36.370345+00:00"}	production	normal	\N	8fd371e8-fff7-4585-a4ec-440107ec8af6	success	\N	2026-09-25 14:51:12.585341+00	2026-09-25T14:47:36.370345+00:00
6ce0680d-5954-4f4e-be2b-c4887cd17723	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	55e5d9d2-4d45-4d32-a5cb-6566ea148cd6	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T14:48:00.349508+00:00"}	production	normal	\N	4e84497f-7ed5-4d89-9335-8c4138ab1de8	success	\N	2026-09-25 14:51:12.598133+00	2026-09-25T14:48:00.349508+00:00
7afe92c2-8da0-4de1-a159-feff6dfadf2d	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	55e5d9d2-4d45-4d32-a5cb-6566ea148cd6	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T14:48:00.349508+00:00"}	production	normal	\N	4e84497f-7ed5-4d89-9335-8c4138ab1de8	success	\N	2026-09-25 14:51:12.611333+00	2026-09-25T14:48:00.349508+00:00
ae67bec8-e631-4c0d-a226-d9030cb88627	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	55e5d9d2-4d45-4d32-a5cb-6566ea148cd6	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T14:48:00.349508+00:00"}	production	normal	\N	4e84497f-7ed5-4d89-9335-8c4138ab1de8	success	\N	2026-09-25 14:51:12.630633+00	2026-09-25T14:48:00.349508+00:00
5bab883d-cb5c-4bc9-86a8-bc9a37c574c8	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	f0a2b5a5-b0d5-4316-8cd4-1e095e241060	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T14:51:07.007024+00:00"}	production	normal	\N	862b2b82-ae8f-4668-b58a-596f73e32533	success	\N	2026-09-25 14:51:12.645106+00	2026-09-25T14:51:07.007024+00:00
eb5d8d8a-5dc7-441f-83e1-fdb2ef571730	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	f0a2b5a5-b0d5-4316-8cd4-1e095e241060	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T14:51:07.007024+00:00"}	production	normal	\N	862b2b82-ae8f-4668-b58a-596f73e32533	success	\N	2026-09-25 14:51:12.660268+00	2026-09-25T14:51:07.007024+00:00
976d0c18-e58b-435c-ae71-76a52445ebc8	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	f0a2b5a5-b0d5-4316-8cd4-1e095e241060	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T14:51:07.007024+00:00"}	production	normal	\N	862b2b82-ae8f-4668-b58a-596f73e32533	success	\N	2026-09-25 14:51:12.679168+00	2026-09-25T14:51:07.007024+00:00
d84e1287-0358-4699-9b2b-622ed7b210f2	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	2de868d1-6a42-4874-b6c4-08a6f521ee4e	\N	{"job_type": "immediate_success", "idempotent_replay": true}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.734049+00	\N
dee0c64a-1ad5-4fc1-b0a8-aa7ac941bfcb	69ff71b2-7a3b-4f5f-9056-2b666d3b0026	viewer	7b3dfe7a-545a-4f92-880f-ca37f5d1f7d8	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/usage/summary", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 14:51:12.752682+00	\N
6414461c-b4bd-4a89-8721-576df9e545a0	69ff71b2-7a3b-4f5f-9056-2b666d3b0026	viewer	7b3dfe7a-545a-4f92-880f-ca37f5d1f7d8	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/providers", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 14:51:12.760606+00	\N
3d2bf4bd-f285-4f36-b716-8a2c77e21d08	69ff71b2-7a3b-4f5f-9056-2b666d3b0026	viewer	7b3dfe7a-545a-4f92-880f-ca37f5d1f7d8	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable", "method": "POST", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 14:51:12.771099+00	\N
02c6c559-426f-4d9c-9003-7745c3c9d9a6	69ff71b2-7a3b-4f5f-9056-2b666d3b0026	viewer	7b3dfe7a-545a-4f92-880f-ca37f5d1f7d8	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable/41f26384-a34f-4fc6-987c-087a046cf42c", "method": "GET", "status": 404}	production	normal	\N	\N	denied	\N	2026-09-25 14:51:12.781533+00	\N
0ea137d3-9dbb-4866-a919-20858528f1fa	8809ba90-55dd-48d0-a895-665fc5872741	operator	1cd446b8-a2b4-43d9-8adb-869d5e854ffc	\N	\N	legal.acceptance	legal_document	acceptable_use_policy	\N	{"version": "1.0", "doc_type": "acceptable_use_policy", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.840615+00	dc6ccfba-2029-4523-ac8f-3078de96b935
b9fdb42e-77ed-48d9-8286-1445a8e4123d	8809ba90-55dd-48d0-a895-665fc5872741	operator	1cd446b8-a2b4-43d9-8adb-869d5e854ffc	\N	\N	legal.acceptance	legal_document	terms_of_service	\N	{"version": "1.0", "doc_type": "terms_of_service", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.844109+00	dc6ccfba-2029-4523-ac8f-3078de96b935
ad20f873-852e-4ad5-b51b-3155485a5596	8809ba90-55dd-48d0-a895-665fc5872741	operator	1cd446b8-a2b4-43d9-8adb-869d5e854ffc	\N	\N	legal.acceptance	legal_document	privacy_notice	\N	{"version": "1.0", "doc_type": "privacy_notice", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.847134+00	dc6ccfba-2029-4523-ac8f-3078de96b935
42c5fc31-fa11-4480-9e0b-f8afc5fe4cd2	8809ba90-55dd-48d0-a895-665fc5872741	requestor	1cd446b8-a2b4-43d9-8adb-869d5e854ffc	\N	\N	job.state.queued	job_request	590d00ff-754c-428e-bec4-dc642314b8d1	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	6ed4e858-451b-48b6-83db-ba11662eac4f	success	\N	2026-09-25 14:51:12.874698+00	\N
79525c52-62ec-4666-b270-1bed6e24e25b	8809ba90-55dd-48d0-a895-665fc5872741	operator	1cd446b8-a2b4-43d9-8adb-869d5e854ffc	\N	\N	job.submit	job_request	590d00ff-754c-428e-bec4-dc642314b8d1	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 14:51:12.879945+00	\N
822a2393-afef-42b7-8d53-78e4cecbd7ef	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": false, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 14:52:43.565195+00	\N
f5c4ea89-36fb-41d4-b061-b61133c07674	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 401}	production	normal	\N	\N	denied	\N	2026-09-25 14:52:43.740685+00	\N
cd5ffaa6-4ed1-4b54-a25a-d3763b19ab8b	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 14:52:43.764315+00	\N
1eeb5845-4de0-402b-88d0-b4cb8d2f678a	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	session.revoke	session	staging-revoke-1790347963767	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 14:52:43.781547+00	\N
45463364-d3ce-426f-b2aa-2cc92fb415e4	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 401}	production	normal	\N	\N	denied	\N	2026-09-25 14:52:43.78681+00	\N
1a1570bd-e05c-41c9-a9e2-351f8f13c275	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": false, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 14:52:54.520886+00	\N
3d589cac-baed-4ee5-a119-649c89d4c931	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 401}	production	normal	\N	\N	denied	\N	2026-09-25 14:52:54.694313+00	\N
28bbd3cc-372e-4c00-a39f-fc4bae7fe1d1	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 14:52:54.717595+00	\N
fc9f2324-cb18-4afd-b490-9e2b7591066e	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	session.revoke	session	staging-revoke-1790347974721	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 14:52:54.736712+00	\N
6578e47f-527f-4868-a520-a2e075ef059d	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 401}	production	normal	\N	\N	denied	\N	2026-09-25 14:52:54.74305+00	\N
eb185caa-b681-49f9-b802-23c4ce155b37	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	legal.acceptance	legal_document	acceptable_use_policy	\N	{"version": "1.0", "doc_type": "acceptable_use_policy", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 14:53:52.533734+00	\N
610403e9-18e5-4f89-b70a-23199ee6fd15	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	legal.acceptance	legal_document	terms_of_service	\N	{"version": "1.0", "doc_type": "terms_of_service", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 14:53:52.537679+00	\N
82982ee8-1dcd-4991-bc4b-11eea366c43b	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	legal.acceptance	legal_document	privacy_notice	\N	{"version": "1.0", "doc_type": "privacy_notice", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 14:53:52.540285+00	\N
464c6dbe-852b-4c71-aa5a-d2c851a5e2c1	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 401}	production	normal	\N	\N	denied	\N	2026-09-25 14:53:52.677885+00	\N
8bcdc584-9647-4457-83de-37ddc114035d	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 14:53:52.69907+00	\N
e7b48555-e8cc-4ef7-a4a2-64b42e8fa21b	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	session.revoke	session	staging-revoke-1790348032703	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 14:53:52.719579+00	\N
db502ed1-9e30-4ec9-a3ac-eeca7ff09f95	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 401}	production	normal	\N	\N	denied	\N	2026-09-25 14:53:52.725208+00	\N
f46b7045-3341-4007-8d05-3938e01298eb	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	preview.start	preview_session	30704cc4-4480-4d91-8c04-2f11de7aae57	\N	{"reason": "staging smoke", "target_role": null}	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 14:53:52.736697+00	\N
ee1888c7-e9da-41a7-be8c-5396ae8ffc88	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	preview.end	preview_session	30704cc4-4480-4d91-8c04-2f11de7aae57	\N	\N	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 14:53:52.754273+00	\N
9881ce03-3bf8-4489-a79d-7338e7485101	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	32baf8fb-af8f-4f7a-a8d1-cd7a30f2c7fe	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	52a538e7-14cd-411f-b68a-a012031f7fc0	success	\N	2026-09-25 14:53:52.796781+00	\N
b0b48d98-e625-4d16-976c-895ac0d731dc	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	32baf8fb-af8f-4f7a-a8d1-cd7a30f2c7fe	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 14:53:52.801151+00	\N
e3ee5d1a-3f0f-4667-8d7e-1b222d818cc5	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	32baf8fb-af8f-4f7a-a8d1-cd7a30f2c7fe	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	52a538e7-14cd-411f-b68a-a012031f7fc0	success	\N	2026-09-25 14:53:52.813696+00	\N
8f44a5b9-2ff1-45b7-8153-1483664c9b7b	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	32baf8fb-af8f-4f7a-a8d1-cd7a30f2c7fe	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	52a538e7-14cd-411f-b68a-a012031f7fc0	success	\N	2026-09-25 14:53:52.828009+00	\N
37ab52dd-75c8-466f-9ea4-cf53c378c448	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	32baf8fb-af8f-4f7a-a8d1-cd7a30f2c7fe	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	52a538e7-14cd-411f-b68a-a012031f7fc0	success	\N	2026-09-25 14:53:52.847859+00	\N
37ccf7c6-1a65-4afb-beb6-1aa3e1d2f3c2	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	066a69b5-3244-4e91-8da5-01f414b9052a	success	\N	2026-09-25 14:53:52.882732+00	\N
b1728fa2-0d1e-4d04-bf66-49acc8dc3f00	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	\N	{"state": "queued", "job_type": "transient_failure", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 14:53:52.886996+00	\N
78131b6b-4054-4ef7-8ad8-522d5065cbaa	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	066a69b5-3244-4e91-8da5-01f414b9052a	success	\N	2026-09-25 14:53:52.899668+00	\N
d17e7ba6-5506-466c-b2f7-5c93e09bd184	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	066a69b5-3244-4e91-8da5-01f414b9052a	success	\N	2026-09-25 14:53:52.913591+00	\N
c6ad67cc-c881-4e09-97a9-649aa2970f62	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.retry_wait	job_request	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	{"actor": "worker", "state": "running"}	{"state": "retry_wait", "reason": "retryable transient_error", "correlation_id": null}	production	normal	\N	066a69b5-3244-4e91-8da5-01f414b9052a	success	\N	2026-09-25 14:53:52.930628+00	\N
77c6c4da-a162-4f84-bf5a-0bad61a3e65b	818d3840-1a16-40b6-9757-9e5a67af68f8	scheduler	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	{"actor": "scheduler", "state": "retry_wait"}	{"state": "queued", "reason": "backoff elapsed", "correlation_id": null}	production	normal	\N	066a69b5-3244-4e91-8da5-01f414b9052a	success	\N	2026-09-25 14:53:52.951818+00	\N
ed95b30d-6ab9-49dc-ba53-f670edfbe5d2	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	066a69b5-3244-4e91-8da5-01f414b9052a	success	\N	2026-09-25 14:53:52.963879+00	\N
3adb2f21-97b4-4bef-a817-f4a18a0578e1	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	066a69b5-3244-4e91-8da5-01f414b9052a	success	\N	2026-09-25 14:53:52.977813+00	\N
bfd13de6-6fbc-46da-a1cf-17414f8cf253	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	066a69b5-3244-4e91-8da5-01f414b9052a	success	\N	2026-09-25 14:53:52.996324+00	\N
a913b967-b7d0-4c6e-a363-f06cf753afed	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.create	job_schedule	af6eb320-1eb3-4f10-9b63-67960864a378	\N	{"enabled": true, "job_type": "immediate_success"}	production	normal	\N	\N	success	\N	2026-09-25 14:53:53.012497+00	\N
6ff20e6d-950f-43ff-9c86-9a488f52fa1e	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	d9001c70-db76-4ee9-a52f-d102a0284ae1	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T14:53:48.009537+00:00"}	production	normal	\N	46a6356b-3b04-4540-bef9-d1ba99fcf6ec	success	\N	2026-09-25 14:53:53.035498+00	2026-09-25T14:53:48.009537+00:00
cc668487-e03c-4859-a718-9517f8aeef9e	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	d9001c70-db76-4ee9-a52f-d102a0284ae1	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 14:53:53.039845+00	2026-09-25T14:53:48.009537+00:00
7fbd328f-7693-43ba-aa5a-086aa27e346e	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	af6eb320-1eb3-4f10-9b63-67960864a378	\N	{"job_id": "d9001c70-db76-4ee9-a52f-d102a0284ae1", "occurrence": "2026-09-25T14:53:48.009537+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 14:53:53.044997+00	\N
289b0210-9c8e-4541-bbcf-3f47003b788f	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	ece8ac3a-1061-486c-a849-7574c872926d	\N	{"job_type": "immediate_success", "idempotent_replay": true}	production	normal	\N	\N	success	\N	2026-09-25 14:53:53.132013+00	staging-req-chain-1
b865726b-a8f1-4609-b74d-c6189113c7e1	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	d9001c70-db76-4ee9-a52f-d102a0284ae1	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T14:53:48.009537+00:00"}	production	normal	\N	46a6356b-3b04-4540-bef9-d1ba99fcf6ec	success	\N	2026-09-25 14:53:53.145173+00	2026-09-25T14:53:48.009537+00:00
5a857c79-72cc-4192-ad76-c5dffd72e0ea	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	d9001c70-db76-4ee9-a52f-d102a0284ae1	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T14:53:48.009537+00:00"}	production	normal	\N	46a6356b-3b04-4540-bef9-d1ba99fcf6ec	success	\N	2026-09-25 14:53:53.159963+00	2026-09-25T14:53:48.009537+00:00
1c22aa0e-2109-4cb3-afb8-e3d0a3e1ef1b	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	d9001c70-db76-4ee9-a52f-d102a0284ae1	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T14:53:48.009537+00:00"}	production	normal	\N	46a6356b-3b04-4540-bef9-d1ba99fcf6ec	success	\N	2026-09-25 14:53:53.179528+00	2026-09-25T14:53:48.009537+00:00
a1fd6ece-4382-44b8-913b-e7716b7aeadc	2bc09d54-2de2-4d09-bd0c-db716530fe25	viewer	c7bdbe56-d353-42b2-aed6-eb7e9ebe2c0e	\N	\N	legal.acceptance	legal_document	acceptable_use_policy	\N	{"version": "1.0", "doc_type": "acceptable_use_policy", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 14:53:53.231185+00	\N
9f64bcc6-2285-4f45-b59c-9786274a27ad	2bc09d54-2de2-4d09-bd0c-db716530fe25	viewer	c7bdbe56-d353-42b2-aed6-eb7e9ebe2c0e	\N	\N	legal.acceptance	legal_document	terms_of_service	\N	{"version": "1.0", "doc_type": "terms_of_service", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 14:53:53.233566+00	\N
e345c087-45ff-4023-b263-492a8b59af71	2bc09d54-2de2-4d09-bd0c-db716530fe25	viewer	c7bdbe56-d353-42b2-aed6-eb7e9ebe2c0e	\N	\N	legal.acceptance	legal_document	privacy_notice	\N	{"version": "1.0", "doc_type": "privacy_notice", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 14:53:53.235993+00	\N
a3a7a152-3b5b-4308-bf81-ef9037f40ba1	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	2de868d1-6a42-4874-b6c4-08a6f521ee4e	\N	{"job_type": "immediate_success", "idempotent_replay": true}	production	normal	\N	\N	success	\N	2026-09-25 14:53:53.244915+00	\N
a8cef719-594c-4878-a153-fd8c53e73759	2bc09d54-2de2-4d09-bd0c-db716530fe25	viewer	c7bdbe56-d353-42b2-aed6-eb7e9ebe2c0e	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/usage/summary", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 14:53:53.263923+00	\N
fb6d2d8e-0147-468d-ac4e-8d481be1e84e	2bc09d54-2de2-4d09-bd0c-db716530fe25	viewer	c7bdbe56-d353-42b2-aed6-eb7e9ebe2c0e	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/providers", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 14:53:53.272064+00	\N
19b6d528-0484-4783-bec8-d5eebd939391	2bc09d54-2de2-4d09-bd0c-db716530fe25	viewer	c7bdbe56-d353-42b2-aed6-eb7e9ebe2c0e	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable", "method": "POST", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 14:53:53.280566+00	\N
575375ac-80f5-4078-8631-4eaa6b0ffe55	2bc09d54-2de2-4d09-bd0c-db716530fe25	viewer	c7bdbe56-d353-42b2-aed6-eb7e9ebe2c0e	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable/d9001c70-db76-4ee9-a52f-d102a0284ae1", "method": "GET", "status": 404}	production	normal	\N	\N	denied	\N	2026-09-25 14:53:53.290047+00	\N
636f1f45-ca25-4890-9677-a1ed5e419c67	4aaa159d-cfe8-41f6-8c52-d2f2d9c214c4	operator	1c30d9ed-d52a-42ed-a4b9-e0bd0f1090eb	\N	\N	legal.acceptance	legal_document	acceptable_use_policy	\N	{"version": "1.0", "doc_type": "acceptable_use_policy", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 14:53:53.32818+00	474753c5-7f67-4470-9a35-83e20b89c2f3
2c4f968a-53cc-40dc-8e5b-2acd42a40a75	4aaa159d-cfe8-41f6-8c52-d2f2d9c214c4	operator	1c30d9ed-d52a-42ed-a4b9-e0bd0f1090eb	\N	\N	legal.acceptance	legal_document	terms_of_service	\N	{"version": "1.0", "doc_type": "terms_of_service", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 14:53:53.330847+00	474753c5-7f67-4470-9a35-83e20b89c2f3
206fc3b4-c035-4d7d-87d0-99b216f449c8	4aaa159d-cfe8-41f6-8c52-d2f2d9c214c4	operator	1c30d9ed-d52a-42ed-a4b9-e0bd0f1090eb	\N	\N	legal.acceptance	legal_document	privacy_notice	\N	{"version": "1.0", "doc_type": "privacy_notice", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 14:53:53.333403+00	474753c5-7f67-4470-9a35-83e20b89c2f3
685283b9-28e6-4303-84f0-afa80068ce91	4aaa159d-cfe8-41f6-8c52-d2f2d9c214c4	requestor	1c30d9ed-d52a-42ed-a4b9-e0bd0f1090eb	\N	\N	job.state.queued	job_request	3a54dc18-4988-4ddf-bdd2-3c50229a2fd6	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	d9dc7462-7954-4ba8-9d77-1c4538ad72e6	success	\N	2026-09-25 14:53:53.355864+00	\N
6d9feecb-e283-400d-9ec6-e5756302479e	4aaa159d-cfe8-41f6-8c52-d2f2d9c214c4	operator	1c30d9ed-d52a-42ed-a4b9-e0bd0f1090eb	\N	\N	job.submit	job_request	3a54dc18-4988-4ddf-bdd2-3c50229a2fd6	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 14:53:53.360099+00	\N
5e202698-ec93-421a-a2ff-5a187fe31496	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": false, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 15:37:31.351693+00	\N
c5e61e44-1165-4110-931d-ca9145775920	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	legal.acceptance	legal_document	private_beta_addendum	\N	{"version": "1.0", "doc_type": "private_beta_addendum", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:37:31.403499+00	\N
0f337b37-5f8c-42fe-8f2c-024999c0b72b	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	legal.acceptance	legal_document	acceptable_use_policy	\N	{"version": "1.0", "doc_type": "acceptable_use_policy", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:37:31.406271+00	\N
321fc741-c005-48c3-8e83-4cda9bc6f3cc	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	legal.acceptance	legal_document	terms_of_service	\N	{"version": "1.0", "doc_type": "terms_of_service", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:37:31.408749+00	\N
6db144a6-58fe-4b6e-a391-ae3327bdf0b4	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	legal.acceptance	legal_document	privacy_notice	\N	{"version": "1.0", "doc_type": "privacy_notice", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:37:31.411114+00	\N
026ab260-f44f-451e-a3a4-e4ccbed69160	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 401}	production	normal	\N	\N	denied	\N	2026-09-25 15:37:31.569652+00	\N
fb394d5b-ded1-48e3-aacd-cf2cc793e2ca	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:37:31.591315+00	\N
a8178515-b84e-4812-a51f-61a3461978ec	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	session.revoke	session	staging-revoke-1790350651595	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 15:37:31.61296+00	\N
c20bd04b-1a4a-4299-896d-ede939671e8c	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 401}	production	normal	\N	\N	denied	\N	2026-09-25 15:37:31.618849+00	\N
9440dcb4-fe95-4dba-ba38-33902c4200d6	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	preview.start	preview_session	f69f9a45-05d5-4fb4-b8c4-a48cdd16c5c6	\N	{"reason": "staging smoke", "target_role": null}	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 15:37:31.632005+00	\N
2b273684-027e-4e50-8d18-84e2141f1461	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	preview.end	preview_session	f69f9a45-05d5-4fb4-b8c4-a48cdd16c5c6	\N	\N	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 15:37:31.650272+00	\N
090896ad-b73b-44a8-bbc3-c79c2cce2663	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	45d210df-829b-4915-8e37-cca1449cb6d9	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	d384a816-2afc-4823-9510-a9e46d265c43	success	\N	2026-09-25 15:37:31.706676+00	\N
a4094116-9db6-4028-a2b1-ebf8d1f0a6ca	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	45d210df-829b-4915-8e37-cca1449cb6d9	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:37:31.711058+00	\N
5014001a-410c-4a40-af4f-eeb0d8a2136f	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	45d210df-829b-4915-8e37-cca1449cb6d9	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	d384a816-2afc-4823-9510-a9e46d265c43	success	\N	2026-09-25 15:37:31.723773+00	\N
f8b5853c-c03a-47b2-865b-5d60b29e4210	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	45d210df-829b-4915-8e37-cca1449cb6d9	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	d384a816-2afc-4823-9510-a9e46d265c43	success	\N	2026-09-25 15:37:31.739239+00	\N
1dcc7d28-c5a2-4493-96d0-aab01ce5d82d	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	45d210df-829b-4915-8e37-cca1449cb6d9	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	d384a816-2afc-4823-9510-a9e46d265c43	success	\N	2026-09-25 15:37:31.759577+00	\N
8fca237f-3330-4fd2-bf01-3f6cc6d0e83d	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	b8208594-7396-49a5-a29e-4518c24a4b93	success	\N	2026-09-25 15:37:31.794186+00	\N
bac92306-a8b0-48fd-8423-15a1a8da8a8b	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	\N	{"state": "queued", "job_type": "transient_failure", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:37:31.798481+00	\N
2d03b9fd-4501-41f4-9037-f981fa63fba0	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	b8208594-7396-49a5-a29e-4518c24a4b93	success	\N	2026-09-25 15:37:31.813175+00	\N
03624c8d-46d9-46a2-af07-731ca5a11f36	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	b8208594-7396-49a5-a29e-4518c24a4b93	success	\N	2026-09-25 15:37:31.828469+00	\N
6d654cff-a0bd-4910-809e-eea256436913	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.retry_wait	job_request	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	{"actor": "worker", "state": "running"}	{"state": "retry_wait", "reason": "retryable transient_error", "correlation_id": null}	production	normal	\N	b8208594-7396-49a5-a29e-4518c24a4b93	success	\N	2026-09-25 15:37:31.845812+00	\N
ac49481d-ffa5-45b0-8139-fa009b57be1b	2e02cc0b-0696-4647-b1b9-a8187761767e	viewer	a5dec5ab-0b73-43e7-b488-fa4b5dcbd340	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/usage/summary", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:38:04.640244+00	\N
215df4a1-d064-47b1-af83-16c1daf11809	818d3840-1a16-40b6-9757-9e5a67af68f8	scheduler	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	{"actor": "scheduler", "state": "retry_wait"}	{"state": "queued", "reason": "backoff elapsed", "correlation_id": null}	production	normal	\N	b8208594-7396-49a5-a29e-4518c24a4b93	success	\N	2026-09-25 15:37:31.86682+00	\N
1feec5a4-efb3-4e02-b835-edd1edc70c86	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	b8208594-7396-49a5-a29e-4518c24a4b93	success	\N	2026-09-25 15:37:31.880189+00	\N
fb9665c2-b5bc-47f5-a3b9-c5699cbeb50c	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	b8208594-7396-49a5-a29e-4518c24a4b93	success	\N	2026-09-25 15:37:31.894101+00	\N
0e73bc42-9537-42ef-9d66-a84ca160212a	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	b8208594-7396-49a5-a29e-4518c24a4b93	success	\N	2026-09-25 15:37:31.911247+00	\N
3761c375-0ad1-4f86-ae6c-c94f4813eb58	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.create	job_schedule	74ed46b8-b272-49cb-ad05-9e8083fb1c8c	\N	{"enabled": true, "job_type": "immediate_success"}	production	normal	\N	\N	success	\N	2026-09-25 15:37:31.927813+00	\N
2efdc069-946d-4822-b12f-7cb590f71a89	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.misfire	job_schedule	9e1827ad-dcba-457c-bc05-5168a0f220c8	\N	{"policy": "skip", "scheduled_for": "2026-09-25T15:11:38.982073+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 15:37:31.936739+00	\N
56a7303f-3766-4cae-9f4e-3e3c0f1f076b	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	3c51e672-9ffc-4708-a633-d6b0080b97db	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T15:37:26.923883+00:00"}	production	normal	\N	c06674c2-6599-436e-99d5-642fcc32e7b8	success	\N	2026-09-25 15:37:31.963571+00	2026-09-25T15:37:26.923883+00:00
e7df34ce-7d46-4ed2-b5df-39c077fb3752	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	3c51e672-9ffc-4708-a633-d6b0080b97db	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:37:31.968494+00	2026-09-25T15:37:26.923883+00:00
70392a02-5108-4270-a91a-4c9a816f2f6d	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	74ed46b8-b272-49cb-ad05-9e8083fb1c8c	\N	{"job_id": "3c51e672-9ffc-4708-a633-d6b0080b97db", "occurrence": "2026-09-25T15:37:26.923883+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 15:37:31.974175+00	\N
64ce3307-e881-43e3-8f0d-fac3ed4fa97d	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	ece8ac3a-1061-486c-a849-7574c872926d	\N	{"job_type": "immediate_success", "idempotent_replay": true}	production	normal	\N	\N	success	\N	2026-09-25 15:37:32.064392+00	staging-req-chain-1
499fb474-21d3-4804-9231-c81cf9a8677f	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	3c51e672-9ffc-4708-a633-d6b0080b97db	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T15:37:26.923883+00:00"}	production	normal	\N	c06674c2-6599-436e-99d5-642fcc32e7b8	success	\N	2026-09-25 15:37:32.076743+00	2026-09-25T15:37:26.923883+00:00
138785d5-4078-4489-941b-d0460339b611	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	3c51e672-9ffc-4708-a633-d6b0080b97db	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T15:37:26.923883+00:00"}	production	normal	\N	c06674c2-6599-436e-99d5-642fcc32e7b8	success	\N	2026-09-25 15:37:32.089841+00	2026-09-25T15:37:26.923883+00:00
ae53d950-9bb9-4e76-bde5-7bdcce72b081	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	3c51e672-9ffc-4708-a633-d6b0080b97db	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T15:37:26.923883+00:00"}	production	normal	\N	c06674c2-6599-436e-99d5-642fcc32e7b8	success	\N	2026-09-25 15:37:32.10874+00	2026-09-25T15:37:26.923883+00:00
10460838-f00e-40f7-8e59-cdeba6320a3c	8d23329e-c826-4cf3-9351-e8675d2c55c5	viewer	41f1bdb5-5143-4fc1-804e-45c1d0ad024f	\N	\N	legal.acceptance	legal_document	private_beta_addendum	\N	{"version": "1.0", "doc_type": "private_beta_addendum", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:37:32.165046+00	\N
75cadca1-e680-4d0f-a025-9a88911af344	8d23329e-c826-4cf3-9351-e8675d2c55c5	viewer	41f1bdb5-5143-4fc1-804e-45c1d0ad024f	\N	\N	legal.acceptance	legal_document	acceptable_use_policy	\N	{"version": "1.0", "doc_type": "acceptable_use_policy", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:37:32.168096+00	\N
0bfd2891-fe9c-4e8a-be4d-cb0fdd4833a4	8d23329e-c826-4cf3-9351-e8675d2c55c5	viewer	41f1bdb5-5143-4fc1-804e-45c1d0ad024f	\N	\N	legal.acceptance	legal_document	terms_of_service	\N	{"version": "1.0", "doc_type": "terms_of_service", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:37:32.171158+00	\N
25ddd9e5-32a7-4082-b8dd-b33628e26023	8d23329e-c826-4cf3-9351-e8675d2c55c5	viewer	41f1bdb5-5143-4fc1-804e-45c1d0ad024f	\N	\N	legal.acceptance	legal_document	privacy_notice	\N	{"version": "1.0", "doc_type": "privacy_notice", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:37:32.174354+00	\N
337e421f-f2cd-4afa-ac24-fc4ad9b2ff2a	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	2de868d1-6a42-4874-b6c4-08a6f521ee4e	\N	{"job_type": "immediate_success", "idempotent_replay": true}	production	normal	\N	\N	success	\N	2026-09-25 15:37:32.190988+00	\N
b69984eb-4c5c-4937-ae1e-0dfc66157528	8d23329e-c826-4cf3-9351-e8675d2c55c5	viewer	41f1bdb5-5143-4fc1-804e-45c1d0ad024f	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/usage/summary", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:37:32.21639+00	\N
9b18cf03-c4d3-4e14-989c-f6a39ca5c7a0	8d23329e-c826-4cf3-9351-e8675d2c55c5	viewer	41f1bdb5-5143-4fc1-804e-45c1d0ad024f	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/providers", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:37:32.225604+00	\N
39b81403-739d-4616-ba1a-17d2ef69b80d	8d23329e-c826-4cf3-9351-e8675d2c55c5	viewer	41f1bdb5-5143-4fc1-804e-45c1d0ad024f	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable", "method": "POST", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:37:32.235507+00	\N
8c80455f-34b4-4c43-9393-93c30cef9840	8d23329e-c826-4cf3-9351-e8675d2c55c5	viewer	41f1bdb5-5143-4fc1-804e-45c1d0ad024f	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable/3c51e672-9ffc-4708-a633-d6b0080b97db", "method": "GET", "status": 404}	production	normal	\N	\N	denied	\N	2026-09-25 15:37:32.246448+00	\N
1eeafbac-8206-4fd5-9086-e1e202059806	f8970e4e-f2bc-46e5-b1e2-6de99e823130	operator	8856d797-5714-421e-9b68-21977321152b	\N	\N	legal.acceptance	legal_document	private_beta_addendum	\N	{"version": "1.0", "doc_type": "private_beta_addendum", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:37:32.29179+00	9b0428e1-635f-471a-9af3-d138786dee4b
6f66f274-d526-407a-aad3-d2ac944d71c5	f8970e4e-f2bc-46e5-b1e2-6de99e823130	operator	8856d797-5714-421e-9b68-21977321152b	\N	\N	legal.acceptance	legal_document	acceptable_use_policy	\N	{"version": "1.0", "doc_type": "acceptable_use_policy", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:37:32.294228+00	9b0428e1-635f-471a-9af3-d138786dee4b
319d295c-0983-4a3d-9cb5-19abc7677fd3	f8970e4e-f2bc-46e5-b1e2-6de99e823130	operator	8856d797-5714-421e-9b68-21977321152b	\N	\N	legal.acceptance	legal_document	terms_of_service	\N	{"version": "1.0", "doc_type": "terms_of_service", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:37:32.296681+00	9b0428e1-635f-471a-9af3-d138786dee4b
374a27c2-cbbf-47d8-b6ae-39935a9b3259	f8970e4e-f2bc-46e5-b1e2-6de99e823130	operator	8856d797-5714-421e-9b68-21977321152b	\N	\N	legal.acceptance	legal_document	privacy_notice	\N	{"version": "1.0", "doc_type": "privacy_notice", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:37:32.298992+00	9b0428e1-635f-471a-9af3-d138786dee4b
2b11fb47-6c0d-48df-95d7-879bd79988ab	f8970e4e-f2bc-46e5-b1e2-6de99e823130	requestor	8856d797-5714-421e-9b68-21977321152b	\N	\N	job.state.queued	job_request	64db6bcb-b7cc-4fa1-9e0a-f78faa9e4121	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	5ee7d797-a106-4fcf-941a-833acb355abc	success	\N	2026-09-25 15:37:32.325481+00	\N
50ae65d3-3c39-4086-9650-ed405af1d79b	f8970e4e-f2bc-46e5-b1e2-6de99e823130	operator	8856d797-5714-421e-9b68-21977321152b	\N	\N	job.submit	job_request	64db6bcb-b7cc-4fa1-9e0a-f78faa9e4121	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:37:32.330165+00	\N
21f3aa53-9fd7-448d-bb95-69d49629a074	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	invite.issue	invite	aeb2cd0d-f153-4631-8034-6ca078234668	\N	{"email_domain": "staging.local"}	production	normal	\N	\N	success	\N	2026-09-25 15:37:32.344823+00	\N
4e6ab2d9-9c7d-4d8f-9463-9b3928a770d0	7ed20cf3-772b-41f7-8aab-1eacfdcbcd09	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	signup.accepted	invite	aeb2cd0d-f153-4631-8034-6ca078234668	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 15:37:32.359687+00	\N
33ef377c-49cd-447a-b6da-ef13b848b98d	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": false, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 15:38:03.823336+00	\N
97fac5cc-ab06-4418-bf57-542a3d926d5a	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 401}	production	normal	\N	\N	denied	\N	2026-09-25 15:38:04.018297+00	\N
d1a750a2-3d79-4521-8262-421400fa39b1	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:38:04.039961+00	\N
63c11fa3-6e19-41c9-9145-4edcf6016e75	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	session.revoke	session	staging-revoke-1790350684043	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.057152+00	\N
661f78a5-8b3d-4899-ad1c-eeac00033ed5	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 401}	production	normal	\N	\N	denied	\N	2026-09-25 15:38:04.062197+00	\N
09a02ff3-cd91-4dee-a051-997a53c73131	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	preview.start	preview_session	65d2d063-5c20-49b4-a018-4c1af0c8b711	\N	{"reason": "staging smoke", "target_role": null}	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 15:38:04.073546+00	\N
c62f48ac-c49c-4268-b649-797348ad24f7	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	preview.end	preview_session	65d2d063-5c20-49b4-a018-4c1af0c8b711	\N	\N	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 15:38:04.091471+00	\N
fb1f41cb-3259-43e1-adcc-b92389c1684b	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	87fd1bcb-34c1-4dc6-b7a0-b8c8d4255e2a	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	447d268e-6349-43bd-b790-d224b352371d	success	\N	2026-09-25 15:38:04.139675+00	\N
aa500c87-1455-45f6-93fe-379a2aaee387	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	87fd1bcb-34c1-4dc6-b7a0-b8c8d4255e2a	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.144217+00	\N
b4e332d5-10fb-481a-a4fb-4960432a747d	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	87fd1bcb-34c1-4dc6-b7a0-b8c8d4255e2a	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	447d268e-6349-43bd-b790-d224b352371d	success	\N	2026-09-25 15:38:04.157761+00	\N
62d9d822-fc98-40a9-aaf1-37ad8579fd9c	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	87fd1bcb-34c1-4dc6-b7a0-b8c8d4255e2a	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	447d268e-6349-43bd-b790-d224b352371d	success	\N	2026-09-25 15:38:04.172786+00	\N
784de406-1ad6-4b20-b12d-7d2d5d5cc9ea	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	87fd1bcb-34c1-4dc6-b7a0-b8c8d4255e2a	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	447d268e-6349-43bd-b790-d224b352371d	success	\N	2026-09-25 15:38:04.191853+00	\N
d86f6c98-d459-432f-a122-9da4893195fa	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	f88b1602-18de-45f7-a836-753ac6dbb73d	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	e870faf1-14e6-40f8-a346-6d60573785af	success	\N	2026-09-25 15:38:04.236156+00	\N
dc766274-44fc-4235-a2ce-3aacdc2da6a9	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	f88b1602-18de-45f7-a836-753ac6dbb73d	\N	{"state": "queued", "job_type": "transient_failure", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.242533+00	\N
1191b771-0276-43f1-b99d-3d53839422a4	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	f88b1602-18de-45f7-a836-753ac6dbb73d	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	e870faf1-14e6-40f8-a346-6d60573785af	success	\N	2026-09-25 15:38:04.258406+00	\N
9437cac8-49fd-476a-8bb5-c13bf1c35869	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	f88b1602-18de-45f7-a836-753ac6dbb73d	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	e870faf1-14e6-40f8-a346-6d60573785af	success	\N	2026-09-25 15:38:04.273407+00	\N
e26d5126-7d89-4095-9aba-b9e271906a28	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.retry_wait	job_request	f88b1602-18de-45f7-a836-753ac6dbb73d	{"actor": "worker", "state": "running"}	{"state": "retry_wait", "reason": "retryable transient_error", "correlation_id": null}	production	normal	\N	e870faf1-14e6-40f8-a346-6d60573785af	success	\N	2026-09-25 15:38:04.290363+00	\N
c18ff68a-5e33-4d9c-8263-baf1f555b22b	818d3840-1a16-40b6-9757-9e5a67af68f8	scheduler	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	f88b1602-18de-45f7-a836-753ac6dbb73d	{"actor": "scheduler", "state": "retry_wait"}	{"state": "queued", "reason": "backoff elapsed", "correlation_id": null}	production	normal	\N	e870faf1-14e6-40f8-a346-6d60573785af	success	\N	2026-09-25 15:38:04.312549+00	\N
aa7e7e20-3a0b-44e3-b125-2f19d5c8e3fa	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	f88b1602-18de-45f7-a836-753ac6dbb73d	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	e870faf1-14e6-40f8-a346-6d60573785af	success	\N	2026-09-25 15:38:04.324769+00	\N
c0710bc5-9d8a-49cb-a92c-093e4085e27e	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	f88b1602-18de-45f7-a836-753ac6dbb73d	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	e870faf1-14e6-40f8-a346-6d60573785af	success	\N	2026-09-25 15:38:04.339236+00	\N
93c5ba8f-927a-4068-a64e-95998c6c1036	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	f88b1602-18de-45f7-a836-753ac6dbb73d	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	e870faf1-14e6-40f8-a346-6d60573785af	success	\N	2026-09-25 15:38:04.357711+00	\N
abcac135-c6a0-4784-b79c-84d8e82bfa5f	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.create	job_schedule	4084524a-06b2-4b3f-b010-48fff44e98cb	\N	{"enabled": true, "job_type": "immediate_success"}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.375603+00	\N
40190d22-953d-4cab-aae1-adbd08bb65d7	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	bb9de075-0d97-4a93-8b3e-72c2bbf0b801	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T15:37:59.371396+00:00"}	production	normal	\N	13cb4d13-6660-4f9f-9730-4a8805603a19	success	\N	2026-09-25 15:38:04.401243+00	2026-09-25T15:37:59.371396+00:00
0c78acdd-995b-4e8f-acd1-06b7f78cd72e	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	bb9de075-0d97-4a93-8b3e-72c2bbf0b801	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.405555+00	2026-09-25T15:37:59.371396+00:00
44ae7d00-bab2-4f27-88d6-bb19db8ed2a2	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	4084524a-06b2-4b3f-b010-48fff44e98cb	\N	{"job_id": "bb9de075-0d97-4a93-8b3e-72c2bbf0b801", "occurrence": "2026-09-25T15:37:59.371396+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.411293+00	\N
5313fc7f-27b0-4fb5-b03f-3a1301314b54	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	ece8ac3a-1061-486c-a849-7574c872926d	\N	{"job_type": "immediate_success", "idempotent_replay": true}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.498282+00	staging-req-chain-1
2bd1e03b-237d-4089-9bd4-db9d5d9ec13e	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	bb9de075-0d97-4a93-8b3e-72c2bbf0b801	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T15:37:59.371396+00:00"}	production	normal	\N	13cb4d13-6660-4f9f-9730-4a8805603a19	success	\N	2026-09-25 15:38:04.508764+00	2026-09-25T15:37:59.371396+00:00
7865e065-78b7-4699-a305-4f481c010d34	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	bb9de075-0d97-4a93-8b3e-72c2bbf0b801	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T15:37:59.371396+00:00"}	production	normal	\N	13cb4d13-6660-4f9f-9730-4a8805603a19	success	\N	2026-09-25 15:38:04.522604+00	2026-09-25T15:37:59.371396+00:00
76454842-649b-4566-9394-a56f609b122c	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	bb9de075-0d97-4a93-8b3e-72c2bbf0b801	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T15:37:59.371396+00:00"}	production	normal	\N	13cb4d13-6660-4f9f-9730-4a8805603a19	success	\N	2026-09-25 15:38:04.540495+00	2026-09-25T15:37:59.371396+00:00
e00f603c-b544-4131-b151-b2cc6a475388	2e02cc0b-0696-4647-b1b9-a8187761767e	viewer	a5dec5ab-0b73-43e7-b488-fa4b5dcbd340	\N	\N	legal.acceptance	legal_document	private_beta_addendum	\N	{"version": "1.0", "doc_type": "private_beta_addendum", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.600627+00	\N
43f1e4f0-c90a-48a7-b298-55d2b73ac3b2	2e02cc0b-0696-4647-b1b9-a8187761767e	viewer	a5dec5ab-0b73-43e7-b488-fa4b5dcbd340	\N	\N	legal.acceptance	legal_document	acceptable_use_policy	\N	{"version": "1.0", "doc_type": "acceptable_use_policy", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.603072+00	\N
034a0769-d905-4d9d-9ddd-3e9aad9746fc	2e02cc0b-0696-4647-b1b9-a8187761767e	viewer	a5dec5ab-0b73-43e7-b488-fa4b5dcbd340	\N	\N	legal.acceptance	legal_document	terms_of_service	\N	{"version": "1.0", "doc_type": "terms_of_service", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.605454+00	\N
c574f193-a689-42f6-bacd-ba3a1449b6e8	2e02cc0b-0696-4647-b1b9-a8187761767e	viewer	a5dec5ab-0b73-43e7-b488-fa4b5dcbd340	\N	\N	legal.acceptance	legal_document	privacy_notice	\N	{"version": "1.0", "doc_type": "privacy_notice", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.608542+00	\N
6245c51b-e0f6-415e-80ad-31fcacaa7a51	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	2de868d1-6a42-4874-b6c4-08a6f521ee4e	\N	{"job_type": "immediate_success", "idempotent_replay": true}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.620008+00	\N
18b351a9-9abb-4824-a675-a3819b6e9817	2e02cc0b-0696-4647-b1b9-a8187761767e	viewer	a5dec5ab-0b73-43e7-b488-fa4b5dcbd340	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/providers", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:38:04.648462+00	\N
29b8bd73-bdb0-4e51-9f9f-d941422998d0	2e02cc0b-0696-4647-b1b9-a8187761767e	viewer	a5dec5ab-0b73-43e7-b488-fa4b5dcbd340	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable", "method": "POST", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:38:04.657295+00	\N
665bcc90-fe0c-4be1-80ca-e52fb9c94482	2e02cc0b-0696-4647-b1b9-a8187761767e	viewer	a5dec5ab-0b73-43e7-b488-fa4b5dcbd340	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable/f88b1602-18de-45f7-a836-753ac6dbb73d", "method": "GET", "status": 404}	production	normal	\N	\N	denied	\N	2026-09-25 15:38:04.668087+00	\N
5fda6425-eca3-4047-89d6-8fb3bd2fe621	189e1da9-2344-4468-aa4c-41235f9bd9c0	operator	9b6e00cd-d3cc-49f2-ab24-e45c50d89b55	\N	\N	legal.acceptance	legal_document	private_beta_addendum	\N	{"version": "1.0", "doc_type": "private_beta_addendum", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.711303+00	7be3e2a1-7951-42a0-aec7-93fdfb51aee7
63d7ce6b-fb3b-4577-909f-b3eea9d031b4	189e1da9-2344-4468-aa4c-41235f9bd9c0	operator	9b6e00cd-d3cc-49f2-ab24-e45c50d89b55	\N	\N	legal.acceptance	legal_document	acceptable_use_policy	\N	{"version": "1.0", "doc_type": "acceptable_use_policy", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.714856+00	7be3e2a1-7951-42a0-aec7-93fdfb51aee7
f5f0b2a6-c33b-4610-8f92-10d454aafc2c	189e1da9-2344-4468-aa4c-41235f9bd9c0	operator	9b6e00cd-d3cc-49f2-ab24-e45c50d89b55	\N	\N	legal.acceptance	legal_document	terms_of_service	\N	{"version": "1.0", "doc_type": "terms_of_service", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.71734+00	7be3e2a1-7951-42a0-aec7-93fdfb51aee7
592ee60a-ea93-404a-a33a-f40908a17a4d	189e1da9-2344-4468-aa4c-41235f9bd9c0	operator	9b6e00cd-d3cc-49f2-ab24-e45c50d89b55	\N	\N	legal.acceptance	legal_document	privacy_notice	\N	{"version": "1.0", "doc_type": "privacy_notice", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.719485+00	7be3e2a1-7951-42a0-aec7-93fdfb51aee7
6c2f36a6-883c-4bb4-b026-c09f2baa836e	189e1da9-2344-4468-aa4c-41235f9bd9c0	requestor	9b6e00cd-d3cc-49f2-ab24-e45c50d89b55	\N	\N	job.state.queued	job_request	00a1fa40-f69b-4121-958d-b8f8d9137513	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	a2d6877d-260c-469f-9662-b129ec767e8a	success	\N	2026-09-25 15:38:04.745542+00	\N
549082d5-d20d-4bc6-826e-c8fe1a68e28c	189e1da9-2344-4468-aa4c-41235f9bd9c0	operator	9b6e00cd-d3cc-49f2-ab24-e45c50d89b55	\N	\N	job.submit	job_request	00a1fa40-f69b-4121-958d-b8f8d9137513	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.74976+00	\N
e12350b9-5a35-44c1-8273-fc84b4f8209b	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	invite.issue	invite	4cbc5a3c-cdd1-4e70-b7ae-b73ac709a856	\N	{"email_domain": "staging.local"}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.763874+00	\N
4f7e3bf2-7084-4aa6-82b9-4c020c42c1e2	d16118e8-09c3-45f9-becf-772303be6bda	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	signup.accepted	invite	4cbc5a3c-cdd1-4e70-b7ae-b73ac709a856	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.778009+00	\N
956f649b-f4cc-4fdd-92ae-8b6c7e1c4035	d16118e8-09c3-45f9-becf-772303be6bda	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	legal.acceptance	legal_document	private_beta_addendum	\N	{"version": "1.0", "doc_type": "private_beta_addendum", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.807225+00	9942a6dc-1a72-4c91-8624-d9cff1f7532c
9c3e692d-ba82-4f27-8fb8-8ac55f0d0b36	d16118e8-09c3-45f9-becf-772303be6bda	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	legal.acceptance	legal_document	acceptable_use_policy	\N	{"version": "1.0", "doc_type": "acceptable_use_policy", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.809778+00	9942a6dc-1a72-4c91-8624-d9cff1f7532c
2bec2085-b137-4d86-89a4-4ec309384964	d16118e8-09c3-45f9-becf-772303be6bda	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	legal.acceptance	legal_document	terms_of_service	\N	{"version": "1.0", "doc_type": "terms_of_service", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.81225+00	9942a6dc-1a72-4c91-8624-d9cff1f7532c
bafeb3d6-3c1b-41c1-837a-5b2fd0515d61	d16118e8-09c3-45f9-becf-772303be6bda	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	legal.acceptance	legal_document	privacy_notice	\N	{"version": "1.0", "doc_type": "privacy_notice", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.815395+00	9942a6dc-1a72-4c91-8624-d9cff1f7532c
e399b078-f836-47fa-acba-b2cc1b323975	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	billing.subscription.settled	subscription	8726f217-7bdd-4011-b86b-0564dfc84086	\N	{"tier": "trial", "price_id": "price_trial", "test_mode": true}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.852515+00	\N
a2f934b8-72b0-418d-8082-90ec08f55f83	d16118e8-09c3-45f9-becf-772303be6bda	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable", "method": "POST", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:38:04.871624+00	\N
aa795ffe-a0ce-4883-bef8-15a177f9e4b9	d16118e8-09c3-45f9-becf-772303be6bda	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable", "method": "POST", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:38:04.88418+00	\N
0cb374db-1b0f-4ed8-a206-84e4e9f325a9	d16118e8-09c3-45f9-becf-772303be6bda	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable", "method": "POST", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:38:04.896469+00	\N
9dc15215-2d88-4734-91a9-3c1201532b04	d16118e8-09c3-45f9-becf-772303be6bda	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable", "method": "POST", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:38:04.907606+00	\N
c5beea0c-b154-4d9f-a5c9-499d447f8a84	d16118e8-09c3-45f9-becf-772303be6bda	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable", "method": "POST", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:38:04.919978+00	\N
048289c8-377f-49f4-ab34-5763842bccbb	d16118e8-09c3-45f9-becf-772303be6bda	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable", "method": "POST", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:38:04.931482+00	\N
49358c54-4252-4f53-81ba-06abff535f10	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	invite.revoke	invite	4cbc5a3c-cdd1-4e70-b7ae-b73ac709a856	\N	{"reason": "e2e end"}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.952739+00	\N
bef5c6c8-5f77-40c6-a589-f78c5392ab2e	d16118e8-09c3-45f9-becf-772303be6bda	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	billing.subscription.cancel	subscription	8726f217-7bdd-4011-b86b-0564dfc84086	\N	{"reason": "owner cancelled", "test_mode": true}	production	normal	\N	\N	success	\N	2026-09-25 15:38:04.966974+00	\N
a8fb8a05-8838-49b6-9071-4d9e011efc98	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": false, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.020345+00	\N
96af5542-64a3-48cb-b5b2-8ead68587b33	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 401}	production	normal	\N	\N	denied	\N	2026-09-25 15:39:15.197213+00	\N
46eca6e1-8d1f-460d-843b-36e6dae5ebe6	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:39:15.215335+00	\N
73a27cf9-58fa-4294-ab91-85013935ed73	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	session.revoke	session	staging-revoke-1790350755218	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.232414+00	\N
74261173-f142-48bb-8548-1adbebb12e3e	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 401}	production	normal	\N	\N	denied	\N	2026-09-25 15:39:15.237288+00	\N
e0598eaa-5c0e-4ff8-944e-f6e7ea65b666	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	preview.start	preview_session	d5c350dd-f32c-4952-a6ca-81574f408d08	\N	{"reason": "staging smoke", "target_role": null}	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 15:39:15.247822+00	\N
ba01de07-5b2b-439b-8f39-e903fafb5b65	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	preview.end	preview_session	d5c350dd-f32c-4952-a6ca-81574f408d08	\N	\N	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 15:39:15.26483+00	\N
867ce465-0ff7-446c-a195-dc07481af831	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	ea1b3ec9-5441-4dd9-a4b6-428886125db7	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	2acbf0ce-aac1-4429-9f62-96a58336f831	success	\N	2026-09-25 15:39:15.309798+00	\N
5decb36e-6b05-400d-9723-719fae60341a	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	ea1b3ec9-5441-4dd9-a4b6-428886125db7	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.31409+00	\N
3dd3e938-c653-4a73-91b6-f56080de9c73	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	ea1b3ec9-5441-4dd9-a4b6-428886125db7	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	2acbf0ce-aac1-4429-9f62-96a58336f831	success	\N	2026-09-25 15:39:15.326361+00	\N
953fe04d-b916-4987-a657-7e5ee2f1e7eb	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	ea1b3ec9-5441-4dd9-a4b6-428886125db7	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	2acbf0ce-aac1-4429-9f62-96a58336f831	success	\N	2026-09-25 15:39:15.339972+00	\N
0cff437c-ef3f-43ec-8e75-fc3d63552e52	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	ea1b3ec9-5441-4dd9-a4b6-428886125db7	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	2acbf0ce-aac1-4429-9f62-96a58336f831	success	\N	2026-09-25 15:39:15.358653+00	\N
7c5bb7a1-085c-4bd4-ae12-0e17fb8b72e9	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	1e82450b-72a9-436b-b3b2-46a915738f5b	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	c3299161-4bdf-49ec-b711-898ae6287e0b	success	\N	2026-09-25 15:39:15.400029+00	\N
fcbae83a-c25e-463d-acbc-5d1ddfc1a0e7	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	1e82450b-72a9-436b-b3b2-46a915738f5b	\N	{"state": "queued", "job_type": "transient_failure", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.404487+00	\N
b312ea51-4773-45a3-963a-c5d8f592e6c0	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	1e82450b-72a9-436b-b3b2-46a915738f5b	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	c3299161-4bdf-49ec-b711-898ae6287e0b	success	\N	2026-09-25 15:39:15.418942+00	\N
0171dca4-2587-4f37-b0c4-e3b57aa3fd7b	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	1e82450b-72a9-436b-b3b2-46a915738f5b	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	c3299161-4bdf-49ec-b711-898ae6287e0b	success	\N	2026-09-25 15:39:15.436233+00	\N
b0367bcf-ae66-4326-b79b-8da5976a0252	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.retry_wait	job_request	1e82450b-72a9-436b-b3b2-46a915738f5b	{"actor": "worker", "state": "running"}	{"state": "retry_wait", "reason": "retryable transient_error", "correlation_id": null}	production	normal	\N	c3299161-4bdf-49ec-b711-898ae6287e0b	success	\N	2026-09-25 15:39:15.455549+00	\N
a0f17c06-6933-463c-a1d5-33f573b7b554	818d3840-1a16-40b6-9757-9e5a67af68f8	scheduler	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	1e82450b-72a9-436b-b3b2-46a915738f5b	{"actor": "scheduler", "state": "retry_wait"}	{"state": "queued", "reason": "backoff elapsed", "correlation_id": null}	production	normal	\N	c3299161-4bdf-49ec-b711-898ae6287e0b	success	\N	2026-09-25 15:39:15.479261+00	\N
3a1ea099-c3a5-4a27-807d-a92ff79cc606	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	1e82450b-72a9-436b-b3b2-46a915738f5b	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	c3299161-4bdf-49ec-b711-898ae6287e0b	success	\N	2026-09-25 15:39:15.493079+00	\N
4cc07c94-3f65-4c39-a81f-c5c882e738a5	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	1e82450b-72a9-436b-b3b2-46a915738f5b	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	c3299161-4bdf-49ec-b711-898ae6287e0b	success	\N	2026-09-25 15:39:15.508336+00	\N
4cb22185-0232-44d6-95cf-00d98a1e68b9	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	1e82450b-72a9-436b-b3b2-46a915738f5b	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	c3299161-4bdf-49ec-b711-898ae6287e0b	success	\N	2026-09-25 15:39:15.527662+00	\N
4e22c0a8-6d0e-4b25-be4b-08b281928ef7	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.create	job_schedule	919354fc-10e9-42d6-a254-c88d1c47bf15	\N	{"enabled": true, "job_type": "immediate_success"}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.5453+00	\N
cfcc0d10-21ca-46f0-9aa6-a8c7ad150c99	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	72709084-6173-43bf-ac05-71607e3bb043	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T15:39:10.542065+00:00"}	production	normal	\N	0e2e02e8-fde2-4386-b45f-94c21fd920c5	success	\N	2026-09-25 15:39:15.57011+00	2026-09-25T15:39:10.542065+00:00
71da8aad-70b7-4f90-a0f8-68e2d28a8a8f	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	72709084-6173-43bf-ac05-71607e3bb043	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.574524+00	2026-09-25T15:39:10.542065+00:00
66048685-f714-4fa7-b88f-b51438b7cdc1	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	919354fc-10e9-42d6-a254-c88d1c47bf15	\N	{"job_id": "72709084-6173-43bf-ac05-71607e3bb043", "occurrence": "2026-09-25T15:39:10.542065+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.57954+00	\N
49ad1942-35b3-40a7-9014-487dd4cec15f	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	ece8ac3a-1061-486c-a849-7574c872926d	\N	{"job_type": "immediate_success", "idempotent_replay": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.673971+00	staging-req-chain-1
40efa994-8852-4c46-ba95-0ebd37fd6e9e	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	72709084-6173-43bf-ac05-71607e3bb043	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T15:39:10.542065+00:00"}	production	normal	\N	0e2e02e8-fde2-4386-b45f-94c21fd920c5	success	\N	2026-09-25 15:39:15.689717+00	2026-09-25T15:39:10.542065+00:00
39f7cfae-cf1a-458d-8399-1cb58db4e9bc	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	72709084-6173-43bf-ac05-71607e3bb043	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T15:39:10.542065+00:00"}	production	normal	\N	0e2e02e8-fde2-4386-b45f-94c21fd920c5	success	\N	2026-09-25 15:39:15.707015+00	2026-09-25T15:39:10.542065+00:00
f729b532-d3c7-43f5-ac5e-ac38fff7678d	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	72709084-6173-43bf-ac05-71607e3bb043	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T15:39:10.542065+00:00"}	production	normal	\N	0e2e02e8-fde2-4386-b45f-94c21fd920c5	success	\N	2026-09-25 15:39:15.729571+00	2026-09-25T15:39:10.542065+00:00
e9ea4cf0-9f3a-4cca-81b9-947f913cac61	a647b2b4-57a1-4ac0-9ae1-de5e30a866e5	viewer	b93d2fc7-f156-4553-b08c-c91232e68197	\N	\N	legal.acceptance	legal_document	private_beta_addendum	\N	{"version": "1.0", "doc_type": "private_beta_addendum", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.786996+00	\N
cc3b1549-1eea-424a-9214-fda557a7bcc3	a647b2b4-57a1-4ac0-9ae1-de5e30a866e5	viewer	b93d2fc7-f156-4553-b08c-c91232e68197	\N	\N	legal.acceptance	legal_document	acceptable_use_policy	\N	{"version": "1.0", "doc_type": "acceptable_use_policy", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.789384+00	\N
cb3e1793-a827-4767-b8da-0e72b6ff47c7	a647b2b4-57a1-4ac0-9ae1-de5e30a866e5	viewer	b93d2fc7-f156-4553-b08c-c91232e68197	\N	\N	legal.acceptance	legal_document	terms_of_service	\N	{"version": "1.0", "doc_type": "terms_of_service", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.791669+00	\N
36885c97-9a08-44af-8c18-5ea467aa818f	a647b2b4-57a1-4ac0-9ae1-de5e30a866e5	viewer	b93d2fc7-f156-4553-b08c-c91232e68197	\N	\N	legal.acceptance	legal_document	privacy_notice	\N	{"version": "1.0", "doc_type": "privacy_notice", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.79396+00	\N
fb0af3b9-7723-4999-b241-4966b5a9e287	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	2de868d1-6a42-4874-b6c4-08a6f521ee4e	\N	{"job_type": "immediate_success", "idempotent_replay": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.805704+00	\N
b6b39164-0820-4aed-a467-f84eb92f8df8	a647b2b4-57a1-4ac0-9ae1-de5e30a866e5	viewer	b93d2fc7-f156-4553-b08c-c91232e68197	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/usage/summary", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:39:15.825594+00	\N
d5e2a8dc-1bd0-4d5e-887e-4dfe6df14fb0	a647b2b4-57a1-4ac0-9ae1-de5e30a866e5	viewer	b93d2fc7-f156-4553-b08c-c91232e68197	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/providers", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:39:15.834434+00	\N
da3cbc22-d593-4e9d-8006-e6a94df60bb1	a647b2b4-57a1-4ac0-9ae1-de5e30a866e5	viewer	b93d2fc7-f156-4553-b08c-c91232e68197	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable", "method": "POST", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:39:15.843158+00	\N
fed87824-9562-419a-abb9-0e3e52d43b26	a647b2b4-57a1-4ac0-9ae1-de5e30a866e5	viewer	b93d2fc7-f156-4553-b08c-c91232e68197	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable/72709084-6173-43bf-ac05-71607e3bb043", "method": "GET", "status": 404}	production	normal	\N	\N	denied	\N	2026-09-25 15:39:15.853367+00	\N
b13816ab-fbfa-426c-9f79-ec5a4153810e	4862db1a-85f3-49c1-bed2-1def9d383dbe	operator	8f3d00ce-4706-4049-88b1-f080bbb33ffc	\N	\N	legal.acceptance	legal_document	private_beta_addendum	\N	{"version": "1.0", "doc_type": "private_beta_addendum", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.896644+00	e46484e4-90ca-4807-87e2-5c7258aec0f5
a15a54fc-2ef5-4421-aa18-cfc43ab893b3	4862db1a-85f3-49c1-bed2-1def9d383dbe	operator	8f3d00ce-4706-4049-88b1-f080bbb33ffc	\N	\N	legal.acceptance	legal_document	acceptable_use_policy	\N	{"version": "1.0", "doc_type": "acceptable_use_policy", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.899821+00	e46484e4-90ca-4807-87e2-5c7258aec0f5
479d35a4-4fc3-4590-aa12-a307bf3a9751	4862db1a-85f3-49c1-bed2-1def9d383dbe	operator	8f3d00ce-4706-4049-88b1-f080bbb33ffc	\N	\N	legal.acceptance	legal_document	terms_of_service	\N	{"version": "1.0", "doc_type": "terms_of_service", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.902202+00	e46484e4-90ca-4807-87e2-5c7258aec0f5
254e8ec4-7bb7-48ca-920f-ec81911386a6	4862db1a-85f3-49c1-bed2-1def9d383dbe	operator	8f3d00ce-4706-4049-88b1-f080bbb33ffc	\N	\N	legal.acceptance	legal_document	privacy_notice	\N	{"version": "1.0", "doc_type": "privacy_notice", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.90475+00	e46484e4-90ca-4807-87e2-5c7258aec0f5
c6e8dc2d-ae00-43c3-abaa-069fc64a58f2	4862db1a-85f3-49c1-bed2-1def9d383dbe	requestor	8f3d00ce-4706-4049-88b1-f080bbb33ffc	\N	\N	job.state.queued	job_request	0e3f8700-edcb-45c3-b183-ebd57436eb4b	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	c6c9b6c9-6898-467a-81a0-cfdcf7904083	success	\N	2026-09-25 15:39:15.931076+00	\N
bde56acc-790d-426b-a983-5062f0611309	4862db1a-85f3-49c1-bed2-1def9d383dbe	operator	8f3d00ce-4706-4049-88b1-f080bbb33ffc	\N	\N	job.submit	job_request	0e3f8700-edcb-45c3-b183-ebd57436eb4b	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.935549+00	\N
6cfbbb48-2ea6-44c8-bc1e-44f6e97ace31	c46f4c20-58bb-4669-8d5f-1cb18ff0b94a	organization_owner	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	legal.acceptance	legal_document	private_beta_addendum	\N	{"version": "1.0", "doc_type": "private_beta_addendum", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.966891+00	\N
8a1bebe7-b6cd-47c7-a6ff-248a87b8af40	c46f4c20-58bb-4669-8d5f-1cb18ff0b94a	organization_owner	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	legal.acceptance	legal_document	acceptable_use_policy	\N	{"version": "1.0", "doc_type": "acceptable_use_policy", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.96936+00	\N
2b0adcf0-e6a8-4b30-a615-3efbe68f6c55	c46f4c20-58bb-4669-8d5f-1cb18ff0b94a	organization_owner	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	legal.acceptance	legal_document	terms_of_service	\N	{"version": "1.0", "doc_type": "terms_of_service", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.97168+00	\N
d8145bb6-2023-4232-8091-4bc917cdb185	c46f4c20-58bb-4669-8d5f-1cb18ff0b94a	organization_owner	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	legal.acceptance	legal_document	privacy_notice	\N	{"version": "1.0", "doc_type": "privacy_notice", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.974066+00	\N
b706c355-3b70-48a7-be06-ec203bcf9766	c46f4c20-58bb-4669-8d5f-1cb18ff0b94a	\N	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	invite.issue	invite	c0b28893-ddab-419d-9384-e1a08ff5394e	\N	{"email_domain": "staging.local"}	production	normal	\N	\N	success	\N	2026-09-25 15:39:15.988643+00	\N
a067165c-f3d9-4cdb-8284-7e73a46f3f15	b0e01231-2313-441a-9bc8-f12449d3d249	\N	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	signup.accepted	invite	c0b28893-ddab-419d-9384-e1a08ff5394e	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 15:39:16.004095+00	\N
1e8764c7-42c8-44c7-8979-64138c469a36	b0e01231-2313-441a-9bc8-f12449d3d249	organization_owner	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	legal.acceptance	legal_document	private_beta_addendum	\N	{"version": "1.0", "doc_type": "private_beta_addendum", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:16.029819+00	ebca4939-f3ec-474b-b784-88b70424218b
bbc8df95-90d6-4e3b-a812-aad2529d960a	b0e01231-2313-441a-9bc8-f12449d3d249	organization_owner	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	legal.acceptance	legal_document	acceptable_use_policy	\N	{"version": "1.0", "doc_type": "acceptable_use_policy", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:16.032618+00	ebca4939-f3ec-474b-b784-88b70424218b
9308da02-b582-4a73-93c9-2f498766ade0	b0e01231-2313-441a-9bc8-f12449d3d249	organization_owner	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	legal.acceptance	legal_document	terms_of_service	\N	{"version": "1.0", "doc_type": "terms_of_service", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:16.035947+00	ebca4939-f3ec-474b-b784-88b70424218b
81b62a62-333a-450d-898c-acab765262a4	b0e01231-2313-441a-9bc8-f12449d3d249	organization_owner	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	legal.acceptance	legal_document	privacy_notice	\N	{"version": "1.0", "doc_type": "privacy_notice", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:16.038628+00	ebca4939-f3ec-474b-b784-88b70424218b
16f21a5c-50a1-471b-a134-8e365fa8295b	b0e01231-2313-441a-9bc8-f12449d3d249	requestor	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	job.state.queued	job_request	d7933dde-59a3-4152-99e1-15461565de3e	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	8fa27db2-9fee-4d10-b980-03a23348cf21	success	\N	2026-09-25 15:39:16.100606+00	\N
8621560e-a042-4a8e-91f2-5fb1bfe673ad	b0e01231-2313-441a-9bc8-f12449d3d249	organization_owner	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	job.submit	job_request	d7933dde-59a3-4152-99e1-15461565de3e	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:16.104959+00	\N
2670571b-06b5-4920-86ff-9b3804ed8025	b0e01231-2313-441a-9bc8-f12449d3d249	requestor	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	job.state.queued	job_request	d4b6deac-d10f-4d17-8d19-2ad319d1c5f4	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	df883f51-cf48-4022-b43d-4657cb645e83	success	\N	2026-09-25 15:39:16.130243+00	\N
0bebeca0-3b7f-4f2c-b83a-83c0246f65a7	b0e01231-2313-441a-9bc8-f12449d3d249	organization_owner	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	job.submit	job_request	d4b6deac-d10f-4d17-8d19-2ad319d1c5f4	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:16.1346+00	\N
75f9c9ac-c1f0-4948-bab4-e6fc5f9bcdd2	b0e01231-2313-441a-9bc8-f12449d3d249	requestor	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	job.state.queued	job_request	8378b1d5-a70a-4e7c-b553-61e7ab149b81	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	91079a87-d676-46e2-8be4-fec56f582d9d	success	\N	2026-09-25 15:39:16.160478+00	\N
f3c5f7c4-b25b-4b9d-8658-c256d46e5751	b0e01231-2313-441a-9bc8-f12449d3d249	organization_owner	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	job.submit	job_request	8378b1d5-a70a-4e7c-b553-61e7ab149b81	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:16.165073+00	\N
a3a186c1-8c7a-4672-9850-91e0324a286e	b0e01231-2313-441a-9bc8-f12449d3d249	requestor	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	job.state.queued	job_request	2af0ccf8-5e8d-47ec-aa8e-9c76a1229f07	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	09dd775d-08f5-461e-99a0-50e3c8c94e95	success	\N	2026-09-25 15:39:16.190829+00	\N
370395ec-4e61-455e-8edb-9832d5bbe306	b0e01231-2313-441a-9bc8-f12449d3d249	organization_owner	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	job.submit	job_request	2af0ccf8-5e8d-47ec-aa8e-9c76a1229f07	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:16.195376+00	\N
6a7769ab-c6a0-4291-86ac-6541df54d9af	b0e01231-2313-441a-9bc8-f12449d3d249	requestor	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	job.state.queued	job_request	5df93f57-0670-43cf-8573-ef4057dfc5ac	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	ef0c7cdd-9bca-47a5-b120-339c63d1c67b	success	\N	2026-09-25 15:39:16.220578+00	\N
0e48f19b-a3b5-48c9-9ee2-3b8285436d28	b0e01231-2313-441a-9bc8-f12449d3d249	organization_owner	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	job.submit	job_request	5df93f57-0670-43cf-8573-ef4057dfc5ac	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:16.224866+00	\N
88d04985-5cf0-4bdc-a7f1-f31a654d78a8	b0e01231-2313-441a-9bc8-f12449d3d249	requestor	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	job.state.queued	job_request	a4b9c007-7508-4e67-ba66-34dcb83afdbc	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	922f1fac-f869-4980-99c1-cb61b74c1d0b	success	\N	2026-09-25 15:39:16.249844+00	\N
562d7a72-dc07-47a3-993c-29a701fe72a0	b0e01231-2313-441a-9bc8-f12449d3d249	organization_owner	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	job.submit	job_request	a4b9c007-7508-4e67-ba66-34dcb83afdbc	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:16.254427+00	\N
6318525c-4485-4b0a-8791-a5fac5954ae7	c46f4c20-58bb-4669-8d5f-1cb18ff0b94a	\N	993df0b6-4bdb-43ea-9e50-715141765180	\N	\N	invite.revoke	invite	c0b28893-ddab-419d-9384-e1a08ff5394e	\N	{"reason": "e2e end"}	production	normal	\N	\N	success	\N	2026-09-25 15:39:16.266307+00	\N
4ddb8de0-ca06-4fea-9edb-7cc93cdd2044	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": false, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:49.903606+00	\N
d570c683-ceec-48be-b19e-30cd1d39b4e9	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 401}	production	normal	\N	\N	denied	\N	2026-09-25 15:39:50.095632+00	\N
0a981367-4f5d-43ec-a92a-b04e835491da	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:39:50.118269+00	\N
db6ea4a6-2431-418d-9a6e-e8e07b1711eb	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	session.revoke	session	staging-revoke-1790350790147	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.161918+00	\N
b74b8d1a-4906-40f3-ba84-581c3f011f60	\N	\N	\N	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/me", "method": "GET", "status": 401}	production	normal	\N	\N	denied	\N	2026-09-25 15:39:50.16687+00	\N
cf9cdea5-519e-4505-9526-ad34b2b24736	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	preview.start	preview_session	b20bbfef-123b-4c31-bf62-153d5345caad	\N	{"reason": "staging smoke", "target_role": null}	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 15:39:50.177904+00	\N
c7fab2a0-4545-466c-8c2c-55d6e28f5132	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	preview.end	preview_session	b20bbfef-123b-4c31-bf62-153d5345caad	\N	\N	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 15:39:50.194515+00	\N
c061d02d-b79b-4d70-ab7e-9aaa90133a26	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	00fb6a50-57ec-4e8d-9a22-94b43b6669cb	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	0d700548-3a64-41b3-9b53-1c19625e9229	success	\N	2026-09-25 15:39:50.24144+00	\N
46f87a45-3f60-46da-aede-b1090b4b66b8	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	00fb6a50-57ec-4e8d-9a22-94b43b6669cb	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.246175+00	\N
0b0d9452-7119-4678-96af-294204d65745	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	00fb6a50-57ec-4e8d-9a22-94b43b6669cb	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	0d700548-3a64-41b3-9b53-1c19625e9229	success	\N	2026-09-25 15:39:50.259789+00	\N
cd227c5d-c51e-4c29-86ec-e242cafc500d	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	00fb6a50-57ec-4e8d-9a22-94b43b6669cb	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	0d700548-3a64-41b3-9b53-1c19625e9229	success	\N	2026-09-25 15:39:50.275246+00	\N
42337111-9fd0-4f04-b422-40e1e6d127ba	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	00fb6a50-57ec-4e8d-9a22-94b43b6669cb	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	0d700548-3a64-41b3-9b53-1c19625e9229	success	\N	2026-09-25 15:39:50.324602+00	\N
f80a9ed3-92ba-4418-845a-80018db0c13c	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	c3eb9278-49f7-4c93-8f8e-a94559908fad	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	c604cf51-ac89-4bdc-9ea2-746cc1adb608	success	\N	2026-09-25 15:39:50.361976+00	\N
529f4370-028b-48a4-ae58-2f61af0f739f	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	c3eb9278-49f7-4c93-8f8e-a94559908fad	\N	{"state": "queued", "job_type": "transient_failure", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.36664+00	\N
fd79c625-92bc-4f11-be71-676ceb655bc9	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	c3eb9278-49f7-4c93-8f8e-a94559908fad	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	c604cf51-ac89-4bdc-9ea2-746cc1adb608	success	\N	2026-09-25 15:39:50.380689+00	\N
24f4b0b7-f05a-43ef-b378-23def2f6d7ff	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	c3eb9278-49f7-4c93-8f8e-a94559908fad	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	c604cf51-ac89-4bdc-9ea2-746cc1adb608	success	\N	2026-09-25 15:39:50.394715+00	\N
9d4b2e3e-8d7e-47fa-bc66-df2c7aa3116d	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.retry_wait	job_request	c3eb9278-49f7-4c93-8f8e-a94559908fad	{"actor": "worker", "state": "running"}	{"state": "retry_wait", "reason": "retryable transient_error", "correlation_id": null}	production	normal	\N	c604cf51-ac89-4bdc-9ea2-746cc1adb608	success	\N	2026-09-25 15:39:50.410856+00	\N
74ec9bb2-22bc-4dac-9956-63cbb7c711e6	818d3840-1a16-40b6-9757-9e5a67af68f8	scheduler	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	c3eb9278-49f7-4c93-8f8e-a94559908fad	{"actor": "scheduler", "state": "retry_wait"}	{"state": "queued", "reason": "backoff elapsed", "correlation_id": null}	production	normal	\N	c604cf51-ac89-4bdc-9ea2-746cc1adb608	success	\N	2026-09-25 15:39:50.432191+00	\N
6142ee87-bfb8-43f9-a9ab-aa7435d482fa	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	organization_owner	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	job.submit	job_request	830cdfcb-df3b-4644-808e-326f472376bb	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:51.082198+00	\N
a5149f97-3c9f-4b92-a961-4ba73b65bec2	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	c3eb9278-49f7-4c93-8f8e-a94559908fad	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	c604cf51-ac89-4bdc-9ea2-746cc1adb608	success	\N	2026-09-25 15:39:50.444089+00	\N
cc73f1ec-9f6c-473c-a5d6-50b22a1740fe	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	c3eb9278-49f7-4c93-8f8e-a94559908fad	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	c604cf51-ac89-4bdc-9ea2-746cc1adb608	success	\N	2026-09-25 15:39:50.457774+00	\N
fd3fa6dd-4d2c-4cb1-8340-22f2d45d6122	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	c3eb9278-49f7-4c93-8f8e-a94559908fad	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	c604cf51-ac89-4bdc-9ea2-746cc1adb608	success	\N	2026-09-25 15:39:50.475921+00	\N
32668f26-31af-4c6b-9be1-0b19193f2576	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.create	job_schedule	81728559-dc82-414e-aa1e-e737ebf2818a	\N	{"enabled": true, "job_type": "immediate_success"}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.491838+00	\N
c43670b4-771c-4cdb-b15f-0736e3784e2e	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	4bcb49ea-f1e8-4f40-92ae-74d72dd2a783	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T15:39:45.488996+00:00"}	production	normal	\N	9077902e-98c6-4ac9-b0be-ca7a1a32e924	success	\N	2026-09-25 15:39:50.515611+00	2026-09-25T15:39:45.488996+00:00
85a0fe0c-9d9e-49e1-9dd5-9e179508589b	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	4bcb49ea-f1e8-4f40-92ae-74d72dd2a783	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.519758+00	2026-09-25T15:39:45.488996+00:00
7c997749-04eb-40ea-8c5f-707ab5755df5	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	81728559-dc82-414e-aa1e-e737ebf2818a	\N	{"job_id": "4bcb49ea-f1e8-4f40-92ae-74d72dd2a783", "occurrence": "2026-09-25T15:39:45.488996+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.524926+00	\N
8a6eba44-b0b0-4745-a8f8-a0d82fb416bd	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	ece8ac3a-1061-486c-a849-7574c872926d	\N	{"job_type": "immediate_success", "idempotent_replay": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.610987+00	staging-req-chain-1
95a2853c-fc8f-469f-8476-1ffdc2ef6de2	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	4bcb49ea-f1e8-4f40-92ae-74d72dd2a783	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T15:39:45.488996+00:00"}	production	normal	\N	9077902e-98c6-4ac9-b0be-ca7a1a32e924	success	\N	2026-09-25 15:39:50.625407+00	2026-09-25T15:39:45.488996+00:00
57871436-1573-41b4-bf82-bfbea73cb9f6	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	4bcb49ea-f1e8-4f40-92ae-74d72dd2a783	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T15:39:45.488996+00:00"}	production	normal	\N	9077902e-98c6-4ac9-b0be-ca7a1a32e924	success	\N	2026-09-25 15:39:50.642259+00	2026-09-25T15:39:45.488996+00:00
534c2c04-3e4b-424a-b09f-2884fbbf7966	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	4bcb49ea-f1e8-4f40-92ae-74d72dd2a783	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T15:39:45.488996+00:00"}	production	normal	\N	9077902e-98c6-4ac9-b0be-ca7a1a32e924	success	\N	2026-09-25 15:39:50.66021+00	2026-09-25T15:39:45.488996+00:00
7a571ef8-9cbe-4560-87c3-ab22f0722710	ab799989-4af7-44f5-8fe8-c85147cc9d5d	viewer	5c20de09-2a06-431d-baf3-ac644f4fec9d	\N	\N	legal.acceptance	legal_document	private_beta_addendum	\N	{"version": "1.0", "doc_type": "private_beta_addendum", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.71843+00	\N
11545109-e724-4e97-8b90-b9aebcae506c	ab799989-4af7-44f5-8fe8-c85147cc9d5d	viewer	5c20de09-2a06-431d-baf3-ac644f4fec9d	\N	\N	legal.acceptance	legal_document	acceptable_use_policy	\N	{"version": "1.0", "doc_type": "acceptable_use_policy", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.720915+00	\N
6c4dc06b-fb90-4a0b-b9de-481275ceeb50	ab799989-4af7-44f5-8fe8-c85147cc9d5d	viewer	5c20de09-2a06-431d-baf3-ac644f4fec9d	\N	\N	legal.acceptance	legal_document	terms_of_service	\N	{"version": "1.0", "doc_type": "terms_of_service", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.724409+00	\N
f51d0ac2-ddbf-4834-929e-718d230e9f84	ab799989-4af7-44f5-8fe8-c85147cc9d5d	viewer	5c20de09-2a06-431d-baf3-ac644f4fec9d	\N	\N	legal.acceptance	legal_document	privacy_notice	\N	{"version": "1.0", "doc_type": "privacy_notice", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.727173+00	\N
f8b90c3e-c936-41d2-ac11-f12203edbb44	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	2de868d1-6a42-4874-b6c4-08a6f521ee4e	\N	{"job_type": "immediate_success", "idempotent_replay": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.7379+00	\N
79e20ecb-22f2-411a-a04d-c54fb8532321	ab799989-4af7-44f5-8fe8-c85147cc9d5d	viewer	5c20de09-2a06-431d-baf3-ac644f4fec9d	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/usage/summary", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:39:50.755501+00	\N
5e8b6f2a-6694-4023-a1ad-296812170082	ab799989-4af7-44f5-8fe8-c85147cc9d5d	viewer	5c20de09-2a06-431d-baf3-ac644f4fec9d	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/providers", "method": "GET", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:39:50.763297+00	\N
1b6d20b5-b355-4598-91b3-7c182e59a1f7	ab799989-4af7-44f5-8fe8-c85147cc9d5d	viewer	5c20de09-2a06-431d-baf3-ac644f4fec9d	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable", "method": "POST", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:39:50.771563+00	\N
e27f391a-bc14-43f9-9fcc-1a86c3b596fe	ab799989-4af7-44f5-8fe8-c85147cc9d5d	viewer	5c20de09-2a06-431d-baf3-ac644f4fec9d	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable/c3eb9278-49f7-4c93-8f8e-a94559908fad", "method": "GET", "status": 404}	production	normal	\N	\N	denied	\N	2026-09-25 15:39:50.783082+00	\N
2c3e952f-379b-403e-af8b-4e4291e00fe2	99d0d2b9-2ad9-4e96-bf2f-d0e2d89a7ff5	operator	0d9868c5-1b93-4b0c-b8d6-8a97cb21594e	\N	\N	legal.acceptance	legal_document	private_beta_addendum	\N	{"version": "1.0", "doc_type": "private_beta_addendum", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.825643+00	1b85e5a8-d475-40a3-805e-2d1d27528157
5e0a278e-e0ed-4b8b-a3f3-55e1a58f80d4	99d0d2b9-2ad9-4e96-bf2f-d0e2d89a7ff5	operator	0d9868c5-1b93-4b0c-b8d6-8a97cb21594e	\N	\N	legal.acceptance	legal_document	acceptable_use_policy	\N	{"version": "1.0", "doc_type": "acceptable_use_policy", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.828019+00	1b85e5a8-d475-40a3-805e-2d1d27528157
bc53d781-0371-4548-9d3c-d0c247da72e9	99d0d2b9-2ad9-4e96-bf2f-d0e2d89a7ff5	operator	0d9868c5-1b93-4b0c-b8d6-8a97cb21594e	\N	\N	legal.acceptance	legal_document	terms_of_service	\N	{"version": "1.0", "doc_type": "terms_of_service", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.830779+00	1b85e5a8-d475-40a3-805e-2d1d27528157
6da00f71-23b1-4a88-8435-994b3d8bcec9	99d0d2b9-2ad9-4e96-bf2f-d0e2d89a7ff5	operator	0d9868c5-1b93-4b0c-b8d6-8a97cb21594e	\N	\N	legal.acceptance	legal_document	privacy_notice	\N	{"version": "1.0", "doc_type": "privacy_notice", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.833242+00	1b85e5a8-d475-40a3-805e-2d1d27528157
b42473a7-b140-4880-ad0a-3587ce007bf4	99d0d2b9-2ad9-4e96-bf2f-d0e2d89a7ff5	requestor	0d9868c5-1b93-4b0c-b8d6-8a97cb21594e	\N	\N	job.state.queued	job_request	a2dd52f7-eb7d-4ea2-9a53-25a8c12fabc7	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	67cf4e56-2251-4762-a408-86f6cd6dce0b	success	\N	2026-09-25 15:39:50.859023+00	\N
8e2ca277-b214-419a-89b7-28f199ca8174	99d0d2b9-2ad9-4e96-bf2f-d0e2d89a7ff5	operator	0d9868c5-1b93-4b0c-b8d6-8a97cb21594e	\N	\N	job.submit	job_request	a2dd52f7-eb7d-4ea2-9a53-25a8c12fabc7	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.863169+00	\N
ac6fe110-c750-4bbd-b18d-fa92acf3a01d	16d2ec3e-5c6c-4f5e-ae69-a9a3c058b69e	organization_owner	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	legal.acceptance	legal_document	private_beta_addendum	\N	{"version": "1.0", "doc_type": "private_beta_addendum", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.889709+00	\N
44ae2475-c89f-476b-8b57-1dfc73922840	16d2ec3e-5c6c-4f5e-ae69-a9a3c058b69e	organization_owner	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	legal.acceptance	legal_document	acceptable_use_policy	\N	{"version": "1.0", "doc_type": "acceptable_use_policy", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.892086+00	\N
0aaabc84-db73-4eb4-b44f-164d86b23150	16d2ec3e-5c6c-4f5e-ae69-a9a3c058b69e	organization_owner	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	legal.acceptance	legal_document	terms_of_service	\N	{"version": "1.0", "doc_type": "terms_of_service", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.894432+00	\N
4cfa43e0-262d-42de-a999-53f069361913	16d2ec3e-5c6c-4f5e-ae69-a9a3c058b69e	organization_owner	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	legal.acceptance	legal_document	privacy_notice	\N	{"version": "1.0", "doc_type": "privacy_notice", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.896801+00	\N
226585ab-6a07-47f7-b8ae-e847b2a65ca5	16d2ec3e-5c6c-4f5e-ae69-a9a3c058b69e	\N	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	invite.issue	invite	4bfa7ff4-ef19-4819-9f87-313aa629a31d	\N	{"email_domain": "staging.local"}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.910695+00	\N
259216e6-d301-49a9-a33d-fd2214e6cfb5	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	\N	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	signup.accepted	invite	4bfa7ff4-ef19-4819-9f87-313aa629a31d	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.924759+00	\N
98a1efa3-2ad6-4e1f-8afb-397c2207e962	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	organization_owner	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	legal.acceptance	legal_document	private_beta_addendum	\N	{"version": "1.0", "doc_type": "private_beta_addendum", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.950079+00	a3c4943b-5daa-4e26-ae22-3730d27d3e25
dfdf5f3c-12ae-4e7d-94f0-7c93cb110620	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	organization_owner	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	legal.acceptance	legal_document	acceptable_use_policy	\N	{"version": "1.0", "doc_type": "acceptable_use_policy", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.952435+00	a3c4943b-5daa-4e26-ae22-3730d27d3e25
f8fa63f7-0e5d-4f86-a9d4-79b6a6cea7c1	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	organization_owner	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	legal.acceptance	legal_document	terms_of_service	\N	{"version": "1.0", "doc_type": "terms_of_service", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.954779+00	a3c4943b-5daa-4e26-ae22-3730d27d3e25
b928fc2e-2a90-424a-9c70-92d72bca73b5	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	organization_owner	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	legal.acceptance	legal_document	privacy_notice	\N	{"version": "1.0", "doc_type": "privacy_notice", "age_18_plus": true, "ip_handling": "not_stored", "business_use": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.957179+00	a3c4943b-5daa-4e26-ae22-3730d27d3e25
6365d338-def2-450d-83f9-95fcc9acb1fa	\N	\N	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	billing.subscription.settled	subscription	8a9aa4cd-19ce-4e28-a34f-4baf005a92dc	\N	{"tier": "trial", "price_id": "price_trial", "test_mode": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:50.990167+00	\N
7840ed3f-4bfa-4ed9-a04d-03d0f9a21e07	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	requestor	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	job.state.queued	job_request	6828b198-0ca2-4889-97ee-bdc5e0ad15c8	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	5544e37b-5705-44bd-b1b6-c7de3e219c7c	success	\N	2026-09-25 15:39:51.018997+00	\N
10752186-8750-4cb7-9b94-29a3d6d86bb2	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	organization_owner	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	job.submit	job_request	6828b198-0ca2-4889-97ee-bdc5e0ad15c8	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:51.023281+00	\N
951715f9-f437-459d-aa9b-b34a0b821753	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	requestor	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	job.state.queued	job_request	6ffc2dab-063d-44af-a3e7-215eaad84634	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	e5d28f54-0ded-42cb-aabe-70d054a67618	success	\N	2026-09-25 15:39:51.049375+00	\N
2b9b8460-f715-4cd0-a8c1-2257dbd775ff	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	organization_owner	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	job.submit	job_request	6ffc2dab-063d-44af-a3e7-215eaad84634	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:51.053603+00	\N
562bf24c-ae4f-4b14-9c82-7873fce984c2	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	requestor	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	job.state.queued	job_request	830cdfcb-df3b-4644-808e-326f472376bb	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	9e454c72-e784-4e01-ace2-e69001e04681	success	\N	2026-09-25 15:39:51.077931+00	\N
00a4d788-f7d2-4dcd-ab4a-a0d3bc8e4251	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	requestor	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	job.state.queued	job_request	11f34eb0-bf3a-4d8a-9156-9746dab1755e	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	1a02805b-9eee-4298-9ac0-ad3ecfa8ab99	success	\N	2026-09-25 15:39:51.106369+00	\N
4e17403f-c9f1-43fc-b96c-727423665396	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	organization_owner	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	job.submit	job_request	11f34eb0-bf3a-4d8a-9156-9746dab1755e	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:51.110605+00	\N
104e0d9d-1448-42c5-9078-6a757cb51f37	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	requestor	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	job.state.queued	job_request	93ae110c-924a-4a5f-9db0-8d7b50e3c135	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	30fac96c-c35a-4b90-a5ed-dcd70cb264d2	success	\N	2026-09-25 15:39:51.135038+00	\N
650af4c7-86da-465a-99d2-dea3ef3c5784	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	organization_owner	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	job.submit	job_request	93ae110c-924a-4a5f-9db0-8d7b50e3c135	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 15:39:51.139241+00	\N
559bebdd-2e72-413f-ab78-dbba91dacad9	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	organization_owner	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	authz.denied	api	\N	\N	{"code": null, "path": "/api/v1/foundation/jobs-durable", "method": "POST", "status": 403}	production	normal	\N	\N	denied	\N	2026-09-25 15:39:51.151157+00	\N
22a53d3f-aa33-42f4-9e4d-689ab902f21b	16d2ec3e-5c6c-4f5e-ae69-a9a3c058b69e	\N	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	invite.revoke	invite	4bfa7ff4-ef19-4819-9f87-313aa629a31d	\N	{"reason": "e2e end"}	production	normal	\N	\N	success	\N	2026-09-25 15:39:51.161721+00	\N
76c21f70-7bd4-4d05-b4b1-55f327334c47	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	\N	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	\N	billing.subscription.cancel	subscription	8a9aa4cd-19ce-4e28-a34f-4baf005a92dc	\N	{"reason": "owner cancelled", "test_mode": true}	production	normal	\N	\N	success	\N	2026-09-25 15:39:51.175952+00	\N
\.


--
-- Data for Name: billing_customers; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.billing_customers (id, organization_id, processor, processor_customer_id, created_at, updated_at) FROM stdin;
dc4cea49-2b69-4252-bd97-98eb732a8e6a	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	test	cus_st	2026-09-25 15:38:04.838613+00	2026-09-25 15:38:04.838614+00
bb921d2e-dc6d-4f6c-8fd5-5a73c38a0da8	993df0b6-4bdb-43ea-9e50-715141765180	test	cus_st	2026-09-25 15:39:16.061852+00	2026-09-25 15:39:16.061853+00
55e92d35-c025-46ee-a7d9-2a674cf8601c	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	test	cus_1790350790868	2026-09-25 15:39:50.977961+00	2026-09-25 15:39:50.977962+00
\.


--
-- Data for Name: billing_events; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.billing_events (id, processor_event_id, event_type, payload_hash, status, processed_at, created_at) FROM stdin;
2a4f8a8c-f554-4bde-a367-5e3bb429f64f	evt_staging_1790350684831	checkout.session.completed	7929c61fa6e3c9dc8483e9ff69602d1f81a260d5a76c1a05eea0849d7fb1d019	processed	2026-09-25 15:38:04.834872+00	2026-09-25 15:38:04.834886+00
dcb5204c-333f-44fb-9ab9-7d6895d6eda1	evt_staging_1790350756055	checkout.session.completed	cc2dc7657781b966cf286f1d439765a4c0670a99f2fb941b49f1257db239e5b2	failed	2026-09-25 15:39:16.05778+00	2026-09-25 15:39:16.057794+00
8050c6a9-32d2-4a4c-8ccf-8c77e5cb03f7	evt_staging_1790350790868	checkout.session.completed	a07470293f5388a21f5f5186a38bf22cd3b2ace70c7170e75c112d4105d8f46b	processed	2026-09-25 15:39:50.974419+00	2026-09-25 15:39:50.974431+00
\.


--
-- Data for Name: catalog_products; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.catalog_products (id, marketplace_id, asin, brand, canonical_title, pack_config_id, variation_family_id, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: checkout_sessions; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.checkout_sessions (id, organization_id, price_id, tier, status, expires_at, created_at) FROM stdin;
f0f436b7-dfc9-4c8d-9a49-9942d183aa04	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	price_trial	trial	completed	2026-09-25 17:38:04.825316+00	2026-09-25 15:38:04.825333+00
09f5120a-6105-4296-8041-8e09e8ca6e97	993df0b6-4bdb-43ea-9e50-715141765180	price_trial	trial	open	2026-09-25 17:39:16.048622+00	2026-09-25 15:39:16.048636+00
92cf443e-9893-476c-ab8b-eca6d309c0e8	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	price_trial	trial	completed	2026-09-25 17:39:50.966317+00	2026-09-25 15:39:50.966332+00
\.


--
-- Data for Name: identity_conflicts; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.identity_conflicts (id, conflict_type, candidate_id, product_id, detail, created_at) FROM stdin;
\.


--
-- Data for Name: import_batches; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.import_batches (id, organization_id, source_file_id, status, submitted_by, submitted_at, started_at, completed_at, summary, created_at) FROM stdin;
7b10eb3c-df22-4bbc-99a9-b6495ee08aed	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	11378e2b-7222-4ed5-9a11-fe7c184d955d	completed	818d3840-1a16-40b6-9757-9e5a67af68f8	2026-09-25 12:47:41.420544+00	2026-09-25 12:47:41.420545+00	2026-09-25 12:47:41.492008+00	{"via_job": false, "accepted_rows": 4, "rejected_rows": 1, "keywords_created": 4, "overlap_detected": []}	2026-09-25 12:47:41.420559+00
\.


--
-- Data for Name: invites; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.invites (id, organization_id, invite_code, email, role, status, created_by, expires_at, used_at, created_at) FROM stdin;
aeb2cd0d-f153-4631-8034-6ca078234668	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	44763271dc5b4618	e2e-1790350652335@staging.local	organization_owner	used	818d3840-1a16-40b6-9757-9e5a67af68f8	2026-09-28 15:37:32.34206+00	2026-09-25 15:37:32.357139+00	2026-09-25 15:37:32.342071+00
4cbc5a3c-cdd1-4e70-b7ae-b73ac709a856	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	fb6e7f2629ef4b38	e2e-1790350684754@staging.local	organization_owner	revoked	818d3840-1a16-40b6-9757-9e5a67af68f8	2026-09-28 15:38:04.761071+00	2026-09-25 15:38:04.77633+00	2026-09-25 15:38:04.761083+00
c0b28893-ddab-419d-9384-e1a08ff5394e	993df0b6-4bdb-43ea-9e50-715141765180	da60111c166e42cd	cust-1790350755976@staging.local	organization_owner	revoked	c46f4c20-58bb-4669-8d5f-1cb18ff0b94a	2026-09-28 15:39:15.986063+00	2026-09-25 15:39:16.001812+00	2026-09-25 15:39:15.986074+00
4bfa7ff4-ef19-4819-9f87-313aa629a31d	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	ca08047cb245430d	cust-1790350790868@staging.local	organization_owner	revoked	16d2ec3e-5c6c-4f5e-ae69-a9a3c058b69e	2026-09-28 15:39:50.908032+00	2026-09-25 15:39:50.923125+00	2026-09-25 15:39:50.908043+00
\.


--
-- Data for Name: job_requests; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.job_requests (id, organization_id, user_id, service, scope_type, scope_id, data_types, provider_policy, max_estimated_cost, currency, environment, idempotency_key, requires_approval, reason, priority, created_at, state, job_type, payload, payload_schema_version, approval_id, provider_class, budget_class, estimated_cost, parent_job_id, correlation_id, provenance) FROM stdin;
bb7b2f11-44e3-44ca-8749-c6a56ee4051d	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:a25e0083-a2f2-4347-8cc3-297c6b6c3bc7:2026-09-25T12:47:36.370345+00:00	f	scheduled occurrence 2026-09-25T12:47:36.370345+00:00	5	2026-09-25 12:47:41.384809+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T12:47:36.370345+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
2d56906f-32ab-438b-a817-f8baef2559f0	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 12:47:41.112463+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
04619a31-fada-4f30-8428-e85428a36d62	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:40b37ae5-1596-4a99-8859-76e7c022769f:2026-09-25T13:42:35.292807+00:00	f	scheduled occurrence 2026-09-25T13:42:35.292807+00:00	5	2026-09-25 13:42:40.306877+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T13:42:35.292807+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
3cee773e-9b1c-484f-8538-4bc9d37773d5	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 12:48:05.064202+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
6ce89210-9d7b-4ef2-a460-7936e37861e9	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 13:43:27.925086+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
a9ee27a7-5545-4d87-a365-1474d10a102b	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:6415cb76-6249-46ad-9649-30d1025ba72c:2026-09-25T12:48:00.349508+00:00	f	scheduled occurrence 2026-09-25T12:48:00.349508+00:00	5	2026-09-25 12:48:05.361028+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T12:48:00.349508+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
cfaf79d9-8e96-4764-a652-19f2f2179004	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 13:42:57.157944+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
1faed168-4681-4d21-9407-62ac9f955cda	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 12:47:41.214009+00	succeeded	transient_failure	{"succeed_on_attempt": 2}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
dee8ad4e-8fe6-40e3-885f-d83b287d400d	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 13:42:40.150963+00	succeeded	transient_failure	{"succeed_on_attempt": 2}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
cc39a661-801a-42f2-9ccc-b0ef2f10137e	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 13:42:40.004318+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
95d4a73e-2173-489d-ab2c-9857472049de	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 12:48:05.202022+00	succeeded	transient_failure	{"succeed_on_attempt": 2}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
74e79cff-759d-4806-b22c-c13f230ff015	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:eb43ac8b-9092-41cd-916e-7029f677874d:2026-09-25T13:42:52.427134+00:00	f	scheduled occurrence 2026-09-25T13:42:52.427134+00:00	5	2026-09-25 13:42:57.439807+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T13:42:52.427134+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
81780c14-5eee-4ff2-ae7f-1ac52fe951f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 13:42:57.287842+00	succeeded	transient_failure	{"succeed_on_attempt": 2}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
ece8ac3a-1061-486c-a849-7574c872926d	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	staging-fin-chain	f	\N	5	2026-09-25 13:42:57.545844+00	succeeded	immediate_success	{"chain": true}	1.0	\N	local	free	0.00	\N	staging-req-chain-1	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
dde1681c-6f4e-4219-97c2-06d1154c7067	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 13:43:28.010414+00	succeeded	transient_failure	{"succeed_on_attempt": 2}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
947d35bd-7f5e-4967-800c-e78b630cd423	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:6c5ed8fa-7912-4a20-8cc0-952cd2522db7:2026-09-25T13:43:23.199997+00:00	f	scheduled occurrence 2026-09-25T13:43:23.199997+00:00	5	2026-09-25 13:43:28.215671+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T13:43:23.199997+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
40a0cbf9-f619-4bb5-a7eb-5cd23cf9dee1	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 13:43:44.005273+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
ecf21bd2-46ad-402b-9329-8c5cae2291e9	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 13:43:44.125972+00	succeeded	transient_failure	{"succeed_on_attempt": 2}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
8368c245-aeb2-4758-b4c8-ba91d8aec34e	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:6c5ed8fa-7912-4a20-8cc0-952cd2522db7:2026-09-25T14:43:23.199997+00:00	f	scheduled occurrence 2026-09-25T14:43:23.199997+00:00	5	2026-09-25 14:51:12.091609+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T14:43:23.199997+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
c9ed2300-a06c-420f-b8fa-b45f0bd28d6b	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:8615ca91-de1c-49ea-85ea-74bede8ae9b8:2026-09-25T13:43:39.275532+00:00	f	scheduled occurrence 2026-09-25T13:43:39.275532+00:00	5	2026-09-25 13:43:44.288155+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T13:43:39.275532+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
a9c8bbb2-aded-4aaa-abaa-3ff70acbee4f	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:9e1827ad-dcba-457c-bc05-5168a0f220c8:2026-09-25T14:11:38.982073+00:00	f	scheduled occurrence 2026-09-25T14:11:38.982073+00:00	5	2026-09-25 14:11:44.013679+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T14:11:38.982073+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
de0a429b-9bcf-4d1d-9198-e1727b230d19	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 14:11:43.755384+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
d1b04528-b5f3-4cd7-a5d8-6534f355e04b	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:a25e0083-a2f2-4347-8cc3-297c6b6c3bc7:2026-09-25T14:47:36.370345+00:00	f	scheduled occurrence 2026-09-25T14:47:36.370345+00:00	5	2026-09-25 14:51:12.157109+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T14:47:36.370345+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
f0a2b5a5-b0d5-4316-8cd4-1e095e241060	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:71f8100f-4b51-4cca-8006-1c767079361e:2026-09-25T14:51:07.007024+00:00	f	scheduled occurrence 2026-09-25T14:51:07.007024+00:00	5	2026-09-25 14:51:12.220747+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T14:51:07.007024+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
2de868d1-6a42-4874-b6c4-08a6f521ee4e	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	staging-authz-owner	f	\N	5	2026-09-25 14:11:44.203159+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
590d00ff-754c-428e-bec4-dc642314b8d1	1cd446b8-a2b4-43d9-8adb-869d5e854ffc	8809ba90-55dd-48d0-a895-665fc5872741	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 14:51:12.85883+00	queued	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "8809ba90-55dd-48d0-a895-665fc5872741"}
d942173e-b6cf-4f51-a3d3-996f6f083813	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 14:11:43.844368+00	succeeded	transient_failure	{"succeed_on_attempt": 2}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
33a7e677-b29a-4895-87f4-1a8b43a1e374	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 14:51:11.866743+00	succeeded	transient_failure	{"succeed_on_attempt": 2}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
a83672ad-6e70-4814-bd20-a28b34c34421	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 14:51:11.718316+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
df75213d-9b26-4a9f-bd32-4cf32de0e372	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:40b37ae5-1596-4a99-8859-76e7c022769f:2026-09-25T14:42:35.292807+00:00	f	scheduled occurrence 2026-09-25T14:42:35.292807+00:00	5	2026-09-25 14:51:12.023145+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T14:42:35.292807+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
55e5d9d2-4d45-4d32-a5cb-6566ea148cd6	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:6415cb76-6249-46ad-9649-30d1025ba72c:2026-09-25T14:48:00.349508+00:00	f	scheduled occurrence 2026-09-25T14:48:00.349508+00:00	5	2026-09-25 14:51:12.189559+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T14:48:00.349508+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
3013ce28-c3cc-4798-be62-1f1df2b99f45	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:8615ca91-de1c-49ea-85ea-74bede8ae9b8:2026-09-25T14:43:39.275532+00:00	f	scheduled occurrence 2026-09-25T14:43:39.275532+00:00	5	2026-09-25 14:51:12.125371+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T14:43:39.275532+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
41f26384-a34f-4fc6-987c-087a046cf42c	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:eb43ac8b-9092-41cd-916e-7029f677874d:2026-09-25T14:42:52.427134+00:00	f	scheduled occurrence 2026-09-25T14:42:52.427134+00:00	5	2026-09-25 14:51:12.05643+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T14:42:52.427134+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
32baf8fb-af8f-4f7a-a8d1-cd7a30f2c7fe	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 14:53:52.782308+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 14:53:52.868573+00	succeeded	transient_failure	{"succeed_on_attempt": 2}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 15:37:31.779756+00	succeeded	transient_failure	{"succeed_on_attempt": 2}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
d9001c70-db76-4ee9-a52f-d102a0284ae1	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:af6eb320-1eb3-4f10-9b63-67960864a378:2026-09-25T14:53:48.009537+00:00	f	scheduled occurrence 2026-09-25T14:53:48.009537+00:00	5	2026-09-25 14:53:53.022455+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T14:53:48.009537+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
3a54dc18-4988-4ddf-bdd2-3c50229a2fd6	1c30d9ed-d52a-42ed-a4b9-e0bd0f1090eb	4aaa159d-cfe8-41f6-8c52-d2f2d9c214c4	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 14:53:53.342679+00	queued	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "4aaa159d-cfe8-41f6-8c52-d2f2d9c214c4"}
1e82450b-72a9-436b-b3b2-46a915738f5b	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 15:39:15.385913+00	succeeded	transient_failure	{"succeed_on_attempt": 2}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
bb9de075-0d97-4a93-8b3e-72c2bbf0b801	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:4084524a-06b2-4b3f-b010-48fff44e98cb:2026-09-25T15:37:59.371396+00:00	f	scheduled occurrence 2026-09-25T15:37:59.371396+00:00	5	2026-09-25 15:38:04.388245+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T15:37:59.371396+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
45d210df-829b-4915-8e37-cca1449cb6d9	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 15:37:31.687163+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
3c51e672-9ffc-4708-a633-d6b0080b97db	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:74ed46b8-b272-49cb-ad05-9e8083fb1c8c:2026-09-25T15:37:26.923883+00:00	f	scheduled occurrence 2026-09-25T15:37:26.923883+00:00	5	2026-09-25 15:37:31.949422+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T15:37:26.923883+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
64db6bcb-b7cc-4fa1-9e0a-f78faa9e4121	8856d797-5714-421e-9b68-21977321152b	f8970e4e-f2bc-46e5-b1e2-6de99e823130	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 15:37:32.312679+00	queued	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "f8970e4e-f2bc-46e5-b1e2-6de99e823130"}
00a1fa40-f69b-4121-958d-b8f8d9137513	9b6e00cd-d3cc-49f2-ab24-e45c50d89b55	189e1da9-2344-4468-aa4c-41235f9bd9c0	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 15:38:04.732708+00	queued	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "189e1da9-2344-4468-aa4c-41235f9bd9c0"}
87fd1bcb-34c1-4dc6-b7a0-b8c8d4255e2a	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 15:38:04.124433+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
f88b1602-18de-45f7-a836-753ac6dbb73d	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 15:38:04.213789+00	succeeded	transient_failure	{"succeed_on_attempt": 2}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
0e3f8700-edcb-45c3-b183-ebd57436eb4b	8f3d00ce-4706-4049-88b1-f080bbb33ffc	4862db1a-85f3-49c1-bed2-1def9d383dbe	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 15:39:15.918512+00	queued	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "4862db1a-85f3-49c1-bed2-1def9d383dbe"}
ea1b3ec9-5441-4dd9-a4b6-428886125db7	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 15:39:15.29489+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
72709084-6173-43bf-ac05-71607e3bb043	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:919354fc-10e9-42d6-a254-c88d1c47bf15:2026-09-25T15:39:10.542065+00:00	f	scheduled occurrence 2026-09-25T15:39:10.542065+00:00	5	2026-09-25 15:39:15.557548+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T15:39:10.542065+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
d7933dde-59a3-4152-99e1-15461565de3e	993df0b6-4bdb-43ea-9e50-715141765180	b0e01231-2313-441a-9bc8-f12449d3d249	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	e2e-0-cust-1790350755976@staging.local	f	\N	5	2026-09-25 15:39:16.088235+00	queued	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "b0e01231-2313-441a-9bc8-f12449d3d249"}
d4b6deac-d10f-4d17-8d19-2ad319d1c5f4	993df0b6-4bdb-43ea-9e50-715141765180	b0e01231-2313-441a-9bc8-f12449d3d249	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	e2e-1-cust-1790350755976@staging.local	f	\N	5	2026-09-25 15:39:16.11747+00	queued	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "b0e01231-2313-441a-9bc8-f12449d3d249"}
8378b1d5-a70a-4e7c-b553-61e7ab149b81	993df0b6-4bdb-43ea-9e50-715141765180	b0e01231-2313-441a-9bc8-f12449d3d249	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	e2e-2-cust-1790350755976@staging.local	f	\N	5	2026-09-25 15:39:16.147202+00	queued	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "b0e01231-2313-441a-9bc8-f12449d3d249"}
2af0ccf8-5e8d-47ec-aa8e-9c76a1229f07	993df0b6-4bdb-43ea-9e50-715141765180	b0e01231-2313-441a-9bc8-f12449d3d249	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	e2e-3-cust-1790350755976@staging.local	f	\N	5	2026-09-25 15:39:16.178133+00	queued	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "b0e01231-2313-441a-9bc8-f12449d3d249"}
5df93f57-0670-43cf-8573-ef4057dfc5ac	993df0b6-4bdb-43ea-9e50-715141765180	b0e01231-2313-441a-9bc8-f12449d3d249	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	e2e-4-cust-1790350755976@staging.local	f	\N	5	2026-09-25 15:39:16.207742+00	queued	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "b0e01231-2313-441a-9bc8-f12449d3d249"}
a4b9c007-7508-4e67-ba66-34dcb83afdbc	993df0b6-4bdb-43ea-9e50-715141765180	b0e01231-2313-441a-9bc8-f12449d3d249	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 15:39:16.236494+00	queued	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "b0e01231-2313-441a-9bc8-f12449d3d249"}
4bcb49ea-f1e8-4f40-92ae-74d72dd2a783	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:81728559-dc82-414e-aa1e-e737ebf2818a:2026-09-25T15:39:45.488996+00:00	f	scheduled occurrence 2026-09-25T15:39:45.488996+00:00	5	2026-09-25 15:39:50.503338+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T15:39:45.488996+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
a2dd52f7-eb7d-4ea2-9a53-25a8c12fabc7	0d9868c5-1b93-4b0c-b8d6-8a97cb21594e	99d0d2b9-2ad9-4e96-bf2f-d0e2d89a7ff5	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 15:39:50.846658+00	queued	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "99d0d2b9-2ad9-4e96-bf2f-d0e2d89a7ff5"}
00fb6a50-57ec-4e8d-9a22-94b43b6669cb	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 15:39:50.224325+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
6828b198-0ca2-4889-97ee-bdc5e0ad15c8	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	e2e-0-cust-1790350790868@staging.local	f	\N	5	2026-09-25 15:39:51.006646+00	queued	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67"}
6ffc2dab-063d-44af-a3e7-215eaad84634	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	e2e-1-cust-1790350790868@staging.local	f	\N	5	2026-09-25 15:39:51.034858+00	queued	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67"}
830cdfcb-df3b-4644-808e-326f472376bb	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	e2e-2-cust-1790350790868@staging.local	f	\N	5	2026-09-25 15:39:51.065717+00	queued	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67"}
c3eb9278-49f7-4c93-8f8e-a94559908fad	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 15:39:50.347286+00	succeeded	transient_failure	{"succeed_on_attempt": 2}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
11f34eb0-bf3a-4d8a-9156-9746dab1755e	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	e2e-3-cust-1790350790868@staging.local	f	\N	5	2026-09-25 15:39:51.094209+00	queued	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67"}
93ae110c-924a-4a5f-9db0-8d7b50e3c135	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	e2e-4-cust-1790350790868@staging.local	f	\N	5	2026-09-25 15:39:51.122267+00	queued	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67"}
\.


--
-- Data for Name: job_runs; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.job_runs (id, job_request_id, state, run_id, attempts, max_attempts, failure_class, error_message, started_at, finished_at, created_at, priority, reserved_cost, actual_cost, scheduled_time, heartbeat_time, lease_owner, lease_expiration, idempotency_key, parent_job_id, correlation_id, output_reference, error_code, error_summary, cancellation_state) FROM stdin;
36ae63b1-ec9c-4dc6-944f-a0740350d437	de0a429b-9bcf-4d1d-9198-e1727b230d19	succeeded	73e7f174-54ac-4d37-9f65-33c1608a6c2b	1	3	\N	\N	\N	2026-09-25 14:11:43.827219+00	2026-09-25 14:11:43.761665+00	5	\N	\N	\N	2026-09-25 14:11:43.815186+00	staging-smoke-worker	2026-09-25 14:12:43.81518+00	\N	\N	\N	job/de0a429b-9bcf-4d1d-9198-e1727b230d19/runs/73e7f174-54ac-4d37-9f65-33c1608a6c2b/output	\N	\N	\N
0f0a520c-bec7-4128-becf-432a731797db	2d56906f-32ab-438b-a817-f8baef2559f0	succeeded	221d84bc-4761-4991-a5aa-acbe38c1e303	1	3	\N	\N	\N	2026-09-25 12:47:41.194973+00	2026-09-25 12:47:41.117921+00	5	\N	\N	\N	2026-09-25 12:47:41.178089+00	staging-smoke-worker	2026-09-25 12:48:41.178084+00	\N	\N	\N	job/2d56906f-32ab-438b-a817-f8baef2559f0/runs/221d84bc-4761-4991-a5aa-acbe38c1e303/output	\N	\N	\N
4065297b-3208-4a1c-a690-a783b8323caa	04619a31-fada-4f30-8428-e85428a36d62	succeeded	013e1cd7-ca06-4dd8-85be-8475bde12d48	1	3	\N	\N	\N	2026-09-25 13:42:57.222301+00	2026-09-25 13:42:40.309807+00	5	\N	\N	\N	2026-09-25 13:42:57.210736+00	staging-smoke-worker	2026-09-25 13:43:57.210731+00	\N	\N	2026-09-25T13:42:35.292807+00:00	job/04619a31-fada-4f30-8428-e85428a36d62/runs/013e1cd7-ca06-4dd8-85be-8475bde12d48/output	\N	\N	\N
cae9e2af-6b8a-47ba-a403-0899612cd5bc	a9ee27a7-5545-4d87-a365-1474d10a102b	succeeded	85f3b973-6cdd-4c00-8f18-b09d72226c07	1	3	\N	\N	\N	2026-09-25 13:42:40.080644+00	2026-09-25 12:48:05.363577+00	5	\N	\N	\N	2026-09-25 13:42:40.064598+00	staging-smoke-worker	2026-09-25 13:43:40.06459+00	\N	\N	2026-09-25T12:48:00.349508+00:00	job/a9ee27a7-5545-4d87-a365-1474d10a102b/runs/85f3b973-6cdd-4c00-8f18-b09d72226c07/output	\N	\N	\N
1f672b74-d648-497e-96a9-3dd5e1ebf17c	cfaf79d9-8e96-4764-a652-19f2f2179004	succeeded	94137786-91d3-4086-8634-5da9968bd6c7	1	3	\N	\N	\N	2026-09-25 13:42:57.269961+00	2026-09-25 13:42:57.161481+00	5	\N	\N	\N	2026-09-25 13:42:57.258643+00	staging-smoke-worker	2026-09-25 13:43:57.258637+00	\N	\N	\N	job/cfaf79d9-8e96-4764-a652-19f2f2179004/runs/94137786-91d3-4086-8634-5da9968bd6c7/output	\N	\N	\N
eba8d2f0-9a42-4265-950f-2d7a29ba0bdb	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	succeeded	7a353e29-dc66-4086-9aa8-64174efe554d	2	3	\N	\N	\N	2026-09-25 13:42:57.413552+00	2026-09-25 13:42:57.290897+00	5	\N	\N	2026-09-25 13:42:52.362996+00	2026-09-25 13:42:57.402427+00	staging-smoke-worker	2026-09-25 13:43:57.402422+00	\N	\N	\N	job/81780c14-5eee-4ff2-ae7f-1ac52fe951f8/runs/7a353e29-dc66-4086-9aa8-64174efe554d/output	transient_failure	transient failure simulated	\N
94629afc-29a5-45bb-860c-eeefa9100db9	bb7b2f11-44e3-44ca-8749-c6a56ee4051d	succeeded	870cad35-bcfe-42cc-ad93-accbc0ee6838	1	3	\N	\N	\N	2026-09-25 12:48:05.135966+00	2026-09-25 12:47:41.387909+00	5	\N	\N	\N	2026-09-25 12:48:05.123792+00	staging-smoke-worker	2026-09-25 12:49:05.123787+00	\N	\N	2026-09-25T12:47:36.370345+00:00	job/bb7b2f11-44e3-44ca-8749-c6a56ee4051d/runs/870cad35-bcfe-42cc-ad93-accbc0ee6838/output	\N	\N	\N
9b0300f5-1c13-4c48-b86a-95c96fe0fdb4	1faed168-4681-4d21-9407-62ac9f955cda	succeeded	e921643e-db91-4827-969e-ed3ef02faf92	2	3	\N	\N	\N	2026-09-25 12:47:41.356651+00	2026-09-25 12:47:41.217148+00	5	\N	\N	2026-09-25 12:47:36.301218+00	2026-09-25 12:47:41.344254+00	staging-smoke-worker	2026-09-25 12:48:41.344249+00	\N	\N	\N	job/1faed168-4681-4d21-9407-62ac9f955cda/runs/e921643e-db91-4827-969e-ed3ef02faf92/output	transient_failure	transient failure simulated	\N
1e24c489-96ef-4850-aac8-29876dd07010	74e79cff-759d-4806-b22c-c13f230ff015	succeeded	891c1282-c650-4b2f-9b9c-4e4bec3eb150	1	3	\N	\N	\N	2026-09-25 13:42:57.610503+00	2026-09-25 13:42:57.442439+00	5	\N	\N	\N	2026-09-25 13:42:57.598839+00	staging-smoke-worker	2026-09-25 13:43:57.598834+00	\N	\N	2026-09-25T13:42:52.427134+00:00	job/74e79cff-759d-4806-b22c-c13f230ff015/runs/891c1282-c650-4b2f-9b9c-4e4bec3eb150/output	\N	\N	\N
e8390d9d-f7eb-40ab-a09e-a909b8995f64	3cee773e-9b1c-484f-8538-4bc9d37773d5	succeeded	f1475883-1c5b-4903-aaaf-b5749f2bbbf6	1	3	\N	\N	\N	2026-09-25 12:48:05.184886+00	2026-09-25 12:48:05.067497+00	5	\N	\N	\N	2026-09-25 12:48:05.173092+00	staging-smoke-worker	2026-09-25 12:49:05.173087+00	\N	\N	\N	job/3cee773e-9b1c-484f-8538-4bc9d37773d5/runs/f1475883-1c5b-4903-aaaf-b5749f2bbbf6/output	\N	\N	\N
20907b76-d3af-4bca-9368-5cbc7c93833f	ece8ac3a-1061-486c-a849-7574c872926d	succeeded	189021bf-e92f-456e-933d-577fb90e6ae2	1	3	\N	\N	\N	2026-09-25 13:42:57.66118+00	2026-09-25 13:42:57.552783+00	5	\N	\N	\N	2026-09-25 13:42:57.649065+00	staging-smoke-worker	2026-09-25 13:43:57.64906+00	\N	\N	staging-req-chain-1	job/ece8ac3a-1061-486c-a849-7574c872926d/runs/189021bf-e92f-456e-933d-577fb90e6ae2/output	\N	\N	\N
e033c99f-6bd9-41c2-a9e3-b91c9221e88f	95d4a73e-2173-489d-ab2c-9857472049de	succeeded	63dcf6f3-2062-4538-80ce-d6b57683b3e8	2	3	\N	\N	\N	2026-09-25 12:48:05.336881+00	2026-09-25 12:48:05.204665+00	5	\N	\N	2026-09-25 12:48:00.283874+00	2026-09-25 12:48:05.32621+00	staging-smoke-worker	2026-09-25 12:49:05.326206+00	\N	\N	\N	job/95d4a73e-2173-489d-ab2c-9857472049de/runs/63dcf6f3-2062-4538-80ce-d6b57683b3e8/output	transient_failure	transient failure simulated	\N
ad4f0efd-1ae2-4e1d-b221-4ae7bb006a2a	6ce89210-9d7b-4ef2-a460-7936e37861e9	succeeded	2ed07a3f-a742-484d-9f51-295bf3c16c52	1	3	\N	\N	\N	2026-09-25 13:43:27.988825+00	2026-09-25 13:43:27.929048+00	5	\N	\N	\N	2026-09-25 13:43:27.977842+00	staging-smoke-worker	2026-09-25 13:44:27.977836+00	\N	\N	\N	job/6ce89210-9d7b-4ef2-a460-7936e37861e9/runs/2ed07a3f-a742-484d-9f51-295bf3c16c52/output	\N	\N	\N
eed18227-06e0-4021-992c-60e0971a3ebc	dde1681c-6f4e-4219-97c2-06d1154c7067	succeeded	6f656618-35bd-4f97-952b-1a5c832d1f8b	2	3	\N	\N	\N	2026-09-25 13:43:28.183628+00	2026-09-25 13:43:28.014097+00	5	\N	\N	2026-09-25 13:43:23.10993+00	2026-09-25 13:43:28.171685+00	staging-smoke-worker	2026-09-25 13:44:28.17168+00	\N	\N	\N	job/dde1681c-6f4e-4219-97c2-06d1154c7067/runs/6f656618-35bd-4f97-952b-1a5c832d1f8b/output	transient_failure	transient failure simulated	\N
0eca3b72-5985-4f78-8d32-1efb28e2fad2	cc39a661-801a-42f2-9ccc-b0ef2f10137e	succeeded	bcb65321-4548-465f-983f-9cd42242069b	1	3	\N	\N	\N	2026-09-25 13:42:40.130554+00	2026-09-25 13:42:40.009759+00	5	\N	\N	\N	2026-09-25 13:42:40.119233+00	staging-smoke-worker	2026-09-25 13:43:40.119225+00	\N	\N	\N	job/cc39a661-801a-42f2-9ccc-b0ef2f10137e/runs/bcb65321-4548-465f-983f-9cd42242069b/output	\N	\N	\N
062ea306-ea40-4a3b-a110-70bd7837478e	dee8ad4e-8fe6-40e3-885f-d83b287d400d	succeeded	028df412-3cd1-4027-9484-8e2677da0df2	2	3	\N	\N	\N	2026-09-25 13:42:40.279677+00	2026-09-25 13:42:40.153772+00	5	\N	\N	2026-09-25 13:42:35.229552+00	2026-09-25 13:42:40.269043+00	staging-smoke-worker	2026-09-25 13:43:40.269038+00	\N	\N	\N	job/dee8ad4e-8fe6-40e3-885f-d83b287d400d/runs/028df412-3cd1-4027-9484-8e2677da0df2/output	transient_failure	transient failure simulated	\N
568df552-aef6-487c-9ede-98a720f902ba	947d35bd-7f5e-4967-800c-e78b630cd423	succeeded	c235be5f-e80d-4af6-983a-76c3d2a8df68	1	3	\N	\N	\N	2026-09-25 13:43:28.365535+00	2026-09-25 13:43:28.218885+00	5	\N	\N	\N	2026-09-25 13:43:28.354096+00	staging-smoke-worker	2026-09-25 13:44:28.354092+00	\N	\N	2026-09-25T13:43:23.199997+00:00	job/947d35bd-7f5e-4967-800c-e78b630cd423/runs/c235be5f-e80d-4af6-983a-76c3d2a8df68/output	\N	\N	\N
23b68e9f-795f-44a7-9d38-1688f76d54ba	40a0cbf9-f619-4bb5-a7eb-5cd23cf9dee1	succeeded	8060967c-9d03-475f-a8ba-ecd05f59fa15	1	3	\N	\N	\N	2026-09-25 13:43:44.107331+00	2026-09-25 13:43:44.008507+00	5	\N	\N	\N	2026-09-25 13:43:44.09467+00	staging-smoke-worker	2026-09-25 13:44:44.094663+00	\N	\N	\N	job/40a0cbf9-f619-4bb5-a7eb-5cd23cf9dee1/runs/8060967c-9d03-475f-a8ba-ecd05f59fa15/output	\N	\N	\N
78629a54-a06c-44da-8f3e-d700b1a88680	ecf21bd2-46ad-402b-9329-8c5cae2291e9	succeeded	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	2	3	\N	\N	\N	2026-09-25 13:43:44.258658+00	2026-09-25 13:43:44.12938+00	5	\N	\N	2026-09-25 13:43:39.204239+00	2026-09-25 13:43:44.24753+00	staging-smoke-worker	2026-09-25 13:44:44.247525+00	\N	\N	\N	job/ecf21bd2-46ad-402b-9329-8c5cae2291e9/runs/ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32/output	transient_failure	transient failure simulated	\N
cde2d0ba-16d7-4b62-94db-1b35b33f57f7	c9ed2300-a06c-420f-b8fa-b45f0bd28d6b	succeeded	980f46bb-1cda-4078-bb7f-a3d73c7b40d8	1	3	\N	\N	\N	2026-09-25 13:43:44.431424+00	2026-09-25 13:43:44.291049+00	5	\N	\N	\N	2026-09-25 13:43:44.420609+00	staging-smoke-worker	2026-09-25 13:44:44.420604+00	\N	\N	2026-09-25T13:43:39.275532+00:00	job/c9ed2300-a06c-420f-b8fa-b45f0bd28d6b/runs/980f46bb-1cda-4078-bb7f-a3d73c7b40d8/output	\N	\N	\N
b9c827d8-4f7a-4278-98e2-e09055bd5004	32baf8fb-af8f-4f7a-a8d1-cd7a30f2c7fe	succeeded	52a538e7-14cd-411f-b68a-a012031f7fc0	1	3	\N	\N	\N	2026-09-25 14:53:52.845624+00	2026-09-25 14:53:52.78605+00	5	\N	\N	\N	2026-09-25 14:53:52.83323+00	staging-smoke-worker	2026-09-25 14:54:52.833223+00	\N	\N	\N	job/32baf8fb-af8f-4f7a-a8d1-cd7a30f2c7fe/runs/52a538e7-14cd-411f-b68a-a012031f7fc0/output	\N	\N	\N
dcbef270-9417-4527-98b6-4e367ddcb82d	d942173e-b6cf-4f51-a3d3-996f6f083813	succeeded	888e1f7b-6639-4463-b86f-c32ff1af4cc3	2	3	\N	\N	\N	2026-09-25 14:11:43.96873+00	2026-09-25 14:11:43.847052+00	5	\N	\N	2026-09-25 14:11:38.919425+00	2026-09-25 14:11:43.958266+00	staging-smoke-worker	2026-09-25 14:12:43.958261+00	\N	\N	\N	job/d942173e-b6cf-4f51-a3d3-996f6f083813/runs/888e1f7b-6639-4463-b86f-c32ff1af4cc3/output	transient_failure	transient failure simulated	\N
381579b6-e07b-4375-8ed7-ef917797b23e	ea1b3ec9-5441-4dd9-a4b6-428886125db7	succeeded	2acbf0ce-aac1-4429-9f62-96a58336f831	1	3	\N	\N	\N	2026-09-25 15:39:15.356397+00	2026-09-25 15:39:15.299144+00	5	\N	\N	\N	2026-09-25 15:39:15.345345+00	staging-smoke-worker	2026-09-25 15:40:15.345339+00	\N	\N	\N	job/ea1b3ec9-5441-4dd9-a4b6-428886125db7/runs/2acbf0ce-aac1-4429-9f62-96a58336f831/output	\N	\N	\N
e7a65f7b-12e3-435f-a477-1cc034d0ca32	a9c8bbb2-aded-4aaa-abaa-3ff70acbee4f	succeeded	b7142c7b-501f-4b67-a1af-6bd40e5de64c	1	3	\N	\N	\N	2026-09-25 14:11:44.164092+00	2026-09-25 14:11:44.016043+00	5	\N	\N	\N	2026-09-25 14:11:44.150006+00	staging-smoke-worker	2026-09-25 14:12:44.150001+00	\N	\N	2026-09-25T14:11:38.982073+00:00	job/a9c8bbb2-aded-4aaa-abaa-3ff70acbee4f/runs/b7142c7b-501f-4b67-a1af-6bd40e5de64c/output	\N	\N	\N
a5b87805-a9d0-403b-8ee3-aad63d3200f5	00a1fa40-f69b-4121-958d-b8f8d9137513	queued	a2d6877d-260c-469f-9662-b129ec767e8a	0	3	\N	\N	\N	\N	2026-09-25 15:38:04.735271+00	5	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
29842960-2422-407e-ac94-191fb94f00a6	d9001c70-db76-4ee9-a52f-d102a0284ae1	succeeded	46a6356b-3b04-4540-bef9-d1ba99fcf6ec	1	3	\N	\N	\N	2026-09-25 14:53:53.177439+00	2026-09-25 14:53:53.025054+00	5	\N	\N	\N	2026-09-25 14:53:53.16558+00	staging-smoke-worker	2026-09-25 14:54:53.165576+00	\N	\N	2026-09-25T14:53:48.009537+00:00	job/d9001c70-db76-4ee9-a52f-d102a0284ae1/runs/46a6356b-3b04-4540-bef9-d1ba99fcf6ec/output	\N	\N	\N
56d4ac9e-d1f2-457d-97ed-a830be1b55ab	2af0ccf8-5e8d-47ec-aa8e-9c76a1229f07	queued	09dd775d-08f5-461e-99a0-50e3c8c94e95	0	3	\N	\N	\N	\N	2026-09-25 15:39:16.180758+00	5	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
8ed50dde-d71d-418d-8759-9ac7309bde13	1e82450b-72a9-436b-b3b2-46a915738f5b	succeeded	c3299161-4bdf-49ec-b711-898ae6287e0b	2	3	\N	\N	\N	2026-09-25 15:39:15.525387+00	2026-09-25 15:39:15.388679+00	5	\N	\N	2026-09-25 15:39:10.471136+00	2026-09-25 15:39:15.513966+00	staging-smoke-worker	2026-09-25 15:40:15.513961+00	\N	\N	\N	job/1e82450b-72a9-436b-b3b2-46a915738f5b/runs/c3299161-4bdf-49ec-b711-898ae6287e0b/output	transient_failure	transient failure simulated	\N
983fad5b-5271-437b-8ef3-b47added51ea	3a54dc18-4988-4ddf-bdd2-3c50229a2fd6	queued	d9dc7462-7954-4ba8-9d77-1c4538ad72e6	0	3	\N	\N	\N	\N	2026-09-25 14:53:53.345286+00	5	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
0dd87e1a-8ab8-4e0b-a317-051a36e692d6	2de868d1-6a42-4874-b6c4-08a6f521ee4e	succeeded	18511b1c-101e-43aa-9811-2a3f0cac75e9	1	3	\N	\N	\N	2026-09-25 14:51:11.789421+00	2026-09-25 14:11:44.206116+00	5	\N	\N	\N	2026-09-25 14:51:11.777192+00	staging-smoke-worker	2026-09-25 14:52:11.777185+00	\N	\N	\N	job/2de868d1-6a42-4874-b6c4-08a6f521ee4e/runs/18511b1c-101e-43aa-9811-2a3f0cac75e9/output	\N	\N	\N
aa929e41-e37d-4448-8e45-3b1a53af5e0e	87fd1bcb-34c1-4dc6-b7a0-b8c8d4255e2a	succeeded	447d268e-6349-43bd-b790-d224b352371d	1	3	\N	\N	\N	2026-09-25 15:38:04.189703+00	2026-09-25 15:38:04.127621+00	5	\N	\N	\N	2026-09-25 15:38:04.177884+00	staging-smoke-worker	2026-09-25 15:39:04.177878+00	\N	\N	\N	job/87fd1bcb-34c1-4dc6-b7a0-b8c8d4255e2a/runs/447d268e-6349-43bd-b790-d224b352371d/output	\N	\N	\N
7b38fdc8-63ba-4e90-be27-fd76d0e1cf5c	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	succeeded	066a69b5-3244-4e91-8da5-01f414b9052a	2	3	\N	\N	\N	2026-09-25 14:53:52.994232+00	2026-09-25 14:53:52.871562+00	5	\N	\N	2026-09-25 14:53:47.944434+00	2026-09-25 14:53:52.98323+00	staging-smoke-worker	2026-09-25 14:54:52.983225+00	\N	\N	\N	job/8d35c923-2d19-4d1b-b28c-ed0d3a6433eb/runs/066a69b5-3244-4e91-8da5-01f414b9052a/output	transient_failure	transient failure simulated	\N
14f2fe6e-158b-409d-bda7-51554be3e9a9	72709084-6173-43bf-ac05-71607e3bb043	succeeded	0e2e02e8-fde2-4386-b45f-94c21fd920c5	1	3	\N	\N	\N	2026-09-25 15:39:15.727102+00	2026-09-25 15:39:15.560157+00	5	\N	\N	\N	2026-09-25 15:39:15.713528+00	staging-smoke-worker	2026-09-25 15:40:15.713523+00	\N	\N	2026-09-25T15:39:10.542065+00:00	job/72709084-6173-43bf-ac05-71607e3bb043/runs/0e2e02e8-fde2-4386-b45f-94c21fd920c5/output	\N	\N	\N
f32674e6-6ba2-415c-9223-1b246d41bc84	0e3f8700-edcb-45c3-b183-ebd57436eb4b	queued	c6c9b6c9-6898-467a-81a0-cfdcf7904083	0	3	\N	\N	\N	\N	2026-09-25 15:39:15.921108+00	5	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
e6f282a7-77c1-4350-889d-2ae1de04b46d	d7933dde-59a3-4152-99e1-15461565de3e	queued	8fa27db2-9fee-4d10-b980-03a23348cf21	0	3	\N	\N	\N	\N	2026-09-25 15:39:16.090812+00	5	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
6a37c74e-9cdc-4c3c-8dd6-e70b918d77aa	d4b6deac-d10f-4d17-8d19-2ad319d1c5f4	queued	df883f51-cf48-4022-b43d-4657cb645e83	0	3	\N	\N	\N	\N	2026-09-25 15:39:16.120054+00	5	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
8c041470-809f-4a2f-8f4a-497b26a2bee1	f88b1602-18de-45f7-a836-753ac6dbb73d	succeeded	e870faf1-14e6-40f8-a346-6d60573785af	2	3	\N	\N	\N	2026-09-25 15:38:04.355684+00	2026-09-25 15:38:04.216625+00	5	\N	\N	2026-09-25 15:37:59.304721+00	2026-09-25 15:38:04.344824+00	staging-smoke-worker	2026-09-25 15:39:04.344818+00	\N	\N	\N	job/f88b1602-18de-45f7-a836-753ac6dbb73d/runs/e870faf1-14e6-40f8-a346-6d60573785af/output	transient_failure	transient failure simulated	\N
4e24df16-c5d7-44cf-b043-31f708edad94	8378b1d5-a70a-4e7c-b553-61e7ab149b81	queued	91079a87-d676-46e2-8be4-fec56f582d9d	0	3	\N	\N	\N	\N	2026-09-25 15:39:16.149765+00	5	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
26b93f3e-5e39-4054-8d7d-af41a89f865b	5df93f57-0670-43cf-8573-ef4057dfc5ac	queued	ef0c7cdd-9bca-47a5-b120-339c63d1c67b	0	3	\N	\N	\N	\N	2026-09-25 15:39:16.210738+00	5	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
467fa535-98fb-47ed-909e-5c708c4b0238	a4b9c007-7508-4e67-ba66-34dcb83afdbc	queued	922f1fac-f869-4980-99c1-cb61b74c1d0b	0	3	\N	\N	\N	\N	2026-09-25 15:39:16.239321+00	5	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
19804421-3abd-4a1a-beac-2f1cd5c650a6	bb9de075-0d97-4a93-8b3e-72c2bbf0b801	succeeded	13cb4d13-6660-4f9f-9730-4a8805603a19	1	3	\N	\N	\N	2026-09-25 15:38:04.538499+00	2026-09-25 15:38:04.391048+00	5	\N	\N	\N	2026-09-25 15:38:04.527737+00	staging-smoke-worker	2026-09-25 15:39:04.527732+00	\N	\N	2026-09-25T15:37:59.371396+00:00	job/bb9de075-0d97-4a93-8b3e-72c2bbf0b801/runs/13cb4d13-6660-4f9f-9730-4a8805603a19/output	\N	\N	\N
3191e854-31ad-43de-b3a7-3ec72f037dbe	a83672ad-6e70-4814-bd20-a28b34c34421	succeeded	c6c4e85b-c433-4539-8baf-0b39ca813496	1	3	\N	\N	\N	2026-09-25 14:51:11.845676+00	2026-09-25 14:51:11.72327+00	5	\N	\N	\N	2026-09-25 14:51:11.834452+00	staging-smoke-worker	2026-09-25 14:52:11.834444+00	\N	\N	\N	job/a83672ad-6e70-4814-bd20-a28b34c34421/runs/c6c4e85b-c433-4539-8baf-0b39ca813496/output	\N	\N	\N
9bc58d94-f8ee-4fdb-b863-51f60035ade1	45d210df-829b-4915-8e37-cca1449cb6d9	succeeded	d384a816-2afc-4823-9510-a9e46d265c43	1	3	\N	\N	\N	2026-09-25 15:37:31.757468+00	2026-09-25 15:37:31.691562+00	5	\N	\N	\N	2026-09-25 15:37:31.745385+00	staging-smoke-worker	2026-09-25 15:38:31.745378+00	\N	\N	\N	job/45d210df-829b-4915-8e37-cca1449cb6d9/runs/d384a816-2afc-4823-9510-a9e46d265c43/output	\N	\N	\N
b91a63d4-ca4f-48ae-97aa-2f378339fb80	00fb6a50-57ec-4e8d-9a22-94b43b6669cb	succeeded	0d700548-3a64-41b3-9b53-1c19625e9229	1	3	\N	\N	\N	2026-09-25 15:39:50.293368+00	2026-09-25 15:39:50.228749+00	5	\N	\N	\N	2026-09-25 15:39:50.281212+00	staging-smoke-worker	2026-09-25 15:40:50.281206+00	\N	\N	\N	job/00fb6a50-57ec-4e8d-9a22-94b43b6669cb/runs/0d700548-3a64-41b3-9b53-1c19625e9229/output	\N	\N	\N
d14a6e89-94a1-4a34-8852-b9c6cdd6167e	c3eb9278-49f7-4c93-8f8e-a94559908fad	succeeded	c604cf51-ac89-4bdc-9ea2-746cc1adb608	2	3	\N	\N	\N	2026-09-25 15:39:50.473699+00	2026-09-25 15:39:50.350276+00	5	\N	\N	2026-09-25 15:39:45.424787+00	2026-09-25 15:39:50.46279+00	staging-smoke-worker	2026-09-25 15:40:50.462786+00	\N	\N	\N	job/c3eb9278-49f7-4c93-8f8e-a94559908fad/runs/c604cf51-ac89-4bdc-9ea2-746cc1adb608/output	transient_failure	transient failure simulated	\N
46a1f7af-76e6-4e66-829d-d80e6ce6e31c	33a7e677-b29a-4895-87f4-1a8b43a1e374	succeeded	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	2	3	\N	\N	\N	2026-09-25 14:51:11.992714+00	2026-09-25 14:51:11.869536+00	5	\N	\N	2026-09-25 14:51:06.942737+00	2026-09-25 14:51:11.981085+00	staging-smoke-worker	2026-09-25 14:52:11.981079+00	\N	\N	\N	job/33a7e677-b29a-4895-87f4-1a8b43a1e374/runs/ce8a1b10-38d0-4ef6-b780-6d9788a4cbed/output	transient_failure	transient failure simulated	\N
795f8698-31bc-468c-8c80-b2ec3dd2eb8d	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	succeeded	b8208594-7396-49a5-a29e-4518c24a4b93	2	3	\N	\N	\N	2026-09-25 15:37:31.909324+00	2026-09-25 15:37:31.782974+00	5	\N	\N	2026-09-25 15:37:26.859572+00	2026-09-25 15:37:31.89914+00	staging-smoke-worker	2026-09-25 15:38:31.899136+00	\N	\N	\N	job/7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe/runs/b8208594-7396-49a5-a29e-4518c24a4b93/output	transient_failure	transient failure simulated	\N
bba478ab-a6e6-41ad-9dbb-1457fcde6f2c	a2dd52f7-eb7d-4ea2-9a53-25a8c12fabc7	queued	67cf4e56-2251-4762-a408-86f6cd6dce0b	0	3	\N	\N	\N	\N	2026-09-25 15:39:50.849181+00	5	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
9c1c9d6e-cb50-4fdd-aaec-9541f36c81e3	3c51e672-9ffc-4708-a633-d6b0080b97db	succeeded	c06674c2-6599-436e-99d5-642fcc32e7b8	1	3	\N	\N	\N	2026-09-25 15:37:32.106889+00	2026-09-25 15:37:31.952184+00	5	\N	\N	\N	2026-09-25 15:37:32.095097+00	staging-smoke-worker	2026-09-25 15:38:32.095092+00	\N	\N	2026-09-25T15:37:26.923883+00:00	job/3c51e672-9ffc-4708-a633-d6b0080b97db/runs/c06674c2-6599-436e-99d5-642fcc32e7b8/output	\N	\N	\N
a6e3b38d-b54b-43ee-bbd1-cace91a5363a	64db6bcb-b7cc-4fa1-9e0a-f78faa9e4121	queued	5ee7d797-a106-4fcf-941a-833acb355abc	0	3	\N	\N	\N	\N	2026-09-25 15:37:32.315369+00	5	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
5aeecdc3-8c3d-4283-a725-debdb0bf473d	4bcb49ea-f1e8-4f40-92ae-74d72dd2a783	succeeded	9077902e-98c6-4ac9-b0be-ca7a1a32e924	1	3	\N	\N	\N	2026-09-25 15:39:50.658193+00	2026-09-25 15:39:50.505967+00	5	\N	\N	\N	2026-09-25 15:39:50.647301+00	staging-smoke-worker	2026-09-25 15:40:50.647296+00	\N	\N	2026-09-25T15:39:45.488996+00:00	job/4bcb49ea-f1e8-4f40-92ae-74d72dd2a783/runs/9077902e-98c6-4ac9-b0be-ca7a1a32e924/output	\N	\N	\N
65597ba2-c104-4551-9eb7-00090731e2d0	df75213d-9b26-4a9f-bd32-4cf32de0e372	succeeded	ed8d2c75-d737-438a-bb53-4e457d4b096b	1	3	\N	\N	\N	2026-09-25 14:51:12.370669+00	2026-09-25 14:51:12.025672+00	5	\N	\N	\N	2026-09-25 14:51:12.359357+00	staging-smoke-worker	2026-09-25 14:52:12.359352+00	\N	\N	2026-09-25T14:42:35.292807+00:00	job/df75213d-9b26-4a9f-bd32-4cf32de0e372/runs/ed8d2c75-d737-438a-bb53-4e457d4b096b/output	\N	\N	\N
eb919111-08a0-425f-b676-ab8e25406cc8	6828b198-0ca2-4889-97ee-bdc5e0ad15c8	queued	5544e37b-5705-44bd-b1b6-c7de3e219c7c	0	3	\N	\N	\N	\N	2026-09-25 15:39:51.009252+00	5	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
046c7f56-bfbc-415e-b727-ec7a668a8827	d1b04528-b5f3-4cd7-a5d8-6534f355e04b	succeeded	8fd371e8-fff7-4585-a4ec-440107ec8af6	1	3	\N	\N	\N	2026-09-25 14:51:12.583392+00	2026-09-25 14:51:12.159916+00	5	\N	\N	\N	2026-09-25 14:51:12.572726+00	staging-smoke-worker	2026-09-25 14:52:12.572721+00	\N	\N	2026-09-25T14:47:36.370345+00:00	job/d1b04528-b5f3-4cd7-a5d8-6534f355e04b/runs/8fd371e8-fff7-4585-a4ec-440107ec8af6/output	\N	\N	\N
59a2ba56-509b-4146-b75d-29a9b47a48e3	6ffc2dab-063d-44af-a3e7-215eaad84634	queued	e5d28f54-0ded-42cb-aabe-70d054a67618	0	3	\N	\N	\N	\N	2026-09-25 15:39:51.039258+00	5	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
ac8ed1c9-a607-441a-8a72-cb2b76e8ab4a	8368c245-aeb2-4758-b4c8-ba91d8aec34e	succeeded	60873eaa-b945-465d-ac58-8761ed134713	1	3	\N	\N	\N	2026-09-25 14:51:12.490954+00	2026-09-25 14:51:12.09432+00	5	\N	\N	\N	2026-09-25 14:51:12.478892+00	staging-smoke-worker	2026-09-25 14:52:12.478887+00	\N	\N	2026-09-25T14:43:23.199997+00:00	job/8368c245-aeb2-4758-b4c8-ba91d8aec34e/runs/60873eaa-b945-465d-ac58-8761ed134713/output	\N	\N	\N
f9278dd6-6588-4eb5-ad08-0d6d3041d79f	41f26384-a34f-4fc6-987c-087a046cf42c	succeeded	3a5821b2-e29b-4355-b128-a97ddd6c4b8d	1	3	\N	\N	\N	2026-09-25 14:51:12.427951+00	2026-09-25 14:51:12.059989+00	5	\N	\N	\N	2026-09-25 14:51:12.416778+00	staging-smoke-worker	2026-09-25 14:52:12.416773+00	\N	\N	2026-09-25T14:42:52.427134+00:00	job/41f26384-a34f-4fc6-987c-087a046cf42c/runs/3a5821b2-e29b-4355-b128-a97ddd6c4b8d/output	\N	\N	\N
7c8becf1-1ba0-487b-97f6-0a345ed7dc07	830cdfcb-df3b-4644-808e-326f472376bb	queued	9e454c72-e784-4e01-ace2-e69001e04681	0	3	\N	\N	\N	\N	2026-09-25 15:39:51.068325+00	5	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
04cfc760-c2ad-41e4-b779-2a66a816dfcb	11f34eb0-bf3a-4d8a-9156-9746dab1755e	queued	1a02805b-9eee-4298-9ac0-ad3ecfa8ab99	0	3	\N	\N	\N	\N	2026-09-25 15:39:51.096683+00	5	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
c37fbc8c-af92-47be-bd4c-b0a6a72e25f9	f0a2b5a5-b0d5-4316-8cd4-1e095e241060	succeeded	862b2b82-ae8f-4668-b58a-596f73e32533	1	3	\N	\N	\N	2026-09-25 14:51:12.677144+00	2026-09-25 14:51:12.22316+00	5	\N	\N	\N	2026-09-25 14:51:12.665981+00	staging-smoke-worker	2026-09-25 14:52:12.665976+00	\N	\N	2026-09-25T14:51:07.007024+00:00	job/f0a2b5a5-b0d5-4316-8cd4-1e095e241060/runs/862b2b82-ae8f-4668-b58a-596f73e32533/output	\N	\N	\N
6e728576-9d5a-4126-b031-42a6b6f77c97	93ae110c-924a-4a5f-9db0-8d7b50e3c135	queued	30fac96c-c35a-4b90-a5ed-dcd70cb264d2	0	3	\N	\N	\N	\N	2026-09-25 15:39:51.124825+00	5	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
10c7ee0e-44d2-40c6-a437-d6e45d648bbc	3013ce28-c3cc-4798-be62-1f1df2b99f45	succeeded	7d07bd89-d711-4209-a0de-7eade8fb8d17	1	3	\N	\N	\N	2026-09-25 14:51:12.539081+00	2026-09-25 14:51:12.12818+00	5	\N	\N	\N	2026-09-25 14:51:12.527489+00	staging-smoke-worker	2026-09-25 14:52:12.527484+00	\N	\N	2026-09-25T14:43:39.275532+00:00	job/3013ce28-c3cc-4798-be62-1f1df2b99f45/runs/7d07bd89-d711-4209-a0de-7eade8fb8d17/output	\N	\N	\N
c64dc50a-6c4b-4e99-a188-5c531ac5d1e3	590d00ff-754c-428e-bec4-dc642314b8d1	queued	6ed4e858-451b-48b6-83db-ba11662eac4f	0	3	\N	\N	\N	\N	2026-09-25 14:51:12.862183+00	5	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N	\N
d6794102-3b3b-49eb-b95d-62bfd32fe9ea	55e5d9d2-4d45-4d32-a5cb-6566ea148cd6	succeeded	4e84497f-7ed5-4d89-9335-8c4138ab1de8	1	3	\N	\N	\N	2026-09-25 14:51:12.628361+00	2026-09-25 14:51:12.192079+00	5	\N	\N	\N	2026-09-25 14:51:12.616729+00	staging-smoke-worker	2026-09-25 14:52:12.616724+00	\N	\N	2026-09-25T14:48:00.349508+00:00	job/55e5d9d2-4d45-4d32-a5cb-6566ea148cd6/runs/4e84497f-7ed5-4d89-9335-8c4138ab1de8/output	\N	\N	\N
\.


--
-- Data for Name: job_schedules; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.job_schedules (id, organization_id, owner_user_id, job_template, timezone, cron_expression, interval_seconds, enabled, next_run_at, last_run_at, concurrency_policy, misfire_policy, approval_policy, budget_policy, provider_policy, failure_policy, version, archived, created_at, updated_at) FROM stdin;
40b37ae5-1596-4a99-8859-76e7c022769f	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	{"job_type": "immediate_success"}	UTC	\N	3600	t	2026-09-25 15:42:35.292807+00	2026-09-25 14:42:35.292807+00	{"max_concurrent": 3}	skip	{}	{}	{}	{}	schedule-1.0.0	f	2026-09-25 13:42:40.292832+00	2026-09-25 14:51:12.049017+00
eb43ac8b-9092-41cd-916e-7029f677874d	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	{"job_type": "immediate_success"}	UTC	\N	3600	t	2026-09-25 15:42:52.427134+00	2026-09-25 14:42:52.427134+00	{"max_concurrent": 3}	skip	{}	{}	{}	{}	schedule-1.0.0	f	2026-09-25 13:42:57.42716+00	2026-09-25 14:51:12.084085+00
6c5ed8fa-7912-4a20-8cc0-952cd2522db7	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	{"job_type": "immediate_success"}	UTC	\N	3600	t	2026-09-25 15:43:23.199997+00	2026-09-25 14:43:23.199997+00	{"max_concurrent": 3}	skip	{}	{}	{}	{}	schedule-1.0.0	f	2026-09-25 13:43:28.200025+00	2026-09-25 14:51:12.117989+00
8615ca91-de1c-49ea-85ea-74bede8ae9b8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	{"job_type": "immediate_success"}	UTC	\N	3600	t	2026-09-25 15:43:39.275532+00	2026-09-25 14:43:39.275532+00	{"max_concurrent": 3}	skip	{}	{}	{}	{}	schedule-1.0.0	f	2026-09-25 13:43:44.275559+00	2026-09-25 14:51:12.150409+00
a25e0083-a2f2-4347-8cc3-297c6b6c3bc7	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	{"job_type": "immediate_success"}	UTC	\N	3600	t	2026-09-25 15:47:36.370345+00	2026-09-25 14:47:36.370345+00	{"max_concurrent": 3}	skip	{}	{}	{}	{}	schedule-1.0.0	f	2026-09-25 12:47:41.37037+00	2026-09-25 14:51:12.181406+00
6415cb76-6249-46ad-9649-30d1025ba72c	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	{"job_type": "immediate_success"}	UTC	\N	3600	t	2026-09-25 15:48:00.349508+00	2026-09-25 14:48:00.349508+00	{"max_concurrent": 3}	skip	{}	{}	{}	{}	schedule-1.0.0	f	2026-09-25 12:48:05.349532+00	2026-09-25 14:51:12.213888+00
71f8100f-4b51-4cca-8006-1c767079361e	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	{"job_type": "immediate_success"}	UTC	\N	3600	t	2026-09-25 15:51:07.007024+00	2026-09-25 14:51:07.007024+00	{"max_concurrent": 3}	skip	{}	{}	{}	{}	schedule-1.0.0	f	2026-09-25 14:51:12.007053+00	2026-09-25 14:51:12.245013+00
af6eb320-1eb3-4f10-9b63-67960864a378	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	{"job_type": "immediate_success"}	UTC	\N	3600	t	2026-09-25 15:53:48.009537+00	2026-09-25 14:53:48.009537+00	{"max_concurrent": 3}	skip	{}	{}	{}	{}	schedule-1.0.0	f	2026-09-25 14:53:53.009562+00	2026-09-25 14:53:53.048195+00
9e1827ad-dcba-457c-bc05-5168a0f220c8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	{"job_type": "immediate_success"}	UTC	\N	3600	t	2026-09-25 16:11:38.982073+00	2026-09-25 15:11:38.982073+00	{"max_concurrent": 3}	skip	{}	{}	{}	{}	schedule-1.0.0	f	2026-09-25 14:11:43.9821+00	2026-09-25 15:37:31.939329+00
74ed46b8-b272-49cb-ad05-9e8083fb1c8c	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	{"job_type": "immediate_success"}	UTC	\N	3600	t	2026-09-25 16:37:26.923883+00	2026-09-25 15:37:26.923883+00	{"max_concurrent": 3}	skip	{}	{}	{}	{}	schedule-1.0.0	f	2026-09-25 15:37:31.923907+00	2026-09-25 15:37:31.97707+00
4084524a-06b2-4b3f-b010-48fff44e98cb	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	{"job_type": "immediate_success"}	UTC	\N	3600	t	2026-09-25 16:37:59.371396+00	2026-09-25 15:37:59.371396+00	{"max_concurrent": 3}	skip	{}	{}	{}	{}	schedule-1.0.0	f	2026-09-25 15:38:04.371426+00	2026-09-25 15:38:04.414663+00
919354fc-10e9-42d6-a254-c88d1c47bf15	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	{"job_type": "immediate_success"}	UTC	\N	3600	t	2026-09-25 16:39:10.542065+00	2026-09-25 15:39:10.542065+00	{"max_concurrent": 3}	skip	{}	{}	{}	{}	schedule-1.0.0	f	2026-09-25 15:39:15.542095+00	2026-09-25 15:39:15.582407+00
81728559-dc82-414e-aa1e-e737ebf2818a	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	{"job_type": "immediate_success"}	UTC	\N	3600	t	2026-09-25 16:39:45.488996+00	2026-09-25 15:39:45.488996+00	{"max_concurrent": 3}	skip	{}	{}	{}	{}	schedule-1.0.0	f	2026-09-25 15:39:50.489022+00	2026-09-25 15:39:50.527425+00
\.


--
-- Data for Name: job_state_history; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.job_state_history (id, job_id, run_id, previous_state, new_state, actor, reason, correlation_id, audit_event_ref, occurred_at) FROM stdin;
97d0f872-12c3-4968-a6a6-f65b6df224df	2d56906f-32ab-438b-a817-f8baef2559f0	221d84bc-4761-4991-a5aa-acbe38c1e303	(created)	draft	system	submission created	\N	\N	2026-09-25 12:47:41.123752+00
59d21f8a-b063-423a-8e0f-06b9141168d8	2d56906f-32ab-438b-a817-f8baef2559f0	221d84bc-4761-4991-a5aa-acbe38c1e303	draft	queued	requestor	submitted	\N	4247fdef-7845-4b3a-8de8-bfd8a8414ea8	2026-09-25 12:47:41.127476+00
771d2f69-ed0c-48e3-84fe-e6a6ea8abbf8	2d56906f-32ab-438b-a817-f8baef2559f0	221d84bc-4761-4991-a5aa-acbe38c1e303	queued	leased	worker	claimed by staging-smoke-worker	\N	18aa9de4-ee85-40a4-be24-6b4ffcb10ae4	2026-09-25 12:47:41.147672+00
49bc54fd-a133-49bb-ad70-71d5d3c5f122	2d56906f-32ab-438b-a817-f8baef2559f0	221d84bc-4761-4991-a5aa-acbe38c1e303	leased	running	worker	execution started	\N	edd12928-8516-4cf5-a2a3-3d8b5a287c56	2026-09-25 12:47:41.167298+00
a49d4243-27c5-446b-b614-10df1db73b2a	2d56906f-32ab-438b-a817-f8baef2559f0	221d84bc-4761-4991-a5aa-acbe38c1e303	running	succeeded	worker	handler success	\N	e9e4570c-13e6-43b3-a74e-e6cc225d6839	2026-09-25 12:47:41.192187+00
88f98aec-6bfc-4444-853a-39562e2567fa	1faed168-4681-4d21-9407-62ac9f955cda	e921643e-db91-4827-969e-ed3ef02faf92	(created)	draft	system	submission created	\N	\N	2026-09-25 12:47:41.220513+00
e796c3ff-f81a-4617-856a-99a53f1ad2b1	1faed168-4681-4d21-9407-62ac9f955cda	e921643e-db91-4827-969e-ed3ef02faf92	draft	queued	requestor	submitted	\N	8ad1f3d3-5d95-43c4-b4c2-413e6c56408a	2026-09-25 12:47:41.224734+00
90ffd649-73f9-4910-bb5f-2253a9f65aac	1faed168-4681-4d21-9407-62ac9f955cda	e921643e-db91-4827-969e-ed3ef02faf92	queued	leased	worker	claimed by staging-smoke-worker	\N	3e614159-9654-4ed0-8111-7cad9a5808c3	2026-09-25 12:47:41.2432+00
2717de20-34e1-4f05-983c-cddd922bedbf	1faed168-4681-4d21-9407-62ac9f955cda	e921643e-db91-4827-969e-ed3ef02faf92	leased	running	worker	execution started	\N	99ce140d-4abc-4e0e-8ff3-4c925c826f89	2026-09-25 12:47:41.260821+00
b899fcd4-5ea3-427f-a967-959228403de7	1faed168-4681-4d21-9407-62ac9f955cda	e921643e-db91-4827-969e-ed3ef02faf92	running	retry_wait	worker	retryable transient_error	\N	6daca6be-4441-4f18-9c86-ab2cf4da4ac2	2026-09-25 12:47:41.284189+00
399a72de-2356-4d49-9974-9f36b25a97ac	1faed168-4681-4d21-9407-62ac9f955cda	e921643e-db91-4827-969e-ed3ef02faf92	retry_wait	queued	scheduler	backoff elapsed	\N	a132d13c-c027-41d2-afba-93455fed1cda	2026-09-25 12:47:41.304672+00
be5d73ee-fe9f-4bb7-b2d4-1ee4b109aad4	1faed168-4681-4d21-9407-62ac9f955cda	e921643e-db91-4827-969e-ed3ef02faf92	queued	leased	worker	claimed by staging-smoke-worker	\N	36620faa-dba7-414c-98cd-a96b3087b4dc	2026-09-25 12:47:41.317982+00
57ca851c-9722-4add-b6b9-be890b10fe50	1faed168-4681-4d21-9407-62ac9f955cda	e921643e-db91-4827-969e-ed3ef02faf92	leased	running	worker	execution started	\N	38f44dcf-6a31-42b2-9c97-e400f7762959	2026-09-25 12:47:41.333093+00
f4503edb-3484-43dc-b234-4c819777f39a	1faed168-4681-4d21-9407-62ac9f955cda	e921643e-db91-4827-969e-ed3ef02faf92	running	succeeded	worker	handler success	\N	cdff6b3b-914c-4b89-b429-7e2d32d7039e	2026-09-25 12:47:41.353979+00
2175c875-5cd5-4463-ad2a-0738a8b159a7	bb7b2f11-44e3-44ca-8749-c6a56ee4051d	870cad35-bcfe-42cc-ad93-accbc0ee6838	(created)	draft	system	submission created	2026-09-25T12:47:36.370345+00:00	\N	2026-09-25 12:47:41.391006+00
5797ff50-8be4-41da-bb7c-885765d20afb	bb7b2f11-44e3-44ca-8749-c6a56ee4051d	870cad35-bcfe-42cc-ad93-accbc0ee6838	draft	queued	requestor	submitted	2026-09-25T12:47:36.370345+00:00	0f6e2670-0e48-413c-b5f6-85697a765e3a	2026-09-25 12:47:41.394125+00
51dc3f0e-91da-43a9-87cf-9bd2608a2146	3cee773e-9b1c-484f-8538-4bc9d37773d5	f1475883-1c5b-4903-aaaf-b5749f2bbbf6	(created)	draft	system	submission created	\N	\N	2026-09-25 12:48:05.071267+00
8c705475-0118-477f-b337-0df1aab5c723	3cee773e-9b1c-484f-8538-4bc9d37773d5	f1475883-1c5b-4903-aaaf-b5749f2bbbf6	draft	queued	requestor	submitted	\N	d3554f3e-85d8-4d94-8278-6f23b6a3fa68	2026-09-25 12:48:05.074287+00
ed4f035d-e639-41fa-b21f-5fa6cd2bcfd6	bb7b2f11-44e3-44ca-8749-c6a56ee4051d	870cad35-bcfe-42cc-ad93-accbc0ee6838	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T12:47:36.370345+00:00	2e235d7e-566d-46d6-9fa5-d48803e5e8b7	2026-09-25 12:48:05.099972+00
ce3f53fe-9f19-4373-865c-ec9f696b98c3	bb7b2f11-44e3-44ca-8749-c6a56ee4051d	870cad35-bcfe-42cc-ad93-accbc0ee6838	leased	running	worker	execution started	2026-09-25T12:47:36.370345+00:00	da2fd708-40bb-4421-97e1-b495160ef17a	2026-09-25 12:48:05.113873+00
0d88ba06-a5e2-4906-af8c-08c3c141a13c	bb7b2f11-44e3-44ca-8749-c6a56ee4051d	870cad35-bcfe-42cc-ad93-accbc0ee6838	running	succeeded	worker	handler success	2026-09-25T12:47:36.370345+00:00	5becec8f-51d8-4168-accd-cf6f8e03d142	2026-09-25 12:48:05.133498+00
6b92cbae-88b1-4782-a7fc-8e5980d827d0	3cee773e-9b1c-484f-8538-4bc9d37773d5	f1475883-1c5b-4903-aaaf-b5749f2bbbf6	queued	leased	worker	claimed by staging-smoke-worker	\N	218f81e9-2f23-4e52-875d-4fdaac771e2a	2026-09-25 12:48:05.14698+00
ea9b3ab1-22ae-4f9f-b58a-d4d231996f55	3cee773e-9b1c-484f-8538-4bc9d37773d5	f1475883-1c5b-4903-aaaf-b5749f2bbbf6	leased	running	worker	execution started	\N	0310e97c-9205-476d-9cc3-42e31369bfba	2026-09-25 12:48:05.16219+00
34e23137-bfa5-400e-be9b-1f4cf94a88bc	3cee773e-9b1c-484f-8538-4bc9d37773d5	f1475883-1c5b-4903-aaaf-b5749f2bbbf6	running	succeeded	worker	handler success	\N	5525c6c0-5276-4c60-9c81-4a574e04016f	2026-09-25 12:48:05.182369+00
8eb9f989-713b-4d6b-a239-519ea2c89173	95d4a73e-2173-489d-ab2c-9857472049de	63dcf6f3-2062-4538-80ce-d6b57683b3e8	(created)	draft	system	submission created	\N	\N	2026-09-25 12:48:05.20843+00
8ad4ea87-b72e-4508-b76c-f05de9737bef	95d4a73e-2173-489d-ab2c-9857472049de	63dcf6f3-2062-4538-80ce-d6b57683b3e8	draft	queued	requestor	submitted	\N	af2992ee-82e3-446d-b597-b6d04f0ddc06	2026-09-25 12:48:05.211431+00
bfd78e3f-77c6-44fc-b95f-618825adb68e	95d4a73e-2173-489d-ab2c-9857472049de	63dcf6f3-2062-4538-80ce-d6b57683b3e8	queued	leased	worker	claimed by staging-smoke-worker	\N	0f19f210-7a57-4ea8-9153-ef0e34698691	2026-09-25 12:48:05.228857+00
63f18618-e49d-4ac3-b6e4-740d9df47813	95d4a73e-2173-489d-ab2c-9857472049de	63dcf6f3-2062-4538-80ce-d6b57683b3e8	leased	running	worker	execution started	\N	3d46d539-087d-4e43-be98-c12e665689f4	2026-09-25 12:48:05.244578+00
4bdca763-d30d-42c5-9023-fd039658899a	95d4a73e-2173-489d-ab2c-9857472049de	63dcf6f3-2062-4538-80ce-d6b57683b3e8	running	retry_wait	worker	retryable transient_error	\N	1f4deb3e-2dd2-4bab-96ba-da2bab806275	2026-09-25 12:48:05.267511+00
77f716a5-9130-4a0f-a738-c4963dc944f6	95d4a73e-2173-489d-ab2c-9857472049de	63dcf6f3-2062-4538-80ce-d6b57683b3e8	retry_wait	queued	scheduler	backoff elapsed	\N	efbcf485-813c-4bf3-96cb-e246616c8bb4	2026-09-25 12:48:05.287139+00
1ecff654-318f-4ccc-b79d-8fa5d2937a85	95d4a73e-2173-489d-ab2c-9857472049de	63dcf6f3-2062-4538-80ce-d6b57683b3e8	queued	leased	worker	claimed by staging-smoke-worker	\N	d93ef76f-79b9-43c8-99af-241cdb2f419d	2026-09-25 12:48:05.300896+00
46930889-81d5-4707-8bea-2af994d28a74	95d4a73e-2173-489d-ab2c-9857472049de	63dcf6f3-2062-4538-80ce-d6b57683b3e8	leased	running	worker	execution started	\N	7cfed139-0c5e-4c9f-a958-8ca2e4955045	2026-09-25 12:48:05.316704+00
647c6737-12bb-4a2f-9f05-80393d7ea602	95d4a73e-2173-489d-ab2c-9857472049de	63dcf6f3-2062-4538-80ce-d6b57683b3e8	running	succeeded	worker	handler success	\N	ed594459-e45f-40e9-84fd-1a455c0f6404	2026-09-25 12:48:05.334594+00
b40337dc-8811-481b-9e13-7ac15c8ce8ef	a9ee27a7-5545-4d87-a365-1474d10a102b	85f3b973-6cdd-4c00-8f18-b09d72226c07	(created)	draft	system	submission created	2026-09-25T12:48:00.349508+00:00	\N	2026-09-25 12:48:05.366462+00
14c0c615-8418-4460-a137-b268d924ada1	a9ee27a7-5545-4d87-a365-1474d10a102b	85f3b973-6cdd-4c00-8f18-b09d72226c07	draft	queued	requestor	submitted	2026-09-25T12:48:00.349508+00:00	952828f9-8361-4011-94d3-6cca4f2ee97b	2026-09-25 12:48:05.369764+00
808e0550-2ea8-4493-9393-98337385c9a3	cc39a661-801a-42f2-9ccc-b0ef2f10137e	bcb65321-4548-465f-983f-9cd42242069b	(created)	draft	system	submission created	\N	\N	2026-09-25 13:42:40.015126+00
469a987b-47d2-49b2-9504-2f832539012c	cc39a661-801a-42f2-9ccc-b0ef2f10137e	bcb65321-4548-465f-983f-9cd42242069b	draft	queued	requestor	submitted	\N	3f088773-de62-42e6-8672-10be1298c3a8	2026-09-25 13:42:40.019796+00
3501a479-9849-4141-b72d-ad6b7d71cbcc	a9ee27a7-5545-4d87-a365-1474d10a102b	85f3b973-6cdd-4c00-8f18-b09d72226c07	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T12:48:00.349508+00:00	0ef6aa9c-031c-4f95-aa95-4ab609a8a315	2026-09-25 13:42:40.038946+00
3d440a3f-1631-4e4b-aa80-fa68a7affb22	a9ee27a7-5545-4d87-a365-1474d10a102b	85f3b973-6cdd-4c00-8f18-b09d72226c07	leased	running	worker	execution started	2026-09-25T12:48:00.349508+00:00	3697c2df-8716-463b-be4f-879a26d94ccb	2026-09-25 13:42:40.053143+00
9ee02280-287b-4c69-a674-3b98e639f6f3	a9ee27a7-5545-4d87-a365-1474d10a102b	85f3b973-6cdd-4c00-8f18-b09d72226c07	running	succeeded	worker	handler success	2026-09-25T12:48:00.349508+00:00	11672b73-b3ff-4d6a-a4e2-e91ca78588fa	2026-09-25 13:42:40.07798+00
7dd66350-100a-477b-99e0-64a7836e92df	cc39a661-801a-42f2-9ccc-b0ef2f10137e	bcb65321-4548-465f-983f-9cd42242069b	queued	leased	worker	claimed by staging-smoke-worker	\N	8f9655ac-a867-48bc-a258-01553f8427f2	2026-09-25 13:42:40.092317+00
de2a5b98-95e4-46ab-9a3a-33379a18f494	cc39a661-801a-42f2-9ccc-b0ef2f10137e	bcb65321-4548-465f-983f-9cd42242069b	leased	running	worker	execution started	\N	eb6d1704-4584-49aa-9c34-8bf24e49dbeb	2026-09-25 13:42:40.108181+00
ce1ff8c4-7e78-4dd7-a109-57cfa63c78ac	cc39a661-801a-42f2-9ccc-b0ef2f10137e	bcb65321-4548-465f-983f-9cd42242069b	running	succeeded	worker	handler success	\N	fde7b0b4-629f-42af-abc4-b2ce14a87936	2026-09-25 13:42:40.12778+00
19e21881-a5a6-4971-8ea4-26a17c5d3e1f	dee8ad4e-8fe6-40e3-885f-d83b287d400d	028df412-3cd1-4027-9484-8e2677da0df2	(created)	draft	system	submission created	\N	\N	2026-09-25 13:42:40.157161+00
1cdefe64-e9f7-4cd2-b57e-6d644925eede	dee8ad4e-8fe6-40e3-885f-d83b287d400d	028df412-3cd1-4027-9484-8e2677da0df2	draft	queued	requestor	submitted	\N	8f30c6d1-01a4-44a8-b05f-8c6c9c4966e5	2026-09-25 13:42:40.160066+00
9b2dd862-a597-4d1b-91a3-ac988b26f537	dee8ad4e-8fe6-40e3-885f-d83b287d400d	028df412-3cd1-4027-9484-8e2677da0df2	queued	leased	worker	claimed by staging-smoke-worker	\N	fc3709b0-5ac4-4e02-a827-07bd1c9a0daf	2026-09-25 13:42:40.177237+00
e82a33d8-1ed2-4b56-9bc2-d7d4d82bce37	dee8ad4e-8fe6-40e3-885f-d83b287d400d	028df412-3cd1-4027-9484-8e2677da0df2	leased	running	worker	execution started	\N	143e1962-a217-474b-9f85-46f96e42b917	2026-09-25 13:42:40.194448+00
a364accb-bbac-4ab3-8a08-114930034515	dee8ad4e-8fe6-40e3-885f-d83b287d400d	028df412-3cd1-4027-9484-8e2677da0df2	running	retry_wait	worker	retryable transient_error	\N	2bb491cb-fa91-4deb-ad80-049303f80474	2026-09-25 13:42:40.211538+00
b6cb0f57-85a9-4500-a9fd-f2f7d4db6cbf	dee8ad4e-8fe6-40e3-885f-d83b287d400d	028df412-3cd1-4027-9484-8e2677da0df2	retry_wait	queued	scheduler	backoff elapsed	\N	9f8079eb-fd6b-4b60-8792-813162539e74	2026-09-25 13:42:40.233096+00
24c9db2f-4a39-4c0c-a299-67b8aa3d03a0	dee8ad4e-8fe6-40e3-885f-d83b287d400d	028df412-3cd1-4027-9484-8e2677da0df2	queued	leased	worker	claimed by staging-smoke-worker	\N	eef15844-711d-47a8-9292-bece232a3437	2026-09-25 13:42:40.246313+00
eaaee181-1f65-42a2-a2a5-e68041e103ad	dee8ad4e-8fe6-40e3-885f-d83b287d400d	028df412-3cd1-4027-9484-8e2677da0df2	leased	running	worker	execution started	\N	107bfd72-dd19-48cc-a371-49f335463858	2026-09-25 13:42:40.260125+00
5e5cffd8-c1d1-4a9e-9c6b-51ff772cf92c	dee8ad4e-8fe6-40e3-885f-d83b287d400d	028df412-3cd1-4027-9484-8e2677da0df2	running	succeeded	worker	handler success	\N	dc854957-0a98-4b94-9fcc-428d74b88c1d	2026-09-25 13:42:40.27739+00
795b6a7b-6aef-4e95-926f-bd3ae34c8ea0	04619a31-fada-4f30-8428-e85428a36d62	013e1cd7-ca06-4dd8-85be-8475bde12d48	(created)	draft	system	submission created	2026-09-25T13:42:35.292807+00:00	\N	2026-09-25 13:42:40.313124+00
a7436cba-b376-47f8-a955-c648459a407b	04619a31-fada-4f30-8428-e85428a36d62	013e1cd7-ca06-4dd8-85be-8475bde12d48	draft	queued	requestor	submitted	2026-09-25T13:42:35.292807+00:00	8e863da3-2429-4646-83af-edc6fa9e0561	2026-09-25 13:42:40.316408+00
be436d6b-1ded-4159-a3cc-0e56d05994b8	cfaf79d9-8e96-4764-a652-19f2f2179004	94137786-91d3-4086-8634-5da9968bd6c7	(created)	draft	system	submission created	\N	\N	2026-09-25 13:42:57.164908+00
9092b3b7-8b01-4bbf-ac69-7a12032a0d6c	cfaf79d9-8e96-4764-a652-19f2f2179004	94137786-91d3-4086-8634-5da9968bd6c7	draft	queued	requestor	submitted	\N	eb8913b7-768f-4554-a2c4-f1cd5d413215	2026-09-25 13:42:57.167988+00
de567242-fe32-47f8-b123-66c05a33fabc	04619a31-fada-4f30-8428-e85428a36d62	013e1cd7-ca06-4dd8-85be-8475bde12d48	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T13:42:35.292807+00:00	509b3717-8713-4757-a438-7d55d3bdc6fa	2026-09-25 13:42:57.186217+00
95838966-35ae-4ad5-8cbf-94e24600b59a	04619a31-fada-4f30-8428-e85428a36d62	013e1cd7-ca06-4dd8-85be-8475bde12d48	leased	running	worker	execution started	2026-09-25T13:42:35.292807+00:00	c79a8a27-f1f0-4a1f-a3f1-ea28a5303e30	2026-09-25 13:42:57.201157+00
e9624904-41ac-4251-8e42-8b76a53100cc	04619a31-fada-4f30-8428-e85428a36d62	013e1cd7-ca06-4dd8-85be-8475bde12d48	running	succeeded	worker	handler success	2026-09-25T13:42:35.292807+00:00	ebed6c91-4496-448e-81ea-fa0a74b6037d	2026-09-25 13:42:57.219874+00
f744b863-0c98-4567-84ae-9b6260f78bae	cfaf79d9-8e96-4764-a652-19f2f2179004	94137786-91d3-4086-8634-5da9968bd6c7	queued	leased	worker	claimed by staging-smoke-worker	\N	d30ee745-d657-46ba-b183-7428bccf928d	2026-09-25 13:42:57.233239+00
0742a7fa-2c71-4ef1-838f-3384e2810b2e	cfaf79d9-8e96-4764-a652-19f2f2179004	94137786-91d3-4086-8634-5da9968bd6c7	leased	running	worker	execution started	\N	0c3667fa-ca8f-4ea1-a3f6-a564bfbacb07	2026-09-25 13:42:57.247788+00
c4499d3e-b89d-43db-82d1-a4c129893241	cfaf79d9-8e96-4764-a652-19f2f2179004	94137786-91d3-4086-8634-5da9968bd6c7	running	succeeded	worker	handler success	\N	64e6b135-dce2-498b-947a-91935c3b1866	2026-09-25 13:42:57.267474+00
0439deea-fe46-428d-a7d6-6927516d16e9	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	7a353e29-dc66-4086-9aa8-64174efe554d	(created)	draft	system	submission created	\N	\N	2026-09-25 13:42:57.294374+00
59ebb2a1-68ef-4846-8d1e-4514426348d1	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	7a353e29-dc66-4086-9aa8-64174efe554d	draft	queued	requestor	submitted	\N	68dd6758-f5a9-42b4-9603-f44dc967163c	2026-09-25 13:42:57.297451+00
447d56e6-3311-4e76-956c-6a3ef460bf06	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	7a353e29-dc66-4086-9aa8-64174efe554d	queued	leased	worker	claimed by staging-smoke-worker	\N	f296de71-a9fd-498e-8626-a8663ce3eced	2026-09-25 13:42:57.315039+00
3834585b-7a05-47d3-86a4-fb80d0b49c42	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	7a353e29-dc66-4086-9aa8-64174efe554d	leased	running	worker	execution started	\N	73f546d8-5dc9-4012-97fa-42d2964bd766	2026-09-25 13:42:57.329528+00
092b8819-e559-414f-aa7f-b716d93f07c5	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	7a353e29-dc66-4086-9aa8-64174efe554d	running	retry_wait	worker	retryable transient_error	\N	bd8cdfe1-dd0f-47d7-a1fc-d28ec083d53e	2026-09-25 13:42:57.346478+00
b6f92eab-a354-489d-9062-8f1b13355acd	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	7a353e29-dc66-4086-9aa8-64174efe554d	retry_wait	queued	scheduler	backoff elapsed	\N	2a1f6838-214b-421b-a409-6f60435e6fc2	2026-09-25 13:42:57.366071+00
25141ffb-6a15-417b-bafb-d221a0f1f8e4	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	7a353e29-dc66-4086-9aa8-64174efe554d	queued	leased	worker	claimed by staging-smoke-worker	\N	9abc7ad1-6617-4e7a-a609-3de11e82e419	2026-09-25 13:42:57.378457+00
84b33fae-004a-4b74-bff1-220592de302c	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	7a353e29-dc66-4086-9aa8-64174efe554d	leased	running	worker	execution started	\N	9b201cd6-6d15-474e-9d29-883375c8a881	2026-09-25 13:42:57.392674+00
95c419b6-8490-490b-8add-5bb42f5852b9	81780c14-5eee-4ff2-ae7f-1ac52fe951f8	7a353e29-dc66-4086-9aa8-64174efe554d	running	succeeded	worker	handler success	\N	0ca8227e-740c-46e7-82a3-e2780fb669c8	2026-09-25 13:42:57.411145+00
d4cccdf9-d3e2-40fc-9bf4-f1bb4af0a011	74e79cff-759d-4806-b22c-c13f230ff015	891c1282-c650-4b2f-9b9c-4e4bec3eb150	(created)	draft	system	submission created	2026-09-25T13:42:52.427134+00:00	\N	2026-09-25 13:42:57.445573+00
6a537a49-23b1-483f-ba48-d190c1b1733c	74e79cff-759d-4806-b22c-c13f230ff015	891c1282-c650-4b2f-9b9c-4e4bec3eb150	draft	queued	requestor	submitted	2026-09-25T13:42:52.427134+00:00	f3e6c5f6-9afb-442f-ba5e-4537db50f62a	2026-09-25 13:42:57.448305+00
f0e8813e-41a4-4c25-9a9a-5b8cc48d403b	ece8ac3a-1061-486c-a849-7574c872926d	189021bf-e92f-456e-933d-577fb90e6ae2	(created)	draft	system	submission created	staging-req-chain-1	\N	2026-09-25 13:42:57.556325+00
aab6f9d8-33b2-45a8-aab0-efa1afd1f4a2	ece8ac3a-1061-486c-a849-7574c872926d	189021bf-e92f-456e-933d-577fb90e6ae2	draft	queued	requestor	submitted	staging-req-chain-1	9c3c2c8e-bceb-4114-8309-0ef8bd6ccdc6	2026-09-25 13:42:57.559165+00
7f1497f9-9752-41fc-899a-ae1fea30def3	74e79cff-759d-4806-b22c-c13f230ff015	891c1282-c650-4b2f-9b9c-4e4bec3eb150	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T13:42:52.427134+00:00	f2fddf15-3c4e-414e-b335-52c424fac30a	2026-09-25 13:42:57.574927+00
a8dbafdf-d974-4302-929e-4de9027812cc	74e79cff-759d-4806-b22c-c13f230ff015	891c1282-c650-4b2f-9b9c-4e4bec3eb150	leased	running	worker	execution started	2026-09-25T13:42:52.427134+00:00	efde55b3-c579-4ff9-a22d-26e4548927e1	2026-09-25 13:42:57.589202+00
ce685ac7-cec0-4eee-aebc-caa8c44d360e	74e79cff-759d-4806-b22c-c13f230ff015	891c1282-c650-4b2f-9b9c-4e4bec3eb150	running	succeeded	worker	handler success	2026-09-25T13:42:52.427134+00:00	eb9084ed-0c95-40cb-972c-5099fad07579	2026-09-25 13:42:57.607934+00
203b89a5-0e4c-4a09-b6c6-2f1de2718ad5	ece8ac3a-1061-486c-a849-7574c872926d	189021bf-e92f-456e-933d-577fb90e6ae2	queued	leased	worker	claimed by staging-smoke-worker	staging-req-chain-1	d222023d-567f-4180-8d30-cd4bdadfdd17	2026-09-25 13:42:57.622835+00
7a6e9643-abd4-403a-900d-f9e37f12ccd3	ece8ac3a-1061-486c-a849-7574c872926d	189021bf-e92f-456e-933d-577fb90e6ae2	leased	running	worker	execution started	staging-req-chain-1	247e37ed-0145-434f-911e-3a8f5c5a55bb	2026-09-25 13:42:57.638513+00
d92c256c-8c44-476b-b439-5374daf1ca47	ece8ac3a-1061-486c-a849-7574c872926d	189021bf-e92f-456e-933d-577fb90e6ae2	running	succeeded	worker	handler success	staging-req-chain-1	1af5550d-0ee9-4f5f-b712-41f9a8ac1465	2026-09-25 13:42:57.658874+00
5bc24d41-2560-4699-ac3f-c14c0d8b5ba8	6ce89210-9d7b-4ef2-a460-7936e37861e9	2ed07a3f-a742-484d-9f51-295bf3c16c52	(created)	draft	system	submission created	\N	\N	2026-09-25 13:43:27.93224+00
8ed451f7-01a7-4e6a-8e6c-f378e26b8202	6ce89210-9d7b-4ef2-a460-7936e37861e9	2ed07a3f-a742-484d-9f51-295bf3c16c52	draft	queued	requestor	submitted	\N	964915b9-75a4-4a60-9229-3889c8fcafcb	2026-09-25 13:43:27.935358+00
4d8d4300-05e1-4ab7-97f8-57b4b9dfcc00	6ce89210-9d7b-4ef2-a460-7936e37861e9	2ed07a3f-a742-484d-9f51-295bf3c16c52	queued	leased	worker	claimed by staging-smoke-worker	\N	7da5166b-0a2a-4280-9392-6e2324f54fe5	2026-09-25 13:43:27.953494+00
8d15cb9d-af0c-476c-b0c5-dd926c4ec5f8	6ce89210-9d7b-4ef2-a460-7936e37861e9	2ed07a3f-a742-484d-9f51-295bf3c16c52	leased	running	worker	execution started	\N	2e6f53ce-2715-47fa-8d26-90afb48f6c1f	2026-09-25 13:43:27.968267+00
f13edffe-ef4c-46c5-aef9-5f2557d39eec	6ce89210-9d7b-4ef2-a460-7936e37861e9	2ed07a3f-a742-484d-9f51-295bf3c16c52	running	succeeded	worker	handler success	\N	073a2299-91ef-47fe-9041-02393d719f0d	2026-09-25 13:43:27.986371+00
067e77b8-938b-4584-afe0-556be4e85d6c	dde1681c-6f4e-4219-97c2-06d1154c7067	6f656618-35bd-4f97-952b-1a5c832d1f8b	(created)	draft	system	submission created	\N	\N	2026-09-25 13:43:28.017476+00
7aa2ed58-aa68-4ca7-9ef2-42f2bf75a0b0	dde1681c-6f4e-4219-97c2-06d1154c7067	6f656618-35bd-4f97-952b-1a5c832d1f8b	draft	queued	requestor	submitted	\N	7840faed-fb44-4dfc-89d1-69c124051363	2026-09-25 13:43:28.022217+00
44c95f71-2c9a-44ac-981e-17a2adb14adc	dde1681c-6f4e-4219-97c2-06d1154c7067	6f656618-35bd-4f97-952b-1a5c832d1f8b	queued	leased	worker	claimed by staging-smoke-worker	\N	9d1e1627-a098-42d3-b6bd-ff9d1bdef395	2026-09-25 13:43:28.041497+00
cb5c2030-f3bf-4cd1-bd51-6cc2cc4abf6d	dde1681c-6f4e-4219-97c2-06d1154c7067	6f656618-35bd-4f97-952b-1a5c832d1f8b	leased	running	worker	execution started	\N	bd2dbff1-1f91-4de7-ad62-77a6ec3276de	2026-09-25 13:43:28.057531+00
ad77e9eb-1ec9-45cd-ab04-2dcf0c42f783	dde1681c-6f4e-4219-97c2-06d1154c7067	6f656618-35bd-4f97-952b-1a5c832d1f8b	running	retry_wait	worker	retryable transient_error	\N	329da63f-babc-441e-8194-ed4bd2675a15	2026-09-25 13:43:28.080804+00
3c07d58e-7404-42f9-bfe9-36dacb84a21b	dde1681c-6f4e-4219-97c2-06d1154c7067	6f656618-35bd-4f97-952b-1a5c832d1f8b	retry_wait	queued	scheduler	backoff elapsed	\N	93b95f2e-62ab-4a24-810d-ce45993116a0	2026-09-25 13:43:28.115296+00
401df7b5-c5d1-4aee-9a11-1b51f12ec9e3	dde1681c-6f4e-4219-97c2-06d1154c7067	6f656618-35bd-4f97-952b-1a5c832d1f8b	queued	leased	worker	claimed by staging-smoke-worker	\N	aacefea9-9579-4124-8f7d-905d5e3637e5	2026-09-25 13:43:28.140825+00
8c58f8f2-4f45-4a48-b2dd-0728d04ef765	dde1681c-6f4e-4219-97c2-06d1154c7067	6f656618-35bd-4f97-952b-1a5c832d1f8b	leased	running	worker	execution started	\N	98db70af-d307-41cf-80ee-1e3f2bde9bd8	2026-09-25 13:43:28.16054+00
9fac2036-9d06-440d-bc8a-a8a39bfa68a0	dde1681c-6f4e-4219-97c2-06d1154c7067	6f656618-35bd-4f97-952b-1a5c832d1f8b	running	succeeded	worker	handler success	\N	24af19ef-c439-4232-a7a4-397cdd4a6d57	2026-09-25 13:43:28.181137+00
e53e087a-b479-466a-9637-7c4c43bc30b0	947d35bd-7f5e-4967-800c-e78b630cd423	c235be5f-e80d-4af6-983a-76c3d2a8df68	(created)	draft	system	submission created	2026-09-25T13:43:23.199997+00:00	\N	2026-09-25 13:43:28.222725+00
c5bc2696-79bb-4c57-9e64-8aabc31b8d92	947d35bd-7f5e-4967-800c-e78b630cd423	c235be5f-e80d-4af6-983a-76c3d2a8df68	draft	queued	requestor	submitted	2026-09-25T13:43:23.199997+00:00	4f09e674-1209-4733-97fc-9646e6723eec	2026-09-25 13:43:28.226478+00
910119d2-9644-478c-873e-ce603aa597ee	947d35bd-7f5e-4967-800c-e78b630cd423	c235be5f-e80d-4af6-983a-76c3d2a8df68	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T13:43:23.199997+00:00	7306581d-fee6-4bc7-8e1f-d06eafa92bf4	2026-09-25 13:43:28.328131+00
b878ca1d-4f18-49f6-9bc3-4369eeb59c50	947d35bd-7f5e-4967-800c-e78b630cd423	c235be5f-e80d-4af6-983a-76c3d2a8df68	leased	running	worker	execution started	2026-09-25T13:43:23.199997+00:00	6b2fd8d3-891b-452b-9948-5ddbca895186	2026-09-25 13:43:28.343842+00
3bc12eae-292b-4b32-9d41-ccc3c48bc362	947d35bd-7f5e-4967-800c-e78b630cd423	c235be5f-e80d-4af6-983a-76c3d2a8df68	running	succeeded	worker	handler success	2026-09-25T13:43:23.199997+00:00	78c8699f-5ca7-4bde-9a5b-b0f85fea4ca4	2026-09-25 13:43:28.363071+00
6cb7ebc9-6684-427a-8712-8629ac873184	40a0cbf9-f619-4bb5-a7eb-5cd23cf9dee1	8060967c-9d03-475f-a8ba-ecd05f59fa15	(created)	draft	system	submission created	\N	\N	2026-09-25 13:43:44.011851+00
a8d71f53-f6d7-453c-8ea6-ebb6f95e93a8	40a0cbf9-f619-4bb5-a7eb-5cd23cf9dee1	8060967c-9d03-475f-a8ba-ecd05f59fa15	draft	queued	requestor	submitted	\N	c1aea68c-8364-4b82-84c2-6a71976cb163	2026-09-25 13:43:44.015076+00
dcddb40a-e56f-4a3e-a535-8e065cbca158	40a0cbf9-f619-4bb5-a7eb-5cd23cf9dee1	8060967c-9d03-475f-a8ba-ecd05f59fa15	queued	leased	worker	claimed by staging-smoke-worker	\N	ee9ee080-18d2-4067-8d4f-3e2daa74bc2b	2026-09-25 13:43:44.068597+00
443e5743-393b-494d-bb64-cbecd6c524eb	40a0cbf9-f619-4bb5-a7eb-5cd23cf9dee1	8060967c-9d03-475f-a8ba-ecd05f59fa15	leased	running	worker	execution started	\N	348e0bbe-6f2d-4c0b-a12b-d82dca8cc509	2026-09-25 13:43:44.084166+00
d2e3de27-dc0c-485f-9905-b69e730105ee	40a0cbf9-f619-4bb5-a7eb-5cd23cf9dee1	8060967c-9d03-475f-a8ba-ecd05f59fa15	running	succeeded	worker	handler success	\N	2b405508-6ff3-4ca1-a50b-f058f0db138a	2026-09-25 13:43:44.104667+00
8eb5b65b-5fda-48e1-9193-1689275f3657	ecf21bd2-46ad-402b-9329-8c5cae2291e9	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	(created)	draft	system	submission created	\N	\N	2026-09-25 13:43:44.132667+00
9b249ac7-e60a-4720-8b3f-c3086a4295fd	ecf21bd2-46ad-402b-9329-8c5cae2291e9	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	draft	queued	requestor	submitted	\N	f9f9bb79-b8a9-4b6f-859b-93a52cf1bf78	2026-09-25 13:43:44.136484+00
73b9c36e-97f3-431f-bff1-e96b3fe8a76a	ecf21bd2-46ad-402b-9329-8c5cae2291e9	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	queued	leased	worker	claimed by staging-smoke-worker	\N	03ae59fb-126c-4976-a840-2a014e661230	2026-09-25 13:43:44.15429+00
de91d99b-0b98-427b-a84c-3bfb5a1c54fa	ecf21bd2-46ad-402b-9329-8c5cae2291e9	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	leased	running	worker	execution started	\N	dbbece5d-c3b3-48bb-84e9-d56c6a882745	2026-09-25 13:43:44.169891+00
770e5212-5f23-43f7-83ae-7e21de8216cd	ecf21bd2-46ad-402b-9329-8c5cae2291e9	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	running	retry_wait	worker	retryable transient_error	\N	c4af66b0-9dab-4f71-b8cf-9309f13e21a0	2026-09-25 13:43:44.186954+00
7a0370cd-7641-4173-b734-c1256de43bb1	ecf21bd2-46ad-402b-9329-8c5cae2291e9	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	retry_wait	queued	scheduler	backoff elapsed	\N	ffce3f19-32d8-49d9-85f3-08a47782681a	2026-09-25 13:43:44.20787+00
875f150b-17a3-447f-9481-3822dc4a819e	ecf21bd2-46ad-402b-9329-8c5cae2291e9	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	queued	leased	worker	claimed by staging-smoke-worker	\N	6353c145-f350-432a-9cfa-6d403d6bfe39	2026-09-25 13:43:44.22146+00
919b9fe0-1ec4-4717-b88b-80b0ead23b8a	ecf21bd2-46ad-402b-9329-8c5cae2291e9	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	leased	running	worker	execution started	\N	aa878488-7f3f-4c9e-bebf-0a0e76c1b8bf	2026-09-25 13:43:44.237168+00
5f220fdb-44f0-4ea6-a1e6-60f3f1400790	ecf21bd2-46ad-402b-9329-8c5cae2291e9	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	running	succeeded	worker	handler success	\N	abf9a387-055b-43d1-b4bb-d8982c021ae7	2026-09-25 13:43:44.256173+00
696e215f-a3a3-4604-a83e-6f869e9c43aa	c9ed2300-a06c-420f-b8fa-b45f0bd28d6b	980f46bb-1cda-4078-bb7f-a3d73c7b40d8	(created)	draft	system	submission created	2026-09-25T13:43:39.275532+00:00	\N	2026-09-25 13:43:44.29407+00
2679d291-ea78-4b6c-a59c-70f598237ca6	c9ed2300-a06c-420f-b8fa-b45f0bd28d6b	980f46bb-1cda-4078-bb7f-a3d73c7b40d8	draft	queued	requestor	submitted	2026-09-25T13:43:39.275532+00:00	cbeff72c-e6bf-4c8a-a8a4-e89c92fa61d8	2026-09-25 13:43:44.296935+00
1f818783-42c0-48d7-a960-b7d9c1068b79	c9ed2300-a06c-420f-b8fa-b45f0bd28d6b	980f46bb-1cda-4078-bb7f-a3d73c7b40d8	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T13:43:39.275532+00:00	497c43fd-135a-4e4b-ac0c-4baa5a5eb94f	2026-09-25 13:43:44.397434+00
44bc6cb3-9020-4cb6-863e-b6e373f43d38	c9ed2300-a06c-420f-b8fa-b45f0bd28d6b	980f46bb-1cda-4078-bb7f-a3d73c7b40d8	leased	running	worker	execution started	2026-09-25T13:43:39.275532+00:00	1ee6064e-5196-439c-add4-c72a02f40ebb	2026-09-25 13:43:44.410527+00
8928031f-68c9-4925-b07a-fd961e8e2773	c9ed2300-a06c-420f-b8fa-b45f0bd28d6b	980f46bb-1cda-4078-bb7f-a3d73c7b40d8	running	succeeded	worker	handler success	2026-09-25T13:43:39.275532+00:00	bf71b19e-4114-426b-b290-7e6d282c3976	2026-09-25 13:43:44.429108+00
59123dd1-5354-4031-8284-167d4294e829	de0a429b-9bcf-4d1d-9198-e1727b230d19	73e7f174-54ac-4d37-9f65-33c1608a6c2b	(created)	draft	system	submission created	\N	\N	2026-09-25 14:11:43.765742+00
06bcaf94-c3b1-4a88-acc5-64a3be1e3ab8	de0a429b-9bcf-4d1d-9198-e1727b230d19	73e7f174-54ac-4d37-9f65-33c1608a6c2b	draft	queued	requestor	submitted	\N	021e232c-772c-4335-8b75-57f59ea42bfe	2026-09-25 14:11:43.769936+00
b75aba1c-8c13-45fd-a16f-08d577872d3b	de0a429b-9bcf-4d1d-9198-e1727b230d19	73e7f174-54ac-4d37-9f65-33c1608a6c2b	queued	leased	worker	claimed by staging-smoke-worker	\N	5208c384-d23f-473a-b7cc-1ff33883a170	2026-09-25 14:11:43.788152+00
bb93b7ec-bb62-4de3-8728-0f86e7f3c0e1	de0a429b-9bcf-4d1d-9198-e1727b230d19	73e7f174-54ac-4d37-9f65-33c1608a6c2b	leased	running	worker	execution started	\N	3ed000b5-7780-42e0-9015-7455c7ee75a3	2026-09-25 14:11:43.805346+00
b2db2654-7c86-4556-8eb8-1e512fa793c2	de0a429b-9bcf-4d1d-9198-e1727b230d19	73e7f174-54ac-4d37-9f65-33c1608a6c2b	running	succeeded	worker	handler success	\N	08e83a4e-c52a-4414-b655-ace8f45f6506	2026-09-25 14:11:43.824671+00
d4cc6d2a-5d70-4dff-8f24-05e3bfa2b505	d942173e-b6cf-4f51-a3d3-996f6f083813	888e1f7b-6639-4463-b86f-c32ff1af4cc3	(created)	draft	system	submission created	\N	\N	2026-09-25 14:11:43.849997+00
c9833d20-62cf-48b0-bf79-5e1575d6ad2d	d942173e-b6cf-4f51-a3d3-996f6f083813	888e1f7b-6639-4463-b86f-c32ff1af4cc3	draft	queued	requestor	submitted	\N	fce94794-0b4d-4967-8ff9-9bb95a48a00c	2026-09-25 14:11:43.853457+00
f1eaa80c-fb9e-4b91-ad04-8bce1016be9d	d942173e-b6cf-4f51-a3d3-996f6f083813	888e1f7b-6639-4463-b86f-c32ff1af4cc3	queued	leased	worker	claimed by staging-smoke-worker	\N	f58cd622-8cc6-479c-8770-3db80935b7a1	2026-09-25 14:11:43.869968+00
e8703154-cb6c-4285-befb-0cdda2eeb2b9	d942173e-b6cf-4f51-a3d3-996f6f083813	888e1f7b-6639-4463-b86f-c32ff1af4cc3	leased	running	worker	execution started	\N	77fdcd3f-95a2-4bd2-b0e7-fdd6c0089e68	2026-09-25 14:11:43.885043+00
3ea42dc3-6f5b-4548-9f3f-862a0038136d	d942173e-b6cf-4f51-a3d3-996f6f083813	888e1f7b-6639-4463-b86f-c32ff1af4cc3	running	retry_wait	worker	retryable transient_error	\N	5e9a16e8-e535-4091-8d80-f5d9c4f59519	2026-09-25 14:11:43.902586+00
76c8c75d-f6d1-4507-81ff-f3dc78d62fba	d942173e-b6cf-4f51-a3d3-996f6f083813	888e1f7b-6639-4463-b86f-c32ff1af4cc3	retry_wait	queued	scheduler	backoff elapsed	\N	76662b07-1009-4c8c-bca4-ebc2c4ea4932	2026-09-25 14:11:43.922401+00
01b5d75a-f380-41b3-b1fb-5dd881f99d31	d942173e-b6cf-4f51-a3d3-996f6f083813	888e1f7b-6639-4463-b86f-c32ff1af4cc3	queued	leased	worker	claimed by staging-smoke-worker	\N	33022903-9f20-413a-8908-8a81947b62c6	2026-09-25 14:11:43.934963+00
93e866ed-d19d-4580-bc61-3b616317447b	d942173e-b6cf-4f51-a3d3-996f6f083813	888e1f7b-6639-4463-b86f-c32ff1af4cc3	leased	running	worker	execution started	\N	94bf3ef9-13d2-47a2-a8f1-e768ee37f472	2026-09-25 14:11:43.948662+00
973410d0-dda4-4a84-aa5f-6fd15113e001	d942173e-b6cf-4f51-a3d3-996f6f083813	888e1f7b-6639-4463-b86f-c32ff1af4cc3	running	succeeded	worker	handler success	\N	b21168e3-6efa-43c7-a364-1e6a6b0299ba	2026-09-25 14:11:43.966508+00
0e393f08-4f7e-4a40-8eab-31436b4eede3	a9c8bbb2-aded-4aaa-abaa-3ff70acbee4f	b7142c7b-501f-4b67-a1af-6bd40e5de64c	(created)	draft	system	submission created	2026-09-25T14:11:38.982073+00:00	\N	2026-09-25 14:11:44.018935+00
a698f39f-a019-4ac0-ac7f-2f3c98a00f6c	a9c8bbb2-aded-4aaa-abaa-3ff70acbee4f	b7142c7b-501f-4b67-a1af-6bd40e5de64c	draft	queued	requestor	submitted	2026-09-25T14:11:38.982073+00:00	2b443e6b-c3ef-4db6-ba79-7d274e16f5fb	2026-09-25 14:11:44.021702+00
29620946-6e78-4904-abdc-8da660b10a47	a9c8bbb2-aded-4aaa-abaa-3ff70acbee4f	b7142c7b-501f-4b67-a1af-6bd40e5de64c	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T14:11:38.982073+00:00	e4f8cd62-c5cc-425c-9214-06693bea1c4e	2026-09-25 14:11:44.123915+00
ecea9dfe-15f2-4ae2-9eec-5977dab8cb92	a9c8bbb2-aded-4aaa-abaa-3ff70acbee4f	b7142c7b-501f-4b67-a1af-6bd40e5de64c	leased	running	worker	execution started	2026-09-25T14:11:38.982073+00:00	e43651b1-b1bd-40d0-9951-df0c469e2d41	2026-09-25 14:11:44.138914+00
07d3d1f4-8992-479d-91a9-663bec1a7d00	a9c8bbb2-aded-4aaa-abaa-3ff70acbee4f	b7142c7b-501f-4b67-a1af-6bd40e5de64c	running	succeeded	worker	handler success	2026-09-25T14:11:38.982073+00:00	f2d77204-ef99-4902-89c4-6cb85958de8d	2026-09-25 14:11:44.16134+00
ef57fcd5-aa09-490c-bc38-498fa88513fd	2de868d1-6a42-4874-b6c4-08a6f521ee4e	18511b1c-101e-43aa-9811-2a3f0cac75e9	(created)	draft	system	submission created	\N	\N	2026-09-25 14:11:44.209717+00
78d697f0-0215-4720-a713-9474b6d11386	2de868d1-6a42-4874-b6c4-08a6f521ee4e	18511b1c-101e-43aa-9811-2a3f0cac75e9	draft	queued	requestor	submitted	\N	79cd5c40-e488-47f6-8379-d66d70a4eb9f	2026-09-25 14:11:44.213272+00
2395d1b0-35cf-43cd-9e18-9e9b9ab06a9b	a83672ad-6e70-4814-bd20-a28b34c34421	c6c4e85b-c433-4539-8baf-0b39ca813496	(created)	draft	system	submission created	\N	\N	2026-09-25 14:51:11.728082+00
91b7d291-3d3f-4cac-b058-69bc82805e9d	a83672ad-6e70-4814-bd20-a28b34c34421	c6c4e85b-c433-4539-8baf-0b39ca813496	draft	queued	requestor	submitted	\N	e4c645ec-a923-40e9-8bb6-54e0e0c6a98f	2026-09-25 14:51:11.732912+00
669804e5-20ff-4133-bca7-8e19e6de8803	2de868d1-6a42-4874-b6c4-08a6f521ee4e	18511b1c-101e-43aa-9811-2a3f0cac75e9	queued	leased	worker	claimed by staging-smoke-worker	\N	f7b1fa0e-ac31-4338-8c31-7207da5a21a9	2026-09-25 14:51:11.750853+00
cc38f084-61d7-4166-8a06-660eff1f05c9	2de868d1-6a42-4874-b6c4-08a6f521ee4e	18511b1c-101e-43aa-9811-2a3f0cac75e9	leased	running	worker	execution started	\N	a2b60184-980e-4dee-8cda-a288c084f459	2026-09-25 14:51:11.766349+00
6fa4e795-a7bf-4750-ae01-d8f508438a7c	2de868d1-6a42-4874-b6c4-08a6f521ee4e	18511b1c-101e-43aa-9811-2a3f0cac75e9	running	succeeded	worker	handler success	\N	cdb5bbd7-0bb3-4fb9-93e6-221d77423592	2026-09-25 14:51:11.78709+00
f179bb2f-62c1-43b1-a007-5b580b9697eb	a83672ad-6e70-4814-bd20-a28b34c34421	c6c4e85b-c433-4539-8baf-0b39ca813496	queued	leased	worker	claimed by staging-smoke-worker	\N	bbd084e3-55bb-466b-9011-5cb5fef628b4	2026-09-25 14:51:11.8007+00
25f20bb4-90f9-4b51-87ab-8d141b2328f4	a83672ad-6e70-4814-bd20-a28b34c34421	c6c4e85b-c433-4539-8baf-0b39ca813496	leased	running	worker	execution started	\N	294d5e68-b4bc-4fa6-b11c-9c7de9759555	2026-09-25 14:51:11.82117+00
7ba605d2-ebb0-4207-aef6-5f2c658304eb	a83672ad-6e70-4814-bd20-a28b34c34421	c6c4e85b-c433-4539-8baf-0b39ca813496	running	succeeded	worker	handler success	\N	ca86f2a4-0b2f-40c9-b4f5-ac7f01294291	2026-09-25 14:51:11.843159+00
ee9217a1-a157-4edb-bcea-2e7dea4d215a	33a7e677-b29a-4895-87f4-1a8b43a1e374	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	(created)	draft	system	submission created	\N	\N	2026-09-25 14:51:11.872704+00
29685ab4-da92-4236-af6c-4c291dafb541	33a7e677-b29a-4895-87f4-1a8b43a1e374	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	draft	queued	requestor	submitted	\N	63ecfced-605b-422c-b26a-4f9bc374dba0	2026-09-25 14:51:11.875811+00
6e10c7db-cfd8-409e-9549-7ec0f90cd042	33a7e677-b29a-4895-87f4-1a8b43a1e374	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	queued	leased	worker	claimed by staging-smoke-worker	\N	bfe3c59e-c8b9-4d32-9050-7318d0294417	2026-09-25 14:51:11.893837+00
22f8f374-8f4c-4cb5-99d7-2f0a737b6488	33a7e677-b29a-4895-87f4-1a8b43a1e374	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	leased	running	worker	execution started	\N	9970c203-e8e9-4fcf-b6dd-c54c55db05dd	2026-09-25 14:51:11.908244+00
4742023a-7583-48b6-9285-b48bfbfb83cf	33a7e677-b29a-4895-87f4-1a8b43a1e374	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	running	retry_wait	worker	retryable transient_error	\N	856a2e2d-fdbf-4158-b4ac-5078f057d9c9	2026-09-25 14:51:11.925075+00
f0fdeb8f-ab85-48bb-acbb-710a44cfe817	33a7e677-b29a-4895-87f4-1a8b43a1e374	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	retry_wait	queued	scheduler	backoff elapsed	\N	01f3e904-3600-414c-8446-140ffc42031d	2026-09-25 14:51:11.945761+00
08eef277-f9d9-4188-9dc6-8d7cd0f445e0	33a7e677-b29a-4895-87f4-1a8b43a1e374	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	queued	leased	worker	claimed by staging-smoke-worker	\N	ed335e47-257b-4cdc-97c9-cdeb58a7802e	2026-09-25 14:51:11.957927+00
4986ddc3-d9d5-42d5-a3fb-c08ca6077587	33a7e677-b29a-4895-87f4-1a8b43a1e374	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	leased	running	worker	execution started	\N	f59ed9ab-5585-4477-bc31-961063e2b55b	2026-09-25 14:51:11.971417+00
b62649c4-232f-4be9-9202-b6e1a7d79c54	33a7e677-b29a-4895-87f4-1a8b43a1e374	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	running	succeeded	worker	handler success	\N	1f227281-4ede-49ae-9c95-6482257d3b69	2026-09-25 14:51:11.989819+00
40c220fa-d282-4c70-a413-3988c6f50f9e	df75213d-9b26-4a9f-bd32-4cf32de0e372	ed8d2c75-d737-438a-bb53-4e457d4b096b	(created)	draft	system	submission created	2026-09-25T14:42:35.292807+00:00	\N	2026-09-25 14:51:12.02844+00
4a5d4a12-8b56-4375-87de-b4c6ca2abcb5	df75213d-9b26-4a9f-bd32-4cf32de0e372	ed8d2c75-d737-438a-bb53-4e457d4b096b	draft	queued	requestor	submitted	2026-09-25T14:42:35.292807+00:00	72a8fbe6-9403-4fcc-b9fa-6a012df5a26a	2026-09-25 14:51:12.031173+00
6e7b47c5-4a4b-427e-8df9-5231c96cc0b0	41f26384-a34f-4fc6-987c-087a046cf42c	3a5821b2-e29b-4355-b128-a97ddd6c4b8d	(created)	draft	system	submission created	2026-09-25T14:42:52.427134+00:00	\N	2026-09-25 14:51:12.063113+00
f5e8e1bf-2213-4ed9-8745-d91f8b8b7f7d	41f26384-a34f-4fc6-987c-087a046cf42c	3a5821b2-e29b-4355-b128-a97ddd6c4b8d	draft	queued	requestor	submitted	2026-09-25T14:42:52.427134+00:00	53f6d7fb-6c69-4ea2-9085-5a4c1918bae6	2026-09-25 14:51:12.066118+00
10bc736c-a2d5-4042-ad2d-198a311650ab	8368c245-aeb2-4758-b4c8-ba91d8aec34e	60873eaa-b945-465d-ac58-8761ed134713	(created)	draft	system	submission created	2026-09-25T14:43:23.199997+00:00	\N	2026-09-25 14:51:12.097558+00
7eaacbcd-4173-4363-b358-073a123455b2	8368c245-aeb2-4758-b4c8-ba91d8aec34e	60873eaa-b945-465d-ac58-8761ed134713	draft	queued	requestor	submitted	2026-09-25T14:43:23.199997+00:00	4771b753-bce2-4c14-a050-7286fc8f2274	2026-09-25 14:51:12.100888+00
6393c4ad-66fc-4066-ac40-5ffe1f32f4bb	3013ce28-c3cc-4798-be62-1f1df2b99f45	7d07bd89-d711-4209-a0de-7eade8fb8d17	(created)	draft	system	submission created	2026-09-25T14:43:39.275532+00:00	\N	2026-09-25 14:51:12.131386+00
422226c5-bcf9-43e4-a96c-e60dc5304709	3013ce28-c3cc-4798-be62-1f1df2b99f45	7d07bd89-d711-4209-a0de-7eade8fb8d17	draft	queued	requestor	submitted	2026-09-25T14:43:39.275532+00:00	20c3ffe3-73d3-4dba-92d6-3d1985bee693	2026-09-25 14:51:12.13408+00
7990a158-73ec-44ff-acb8-a08d16298fa5	d1b04528-b5f3-4cd7-a5d8-6534f355e04b	8fd371e8-fff7-4585-a4ec-440107ec8af6	(created)	draft	system	submission created	2026-09-25T14:47:36.370345+00:00	\N	2026-09-25 14:51:12.162686+00
24aa69f9-aa75-4220-b0f6-c01b072da059	d1b04528-b5f3-4cd7-a5d8-6534f355e04b	8fd371e8-fff7-4585-a4ec-440107ec8af6	draft	queued	requestor	submitted	2026-09-25T14:47:36.370345+00:00	28a44329-fca2-4ae8-9ef9-e66dbfcdf1e4	2026-09-25 14:51:12.165241+00
797a64f2-9d4e-4209-b22d-b06ed3b476ad	55e5d9d2-4d45-4d32-a5cb-6566ea148cd6	4e84497f-7ed5-4d89-9335-8c4138ab1de8	(created)	draft	system	submission created	2026-09-25T14:48:00.349508+00:00	\N	2026-09-25 14:51:12.194857+00
743a127a-e716-4d6a-b3e7-cd4a5f9334c3	55e5d9d2-4d45-4d32-a5cb-6566ea148cd6	4e84497f-7ed5-4d89-9335-8c4138ab1de8	draft	queued	requestor	submitted	2026-09-25T14:48:00.349508+00:00	139565d7-f955-45fe-8733-58a2e3fa76eb	2026-09-25 14:51:12.197543+00
5ff1256e-48ad-4eca-92b7-639586ab0f1b	f0a2b5a5-b0d5-4316-8cd4-1e095e241060	862b2b82-ae8f-4668-b58a-596f73e32533	(created)	draft	system	submission created	2026-09-25T14:51:07.007024+00:00	\N	2026-09-25 14:51:12.225937+00
88da5990-6e86-42b8-b2a2-a4f263183af4	f0a2b5a5-b0d5-4316-8cd4-1e095e241060	862b2b82-ae8f-4668-b58a-596f73e32533	draft	queued	requestor	submitted	2026-09-25T14:51:07.007024+00:00	36015b7d-4111-412a-ab23-0ed827ff2bcf	2026-09-25 14:51:12.228836+00
b6383120-c1e9-4927-a9ca-4d5f12459732	df75213d-9b26-4a9f-bd32-4cf32de0e372	ed8d2c75-d737-438a-bb53-4e457d4b096b	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T14:42:35.292807+00:00	394ccc4d-4a71-46a3-9ee3-4acf70fb58cf	2026-09-25 14:51:12.333815+00
ecef8d3b-bd17-4027-921b-0f6fb47ab910	df75213d-9b26-4a9f-bd32-4cf32de0e372	ed8d2c75-d737-438a-bb53-4e457d4b096b	leased	running	worker	execution started	2026-09-25T14:42:35.292807+00:00	9769259c-9512-4991-ba9e-baf33245b174	2026-09-25 14:51:12.349007+00
fbc30cd6-0bca-4271-bf6f-1208c69369a5	df75213d-9b26-4a9f-bd32-4cf32de0e372	ed8d2c75-d737-438a-bb53-4e457d4b096b	running	succeeded	worker	handler success	2026-09-25T14:42:35.292807+00:00	952b480f-6fff-4e16-be5e-5c256475933d	2026-09-25 14:51:12.368156+00
517d4473-e861-4927-98c0-8556c29270ed	41f26384-a34f-4fc6-987c-087a046cf42c	3a5821b2-e29b-4355-b128-a97ddd6c4b8d	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T14:42:52.427134+00:00	6e73bb9d-1659-4c0c-af1b-a4aec57ef05c	2026-09-25 14:51:12.383165+00
4be8fbc7-37a2-44ca-86d1-30538c63f5a3	41f26384-a34f-4fc6-987c-087a046cf42c	3a5821b2-e29b-4355-b128-a97ddd6c4b8d	leased	running	worker	execution started	2026-09-25T14:42:52.427134+00:00	ee6e4b13-b671-4f16-9af3-4b663329456f	2026-09-25 14:51:12.40636+00
e91ae8a3-3642-4fc7-9e41-ba36de4aa2b8	41f26384-a34f-4fc6-987c-087a046cf42c	3a5821b2-e29b-4355-b128-a97ddd6c4b8d	running	succeeded	worker	handler success	2026-09-25T14:42:52.427134+00:00	cbe7f7e1-f49d-4781-9177-3e96e9afb965	2026-09-25 14:51:12.425579+00
19a50b56-2c91-4c28-99c7-a06e6776ab26	8368c245-aeb2-4758-b4c8-ba91d8aec34e	60873eaa-b945-465d-ac58-8761ed134713	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T14:43:23.199997+00:00	b3538086-8f2c-489c-80a2-30decf78d602	2026-09-25 14:51:12.455485+00
ab409ad7-5199-4489-8ea4-22c53144db2d	8368c245-aeb2-4758-b4c8-ba91d8aec34e	60873eaa-b945-465d-ac58-8761ed134713	leased	running	worker	execution started	2026-09-25T14:43:23.199997+00:00	ff2109d0-d74a-4522-a922-8125db79c2b5	2026-09-25 14:51:12.469122+00
1b794743-8b72-4e3f-b61f-db7eae837d5b	8368c245-aeb2-4758-b4c8-ba91d8aec34e	60873eaa-b945-465d-ac58-8761ed134713	running	succeeded	worker	handler success	2026-09-25T14:43:23.199997+00:00	8f5ea4f0-de62-4d69-895c-0333828c20ca	2026-09-25 14:51:12.488485+00
2edbb062-b7d6-4243-a995-704a4cdeea48	3013ce28-c3cc-4798-be62-1f1df2b99f45	7d07bd89-d711-4209-a0de-7eade8fb8d17	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T14:43:39.275532+00:00	116799a6-9953-4b99-ae69-a353d411c43c	2026-09-25 14:51:12.502822+00
5818004b-6e4b-46ef-a989-f724d97ee431	3013ce28-c3cc-4798-be62-1f1df2b99f45	7d07bd89-d711-4209-a0de-7eade8fb8d17	leased	running	worker	execution started	2026-09-25T14:43:39.275532+00:00	20727a47-7edd-47fa-ab90-490546ce6a5b	2026-09-25 14:51:12.517326+00
b3d6915c-2a05-4742-97a0-7d9dbccab4d5	3013ce28-c3cc-4798-be62-1f1df2b99f45	7d07bd89-d711-4209-a0de-7eade8fb8d17	running	succeeded	worker	handler success	2026-09-25T14:43:39.275532+00:00	6ade6495-80fb-4e29-9024-0fa61609c5a8	2026-09-25 14:51:12.536461+00
a4b90193-6039-4437-ac1a-44e8b282b2f5	d1b04528-b5f3-4cd7-a5d8-6534f355e04b	8fd371e8-fff7-4585-a4ec-440107ec8af6	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T14:47:36.370345+00:00	97f4608b-aae1-4ce4-ba89-9803024e101d	2026-09-25 14:51:12.550141+00
78773ec3-e7c9-4296-8ea1-4822a160de37	d1b04528-b5f3-4cd7-a5d8-6534f355e04b	8fd371e8-fff7-4585-a4ec-440107ec8af6	leased	running	worker	execution started	2026-09-25T14:47:36.370345+00:00	3481cbea-6f9b-45f8-8a46-0ebe2559d9db	2026-09-25 14:51:12.563372+00
be306c65-4958-429c-92bd-5b465533aaa6	d1b04528-b5f3-4cd7-a5d8-6534f355e04b	8fd371e8-fff7-4585-a4ec-440107ec8af6	running	succeeded	worker	handler success	2026-09-25T14:47:36.370345+00:00	2b66550d-5a27-47be-b33a-dad92e8eaffe	2026-09-25 14:51:12.580913+00
84a5464c-020f-4e2d-9f59-5286908a3415	55e5d9d2-4d45-4d32-a5cb-6566ea148cd6	4e84497f-7ed5-4d89-9335-8c4138ab1de8	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T14:48:00.349508+00:00	6ce0680d-5954-4f4e-be2b-c4887cd17723	2026-09-25 14:51:12.593965+00
a62fba49-f24f-4681-a34b-18cd2ba5c82a	55e5d9d2-4d45-4d32-a5cb-6566ea148cd6	4e84497f-7ed5-4d89-9335-8c4138ab1de8	leased	running	worker	execution started	2026-09-25T14:48:00.349508+00:00	7afe92c2-8da0-4de1-a159-feff6dfadf2d	2026-09-25 14:51:12.607024+00
f327a018-4041-46ae-9aa3-390482838085	55e5d9d2-4d45-4d32-a5cb-6566ea148cd6	4e84497f-7ed5-4d89-9335-8c4138ab1de8	running	succeeded	worker	handler success	2026-09-25T14:48:00.349508+00:00	ae67bec8-e631-4c0d-a226-d9030cb88627	2026-09-25 14:51:12.625945+00
a7e6cf7e-7f3c-4aa5-9aec-f6516b0429fa	f0a2b5a5-b0d5-4316-8cd4-1e095e241060	862b2b82-ae8f-4668-b58a-596f73e32533	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T14:51:07.007024+00:00	5bab883d-cb5c-4bc9-86a8-bc9a37c574c8	2026-09-25 14:51:12.640431+00
15e786cc-59e2-4baa-a092-b9ade324ecd5	f0a2b5a5-b0d5-4316-8cd4-1e095e241060	862b2b82-ae8f-4668-b58a-596f73e32533	leased	running	worker	execution started	2026-09-25T14:51:07.007024+00:00	eb5d8d8a-5dc7-441f-83e1-fdb2ef571730	2026-09-25 14:51:12.655366+00
c87f5947-3f00-4f94-b505-4d973c3126fc	f0a2b5a5-b0d5-4316-8cd4-1e095e241060	862b2b82-ae8f-4668-b58a-596f73e32533	running	succeeded	worker	handler success	2026-09-25T14:51:07.007024+00:00	976d0c18-e58b-435c-ae71-76a52445ebc8	2026-09-25 14:51:12.674701+00
1f0ead14-a0d6-46b1-829a-3101b6e814e5	590d00ff-754c-428e-bec4-dc642314b8d1	6ed4e858-451b-48b6-83db-ba11662eac4f	(created)	draft	system	submission created	\N	\N	2026-09-25 14:51:12.865999+00
2b1d073b-5552-4443-b3fe-493006a8d156	590d00ff-754c-428e-bec4-dc642314b8d1	6ed4e858-451b-48b6-83db-ba11662eac4f	draft	queued	requestor	submitted	\N	42c5fc31-fa11-4480-9e0b-f8afc5fe4cd2	2026-09-25 14:51:12.869378+00
53126b21-cc6b-46ca-afe2-8c6cae6c98b0	32baf8fb-af8f-4f7a-a8d1-cd7a30f2c7fe	52a538e7-14cd-411f-b68a-a012031f7fc0	(created)	draft	system	submission created	\N	\N	2026-09-25 14:53:52.78924+00
5081c41d-0e89-4a6b-96f1-20e605dabd35	32baf8fb-af8f-4f7a-a8d1-cd7a30f2c7fe	52a538e7-14cd-411f-b68a-a012031f7fc0	draft	queued	requestor	submitted	\N	9881ce03-3bf8-4489-a79d-7338e7485101	2026-09-25 14:53:52.792377+00
bb192ad9-773b-4719-abb6-398d0757ccca	32baf8fb-af8f-4f7a-a8d1-cd7a30f2c7fe	52a538e7-14cd-411f-b68a-a012031f7fc0	queued	leased	worker	claimed by staging-smoke-worker	\N	e3ee5d1a-3f0f-4667-8d7e-1b222d818cc5	2026-09-25 14:53:52.809031+00
f74d24cc-114c-41e6-8816-29ea8a48b102	32baf8fb-af8f-4f7a-a8d1-cd7a30f2c7fe	52a538e7-14cd-411f-b68a-a012031f7fc0	leased	running	worker	execution started	\N	8f44a5b9-2ff1-45b7-8153-1483664c9b7b	2026-09-25 14:53:52.823396+00
b7fd1c1a-4447-4795-ae58-8c940fd4d5e6	32baf8fb-af8f-4f7a-a8d1-cd7a30f2c7fe	52a538e7-14cd-411f-b68a-a012031f7fc0	running	succeeded	worker	handler success	\N	37ab52dd-75c8-466f-9ea4-cf53c378c448	2026-09-25 14:53:52.842773+00
75c941ec-3a37-4c72-bc13-970bc1531be9	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	066a69b5-3244-4e91-8da5-01f414b9052a	(created)	draft	system	submission created	\N	\N	2026-09-25 14:53:52.874531+00
4be1f083-26a4-4745-a988-0f413a5e0fbc	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	066a69b5-3244-4e91-8da5-01f414b9052a	draft	queued	requestor	submitted	\N	37ccf7c6-1a65-4afb-beb6-1aa3e1d2f3c2	2026-09-25 14:53:52.878136+00
05270bcf-d1d3-4b88-a378-5434873e4f57	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	066a69b5-3244-4e91-8da5-01f414b9052a	queued	leased	worker	claimed by staging-smoke-worker	\N	78131b6b-4054-4ef7-8ad8-522d5065cbaa	2026-09-25 14:53:52.894697+00
8fe99747-b92e-4fa9-857b-722ad1df43b9	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	066a69b5-3244-4e91-8da5-01f414b9052a	leased	running	worker	execution started	\N	d17e7ba6-5506-466c-b2f7-5c93e09bd184	2026-09-25 14:53:52.909354+00
d2cfeb29-68d8-4680-9282-4e482452e1ba	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	066a69b5-3244-4e91-8da5-01f414b9052a	running	retry_wait	worker	retryable transient_error	\N	c6ad67cc-c881-4e09-97a9-649aa2970f62	2026-09-25 14:53:52.925447+00
890cfac7-64df-420b-b0cc-2ace3c84be93	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	066a69b5-3244-4e91-8da5-01f414b9052a	retry_wait	queued	scheduler	backoff elapsed	\N	77c6c4da-a162-4f84-bf5a-0bad61a3e65b	2026-09-25 14:53:52.947349+00
fa250a5d-27f3-49b5-993b-46ec160bdf9f	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	066a69b5-3244-4e91-8da5-01f414b9052a	queued	leased	worker	claimed by staging-smoke-worker	\N	ed95b30d-6ab9-49dc-ba53-f670edfbe5d2	2026-09-25 14:53:52.959542+00
88be9266-5cc7-4732-a666-0be410bcf3f5	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	066a69b5-3244-4e91-8da5-01f414b9052a	leased	running	worker	execution started	\N	3adb2f21-97b4-4bef-a817-f4a18a0578e1	2026-09-25 14:53:52.973473+00
edbbfeaa-7c00-4c9e-b445-055573702afa	8d35c923-2d19-4d1b-b28c-ed0d3a6433eb	066a69b5-3244-4e91-8da5-01f414b9052a	running	succeeded	worker	handler success	\N	bfd13de6-6fbc-46da-a1cf-17414f8cf253	2026-09-25 14:53:52.991882+00
c95b749b-6e92-4695-b233-afa8be33a3ff	d9001c70-db76-4ee9-a52f-d102a0284ae1	46a6356b-3b04-4540-bef9-d1ba99fcf6ec	(created)	draft	system	submission created	2026-09-25T14:53:48.009537+00:00	\N	2026-09-25 14:53:53.027876+00
3b136c8a-dc8e-4872-a0c4-14c6c4ccdabe	d9001c70-db76-4ee9-a52f-d102a0284ae1	46a6356b-3b04-4540-bef9-d1ba99fcf6ec	draft	queued	requestor	submitted	2026-09-25T14:53:48.009537+00:00	6ff20e6d-950f-43ff-9c86-9a488f52fa1e	2026-09-25 14:53:53.030696+00
7c8c5d1f-d270-4ca1-8b48-20e11dd8c735	d9001c70-db76-4ee9-a52f-d102a0284ae1	46a6356b-3b04-4540-bef9-d1ba99fcf6ec	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T14:53:48.009537+00:00	b865726b-a8f1-4609-b74d-c6189113c7e1	2026-09-25 14:53:53.140592+00
0606f1e7-488b-45a1-b77d-b8b2d15f4555	d9001c70-db76-4ee9-a52f-d102a0284ae1	46a6356b-3b04-4540-bef9-d1ba99fcf6ec	leased	running	worker	execution started	2026-09-25T14:53:48.009537+00:00	5a857c79-72cc-4192-ad76-c5dffd72e0ea	2026-09-25 14:53:53.15531+00
1328837d-ce00-4b9d-8829-c496b0501e13	d9001c70-db76-4ee9-a52f-d102a0284ae1	46a6356b-3b04-4540-bef9-d1ba99fcf6ec	running	succeeded	worker	handler success	2026-09-25T14:53:48.009537+00:00	1c22aa0e-2109-4cb3-afb8-e3d0a3e1ef1b	2026-09-25 14:53:53.174648+00
023bb0b4-6446-4759-b928-9320a6a54b9a	3a54dc18-4988-4ddf-bdd2-3c50229a2fd6	d9dc7462-7954-4ba8-9d77-1c4538ad72e6	(created)	draft	system	submission created	\N	\N	2026-09-25 14:53:53.348409+00
f6c451c3-20de-4b68-a987-2a5eb0a098d8	3a54dc18-4988-4ddf-bdd2-3c50229a2fd6	d9dc7462-7954-4ba8-9d77-1c4538ad72e6	draft	queued	requestor	submitted	\N	685283b9-28e6-4303-84f0-afa80068ce91	2026-09-25 14:53:53.351254+00
077c0c8b-9473-42ef-b09e-07978de76cbd	45d210df-829b-4915-8e37-cca1449cb6d9	d384a816-2afc-4823-9510-a9e46d265c43	(created)	draft	system	submission created	\N	\N	2026-09-25 15:37:31.696729+00
cedfb1e5-c4e2-46bb-9b8b-f461908fbd8a	45d210df-829b-4915-8e37-cca1449cb6d9	d384a816-2afc-4823-9510-a9e46d265c43	draft	queued	requestor	submitted	\N	090896ad-b73b-44a8-bbc3-c79c2cce2663	2026-09-25 15:37:31.701664+00
339e93e4-66f6-4c4d-b943-c018363b3583	45d210df-829b-4915-8e37-cca1449cb6d9	d384a816-2afc-4823-9510-a9e46d265c43	queued	leased	worker	claimed by staging-smoke-worker	\N	5014001a-410c-4a40-af4f-eeb0d8a2136f	2026-09-25 15:37:31.719064+00
9e06d004-94aa-4f65-bbf4-0c07f83ace46	45d210df-829b-4915-8e37-cca1449cb6d9	d384a816-2afc-4823-9510-a9e46d265c43	leased	running	worker	execution started	\N	f8b5853c-c03a-47b2-865b-5d60b29e4210	2026-09-25 15:37:31.734783+00
baf6f00d-b9e6-467a-a375-0d3131910ed2	45d210df-829b-4915-8e37-cca1449cb6d9	d384a816-2afc-4823-9510-a9e46d265c43	running	succeeded	worker	handler success	\N	1dcc7d28-c5a2-4493-96d0-aab01ce5d82d	2026-09-25 15:37:31.755045+00
cfc10058-830d-4287-9402-5734d0eba94d	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	b8208594-7396-49a5-a29e-4518c24a4b93	(created)	draft	system	submission created	\N	\N	2026-09-25 15:37:31.785996+00
b317d423-e06f-453d-b27c-713f734f05a2	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	b8208594-7396-49a5-a29e-4518c24a4b93	draft	queued	requestor	submitted	\N	8fca237f-3330-4fd2-bf01-3f6cc6d0e83d	2026-09-25 15:37:31.78971+00
b38824c9-9b3a-43cf-92f2-0fa639f0804a	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	b8208594-7396-49a5-a29e-4518c24a4b93	queued	leased	worker	claimed by staging-smoke-worker	\N	2d03b9fd-4501-41f4-9037-f981fa63fba0	2026-09-25 15:37:31.808175+00
d951f700-4343-40c7-bf08-0949631d55ee	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	b8208594-7396-49a5-a29e-4518c24a4b93	leased	running	worker	execution started	\N	03624c8d-46d9-46a2-af07-731ca5a11f36	2026-09-25 15:37:31.823807+00
9158f13a-fe11-44c2-9795-120b6a73d78b	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	b8208594-7396-49a5-a29e-4518c24a4b93	running	retry_wait	worker	retryable transient_error	\N	6d654cff-a0bd-4910-809e-eea256436913	2026-09-25 15:37:31.840894+00
f1595d0c-d781-4552-93b5-0c11f871b832	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	b8208594-7396-49a5-a29e-4518c24a4b93	retry_wait	queued	scheduler	backoff elapsed	\N	215df4a1-d064-47b1-af83-16c1daf11809	2026-09-25 15:37:31.862441+00
9d2a9088-747b-4188-aa86-6c87c552f982	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	b8208594-7396-49a5-a29e-4518c24a4b93	queued	leased	worker	claimed by staging-smoke-worker	\N	1feec5a4-efb3-4e02-b835-edd1edc70c86	2026-09-25 15:37:31.875211+00
d70f08c5-c8a9-4df0-ab6d-072f8b006793	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	b8208594-7396-49a5-a29e-4518c24a4b93	leased	running	worker	execution started	\N	fb9665c2-b5bc-47f5-a3b9-c5699cbeb50c	2026-09-25 15:37:31.889646+00
289229e9-9eb6-46e1-ba97-9c477b4d0b14	7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe	b8208594-7396-49a5-a29e-4518c24a4b93	running	succeeded	worker	handler success	\N	0e73bc42-9537-42ef-9d66-a84ca160212a	2026-09-25 15:37:31.907079+00
57f2c836-542e-4dfd-93db-9b13cdc01333	3c51e672-9ffc-4708-a633-d6b0080b97db	c06674c2-6599-436e-99d5-642fcc32e7b8	(created)	draft	system	submission created	2026-09-25T15:37:26.923883+00:00	\N	2026-09-25 15:37:31.955437+00
b78c07ee-386e-41b8-9589-1c467f786d79	3c51e672-9ffc-4708-a633-d6b0080b97db	c06674c2-6599-436e-99d5-642fcc32e7b8	draft	queued	requestor	submitted	2026-09-25T15:37:26.923883+00:00	56a7303f-3766-4cae-9f4e-3e3c0f1f076b	2026-09-25 15:37:31.958392+00
a1b24d6b-961a-4c30-8c59-711b34a411c1	3c51e672-9ffc-4708-a633-d6b0080b97db	c06674c2-6599-436e-99d5-642fcc32e7b8	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T15:37:26.923883+00:00	499fb474-21d3-4804-9231-c81cf9a8677f	2026-09-25 15:37:32.072541+00
98dc4878-c4f7-4443-a71c-15e9322579c6	3c51e672-9ffc-4708-a633-d6b0080b97db	c06674c2-6599-436e-99d5-642fcc32e7b8	leased	running	worker	execution started	2026-09-25T15:37:26.923883+00:00	138785d5-4078-4489-941b-d0460339b611	2026-09-25 15:37:32.085719+00
e8768cad-d19e-45d6-9ee1-b62d754ace28	3c51e672-9ffc-4708-a633-d6b0080b97db	c06674c2-6599-436e-99d5-642fcc32e7b8	running	succeeded	worker	handler success	2026-09-25T15:37:26.923883+00:00	ae53d950-9bb9-4e76-bde5-7bdcce72b081	2026-09-25 15:37:32.104689+00
0ae87d9c-3738-4e26-bdde-c88fad6a50b5	64db6bcb-b7cc-4fa1-9e0a-f78faa9e4121	5ee7d797-a106-4fcf-941a-833acb355abc	(created)	draft	system	submission created	\N	\N	2026-09-25 15:37:32.318183+00
21f16d22-6568-4b67-b085-3a954ffe9994	64db6bcb-b7cc-4fa1-9e0a-f78faa9e4121	5ee7d797-a106-4fcf-941a-833acb355abc	draft	queued	requestor	submitted	\N	2b11fb47-6c0d-48df-95d7-879bd79988ab	2026-09-25 15:37:32.320981+00
755662f6-5766-4849-9c84-bea46d9855a5	87fd1bcb-34c1-4dc6-b7a0-b8c8d4255e2a	447d268e-6349-43bd-b790-d224b352371d	(created)	draft	system	submission created	\N	\N	2026-09-25 15:38:04.131501+00
c521bd4f-d2d0-4f7d-a319-76c1fadd92b5	87fd1bcb-34c1-4dc6-b7a0-b8c8d4255e2a	447d268e-6349-43bd-b790-d224b352371d	draft	queued	requestor	submitted	\N	fb1f41cb-3259-43e1-adcc-b92389c1684b	2026-09-25 15:38:04.134553+00
4785efa6-835e-4a98-acc6-984fc9dec625	87fd1bcb-34c1-4dc6-b7a0-b8c8d4255e2a	447d268e-6349-43bd-b790-d224b352371d	queued	leased	worker	claimed by staging-smoke-worker	\N	b4e332d5-10fb-481a-a4fb-4960432a747d	2026-09-25 15:38:04.153225+00
a83d4ac8-09fd-4b86-b186-efc89e3d2df8	87fd1bcb-34c1-4dc6-b7a0-b8c8d4255e2a	447d268e-6349-43bd-b790-d224b352371d	leased	running	worker	execution started	\N	62d9d822-fc98-40a9-aaf1-37ad8579fd9c	2026-09-25 15:38:04.16788+00
d4a4b251-b004-4ae2-b1af-ae8208e4d189	87fd1bcb-34c1-4dc6-b7a0-b8c8d4255e2a	447d268e-6349-43bd-b790-d224b352371d	running	succeeded	worker	handler success	\N	784de406-1ad6-4b20-b12d-7d2d5d5cc9ea	2026-09-25 15:38:04.186596+00
da532931-64c6-4fa9-856e-10c5c95c07aa	f88b1602-18de-45f7-a836-753ac6dbb73d	e870faf1-14e6-40f8-a346-6d60573785af	(created)	draft	system	submission created	\N	\N	2026-09-25 15:38:04.219734+00
8ab36093-2979-4043-a7b0-9340e14c7c0a	f88b1602-18de-45f7-a836-753ac6dbb73d	e870faf1-14e6-40f8-a346-6d60573785af	draft	queued	requestor	submitted	\N	d86f6c98-d459-432f-a122-9da4893195fa	2026-09-25 15:38:04.231064+00
d97067c1-c935-479e-b037-180551286f39	f88b1602-18de-45f7-a836-753ac6dbb73d	e870faf1-14e6-40f8-a346-6d60573785af	queued	leased	worker	claimed by staging-smoke-worker	\N	1191b771-0276-43f1-b99d-3d53839422a4	2026-09-25 15:38:04.251044+00
ce839e82-c440-43bb-8848-525fbf33c7f3	f88b1602-18de-45f7-a836-753ac6dbb73d	e870faf1-14e6-40f8-a346-6d60573785af	leased	running	worker	execution started	\N	9437cac8-49fd-476a-8bb5-c13bf1c35869	2026-09-25 15:38:04.268861+00
6f2589b3-79ec-4c5b-b817-1e34271d7ce9	f88b1602-18de-45f7-a836-753ac6dbb73d	e870faf1-14e6-40f8-a346-6d60573785af	running	retry_wait	worker	retryable transient_error	\N	e26d5126-7d89-4095-9aba-b9e271906a28	2026-09-25 15:38:04.285666+00
5b736e56-3285-4eda-9162-5b04f44ee5a2	f88b1602-18de-45f7-a836-753ac6dbb73d	e870faf1-14e6-40f8-a346-6d60573785af	retry_wait	queued	scheduler	backoff elapsed	\N	c18ff68a-5e33-4d9c-8263-baf1f555b22b	2026-09-25 15:38:04.308+00
f2b1cf7c-94f6-4ba9-a327-44e395dc1137	f88b1602-18de-45f7-a836-753ac6dbb73d	e870faf1-14e6-40f8-a346-6d60573785af	queued	leased	worker	claimed by staging-smoke-worker	\N	aa7e7e20-3a0b-44e3-b125-2f19d5c8e3fa	2026-09-25 15:38:04.32045+00
f7bc6797-603f-47c0-b0ee-e0d08dfb389f	f88b1602-18de-45f7-a836-753ac6dbb73d	e870faf1-14e6-40f8-a346-6d60573785af	leased	running	worker	execution started	\N	c0710bc5-9d8a-49cb-a92c-093e4085e27e	2026-09-25 15:38:04.334428+00
cbb07701-1743-49c5-8514-e5b8c65ece6a	f88b1602-18de-45f7-a836-753ac6dbb73d	e870faf1-14e6-40f8-a346-6d60573785af	running	succeeded	worker	handler success	\N	93c5ba8f-927a-4068-a64e-95998c6c1036	2026-09-25 15:38:04.353042+00
7ee6f354-70d0-4bfe-9a0c-ab15f2cf812f	bb9de075-0d97-4a93-8b3e-72c2bbf0b801	13cb4d13-6660-4f9f-9730-4a8805603a19	(created)	draft	system	submission created	2026-09-25T15:37:59.371396+00:00	\N	2026-09-25 15:38:04.394108+00
100ea120-dbff-41ec-86a4-cd1d60bb9ee9	bb9de075-0d97-4a93-8b3e-72c2bbf0b801	13cb4d13-6660-4f9f-9730-4a8805603a19	draft	queued	requestor	submitted	2026-09-25T15:37:59.371396+00:00	40190d22-953d-4cab-aae1-adbd08bb65d7	2026-09-25 15:38:04.397033+00
5aac620a-2a7e-4f10-8c4b-97278eb7dbc2	bb9de075-0d97-4a93-8b3e-72c2bbf0b801	13cb4d13-6660-4f9f-9730-4a8805603a19	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T15:37:59.371396+00:00	2bd1e03b-237d-4089-9bd4-db9d5d9ec13e	2026-09-25 15:38:04.50462+00
877a9d7b-43c8-4169-af8e-70fe419b3414	bb9de075-0d97-4a93-8b3e-72c2bbf0b801	13cb4d13-6660-4f9f-9730-4a8805603a19	leased	running	worker	execution started	2026-09-25T15:37:59.371396+00:00	7865e065-78b7-4699-a305-4f481c010d34	2026-09-25 15:38:04.517901+00
2fc2ef39-de3c-46f6-919d-f8cb1d713e76	bb9de075-0d97-4a93-8b3e-72c2bbf0b801	13cb4d13-6660-4f9f-9730-4a8805603a19	running	succeeded	worker	handler success	2026-09-25T15:37:59.371396+00:00	76454842-649b-4566-9394-a56f609b122c	2026-09-25 15:38:04.536089+00
d47de028-08b3-4346-9ee4-8e29e4a778af	00a1fa40-f69b-4121-958d-b8f8d9137513	a2d6877d-260c-469f-9662-b129ec767e8a	(created)	draft	system	submission created	\N	\N	2026-09-25 15:38:04.738249+00
9cc5b659-f6e1-4b73-ae15-9f049ece9dd9	00a1fa40-f69b-4121-958d-b8f8d9137513	a2d6877d-260c-469f-9662-b129ec767e8a	draft	queued	requestor	submitted	\N	6c2f36a6-883c-4bb4-b026-c09f2baa836e	2026-09-25 15:38:04.740963+00
e8213fe1-ab3d-4eff-9dc6-688807368f72	ea1b3ec9-5441-4dd9-a4b6-428886125db7	2acbf0ce-aac1-4429-9f62-96a58336f831	(created)	draft	system	submission created	\N	\N	2026-09-25 15:39:15.302216+00
954bf95e-f28a-4305-9c7d-b51d45c4ba7a	ea1b3ec9-5441-4dd9-a4b6-428886125db7	2acbf0ce-aac1-4429-9f62-96a58336f831	draft	queued	requestor	submitted	\N	867ce465-0ff7-446c-a195-dc07481af831	2026-09-25 15:39:15.30517+00
0c5406e2-b6c6-40b1-9085-cea1e76af19e	ea1b3ec9-5441-4dd9-a4b6-428886125db7	2acbf0ce-aac1-4429-9f62-96a58336f831	queued	leased	worker	claimed by staging-smoke-worker	\N	3dd3e938-c653-4a73-91b6-f56080de9c73	2026-09-25 15:39:15.321969+00
19098663-3604-4b06-8c24-e433fb2818e2	ea1b3ec9-5441-4dd9-a4b6-428886125db7	2acbf0ce-aac1-4429-9f62-96a58336f831	leased	running	worker	execution started	\N	953fe04d-b916-4987-a657-7e5ee2f1e7eb	2026-09-25 15:39:15.335653+00
c3759542-f00a-4e80-a21c-e8a75ea79505	ea1b3ec9-5441-4dd9-a4b6-428886125db7	2acbf0ce-aac1-4429-9f62-96a58336f831	running	succeeded	worker	handler success	\N	0cff437c-ef3f-43ec-8e75-fc3d63552e52	2026-09-25 15:39:15.354024+00
9de21f56-e70b-45da-b22d-876209363e46	1e82450b-72a9-436b-b3b2-46a915738f5b	c3299161-4bdf-49ec-b711-898ae6287e0b	(created)	draft	system	submission created	\N	\N	2026-09-25 15:39:15.391667+00
8c27bba7-aeab-4590-a1c6-360f0dce66b4	1e82450b-72a9-436b-b3b2-46a915738f5b	c3299161-4bdf-49ec-b711-898ae6287e0b	draft	queued	requestor	submitted	\N	7c5bb7a1-085c-4bd4-ae12-0e17fb8b72e9	2026-09-25 15:39:15.395263+00
5cef8f03-ed0e-4eb7-8f94-73d055dce790	1e82450b-72a9-436b-b3b2-46a915738f5b	c3299161-4bdf-49ec-b711-898ae6287e0b	queued	leased	worker	claimed by staging-smoke-worker	\N	b312ea51-4773-45a3-963a-c5d8f592e6c0	2026-09-25 15:39:15.412763+00
e4e2858e-5216-42f4-bd4e-8dd9e5c65316	1e82450b-72a9-436b-b3b2-46a915738f5b	c3299161-4bdf-49ec-b711-898ae6287e0b	leased	running	worker	execution started	\N	0171dca4-2587-4f37-b0c4-e3b57aa3fd7b	2026-09-25 15:39:15.43081+00
77721202-cf65-4d69-a627-787e06efa7c6	1e82450b-72a9-436b-b3b2-46a915738f5b	c3299161-4bdf-49ec-b711-898ae6287e0b	running	retry_wait	worker	retryable transient_error	\N	b0367bcf-ae66-4326-b79b-8da5976a0252	2026-09-25 15:39:15.45065+00
1317f313-ac9e-4822-98cf-cec49954802a	1e82450b-72a9-436b-b3b2-46a915738f5b	c3299161-4bdf-49ec-b711-898ae6287e0b	retry_wait	queued	scheduler	backoff elapsed	\N	a0f17c06-6933-463c-a1d5-33f573b7b554	2026-09-25 15:39:15.474533+00
99081f8e-f59f-40b8-9701-6cd3e1bb9f5a	1e82450b-72a9-436b-b3b2-46a915738f5b	c3299161-4bdf-49ec-b711-898ae6287e0b	queued	leased	worker	claimed by staging-smoke-worker	\N	3a1ea099-c3a5-4a27-807d-a92ff79cc606	2026-09-25 15:39:15.488517+00
e53de8ae-7a07-44d2-b8e9-0152f31ef758	1e82450b-72a9-436b-b3b2-46a915738f5b	c3299161-4bdf-49ec-b711-898ae6287e0b	leased	running	worker	execution started	\N	4cc07c94-3f65-4c39-a81f-c5c882e738a5	2026-09-25 15:39:15.50351+00
bf1486a3-ec51-493c-929b-ee66003bd85c	1e82450b-72a9-436b-b3b2-46a915738f5b	c3299161-4bdf-49ec-b711-898ae6287e0b	running	succeeded	worker	handler success	\N	4cb22185-0232-44d6-95cf-00d98a1e68b9	2026-09-25 15:39:15.522943+00
fb883ee0-f0a9-4e2c-a460-3c92facfe44c	72709084-6173-43bf-ac05-71607e3bb043	0e2e02e8-fde2-4386-b45f-94c21fd920c5	(created)	draft	system	submission created	2026-09-25T15:39:10.542065+00:00	\N	2026-09-25 15:39:15.563096+00
9022bb35-5096-4fe8-bdb8-1b8b11efe4c7	72709084-6173-43bf-ac05-71607e3bb043	0e2e02e8-fde2-4386-b45f-94c21fd920c5	draft	queued	requestor	submitted	2026-09-25T15:39:10.542065+00:00	cfcc0d10-21ca-46f0-9aa6-a8c7ad150c99	2026-09-25 15:39:15.565779+00
b155d36b-e6d4-4ffe-ad5c-d4c4f1703a38	72709084-6173-43bf-ac05-71607e3bb043	0e2e02e8-fde2-4386-b45f-94c21fd920c5	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T15:39:10.542065+00:00	40efa994-8852-4c46-ba95-0ebd37fd6e9e	2026-09-25 15:39:15.683411+00
e6290767-7376-4206-87fd-aa3289842b1f	72709084-6173-43bf-ac05-71607e3bb043	0e2e02e8-fde2-4386-b45f-94c21fd920c5	leased	running	worker	execution started	2026-09-25T15:39:10.542065+00:00	39f7cfae-cf1a-458d-8399-1cb58db4e9bc	2026-09-25 15:39:15.701294+00
f1af8db9-e173-42ae-8264-7c237bf5122b	72709084-6173-43bf-ac05-71607e3bb043	0e2e02e8-fde2-4386-b45f-94c21fd920c5	running	succeeded	worker	handler success	2026-09-25T15:39:10.542065+00:00	f729b532-d3c7-43f5-ac5e-ac38fff7678d	2026-09-25 15:39:15.723965+00
362ab81b-b73a-4350-bb3b-f2578cf0cc42	0e3f8700-edcb-45c3-b183-ebd57436eb4b	c6c9b6c9-6898-467a-81a0-cfdcf7904083	(created)	draft	system	submission created	\N	\N	2026-09-25 15:39:15.924013+00
7db70105-936a-4e64-a4fb-98c627b2a397	0e3f8700-edcb-45c3-b183-ebd57436eb4b	c6c9b6c9-6898-467a-81a0-cfdcf7904083	draft	queued	requestor	submitted	\N	c6e8dc2d-ae00-43c3-abaa-069fc64a58f2	2026-09-25 15:39:15.926855+00
02a6cef0-0197-4b75-8841-8907d074af12	d7933dde-59a3-4152-99e1-15461565de3e	8fa27db2-9fee-4d10-b980-03a23348cf21	(created)	draft	system	submission created	\N	\N	2026-09-25 15:39:16.093594+00
a6b1606b-88c4-46e0-bd82-0f3d284fbeac	d7933dde-59a3-4152-99e1-15461565de3e	8fa27db2-9fee-4d10-b980-03a23348cf21	draft	queued	requestor	submitted	\N	16f21a5c-50a1-471b-a134-8e365fa8295b	2026-09-25 15:39:16.096259+00
698ef54d-9484-4eb4-9fbf-e428ae26b54e	d4b6deac-d10f-4d17-8d19-2ad319d1c5f4	df883f51-cf48-4022-b43d-4657cb645e83	(created)	draft	system	submission created	\N	\N	2026-09-25 15:39:16.123012+00
fe1f888a-b9fa-4c36-aed2-6ed7ca51c9fc	d4b6deac-d10f-4d17-8d19-2ad319d1c5f4	df883f51-cf48-4022-b43d-4657cb645e83	draft	queued	requestor	submitted	\N	2670571b-06b5-4920-86ff-9b3804ed8025	2026-09-25 15:39:16.125873+00
149a5d63-1b82-4164-9350-bc595a4ded56	8378b1d5-a70a-4e7c-b553-61e7ab149b81	91079a87-d676-46e2-8be4-fec56f582d9d	(created)	draft	system	submission created	\N	\N	2026-09-25 15:39:16.152726+00
6ddd6b39-8c2c-4979-b189-8ceae276f682	8378b1d5-a70a-4e7c-b553-61e7ab149b81	91079a87-d676-46e2-8be4-fec56f582d9d	draft	queued	requestor	submitted	\N	75f9c9ac-c1f0-4948-bab4-e6fc5f9bcdd2	2026-09-25 15:39:16.155643+00
81cc0cfb-8a9f-4b79-95ac-c19524fa9cbf	2af0ccf8-5e8d-47ec-aa8e-9c76a1229f07	09dd775d-08f5-461e-99a0-50e3c8c94e95	(created)	draft	system	submission created	\N	\N	2026-09-25 15:39:16.183457+00
137c4604-65b6-41fa-9e22-cd7ab00aa46b	2af0ccf8-5e8d-47ec-aa8e-9c76a1229f07	09dd775d-08f5-461e-99a0-50e3c8c94e95	draft	queued	requestor	submitted	\N	a3a186c1-8c7a-4672-9850-91e0324a286e	2026-09-25 15:39:16.18621+00
b34e9a21-7ea1-4503-9431-bf4e795eae41	5df93f57-0670-43cf-8573-ef4057dfc5ac	ef0c7cdd-9bca-47a5-b120-339c63d1c67b	(created)	draft	system	submission created	\N	\N	2026-09-25 15:39:16.213568+00
de4f2d6d-f4cb-4b12-85a2-6844f53d3499	5df93f57-0670-43cf-8573-ef4057dfc5ac	ef0c7cdd-9bca-47a5-b120-339c63d1c67b	draft	queued	requestor	submitted	\N	6a7769ab-c6a0-4291-86ac-6541df54d9af	2026-09-25 15:39:16.216355+00
79a79b4c-e23d-4b9b-a0e2-922dcb81bcf8	a4b9c007-7508-4e67-ba66-34dcb83afdbc	922f1fac-f869-4980-99c1-cb61b74c1d0b	(created)	draft	system	submission created	\N	\N	2026-09-25 15:39:16.242343+00
5cd25c0f-7b70-4568-b46f-f04a65f76ea2	a4b9c007-7508-4e67-ba66-34dcb83afdbc	922f1fac-f869-4980-99c1-cb61b74c1d0b	draft	queued	requestor	submitted	\N	88d04985-5cf0-4bdc-a7f1-f31a654d78a8	2026-09-25 15:39:16.245001+00
70e1a7b1-3d20-44da-9025-e769e6c2dbca	00fb6a50-57ec-4e8d-9a22-94b43b6669cb	0d700548-3a64-41b3-9b53-1c19625e9229	(created)	draft	system	submission created	\N	\N	2026-09-25 15:39:50.232356+00
8c52689b-fa40-4951-bd04-6477c7d9c0d0	00fb6a50-57ec-4e8d-9a22-94b43b6669cb	0d700548-3a64-41b3-9b53-1c19625e9229	draft	queued	requestor	submitted	\N	c061d02d-b79b-4d70-ab7e-9aaa90133a26	2026-09-25 15:39:50.236446+00
a017021e-81f0-412f-9422-d76aeb28b360	00fb6a50-57ec-4e8d-9a22-94b43b6669cb	0d700548-3a64-41b3-9b53-1c19625e9229	queued	leased	worker	claimed by staging-smoke-worker	\N	0b0d9452-7119-4678-96af-294204d65745	2026-09-25 15:39:50.25493+00
ab7b54f8-747c-4575-b2b4-b728bcf79756	00fb6a50-57ec-4e8d-9a22-94b43b6669cb	0d700548-3a64-41b3-9b53-1c19625e9229	leased	running	worker	execution started	\N	cd227c5d-c51e-4c29-86ec-e242cafc500d	2026-09-25 15:39:50.270321+00
4a0503c7-f829-49f0-9108-8c78ee79615c	00fb6a50-57ec-4e8d-9a22-94b43b6669cb	0d700548-3a64-41b3-9b53-1c19625e9229	running	succeeded	worker	handler success	\N	42337111-9fd0-4f04-b422-40e1e6d127ba	2026-09-25 15:39:50.290458+00
478ba755-c48d-47da-9121-e60f85206b9d	c3eb9278-49f7-4c93-8f8e-a94559908fad	c604cf51-ac89-4bdc-9ea2-746cc1adb608	(created)	draft	system	submission created	\N	\N	2026-09-25 15:39:50.353561+00
cf40bb47-0d56-403f-b412-8c6470c4a7c2	c3eb9278-49f7-4c93-8f8e-a94559908fad	c604cf51-ac89-4bdc-9ea2-746cc1adb608	draft	queued	requestor	submitted	\N	f80a9ed3-92ba-4418-845a-80018db0c13c	2026-09-25 15:39:50.35731+00
3f15a156-8eb9-44c0-b797-ef6b7d97398f	c3eb9278-49f7-4c93-8f8e-a94559908fad	c604cf51-ac89-4bdc-9ea2-746cc1adb608	queued	leased	worker	claimed by staging-smoke-worker	\N	fd79c625-92bc-4f11-be71-676ceb655bc9	2026-09-25 15:39:50.375648+00
b1c59f25-362b-4e5e-9ce0-bc4971d2b0a7	c3eb9278-49f7-4c93-8f8e-a94559908fad	c604cf51-ac89-4bdc-9ea2-746cc1adb608	leased	running	worker	execution started	\N	24f4b0b7-f05a-43ef-b378-23def2f6d7ff	2026-09-25 15:39:50.390482+00
60a53701-31e5-44e6-80aa-d63902e3e3b1	c3eb9278-49f7-4c93-8f8e-a94559908fad	c604cf51-ac89-4bdc-9ea2-746cc1adb608	running	retry_wait	worker	retryable transient_error	\N	9d4b2e3e-8d7e-47fa-bc66-df2c7aa3116d	2026-09-25 15:39:50.40653+00
e03eafd4-9441-4b3a-a05d-1f9b7fda62f0	c3eb9278-49f7-4c93-8f8e-a94559908fad	c604cf51-ac89-4bdc-9ea2-746cc1adb608	retry_wait	queued	scheduler	backoff elapsed	\N	74ec9bb2-22bc-4dac-9956-63cbb7c711e6	2026-09-25 15:39:50.427626+00
0c7fd420-6e74-46ea-99b4-40f3bff77d14	c3eb9278-49f7-4c93-8f8e-a94559908fad	c604cf51-ac89-4bdc-9ea2-746cc1adb608	queued	leased	worker	claimed by staging-smoke-worker	\N	a5149f97-3c9f-4b92-a961-4ba73b65bec2	2026-09-25 15:39:50.439915+00
bae89d4a-5a12-4745-8215-e0690052f694	c3eb9278-49f7-4c93-8f8e-a94559908fad	c604cf51-ac89-4bdc-9ea2-746cc1adb608	leased	running	worker	execution started	\N	cc73f1ec-9f6c-473c-a5d6-50b22a1740fe	2026-09-25 15:39:50.453352+00
268df71f-40ef-4222-bcb7-1426fc5b9294	c3eb9278-49f7-4c93-8f8e-a94559908fad	c604cf51-ac89-4bdc-9ea2-746cc1adb608	running	succeeded	worker	handler success	\N	fd3fa6dd-4d2c-4cb1-8340-22f2d45d6122	2026-09-25 15:39:50.470703+00
a43c8fd8-0140-49d1-9b92-42b793c1f6ba	4bcb49ea-f1e8-4f40-92ae-74d72dd2a783	9077902e-98c6-4ac9-b0be-ca7a1a32e924	(created)	draft	system	submission created	2026-09-25T15:39:45.488996+00:00	\N	2026-09-25 15:39:50.508757+00
bf0c8863-207e-4420-8da5-5bc942893a3e	4bcb49ea-f1e8-4f40-92ae-74d72dd2a783	9077902e-98c6-4ac9-b0be-ca7a1a32e924	draft	queued	requestor	submitted	2026-09-25T15:39:45.488996+00:00	c43670b4-771c-4cdb-b15f-0736e3784e2e	2026-09-25 15:39:50.511405+00
dcf1cb3b-a7ae-452f-9542-33d77e875602	4bcb49ea-f1e8-4f40-92ae-74d72dd2a783	9077902e-98c6-4ac9-b0be-ca7a1a32e924	queued	leased	worker	claimed by staging-smoke-worker	2026-09-25T15:39:45.488996+00:00	95a2853c-fc8f-469f-8476-1ffdc2ef6de2	2026-09-25 15:39:50.621108+00
352b2c82-8209-466b-bfc4-43a23cdc702c	4bcb49ea-f1e8-4f40-92ae-74d72dd2a783	9077902e-98c6-4ac9-b0be-ca7a1a32e924	leased	running	worker	execution started	2026-09-25T15:39:45.488996+00:00	57871436-1573-41b4-bf82-bfbea73cb9f6	2026-09-25 15:39:50.637977+00
b1b35a24-c518-460a-bf5d-4fe634891652	4bcb49ea-f1e8-4f40-92ae-74d72dd2a783	9077902e-98c6-4ac9-b0be-ca7a1a32e924	running	succeeded	worker	handler success	2026-09-25T15:39:45.488996+00:00	534c2c04-3e4b-424a-b09f-2884fbbf7966	2026-09-25 15:39:50.6559+00
595112db-f42a-4829-afdd-5adf0f05aa0c	a2dd52f7-eb7d-4ea2-9a53-25a8c12fabc7	67cf4e56-2251-4762-a408-86f6cd6dce0b	(created)	draft	system	submission created	\N	\N	2026-09-25 15:39:50.852048+00
4a23942e-e898-4e7d-a8f3-7d533e1b0ed5	a2dd52f7-eb7d-4ea2-9a53-25a8c12fabc7	67cf4e56-2251-4762-a408-86f6cd6dce0b	draft	queued	requestor	submitted	\N	b42473a7-b140-4880-ad0a-3587ce007bf4	2026-09-25 15:39:50.854769+00
1ca3b7c8-359b-47ab-b388-72d49bdc48f8	6828b198-0ca2-4889-97ee-bdc5e0ad15c8	5544e37b-5705-44bd-b1b6-c7de3e219c7c	(created)	draft	system	submission created	\N	\N	2026-09-25 15:39:51.012128+00
375f4f93-c0d8-47a2-8e13-1618c682004d	6828b198-0ca2-4889-97ee-bdc5e0ad15c8	5544e37b-5705-44bd-b1b6-c7de3e219c7c	draft	queued	requestor	submitted	\N	7840ed3f-4bfa-4ed9-a04d-03d0f9a21e07	2026-09-25 15:39:51.014836+00
b02ba27e-0bfa-4ff6-a2d0-41d438a4a887	6ffc2dab-063d-44af-a3e7-215eaad84634	e5d28f54-0ded-42cb-aabe-70d054a67618	(created)	draft	system	submission created	\N	\N	2026-09-25 15:39:51.042388+00
017f24b6-07c4-4954-ae7d-266a3b0143f2	6ffc2dab-063d-44af-a3e7-215eaad84634	e5d28f54-0ded-42cb-aabe-70d054a67618	draft	queued	requestor	submitted	\N	951715f9-f437-459d-aa9b-b34a0b821753	2026-09-25 15:39:51.045058+00
e3a71434-908e-4d6b-80f4-0b289b52909d	830cdfcb-df3b-4644-808e-326f472376bb	9e454c72-e784-4e01-ace2-e69001e04681	(created)	draft	system	submission created	\N	\N	2026-09-25 15:39:51.071149+00
d5cecdba-ba67-4b4b-8b0c-d2910b24dac3	830cdfcb-df3b-4644-808e-326f472376bb	9e454c72-e784-4e01-ace2-e69001e04681	draft	queued	requestor	submitted	\N	562bf24c-ae4f-4b14-9c82-7873fce984c2	2026-09-25 15:39:51.073916+00
8ee0cd6c-fc45-49d5-b19c-e48397e47724	11f34eb0-bf3a-4d8a-9156-9746dab1755e	1a02805b-9eee-4298-9ac0-ad3ecfa8ab99	(created)	draft	system	submission created	\N	\N	2026-09-25 15:39:51.099439+00
721f5130-79c1-4688-bcc2-94f14c6acfff	11f34eb0-bf3a-4d8a-9156-9746dab1755e	1a02805b-9eee-4298-9ac0-ad3ecfa8ab99	draft	queued	requestor	submitted	\N	00a4d788-f7d2-4dcd-ab4a-a0d3bc8e4251	2026-09-25 15:39:51.102072+00
c5ab0840-a582-4f55-aa4d-3a99b088171a	93ae110c-924a-4a5f-9db0-8d7b50e3c135	30fac96c-c35a-4b90-a5ed-dcd70cb264d2	(created)	draft	system	submission created	\N	\N	2026-09-25 15:39:51.127599+00
76d773f4-a777-482c-8bf2-3ac8344cc7a3	93ae110c-924a-4a5f-9db0-8d7b50e3c135	30fac96c-c35a-4b90-a5ed-dcd70cb264d2	draft	queued	requestor	submitted	\N	104e0d9d-1448-42c5-9078-6a757cb51f37	2026-09-25 15:39:51.130382+00
\.


--
-- Data for Name: keyword_conflicts; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.keyword_conflicts (id, organization_id, keyword_id_a, keyword_id_b, conflict_type, detail, created_at) FROM stdin;
\.


--
-- Data for Name: keyword_links; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.keyword_links (id, organization_id, keyword_id, link_kind, target_ref, asin, product_id, note, created_at) FROM stdin;
\.


--
-- Data for Name: keywords; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.keywords (id, organization_id, normalized_phrase, original_phrase, marketplace, language, match_type, brand_terms, confidence, freshness_state, created_at) FROM stdin;
78dabb79-0ae3-4c3d-8e9f-c6602489a732	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	dog leash	dog leash	amazon.com	en	exact	[]	1	unknown_age	2026-09-25 12:47:41.4285+00
00430c96-d36c-4393-8570-687a65660f2b	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	dog leash for small dogs	dog leash for small dogs	amazon.com	en	phrase	[]	1	unknown_age	2026-09-25 12:47:41.447498+00
ed9cb248-93eb-4a0a-88d4-fc8e4035d8e6	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	retractable dog leash	retractable dog leash	amazon.com	en	phrase	[]	1	unknown_age	2026-09-25 12:47:41.462273+00
b54f87c2-c659-498a-aed4-e29a066954f6	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	durable dog chew toy	durable dog chew toy	amazon.com	en	exact	[]	1	unknown_age	2026-09-25 12:47:41.476816+00
\.


--
-- Data for Name: legal_documents; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.legal_documents (id, doc_type, version, title, content_hash, status, published_at, created_at) FROM stdin;
a0e3ef7d-0ec5-4bd7-a898-8684b5c86427	privacy_notice	1.0	Privacy Notice (Beta)	05a573b1cb8f2a087491b605c2894609246c4f0740569804574d279ebaaad2d4	published	2026-09-25 14:51:12.786053+00	2026-09-25 14:51:12.786069+00
e758adca-4723-4b26-a74a-fe6285514e46	terms_of_service	1.0	Terms of Service (Beta)	b1d54c9387a439cdd1f4f4a59c83eacf8116edd1a46b3a58f3d12bdaccbc2acd	published	2026-09-25 14:51:12.790263+00	2026-09-25 14:51:12.790277+00
afb0f170-2278-4ef2-bac9-b699c8dbe950	acceptable_use_policy	1.0	Acceptable Use Policy (Beta)	8917d563b218aa53be41483957709811049deba6dc0bcb6a56cb22f6d7732c9f	published	2026-09-25 14:51:12.793512+00	2026-09-25 14:51:12.793522+00
52454187-35a3-42f0-8b57-ed7339678b01	private_beta_addendum	1.0	Private Beta Addendum (Beta)	00c72e991638fc7495f88dc3afc86c6e33ca8487aa267c3fb65f2e382f514339	published	2026-09-25 15:37:31.384001+00	2026-09-25 15:37:31.384024+00
\.


--
-- Data for Name: marketplaces; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.marketplaces (id, code, country, currency, domain, active) FROM stdin;
0864385c-f8eb-4c34-a76c-d39451508733	amazon.com	US	USD	www.amazon.com	t
\.


--
-- Data for Name: memberships; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.memberships (id, organization_id, user_id, role, status, created_at) FROM stdin;
5d737637-84da-4e97-8522-129e3e174557	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	active	2026-09-25 12:46:53.521876+00
5ff99c6892f041a3a652fa851927001d	cd933802-95dc-4ce6-a8b7-15b1879ba1cc	7013f362-8338-48a2-a3f0-0b65d6216a2c	viewer	active	2026-09-25 14:11:44.195248+00
4ef19c52c822404ba1eafc531767c984	7b3dfe7a-545a-4f92-880f-ca37f5d1f7d8	69ff71b2-7a3b-4f5f-9056-2b666d3b0026	viewer	active	2026-09-25 14:51:12.72376+00
e241db5c12bd4374ad74b574e12e2f89	1cd446b8-a2b4-43d9-8adb-869d5e854ffc	8809ba90-55dd-48d0-a895-665fc5872741	operator	active	2026-09-25 14:51:12.801573+00
bae7d5a405904bcfa1eefd0600aace34	c7bdbe56-d353-42b2-aed6-eb7e9ebe2c0e	2bc09d54-2de2-4d09-bd0c-db716530fe25	viewer	active	2026-09-25 14:53:53.215465+00
db41753c4dbb400db0172248dc2d2795	1c30d9ed-d52a-42ed-a4b9-e0bd0f1090eb	4aaa159d-cfe8-41f6-8c52-d2f2d9c214c4	operator	active	2026-09-25 14:53:53.30001+00
a86fc23a80a64ad0880f4a7b1e333952	41f1bdb5-5143-4fc1-804e-45c1d0ad024f	8d23329e-c826-4cf3-9351-e8675d2c55c5	viewer	active	2026-09-25 15:37:32.145932+00
627b96ed9ee54ad58fc6ab5437ffc17d	8856d797-5714-421e-9b68-21977321152b	f8970e4e-f2bc-46e5-b1e2-6de99e823130	operator	active	2026-09-25 15:37:32.257956+00
1014b783-0686-4ef4-ba27-0c922880184e	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	7ed20cf3-772b-41f7-8aab-1eacfdcbcd09	organization_owner	active	2026-09-25 15:37:32.354651+00
f137d5aaec744fbb8a5a73b1571fb9b6	a5dec5ab-0b73-43e7-b488-fa4b5dcbd340	2e02cc0b-0696-4647-b1b9-a8187761767e	viewer	active	2026-09-25 15:38:04.581459+00
e86af7d52c1a4553957c88b78f5fb39f	9b6e00cd-d3cc-49f2-ab24-e45c50d89b55	189e1da9-2344-4468-aa4c-41235f9bd9c0	operator	active	2026-09-25 15:38:04.679149+00
81ba5ca7-21cd-4d71-ac4a-9592dbed4019	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	d16118e8-09c3-45f9-becf-772303be6bda	organization_owner	active	2026-09-25 15:38:04.773936+00
8319dc4a222b41ecad268dd3c323627b	b93d2fc7-f156-4553-b08c-c91232e68197	a647b2b4-57a1-4ac0-9ae1-de5e30a866e5	viewer	active	2026-09-25 15:39:15.769027+00
c6ca6dd2bece42f887126c1b9ea5668b	8f3d00ce-4706-4049-88b1-f080bbb33ffc	4862db1a-85f3-49c1-bed2-1def9d383dbe	operator	active	2026-09-25 15:39:15.863616+00
0d921effb7274f85aee0ad8fd609d684	993df0b6-4bdb-43ea-9e50-715141765180	c46f4c20-58bb-4669-8d5f-1cb18ff0b94a	organization_owner	active	2026-09-25 15:39:15.945857+00
c1d25d4d-7ce9-43cf-aff8-16fd17e8ad09	993df0b6-4bdb-43ea-9e50-715141765180	b0e01231-2313-441a-9bc8-f12449d3d249	organization_owner	active	2026-09-25 15:39:15.999443+00
540ba8daf6b14b31ac02c9afc3637695	5c20de09-2a06-431d-baf3-ac644f4fec9d	ab799989-4af7-44f5-8fe8-c85147cc9d5d	viewer	active	2026-09-25 15:39:50.701206+00
03d2bba643e24588ab9a36e5dc75ccdc	0d9868c5-1b93-4b0c-b8d6-8a97cb21594e	99d0d2b9-2ad9-4e96-bf2f-d0e2d89a7ff5	operator	active	2026-09-25 15:39:50.793486+00
83699de1ee3f4cc384717e0d1e9109f3	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	16d2ec3e-5c6c-4f5e-ae69-a9a3c058b69e	organization_owner	active	2026-09-25 15:39:50.872901+00
6cc8fa94-ed31-47d1-82c6-ef9a43576ef6	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	organization_owner	active	2026-09-25 15:39:50.9208+00
\.


--
-- Data for Name: normalization_decisions; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.normalization_decisions (id, organization_id, original_phrase, normalized_phrase, rule, created_at) FROM stdin;
\.


--
-- Data for Name: observations; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.observations (id, product_id, candidate_id, marketplace_id, provider, provider_record_id, observation_type, observed_value, currency, unit, captured_at, effective_at, expires_at, confidence, verification_state, provenance_class, raw_source_ref, transformation_version, job_run_id, environment, created_at) FROM stdin;
\.


--
-- Data for Name: org_balances; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.org_balances (organization_id, granted, reserved, consumed, updated_at) FROM stdin;
5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	0	0	0	2026-09-25 15:39:50.649715+00
05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	0	0	0	2026-09-25 15:39:50.983974+00
\.


--
-- Data for Name: org_entitlements; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.org_entitlements (organization_id, tier, max_jobs_per_month, export_enabled, advanced_reports, seat_limit, updated_at) FROM stdin;
8856d797-5714-421e-9b68-21977321152b	free	1000	f	f	10	2026-09-25 15:37:32.309576+00
9b6e00cd-d3cc-49f2-ab24-e45c50d89b55	free	1000	f	f	10	2026-09-25 15:38:04.729906+00
5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	free	1000	f	f	10	2026-09-25 15:38:04.964466+00
8f3d00ce-4706-4049-88b1-f080bbb33ffc	free	1000	f	f	10	2026-09-25 15:39:15.915498+00
993df0b6-4bdb-43ea-9e50-715141765180	free	1000	f	f	10	2026-09-25 15:39:16.077064+00
0d9868c5-1b93-4b0c-b8d6-8a97cb21594e	free	1000	f	f	10	2026-09-25 15:39:50.843795+00
05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	free	1000	f	f	10	2026-09-25 15:39:51.17325+00
\.


--
-- Data for Name: organizations; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.organizations (id, name, slug, environment, active, created_at) FROM stdin;
5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	Staging Smoke	staging-smoke	production	t	2026-09-25 12:46:53.510613+00
cd933802-95dc-4ce6-a8b7-15b1879ba1cc	Staging Viewer Org	staging-viewer-org	production	t	2026-09-25 14:11:44.189972+00
7b3dfe7a-545a-4f92-880f-ca37f5d1f7d8	Staging Viewer Org	staging-viewer-org	production	t	2026-09-25 14:51:12.705425+00
1cd446b8-a2b4-43d9-8adb-869d5e854ffc	Staging Beta Org	staging-beta-org	production	t	2026-09-25 14:51:12.796255+00
c7bdbe56-d353-42b2-aed6-eb7e9ebe2c0e	Staging Viewer Org	staging-viewer-org	production	t	2026-09-25 14:53:53.208613+00
1c30d9ed-d52a-42ed-a4b9-e0bd0f1090eb	Staging Beta Org	staging-beta-org	production	t	2026-09-25 14:53:53.295041+00
41f1bdb5-5143-4fc1-804e-45c1d0ad024f	Staging Viewer Org	staging-viewer-org	production	t	2026-09-25 15:37:32.140651+00
8856d797-5714-421e-9b68-21977321152b	Staging Beta Org	staging-beta-org	production	t	2026-09-25 15:37:32.252675+00
a5dec5ab-0b73-43e7-b488-fa4b5dcbd340	Staging Viewer Org	staging-viewer-org	production	t	2026-09-25 15:38:04.57196+00
9b6e00cd-d3cc-49f2-ab24-e45c50d89b55	Staging Beta Org	staging-beta-org	production	t	2026-09-25 15:38:04.674436+00
b93d2fc7-f156-4553-b08c-c91232e68197	Staging Viewer Org	staging-viewer-org	production	t	2026-09-25 15:39:15.762325+00
8f3d00ce-4706-4049-88b1-f080bbb33ffc	Staging Beta Org	staging-beta-org	production	t	2026-09-25 15:39:15.858789+00
993df0b6-4bdb-43ea-9e50-715141765180	E2E Org	e2e-org-1790350755940	production	t	2026-09-25 15:39:15.940883+00
5c20de09-2a06-431d-baf3-ac644f4fec9d	Staging Viewer Org	staging-viewer-org	production	t	2026-09-25 15:39:50.694516+00
0d9868c5-1b93-4b0c-b8d6-8a97cb21594e	Staging Beta Org	staging-beta-org	production	t	2026-09-25 15:39:50.78859+00
05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	E2E Org	e2e-org-1790350790868	production	t	2026-09-25 15:39:50.86821+00
\.


--
-- Data for Name: pack_configs; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.pack_configs (id, product_id, count, unit, unit_type, is_multipack, is_bundle, verification_state) FROM stdin;
\.


--
-- Data for Name: preview_sessions; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.preview_sessions (id, actor_user_id, target_organization_id, target_role, started_at, ended_at, reason, read_only, active) FROM stdin;
73ffa11e-e1b4-49f4-9286-678ff87055cf	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	2026-09-25 12:46:53.688421+00	\N	staging smoke	t	t
c4335540-0bea-41c4-a3b1-29c3ae2c8d2d	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	2026-09-25 12:47:41.062393+00	2026-09-25 12:47:41.081108+00	staging smoke	t	f
1f7dd4d2-bdfa-4846-b79e-58a65433425f	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	2026-09-25 12:48:05.026168+00	2026-09-25 12:48:05.039821+00	staging smoke	t	f
ba86900d-807f-48b4-998f-1ced08a4973d	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	2026-09-25 13:42:39.956842+00	2026-09-25 13:42:39.971923+00	staging smoke	t	f
633bf211-32a7-4741-b50e-069da58a7b3f	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	2026-09-25 13:42:57.116693+00	2026-09-25 13:42:57.130416+00	staging smoke	t	f
848d8517-6ce9-4f2e-915c-845739356e16	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	2026-09-25 13:43:27.884386+00	2026-09-25 13:43:27.899281+00	staging smoke	t	f
cd7eb473-9fb7-4bb9-9c2e-acdd644e8232	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	2026-09-25 13:43:43.966123+00	2026-09-25 13:43:43.979246+00	staging smoke	t	f
1c675d9f-e454-46b3-85c7-c19e029e8857	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	2026-09-25 14:11:43.707315+00	2026-09-25 14:11:43.723646+00	staging smoke	t	f
6310af0e-cd5d-4130-9cb1-f5f8831533e2	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	2026-09-25 14:51:11.671932+00	2026-09-25 14:51:11.688363+00	staging smoke	t	f
30704cc4-4480-4d91-8c04-2f11de7aae57	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	2026-09-25 14:53:52.734599+00	2026-09-25 14:53:52.752442+00	staging smoke	t	f
f69f9a45-05d5-4fb4-b8c4-a48cdd16c5c6	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	2026-09-25 15:37:31.629084+00	2026-09-25 15:37:31.648479+00	staging smoke	t	f
65d2d063-5c20-49b4-a018-4c1af0c8b711	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	2026-09-25 15:38:04.071603+00	2026-09-25 15:38:04.089389+00	staging smoke	t	f
d5c350dd-f32c-4952-a6ca-81574f408d08	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	2026-09-25 15:39:15.245999+00	2026-09-25 15:39:15.263157+00	staging smoke	t	f
b20bbfef-123b-4c31-bf62-153d5345caad	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	2026-09-25 15:39:50.176221+00	2026-09-25 15:39:50.19283+00	staging smoke	t	f
\.


--
-- Data for Name: pricing_policies; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.pricing_policies (version, platform_markup, minimum_charge, service_multipliers, free_local_execution, failed_run_charge) FROM stdin;
shadow-0	0	0	{}	t	f
\.


--
-- Data for Name: product_aliases; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.product_aliases (id, product_id, alias_value, reason, created_at) FROM stdin;
\.


--
-- Data for Name: product_identifiers; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.product_identifiers (id, product_id, kind, raw_value, normalized_value, marketplace_id, verification_state, created_at) FROM stdin;
\.


--
-- Data for Name: providers; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.providers (id, provider_key, name, category, adapter_module, read_capable, write_capable, sandbox_supported, credential_ref_names, rate_limit_rpm, timeout_seconds, cost_model, health, enabled) FROM stdin;
25effb03-472b-4948-8425-074a5e891dd3	ollama	Ollama (local)	ai	\N	t	f	t	[]	\N	\N	\N	unknown	f
23b3fb84-6b79-4e41-8e65-c2161621491c	fixture_price	Fixture Price (dev)	discovery	\N	t	f	t	[]	\N	\N	\N	unknown	f
\.


--
-- Data for Name: rank_observations; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.rank_observations (id, organization_id, keyword_id, asin, rank, placement, observed_at, source, confidence, freshness_state, created_at) FROM stdin;
\.


--
-- Data for Name: rejected_rows; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.rejected_rows (id, organization_id, import_batch_id, source_file_id, row_index, row_json, rejection_reason, created_at) FROM stdin;
e4c9bf40-9553-412d-bd59-9c976349ced8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	7b10eb3c-df22-4bbc-99a9-b6495ee08aed	11378e2b-7222-4ed5-9a11-fe7c184d955d	4	{"Spend": "0.00", "Clicks": "0", "Orders": "0", "Revenue": "", "Currency": "USD", "End Date": "2026-08-31", "Match Type": "Broad", "Start Date": "2026-08-01", "Impressions": "0", "Marketplace": "amazon.com", "Search Term": "", "Ad Group Name": "Dog Leads", "Campaign Name": "KW Launch"}	missing_search_term	2026-09-25 12:47:41.487836+00
\.


--
-- Data for Name: schedule_occurrences; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.schedule_occurrences (id, schedule_id, occurrence_key, scheduled_for, enqueued_job_request_id, state, created_at) FROM stdin;
69729b29-d226-43f9-baf4-7b7a57315348	a25e0083-a2f2-4347-8cc3-297c6b6c3bc7	2026-09-25T12:47:36.370345+00:00	2026-09-25 12:47:36.370345+00	bb7b2f11-44e3-44ca-8749-c6a56ee4051d	enqueued	2026-09-25 12:47:41.377616+00
87506054-2bd7-4a87-90fd-7c057a2b9b6a	6415cb76-6249-46ad-9649-30d1025ba72c	2026-09-25T12:48:00.349508+00:00	2026-09-25 12:48:00.349508+00	a9ee27a7-5545-4d87-a365-1474d10a102b	enqueued	2026-09-25 12:48:05.355676+00
b09fffa0-f2d4-418d-9ae8-4341a67f840b	40b37ae5-1596-4a99-8859-76e7c022769f	2026-09-25T13:42:35.292807+00:00	2026-09-25 13:42:35.292807+00	04619a31-fada-4f30-8428-e85428a36d62	enqueued	2026-09-25 13:42:40.300289+00
7c502e1d-26ee-468e-94e1-2a64f7c95758	eb43ac8b-9092-41cd-916e-7029f677874d	2026-09-25T13:42:52.427134+00:00	2026-09-25 13:42:52.427134+00	74e79cff-759d-4806-b22c-c13f230ff015	enqueued	2026-09-25 13:42:57.434406+00
0fd5a932-db86-4540-bd2c-44f295478313	6c5ed8fa-7912-4a20-8cc0-952cd2522db7	2026-09-25T13:43:23.199997+00:00	2026-09-25 13:43:23.199997+00	947d35bd-7f5e-4967-800c-e78b630cd423	enqueued	2026-09-25 13:43:28.208251+00
48b7ab45-21ee-425c-8b50-bfeb3af0a03a	8615ca91-de1c-49ea-85ea-74bede8ae9b8	2026-09-25T13:43:39.275532+00:00	2026-09-25 13:43:39.275532+00	c9ed2300-a06c-420f-b8fa-b45f0bd28d6b	enqueued	2026-09-25 13:43:44.282401+00
e169bb5e-af1b-43b6-85b7-331cdf5be308	a25e0083-a2f2-4347-8cc3-297c6b6c3bc7	2026-09-25T13:47:36.370345+00:00	2026-09-25 13:47:36.370345+00	\N	misfired	2026-09-25 14:11:43.989057+00
9d3399c9-caec-409f-99fc-c5440ea24373	6415cb76-6249-46ad-9649-30d1025ba72c	2026-09-25T13:48:00.349508+00:00	2026-09-25 13:48:00.349508+00	\N	misfired	2026-09-25 14:11:43.998375+00
5338692e-8048-4531-b172-6c04b6d55792	9e1827ad-dcba-457c-bc05-5168a0f220c8	2026-09-25T14:11:38.982073+00:00	2026-09-25 14:11:38.982073+00	a9c8bbb2-aded-4aaa-abaa-3ff70acbee4f	enqueued	2026-09-25 14:11:44.007961+00
4e21dbf3-4a6d-4549-83e7-99e281d7d410	40b37ae5-1596-4a99-8859-76e7c022769f	2026-09-25T14:42:35.292807+00:00	2026-09-25 14:42:35.292807+00	df75213d-9b26-4a9f-bd32-4cf32de0e372	enqueued	2026-09-25 14:51:12.017016+00
3100e6d4-22c7-40dd-911e-cf386791b959	eb43ac8b-9092-41cd-916e-7029f677874d	2026-09-25T14:42:52.427134+00:00	2026-09-25 14:42:52.427134+00	41f26384-a34f-4fc6-987c-087a046cf42c	enqueued	2026-09-25 14:51:12.050819+00
461e0bf3-d88a-473f-95d1-69bb70ddad91	6c5ed8fa-7912-4a20-8cc0-952cd2522db7	2026-09-25T14:43:23.199997+00:00	2026-09-25 14:43:23.199997+00	8368c245-aeb2-4758-b4c8-ba91d8aec34e	enqueued	2026-09-25 14:51:12.085903+00
5c879e74-fa4d-4555-b431-9f36df90de02	8615ca91-de1c-49ea-85ea-74bede8ae9b8	2026-09-25T14:43:39.275532+00:00	2026-09-25 14:43:39.275532+00	3013ce28-c3cc-4798-be62-1f1df2b99f45	enqueued	2026-09-25 14:51:12.119563+00
b6995aaf-f5e3-480a-a6b1-94758b00589e	a25e0083-a2f2-4347-8cc3-297c6b6c3bc7	2026-09-25T14:47:36.370345+00:00	2026-09-25 14:47:36.370345+00	d1b04528-b5f3-4cd7-a5d8-6534f355e04b	enqueued	2026-09-25 14:51:12.152021+00
0506797d-16db-4292-962f-367fff69ff4e	6415cb76-6249-46ad-9649-30d1025ba72c	2026-09-25T14:48:00.349508+00:00	2026-09-25 14:48:00.349508+00	55e5d9d2-4d45-4d32-a5cb-6566ea148cd6	enqueued	2026-09-25 14:51:12.183072+00
0bf8bc5b-9942-4309-bb0d-86bf8b640b3b	71f8100f-4b51-4cca-8006-1c767079361e	2026-09-25T14:51:07.007024+00:00	2026-09-25 14:51:07.007024+00	f0a2b5a5-b0d5-4316-8cd4-1e095e241060	enqueued	2026-09-25 14:51:12.215739+00
782abceb-a785-4d96-bbf6-d94a708a1bf3	af6eb320-1eb3-4f10-9b63-67960864a378	2026-09-25T14:53:48.009537+00:00	2026-09-25 14:53:48.009537+00	d9001c70-db76-4ee9-a52f-d102a0284ae1	enqueued	2026-09-25 14:53:53.016715+00
ce1f98ff-1dbd-4b8e-aaef-cc70731251b7	9e1827ad-dcba-457c-bc05-5168a0f220c8	2026-09-25T15:11:38.982073+00:00	2026-09-25 15:11:38.982073+00	\N	misfired	2026-09-25 15:37:31.9314+00
4d0f4922-6f04-4755-9a7a-e4246943b5bf	74ed46b8-b272-49cb-ad05-9e8083fb1c8c	2026-09-25T15:37:26.923883+00:00	2026-09-25 15:37:26.923883+00	3c51e672-9ffc-4708-a633-d6b0080b97db	enqueued	2026-09-25 15:37:31.941006+00
53853da1-9738-4041-b164-0004f26a3a87	4084524a-06b2-4b3f-b010-48fff44e98cb	2026-09-25T15:37:59.371396+00:00	2026-09-25 15:37:59.371396+00	bb9de075-0d97-4a93-8b3e-72c2bbf0b801	enqueued	2026-09-25 15:38:04.379398+00
26a1adef-ccc3-4cc6-a0e8-ba6a9b7a79a5	919354fc-10e9-42d6-a254-c88d1c47bf15	2026-09-25T15:39:10.542065+00:00	2026-09-25 15:39:10.542065+00	72709084-6173-43bf-ac05-71607e3bb043	enqueued	2026-09-25 15:39:15.549205+00
c69c1fef-bf3a-409d-8d66-50224136c01d	81728559-dc82-414e-aa1e-e737ebf2818a	2026-09-25T15:39:45.488996+00:00	2026-09-25 15:39:45.488996+00	4bcb49ea-f1e8-4f40-92ae-74d72dd2a783	enqueued	2026-09-25 15:39:50.495576+00
\.


--
-- Data for Name: search_terms; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.search_terms (id, organization_id, raw_term, normalized_term, marketplace, search_volume, observed_volume, impressions, clicks, spend, orders, revenue, source, observed_at, created_at) FROM stdin;
550c0a76-d1c7-46f5-ac2e-c77706afd705	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	dog leash	dog leash	amazon.com	\N	\N	1200	45	22.50	3	89.97	import	\N	2026-09-25 12:47:41.434109+00
34d0090e-fff9-42e3-b0c4-00603c5bb5b9	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	dog leash for small dogs	dog leash for small dogs	amazon.com	\N	\N	340	12	6.00	1	29.99	import	\N	2026-09-25 12:47:41.45084+00
49247626-9c2e-4d6f-9114-a2fb22fd7bab	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	retractable dog leash	retractable dog leash	amazon.com	\N	\N	810	33	16.50	2	59.98	import	\N	2026-09-25 12:47:41.46548+00
21e21fb5-cd9a-4bc7-bf78-396174fcc065	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	durable dog chew toy	durable dog chew toy	amazon.com	\N	\N	95	4	2.00	0	\N	import	\N	2026-09-25 12:47:41.479994+00
\.


--
-- Data for Name: sessions; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.sessions (jti, user_id, organization_id, issued_at, expires_at, revoked_at, revoked_reason) FROM stdin;
sess_test_818d3840-1a16-40b6-9757-9e5a67af68f8	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	2026-09-25 12:46:53.636401+00	2026-09-25 13:46:53+00	\N	\N
staging-revoke-1	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	2026-09-25 12:46:53.665916+00	2026-09-25 13:46:53+00	2026-09-25 12:46:53.676003+00	operator_revoked
staging-revoke-1790340484999	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	2026-09-25 12:48:05.002018+00	2026-09-25 13:48:04+00	2026-09-25 12:48:05.013315+00	operator_revoked
staging-revoke-1790343759932	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	2026-09-25 13:42:39.935201+00	2026-09-25 14:42:39+00	2026-09-25 13:42:39.944458+00	operator_revoked
staging-revoke-1790343777083	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	2026-09-25 13:42:57.086148+00	2026-09-25 14:42:57+00	2026-09-25 13:42:57.102848+00	operator_revoked
staging-revoke-1790343807854	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	2026-09-25 13:43:27.856877+00	2026-09-25 14:43:27+00	2026-09-25 13:43:27.870937+00	operator_revoked
staging-revoke-1790343823940	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	2026-09-25 13:43:43.943035+00	2026-09-25 14:43:43+00	2026-09-25 13:43:43.9524+00	operator_revoked
staging-revoke-1790345503675	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	2026-09-25 14:11:43.678518+00	2026-09-25 15:11:43+00	2026-09-25 14:11:43.688473+00	operator_revoked
sess_test_7013f362-8338-48a2-a3f0-0b65d6216a2c	7013f362-8338-48a2-a3f0-0b65d6216a2c	cd933802-95dc-4ce6-a8b7-15b1879ba1cc	2026-09-25 14:11:44.231786+00	2026-09-25 15:11:44+00	\N	\N
staging-revoke-1790347871640	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	2026-09-25 14:51:11.642922+00	2026-09-25 15:51:11+00	2026-09-25 14:51:11.652375+00	operator_revoked
sess_test_69ff71b2-7a3b-4f5f-9056-2b666d3b0026	69ff71b2-7a3b-4f5f-9056-2b666d3b0026	7b3dfe7a-545a-4f92-880f-ca37f5d1f7d8	2026-09-25 14:51:12.741884+00	2026-09-25 15:51:12+00	\N	\N
sess_test_8809ba90-55dd-48d0-a895-665fc5872741	8809ba90-55dd-48d0-a895-665fc5872741	1cd446b8-a2b4-43d9-8adb-869d5e854ffc	2026-09-25 14:51:12.809191+00	2026-09-25 15:51:12+00	\N	\N
staging-revoke-1790347963767	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	2026-09-25 14:52:43.770234+00	2026-09-25 15:52:43+00	2026-09-25 14:52:43.779189+00	operator_revoked
staging-revoke-1790347974721	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	2026-09-25 14:52:54.724504+00	2026-09-25 15:52:54+00	2026-09-25 14:52:54.73407+00	operator_revoked
staging-revoke-1790348032703	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	2026-09-25 14:53:52.706743+00	2026-09-25 15:53:52+00	2026-09-25 14:53:52.71675+00	operator_revoked
sess_test_2bc09d54-2de2-4d09-bd0c-db716530fe25	2bc09d54-2de2-4d09-bd0c-db716530fe25	c7bdbe56-d353-42b2-aed6-eb7e9ebe2c0e	2026-09-25 14:53:53.2514+00	2026-09-25 15:53:53+00	\N	\N
sess_test_4aaa159d-cfe8-41f6-8c52-d2f2d9c214c4	4aaa159d-cfe8-41f6-8c52-d2f2d9c214c4	1c30d9ed-d52a-42ed-a4b9-e0bd0f1090eb	2026-09-25 14:53:53.30569+00	2026-09-25 15:53:53+00	\N	\N
staging-revoke-1790350651595	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	2026-09-25 15:37:31.598982+00	2026-09-25 16:37:31+00	2026-09-25 15:37:31.610002+00	operator_revoked
sess_test_8d23329e-c826-4cf3-9351-e8675d2c55c5	8d23329e-c826-4cf3-9351-e8675d2c55c5	41f1bdb5-5143-4fc1-804e-45c1d0ad024f	2026-09-25 15:37:32.200963+00	2026-09-25 16:37:32+00	\N	\N
sess_test_f8970e4e-f2bc-46e5-b1e2-6de99e823130	f8970e4e-f2bc-46e5-b1e2-6de99e823130	8856d797-5714-421e-9b68-21977321152b	2026-09-25 15:37:32.264943+00	2026-09-25 16:37:32+00	\N	\N
staging-revoke-1790350684043	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	2026-09-25 15:38:04.046001+00	2026-09-25 16:38:04+00	2026-09-25 15:38:04.054738+00	operator_revoked
sess_test_2e02cc0b-0696-4647-b1b9-a8187761767e	2e02cc0b-0696-4647-b1b9-a8187761767e	a5dec5ab-0b73-43e7-b488-fa4b5dcbd340	2026-09-25 15:38:04.62751+00	2026-09-25 16:38:04+00	\N	\N
sess_test_189e1da9-2344-4468-aa4c-41235f9bd9c0	189e1da9-2344-4468-aa4c-41235f9bd9c0	9b6e00cd-d3cc-49f2-ab24-e45c50d89b55	2026-09-25 15:38:04.684994+00	2026-09-25 16:38:04+00	\N	\N
sess_test_d16118e8-09c3-45f9-becf-772303be6bda	d16118e8-09c3-45f9-becf-772303be6bda	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	2026-09-25 15:38:04.788024+00	2026-09-25 16:38:04+00	\N	\N
staging-revoke-1790350755218	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	2026-09-25 15:39:15.221526+00	2026-09-25 16:39:15+00	2026-09-25 15:39:15.229986+00	operator_revoked
sess_test_a647b2b4-57a1-4ac0-9ae1-de5e30a866e5	a647b2b4-57a1-4ac0-9ae1-de5e30a866e5	b93d2fc7-f156-4553-b08c-c91232e68197	2026-09-25 15:39:15.813217+00	2026-09-25 16:39:15+00	\N	\N
sess_test_4862db1a-85f3-49c1-bed2-1def9d383dbe	4862db1a-85f3-49c1-bed2-1def9d383dbe	8f3d00ce-4706-4049-88b1-f080bbb33ffc	2026-09-25 15:39:15.869078+00	2026-09-25 16:39:15+00	\N	\N
sess_test_c46f4c20-58bb-4669-8d5f-1cb18ff0b94a	c46f4c20-58bb-4669-8d5f-1cb18ff0b94a	993df0b6-4bdb-43ea-9e50-715141765180	2026-09-25 15:39:15.980174+00	2026-09-25 16:39:15+00	\N	\N
sess_test_b0e01231-2313-441a-9bc8-f12449d3d249	b0e01231-2313-441a-9bc8-f12449d3d249	993df0b6-4bdb-43ea-9e50-715141765180	2026-09-25 15:39:16.011676+00	2026-09-25 16:39:16+00	\N	\N
staging-revoke-1790350790147	818d3840-1a16-40b6-9757-9e5a67af68f8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	2026-09-25 15:39:50.151193+00	2026-09-25 16:39:50+00	2026-09-25 15:39:50.159625+00	operator_revoked
sess_test_ab799989-4af7-44f5-8fe8-c85147cc9d5d	ab799989-4af7-44f5-8fe8-c85147cc9d5d	5c20de09-2a06-431d-baf3-ac644f4fec9d	2026-09-25 15:39:50.744452+00	2026-09-25 16:39:50+00	\N	\N
sess_test_99d0d2b9-2ad9-4e96-bf2f-d0e2d89a7ff5	99d0d2b9-2ad9-4e96-bf2f-d0e2d89a7ff5	0d9868c5-1b93-4b0c-b8d6-8a97cb21594e	2026-09-25 15:39:50.799044+00	2026-09-25 16:39:50+00	\N	\N
sess_test_16d2ec3e-5c6c-4f5e-ae69-a9a3c058b69e	16d2ec3e-5c6c-4f5e-ae69-a9a3c058b69e	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	2026-09-25 15:39:50.902683+00	2026-09-25 16:39:50+00	\N	\N
sess_test_5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	2026-09-25 15:39:50.931776+00	2026-09-25 16:39:50+00	\N	\N
\.


--
-- Data for Name: source_files; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.source_files (id, organization_id, file_name, file_sha256, file_size, marketplace, currency, report_type, date_from, date_to, status, registered_at, created_at) FROM stdin;
11378e2b-7222-4ed5-9a11-fe7c184d955d	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	search_term_report_sample.csv	d19d576f82e5ddb5abd4479ae16d804992d173521218f2cb8bab82a4265f61b1	611	amazon.com	USD	search_term	2026-08-01 00:00:00+00	2026-08-31 00:00:00+00	imported	2026-09-25 12:47:41.416156+00	2026-09-25 12:47:41.416168+00
\.


--
-- Data for Name: source_rows; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.source_rows (id, organization_id, import_batch_id, source_file_id, row_index, row_json, status, created_at) FROM stdin;
e69a66be-c283-49d5-a42f-04437ced9820	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	7b10eb3c-df22-4bbc-99a9-b6495ee08aed	11378e2b-7222-4ed5-9a11-fe7c184d955d	0	{"Spend": "22.50", "Clicks": "45", "Orders": "3", "Revenue": "89.97", "Currency": "USD", "End Date": "2026-08-31", "Match Type": "Exact", "Start Date": "2026-08-01", "Impressions": "1200", "Marketplace": "amazon.com", "Search Term": "dog leash", "Ad Group Name": "Dog Leads", "Campaign Name": "KW Launch"}	accepted	2026-09-25 12:47:41.424478+00
8836cd7b-f409-4ed8-bb7f-0783760680c6	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	7b10eb3c-df22-4bbc-99a9-b6495ee08aed	11378e2b-7222-4ed5-9a11-fe7c184d955d	1	{"Spend": "6.00", "Clicks": "12", "Orders": "1", "Revenue": "29.99", "Currency": "USD", "End Date": "2026-08-31", "Match Type": "Phrase", "Start Date": "2026-08-01", "Impressions": "340", "Marketplace": "amazon.com", "Search Term": "dog leash for small dogs", "Ad Group Name": "Dog Leads", "Campaign Name": "KW Launch"}	accepted	2026-09-25 12:47:41.444285+00
e5e4cb21-ad11-4197-b47c-0030e3d1debc	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	7b10eb3c-df22-4bbc-99a9-b6495ee08aed	11378e2b-7222-4ed5-9a11-fe7c184d955d	2	{"Spend": "16.50", "Clicks": "33", "Orders": "2", "Revenue": "59.98", "Currency": "USD", "End Date": "2026-08-31", "Match Type": "Phrase", "Start Date": "2026-08-01", "Impressions": "810", "Marketplace": "amazon.com", "Search Term": "retractable dog leash", "Ad Group Name": "Dog Leads", "Campaign Name": "KW Launch"}	accepted	2026-09-25 12:47:41.459161+00
6b37f924-5e43-4ffd-be0e-5c517e96029e	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	7b10eb3c-df22-4bbc-99a9-b6495ee08aed	11378e2b-7222-4ed5-9a11-fe7c184d955d	3	{"Spend": "2.00", "Clicks": "4", "Orders": "0", "Revenue": "", "Currency": "USD", "End Date": "2026-08-31", "Match Type": "Exact", "Start Date": "2026-08-01", "Impressions": "95", "Marketplace": "amazon.com", "Search Term": "durable dog chew toy", "Ad Group Name": "Chews", "Campaign Name": "KW Launch"}	accepted	2026-09-25 12:47:41.473675+00
\.


--
-- Data for Name: subscriptions; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.subscriptions (id, organization_id, billing_customer_id, processor_subscription_id, price_id, tier, status, current_period_end, created_at, updated_at) FROM stdin;
8726f217-7bdd-4011-b86b-0564dfc84086	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	dc4cea49-2b69-4252-bd97-98eb732a8e6a	sub_st	price_trial	trial	canceled	\N	2026-09-25 15:38:04.842057+00	2026-09-25 15:38:04.961832+00
8a9aa4cd-19ce-4e28-a34f-4baf005a92dc	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	55e92d35-c025-46ee-a7d9-2a674cf8601c	sub_1790350790868	price_trial	trial	canceled	\N	2026-09-25 15:39:50.980771+00	2026-09-25 15:39:51.170418+00
\.


--
-- Data for Name: supplier_documentation; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.supplier_documentation (id, supplier_id, product_id, supply_state, documentation_state, note, created_at) FROM stdin;
\.


--
-- Data for Name: suppliers; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.suppliers (id, name, supplier_class, public_catalog_url, created_at) FROM stdin;
\.


--
-- Data for Name: targets; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.targets (id, organization_id, keyword_id, campaign_id, ad_group_id, match_type, bid, status, created_at) FROM stdin;
5ccbb06a-95bf-4a9f-9333-b0e41d7a181e	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	78dabb79-0ae3-4c3d-8e9f-c6602489a732	KW Launch	Dog Leads	exact	\N	active	2026-09-25 12:47:41.438+00
115f591e-c3a4-4a31-9540-0596824d36d3	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	00430c96-d36c-4393-8570-687a65660f2b	KW Launch	Dog Leads	phrase	\N	active	2026-09-25 12:47:41.453714+00
e43e5ff5-4693-4880-bbdb-9c5e6dd9d29a	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	ed9cb248-93eb-4a0a-88d4-fc8e4035d8e6	KW Launch	Dog Leads	phrase	\N	active	2026-09-25 12:47:41.468116+00
2b85d000-74fb-4543-861e-3c7c97fea3da	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	b54f87c2-c659-498a-aed4-e29a066954f6	KW Launch	Chews	exact	\N	active	2026-09-25 12:47:41.482596+00
\.


--
-- Data for Name: ui_preferences; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.ui_preferences (user_id, organization_id, key, value, updated_at) FROM stdin;
\.


--
-- Data for Name: unresolved_candidates; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.unresolved_candidates (id, raw_asin, raw_title, raw_identifier, reason, source, source_identifier, created_at) FROM stdin;
\.


--
-- Data for Name: usage_events; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.usage_events (id, organization_id, user_id, service, workflow_run_id, provider, model_or_endpoint, input_units, output_units, provider_reported_cost, estimated_cost, credits_debited_shadow, cost_kind, status, idempotency_key, reversal_ref, environment, occurred_at, provenance) FROM stdin;
fe304996-9803-42b2-b337-b045588dcc1a	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	221d84bc-4761-4991-a5aa-acbe38c1e303	local	\N	\N	\N	0	0	0	reported	finalized	settle:221d84bc-4761-4991-a5aa-acbe38c1e303:1	221d84bc-4761-4991-a5aa-acbe38c1e303	production	2026-09-25 12:47:41.18273+00	{"ok": true, "kind": "job_settlement", "job_id": "2d56906f-32ab-438b-a817-f8baef2559f0", "run_id": "221d84bc-4761-4991-a5aa-acbe38c1e303", "attempt": 1, "failure_class": null}
b6b16144-ba6f-4729-a928-01072e701313	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	e921643e-db91-4827-969e-ed3ef02faf92	local	\N	\N	\N	0	0	0	estimated	finalized	settle:e921643e-db91-4827-969e-ed3ef02faf92:1	e921643e-db91-4827-969e-ed3ef02faf92	production	2026-09-25 12:47:41.275935+00	{"ok": false, "kind": "job_settlement", "job_id": "1faed168-4681-4d21-9407-62ac9f955cda", "run_id": "e921643e-db91-4827-969e-ed3ef02faf92", "attempt": 1, "failure_class": "transient_error"}
d099454d-441d-41f5-aff0-e7788430b0f9	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	e921643e-db91-4827-969e-ed3ef02faf92	local	\N	\N	\N	0	0	0	reported	finalized	settle:e921643e-db91-4827-969e-ed3ef02faf92:2	e921643e-db91-4827-969e-ed3ef02faf92	production	2026-09-25 12:47:41.348281+00	{"ok": true, "kind": "job_settlement", "job_id": "1faed168-4681-4d21-9407-62ac9f955cda", "run_id": "e921643e-db91-4827-969e-ed3ef02faf92", "attempt": 2, "failure_class": null}
9007cc44-faa8-4602-9352-7624949d72fc	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	870cad35-bcfe-42cc-ad93-accbc0ee6838	local	\N	\N	\N	0	0	0	reported	finalized	settle:870cad35-bcfe-42cc-ad93-accbc0ee6838:1	870cad35-bcfe-42cc-ad93-accbc0ee6838	production	2026-09-25 12:48:05.127744+00	{"ok": true, "kind": "job_settlement", "job_id": "bb7b2f11-44e3-44ca-8749-c6a56ee4051d", "run_id": "870cad35-bcfe-42cc-ad93-accbc0ee6838", "attempt": 1, "failure_class": null}
f837f2bd-c74e-41e0-979b-0c1a8a7000b7	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	f1475883-1c5b-4903-aaaf-b5749f2bbbf6	local	\N	\N	\N	0	0	0	reported	finalized	settle:f1475883-1c5b-4903-aaaf-b5749f2bbbf6:1	f1475883-1c5b-4903-aaaf-b5749f2bbbf6	production	2026-09-25 12:48:05.17688+00	{"ok": true, "kind": "job_settlement", "job_id": "3cee773e-9b1c-484f-8538-4bc9d37773d5", "run_id": "f1475883-1c5b-4903-aaaf-b5749f2bbbf6", "attempt": 1, "failure_class": null}
6e8f8556-5d32-465e-a0c5-0ceda6ab3e3d	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	63dcf6f3-2062-4538-80ce-d6b57683b3e8	local	\N	\N	\N	0	0	0	estimated	finalized	settle:63dcf6f3-2062-4538-80ce-d6b57683b3e8:1	63dcf6f3-2062-4538-80ce-d6b57683b3e8	production	2026-09-25 12:48:05.259667+00	{"ok": false, "kind": "job_settlement", "job_id": "95d4a73e-2173-489d-ab2c-9857472049de", "run_id": "63dcf6f3-2062-4538-80ce-d6b57683b3e8", "attempt": 1, "failure_class": "transient_error"}
14df9f80-35a6-41a5-b7eb-9976b54ca059	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	63dcf6f3-2062-4538-80ce-d6b57683b3e8	local	\N	\N	\N	0	0	0	reported	finalized	settle:63dcf6f3-2062-4538-80ce-d6b57683b3e8:2	63dcf6f3-2062-4538-80ce-d6b57683b3e8	production	2026-09-25 12:48:05.32972+00	{"ok": true, "kind": "job_settlement", "job_id": "95d4a73e-2173-489d-ab2c-9857472049de", "run_id": "63dcf6f3-2062-4538-80ce-d6b57683b3e8", "attempt": 2, "failure_class": null}
78a1e645-03fb-49bd-8087-784971ec3323	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	85f3b973-6cdd-4c00-8f18-b09d72226c07	local	\N	\N	\N	0	0	0	reported	finalized	settle:85f3b973-6cdd-4c00-8f18-b09d72226c07:1	85f3b973-6cdd-4c00-8f18-b09d72226c07	production	2026-09-25 13:42:40.069719+00	{"ok": true, "kind": "job_settlement", "job_id": "a9ee27a7-5545-4d87-a365-1474d10a102b", "run_id": "85f3b973-6cdd-4c00-8f18-b09d72226c07", "attempt": 1}
ee423fca-d7ff-4f56-a25c-835e52c1ecac	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	bcb65321-4548-465f-983f-9cd42242069b	local	\N	\N	\N	0	0	0	reported	finalized	settle:bcb65321-4548-465f-983f-9cd42242069b:1	bcb65321-4548-465f-983f-9cd42242069b	production	2026-09-25 13:42:40.121815+00	{"ok": true, "kind": "job_settlement", "job_id": "cc39a661-801a-42f2-9ccc-b0ef2f10137e", "run_id": "bcb65321-4548-465f-983f-9cd42242069b", "attempt": 1}
58994878-814e-410e-8b88-78f63874e3ec	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	028df412-3cd1-4027-9484-8e2677da0df2	local	\N	\N	\N	0	0	0	reported	finalized	settle:028df412-3cd1-4027-9484-8e2677da0df2:2	028df412-3cd1-4027-9484-8e2677da0df2	production	2026-09-25 13:42:40.271386+00	{"ok": true, "kind": "job_settlement", "job_id": "dee8ad4e-8fe6-40e3-885f-d83b287d400d", "run_id": "028df412-3cd1-4027-9484-8e2677da0df2", "attempt": 2}
8d4fbe0b-db6c-46d0-aa46-88f0f52517fe	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	013e1cd7-ca06-4dd8-85be-8475bde12d48	local	\N	\N	\N	0	0	0	reported	finalized	settle:013e1cd7-ca06-4dd8-85be-8475bde12d48:1	013e1cd7-ca06-4dd8-85be-8475bde12d48	production	2026-09-25 13:42:57.213453+00	{"ok": true, "kind": "job_settlement", "job_id": "04619a31-fada-4f30-8428-e85428a36d62", "run_id": "013e1cd7-ca06-4dd8-85be-8475bde12d48", "attempt": 1}
649983cc-2e38-4487-b74c-4ed977c19b3f	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	94137786-91d3-4086-8634-5da9968bd6c7	local	\N	\N	\N	0	0	0	reported	finalized	settle:94137786-91d3-4086-8634-5da9968bd6c7:1	94137786-91d3-4086-8634-5da9968bd6c7	production	2026-09-25 13:42:57.261186+00	{"ok": true, "kind": "job_settlement", "job_id": "cfaf79d9-8e96-4764-a652-19f2f2179004", "run_id": "94137786-91d3-4086-8634-5da9968bd6c7", "attempt": 1}
dee33240-98ee-48b6-9e5a-61905ff4ac97	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	7a353e29-dc66-4086-9aa8-64174efe554d	local	\N	\N	\N	0	0	0	reported	finalized	settle:7a353e29-dc66-4086-9aa8-64174efe554d:2	7a353e29-dc66-4086-9aa8-64174efe554d	production	2026-09-25 13:42:57.404935+00	{"ok": true, "kind": "job_settlement", "job_id": "81780c14-5eee-4ff2-ae7f-1ac52fe951f8", "run_id": "7a353e29-dc66-4086-9aa8-64174efe554d", "attempt": 2}
3dea082b-dfd2-4db0-82d7-617ac2fb4ef4	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	891c1282-c650-4b2f-9b9c-4e4bec3eb150	local	\N	\N	\N	0	0	0	reported	finalized	settle:891c1282-c650-4b2f-9b9c-4e4bec3eb150:1	891c1282-c650-4b2f-9b9c-4e4bec3eb150	production	2026-09-25 13:42:57.601676+00	{"ok": true, "kind": "job_settlement", "job_id": "74e79cff-759d-4806-b22c-c13f230ff015", "run_id": "891c1282-c650-4b2f-9b9c-4e4bec3eb150", "attempt": 1}
4f932297-13dd-44ce-bb77-17f94c6299a5	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	189021bf-e92f-456e-933d-577fb90e6ae2	local	\N	\N	\N	0	0	0	reported	finalized	settle:189021bf-e92f-456e-933d-577fb90e6ae2:1	189021bf-e92f-456e-933d-577fb90e6ae2	production	2026-09-25 13:42:57.651862+00	{"ok": true, "kind": "job_settlement", "job_id": "ece8ac3a-1061-486c-a849-7574c872926d", "run_id": "189021bf-e92f-456e-933d-577fb90e6ae2", "attempt": 1}
be0e77f2-92c7-491a-b7bb-082be6d37ef8	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	2ed07a3f-a742-484d-9f51-295bf3c16c52	local	\N	\N	\N	0	0	0	reported	finalized	settle:2ed07a3f-a742-484d-9f51-295bf3c16c52:1	2ed07a3f-a742-484d-9f51-295bf3c16c52	production	2026-09-25 13:43:27.980441+00	{"ok": true, "kind": "job_settlement", "job_id": "6ce89210-9d7b-4ef2-a460-7936e37861e9", "run_id": "2ed07a3f-a742-484d-9f51-295bf3c16c52", "attempt": 1}
c5330c9e-40f5-42c8-9527-ca5ac23a2b67	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	6f656618-35bd-4f97-952b-1a5c832d1f8b	local	\N	\N	\N	0	0	0	reported	finalized	settle:6f656618-35bd-4f97-952b-1a5c832d1f8b:2	6f656618-35bd-4f97-952b-1a5c832d1f8b	production	2026-09-25 13:43:28.174947+00	{"ok": true, "kind": "job_settlement", "job_id": "dde1681c-6f4e-4219-97c2-06d1154c7067", "run_id": "6f656618-35bd-4f97-952b-1a5c832d1f8b", "attempt": 2}
eabb1192-b790-44e7-bb19-1735ef26c474	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	c235be5f-e80d-4af6-983a-76c3d2a8df68	local	\N	\N	\N	0	0	0	reported	finalized	settle:c235be5f-e80d-4af6-983a-76c3d2a8df68:1	c235be5f-e80d-4af6-983a-76c3d2a8df68	production	2026-09-25 13:43:28.356725+00	{"ok": true, "kind": "job_settlement", "job_id": "947d35bd-7f5e-4967-800c-e78b630cd423", "run_id": "c235be5f-e80d-4af6-983a-76c3d2a8df68", "attempt": 1}
15b189ab-4637-4ba1-978d-51740ad3c8cc	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	8060967c-9d03-475f-a8ba-ecd05f59fa15	local	\N	\N	\N	0	0	0	reported	finalized	settle:8060967c-9d03-475f-a8ba-ecd05f59fa15:1	8060967c-9d03-475f-a8ba-ecd05f59fa15	production	2026-09-25 13:43:44.09764+00	{"ok": true, "kind": "job_settlement", "job_id": "40a0cbf9-f619-4bb5-a7eb-5cd23cf9dee1", "run_id": "8060967c-9d03-475f-a8ba-ecd05f59fa15", "attempt": 1}
b63c1092-fc31-454f-ac36-adf63d75e735	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	local	\N	\N	\N	0	0	0	reported	finalized	settle:ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32:2	ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32	production	2026-09-25 13:43:44.25005+00	{"ok": true, "kind": "job_settlement", "job_id": "ecf21bd2-46ad-402b-9329-8c5cae2291e9", "run_id": "ff3c8078-7f80-4dfa-a4ce-0e7615b0ec32", "attempt": 2}
abbe8bb6-cd7b-4b18-b7f5-777a19f38440	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	980f46bb-1cda-4078-bb7f-a3d73c7b40d8	local	\N	\N	\N	0	0	0	reported	finalized	settle:980f46bb-1cda-4078-bb7f-a3d73c7b40d8:1	980f46bb-1cda-4078-bb7f-a3d73c7b40d8	production	2026-09-25 13:43:44.423115+00	{"ok": true, "kind": "job_settlement", "job_id": "c9ed2300-a06c-420f-b8fa-b45f0bd28d6b", "run_id": "980f46bb-1cda-4078-bb7f-a3d73c7b40d8", "attempt": 1}
caee6511-f17b-442a-871f-98e3d7f14da5	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	73e7f174-54ac-4d37-9f65-33c1608a6c2b	local	\N	\N	\N	0	0	0	reported	finalized	settle:73e7f174-54ac-4d37-9f65-33c1608a6c2b:1	73e7f174-54ac-4d37-9f65-33c1608a6c2b	production	2026-09-25 14:11:43.818008+00	{"ok": true, "kind": "job_settlement", "job_id": "de0a429b-9bcf-4d1d-9198-e1727b230d19", "run_id": "73e7f174-54ac-4d37-9f65-33c1608a6c2b", "attempt": 1}
75c7c063-2467-4b3c-98d0-e17cd860f04c	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	888e1f7b-6639-4463-b86f-c32ff1af4cc3	local	\N	\N	\N	0	0	0	reported	finalized	settle:888e1f7b-6639-4463-b86f-c32ff1af4cc3:2	888e1f7b-6639-4463-b86f-c32ff1af4cc3	production	2026-09-25 14:11:43.960768+00	{"ok": true, "kind": "job_settlement", "job_id": "d942173e-b6cf-4f51-a3d3-996f6f083813", "run_id": "888e1f7b-6639-4463-b86f-c32ff1af4cc3", "attempt": 2}
7deb13b5-8548-472b-bcc3-9ad9e19d49de	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	b7142c7b-501f-4b67-a1af-6bd40e5de64c	local	\N	\N	\N	0	0	0	reported	finalized	settle:b7142c7b-501f-4b67-a1af-6bd40e5de64c:1	b7142c7b-501f-4b67-a1af-6bd40e5de64c	production	2026-09-25 14:11:44.15361+00	{"ok": true, "kind": "job_settlement", "job_id": "a9c8bbb2-aded-4aaa-abaa-3ff70acbee4f", "run_id": "b7142c7b-501f-4b67-a1af-6bd40e5de64c", "attempt": 1}
70de9086-182a-43bc-ab57-ce060432af6e	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	18511b1c-101e-43aa-9811-2a3f0cac75e9	local	\N	\N	\N	0	0	0	reported	finalized	settle:18511b1c-101e-43aa-9811-2a3f0cac75e9:1	18511b1c-101e-43aa-9811-2a3f0cac75e9	production	2026-09-25 14:51:11.780405+00	{"ok": true, "kind": "job_settlement", "job_id": "2de868d1-6a42-4874-b6c4-08a6f521ee4e", "run_id": "18511b1c-101e-43aa-9811-2a3f0cac75e9", "attempt": 1}
1cb2c84f-c808-4ebb-bd06-7e13c6aa5a94	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	c6c4e85b-c433-4539-8baf-0b39ca813496	local	\N	\N	\N	0	0	0	reported	finalized	settle:c6c4e85b-c433-4539-8baf-0b39ca813496:1	c6c4e85b-c433-4539-8baf-0b39ca813496	production	2026-09-25 14:51:11.837227+00	{"ok": true, "kind": "job_settlement", "job_id": "a83672ad-6e70-4814-bd20-a28b34c34421", "run_id": "c6c4e85b-c433-4539-8baf-0b39ca813496", "attempt": 1}
f8eae2ce-6bf9-4ca9-81b9-40941582ffbb	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	local	\N	\N	\N	0	0	0	reported	finalized	settle:ce8a1b10-38d0-4ef6-b780-6d9788a4cbed:2	ce8a1b10-38d0-4ef6-b780-6d9788a4cbed	production	2026-09-25 14:51:11.983738+00	{"ok": true, "kind": "job_settlement", "job_id": "33a7e677-b29a-4895-87f4-1a8b43a1e374", "run_id": "ce8a1b10-38d0-4ef6-b780-6d9788a4cbed", "attempt": 2}
10597333-33cc-4b4a-8218-ed79327e6427	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	ed8d2c75-d737-438a-bb53-4e457d4b096b	local	\N	\N	\N	0	0	0	reported	finalized	settle:ed8d2c75-d737-438a-bb53-4e457d4b096b:1	ed8d2c75-d737-438a-bb53-4e457d4b096b	production	2026-09-25 14:51:12.362004+00	{"ok": true, "kind": "job_settlement", "job_id": "df75213d-9b26-4a9f-bd32-4cf32de0e372", "run_id": "ed8d2c75-d737-438a-bb53-4e457d4b096b", "attempt": 1}
bcb9ef16-04dc-4a14-a91c-807eb4ed845d	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	3a5821b2-e29b-4355-b128-a97ddd6c4b8d	local	\N	\N	\N	0	0	0	reported	finalized	settle:3a5821b2-e29b-4355-b128-a97ddd6c4b8d:1	3a5821b2-e29b-4355-b128-a97ddd6c4b8d	production	2026-09-25 14:51:12.419583+00	{"ok": true, "kind": "job_settlement", "job_id": "41f26384-a34f-4fc6-987c-087a046cf42c", "run_id": "3a5821b2-e29b-4355-b128-a97ddd6c4b8d", "attempt": 1}
d4d4d1bc-12da-41ee-9012-51a5797393ed	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	60873eaa-b945-465d-ac58-8761ed134713	local	\N	\N	\N	0	0	0	reported	finalized	settle:60873eaa-b945-465d-ac58-8761ed134713:1	60873eaa-b945-465d-ac58-8761ed134713	production	2026-09-25 14:51:12.481352+00	{"ok": true, "kind": "job_settlement", "job_id": "8368c245-aeb2-4758-b4c8-ba91d8aec34e", "run_id": "60873eaa-b945-465d-ac58-8761ed134713", "attempt": 1}
7c1fdf0f-45db-42cf-8a83-d08fa70f56ea	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	7d07bd89-d711-4209-a0de-7eade8fb8d17	local	\N	\N	\N	0	0	0	reported	finalized	settle:7d07bd89-d711-4209-a0de-7eade8fb8d17:1	7d07bd89-d711-4209-a0de-7eade8fb8d17	production	2026-09-25 14:51:12.53038+00	{"ok": true, "kind": "job_settlement", "job_id": "3013ce28-c3cc-4798-be62-1f1df2b99f45", "run_id": "7d07bd89-d711-4209-a0de-7eade8fb8d17", "attempt": 1}
265df468-a875-4e10-b6d8-e5aa78664c8d	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	8fd371e8-fff7-4585-a4ec-440107ec8af6	local	\N	\N	\N	0	0	0	reported	finalized	settle:8fd371e8-fff7-4585-a4ec-440107ec8af6:1	8fd371e8-fff7-4585-a4ec-440107ec8af6	production	2026-09-25 14:51:12.575154+00	{"ok": true, "kind": "job_settlement", "job_id": "d1b04528-b5f3-4cd7-a5d8-6534f355e04b", "run_id": "8fd371e8-fff7-4585-a4ec-440107ec8af6", "attempt": 1}
920c6cb3-106f-4281-a301-5d463f4dc62f	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	4e84497f-7ed5-4d89-9335-8c4138ab1de8	local	\N	\N	\N	0	0	0	reported	finalized	settle:4e84497f-7ed5-4d89-9335-8c4138ab1de8:1	4e84497f-7ed5-4d89-9335-8c4138ab1de8	production	2026-09-25 14:51:12.61967+00	{"ok": true, "kind": "job_settlement", "job_id": "55e5d9d2-4d45-4d32-a5cb-6566ea148cd6", "run_id": "4e84497f-7ed5-4d89-9335-8c4138ab1de8", "attempt": 1}
c55fd7e3-bfe5-4b58-8af9-39d66976945a	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	862b2b82-ae8f-4668-b58a-596f73e32533	local	\N	\N	\N	0	0	0	reported	finalized	settle:862b2b82-ae8f-4668-b58a-596f73e32533:1	862b2b82-ae8f-4668-b58a-596f73e32533	production	2026-09-25 14:51:12.668746+00	{"ok": true, "kind": "job_settlement", "job_id": "f0a2b5a5-b0d5-4316-8cd4-1e095e241060", "run_id": "862b2b82-ae8f-4668-b58a-596f73e32533", "attempt": 1}
dcd3add1-ca96-410e-8d64-05048c589b83	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	52a538e7-14cd-411f-b68a-a012031f7fc0	local	\N	\N	\N	0	0	0	reported	finalized	settle:52a538e7-14cd-411f-b68a-a012031f7fc0:1	52a538e7-14cd-411f-b68a-a012031f7fc0	production	2026-09-25 14:53:52.836508+00	{"ok": true, "kind": "job_settlement", "job_id": "32baf8fb-af8f-4f7a-a8d1-cd7a30f2c7fe", "run_id": "52a538e7-14cd-411f-b68a-a012031f7fc0", "attempt": 1}
a11a35eb-a6dc-4e1e-8562-abfe803f7b91	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	066a69b5-3244-4e91-8da5-01f414b9052a	local	\N	\N	\N	0	0	0	reported	finalized	settle:066a69b5-3244-4e91-8da5-01f414b9052a:2	066a69b5-3244-4e91-8da5-01f414b9052a	production	2026-09-25 14:53:52.985716+00	{"ok": true, "kind": "job_settlement", "job_id": "8d35c923-2d19-4d1b-b28c-ed0d3a6433eb", "run_id": "066a69b5-3244-4e91-8da5-01f414b9052a", "attempt": 2}
ebac1fad-a036-46a7-a43b-c45f69e63ca7	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	46a6356b-3b04-4540-bef9-d1ba99fcf6ec	local	\N	\N	\N	0	0	0	reported	finalized	settle:46a6356b-3b04-4540-bef9-d1ba99fcf6ec:1	46a6356b-3b04-4540-bef9-d1ba99fcf6ec	production	2026-09-25 14:53:53.168485+00	{"ok": true, "kind": "job_settlement", "job_id": "d9001c70-db76-4ee9-a52f-d102a0284ae1", "run_id": "46a6356b-3b04-4540-bef9-d1ba99fcf6ec", "attempt": 1}
40e95d0e-1b4c-4f4d-bb24-254592be8f5c	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	d384a816-2afc-4823-9510-a9e46d265c43	local	\N	\N	\N	0	0	0	reported	finalized	settle:d384a816-2afc-4823-9510-a9e46d265c43:1	d384a816-2afc-4823-9510-a9e46d265c43	production	2026-09-25 15:37:31.748156+00	{"ok": true, "kind": "job_settlement", "job_id": "45d210df-829b-4915-8e37-cca1449cb6d9", "run_id": "d384a816-2afc-4823-9510-a9e46d265c43", "attempt": 1}
21e064c8-b2f5-492d-82da-590dd058022c	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	b8208594-7396-49a5-a29e-4518c24a4b93	local	\N	\N	\N	0	0	0	reported	finalized	settle:b8208594-7396-49a5-a29e-4518c24a4b93:2	b8208594-7396-49a5-a29e-4518c24a4b93	production	2026-09-25 15:37:31.901511+00	{"ok": true, "kind": "job_settlement", "job_id": "7ee3b24c-6b2f-4b10-ad6d-2cad798d2fbe", "run_id": "b8208594-7396-49a5-a29e-4518c24a4b93", "attempt": 2}
9c267b3b-2f58-4466-ade2-244273b3949a	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	c06674c2-6599-436e-99d5-642fcc32e7b8	local	\N	\N	\N	0	0	0	reported	finalized	settle:c06674c2-6599-436e-99d5-642fcc32e7b8:1	c06674c2-6599-436e-99d5-642fcc32e7b8	production	2026-09-25 15:37:32.09861+00	{"ok": true, "kind": "job_settlement", "job_id": "3c51e672-9ffc-4708-a633-d6b0080b97db", "run_id": "c06674c2-6599-436e-99d5-642fcc32e7b8", "attempt": 1}
41956b47-9b0b-44fa-83f1-d207bb72b70e	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	447d268e-6349-43bd-b790-d224b352371d	local	\N	\N	\N	0	0	0	reported	finalized	settle:447d268e-6349-43bd-b790-d224b352371d:1	447d268e-6349-43bd-b790-d224b352371d	production	2026-09-25 15:38:04.180483+00	{"ok": true, "kind": "job_settlement", "job_id": "87fd1bcb-34c1-4dc6-b7a0-b8c8d4255e2a", "run_id": "447d268e-6349-43bd-b790-d224b352371d", "attempt": 1}
2f88ea73-3bec-4eaf-9787-36e1ac0a27a9	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	e870faf1-14e6-40f8-a346-6d60573785af	local	\N	\N	\N	0	0	0	reported	finalized	settle:e870faf1-14e6-40f8-a346-6d60573785af:2	e870faf1-14e6-40f8-a346-6d60573785af	production	2026-09-25 15:38:04.347234+00	{"ok": true, "kind": "job_settlement", "job_id": "f88b1602-18de-45f7-a836-753ac6dbb73d", "run_id": "e870faf1-14e6-40f8-a346-6d60573785af", "attempt": 2}
8ab92ab1-3e9f-49fa-85fe-7fc44b6531d9	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	13cb4d13-6660-4f9f-9730-4a8805603a19	local	\N	\N	\N	0	0	0	reported	finalized	settle:13cb4d13-6660-4f9f-9730-4a8805603a19:1	13cb4d13-6660-4f9f-9730-4a8805603a19	production	2026-09-25 15:38:04.530107+00	{"ok": true, "kind": "job_settlement", "job_id": "bb9de075-0d97-4a93-8b3e-72c2bbf0b801", "run_id": "13cb4d13-6660-4f9f-9730-4a8805603a19", "attempt": 1}
0debe028-b717-4a86-850c-188ef4bdef79	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	billing:subscription	\N	test	\N	\N	\N	0	\N	0	reported	finalized	billing:evt_staging_1790350684831	evt_staging_1790350684831	production	2026-09-25 15:38:04.846184+00	{"kind": "billing_settlement", "tier": "trial", "event_id": "evt_staging_1790350684831", "test_mode": true}
8032c7cb-e00c-42b9-b37b-4c60a4588c45	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	2acbf0ce-aac1-4429-9f62-96a58336f831	local	\N	\N	\N	0	0	0	reported	finalized	settle:2acbf0ce-aac1-4429-9f62-96a58336f831:1	2acbf0ce-aac1-4429-9f62-96a58336f831	production	2026-09-25 15:39:15.347976+00	{"ok": true, "kind": "job_settlement", "job_id": "ea1b3ec9-5441-4dd9-a4b6-428886125db7", "run_id": "2acbf0ce-aac1-4429-9f62-96a58336f831", "attempt": 1}
ec1d06c2-d113-459a-a0e9-db1ecfcca243	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	c3299161-4bdf-49ec-b711-898ae6287e0b	local	\N	\N	\N	0	0	0	reported	finalized	settle:c3299161-4bdf-49ec-b711-898ae6287e0b:2	c3299161-4bdf-49ec-b711-898ae6287e0b	production	2026-09-25 15:39:15.516723+00	{"ok": true, "kind": "job_settlement", "job_id": "1e82450b-72a9-436b-b3b2-46a915738f5b", "run_id": "c3299161-4bdf-49ec-b711-898ae6287e0b", "attempt": 2}
9c8c568b-2df5-459d-aa55-18e3998ad8d2	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	0e2e02e8-fde2-4386-b45f-94c21fd920c5	local	\N	\N	\N	0	0	0	reported	finalized	settle:0e2e02e8-fde2-4386-b45f-94c21fd920c5:1	0e2e02e8-fde2-4386-b45f-94c21fd920c5	production	2026-09-25 15:39:15.716488+00	{"ok": true, "kind": "job_settlement", "job_id": "72709084-6173-43bf-ac05-71607e3bb043", "run_id": "0e2e02e8-fde2-4386-b45f-94c21fd920c5", "attempt": 1}
b18138c4-4cdf-4b3d-aef4-8bb927de21cd	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	0d700548-3a64-41b3-9b53-1c19625e9229	local	\N	\N	\N	0	0	0	reported	finalized	settle:0d700548-3a64-41b3-9b53-1c19625e9229:1	0d700548-3a64-41b3-9b53-1c19625e9229	production	2026-09-25 15:39:50.284186+00	{"ok": true, "kind": "job_settlement", "job_id": "00fb6a50-57ec-4e8d-9a22-94b43b6669cb", "run_id": "0d700548-3a64-41b3-9b53-1c19625e9229", "attempt": 1}
afff6378-5d7b-4476-b72e-052411ed2542	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	c604cf51-ac89-4bdc-9ea2-746cc1adb608	local	\N	\N	\N	0	0	0	reported	finalized	settle:c604cf51-ac89-4bdc-9ea2-746cc1adb608:2	c604cf51-ac89-4bdc-9ea2-746cc1adb608	production	2026-09-25 15:39:50.46512+00	{"ok": true, "kind": "job_settlement", "job_id": "c3eb9278-49f7-4c93-8f8e-a94559908fad", "run_id": "c604cf51-ac89-4bdc-9ea2-746cc1adb608", "attempt": 2}
c640f256-468a-4aa3-940d-23910b1de920	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	9077902e-98c6-4ac9-b0be-ca7a1a32e924	local	\N	\N	\N	0	0	0	reported	finalized	settle:9077902e-98c6-4ac9-b0be-ca7a1a32e924:1	9077902e-98c6-4ac9-b0be-ca7a1a32e924	production	2026-09-25 15:39:50.649712+00	{"ok": true, "kind": "job_settlement", "job_id": "4bcb49ea-f1e8-4f40-92ae-74d72dd2a783", "run_id": "9077902e-98c6-4ac9-b0be-ca7a1a32e924", "attempt": 1}
31d5455d-ed50-439c-907e-c5ec941b9971	05f4a6f3-9d7d-4ed0-91a8-8a55a1fbb3f4	\N	billing:subscription	\N	test	\N	\N	\N	0	\N	0	reported	finalized	billing:evt_staging_1790350790868	evt_staging_1790350790868	production	2026-09-25 15:39:50.984478+00	{"kind": "billing_settlement", "tier": "trial", "event_id": "evt_staging_1790350790868", "test_mode": true}
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.users (id, email, display_name, active, created_at) FROM stdin;
818d3840-1a16-40b6-9757-9e5a67af68f8	tyrone@staging.local	tyrone@staging.local	t	2026-09-25 12:46:53.518432+00
7013f362-8338-48a2-a3f0-0b65d6216a2c	viewer@staging.local		t	2026-09-25 14:11:44.192678+00
69ff71b2-7a3b-4f5f-9056-2b666d3b0026	viewer@staging.local		t	2026-09-25 14:51:12.714376+00
8809ba90-55dd-48d0-a895-665fc5872741	beta@staging.local		t	2026-09-25 14:51:12.79896+00
2bc09d54-2de2-4d09-bd0c-db716530fe25	viewer@staging.local		t	2026-09-25 14:53:53.212614+00
4aaa159d-cfe8-41f6-8c52-d2f2d9c214c4	beta@staging.local		t	2026-09-25 14:53:53.297596+00
8d23329e-c826-4cf3-9351-e8675d2c55c5	viewer@staging.local		t	2026-09-25 15:37:32.143396+00
f8970e4e-f2bc-46e5-b1e2-6de99e823130	beta@staging.local		t	2026-09-25 15:37:32.255322+00
7ed20cf3-772b-41f7-8aab-1eacfdcbcd09	e2e-1790350652335@staging.local	e2e-1790350652335	t	2026-09-25 15:37:32.351358+00
2e02cc0b-0696-4647-b1b9-a8187761767e	viewer@staging.local		t	2026-09-25 15:38:04.578669+00
189e1da9-2344-4468-aa4c-41235f9bd9c0	beta@staging.local		t	2026-09-25 15:38:04.676814+00
d16118e8-09c3-45f9-becf-772303be6bda	e2e-1790350684754@staging.local	e2e-1790350684754	t	2026-09-25 15:38:04.770601+00
a647b2b4-57a1-4ac0-9ae1-de5e30a866e5	viewer@staging.local		t	2026-09-25 15:39:15.766479+00
4862db1a-85f3-49c1-bed2-1def9d383dbe	beta@staging.local		t	2026-09-25 15:39:15.861269+00
c46f4c20-58bb-4669-8d5f-1cb18ff0b94a	admin-1790350755943@staging.local		t	2026-09-25 15:39:15.943363+00
b0e01231-2313-441a-9bc8-f12449d3d249	cust-1790350755976@staging.local	cust-1790350755976	t	2026-09-25 15:39:15.996123+00
ab799989-4af7-44f5-8fe8-c85147cc9d5d	viewer@staging.local		t	2026-09-25 15:39:50.698768+00
99d0d2b9-2ad9-4e96-bf2f-d0e2d89a7ff5	beta@staging.local		t	2026-09-25 15:39:50.791093+00
16d2ec3e-5c6c-4f5e-ae69-a9a3c058b69e	admin-1790350790868@staging.local		t	2026-09-25 15:39:50.870579+00
5bd4e3f5-c14c-4d99-8d5a-3b872bd58f67	cust-1790350790868@staging.local	cust-1790350790868	t	2026-09-25 15:39:50.917682+00
\.


--
-- Data for Name: variation_relationships; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.variation_relationships (id, family_id, child_product_id, axis, created_at) FROM stdin;
\.


--
-- Name: acceptance_events acceptance_events_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.acceptance_events
    ADD CONSTRAINT acceptance_events_pkey PRIMARY KEY (id);


--
-- Name: account_acceptance account_acceptance_organization_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.account_acceptance
    ADD CONSTRAINT account_acceptance_organization_id_user_id_key UNIQUE (organization_id, user_id);


--
-- Name: account_acceptance account_acceptance_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.account_acceptance
    ADD CONSTRAINT account_acceptance_pkey PRIMARY KEY (id);


--
-- Name: ad_performance_observations ad_performance_observations_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.ad_performance_observations
    ADD CONSTRAINT ad_performance_observations_pkey PRIMARY KEY (id);


--
-- Name: approval_decisions approval_decisions_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.approval_decisions
    ADD CONSTRAINT approval_decisions_pkey PRIMARY KEY (id);


--
-- Name: approval_requests approval_requests_idempotency_key_key; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.approval_requests
    ADD CONSTRAINT approval_requests_idempotency_key_key UNIQUE (idempotency_key);


--
-- Name: approval_requests approval_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.approval_requests
    ADD CONSTRAINT approval_requests_pkey PRIMARY KEY (id);


--
-- Name: audit_events audit_events_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.audit_events
    ADD CONSTRAINT audit_events_pkey PRIMARY KEY (id);


--
-- Name: billing_customers billing_customers_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.billing_customers
    ADD CONSTRAINT billing_customers_pkey PRIMARY KEY (id);


--
-- Name: billing_events billing_events_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.billing_events
    ADD CONSTRAINT billing_events_pkey PRIMARY KEY (id);


--
-- Name: billing_events billing_events_processor_event_id_key; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.billing_events
    ADD CONSTRAINT billing_events_processor_event_id_key UNIQUE (processor_event_id);


--
-- Name: catalog_products catalog_products_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.catalog_products
    ADD CONSTRAINT catalog_products_pkey PRIMARY KEY (id);


--
-- Name: checkout_sessions checkout_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.checkout_sessions
    ADD CONSTRAINT checkout_sessions_pkey PRIMARY KEY (id);


--
-- Name: identity_conflicts identity_conflicts_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.identity_conflicts
    ADD CONSTRAINT identity_conflicts_pkey PRIMARY KEY (id);


--
-- Name: import_batches import_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.import_batches
    ADD CONSTRAINT import_batches_pkey PRIMARY KEY (id);


--
-- Name: invites invites_invite_code_key; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.invites
    ADD CONSTRAINT invites_invite_code_key UNIQUE (invite_code);


--
-- Name: invites invites_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.invites
    ADD CONSTRAINT invites_pkey PRIMARY KEY (id);


--
-- Name: job_requests job_requests_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.job_requests
    ADD CONSTRAINT job_requests_pkey PRIMARY KEY (id);


--
-- Name: job_runs job_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.job_runs
    ADD CONSTRAINT job_runs_pkey PRIMARY KEY (id);


--
-- Name: job_schedules job_schedules_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.job_schedules
    ADD CONSTRAINT job_schedules_pkey PRIMARY KEY (id);


--
-- Name: job_state_history job_state_history_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.job_state_history
    ADD CONSTRAINT job_state_history_pkey PRIMARY KEY (id);


--
-- Name: keyword_conflicts keyword_conflicts_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.keyword_conflicts
    ADD CONSTRAINT keyword_conflicts_pkey PRIMARY KEY (id);


--
-- Name: keyword_links keyword_links_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.keyword_links
    ADD CONSTRAINT keyword_links_pkey PRIMARY KEY (id);


--
-- Name: keywords keywords_organization_id_normalized_phrase_match_type_marke_key; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.keywords
    ADD CONSTRAINT keywords_organization_id_normalized_phrase_match_type_marke_key UNIQUE (organization_id, normalized_phrase, match_type, marketplace);


--
-- Name: keywords keywords_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.keywords
    ADD CONSTRAINT keywords_pkey PRIMARY KEY (id);


--
-- Name: legal_documents legal_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.legal_documents
    ADD CONSTRAINT legal_documents_pkey PRIMARY KEY (id);


--
-- Name: marketplaces marketplaces_code_key; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.marketplaces
    ADD CONSTRAINT marketplaces_code_key UNIQUE (code);


--
-- Name: marketplaces marketplaces_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.marketplaces
    ADD CONSTRAINT marketplaces_pkey PRIMARY KEY (id);


--
-- Name: memberships memberships_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.memberships
    ADD CONSTRAINT memberships_pkey PRIMARY KEY (id);


--
-- Name: normalization_decisions normalization_decisions_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.normalization_decisions
    ADD CONSTRAINT normalization_decisions_pkey PRIMARY KEY (id);


--
-- Name: observations observations_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.observations
    ADD CONSTRAINT observations_pkey PRIMARY KEY (id);


--
-- Name: org_balances org_balances_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.org_balances
    ADD CONSTRAINT org_balances_pkey PRIMARY KEY (organization_id);


--
-- Name: org_entitlements org_entitlements_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.org_entitlements
    ADD CONSTRAINT org_entitlements_pkey PRIMARY KEY (organization_id);


--
-- Name: organizations organizations_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.organizations
    ADD CONSTRAINT organizations_pkey PRIMARY KEY (id);


--
-- Name: pack_configs pack_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.pack_configs
    ADD CONSTRAINT pack_configs_pkey PRIMARY KEY (id);


--
-- Name: preview_sessions preview_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.preview_sessions
    ADD CONSTRAINT preview_sessions_pkey PRIMARY KEY (id);


--
-- Name: pricing_policies pricing_policies_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.pricing_policies
    ADD CONSTRAINT pricing_policies_pkey PRIMARY KEY (version);


--
-- Name: product_aliases product_aliases_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.product_aliases
    ADD CONSTRAINT product_aliases_pkey PRIMARY KEY (id);


--
-- Name: product_identifiers product_identifiers_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.product_identifiers
    ADD CONSTRAINT product_identifiers_pkey PRIMARY KEY (id);


--
-- Name: providers providers_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.providers
    ADD CONSTRAINT providers_pkey PRIMARY KEY (id);


--
-- Name: providers providers_provider_key_key; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.providers
    ADD CONSTRAINT providers_provider_key_key UNIQUE (provider_key);


--
-- Name: rank_observations rank_observations_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.rank_observations
    ADD CONSTRAINT rank_observations_pkey PRIMARY KEY (id);


--
-- Name: rejected_rows rejected_rows_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.rejected_rows
    ADD CONSTRAINT rejected_rows_pkey PRIMARY KEY (id);


--
-- Name: schedule_occurrences schedule_occurrences_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.schedule_occurrences
    ADD CONSTRAINT schedule_occurrences_pkey PRIMARY KEY (id);


--
-- Name: schedule_occurrences schedule_occurrences_schedule_id_occurrence_key_key; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.schedule_occurrences
    ADD CONSTRAINT schedule_occurrences_schedule_id_occurrence_key_key UNIQUE (schedule_id, occurrence_key);


--
-- Name: search_terms search_terms_organization_id_normalized_term_marketplace_key; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.search_terms
    ADD CONSTRAINT search_terms_organization_id_normalized_term_marketplace_key UNIQUE (organization_id, normalized_term, marketplace);


--
-- Name: search_terms search_terms_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.search_terms
    ADD CONSTRAINT search_terms_pkey PRIMARY KEY (id);


--
-- Name: sessions sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.sessions
    ADD CONSTRAINT sessions_pkey PRIMARY KEY (jti);


--
-- Name: source_files source_files_organization_id_file_sha256_key; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.source_files
    ADD CONSTRAINT source_files_organization_id_file_sha256_key UNIQUE (organization_id, file_sha256);


--
-- Name: source_files source_files_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.source_files
    ADD CONSTRAINT source_files_pkey PRIMARY KEY (id);


--
-- Name: source_rows source_rows_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.source_rows
    ADD CONSTRAINT source_rows_pkey PRIMARY KEY (id);


--
-- Name: subscriptions subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_pkey PRIMARY KEY (id);


--
-- Name: subscriptions subscriptions_processor_subscription_id_key; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.subscriptions
    ADD CONSTRAINT subscriptions_processor_subscription_id_key UNIQUE (processor_subscription_id);


--
-- Name: supplier_documentation supplier_documentation_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.supplier_documentation
    ADD CONSTRAINT supplier_documentation_pkey PRIMARY KEY (id);


--
-- Name: suppliers suppliers_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.suppliers
    ADD CONSTRAINT suppliers_pkey PRIMARY KEY (id);


--
-- Name: targets targets_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.targets
    ADD CONSTRAINT targets_pkey PRIMARY KEY (id);


--
-- Name: ui_preferences ui_preferences_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.ui_preferences
    ADD CONSTRAINT ui_preferences_pkey PRIMARY KEY (user_id, organization_id, key);


--
-- Name: unresolved_candidates unresolved_candidates_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.unresolved_candidates
    ADD CONSTRAINT unresolved_candidates_pkey PRIMARY KEY (id);


--
-- Name: usage_events usage_events_idempotency_key_key; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.usage_events
    ADD CONSTRAINT usage_events_idempotency_key_key UNIQUE (idempotency_key);


--
-- Name: usage_events usage_events_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.usage_events
    ADD CONSTRAINT usage_events_pkey PRIMARY KEY (id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: variation_relationships variation_relationships_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.variation_relationships
    ADD CONSTRAINT variation_relationships_pkey PRIMARY KEY (id);


--
-- Name: idx_acceptance_events__organization_id__user_id__accepted_at; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE INDEX idx_acceptance_events__organization_id__user_id__accepted_at ON public.acceptance_events USING btree (organization_id, user_id, accepted_at);


--
-- Name: idx_audit_events__organization_id__occurred_at; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE INDEX idx_audit_events__organization_id__occurred_at ON public.audit_events USING btree (organization_id, occurred_at);


--
-- Name: idx_invites__organization_id__email; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE INDEX idx_invites__organization_id__email ON public.invites USING btree (organization_id, email);


--
-- Name: idx_job_requests__organization_id__created_at; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE INDEX idx_job_requests__organization_id__created_at ON public.job_requests USING btree (organization_id, created_at);


--
-- Name: idx_job_runs__job_request_id__created_at; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE INDEX idx_job_runs__job_request_id__created_at ON public.job_runs USING btree (job_request_id, created_at);


--
-- Name: idx_job_runs__lease_expiration; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE INDEX idx_job_runs__lease_expiration ON public.job_runs USING btree (lease_expiration);


--
-- Name: idx_job_runs__state__priority__created_at; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE INDEX idx_job_runs__state__priority__created_at ON public.job_runs USING btree (state, priority, created_at);


--
-- Name: idx_job_schedules__next_run_at; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE INDEX idx_job_schedules__next_run_at ON public.job_schedules USING btree (next_run_at);


--
-- Name: idx_job_schedules__organization_id__enabled; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE INDEX idx_job_schedules__organization_id__enabled ON public.job_schedules USING btree (organization_id, enabled);


--
-- Name: idx_job_state_history__job_id__run_id; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE INDEX idx_job_state_history__job_id__run_id ON public.job_state_history USING btree (job_id, run_id);


--
-- Name: idx_job_state_history__occurred_at; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE INDEX idx_job_state_history__occurred_at ON public.job_state_history USING btree (occurred_at);


--
-- Name: idx_legal_documents__doc_type__version; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE INDEX idx_legal_documents__doc_type__version ON public.legal_documents USING btree (doc_type, version);


--
-- Name: idx_schedule_occurrences__schedule_id__scheduled_for; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE INDEX idx_schedule_occurrences__schedule_id__scheduled_for ON public.schedule_occurrences USING btree (schedule_id, scheduled_for);


--
-- Name: idx_subscriptions__organization_id__status; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE INDEX idx_subscriptions__organization_id__status ON public.subscriptions USING btree (organization_id, status);


--
-- Name: uq_account_acceptance_org_user; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE UNIQUE INDEX uq_account_acceptance_org_user ON public.account_acceptance USING btree (organization_id, user_id);


--
-- Name: uq_billing_events_processor_event_id; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE UNIQUE INDEX uq_billing_events_processor_event_id ON public.billing_events USING btree (processor_event_id);


--
-- Name: uq_invites_invite_code; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE UNIQUE INDEX uq_invites_invite_code ON public.invites USING btree (invite_code);


--
-- Name: uq_job_requests_org_type_idem; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE UNIQUE INDEX uq_job_requests_org_type_idem ON public.job_requests USING btree (organization_id, job_type, idempotency_key);


--
-- Name: uq_keywords_org_phrase_match_mp; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE UNIQUE INDEX uq_keywords_org_phrase_match_mp ON public.keywords USING btree (organization_id, normalized_phrase, match_type, marketplace);


--
-- Name: uq_schedule_occurrences_schedule_key; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE UNIQUE INDEX uq_schedule_occurrences_schedule_key ON public.schedule_occurrences USING btree (schedule_id, occurrence_key);


--
-- Name: uq_search_terms_org_term_mp; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE UNIQUE INDEX uq_search_terms_org_term_mp ON public.search_terms USING btree (organization_id, normalized_term, marketplace);


--
-- Name: uq_source_files_org_sha; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE UNIQUE INDEX uq_source_files_org_sha ON public.source_files USING btree (organization_id, file_sha256);


--
-- Name: uq_subscriptions_processor_subscription_id; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE UNIQUE INDEX uq_subscriptions_processor_subscription_id ON public.subscriptions USING btree (processor_subscription_id);


--
-- Name: ad_performance_observations fk_ad_performance_observations_search_term_id; Type: FK CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.ad_performance_observations
    ADD CONSTRAINT fk_ad_performance_observations_search_term_id FOREIGN KEY (search_term_id) REFERENCES public.search_terms(id);


--
-- Name: import_batches fk_import_batches_organization_id; Type: FK CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.import_batches
    ADD CONSTRAINT fk_import_batches_organization_id FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: import_batches fk_import_batches_source_file_id; Type: FK CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.import_batches
    ADD CONSTRAINT fk_import_batches_source_file_id FOREIGN KEY (source_file_id) REFERENCES public.source_files(id);


--
-- Name: job_requests fk_job_requests_organization_id; Type: FK CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.job_requests
    ADD CONSTRAINT fk_job_requests_organization_id FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: job_runs fk_job_runs_job_request_id; Type: FK CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.job_runs
    ADD CONSTRAINT fk_job_runs_job_request_id FOREIGN KEY (job_request_id) REFERENCES public.job_requests(id);


--
-- Name: job_schedules fk_job_schedules_organization_id; Type: FK CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.job_schedules
    ADD CONSTRAINT fk_job_schedules_organization_id FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: keyword_links fk_keyword_links_keyword_id; Type: FK CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.keyword_links
    ADD CONSTRAINT fk_keyword_links_keyword_id FOREIGN KEY (keyword_id) REFERENCES public.keywords(id);


--
-- Name: keywords fk_keywords_organization_id; Type: FK CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.keywords
    ADD CONSTRAINT fk_keywords_organization_id FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: rank_observations fk_rank_observations_keyword_id; Type: FK CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.rank_observations
    ADD CONSTRAINT fk_rank_observations_keyword_id FOREIGN KEY (keyword_id) REFERENCES public.keywords(id);


--
-- Name: rejected_rows fk_rejected_rows_import_batch_id; Type: FK CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.rejected_rows
    ADD CONSTRAINT fk_rejected_rows_import_batch_id FOREIGN KEY (import_batch_id) REFERENCES public.import_batches(id);


--
-- Name: schedule_occurrences fk_schedule_occurrences_schedule_id; Type: FK CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.schedule_occurrences
    ADD CONSTRAINT fk_schedule_occurrences_schedule_id FOREIGN KEY (schedule_id) REFERENCES public.job_schedules(id);


--
-- Name: search_terms fk_search_terms_organization_id; Type: FK CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.search_terms
    ADD CONSTRAINT fk_search_terms_organization_id FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: source_files fk_source_files_organization_id; Type: FK CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.source_files
    ADD CONSTRAINT fk_source_files_organization_id FOREIGN KEY (organization_id) REFERENCES public.organizations(id);


--
-- Name: targets fk_targets_keyword_id; Type: FK CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.targets
    ADD CONSTRAINT fk_targets_keyword_id FOREIGN KEY (keyword_id) REFERENCES public.keywords(id);


--
-- PostgreSQL database dump complete
--

\unrestrict XdDe0Q4tCf10NpGx7kW1SdaKiImBshyZndqw5fL5acrUSUVgdVfRwSQnuBqRKBN

