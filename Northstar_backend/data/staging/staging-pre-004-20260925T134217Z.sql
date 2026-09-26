--
-- PostgreSQL database dump
--

\restrict AQCCW19bcv9KFqLgvtEMmaVbiWQYNImLGWeiVJDyFqmQuu6OkrgkhE20rjF8SeS

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
    occurred_at timestamp with time zone
);


ALTER TABLE public.audit_events OWNER TO northstar_staging_owner;

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

COPY public.audit_events (id, actor_user_id, actor_role, organization_id, target_organization_id, target_user_id, action, resource_type, resource_id, before_meta, after_meta, environment, view_context, approval_ref, job_run_ref, result, failure_class, occurred_at) FROM stdin;
509e61d7-d0ee-4dfe-8271-75e3b4a85886	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": true, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 12:46:53.524849+00
1741b8b4-59b2-4383-abb1-e01c95b3d30f	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	session.revoke	session	staging-revoke-1	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 12:46:53.678852+00
b07d23ee-ef69-4e49-9f8c-8c448d4068a2	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	preview.start	preview_session	73ffa11e-e1b4-49f4-9286-678ff87055cf	\N	{"reason": "staging smoke", "target_role": null}	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 12:46:53.69063+00
02a0232b-dc62-4877-a4cd-3b87efe35074	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": false, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 12:47:40.908612+00
18f390ba-5ab6-4ef3-a796-c52603a9bebb	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	preview.start	preview_session	c4335540-0bea-41c4-a3b1-29c3ae2c8d2d	\N	{"reason": "staging smoke", "target_role": null}	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 12:47:41.06491+00
7bbcb6a8-9544-4247-a4e1-6a0a14cc4886	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	preview.end	preview_session	c4335540-0bea-41c4-a3b1-29c3ae2c8d2d	\N	\N	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 12:47:41.084263+00
4247fdef-7845-4b3a-8de8-bfd8a8414ea8	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	2d56906f-32ab-438b-a817-f8baef2559f0	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	221d84bc-4761-4991-a5aa-acbe38c1e303	success	\N	2026-09-25 12:47:41.13251+00
43ca1a06-7433-47f5-b0c0-95546a93416a	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	2d56906f-32ab-438b-a817-f8baef2559f0	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 12:47:41.137442+00
18aa9de4-ee85-40a4-be24-6b4ffcb10ae4	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	2d56906f-32ab-438b-a817-f8baef2559f0	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	221d84bc-4761-4991-a5aa-acbe38c1e303	success	\N	2026-09-25 12:47:41.152615+00
edd12928-8516-4cf5-a2a3-3d8b5a287c56	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	2d56906f-32ab-438b-a817-f8baef2559f0	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	221d84bc-4761-4991-a5aa-acbe38c1e303	success	\N	2026-09-25 12:47:41.172251+00
e9e4570c-13e6-43b3-a74e-e6cc225d6839	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	2d56906f-32ab-438b-a817-f8baef2559f0	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	221d84bc-4761-4991-a5aa-acbe38c1e303	success	\N	2026-09-25 12:47:41.19748+00
8ad1f3d3-5d95-43c4-b4c2-413e6c56408a	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	1faed168-4681-4d21-9407-62ac9f955cda	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	e921643e-db91-4827-969e-ed3ef02faf92	success	\N	2026-09-25 12:47:41.229983+00
3547bea8-cee6-4bc8-8569-af4af31015a8	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	1faed168-4681-4d21-9407-62ac9f955cda	\N	{"state": "queued", "job_type": "transient_failure", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 12:47:41.234735+00
3e614159-9654-4ed0-8111-7cad9a5808c3	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	1faed168-4681-4d21-9407-62ac9f955cda	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	e921643e-db91-4827-969e-ed3ef02faf92	success	\N	2026-09-25 12:47:41.249791+00
99ce140d-4abc-4e0e-8ff3-4c925c826f89	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	1faed168-4681-4d21-9407-62ac9f955cda	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	e921643e-db91-4827-969e-ed3ef02faf92	success	\N	2026-09-25 12:47:41.265686+00
6daca6be-4441-4f18-9c86-ab2cf4da4ac2	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.retry_wait	job_request	1faed168-4681-4d21-9407-62ac9f955cda	{"actor": "worker", "state": "running"}	{"state": "retry_wait", "reason": "retryable transient_error", "correlation_id": null}	production	normal	\N	e921643e-db91-4827-969e-ed3ef02faf92	success	\N	2026-09-25 12:47:41.289038+00
a132d13c-c027-41d2-afba-93455fed1cda	818d3840-1a16-40b6-9757-9e5a67af68f8	scheduler	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	1faed168-4681-4d21-9407-62ac9f955cda	{"actor": "scheduler", "state": "retry_wait"}	{"state": "queued", "reason": "backoff elapsed", "correlation_id": null}	production	normal	\N	e921643e-db91-4827-969e-ed3ef02faf92	success	\N	2026-09-25 12:47:41.309557+00
36620faa-dba7-414c-98cd-a96b3087b4dc	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	1faed168-4681-4d21-9407-62ac9f955cda	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	e921643e-db91-4827-969e-ed3ef02faf92	success	\N	2026-09-25 12:47:41.3227+00
38f44dcf-6a31-42b2-9c97-e400f7762959	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	1faed168-4681-4d21-9407-62ac9f955cda	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	e921643e-db91-4827-969e-ed3ef02faf92	success	\N	2026-09-25 12:47:41.337893+00
cdff6b3b-914c-4b89-b429-7e2d32d7039e	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	1faed168-4681-4d21-9407-62ac9f955cda	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	e921643e-db91-4827-969e-ed3ef02faf92	success	\N	2026-09-25 12:47:41.35884+00
c80d3e86-1136-4764-8fc2-70401902fd14	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.create	job_schedule	a25e0083-a2f2-4347-8cc3-297c6b6c3bc7	\N	{"enabled": true, "job_type": "immediate_success"}	production	normal	\N	\N	success	\N	2026-09-25 12:47:41.374052+00
0f6e2670-0e48-413c-b5f6-85697a765e3a	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	bb7b2f11-44e3-44ca-8749-c6a56ee4051d	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T12:47:36.370345+00:00"}	production	normal	\N	870cad35-bcfe-42cc-ad93-accbc0ee6838	success	\N	2026-09-25 12:47:41.398695+00
bce345aa-a5ea-41e9-aa81-76b7bcf37edd	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	bb7b2f11-44e3-44ca-8749-c6a56ee4051d	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 12:47:41.404317+00
a5877f71-8d2f-4550-bdb3-05ba3a419f67	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	a25e0083-a2f2-4347-8cc3-297c6b6c3bc7	\N	{"job_id": "bb7b2f11-44e3-44ca-8749-c6a56ee4051d", "occurrence": "2026-09-25T12:47:36.370345+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 12:47:41.40953+00
ab506eaf-7699-418c-b85a-e086e6a6e059	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	keyword.import	import_batch	7b10eb3c-df22-4bbc-99a9-b6495ee08aed	\N	{"via_job": false, "accepted": 4, "rejected": 1, "report_type": "search_term", "source_file": "search_term_report_sample.csv", "overlap_detected": []}	production	normal	\N	\N	success	\N	2026-09-25 12:47:41.495106+00
59bf488b-c8fe-41f1-91cc-897ccbe7facf	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	bootstrap.owner	membership	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	{"role": "organization_owner", "email": "t***@staging.local", "created": false, "recover": true}	production	normal	\N	\N	success	\N	2026-09-25 12:48:04.863104+00
00d3eb52-3d01-434b-8c24-28ae3424f30f	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	session.revoke	session	staging-revoke-1790340484999	\N	\N	production	normal	\N	\N	success	\N	2026-09-25 12:48:05.015983+00
094651c5-70d2-47f1-b22f-27d4bb0e6a2b	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	preview.start	preview_session	1f7dd4d2-bdfa-4846-b79e-58a65433425f	\N	{"reason": "staging smoke", "target_role": null}	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 12:48:05.027906+00
c3d0eecf-77f0-49d1-8d2e-9aca12bc161a	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	preview.end	preview_session	1f7dd4d2-bdfa-4846-b79e-58a65433425f	\N	\N	production	audited_customer_preview	\N	\N	success	\N	2026-09-25 12:48:05.04167+00
d3554f3e-85d8-4d94-8278-6f23b6a3fa68	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	3cee773e-9b1c-484f-8538-4bc9d37773d5	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	f1475883-1c5b-4903-aaaf-b5749f2bbbf6	success	\N	2026-09-25 12:48:05.086649+00
311e59d4-c06f-4e82-b82a-11e457329acb	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	3cee773e-9b1c-484f-8538-4bc9d37773d5	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 12:48:05.091418+00
2e235d7e-566d-46d6-9fa5-d48803e5e8b7	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	bb7b2f11-44e3-44ca-8749-c6a56ee4051d	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": "2026-09-25T12:47:36.370345+00:00"}	production	normal	\N	870cad35-bcfe-42cc-ad93-accbc0ee6838	success	\N	2026-09-25 12:48:05.104536+00
da2fd708-40bb-4421-97e1-b495160ef17a	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	bb7b2f11-44e3-44ca-8749-c6a56ee4051d	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": "2026-09-25T12:47:36.370345+00:00"}	production	normal	\N	870cad35-bcfe-42cc-ad93-accbc0ee6838	success	\N	2026-09-25 12:48:05.118317+00
5becec8f-51d8-4168-accd-cf6f8e03d142	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	bb7b2f11-44e3-44ca-8749-c6a56ee4051d	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": "2026-09-25T12:47:36.370345+00:00"}	production	normal	\N	870cad35-bcfe-42cc-ad93-accbc0ee6838	success	\N	2026-09-25 12:48:05.138164+00
218f81e9-2f23-4e52-875d-4fdaac771e2a	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	3cee773e-9b1c-484f-8538-4bc9d37773d5	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	f1475883-1c5b-4903-aaaf-b5749f2bbbf6	success	\N	2026-09-25 12:48:05.152498+00
0310e97c-9205-476d-9cc3-42e31369bfba	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	3cee773e-9b1c-484f-8538-4bc9d37773d5	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	f1475883-1c5b-4903-aaaf-b5749f2bbbf6	success	\N	2026-09-25 12:48:05.167573+00
5525c6c0-5276-4c60-9c81-4a574e04016f	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	3cee773e-9b1c-484f-8538-4bc9d37773d5	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	f1475883-1c5b-4903-aaaf-b5749f2bbbf6	success	\N	2026-09-25 12:48:05.186967+00
af2992ee-82e3-446d-b597-b6d04f0ddc06	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	95d4a73e-2173-489d-ab2c-9857472049de	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": null}	production	normal	\N	63dcf6f3-2062-4538-80ce-d6b57683b3e8	success	\N	2026-09-25 12:48:05.215924+00
0fbde57f-9767-4c2e-8bdc-e79fbcdf3a03	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	95d4a73e-2173-489d-ab2c-9857472049de	\N	{"state": "queued", "job_type": "transient_failure", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 12:48:05.220381+00
0f19f210-7a57-4ea8-9153-ef0e34698691	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	95d4a73e-2173-489d-ab2c-9857472049de	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	63dcf6f3-2062-4538-80ce-d6b57683b3e8	success	\N	2026-09-25 12:48:05.233989+00
3d46d539-087d-4e43-be98-c12e665689f4	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	95d4a73e-2173-489d-ab2c-9857472049de	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	63dcf6f3-2062-4538-80ce-d6b57683b3e8	success	\N	2026-09-25 12:48:05.249399+00
1f4deb3e-2dd2-4bab-96ba-da2bab806275	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.retry_wait	job_request	95d4a73e-2173-489d-ab2c-9857472049de	{"actor": "worker", "state": "running"}	{"state": "retry_wait", "reason": "retryable transient_error", "correlation_id": null}	production	normal	\N	63dcf6f3-2062-4538-80ce-d6b57683b3e8	success	\N	2026-09-25 12:48:05.272236+00
efbcf485-813c-4bf3-96cb-e246616c8bb4	818d3840-1a16-40b6-9757-9e5a67af68f8	scheduler	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	95d4a73e-2173-489d-ab2c-9857472049de	{"actor": "scheduler", "state": "retry_wait"}	{"state": "queued", "reason": "backoff elapsed", "correlation_id": null}	production	normal	\N	63dcf6f3-2062-4538-80ce-d6b57683b3e8	success	\N	2026-09-25 12:48:05.291933+00
d93ef76f-79b9-43c8-99af-241cdb2f419d	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.leased	job_request	95d4a73e-2173-489d-ab2c-9857472049de	{"actor": "worker", "state": "queued"}	{"state": "leased", "reason": "claimed by staging-smoke-worker", "correlation_id": null}	production	normal	\N	63dcf6f3-2062-4538-80ce-d6b57683b3e8	success	\N	2026-09-25 12:48:05.306455+00
7cfed139-0c5e-4c9f-a958-8ca2e4955045	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.running	job_request	95d4a73e-2173-489d-ab2c-9857472049de	{"actor": "worker", "state": "leased"}	{"state": "running", "reason": "execution started", "correlation_id": null}	production	normal	\N	63dcf6f3-2062-4538-80ce-d6b57683b3e8	success	\N	2026-09-25 12:48:05.321301+00
ed594459-e45f-40e9-84fd-1a455c0f6404	818d3840-1a16-40b6-9757-9e5a67af68f8	worker	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.succeeded	job_request	95d4a73e-2173-489d-ab2c-9857472049de	{"actor": "worker", "state": "running"}	{"state": "succeeded", "reason": "handler success", "correlation_id": null}	production	normal	\N	63dcf6f3-2062-4538-80ce-d6b57683b3e8	success	\N	2026-09-25 12:48:05.338806+00
635955b9-c90f-46b8-99aa-8c509f1e691e	818d3840-1a16-40b6-9757-9e5a67af68f8	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.create	job_schedule	6415cb76-6249-46ad-9649-30d1025ba72c	\N	{"enabled": true, "job_type": "immediate_success"}	production	normal	\N	\N	success	\N	2026-09-25 12:48:05.352319+00
952828f9-8361-4011-94d3-6cca4f2ee97b	818d3840-1a16-40b6-9757-9e5a67af68f8	requestor	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.state.queued	job_request	a9ee27a7-5545-4d87-a365-1474d10a102b	{"actor": "requestor", "state": "draft"}	{"state": "queued", "reason": "submitted", "correlation_id": "2026-09-25T12:48:00.349508+00:00"}	production	normal	\N	85f3b973-6cdd-4c00-8f18-b09d72226c07	success	\N	2026-09-25 12:48:05.373857+00
f37a6a50-31bc-4535-b638-9d6d76375cc1	818d3840-1a16-40b6-9757-9e5a67af68f8	organization_owner	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	job.submit	job_request	a9ee27a7-5545-4d87-a365-1474d10a102b	\N	{"state": "queued", "job_type": "immediate_success", "requires_approval": false}	production	normal	\N	\N	success	\N	2026-09-25 12:48:05.378054+00
f35de974-ab2e-44af-b046-76c28ba84526	\N	\N	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	\N	\N	schedule.enqueue	job_schedule	6415cb76-6249-46ad-9649-30d1025ba72c	\N	{"job_id": "a9ee27a7-5545-4d87-a365-1474d10a102b", "occurrence": "2026-09-25T12:48:00.349508+00:00"}	production	normal	\N	\N	success	\N	2026-09-25 12:48:05.383035+00
\.


--
-- Data for Name: catalog_products; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.catalog_products (id, marketplace_id, asin, brand, canonical_title, pack_config_id, variation_family_id, created_at, updated_at) FROM stdin;
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
-- Data for Name: job_requests; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.job_requests (id, organization_id, user_id, service, scope_type, scope_id, data_types, provider_policy, max_estimated_cost, currency, environment, idempotency_key, requires_approval, reason, priority, created_at, state, job_type, payload, payload_schema_version, approval_id, provider_class, budget_class, estimated_cost, parent_job_id, correlation_id, provenance) FROM stdin;
a9ee27a7-5545-4d87-a365-1474d10a102b	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:6415cb76-6249-46ad-9649-30d1025ba72c:2026-09-25T12:48:00.349508+00:00	f	scheduled occurrence 2026-09-25T12:48:00.349508+00:00	5	2026-09-25 12:48:05.361028+00	queued	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T12:48:00.349508+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
bb7b2f11-44e3-44ca-8749-c6a56ee4051d	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	schedule:a25e0083-a2f2-4347-8cc3-297c6b6c3bc7:2026-09-25T12:47:36.370345+00:00	f	scheduled occurrence 2026-09-25T12:47:36.370345+00:00	5	2026-09-25 12:47:41.384809+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	2026-09-25T12:47:36.370345+00:00	{"auth_method": null, "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
2d56906f-32ab-438b-a817-f8baef2559f0	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 12:47:41.112463+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
3cee773e-9b1c-484f-8538-4bc9d37773d5	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:immediate_success	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 12:48:05.064202+00	succeeded	immediate_success	{}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
1faed168-4681-4d21-9407-62ac9f955cda	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 12:47:41.214009+00	succeeded	transient_failure	{"succeed_on_attempt": 2}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
95d4a73e-2173-489d-ab2c-9857472049de	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	durable:transient_failure	\N	\N	[]	\N	\N	USD	production	\N	f	\N	5	2026-09-25 12:48:05.202022+00	succeeded	transient_failure	{"succeed_on_attempt": 2}	1.0	\N	local	free	0.00	\N	\N	{"auth_method": "jwt", "submitted_by": "818d3840-1a16-40b6-9757-9e5a67af68f8"}
\.


--
-- Data for Name: job_runs; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.job_runs (id, job_request_id, state, run_id, attempts, max_attempts, failure_class, error_message, started_at, finished_at, created_at, priority, reserved_cost, actual_cost, scheduled_time, heartbeat_time, lease_owner, lease_expiration, idempotency_key, parent_job_id, correlation_id, output_reference, error_code, error_summary, cancellation_state) FROM stdin;
0f0a520c-bec7-4128-becf-432a731797db	2d56906f-32ab-438b-a817-f8baef2559f0	succeeded	221d84bc-4761-4991-a5aa-acbe38c1e303	1	3	\N	\N	\N	2026-09-25 12:47:41.194973+00	2026-09-25 12:47:41.117921+00	5	\N	\N	\N	2026-09-25 12:47:41.178089+00	staging-smoke-worker	2026-09-25 12:48:41.178084+00	\N	\N	\N	job/2d56906f-32ab-438b-a817-f8baef2559f0/runs/221d84bc-4761-4991-a5aa-acbe38c1e303/output	\N	\N	\N
94629afc-29a5-45bb-860c-eeefa9100db9	bb7b2f11-44e3-44ca-8749-c6a56ee4051d	succeeded	870cad35-bcfe-42cc-ad93-accbc0ee6838	1	3	\N	\N	\N	2026-09-25 12:48:05.135966+00	2026-09-25 12:47:41.387909+00	5	\N	\N	\N	2026-09-25 12:48:05.123792+00	staging-smoke-worker	2026-09-25 12:49:05.123787+00	\N	\N	2026-09-25T12:47:36.370345+00:00	job/bb7b2f11-44e3-44ca-8749-c6a56ee4051d/runs/870cad35-bcfe-42cc-ad93-accbc0ee6838/output	\N	\N	\N
9b0300f5-1c13-4c48-b86a-95c96fe0fdb4	1faed168-4681-4d21-9407-62ac9f955cda	succeeded	e921643e-db91-4827-969e-ed3ef02faf92	2	3	\N	\N	\N	2026-09-25 12:47:41.356651+00	2026-09-25 12:47:41.217148+00	5	\N	\N	2026-09-25 12:47:36.301218+00	2026-09-25 12:47:41.344254+00	staging-smoke-worker	2026-09-25 12:48:41.344249+00	\N	\N	\N	job/1faed168-4681-4d21-9407-62ac9f955cda/runs/e921643e-db91-4827-969e-ed3ef02faf92/output	transient_failure	transient failure simulated	\N
e8390d9d-f7eb-40ab-a09e-a909b8995f64	3cee773e-9b1c-484f-8538-4bc9d37773d5	succeeded	f1475883-1c5b-4903-aaaf-b5749f2bbbf6	1	3	\N	\N	\N	2026-09-25 12:48:05.184886+00	2026-09-25 12:48:05.067497+00	5	\N	\N	\N	2026-09-25 12:48:05.173092+00	staging-smoke-worker	2026-09-25 12:49:05.173087+00	\N	\N	\N	job/3cee773e-9b1c-484f-8538-4bc9d37773d5/runs/f1475883-1c5b-4903-aaaf-b5749f2bbbf6/output	\N	\N	\N
e033c99f-6bd9-41c2-a9e3-b91c9221e88f	95d4a73e-2173-489d-ab2c-9857472049de	succeeded	63dcf6f3-2062-4538-80ce-d6b57683b3e8	2	3	\N	\N	\N	2026-09-25 12:48:05.336881+00	2026-09-25 12:48:05.204665+00	5	\N	\N	2026-09-25 12:48:00.283874+00	2026-09-25 12:48:05.32621+00	staging-smoke-worker	2026-09-25 12:49:05.326206+00	\N	\N	\N	job/95d4a73e-2173-489d-ab2c-9857472049de/runs/63dcf6f3-2062-4538-80ce-d6b57683b3e8/output	transient_failure	transient failure simulated	\N
cae9e2af-6b8a-47ba-a403-0899612cd5bc	a9ee27a7-5545-4d87-a365-1474d10a102b	queued	85f3b973-6cdd-4c00-8f18-b09d72226c07	0	3	\N	\N	\N	\N	2026-09-25 12:48:05.363577+00	5	\N	\N	\N	\N	\N	\N	\N	\N	2026-09-25T12:48:00.349508+00:00	\N	\N	\N	\N
\.


--
-- Data for Name: job_schedules; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.job_schedules (id, organization_id, owner_user_id, job_template, timezone, cron_expression, interval_seconds, enabled, next_run_at, last_run_at, concurrency_policy, misfire_policy, approval_policy, budget_policy, provider_policy, failure_policy, version, archived, created_at, updated_at) FROM stdin;
a25e0083-a2f2-4347-8cc3-297c6b6c3bc7	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	{"job_type": "immediate_success"}	UTC	\N	3600	t	2026-09-25 13:47:36.370345+00	2026-09-25 12:47:36.370345+00	{"max_concurrent": 3}	skip	{}	{}	{}	{}	schedule-1.0.0	f	2026-09-25 12:47:41.37037+00	2026-09-25 12:47:41.412191+00
6415cb76-6249-46ad-9649-30d1025ba72c	5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	818d3840-1a16-40b6-9757-9e5a67af68f8	{"job_type": "immediate_success"}	UTC	\N	3600	t	2026-09-25 13:48:00.349508+00	2026-09-25 12:48:00.349508+00	{"max_concurrent": 3}	skip	{}	{}	{}	{}	schedule-1.0.0	f	2026-09-25 12:48:05.349532+00	2026-09-25 12:48:05.385536+00
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
5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	0.00	0	0	2026-09-25 12:48:05.327846+00
\.


--
-- Data for Name: organizations; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.organizations (id, name, slug, environment, active, created_at) FROM stdin;
5f22dc6f-ddc5-4e35-8f8d-a8803cd5b619	Staging Smoke	staging-smoke	production	t	2026-09-25 12:46:53.510613+00
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
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.users (id, email, display_name, active, created_at) FROM stdin;
818d3840-1a16-40b6-9757-9e5a67af68f8	tyrone@staging.local	tyrone@staging.local	t	2026-09-25 12:46:53.518432+00
\.


--
-- Data for Name: variation_relationships; Type: TABLE DATA; Schema: public; Owner: northstar_staging_owner
--

COPY public.variation_relationships (id, family_id, child_product_id, axis, created_at) FROM stdin;
\.


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
-- Name: catalog_products catalog_products_pkey; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.catalog_products
    ADD CONSTRAINT catalog_products_pkey PRIMARY KEY (id);


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
-- Name: job_requests job_requests_organization_id_idempotency_key_key; Type: CONSTRAINT; Schema: public; Owner: northstar_staging_owner
--

ALTER TABLE ONLY public.job_requests
    ADD CONSTRAINT job_requests_organization_id_idempotency_key_key UNIQUE (organization_id, idempotency_key);


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
-- Name: idx_audit_events__organization_id__occurred_at; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE INDEX idx_audit_events__organization_id__occurred_at ON public.audit_events USING btree (organization_id, occurred_at);


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
-- Name: idx_schedule_occurrences__schedule_id__scheduled_for; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE INDEX idx_schedule_occurrences__schedule_id__scheduled_for ON public.schedule_occurrences USING btree (schedule_id, scheduled_for);


--
-- Name: uq_job_requests_org_idem; Type: INDEX; Schema: public; Owner: northstar_staging_owner
--

CREATE UNIQUE INDEX uq_job_requests_org_idem ON public.job_requests USING btree (organization_id, idempotency_key);


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

\unrestrict AQCCW19bcv9KFqLgvtEMmaVbiWQYNImLGWeiVJDyFqmQuu6OkrgkhE20rjF8SeS

