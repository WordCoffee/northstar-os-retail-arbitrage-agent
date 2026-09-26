# 28 — Evidence Index

Evidence states: STATICALLY_CONFIRMED (S) / RUNTIME_CONFIRMED (R) / HISTORICALLY_RECORDED (H) / INFERRED (I) / UNKNOWN (K).

## 1. Phase 0 corrections recorded (this session)

| Item | Correction |
|---|---|
| Git record | `git status --short` + `git ls-files docs/northstar-discovery` WERE executed (read-only validation); `git diff`/`git diff --stat`/`git log`/`git add`/`git commit` NOT executed. Corrected in Phase 0 `00` line 15 and `17` §G. |
| Ollama disclosure | R1 executed DURING the Phase 0 audit (2026-09-23): `POST /api/autothink/run` `{provider:"local", tier:"T2"}`, model `northstar-qwen3:rev1`, `elapsed_ms≈10,738`, tokens 134/555. Local Ollama only — no external/cloud/quota consumed. Disclosed in Phase 0 `00`, `04`, `06`, `17` §R1, and `provider-registry.json`. |

## 2. Source-of-truth references for this Phase 1A spec

| Doc | Grounded in (Phase 0) |
|---|---|
| 00 owner decisions | owner directive + Phase 0 R1/R4/R15/R20/R6/R7 |
| 01 target architecture | Phase 0 `01`,`02`,`04`,`06` (module boundaries from existing modules) |
| 02 domain model | Phase 0 `07` (data_layer tables), `08` (four stores), owner `00` §1 |
| 03 product identity/migration | Phase 0 `07`,`08` (source inventory + field mapping) |
| 04 master brain | Phase 0 `08` (gateway/learning/profiles), `04` §8/§9 |
| 05 permissions/modes | Phase 0 `12` (auth/roles/alpha/rate-limit; no modes/impersonation), owner `00` §2 |
| 06 provider/job | Phase 0 `06` (provider registry), `02` (no scheduler), owner `00` §5 |
| 07 usage/billing | Phase 0 `04` §2, `07` (credit_ledger, main.py:1717), owner `00` §3 |
| 08 frontend | Phase 0 `03` (four surfaces), `11` (design), owner `00` §4 |
| 09 design system | Phase 0 `11` (issues) + owner design directive |
| 10 navigation | Phase 0 `03`,`11` (nav duplication, persistent rail) |
| 11–22 service specs | Phase 0 `04` capability matrix + owner service directives |
| 23 API contract | Phase 0 `03` (route inventory) + Phase 0 `02` (bff envelope) |
| 24 event catalog | Phase 0 `08` (no event bus) + `01` module ownership |
| 25 testing/release | Phase 0 `10` (test inventory, network guard, dangerous tests) |
| 26 backlog | this Phase 1A spec + Phase 0 gap register `13` |
| 27 open decisions | Phase 0 `15` + this spec |

## 3. Evidence-state summary for Phase 1A

- All architecture/UX statements are SPECIFICATION (INFERRED from Phase 0 evidence + owner directive) — none implemented.
- Runtime evidence reused: Phase 0 R1 (local Ollama), R2–R7 (backend endpoints) remain the only RUNTIME_CONFIRMED items; they validate the existing backend paths, not any Phase 1A construct.
- No new code, migration, DB change, policy change, provider call, or secret access was performed to produce this Phase 1A package.

## 4. Validation performed (this session, read-only)

- Phase 0 corrections verified: secret scan (none), JSON parse (5/5), internal links (resolve), git statements corrected.
- Phase 1A files created and validated (see acceptance report): JSON parse, link check, Phase 0 intact, no prod/policy/db change.
