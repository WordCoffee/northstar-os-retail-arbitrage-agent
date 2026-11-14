# PPC G4 — AdPilot's primary action now has a probed, persisted contract (2026-11-14)

**Outcome: PPC G4 is met.** The stored contract artefact was stale (generated 2026-11-09, live)
and predated the override that gives AdPilot a *persisted* primary action. Regenerating it
against the live backend proves the action: **POST `/api/v1/foundation/jobs-durable` → 201**,
read back by id → `pass`, `persisted: true`.

## Measured

| item | before | after |
|---|---|---|
| contract artefact | generated `2026-11-09T06:44:25Z`, 29 services, 20 pass / 4 persisted / 3 gaps | generated `2026-11-14T12:01:30Z`, **28 services, 20 pass / 5 persisted / 3 gaps** |
| adpilot primary action | `GET /api/design-studio/amazon-files` → `empty_payload` (`{uploads, note}`) | `POST /api/v1/foundation/jobs-durable` → **201, persisted by id** |
| adpilot `contract` | 0.0 | **100.0** |
| adpilot score / gap | 79.8 / 3.6 | **89.8 / 0.0** |
| scorecard row-level diff vs HEAD | — | **only adpilot changed**, 28 rows either side |
| services ≥ 85 | 22 | **23 of 28** |

Top ranked gap is now **listings 7.2** alone (an honest zero; its product belongs to
ListingForge). AdPilot's weakest dimension is `correct` (60 by the artefact rule), so it is
≥85 but **not at bar on every dimension** — stated, not hidden.

## Two tool defects found and fixed in the same pass

1. **A partial probe overwrote the published artefact.** `python tools/contract_check.py
   --service adpilot` wrote its one-row result over `state/contracts/service_contracts.json`
   (measured this session; recovered by re-running the full live probe). A `--service` probe now
   writes **nothing** unless `--out` is given, and says so in its output
   (`partial_probe_not_written`). A test pins it.
2. **The product-finder override outlived its reason.** It existed only while the registry had
   `actions: []`; `fix-product-finder-wiring` added the finder read, so the override was
   **removed** and the contract now comes from `ty/services.json`. Three stale tests were
   reconciled (29 → 28 services, the override premise, the e2e counts). `test_contract_check.py`
   → **12 passed**, exit 0.

## Honest limits

The contract proves the mounted action and its persisted read-back. It does **not** prove
AdPilot's ad-copy quality — that is the separate `service-path` sample (98.1 over 6, fixture
level) — and the durable job is a campaign **plan**, not a live ad change. No Amazon host was
contacted, no spend, no credential read. The probe writes its own test rows into the dev
database (a durable job per run), which is the persistence under test.

## Environment

The backend died twice mid-session (connection refused; first the verifier's pass, then this
unit's first probe). The stack is now **supervised** by `scripts/dev-start.ps1`, launched
detached through WMI with the media lane off (RAM): backend **21864**, UI **29708**, `/health`
ok. Restarts are recorded in `dev-start.pids(.json)`.
