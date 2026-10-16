# REA pattern pass — Canva / Helium 10 / tryholo.ai (2026-10-16)

**Method:** public pages only (no logins, no browser automation this session —
the repo's Chrome-Connect guardrails own that; these fetches are the same
research method the 224-source deep research used). Existing teardown mined:
`research/design-studio/ux-teardown.md` (10 best / 10 to avoid) and
`research/design_studio_deep_research_20261008/COMPETITOR_MATRIX.csv`.

**Coverage limits (honest):**
- **tryholo.ai** — fetched fresh today (VERIFIED): "Paste your website — Holo
  plans, writes, and publishes your ads, socials, emails, and SEO every day,
  on autopilot. **You just tap approve.**" Zero-click seed (URL) + autopilot +
  tap-approve. Also: social proof (4.6/5, 4,268 reviews), "Private and secure /
  your data stays yours", "All systems operational" status line.
- **canva.com** — the homepage served a browser-check interstitial to the
  fetcher (documented limitation; the deep research hit the same class of
  dynamic rendering). Canva patterns below come from the existing documented
  teardown, not a fresh read.
- **Helium 10** — covered by the existing research corpus (dashboard IA, table
  density, alerting); no fresh fetch was needed for the adoptions chosen.

## Adoptions (each mapped to a real surface)

| # | Pattern (source) | Northstar translation | Status |
|---|---|---|---|
| 1 | Zero-click seed: paste a URL (Holo) | **"Start from an ASIN"** on the home; the ASIN seeds a SourceScout lookup | **implemented this pass** |
| 2 | Autopilot with tap-approve (Holo) | The approval queue IS the product's core; empty states now say "plan → approve → export" explicitly | **implemented this pass** (copy) |
| 3 | Task-first home: template grid, blank page never appears (Canva, documented) | "Start something" tiles + Quick start in the studio | done (earlier this session) |
| 4 | Structure chosen before artwork (Pacdora) | Dielines & Print section; print lane picks geometry first | already shipped |
| 5 | Pre-flight that blocks, not a review that catches (Canva Brand Controls) | The compliance pre-flight already blocks export | already shipped |
| 6 | Format-aware safe zones (Adobe Express, documented) | Safe-zone overlays in the studio | already shipped |
| 7 | One workspace, tool rail over uploaded + generated (Firefly, documented) | Compositing surface on every section | already shipped |
| 8 | Status transparency (Holo "All systems operational") | Monitoring room + the honest UNKNOWN language | already shipped |
| 9 | Bulk create from a master + spreadsheet (Canva Bulk Create, documented) | **Declined for now**: ListingForge variant-bulk is a feature, not a copy pass; logged as a Phase-2+ candidate | declined (logged) |
| 10 | Social proof / review counts on marketing surfaces | **Declined**: Northstar is an internal tool for the operator + partner, not a public SaaS — claims would be fabricated | declined |

## What this pass deliberately does NOT do

- No scraping behind logins, no automated browsing of the targets (the
  Chrome-Connect guardrails bound any future scan; a scan session with the
  `chromeconnect_*` tools can deepen the Canva/Helium 10 reads).
- No cosmetic copying: every adoption above maps to an existing real surface
  and changes behaviour or framing the operator actually sees.
