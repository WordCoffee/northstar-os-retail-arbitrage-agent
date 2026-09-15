# Northstar OS API Reference

> Version 1.0.0 | Base URL: `http://localhost:8000`

## Authentication

All endpoints require a Bearer token. Get one via:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepass123"}'
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

Then include the token in all requests:
```bash
curl -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  http://localhost:8000/api/v1/dashboard/portfolio
```

## Plan Tiers & Rate Limits

| Plan | Price | Rate Limit | Features |
|------|-------|------------|----------|
| Foundation | $0/mo | 30 req/min | Dashboard, read-only, basic analytics |
| Scout | $29/mo | 60 req/min | SourceScout, ListingForge, memory |
| Mover | $79/mo | 120 req/min | AdPilot, SocialPulse, media gen |
| AutothinK | $149/mo | 300 req/min | AI workspace, bulk ops, voice |

## Endpoints

### Auth (`/api/v1/auth`)

#### POST `/auth/register`
Create a new account.

**Body:**
```json
{
  "email": "user@example.com",
  "password": "securepass123",
  "name": "John Doe"
}
```

**Response (201):**
```json
{
  "id": "usr_abc123",
  "email": "user@example.com",
  "name": "John Doe",
  "plan": "foundation",
  "created_at": "2026-01-15T10:00:00Z"
}
```

#### POST `/auth/login`
Get JWT access token.

**Body:** `{"email": "string", "password": "string"}`

**Response (200):**
```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

#### GET `/auth/me`
Get current user profile. Requires auth.

---

### Dashboard (`/api/v1/dashboard`)

#### GET `/dashboard/portfolio`
Portfolio-level KPIs: total revenue, margin, inventory health, alerts count.

**Response (200):**
```json
{
  "total_revenue": 125430.50,
  "total_margin_pct": 34.2,
  "active_asins": 156,
  "inventory_health": "good",
  "pending_alerts": 3,
  "top_products": [...]
}
```

#### GET `/dashboard/product/{asin}`
Detailed analytics for a single ASIN.

---

### SourceScout (`/api/v1`)

#### GET `/buy-list`
Ranked buy list with margin analysis and risk scores.

**Query params:** `?min_margin=20&max_cogs=50&sort=margin`

#### GET `/alerts`
Active alerts: stockout warnings, price war detections, seller crowding.

#### POST `/sourcescout/enrich`
Enrich product data from Bright Data, EasyParser, etc.

**Body:** `{"asin": "B08N5WRWNW", "providers": ["brightdata", "easyparser"]}`

---

### ListingForge (`/api/v1/listings`)

#### POST `/listings/generate`
Generate complete listing copy.

**Body:**
```json
{
  "asin": "B08N5WRWNW",
  "keywords": ["wireless earbuds", "noise cancelling"],
  "brand_voice": "professional",
  "marketplace": "US"
}
```

**Response (200):**
```json
{
  "title": "Wireless Earbuds Noise Cancelling - Bluetooth 5.3...",
  "bullets": ["...", "..."],
  "description": "...",
  "backend_keywords": "...",
  "rufus_score": 87,
  "compliance": {"passed": true, "issues": []}
}
```

#### POST `/listings/compliance-check`
Check listing against Amazon TOS.

#### POST `/listings/rufus-score`
Score listing for Rufus AI readiness.

---

### AdPilot (`/api/v1/ads`)

#### POST `/ads/optimize-bids`
Optimize PPC bids based on ACoS targets.

**Body:**
```json
{
  "campaign_id": "camp_abc",
  "target_acos": 25.0,
  "keywords": [
    {"keyword": "wireless earbuds", "current_bid": 0.85, "impressions": 15000, "clicks": 45, "sales": 120.50}
  ]
}
```

#### POST `/ads/negative-keywords`
Detect wasteful spend and suggest negative keywords.

#### POST `/ads/campaign-structure`
Generate four-tier campaign structure (Research → Optimization → Performance → Defense).

#### GET `/ads/keyword-lifecycle`
Get keyword lifecycle stages and transition rules.

---

### SocialPulse (`/api/v1/social`)

#### POST `/social/caption`
Generate platform-specific caption.

**Body:**
```json
{
  "platform": "instagram",
  "product_name": "Wireless Earbuds",
  "tone": "lifestyle",
  "include_emoji": true
}
```

#### POST `/social/calendar`
Generate 30-day content calendar.

**Body:** `{"brand": "MyBrand", "platforms": ["instagram", "tiktok"], "products": [...]}`

#### POST `/social/hashtags`
Generate relevant hashtags.

#### POST `/social/attribution`
Track social media → Amazon attribution.

---

### AutothinK (`/api/v1/autothink`)

#### POST `/autothink/chat`
Natural language AI workspace.

**Body:**
```json
{
  "message": "What's my best performing product this month?",
  "context": "dashboard",
  "stream": false
}
```

#### POST `/autothink/orchestrate`
Multi-agent orchestration.

---

### Memory (`/api/v1/memory`)

#### POST `/memory/ingest`
Ingest knowledge into memory bank.

**Body:**
```json
{
  "content": "Customers prefer wireless over wired earbuds 3:1",
  "source": "review_analysis",
  "account_id": "usr_abc123"
}
```

#### POST `/memory/search`
Search memory bank by intent.

**Body:** `{"query": "customer preferences for earbuds", "limit": 5}`

---

### Health

#### GET `/health`
Basic health check. No auth required.

**Response:** `{"status": "ok", "version": "1.0.0"}`

#### GET `/health/detailed`
Detailed health with database, Ollama, and adapter status.

---

## Error Codes

| Code | Description |
|------|-------------|
| 400 | Bad request / validation error |
| 401 | Unauthorized (missing or invalid token) |
| 403 | Forbidden (insufficient plan tier) |
| 404 | Resource not found |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

## Rate Limiting

Rate limits are enforced per IP (anonymous) or per user (authenticated). Response headers include:
- `X-RateLimit-Limit`: Maximum requests per window
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Seconds until window resets

## Data Privacy

All AI processing runs locally via Ollama (qwen3:14b). No business data is sent to external LLM APIs. The Memory Bank learns from your data locally. External API calls (Amazon SP-API, Bright Data) are used only for data enrichment and are logged in the audit trail.
