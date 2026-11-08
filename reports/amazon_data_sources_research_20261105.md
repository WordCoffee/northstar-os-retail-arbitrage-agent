# Amazon product/sales data sources — deep research (2026-11-05)

**Scope:** GitHub repos, Hugging Face datasets/models, MCP/agent tools, and free-tier APIs that can pull
Amazon **product** and/or **sales** data. Research only — no Amazon request was made, no credentials used.
Standing gate (Amazon = operator approval) respected; this report is a decision aid, not an execution.

**Repo context:** Northstar already wires Bright Data Web Unlocker (primary), ChocoData, Scavio,
Unwrangle, Easyparser, Rainforest, DataForSEO, Firecrawl, Browserbase, Scrapedo, Canopy, RapidAPI
router. Current pain: Unwrangle 403 quota exhaustion, Bright Data zone mismatch (fixed 2026-11-02),
ChocoData 0 credits. Goal of this research = find *better/free* alternatives or complements.

---

## 1. Executive summary (TL;DR)

- **No single free source replaces a paid scraper at scale.** Amazon's official surfaces (Creators API,
  SP-API, Data Kiosk) are the only "free"/contractual sources, but they are **gated**: Creators API
  requires an Amazon Associates account with qualifying sales; SP-API/Data Kiosk require a Seller
  (or Vendor) account and LWA/OAuth. None gives arbitrary third-party product/sales data.
- **PA-API 5 is dead (deprecated, 403 AccessDenied since 2026-04-30).** Migrate to **Creators API**
  only if Northstar qualifies as an affiliate publisher. Otherwise it is not an option.
- **Best free-tier *managed* scraper for product data:** Pangolinfo (60 credits/mo, no card) and
  ScraperAPI/Scrapingdog free tiers (100–5,000 credits). **Pangolinfo is the only one with an
  Amazon-specific MCP server (20 tools)** — directly relevant to our agent lane.
- **Best open-source, no-key GitHub repos:** `omkarcloud/amazon-scraper` (252★, 2026-02, no key, no
  proxies, clean JSON) and `theonlyanil/amzpy` (AmzPy, lightweight, no key). Both are **best-effort
  and break on anti-bot**; treat as fallback/enrichment, not primary.
- **Browser agents (Browser Use, Skyvern) are the wrong tool for Amazon product data** at volume:
  they cost LLM tokens per page and are fragile vs Amazon's anti-bot. Use them only for form-filling
  or one-off extraction, not catalog scans.
- **Hugging Face contributes models, not live data.** `McAuley-Lab/Amazon-Reviews-2023` is the
  canonical large-scale dataset (571M reviews, 48M items, to Sep-2023) — useful for offline
  benchmarking/training, not live sourcing. `NuExtract` + DOM pruning is the right pattern for
  LLM-based extraction from HTML we already fetch.
- **Recommendation:** keep Bright Data primary; add **Pangolinfo free tier** as a new secondary
  (MCP + REST, Amazon-specific, 60 credits/mo) and **omkarcloud/amazon-scraper** as a local
  no-key fallback for enrichment; evaluate **Creators API** only if/when Northstar holds an
  Associates account with qualifying sales; use **NuExtract + Qwen3** for extraction from HTML we
  already own (no new network calls).

---

## 2. Official Amazon surfaces (free but gated)

| Surface | What it gives | Gate / cost | Verdict for Northstar |
|---|---|---|---|
| **Creators API** (successor to PA-API 5) | Catalog: title, price, images, features, offers; search by keyword/ASIN; variations; browse nodes | Amazon Associates account + **3 qualifying sales in 30 days** to keep access; affiliate attribution expected | Not available today (no Associates account with sales). Re-evaluate if Northstar ever publishes affiliate content. Migration doc: affiliate-program.amazon.com/creatorsapi |
| **SP-API** (Selling Partner) | **Your own** catalog, orders, inventory, FBA fees, reports | Seller account + LWA OAuth + AWS IAM; rate limits | Only for data Northstar *sells*; not for third-party sourcing. Already referenced in repo (sp-api topic). |
| **Data Kiosk** (SP-API) | Sales, traffic, inventory analytics for **your** store | Same as SP-API | Same; an MCP server exists (amzn/selling-partner-api-samples) — useful only post-seller-account. |
| **Amazon Business Product Search API** | Business purchasing/procurement catalog | Amazon Business account | Procurement angle, not arbitrage sourcing; skip. |

