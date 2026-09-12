# Provider Setup

## Bright Data (PRIMARY)
Bright Data remains the **primary** Amazon current-listing and product-enrichment
source. Its configuration, credentials, routing, code, tests, cache behavior,
and workflows are unchanged and must not be disabled or replaced.

## DataForSEO (SECONDARY — validation only)
DataForSEO is configured as a **secondary, narrowly routed** Amazon Merchant
validation source. It is **not** a replacement for Bright Data and is **not**
used for broad discovery by default.

Credentials are supplied only through local environment variables in `.env`
(which is git-ignored and never committed):

- `DATAFORSEO_LOGIN`
- `DATAFORSEO_PASSWORD`

No credential values are stored in this repository, in `config/`, in docs, or in
any tracked file. The configuration below is **secret-free** — it references the
environment variable *names* only.

Secret-free configuration lives in `config/provider_config.example.json`:

| Field | Value | Meaning |
|-------|-------|---------|
| `enabled` | `true` | Provider entry is present for future design. |
| `provider_role` | `secondary_validation` | Narrowly routed validation only. |
| `marketplace` | `US` | Amazon US marketplace. |
| `login_environment_variable` | `DATAFORSEO_LOGIN` | Env var name (no value stored). |
| `password_environment_variable` | `DATAFORSEO_PASSWORD` | Env var name (no value stored). |
| `mode` | `offline_design_only` | No live calls yet; design/adapter prep only. |
| `use_only_after_bright_data_shortlist` | `true` | Only for Bright Data-shortlisted ASINs. |

### Future DataForSEO ownership (design only — no live calls yet)
- Amazon Merchant product lookup by keyword.
- Amazon ASIN validation.
- Seller/offer validation for Bright Data-shortlisted ASINs.
- Seller fields: price, condition, shipping/shipment, and seller rating.

### Out of scope for DataForSEO
- Broad discovery by default.
- Any Amazon eligibility, restriction, fee, HAZMAT, invoice, authenticity,
  supplier-authorization, or purchase-approval decision. Those fields are
  treated as unverified / not final.

## Keepa
Not used.
