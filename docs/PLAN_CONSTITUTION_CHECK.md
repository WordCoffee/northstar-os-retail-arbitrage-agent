# PLAN CONSTITUTION CHECK — Master Build Plan vs Operating Constitution

Companion to `docs/NORTHSTAROS_MASTER_BUILD_PLAN.md`. Authority order: the
Constitution wins (Plan 1.1.1). Scope of this check: the four items the plan's
P0-T3 names — Owner Test Mode, live provider arming, self-approval, ChromeConnect
scope — plus every other Constitution rule this plan touches.

Legend: COMPATIBLE = no amendment needed. NEEDS-AMENDMENT = a clause or explicit
owner ruling is required before the plan can be executed as written.

| # | Plan item | Constitution ref | Verdict | Note |
|---|---|---|---|---|
| 1 | Owner Test Mode flag, scope, banner (P3-T1) | §3.2, §3.6, §5 | COMPATIBLE | Flag limited to `internal_platform_admin` + non-production; behavior is audited; off = zero change. No guardrail loosened. |
| 2 | Test-mode bypasses: entitlements, quotas, billing/org-lifecycle, RBAC, concept badges (P3-T2) | (no direct rule) | COMPATIBLE | These are product-layer gates, not §3 guardrails. |
| 3 | Test-mode **self-approval** including the `purchase` permission (P3-T2) | §3 (Amazon/purchase actions need fresh explicit approval), §2A | **NEEDS-AMENDMENT** | Ambiguous: does self-approval let the owner satisfy the §3 "explicit approval" for a real purchase without a second actor? Plan P3-T3 says test mode does NOT bypass the rule that a score alone never yields `PURCHASE_READY`, and does NOT bypass spend caps — but self-approval itself is not reconciled with §3. Needs an explicit owner ruling (see ASK OWNER). |
| 4 | Test mode does NOT bypass truth labels, fail-closed providers, frozen files, spend caps, score!=purchase (P3-T3) | §3, §4, 1.1.2/3/4/5 | COMPATIBLE | Mirrors the Constitution exactly. |
| 5 | Demo Dataset toggle, `is_sample` rows isolated (P3-T4) | 1.1.3 truth labels | COMPATIBLE | SAMPLE only when toggle on; never mixed into real aggregates/exports. |
| 6 | Live provider arming with owner-set daily/monthly caps, hard stop, default disarmed (P7-T1) | §3.1, §3.2, §3.4 | COMPATIBLE | Stricter than §3.2 (per-provider cap + auto-disarm). Owner sets caps. |
| 7 | Every live call metered to `usage` with cost + correlation id (P7-T1) | §3.2 reconcile, §4 | COMPATIBLE | Supports envelope reconciliation. |
| 8 | Credential intake: owner creates key in dashboard, pastes into Admin; stored in secret store; never echoed (P7-T2) | §1.1.7, §3, §3.1 | COMPATIBLE | AI never sees/prints secrets; only names referenced. |
| 9 | Default provider posture $5/day each, all disarmed (P7-T1 default) | §3.2 | COMPATIBLE | Safe default; no spend without owner arm. |
| 10 | ChromeConnect scope: owner's own sessions, read-only, human-paced, no CAPTCHA solving, no fingerprint spoofing, no credential entry, honor site terms, pause-all kill switch (P6-T2, P6-T3) | §3, §1.1.7, Plan 1.4 | COMPATIBLE | Explicitly narrower than any §3 boundary; aligns with 1.4 sign-in gate. |
| 11 | ChromeConnect sign-in gate never enters credentials/solves challenges; owner does (Plan 1.4) | §1.1.7, Stop rules 1.6 | COMPATIBLE | |
| 12 | Durable jobs; unregistered job types fail closed; disabled providers raise `ProviderDisabledError` (P6-T1, architecture) | 1.1.4 fail closed | COMPATIBLE | |
| 13 | Frozen files untouched by the plan (Plan 1.1.6) | §3 protected files | COMPATIBLE | P0-T1 left dirty frozen files unstaged. |
| 14 | Data rights register; `INTERNAL_ONLY` excluded from customer tenants; SP-API INTERNAL_ONLY until counsel clears (P4-T3, P10-T7) | (no direct rule; §1.1.2 honesty) | COMPATIBLE | Tighter than Constitution; no conflict. |
| 15 | Freshness: stale observations degrade to UNKNOWN for gates (P4-T4) | 1.1.3, 1.1.4 | COMPATIBLE | |
| 16 | Commits per card; no push/force-push/branch-delete on protected branches (Plan 1.2, 1.1.6) | §3.3 | COMPATIBLE | Plan's git discipline matches §3.3. |
| 17 | Hosted delivery, Postgres, Docker Compose, Caddy, nightly backup + restore drill (P2, P10-T4) | §2A (build everything), §3 | COMPATIBLE | Build work; no live money; secrets stay server-side. |
| 18 | Real auth: seed one `internal_platform_admin` via local CLI prompt; secret never in env/git (P2-T5) | §1.1.7, §3 | COMPATIBLE | |
| 19 | Amazon SP-API / Ads / listing-adjacent rooms are read-only; nothing publishes/posts/auto-edits; all writes need approval (P8C-8E, P9-T2) | §3 (Amazon listing/pricing/purchase) | COMPATIBLE | Stays read-only / approval-gated. |
| 20 | AutothinK tool registry: no tool can purchase, publish, post, or change a live listing (P9-T2) | §3 | COMPATIBLE | |
| 21 | Hosted deployment + browser runner exchanges: runner pulls over authenticated HTTPS, no inbound ports, revocable tokens (P6-T1/T2) | §3.3 (no remote ops without approval) | COMPATIBLE | Outbound pull model; no protected-branch pushes. |

## Conflicts requiring owner input

- **Item 3 — self-approval (P3-T2).** The only NEEDS-AMENDMENT. See ASK OWNER
  block in the P0-T3 report. Safe default applied: self-approval is permitted in
  Owner Test Mode for non-purchase actions only; any real purchase still requires
  a fresh, explicit, named owner approval per §3 (a score or self-approval alone
  never yields `PURCHASE_READY`).

## Ruling

No other conflict found between the Master Build Plan and the Constitution.
Items 1-21 are COMPATIBLE except item 3 (NEEDS-AMENDMENT, default applied
pending owner ruling).