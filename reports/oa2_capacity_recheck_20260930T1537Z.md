# OA-2 — A1 capacity recheck (READ-ONLY)

- **When:** 2026-09-30T15:37Z
- **Mode:** READ-ONLY. No resource created or modified; no Create action; no retries.
- **Question:** current capacity for `VM.Standard.A1.Flex` 1 OCPU/6 GB, image OL9/Arm64, region `us-chicago-1`, compartment `northstar-beta`, candidate ADs AD-1/AD-2/AD-3, no fault domain.

## Result: capacity report UNAVAILABLE

| Check | Finding |
|---|---|
| Oracle Console capacity-report page | **Not present.** `Compute → Overview/Instances/…` has no "Capacity report". Routes `/compute/capacity-reports` and `/compute/capacity` fall back to the Create-instance page. Left-nav has only **Capacity Reservations** (a paid reservation feature, not a report). |
| Console global search "capacity report" | Returns **documentation links only** (Ops Insights / News Reports / Analytics / Actionable Insights); no console tool. |
| Supported OCI capacity-report API (`CreateComputeCapacityReport`) | **Not reachable.** OCI CLI not installed (`oci` not found); no `~/.oci/config`. The API is signed-request/CLI/SDK-only and is not exposed in this console. No credentials were read or used. |
| Per-AD result (AD-1/AD-2/AD-3) | **UNKNOWN** — no report capability available; therefore no exact per-AD capacity result to report. |

> Note: the only A1 capacity signals observed today were **negative** — three create attempts (08:37 AD-1, 08:50 AD-2, 08:55 AD-3) each returned "Out of capacity for shape VM.Standard.A1.Flex". Those were *create attempts*, not a capacity report, and are not treated as a report here.

## Other requested items

- **Timestamp/source of the result:** 2026-09-30T15:37Z, checked live in the Oracle Console (`us-chicago-1`) via the selection-aware Playwright MCP; plus local tool check confirming no OCI CLI.
- **A1 remains visibly Always Free-eligible:** **YES** — read-only check of Compute → Create instance (Image and shape) shows `VM.Standard.A1.Flex` labeled **"Always Free-eligible"**, build "Virtual machine, 1 core OCPU, 6 GB memory". (No fields filled; page left without any Create.)
- **Paid/trial-credit/upgrade indication:** **NONE** observed. No paid SKU, upgrade, or trial-credit use indicated.
- **No changes made:** no Create, no retries, no configuration change. Current network (`ns-beta-vcn` / `ns-beta-public-subnet`) and all cloud resources unchanged.

## Recommendation

Capacity report is unavailable, so this is the "report unavailable" branch: **STOP**.

- **Recommended next manual recheck:** in ~**12–24 hours**, i.e. around **2026-10-01T04:00–08:00Z**, and periodically thereafter (e.g., every 6–12 h). Oracle Always Free A1 capacity is released intermittently and tends to be more available in the region's **off-peak** window (early U.S. Central morning). A repeat console check of the A1 "Always Free-eligible" label + one create attempt (on fresh authorization) remains the only in-console method.
- If a supported capacity-report capability becomes available later (e.g., OCI CLI configured), a per-AD report for `VM.Standard.A1.Flex` can be generated without creating resources.

## Artifacts

- This report: `reports/oa2_capacity_recheck_20260930T1537Z.md`
- `00_STATE.json` history entry appended.

---

```
CARD: OA-2  STATUS: PARTIAL
CHANGED: reports/oa2_capacity_recheck_20260930T1537Z.md; 00_STATE.json
TESTS: console capacity-report page absent; search -> docs only; oci CLI not found; no ~/.oci config; A1 still labeled "Always Free-eligible"; no create/modify
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: manual recheck ~2026-10-01T04:00–08:00Z (or any off-peak), then fresh authorization for one create attempt
BLOCKERS: ASK OWNER — capacity report unavailable; no per-AD capacity result obtainable read-only
```
