# 04 — API Contracts Implemented

Base path: **`/api/v1/foundation`** (versioned, additive). **32 routes.**

Naming decision: namespaced under `/api/v1/foundation/*` (not bare `/api/v1/*`) to avoid
collisions with the existing live endpoints (`/api/v1/auth/*`, `/api/v1/models`,
`/api/v1/credits/me`, `/api/v1/catalog/*`, etc.). See `15-known-gaps.md` §Deviations.

## Endpoints

### Context & mode
| Method | Path | Auth (perm) | Notes |
|---|---|---|---|
| GET | `/me` | view (implicit) | user context, orgs, role, env, view_context, permissions |
| GET | `/roles` | — | role → permission matrix |
| GET | `/environment` | — | environment / view_context / is_sandbox / is_preview / writes_allowed |

### Organizations
| Method | Path | Perm |
|---|---|---|
| GET | `/organizations` | view |
| POST | `/organizations` | manage_org |
| GET | `/organizations/{org_id}/memberships` | manage_team |

### Customer preview
| Method | Path | Perm |
|---|---|---|
| POST | `/preview/start` | preview |
| POST | `/preview/end` | preview |
| GET | `/preview/active` | — |

### Marketplaces
| Method | Path | Perm |
|---|---|---|
| GET | `/marketplaces` | view |

### Products & identity
| Method | Path | Perm |
|---|---|---|
| GET | `/products` | view |
| GET | `/products/{product_id}` | view |
| POST | `/identity/submit` | draft |
| GET | `/identity/candidates` | view |
| GET | `/identity/conflicts` | view |

### Observations
| Method | Path | Perm |
|---|---|---|
| POST | `/observations` | draft |
| GET | `/products/{product_id}/observations` | view |

### Providers
| Method | Path | Perm |
|---|---|---|
| GET | `/providers` | view |
| GET | `/providers/{provider_key}` | view |

### Jobs
| Method | Path | Perm |
|---|---|---|
| POST | `/jobs` | request_refresh |
| GET | `/jobs/{job_request_id}` | view |
| GET | `/jobs/runs/{run_id}` | view |
| POST | `/jobs/runs/{run_id}/cancel` | request_refresh |

### Usage
| Method | Path | Perm |
|---|---|---|
| GET | `/usage/summary` | view |
| GET | `/usage/events` | view |

### Approvals
| Method | Path | Perm |
|---|---|---|
| GET | `/approvals` | view |
| POST | `/approvals` | draft |
| POST | `/approvals/{id}/decide` | approve |
| POST | `/approvals/{id}/cancel` | approve |

### Audit
| Method | Path | Perm |
|---|---|---|
| GET | `/audit` | view_audit |

### UI preferences
| Method | Path | Perm |
|---|---|---|
| GET | `/ui/preferences/{key}` | view |
| PUT | `/ui/preferences/{key}` | view |

## Contract conventions

- Typed request/response schemas (pydantic).
- Stable error envelope: `{ detail: { code, message, details } }`.
- Pagination: `limit`/`offset` (list limits capped).
- Explicit provenance in product/observation responses (`meta`).
- Null-first responses (unknown → `null`, never `0`).
- `X-Request-Id` echoed; no GET triggers provider calls or writes.

## Live verification

Verified over HTTP against a local standalone foundation app (`uvicorn` on a spare port,
started only for verification and then stopped): `/environment`, `/roles`, `/me`,
`/providers` (403 without auth), `/usage/summary`, and an authorized `POST /identity/submit`
(created a product) plus a viewer `403`. No external provider was contacted.