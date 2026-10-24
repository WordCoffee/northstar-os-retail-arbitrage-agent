# Warehouse-Club → Amazon Resell Research — Report (2026-09-30)

**Mode:** browser-driven, research only (Playwright/ChromeConnect, no-account profile). No sign-in, accounts, carts, forms, contacts, payments, purchases, listings, ungating, paid tools, or CAPTCHA bypass. Kirkland excluded. Faire remains banned as a supplier.

## Outcome
All 8 goals attempted; **data collection completed only where public pages rendered**:

| Club | Public extraction | Leads |
|---|---|---|
| Sam's Club | WORKED (public search tiles) | **243 unique rows** (189 DISCOVERY_LEAD / 54 REJECTED) |
| Costco | BLOCKED (grid did not render) | 0 |
| BJ's | BLOCKED (grid did not render) | 0 |
| Amazon screening | INCOMPLETE (needs sign-in/anti-bot) | 0 |
| YouTube | WORKED (11 club videos; 2 transcripts read this pass) | — |

## Files produced
- `data/club_sourcing/club_product_universe.csv` (+ `.json`) — 243 rows, full required schema (many UNKNOWN by rule).
- `data/club_sourcing/club_rejections.csv` — 54.
- `data/club_sourcing/club_exact_match_reviews.csv` — headers (0 completed).
- `data/club_sourcing/club_youtube_transcripts.csv`.
- `docs/club-sourcing-research-2026-09-30/` — `club_goal1_sourcing_playbook.md`, `club_goal1_youtube_transcripts.md`, `club_goal2_costco_universe.csv`, `club_goal3_sams_universe.csv`, `club_goal4_bjs_universe.csv`, `club_methodology.md`, `club_northstar_backlog.md`, `club_final_report.md`.

## Dataset highlights (Sam's)
Real public titles/prices captured, e.g.: `Sharpie Accent Highlighters, 24 Pack — $10.28`; `BIC 4-Color Retractable Ball Point Pens, 7-Count — $9.98`; `Post-it Super Sticky Pop-up Notes, 16 Pack — $15.36`; `Paper Mate Flair Felt Tip Pens, 17 Count — $16.98`; `Swingline Commercial Desk Stapler Value Pack — $9.98`. Private-label (Member's Mark) and commodity paper rows were **REJECTED**.

## Why the targets were not met (honest)
The brief's targets (Costco ≥250, Sam's ≥250, BJ's ≥150, 300 screens, 75 exact reviews, 30 videos/15 transcripts) require product grids and Amazon seller data that **public, no-account pages do not expose** in this environment. Costco/BJ's grids did not render; Amazon seller/offer data needs sign-in. Per the stop condition, a **public-access limitation is recorded for each unfinished task** (Costco, BJ's, Amazon screening, exact-identity reviews).

## Integrity
No candidate labeled BUY/APPROVED/SAFE/UNGATED/PROFITABLE. Unknowns preserved. No fabricated UPC/ASIN/price/fee/permission. No external action taken.

```
CARD: CLUB-SOURCING-RESEARCH  STATUS: PARTIAL (public-access limits recorded)
CHANGED: data/club_sourcing/* (4 csv/json); docs/club-sourcing-research-2026-09-30/* (8); reports/club_sourcing_research_20260930.md; 00_STATE.json
TESTS: browser extraction — Sam's 243 rows (189 leads/54 rejected); Costco 0 (blocked); BJ's 0 (blocked); Amazon 0 (incomplete); YouTube 11 discovered/2 transcripts
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: owner-only — UPC verification, Amazon seller screening (authorized method), club purchases on approval
BLOCKERS: ASK OWNER — Costco/BJ's grids and Amazon seller data are not publicly extractable; targets unreachable without sign-in/authorized access
```
