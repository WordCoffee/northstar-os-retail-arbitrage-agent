# 15 — Evidence Index

## Code (offline research layer)

| Path | What |
|---|---|
| `Northstar_backend/faire_research/__init__.py` | Public API + gate/compliance header |
| `Northstar_backend/faire_research/enums.py` | States/classes (provenance, match, eligibility, brand risk, fee, pack, states, modes) |
| `Northstar_backend/faire_research/economics.py` | TEMPORARY Decimal economics adapter |
| `Northstar_backend/faire_research/matching.py` | Identity match, exact-match safety, pack/case logic |
| `Northstar_backend/faire_research/qualification.py` | Hard disqualifiers, scoring, state machine, compliance |
| `Northstar_backend/faire_research/tests/test_economics.py` | 12 tests |
| `Northstar_backend/faire_research/tests/test_matching_packs.py` | 19 tests |
| `Northstar_backend/faire_research/tests/test_qualification.py` | 14 tests |

## Schemas + docs

`docs/northstar-faire-discovery/` — this package: `00`–`15` markdown and
`faire-discovery-schema.json`, `amazon-match-schema.json`,
`pack-normalization-schema.json`, `opportunity-score-contract.json`,
`research-batch-contract.json`, `risk-register.json`.

## Discovery evidence gathered this session (offline artifacts, not committed as data)

| Artifact | Content |
|---|---|
| `.playwright-mcp/faire-products-batch1.json`, `batch2.json` | 2,703 Faire products (discovery; authenticated reference) |
| `Northstar_backend/data/faire/faire_candidates.csv` | Normalized Faire candidates |
| `Northstar_backend/data/faire/faire_small_candidates.csv` | 978 small-item candidates |
| `Northstar_backend/data/faire/faire_amazon_screened.json` | 60 searched / 24 detailed ASIN screen |
| `Northstar_backend/data/faire/faire_amazon_final.json` | Ranked strict/relaxed passes |
| `data/seller-offer-cache.json` | 247 ASINs (prior run) |
| `data/enriched-offer-cache.json` | 263 ASINs (prior run) |

## Prior-phase grounding

| Path | Relevance |
|---|---|
| `docs/northstar-phase1b/00-implementation-summary.md` | Foundation delivered |
| `docs/northstar-phase1b/15-known-gaps.md` | Gates: economics/jobs/auth/keyword |
| `docs/northstar-phase1b/16-phase1c-recommendation.md` | 1C-01..1C-14 dependency order |
| `docs/northstar-phase1b/13-security-review.md` | Auth shim / security posture |
| `docs/OPERATING_CONSTITUTION.md` | Authority order, compliance |

## Faire policy references (operator-supplied)

- https://www.faire.com/support/articles/31169832450971
- https://www.faire.com/support/articles/32636987402651
- https://www.faire.com/support/articles/360059304192