**Key fact:** PA-API 5 now returns `403 AccessDeniedException` ("Product Advertising API is
deprecated. Please migrate to Creators API"). Any code still calling PA-API must migrate.

## 3. Free-tier *managed* scraper APIs (product data)

| Provider | Free tier | Amazon coverage | Notes / fit |
|---|---|---|---|
| **Pangolinfo** | 60 credits/mo, reset monthly, **no card** | Product (1 credit/page), reviews (5 credits/page); 51 product fields | **Best new candidate.** Ships an **Amazon Data MCP server (20 tools)** + REST + agent "Scraper Skill". Directly feeds our agent lane. Repo: `Pangolin-spg/amazon-scraper`. |
| **ScraperAPI** | 5,000 credits on signup | Generic Amazon endpoint (product/search/reviews) | Higher volume free; generic (not Amazon-specific fields). Good bulk fallback. |
| **Scrapingdog** | 100 credits (one-time) | `/amazon/product`, `/amazon/search`, `/amazon/reviews` | Small; useful for smoke tests only. |
| **SerpApi** | 100 searches/mo | Amazon search/product/reviews | Good for keyword discovery; structured. |
| **Bright Data** (already wired) | 5,000 credits/mo shared pool, 1 credit=request, hard stop at 0, no rollover | Web Unlocker (raw HTML) | **Primary today.** Zone mismatch fixed 2026-11-02; datasets API not provisioned on account. |
| **ChocoData** (already wired) | 1,000 credits on signup | `/amazon/search` 5 credits/call, `/amazon/detail` 5/ASIN | **Exhausted (0 credits)** per 2026-11-02 verification. Replenish or drop. |
| **Rainforest** (already wired) | 100 credits/mo, resets 2026-12-03 | Product/search/reviews/offers | **Configured & healthy** (verified 2026-11-02). Underused relative to Bright Data. |
| **Oxylabs** | Free trial (limited) | Managed Amazon scraper | Trial only; not a standing free source. |
| **Thordata** | Free trial | Amazon spider | Trial only. |

## 4. Open-source GitHub repos (no key / no proxy)

| Repo | ★ | Last push | Key | Anti-bot | Fit |
|---|---|---|---|---|---|
| `omkarcloud/amazon-scraper` | 252 | 2026-02 | No | No | **Best no-key fallback.** Unlimited details/prices/reviews/best-sellers as clean JSON, Flask API (`python run.py`). Use as local enrichment when managed providers are empty. |
| `theonlyanil/amzpy` (AmzPy) | 117 | 2026-02 | No | No | Lightweight product+search; good for quick ASIN lookup. |
| `drawrowfly/amazon-product-api` (amazon-buddy) | 771 | 2022-11 | No | No | Stale selectors; search returns no results. **Avoid.** |
| `scrapehero-code/amazon-review-api` | 63 | older | No | No | Reviews only; basic. |
| `apiguru-app/amazon-scraper-v2` | 226 | 2026-10 | 3 free calls/day, no key | Managed | "Agent-ready" + MCP server; interesting but only 3 calls/day free. |
| `Thordata/how-to-scrape-amazon-product-data-for-free` | 11 | 2026-02 | Thordata key | Managed | Tutorial + SDK; not a library. |
| `data-scrape/best-amazon-scraper` | low | 2026 | n/a | n/a | Sponsored/low signal; skip. |

**Reality check (scrapfly 2026-04 benchmark):** repos without anti-bot handling fail silently on
Amazon search (HTTP 503) and break when selectors drift. Use them as *enrichment of pages we
already fetched*, not as the fetch layer. Our existing Bright Data Web Unlocker fetch + local
parser is more reliable than any of these.

## 5. Browser agents (Browser Use, Skyvern, etc.)

| Tool | License | Strength | Amazon fit |
|---|---|---|---|
| **Browser Use** | MIT | General-purpose LLM-driven browser; 108k★; #1 Odysseys (87.4%) | **Wrong for volume.** LLM tokens per page, fragile, anti-bot still applies. Use only for one-off extraction or form flows. |
| **Skyvern** | AGPL-3.0 | Form-heavy, visual, self-healing | Form-filling (brand registration), not catalog scans. AGPL network clause → local-lane only. |
| **Firecrawl** | (managed + OSS) | DOM pruning → 97.9% token reduction; `/scrape` + `/interact` | Good *extraction* layer on top of HTML we already have; not a fetch bypass. |
| **Crawl4AI** | Apache-2.0 | Open-source, LLM-friendly extraction | Same as Firecrawl; useful for cleaning HTML before NuExtract. |

**Verdict:** agents do not beat a managed scraper on Amazon. Keep Chrome Connect (Profile 6) as the
only sanctioned browser path for any Amazon-adjacent browsing, and never let an agent drive it.

## 6. Hugging Face — datasets & models (offline value only)

| Asset | Type | Value |
|---|---|---|
| `McAuley-Lab/Amazon-Reviews-2023` | Dataset | 571.5M reviews, 48M items, to Sep-2023; rich metadata (images, store, categories, bought-together). **Best offline benchmark/training corpus.** |
| `calmgoose/amazon-product-data-2020` | Dataset | Older product pages (2020); stale prices. |
| `sentence-transformers/amazon-reviews` | Dataset | Reviews for embedding fine-tuning. |
| `amazon/chronos-*` (Amazon) | Models | Time-series forecasting (Chronos/Chronos-Bolt) — useful for **price/demand forecasting** on our own price history, not for live data. |
| `numind/NuExtract` (family) | Model | Small LLM fine-tuned for structured extraction from text/HTML — **directly applicable** to turning Bright Data HTML into our schema. |
| Qwen3 (via HF/Ollama) | Model | Local extraction LLM; Bright Data's published tutorial uses Qwen3 for product extraction. |

**Pattern to adopt (zero new network calls):** fetch HTML with Bright Data (already paid for) →
prune DOM (Firecrawl-style, or our own) → extract with **NuExtract / Qwen3 locally** → validate
against our intel schema. This removes CSS-selector maintenance and reduces reliance on paid
structured endpoints. Fits the local lane and our existing Ollama stack.

## 7. MCP servers relevant to Northstar

| Server | Source | Notes |
|---|---|---|
| **Pangolinfo Amazon Data MCP** (20 tools) | Pangolinfo | Free tier 60 credits/mo; Amazon-specific; agent-native. **Top candidate to wire as a tool.** |
| **apiguru-app/amazon-scraper-v2** MCP | GitHub | 3 free calls/day; broader (20 marketplaces, offers/seller data). |
| **rigwild/mcp-server-amazon** | GitHub | Unofficial; uses Amazon cookies/session — **credential hygiene risk; avoid** (would need Profile 6 cookies). |
| **amzn/selling-partner-api-samples Data Kiosk MCP** | GitHub (Amazon) | Only for our own seller data; needs SP-API creds. |
| **jay-trivedi/amazon_sp_mcp** | GitHub | Same; SP-API based. |
| **Browserless MCP** | Commercial | 1,000 units/mo free; bypasses bot detection; but a second browser path — conflicts with Chrome Connect exclusivity. Skip unless operator carves out. |

## 8. Recommendation (ranked, with effort)

1. **Wire Rainforest harder** (already configured & healthy, 100 credits/mo resetting 2026-12-03)
   before adding anything. It is paid-for capacity we underuse. Effort: small (adapter exists).
2. **Add Pangolinfo free tier** as a secondary provider adapter (REST + optional MCP) for product
   + review enrichment when Bright Data returns empty/partial. Effort: medium (new client +
   contract tests + env var). Value: Amazon-specific MCP + 60 credits/mo forever.
3. **Adopt NuExtract/Qwen3 local extraction** on top of Bright Data HTML to drop CSS-selector
   maintenance and reduce paid structured calls. Effort: medium; fits local lane and existing Ollama.
4. **Evaluate Creators API** only after Northstar holds an Associates account with 3 qualifying
   sales in 30 days. Track as a future gate, not now.
5. **Keep omkarcloud/amazon-scraper as a no-key local fallback** (enrichment only, not fetch).
   Add as an optional adapter behind the same contract; never primary.
6. **Do not adopt** Browser Use/Skyvern for Amazon scanning; do not use rigwild MCP (cookie risk);
   do not chase stale repos (amazon-buddy 2022).

## 9. Blockers / decisions needed from operator

- Standing gate **b (Amazon)**: any actual call to Amazon (including a smoke test of a new
  provider) requires a fresh, explicit operator approval. This report makes **no** live calls.
- If proceeding with Pangolinfo, need: account signup (no card, free) + API key in `.env`
  (non-secret name only: `PANGOLINFO_API_KEY`), and a named approval for one smoke call.
- If proceeding with Creators API, need: Associates account + 3 qualifying sales first.

## 10. Sources

- Glade API — "Amazon Product Advertising API Alternatives in 2026" (Creators API ops list).
- Amazon Associates Central — Creators API docs (affiliate-program.amazon.com/creatorsapi).
- scrapfly.io — "4 Best Amazon Scraper Repos on GitHub (2026)" (AmzPy, amazon-buddy, sushil-rgb).
- Pangolinfo — "Best Free Amazon Scraper APIs in 2026" (60 credits/mo, MCP 20 tools).
- Bright Data blog — "Web Scraping with Qwen3" (local extraction pattern).
- Hugging Face — McAuley-Lab/Amazon-Reviews-2023 (571M reviews).
- scrapfly.io — "Best AI Browser Agents for Automation and Scraping in 2026".
- GitHub topics: amazon-api-data, amazon-scrape-api (apiguru-app, omkarcloud).
- Northstar repo: `.env.example`, `shared/provider-suite.json`, `reports/github_scan_20261104`.
- Northstar state: `00_STATE.json` (Unwrangle 403 quota, Rainforest healthy, ChocoData 0 credits).
