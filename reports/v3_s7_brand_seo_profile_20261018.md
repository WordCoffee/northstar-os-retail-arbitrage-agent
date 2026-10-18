# V3 S7 — Brand SEO Profile (foundation) — Build Report

**Date:** 2026-10-18
**Branch:** `feature/v3-simple-view`
**Commit:** `422bac4`
**Rollback baseline:** tag `v0.2.0-pre-v3-simple-view` (`6d4e847`) — untouched.

---

## 1. What shipped — S7 §5.1 (Brand SEO Profile, versioned)

The principle from the plan: **SEO is a property of the brand, not a listings
feature.** This milestone builds the one canonical object everything else hangs
off — and makes it versioned so history can never be silently rewritten.

| Piece | File | Notes |
|---|---|---|
| Schema | `Northstar_backend/seo_schema.py` | `brand_seo_profiles` (identity + `current_version` pointer) and **immutable** `brand_seo_profile_versions`. Additive; one source of truth shared by the DDL and the offline tests. |
| Store | `Northstar_backend/data_layer.py` (`SeoProfilesDB`, `SeoContainer`) | create / get (with current body + version count) / list / **append version** / list versions / get version. Tenant-scoped on every read and write. |
| Body rule | `Northstar_backend/seo_profile.py` (`normalize_body`) | A body is a JSON object; known sections must have the right container shape; **unknown keys are preserved, never dropped or coerced**; nothing is invented for the operator. |
| Service | `Northstar_backend/seo_router.py` (`/api/seo/*`) | `GET/POST /profiles`, `GET /profiles/{id}`, `GET/POST /profiles/{id}/versions`, `GET /profiles/{id}/versions/{v}`. Registered in `main.py` behind its own import guard (an SEO fault can never disable the rest of the app). |
| Shell hook | `Northstar_backend/chat_tools.py` (`seo_profile`, Grow focus) | Surfaces the current profile — or the account's profile list — as an **AG-UI card**, so S7 is reachable from the chat-first shell. Read-only; never invents a profile. |

### Honesty / safety properties
- **Append-only versions:** editing a profile appends a version and repoints
  `current_version`. Old versions stay readable → rollback is always possible.
- **No fabrication:** a missing profile/section is reported as missing.
- **Tenant-scoped:** a profile owned by another account returns 404, never a leak.
- **No live action:** local SQLite only; arms no live/paid action.

---

## 2. Verification (real runs)

| Suite | Command | Result |
|---|---|---|
| SEO profiles | `pytest test_seo_profiles.py -q` | **17 passed** |
| Combined chat/shell/seo | `pytest test_seo_profiles test_shell_modes test_chat_tools test_chat_core test_chat_fork test_tool_gateway test_voicestudio_adapter -q` | **102 passed** |
| Router registration | `python -c "import seo_router"` | 6 routes mounted |
| Python compile | `py_compile` on all touched modules | OK |

The SEO tests cover body validation, create-at-v1, duplicate-brand rejection,
append-only/immutable versioning, tenant scoping on every path, the router
(create/get/version/list + 404/400), and the Grow-focus tool card.

---

## 3. Guardrails honored

- No credential value read, printed, or committed.
- No real-money or live action.
- No push to a protected branch (work stays on `feature/v3-simple-view`).
- Only authored files staged; pre-existing runtime dirt untouched.
- gitleaks pre-commit hook: "no leaks found".

---

## 4. Next (S7 continued)

- **§5.2** Listing revisions — newest revision is the SEO beneficiary; prior
  revisions archived read-only; additive linkage to `ds_listing_records`.
- **§5.3** Cross-service hooks — ListingForge / Creative Studio / AdPilot /
  SocialPulse / SourceScout scoring against the profile.
- **§5.4** Measurement + learning — SQP / search-term imports; embeddings drift;
  operator-approved profile updates; no rank-change claims.
- **S5 remainder:** plan/DAG visualiser, sandbox runner panel, artifact browser.
- **S8:** curated corpus + continuous learning.
