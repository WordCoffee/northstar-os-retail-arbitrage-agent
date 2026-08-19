# Provider Setup Guide — Keepa & DataForSEO

> **Security notice:** All secrets are stored exclusively in `.env` on your local machine.
> `.env` is git-ignored and must never be committed, pushed, shared, or logged.
> If a credential is ever exposed, revoke and replace it immediately through the
> provider's dashboard before doing anything else.

---

## Status

- **No live API request has been made to either provider.**
- Both providers are configured in `mode: offline_design_only`.
- Credentials are stored locally only; no secret has been committed to this repository.

---

## 1. Keepa

### Purpose

Keepa provides historical Amazon market intelligence via a REST/JSON API:
- Complete price history (Amazon, New, Used, FBA, FBM, Warehouse Deals, Buy Box, Lightning Deals)
- Sales rank (BSR) history
- Rating and review count history
- Detailed product attributes (100+ fields per ASIN)
- Live marketplace offers with seller, condition, shipping, coupons, and Prime pricing
- Buy Box seller history
- Best seller lists (up to 500,000 ASINs)
- Seller profiles with rating history and storefronts
- Product Finder: query the full product database by any field
- Deals feed: everything that changed in the last 12 hours

### Local Secret Handling

The Keepa API key is stored in your local `.env` file as:

```
KEEPA_API_KEY=
```

The actual key value is never stored in source code, JSON, YAML, logs, reports,
or any file tracked by Git.

### Required Environment Variable

| Variable | Description |
|---|---|
| `KEEPA_API_KEY` | Your Keepa REST API key (obtained from the Keepa account API page) |

### Official Documentation

- API overview: https://keepa.com/#!api
- Full API reference: https://keepa.com/api-docs/
- Product Tracking / Webhooks: https://keepa.com/api-docs/tracking.html
- Graph Image API: https://keepa.com/api-docs/graph-image.html

### Relevant Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /product` | Fetch product data, price history, BSR, offers, Buy Box history by ASIN |
| `GET /search` | Keyword product search across Keepa's database |
| `GET /category` | Category lookup and browsing |
| `GET /bestsellers` | Best seller lists by category |
| `GET /deals` | Recent price changes and deal feed |
| `GET /seller` | Seller profile, rating history, storefront ASINs |
| `GET /tracking` | Product price-alert tracking |

### Marketplace Coverage

Keepa covers 11 Amazon marketplaces. This project is configured for `US` (amazon.com).
Other available domains: de, co.uk, fr, co.jp, ca, it, es, in, com.mx, com.br.

### Token / Plan

Keepa uses a token-based billing model. Tokens regenerate per minute around the
clock based on your plan tier. Most single-product lookups cost one token.
Check your current token balance and regeneration rate at: https://keepa.com/#!api

### Key Rotation Warning

Rotating your Keepa API key immediately invalidates any existing integrations using
that key. Coordinate rotation with all consumers before proceeding. After rotation,
update only the local `.env` file — never source code.

---

## 2. DataForSEO

### Purpose

DataForSEO provides current (live) Amazon data via its Amazon Merchant API:
- Current product data and metadata
- Pricing and offer validation
- Seller identity, ratings, and condition
- Shipment options
- Rating and review data
- Offer comparison across merchants

### Local Secret Handling

DataForSEO uses HTTP Basic Auth (login + password). Both values are stored in your
local `.env` file as:

```
DATAFORSEO_LOGIN=
DATAFORSEO_PASSWORD=
```

Neither value is stored in source code, JSON, YAML, logs, reports, or any file
tracked by Git. Authorization headers are constructed at runtime using these
environment variables.

### Required Environment Variables

| Variable | Description |
|---|---|
| `DATAFORSEO_LOGIN` | Your DataForSEO account login (email) |
| `DATAFORSEO_PASSWORD` | Your DataForSEO API password (from the API Access dashboard) |

For programmatic use, combine as `login:password`, Base64-encode the result,
and pass as the `Authorization: Basic <base64>` header.

### Official Documentation

- Full API reference: https://docs.dataforseo.com/v3/
- Authentication guide: https://docs.dataforseo.com/v3/auth/
- API Access dashboard: https://app.dataforseo.com/api-access
- Kickstart guide: https://dataforseo.com/blog/a-kickstart-guide-to-using-dataforseo-apis

### Relevant Amazon Merchant Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/v3/merchant/amazon/products/task_post` | POST | Submit Amazon product data task |
| `/v3/merchant/amazon/products/task_get/$id` | GET | Retrieve product task results |
| `/v3/merchant/amazon/products/live/advanced` | POST | Live advanced Amazon product lookup |
| `/v3/merchant/amazon/asin/task_post` | POST | Submit Amazon ASIN lookup task |
| `/v3/merchant/amazon/asin/task_get/$id` | GET | Retrieve ASIN task results |
| `/v3/merchant/amazon/asin/live/advanced` | POST | Live ASIN advanced lookup |
| `/v3/merchant/amazon/sellers/task_post` | POST | Submit Amazon seller data task |
| `/v3/merchant/amazon/sellers/task_get/$id` | GET | Retrieve seller task results |

### Account Balance

Balance is visible in the DataForSEO dashboard at: https://app.dataforseo.com/api-access
Monitor balance before running batch operations to avoid interruptions.

### Credential Rotation Warning

Resetting the DataForSEO API password immediately invalidates the existing password.
Coordinate with all consumers before rotating. After rotation, update only the
local `.env` file — never source code or committed files.

---

## Pre-Deployment Checklist

Before deploying Northstar OS to any non-local environment:

1. **Rotate both credentials** — generate fresh Keepa API key and DataForSEO
   API password specifically for the production environment.
2. **Store secrets in the deployment platform's secret manager** (e.g., Cloudflare
   Workers Secrets, not `wrangler.toml` or committed environment files).
3. **Delete or re-scope any development credentials** that were used locally.
4. **Verify `.env` is not tracked** by running `git status` and confirming `.env`
   does not appear.
5. **Audit git log** to confirm no secret was ever accidentally committed.

## If a Secret Is Exposed

1. **Revoke immediately** — go to the provider dashboard and rotate/reset the
   credential before doing anything else.
2. **Audit git history** to confirm the scope of exposure.
3. **Notify the provider** if the key may have been used by an unauthorized party.
4. **Update your local `.env`** with the new credential.
5. **Review all systems** that consumed the old credential.
