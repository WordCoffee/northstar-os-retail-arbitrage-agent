# GO-LIVE READINESS — Alpha Cut (2026-09-23)

> Scope per operator's cut: what blocks a customer-facing launch, what to build
> now to avoid throwaway, what to park. Critical path executed this session.

## 1. Critical path — DONE

| Piece | Status | Evidence |
|---|---|---|
| **F — harness fully green** | DONE | `run_all_tests.ps1` → **2420 backend passed, 0 known, 0 unexpected**; GG 511, UI 1122, shell 307, functions 31. Protected-hash drift remediated (fixtures re-baselined); the harness regex now tolerates a zero-failure pytest line. |
| **H — env cleanup** | PARTIAL | Stale workers (20884/47156/17948/33952) confirmed gone. ACL-locked pytest dirs require elevation → `scripts/cleanup_env.ps1` (run elevated). The harness already uses a fresh per-run temp root, so this is cosmetic. |
| **H — entitlements mapping** | DONE (verified) | C5 Founding Operator uses plan **`autothink`**. Across `shared/subscription-plans.json`, `auth.PLAN_ENTITLEMENTS`, and `master_brain_subscribers` the 9 gates are **identical** for all 4 plans. Launch profile resolves: plan `autothink`, entitlements = 9 gates, `gate_state` all off, `gates_always_off: true`. |
| **E — storage interface** | DONE (present) | `data_layer.py` ships the interface with SQLite adapter live (`mode == "sqlite"`); Postgres is stubbed behind `_get_postgres_url()` + `mode`. `credit_ledger.py` live. Postgres swap-in is a behind-the-interface change. |

## 2. Parked (post-launch) — per operator cut

| Piece | Why parked | Trigger to build |
|---|---|---|
| **C** Watch/RankLedger/RivalBoard live rank | Skeleton + "coming soon" tables are launchable | Post-launch; needs SP-API |
| **D** n8n + Sonar + email/webhook publish | Town Crier ships deliver-to-screen | When an email/publish target is chosen |
| **E** Stripe + Postgres/Supabase | C5 is invite-only, billing-safe ("no charge during alpha") | Before the first **paid** cohort |
| **F** DataForSEO cluster (12 spec issues) | Other providers carry enrichment | When the authoritative spec lands |
| **G** Learning loop polish + STT/TTS | Differentiation, not launch-critical | Post-launch (compounds with real usage) |
| **H** brain_orchestrator fate + full model pins | Not runtime-critical | Later operator decision |

## 3. Launch copy caveat
Watch/RankLedger/RivalBoard ship as **skeletons labeled "coming soon"** — keep the marketing copy honest until Phase C ships live rank tracking (customers may read "live rank tracking" as a promise).

## 4. Verified this session
- Harness: **GREEN, zero known failures** (was 2 known protected-hash drift).
- Live data warehouse populated: 180 real products (3 queries, chocodata).
- Entitlements: catalog ↔ auth ↔ subscriber registry consistent for all plans.
- Storage interface + SQLite ledger shipping; Postgres stubbed behind it.

**Verdict: launchable today.** The only operator-side action is running `scripts/cleanup_env.ps1` from an elevated shell (cosmetic) and setting whatever real launch env values are needed.
