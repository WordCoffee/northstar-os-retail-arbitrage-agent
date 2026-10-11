# Design Studio research — assembled 2026-10-11

**Assembly date:** 2026-10-11 (UTC)
**Base:** `research/design_studio_deep_research_20261008/` (research run 2026-10-08 → 2026-10-09)
**Method of this folder:** assembly and update only. No new outbound research was
performed for this folder; the files are the 2026-10-08 deliverables carried
forward verbatim, plus a dated summary that states what changed since, the
label system, and the coverage limits. **No logins, no trials, no API keys, no
paid calls, no provider calls.**

## Files here

| File | Provenance |
| --- | --- |
| `SOURCES.csv` | Copied verbatim from the 2026-10-08 research (325 rows). Every finding in the other files traces to a row here. |
| `COMPETITOR_MATRIX.csv` | Copied verbatim (18 competitors × 20 columns). |
| `WORKFLOWS.md` | Copied verbatim (8 end-to-end teardowns + cross-cutting patterns). |
| `AMAZON_REQUIREMENTS.md` | Copied verbatim (~60 spec rows across 11 surfaces; all date-sensitive). |
| `SELLER_PAIN_POINTS.md` | Copied verbatim (5 themes with explicit sample sizes — anecdote clusters, not trends). |
| `SEO_AD_LOOP.md` | Copied verbatim. |
| `FEASIBILITY.md` | Copied verbatim. |
| `OPPORTUNITIES.md` | Copied verbatim (all concepts PROPOSED). |
| `RULES.md` | Copied verbatim — the evidence rules the research ran under. |
| `RESEARCH_SUMMARY.md` | Written 2026-10-11: the label system, what changed since 2026-10-08, coverage limits, items NOT inspected. |

## Label system (carried from RULES.md)

- **VERIFIED** — directly observed on an official page, official PDF or official
  API documentation at the stated date.
- **REPORTED** — a vendor or third-party claim, not confirmed against an
  official Amazon source.
- **UNKNOWN** — not confirmed. An UNKNOWN is never treated as zero and never
  silently filled in.

## What changed since 2026-10-08 (product decisions that consume this research)

1. **File-only Amazon architecture (owner decisions D32–D35).** NorthstarOS
   does not sign in to Amazon, holds no SP-API / Ads API / OAuth / credentials,
   and never submits anything. The seller downloads files from Amazon, uploads
   them here, and uploads the change file back manually. Research consequences:
   the "creative-level attribution" constraint (search-term reports carry no
   creative identifier) is handled by recording which variant was live in which
   window and letting the operator attribute — the loop never infers it.
2. **Title rules verified by owner capture.** The 75-character limit, banned
   characters, repeated-word limit and promotional-phrase flags were confirmed
   against an owner capture on 2026-10-11 and are enforced as FLAGS in every
   writer (never silent edits).
3. **Item Highlights column stays UNKNOWN.** Amazon has not published the
   flat-file/API column; nothing maps or emits one.
4. **A+ output is an asset pack, not an uploadable module file.** The ASIN
   bulk-upload limit remains UNKNOWN (sources conflict).
5. **Fonts self-hosted** (2026-10-11): the UI makes zero third-party requests;
   this is a build fact, not a research finding.

## Coverage limits (state plainly)

- No logged-in surface was reached in the underlying research. Anything behind
  a login (Amazon Ads console, Manage Your Experiments UI, Helium 10, Pacvue,
  Perpetua, Canva editor) is REPORTED at best.
- Seller Central help pages are JS-gated; content came from Amazon's own
  summaries or official PDFs.
- G2 / Capterra / Trustpilot / Product Hunt returned HTTP 403; no review text
  from those sites was read (one REPORTED exception).
- No YouTube comment text was obtained at all.
- `pacvue.com` returns HTTP 403 to automated fetching — the weakest evidence
  in the set.
- Generation was never run; maturity calls describe documentation, not observed
  reliability.
- The claim that Amazon removed A+ alt-text could not be confirmed from any
  Amazon announcement — an unverified live risk, not fact.
- Ads API v1 (`ads-v1`) report shapes were not fetched; v3 deprecates
  2027-06-30 and must be re-verified before any build depends on it.
- Pricing for Canva, Adobe Firefly, Packify and AdCreative.ai is UNKNOWN
  (dynamic rendering); Helium 10 pricing is third-party REPORTED only and the
  sources disagree.

## Items explicitly NOT inspected (and why)

| Not inspected | Why | Impact |
| --- | --- | --- |
| Amazon Ads console (logged in) | login-gated; owner capture tasks filed in `research/design-studio/OWNER_CAPTURE_TASKS.md` | Ads-console capabilities are REPORTED |
| Manage Your Experiments UI | login-gated; no programmatic API exists (verified by absence from the API indexes) | MYE stays a handoff manifest |
| A+ Content Manager live editor | login-gated | module assembly stays operator work |
| Helium 10 / Pacvue / Perpetua live dashboards | login-gated | their dashboards are REPORTED |
| Reddit at source | reachable only through a search index during the research window | pain-point samples are anecdote clusters |
| Any live Amazon upload / report round-trip | by design: the owner performs it manually | marked NOT RUN with cause in the regression |

No fabricated pricing or statistics appear in this folder. Where a number could
not be read from an official source, the cell says UNKNOWN.
