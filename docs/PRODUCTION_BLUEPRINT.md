# NORTHSTAR OS — PRODUCTION BLUEPRINT
## Complete Service Suite + AutothinK Build Plan
### Version 1.0 | 2026-09-15

> This is the authoritative production plan for Northstar OS and AutothinK. Every
> service, every feature, every integration — mapped to competitive parity and
> beyond. No reinventing wheels. Building from what exists, improving where we
> differentiate.

---

## TABLE OF CONTENTS

1. [Platform Architecture](#1-platform-architecture)
2. [Data Foundation — Shared Data Layer](#2-data-foundation)
3. [Service 1: SourceScout — Retail Arbitrage Agent](#3-sourcescout)
4. [Service 2: ListingForge — Listing Optimization Agent](#4-listingforge)
5. [Service 3: AdPilot — Amazon Ads Agent](#5-adpilot)
6. [Service 4: SocialPulse — Social Media Agent](#6-socialpulse)
7. [Service 5: AutothinK — Premium AI Workspace](#7-autothink)
8. [Shared Infrastructure](#8-shared-infrastructure)
9. [Implementation Phases](#9-implementation-phases)
10. [Competitive Feature Matrix](#10-competitive-matrix)
11. [Data Sources & Integrations](#11-data-sources)
12. [Revenue Model](#12-revenue-model)
13. [API Endpoint Map](#13-api-endpoints)
14. [Prompt Templates](#14-prompt-templates)
15. [n8n Workflow Templates](#15-n8n-workflows)

---

## 1. PLATFORM ARCHITECTURE {#1-platform-architecture}

### 1.1 What We're Building vs What Exists

| Competitor | What they are | What we are |
|---|---|---|
| Helium 10 | 30+ SaaS tools for Amazon sellers ($79-$279/mo) | AI-native service suite where agents do the work, not just show data |
| Jungle Scout | Product research + listing builder + ads ($49-$149/mo) | Full arbitrage intelligence from Costco shelf → Amazon listing |
| Advigator | PPC automation, no monthly fee (per-click pricing) | Ads agent with brand-voice awareness and cross-service intelligence |
| Nova | Analytics dashboard + MCP AI integration ($79-$399/mo) | Local-first AI that knows your business better than any dashboard |
| Tryholo.ai | AI ad/social content generation ($29-$99/mo) | Integrated creative pipeline tied to real product data and brand voice |

### 1.2 Our Moat (What Nobody Else Has)

1. **Costco-to-Amazon arbitrage pipeline** — nobody else does this. Period.
2. **Local LLM brain** — your data never leaves your machine. Privacy advantage.
3. **Agent-to-agent coordination** — AdPilot feeds winning keywords to ListingForge. SourceScout feeds COGS to AdPilot for ROAS calculations. No siloed tools.
4. **Memory Bank** — the system learns YOUR judgment over time. Gets better the more you use it.
5. **Subscription tiers with real gates** — Foundation free → Scout → Mover → AutothinK premium.

### 1.3 Technical Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     NORTHSTAR OS PLATFORM                       │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐      │
│  │ SourceScout│  │ListingForge│  │ AdPilot  │  │SocialPulse│      │
│  │ (Arbitrage)│  │(Listings) │  │  (Ads)   │  │(Social)  │      │
│  └─────┬────┘  └─────┬────┘  └────┬─────┘  └────┬─────┘      │
│        │              │            │              │              │
│  ┌─────┴──────────────┴────────────┴──────────────┴─────┐      │
│  │              MASTER BRAIN (Orchestrator)              │      │
│  │   TaskRouter → Agent Delegation → Validation → Learn  │      │
│  └───────────────────────┬───────────────────────────────┘      │
│                          │                                      │
│  ┌───────────────────────┴───────────────────────────────┐      │
│  │              SHARED DATA LAYER                        │      │
│  │  Products │ Keywords │ Campaigns │ Content │ Memory   │      │
│  │  (PostgreSQL + FTS5 + JSONL Audit + Local Embeddings) │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                 │
│  ┌───────────────────────────────────────────────────────┐      │
│  │              PROVIDER ADAPTERS                         │      │
│  │  Amazon SP-API │ Ads API │ Brand Analytics             │      │
│  │  Bright Data   │ Tryholo  │ Perplexity Sonar           │      │
│  │  OpenWebNinja  │ Easyparser│ Scrape.do                │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                 │
│  ┌───────────────────────────────────────────────────────┐      │
│  │              AUTOTHINK WORKSPACE                       │      │
│  │  Chat UI → Router → Context Builder → LLM → Audit     │      │
│  └───────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘

Deployment: Docker Compose (3 services + Ollama + n8n + Supabase)
Ports: 8000 (Northstar API) | 8100 (AutothinK) | 5678 (n8n) | 5432 (Postgres)
```

---

## 2. DATA FOUNDATION — SHARED DATA LAYER {#2-data-foundation}

> Before ANY service can be production-grade, the data layer must be solid.
> Every service reads from and writes to this shared foundation.

### 2.1 Database Schema (PostgreSQL via Supabase)

```sql
-- CORE: Products
CREATE TABLE products (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asin VARCHAR(10) UNIQUE NOT NULL,
  title TEXT,
  brand VARCHAR(255),
  category VARCHAR(255),
  marketplace VARCHAR(10) DEFAULT 'US',

  -- Pricing
  amazon_price DECIMAL(10,2),
  buy_box_price DECIMAL(10,2),
  costco_cost DECIMAL(10,2),
  cost_basis_source VARCHAR(50),

  -- Physical
  weight_lbs DECIMAL(8,2),
  dimensions JSONB,
  fba_fee_estimate DECIMAL(10,2),
  referral_fee_pct DECIMAL(5,2),

  -- Demand
  bsr_rank INTEGER,
  bsr_category TEXT,
  monthly_sales_estimate INTEGER,
  review_count INTEGER,
  rating DECIMAL(3,2),
  seller_count INTEGER,

  -- Economics
  net_profit DECIMAL(10,2),
  roi_pct DECIMAL(6,2),
  risk_score INTEGER,
  authorization_status VARCHAR(30),

  -- Metadata
  last_enriched_at TIMESTAMPTZ,
  data_sources JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- KEYWORDS
CREATE TABLE keywords (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  keyword TEXT NOT NULL,
  search_volume INTEGER,
  relevance_score DECIMAL(3,2),
  trend_direction VARCHAR(10),
  competition_level VARCHAR(20),
  associated_asins TEXT[],
  source VARCHAR(50),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- LISTINGS (versioned)
CREATE TABLE listings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asin VARCHAR(10) REFERENCES products(asin),
  version INTEGER DEFAULT 1,
  title TEXT,
  bullet_points TEXT[],
  description TEXT,
  backend_terms TEXT[],
  search_terms TEXT,
  seo_score DECIMAL(5,2),
  conversion_score DECIMAL(5,2),
  compliance_score DECIMAL(5,2),
  visual_score DECIMAL(5,2),
  rufus_score DECIMAL(5,2),
  overall_score DECIMAL(5,2),
  status VARCHAR(20) DEFAULT 'draft',
  published_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- CAMPAIGNS (ads)
CREATE TABLE campaigns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asin VARCHAR(10) REFERENCES products(asin),
  campaign_type VARCHAR(20),
  campaign_name TEXT,
  status VARCHAR(20) DEFAULT 'paused',
  daily_budget DECIMAL(10,2),
  targeting_type VARCHAR(20),
  impressions INTEGER DEFAULT 0,
  clicks INTEGER DEFAULT 0,
  spend DECIMAL(10,2) DEFAULT 0,
  orders INTEGER DEFAULT 0,
  revenue DECIMAL(10,2) DEFAULT 0,
  acos DECIMAL(6,2),
  roas DECIMAL(6,2),
  bid_strategy VARCHAR(30),
  negative_keywords TEXT[],
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- KEYWORD PERFORMANCE
CREATE TABLE keyword_performance (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  keyword_id UUID REFERENCES keywords(id),
  asin VARCHAR(10) REFERENCES products(asin),
  campaign_id UUID REFERENCES campaigns(id),
  search_volume INTEGER,
  organic_rank INTEGER,
  sponsored_rank INTEGER,
  impressions INTEGER DEFAULT 0,
  clicks INTEGER DEFAULT 0,
  spend DECIMAL(10,2) DEFAULT 0,
  orders INTEGER DEFAULT 0,
  revenue DECIMAL(10,2) DEFAULT 0,
  acos DECIMAL(6,2),
  tier VARCHAR(20) DEFAULT 'bench',
  movement VARCHAR(15),
  days_in_tier INTEGER DEFAULT 0,
  recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- SOCIAL CONTENT
CREATE TABLE social_content (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asin VARCHAR(10) REFERENCES products(asin),
  brand VARCHAR(255),
  channel VARCHAR(20),
  content_type VARCHAR(20),
  body TEXT,
  hashtags TEXT[],
  media_urls TEXT[],
  scheduled_at TIMESTAMPTZ,
  published_at TIMESTAMPTZ,
  status VARCHAR(20) DEFAULT 'draft',
  engagement_metrics JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- FINANCIAL TRACKING
CREATE TABLE transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asin VARCHAR(10) REFERENCES products(asin),
  transaction_type VARCHAR(20),
  amount DECIMAL(10,2),
  quantity INTEGER,
  source VARCHAR(50),
  report_date DATE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- SEARCH QUERY PERFORMANCE
CREATE TABLE search_query_performance (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  query TEXT NOT NULL,
  asin VARCHAR(10),
  date_range DATERANGE,
  impressions INTEGER,
  clicks INTEGER,
  cart_adds INTEGER,
  purchases INTEGER,
  impression_share DECIMAL(5,4),
  click_share DECIMAL(5,4),
  cart_share DECIMAL(5,4),
  purchase_share DECIMAL(5,4),
  search_frequency_rank INTEGER,
  recorded_at TIMESTAMPTZ DEFAULT NOW()
);

-- MEMORY BANK
CREATE TABLE memory_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id UUID NOT NULL,
  entry_type VARCHAR(20),
  content TEXT NOT NULL,
  source VARCHAR(50),
  confidence DECIMAL(3,2) DEFAULT 0.8,
  tags TEXT[],
  provenance JSONB,
  retired_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- AUDIT LOG
CREATE TABLE audit_log (
  id BIGSERIAL PRIMARY KEY,
  account_id UUID,
  action VARCHAR(50),
  entity_type VARCHAR(30),
  entity_id UUID,
  details JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 2.2 Data Import Pipelines

| Source | What it provides | Import frequency | Tool |
|---|---|---|---|
| Amazon SP-API | Orders, inventory, fees, settlements | Hourly | `importers/sp_api_importer.py` |
| Amazon Ads API | Campaigns, keywords, search terms, placements | Daily | `importers/ads_api_importer.py` |
| Amazon Brand Analytics | Search Query Performance, Search Catalog Performance | Weekly | `importers/brand_analytics_importer.py` |
| Amazon Search Term Reports | CSV from Seller Central | Weekly (manual or automated) | `importers/search_term_importer.py` |
| Bright Data / Scrape.do | Product pages, BSR, prices, seller counts | On-demand | Existing adapters |
| Costco catalog | COGS, pack sizes, pricing | Manual + automated refresh | Existing `costco_api_client.py` |
| EasyParser | Seller rosters, buy box, fulfillment | On-demand | Existing `easyparser_seller_enrich.py` |
| Tryholo.ai | Generated ad creatives, social content | On-demand | `importers/tryholo_importer.py` |
| Advigator exports | PPC performance history, bid history | Weekly (CSV upload) | `importers/advigator_importer.py` |

---

## 3. SOURCESCOUT — RETAIL ARBITRAGE AGENT {#3-sourcescout}

> **What it is:** The product sourcing intelligence engine. Finds profitable
> arbitrage opportunities between Costco and Amazon. Scores them. Tracks them.
> Gets you to a buying decision.

### 3.1 Competitive Parity Features

| Feature | Helium 10 name | Jungle Scout name | Our implementation |
|---|---|---|---|
| Product database search | Black Box | Product Database | Our Costco catalog + Amazon cross-reference |
| Sales estimator | Xray | Sales Estimator | `demand_estimator.py` (BSR → monthly sales) |
| Revenue/profit calculator | profitability Calculator | Profit Calculator | `fee_calculator.py` + `pricing.py` (already built) |
| Product tracker | Trendster | Product Tracker | `products` table + BSR/price monitoring |
| Competitor analysis | Market Tracker | Competitive Intelligence | Seller count + BSR movement + review velocity |
| Niche score/opportunity | Xray niche score | Opportunity Score | `margin_shortlist.py` scoring (already built) |
| Inventory management | Inventory Protector | Inventory Manager | Weighted-stockout-prediction from BSR velocity |
| Historical data | Keepa integration | Historical data charts | BSR/price snapshots over time in `market_snapshot_store.py` |
| Supplier research | Supplier Database | Supplier Database | Costco Business Center + online catalog data |
| Category trends | Category Trends | Category Trends | BSR movement analysis across categories |

### 3.2 Northstar Differentiators

| Feature | What it does | Why it matters |
|---|---|---|
| **Costco-to-Amazon mapping** | Maps Costco items → Amazon ASINs by title/UPC/category matching | Nobody else tracks wholesale club arbitrage this way |
| **Invoice verification pipeline** | Validates COGS against Costco receipts, tags match quality | Required for Amazon account health; no other tool does this |
| **COGS gap mining** | Automatically discovers Costco prices for ASINs missing COGS | Already 83 gap ASINs identified in `review_queue.json` |
| **Risk scoring (100-point model)** | Compliance 30 + Margin 20 + Crowding 15 + Volatility 15 + Packaging 10 + Replenishment 10 | Multi-dimensional risk nobody else models |
| **Cycle scaling model** | 50-unit Cycle 1 → compound growth → $10K infusion per cycle | Built-in inventory investment planning |
| **FBA fee verification** | Weight-based fee estimation against actual Amazon 2026 schedule | `amazon_us_fee_rules_2026.py` already built |
| **Authorization Gate** | 4-state buy authorization (blocked / authorized / invoice_pending / needs_review) | Prevents bad buys before money is spent |

### 3.3 Production Build Checklist

#### Phase A: Data Pipeline (Week 1-2)

- [ ] **SP-API product import** — Pull current catalog, pricing, BSR, reviews for tracked ASINs
- [ ] **Brand Analytics import** — Search Query Performance for tracked ASINs
- [ ] **Keepa-style BSR/price history** — Daily snapshots
- [ ] **Costco price refresh** — Automated catalog updates

#### Phase B: Intelligence Engine (Week 2-3)

- [ ] **Demand estimator upgrade** — Move from BSR-only to multi-signal
- [ ] **Competitor crowding detection** — Track seller count changes
- [ ] **Price volatility scoring** — 30/60/90 day price range
- [ ] **Replenishment intelligence** — Stockout prediction

#### Phase C: UI Production (Week 3-4)

- [ ] **Dashboard KPIs** — Real-time portfolio view
- [ ] **Opportunity finder** — New product discovery
- [ ] **Buy list workflow** — From scored to purchased
- [ ] **Historical charts** — Keepa-style trend visualization

### 3.4 Data Requirements

1. Amazon Search Term Reports (CSV from Seller Central)
2. Amazon Business Reports (traffic, conversion, sessions)
3. Costco receipts / invoices (for COGS verification)
4. Current shortlist criteria and thresholds

---

## 4. LISTINGFORGE — LISTING OPTIMIZATION AGENT {#4-listingforge}

> **What it is:** AI-powered listing creation and optimization. Generates titles,
> bullets, descriptions, backend keywords, A+ content copy, and image prompts.
> Scores every listing against Amazon best practices. Tracks Rufus AI readiness.

### 4.1 Competitive Parity Features

| Feature | Helium 10 name | Jungle Scout name | Our implementation |
|---|---|---|---|
| Listing optimizer | Scribbles | Listing Builder | `listing_forge/optimizer.py` |
| Keyword integration | Frankenstein + Scribbles | Listing Builder + Keyword Scout | Keyword Bridge module |
| Listing quality score | Listing Optimization Score | Listing Optimization Score (LOS) | Weighted scoring engine (already built) |
| Backend keyword manager | Frankenstein | — | Backend terms module (250-byte cap) |
| Competitor listing analysis | Xray listing view | Competitive Intelligence | Pull competitor listings, extract patterns |
| A/B testing support | Listing Builder A/B | — | A/B test ingestion module |
| Bulk listing management | Bulk processing | — | Bulk upload parser (already built) |
| Compliance checking | — | — | Rule-based compliance guardrails (already built) |
| Rufus AI optimization | — | — | Rufus readiness scoring (already built) |

### 4.2 Northstar Differentiators

| Feature | What it does | Why it matters |
|---|---|---|
| **AI copy generation (local LLM)** | Generate full listings using qwen3:14b — no API costs, no data leakage | Competitors charge $0.50-2.00 per listing generation |
| **Brand voice enforcement** | Every listing matches your brand's exact tone | No other tool captures and enforces brand voice |
| **Cross-service keyword intelligence** | AdPilot's winning keywords auto-suggest for ListingForge | No competitor connects ads data to listing optimization |
| **Rufus readiness scoring** | Dedicated score for Amazon's AI shopping assistant | Cutting-edge — most competitors don't address Rufus yet |
| **Multi-language generation** | Generate JP/DE/ES/FR listings from English source | Important for Amazon global expansion |
| **A+ Content module prompts** | Generate image prompts for A+ modules with brand colors | Tryholo.ai integration for visual generation |
| **Listing → Ads feedback loop** | Keywords that convert in ads get reinforced in listings | Closed-loop optimization nobody else offers |

### 4.3 Production Build Checklist

#### Phase A: Copy Engine (Week 1-2)

- [ ] **Title generator** — AI-generated titles (≤200 chars, keyword-optimized)
- [ ] **Bullet point generator** — 5 feature bullets (≤500 chars each)
- [ ] **Description / A+ copy generator** — Product description + A+ module text
- [ ] **Backend terms generator** — 250-byte keyword bank
- [ ] **Search terms field** — Hidden search term optimization

#### Phase B: Scoring & Compliance (Week 2-3)

- [ ] **Listing optimization score** — 0-100 composite score
- [ ] **Compliance guardrails** — Rule-based screening
- [ ] **Rufus readiness scorer** — AI assistant optimization

#### Phase C: Integration & UI (Week 3-4)

- [ ] **Keyword bridge** — Connects Ads keywords to Listing optimization
- [ ] **Media prompt generator** — Image/video prompts for A+
- [ ] **Listing versioning** — Track every change
- [ ] **Bulk listing builder** — Process multiple ASINs at once

### 4.4 Data Requirements

1. Word Coffee listing examples (best-performing copy for brand voice)
2. Amazon Brand Analytics Search Query Performance
3. Amazon bulk upload template for your category
4. Tryholo.ai account details and brand assets
5. Advigator export data (converting keywords for keyword bridge)

---

## 5. ADPILOT — AMAZON ADS AGENT {#5-adpilot}

> **What it is:** Amazon PPC campaign management. Automates keyword harvesting,
> bid optimization, negative keyword management, and campaign structure.

### 5.1 Competitive Parity Features

| Feature | Helium 10 name | Advigator name | Our implementation |
|---|---|---|---|
| Campaign management | Adtomic | Core automation | `ad_pilot/campaign_manager.py` |
| Keyword harvesting | Cerebro + Adtomic | Auto keyword harvest | `ad_pilot/keyword_harvester.py` |
| Bid optimization | Adtomic AI | Auto bid rules | `ad_pilot/bid_optimizer.py` |
| Negative keyword mgmt | Adtomic | Auto negative | `ad_pilot/negative_manager.py` |
| ACoS target management | Adtomic | Campaign goals | Rule engine (already built) |
| Search term analysis | Cerebro | Search term report analysis | `ad_pilot/search_term_analyzer.py` |
| Campaign structure | Adtomic templates | Auto structure | Four-tier model (already designed) |
| Placement optimization | Adtomic | — | `ad_pilot/placement_optimizer.py` |
| Dayparting | Adtomic | — | `ad_pilot/dayparting.py` |
| Budget allocation | Adtomic | Budget rules | `ad_pilot/budget_allocator.py` |

### 5.2 Northstar Differentiators

| Feature | What it does | Why it matters |
|---|---|---|
| **Four-tier campaign structure (automated)** | Auto → Broad → Phrase → Exact promotion lifecycle | Advigator charges per-click; we do this with local AI for free |
| **Keyword lifecycle tracking** | Bench → Almost Winner → Winner with automated promotion/demotion | Nobody tracks keyword lifecycle this granularly |
| **Fixed bid guardrails** | Autonomous: ≤20% decrease, ≤10% increase, add negatives. Gated: everything else | Safety rails that prevent runaway ad spend |
| **Cross-service intelligence** | ListingForge keywords feed into AdPilot; AdPilot winners feed back | Closed-loop no competitor offers |
| **ROI-integrated bidding** | Knows your actual COGS and margin → bids accordingly | Not just ACoS — real profit optimization |
| **Negative keyword intelligence** | Auto-detects irrelevant traffic from search term reports | Saves money on wasted clicks |
| **Competitor ASIN targeting** | Find competitor ASINs for product targeting campaigns | Auto-discovered from SourceScout data |
| **Amazon Attribution tracking** | External traffic attribution for rank boost | SocialPulse drives traffic → AdPilot measures impact |

### 5.3 Production Build Checklist

#### Phase A: Amazon Ads API Integration (Week 1-2)

- [ ] **Amazon Ads API client** — Connect to Sponsored Products, Sponsored Brands
- [ ] **Search Term Report import** — Pull and analyze search terms
- [ ] **Campaign structure builder** — Automated four-tier setup
- [ ] **Daily performance sync** — Automated data pull

#### Phase B: Intelligence Engine (Week 2-3)

- [ ] **Keyword harvester** — Auto-promote winners, auto-demote losers
- [ ] **Negative keyword manager** — Auto-add irrelevant terms
- [ ] **Bid optimizer** — Continuous bid adjustment
- [ ] **Budget allocator** — Shift budget to winners

#### Phase C: Advanced Features (Week 3-4)

- [ ] **Placement optimization** — Top of Search vs Rest of Search
- [ ] **Dayparting** — Time-of-day bid adjustment
- [ ] **Competitor ASIN targeting** — Auto-discover targets
- [ ] **Campaign reporting dashboard** — Real-time performance view

### 5.4 Data Requirements

1. Amazon Ads API developer credentials (OAuth)
2. Search Term Reports (as many months as available)
3. Advigator export data (historical performance)
4. Current campaign structure
5. Target ACoS per product

---

## 6. SOCIALPULSE — SOCIAL MEDIA AGENT {#6-socialpulse}

> **What it is:** Brand-aware social media content generation and scheduling.
> Creates posts, captions, hashtags, ad creatives, and email content across
> Instagram, Facebook, TikTok, and Twitter — all in your brand's voice.

### 6.1 Competitive Parity Features

| Feature | Hootsuite/Buffer | Tryholo.ai | Our implementation |
|---|---|---|---|
| Multi-platform posting | Core feature | Core feature | `social_pulse/publisher.py` |
| Content calendar | Content calendar | Auto-calendar | 7-slot calendar (already built) |
| AI content generation | — | Core feature | Local LLM + brand voice |
| Hashtag research | Hashtag suggestions | Auto-hashtags | `social_pulse/hashtag_engine.py` |
| Analytics/tracking | Platform analytics | Basic tracking | `engagement_metrics` in DB |
| Content templates | Post templates | Ad templates | `social_pulse/templates/` |
| Image generation | — | Core feature (Holo) | Tryholo.ai integration |
| Email marketing | — | Auto-emails | `social_pulse/email_generator.py` |

### 6.2 Northstar Differentiators

| Feature | What it does | Why it matters |
|---|---|---|
| **Brand voice learning** | Captures YOUR voice from past posts, edits, and preferences | Gets more "you" over time |
| **Product-to-social pipeline** | SourceScout finds a product → ListingForge writes the listing → SocialPulse creates social content | End-to-end content from one data flow |
| **Amazon Attribution integration** | Every social post can include `maas=` tracking tags | Measures external traffic's impact on Amazon rank |
| **Occasion/niche gifting angles** | Word Coffee lesson: gifting angles convert better than category terms | AI-generated niche angles per product |
| **Seasonal content planning** | Auto-generates seasonal content calendar | Proactive, not reactive |
| **Content → Ads feedback loop** | Social engagement data informs Amazon ad targeting | Cross-channel intelligence |
| **Influencer outreach templates** | AI-generated outreach messages per niche | Saves hours of manual outreach |
| **TOS-compliant review requests** | Generates Amazon-compliant review request emails | Won't get your account banned |

### 6.3 Production Build Checklist

#### Phase A: Content Generation Engine (Week 1-2)

- [ ] **Brand voice profiles** — Codify each brand's voice
- [ ] **Caption generator** — Platform-specific content
- [ ] **Hashtag engine** — Smart hashtag sets per post
- [ ] **Image prompt generator** — Scene descriptions for Tryholo.ai

#### Phase B: Content Calendar & Scheduling (Week 2-3)

- [ ] **Content calendar** — 30-day rolling calendar
- [ ] **Scheduling system** — Queue and publish
- [ ] **Engagement tracking** — What's working

#### Phase C: Advanced Features (Week 3-4)

- [ ] **Influencer outreach** — AI-generated outreach
- [ ] **Email marketing** — Amazon-compliant review requests
- [ ] **External traffic strategy** — Amazon Attribution

### 6.4 Data Requirements

1. Brand voice examples (5-10 past social posts per brand)
2. Tryholo.ai API key + examples of generated content you like
3. Social media account credentials
4. Amazon Attribution tags
5. Seasonal calendar (key dates for your brands)

---

## 7. AUTOTHINK — PREMIUM AI WORKSPACE {#7-autothink}

> **What it is:** The premium layer. A chat-based workspace where you describe
> what you want and the Master Brain orchestrates it — pulling from any service,
> any data source, any tool. Think: Claude Code meets Amazon Seller Central.

### 7.1 Competitive Parity Features

| Feature | Claude Code | Perplexity | Our implementation |
|---|---|---|---|
| Natural language interface | Core | Core | AutothinK chat UI (already built) |
| Code generation | Core | — | AUTOTHINK_CODE track |
| Research & analysis | — | Core | AUTOTHINK_RESEARCH track |
| File operations | Core | — | AUTOTHINK_COMPUTER track |
| Tool use | Core | Core | Master Brain Gateway (already built) |
| Session history | — | — | SessionStore (already built) |
| Audit trail | — | — | autothink-runs.jsonl (already built) |

### 7.2 Northstar Differentiators

| Feature | What it does | Why it matters |
|---|---|---|
| **Private/local-first** | Runs on your machine via Ollama. Data never leaves. | Privacy advantage over all cloud competitors |
| **Domain-specific intelligence** | Knows Amazon FBA, PPC, listings, sourcing — not just generic AI | Purpose-built for your business |
| **Agent orchestration** | "Optimize my listing and adjust bids" → routes to ListingForge + AdPilot | No competitor connects multiple AI services |
| **Memory Bank integration** | Remembers preferences, past decisions, brand guidelines | Gets better the more you use it |
| **Cross-service queries** | "Most profitable product and how are its ads?" | Pulls data from SourceScout + AdPilot |
| **Proactive suggestions** | Memory Bank detects patterns → suggests actions | Anticipates needs |
| **Voice interface** | Speak to your AI assistant | Already scaffolded |

### 7.3 Production Build Checklist

#### Phase A: Core Intelligence (Week 1-2)

- [ ] **Context builder upgrade** — Real data injection
- [ ] **Tool definitions** — Let the LLM call real functions
- [ ] **Response formatting** — Structured, actionable output
- [ ] **Multi-turn conversations** — Context persistence

#### Phase B: Memory Bank Integration (Week 2-3)

- [ ] **Memory ingestion** — From chat, from edits, from data
- [ ] **Memory retrieval** — Context-aware recall
- [ ] **Proactive mode** — Knowledge mass triggers suggestions

#### Phase C: Advanced Features (Week 3-4)

- [ ] **Voice interface** — Speak to AutothinK
- [ ] **Workflow automation** — Natural language → n8n workflows
- [ ] **Multi-brand management** — Switch between brands

### 7.4 Data Requirements

1. Real questions you want to ask
2. Workflow automations (repetitive weekly tasks)
3. Voice preferences (input/output)

---

## 8. SHARED INFRASTRUCTURE {#8-shared-infrastructure}

### 8.1 Authentication & Multi-Tenancy

| Component | Implementation | Priority |
|---|---|---|
| JWT authentication | FastAPI dependency + refresh tokens | P0 |
| User registration/login | `/api/v1/auth/*` endpoints | P0 |
| Plan enforcement | Middleware checks `subscription_plans.json` entitlements | P0 |
| API key management | Per-subscriber keys for programmatic access | P1 |
| OAuth2 (future) | Google, Amazon Seller Central SSO | P2 |

### 8.2 Billing & Subscriptions (Stripe)

| Plan | Price | Gates Entitled | Target User |
|---|---|---|---|
| Foundation | $0/mo | None (demo/read-only) | Tire-kickers, learners |
| Scout | $29/mo | sourcescout_live_pull, sourcescout_enrich, listingforge_copy, adpilot_ads_read | Single-product sellers |
| Mover | $79/mo | All Scout + listingforge_media, socialpulse_attrib | Growing brands |
| AutothinK | $149/mo | Everything + adpilot_bulk_exec, socialpulse_publish, autothink_workspace | Full-service operators |

### 8.3 Deployment Architecture

```yaml
# docker-compose.prod.yml
services:
  nginx:
    image: nginx:alpine
    ports: ["443:443", "80:80"]

  ollama:
    image: ollama/ollama:latest
    deploy:
      resources:
        reservations:
          devices: [{driver: nvidia, count: all, capabilities: [gpu]}]

  northstar:
    build: ./Northstar_backend
    environment:
      - DATABASE_URL=postgresql://...

  autothink:
    build: ./autothink
    environment:
      - OLLAMA_HOST=http://ollama:11434

  n8n:
    image: n8nio/n8n
    ports: ["5678:5678"]

  supabase-db:
    image: supabase/postgres:latest

  redis:
    image: redis:alpine
```

### 8.4 Monitoring & Observability

| Tool | What it monitors | Alert channel |
|---|---|---|
| Health endpoints | Service liveness, Ollama connectivity, DB connectivity | Docker healthcheck |
| Structured logging (JSON) | All API requests, errors, provider calls | Log aggregation |
| Credit tracking | API credit balance per provider | Alert at 20% remaining |
| Performance metrics | Response times, throughput, error rates | Dashboard |

---

## 9. IMPLEMENTATION PHASES {#9-implementation-phases}

### Master Timeline (13 Weeks)

```
WEEK  1  2  3  4  5  6  7  8  9  10  11  12  13
      ├──────────┤
      Phase 1: Foundation (test suite, data layer, CI/CD)
         ├──────────┤
         Phase 2: SourceScout Production (data pipeline, intelligence, UI)
            ├──────────────┤
            Phase 3: ListingForge + AdPilot (copy engine, ads API, scoring)
               ├──────────┤
               Phase 4: SocialPulse + AutothinK (content, memory, voice)
                  ├──────────────────┤
                  Phase 5: Auth + Billing + Deploy (auth, Stripe, Docker)
                                    ├──────────┤
                                    Phase 6: Launch Prep (docs, soft launch)
```

### Phase 1: Foundation (Weeks 1-2)

| Day | Task | Blocker |
|---|---|---|
| 1-2 | Fix DataForSEO adapter (15 missing symbols) | None |
| 2 | Fix credential exposure in tests | None |
| 3 | Delete dead code, consolidate .env | None |
| 4 | Structured logging | None |
| 5 | Health check endpoints + API versioning | None |
| 6 | Error handling + rate limiting + CORS | None |
| 7-8 | CI/CD pipeline (GitHub Actions) | None |
| 9-10 | PostgreSQL schema + data import scaffolding | None |

### Phase 2: SourceScout Production (Weeks 3-4)

SP-API import, Brand Analytics, BSR snapshots, demand estimator upgrade, competitor detection, price volatility, dashboard KPIs, opportunity finder, buy list workflow, historical charts.

### Phase 3: ListingForge + AdPilot (Weeks 5-8)

Title/bullet/desc generators, compliance + Rufus scoring, keyword bridge, media prompts, Amazon Ads API client, Search Term import, keyword harvester, bid optimizer, campaign structure, budget allocator, placement optimization, dayparting.

### Phase 4: SocialPulse + AutothinK (Weeks 8-10)

Brand voice profiles, caption generator, hashtag engine, content calendar, scheduling, AutothinK context builder, tool definitions, Memory Bank MVP, voice interface.

### Phase 5: Auth + Billing + Deploy (Weeks 10-12)

JWT auth, user management, Stripe, onboarding, admin dashboard, production Docker, Nginx + TLS, monitoring.

### Phase 6: Launch Prep (Week 13)

Security audit, documentation, landing page, soft launch, feedback, public launch.

---

## 10. COMPETITIVE FEATURE MATRIX {#10-competitive-matrix}

| Feature | H10 | JS | Advigator | Tryholo | **Northstar** |
|---|---|---|---|---|---|
| Product Research | ✅ | ✅ | — | — | ✅ Costco+Amazon |
| Keyword Research | ✅ | ✅ | — | — | ✅ Brand Analytics+Ads |
| Listing Optimization | ✅ | ✅ | — | — | ✅ AI-generated+scored |
| PPC Management | ✅ | — | ✅ | — | ✅ Full+cross-service |
| Social Media | — | — | — | ✅ | ✅ Brand-voice aware |
| Ad Creative Gen | — | — | — | ✅ | ✅ Tryholo+local AI |
| Inventory Mgmt | ✅ | ✅ | — | — | ✅ Costco restocking |
| Profit Tracking | ✅ | ✅ | — | — | ✅ COGS verification |
| BSR Tracking | ✅ | ✅ | — | — | ✅ With cost basis |
| Competitor Analysis | ✅ | ✅ | — | — | ✅ Seller+price+BSR |
| AI Chat Assistant | — | — | — | — | ✅ AutothinK |
| Local/Private Mode | — | — | — | — | ✅ Ollama |
| Memory/Learning | — | — | — | — | ✅ Memory Bank |
| Multi-Brand | ✅ | ✅ | — | ✅ | ✅ Per-brand memory |
| Pricing | $79-279/mo | $49-149/mo | per-click | $29-99/mo | **$0-149/mo** |

---

## 11. DATA SOURCES & INTEGRATIONS {#11-data-sources}

### 11.1 Amazon APIs

| API | What it provides | Access requirements | Cost |
|---|---|---|---|
| SP-API | Orders, inventory, fees, settlements, catalog | Developer registration + LWA auth | Free |
| Ads API | Campaigns, keywords, search terms, reporting | Amazon Ads console developer access | Free |
| Brand Analytics | Search Query Performance, catalog performance | Brand Registry required | Free |

### 11.2 Third-Party Providers (already configured)

| Provider | What it provides | Cost | Status |
|---|---|---|---|
| Bright Data Web Unlocker | Amazon product pages, Costco pages | 5,000 free credits/mo | ✅ Active |
| EasyParser | Amazon seller rosters, buy box data | ~$0.01/ASIN | ✅ Active, balance 31 |
| OpenWebNinja | Costco search/refresh | 100 free req/mo | ✅ Active |
| Scrape.do | Amazon dp pages (fallback) | Free tier available | ✅ Key SET |
| Firecrawl | Amazon pages (fallback) | 1,000 free pages/mo | ✅ Key SET |
| Chocodata | Amazon product data | Free tier available | ⚠️ Key SET, untested |
| Tryholo.ai | Ad/social content generation | API key needed | ⬜ Needs setup |

### 11.3 Data You Need to Provide

| Data | Where to get it | What it enables |
|---|---|---|
| Amazon Search Term Reports | Seller Central → Advertising → Reports | Keyword intelligence, AdPilot |
| Amazon Business Reports | Seller Central → Reports → Business | Traffic, conversion, sessions |
| Amazon Search Query Performance | Seller Central → Brand Analytics | Keyword funnel data |
| Amazon Fee Reports | Seller Central → Payments → Transaction | Accurate fee calculations |
| Advigator exports | Advigator dashboard | Historical PPC data |
| Costco invoices/receipts | Your records | COGS verification |
| Tryholo.ai account | tryholo.ai | Creative generation API |
| Social media credentials | Meta Business, TikTok Business | Content scheduling |

---

## 12. REVENUE MODEL {#12-revenue-model}

### 12.1 Cost Structure

| Item | Monthly cost | Notes |
|---|---|---|
| Ollama (local) | $0 | Free, runs on your GPU |
| Supabase | $0-25 | Free tier or Pro |
| n8n | $5-10 | Self-hosted |
| Cloudflare | $0-5 | Tunnel + Pages |
| Domain + TLS | $1-2 | Cloudflare manages |
| **Total** | **~$30-40/mo** | Scales with users |

### 12.2 Unit Economics

| Metric | Value |
|---|---|
| Cost to serve per user | ~$1-2/mo |
| Gross margin | 90%+ |
| Break-even | ~5 subscribers at $29/mo |
| Revenue at 100 subscribers | ~$7,900/mo |
| Revenue at 1000 subscribers | ~$79,000/mo |

---

## 13. API ENDPOINT MAP {#13-api-endpoints}

### Northstar OS API (port 8000)

```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
GET    /api/v1/auth/me
GET    /api/v1/products
GET    /api/v1/products/{asin}
POST   /api/v1/products/import
PATCH  /api/v1/products/{asin}
GET    /api/v1/keywords
GET    /api/v1/keywords/{id}/performance
POST   /api/v1/keywords/sync
GET    /api/v1/listings
POST   /api/v1/listings/generate
PATCH  /api/v1/listings/{id}
POST   /api/v1/listings/{id}/publish
GET    /api/v1/campaigns
GET    /api/v1/campaigns/{id}/keywords
POST   /api/v1/campaigns/sync
POST   /api/v1/campaigns/recommend
GET    /api/v1/social/calendar
POST   /api/v1/social/generate
POST   /api/v1/social/{id}/publish
GET    /api/v1/analytics/dashboard
GET    /api/v1/analytics/trends
GET    /api/v1/analytics/keywords
GET    /api/v1/memory/search
POST   /api/v1/memory/ingest
DELETE /api/v1/memory/{id}
GET    /health
GET    /health/detailed
```

### AutothinK API (port 8100)

```
GET    /
GET    /health
GET    /api/autothink/models
POST   /api/autothink/run
GET    /api/autothink/history
GET    /api/autothink/suggestions
```

---

## 14. PROMPT TEMPLATES {#14-prompt-templates}

### Listing Title Generation

```
You are a world-class Amazon listing copywriter. Generate an optimized product title.

Product: {product_title}
Brand: {brand_name}
Category: {category}
Top keywords (by search volume): {top_10_keywords}
Competitor titles: {competitor_titles}
Brand voice: {brand_voice_profile}

Rules:
- Maximum 200 characters
- Lead with the most important keyword
- Include brand name
- Include key product attributes (size, count, flavor, etc.)
- No prohibited words (best, #1, guaranteed, etc.)
- Make it readable and compelling

Generate 3 title options with scores.
```

### Bid Optimization Decision

```
You are an Amazon PPC optimization expert. Analyze this keyword's performance.

Keyword: {keyword}
ASIN: {asin}
Current bid: ${current_bid}
ACoS: {acos}%
Target ACoS: {target_acos}%
Clicks (7d): {clicks}
Orders (7d): {orders}
CTR: {ctr}%
CVR: {cvr}%

Rules:
- ACoS >45% AND ≥10 clicks: decrease 10-30%
- ACoS 30-45%: decrease 5-10%
- ACoS 15-30%: increase 5-15%
- ACoS <15%: increase 15-30%
- ≥20 clicks, 0 orders: pause
- 1-2 orders + ACoS ≤ target: promote tier

Provide: recommended bid, adjustment %, reasoning, confidence, approval needed.
```

---

## 15. N8N WORKFLOW TEMPLATES {#15-n8n-workflows}

### Workflow 1: Daily Data Refresh

```
Trigger: Cron (6:00 AM daily)
1. SP-API: Pull latest orders + inventory
2. SP-API: Pull campaign performance (yesterday)
3. SP-API: Pull search term report
4. Bright Data: BSR snapshot for tracked ASINs
5. Database: Write all data to Postgres
6. Database: Recalculate margins + scores
7. Notification: "Daily refresh complete."
```

### Workflow 2: Price Change Alert

```
Trigger: Database webhook (price change > 10%)
1. Detect: product.amazon_price changed by >10%
2. Calculate: new margin vs old margin
3. Alert: "Price dropped on {asin}. New margin: {margin}."
```

### Workflow 3: Keyword Promotion

```
Trigger: Daily analysis (AdPilot keyword harvester)
1. Query: keywords with 1-2 orders + ACoS ≤ target
2. Action: promote to next tier campaign
3. Notify: "Promoted {keyword} to {new_tier}."
```

---

*This blueprint is the living reference. Update it as features ship, requirements
change, or new competitive intelligence emerges. Version-stamp updates.*

*Last updated: 2026-09-15*
*Author: Northstar Master Brain*
*Status: Version 1.0 — ready for implementation*
