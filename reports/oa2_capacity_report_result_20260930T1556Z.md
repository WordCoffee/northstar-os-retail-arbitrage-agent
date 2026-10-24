# OA-2 — A1 capacity report result (READ-ONLY) — NO capacity in any AD

- **When:** 2026-09-30T15:56Z
- **Method:** Oracle Cloud Shell (pre-authenticated OCI CLI), `oci compute compute-capacity-report create` — **read-only**, no resources created/modified.
- **Result:** **NO capacity — `OUT_OF_HOST_CAPACITY` in AD-1, AD-2, and AD-3** for `VM.Standard.A1.Flex` (both 1 OCPU/6 GB and 2 OCPU/12 GB).

## Exact results

| AD | Shape config | availability-status | available-count |
|---|---|---|---|
| `sqDB:US-CHICAGO-1-AD-1` | VM.Standard.A1.Flex 1 OCPU / 6 GB | **OUT_OF_HOST_CAPACITY** | null |
| `sqDB:US-CHICAGO-1-AD-1` | VM.Standard.A1.Flex 2 OCPU / 12 GB | **OUT_OF_HOST_CAPACITY** | null |
| `sqDB:US-CHICAGO-1-AD-2` | VM.Standard.A1.Flex 1 OCPU / 6 GB | **OUT_OF_HOST_CAPACITY** | null |
| `sqDB:US-CHICAGO-1-AD-2` | VM.Standard.A1.Flex 2 OCPU / 12 GB | **OUT_OF_HOST_CAPACITY** | null |
| `sqDB:US-CHICAGO-1-AD-3` | VM.Standard.A1.Flex 1 OCPU / 6 GB | **OUT_OF_HOST_CAPACITY** | null |
| `sqDB:US-CHICAGO-1-AD-3` | VM.Standard.A1.Flex 2 OCPU / 12 GB | **OUT_OF_HOST_CAPACITY** | null |

Also: `fault-domain: null`, `instance-shape: VM.Standard.A1.Flex`, `nvmes: 0`, `baseline-ocpu-utilization: null`.

- **Timestamp/source:** 2026-09-30T15:5xZ, generated live in the Oracle Console → Cloud Shell (`us-chicago-1`, tenancy `northstarosllc`, user `northstarosllc@gmail.com`). Command: `oci compute compute-capacity-report create --compartment-id <tenancy> --availability-domain <AD> --shape-availabilities file:///tmp/s.json` per AD, no fault domain specified.
- **Compartment:** report run at tenancy/`northstar-beta` scope (`us-chicago-1`) as approved.
- **A1 remains visibly Always Free-eligible:** **YES** (`VM.Standard.A1.Flex` = "Always Free-eligible").
- **Paid/trial-credit/upgrade indication:** **NONE**.
- **No Create, no retries, no configuration changes.** Network (`ns-beta-vcn` / `ns-beta-public-subnet`) and all cloud resources unchanged.
- **Cloud Shell** was opened as the read-only vehicle (ephemeral/free/console-provided). No persistent resource created or modified.

## Decision (report shows no capacity → STOP)

Per the standing rule, **STOP** and recommend the next manual recheck.

- **Recommended next recheck:** in ~**12–24 h**, around **2026-10-01T04:00–08:00Z** (region off-peak, early U.S.-Central morning), and periodically thereafter (every ~6–12 h). Re-run the same read-only capacity report (or the console check) then.
- If a future report shows `availability-status` other than `OUT_OF_HOST_CAPACITY` with a non-null `available-count`, request exactly one create attempt in the specific AD named by the report.
- No create attempt is proposed now; all ADs report no capacity.

## Artifacts

- This report: `reports/oa2_capacity_report_result_20260930T1556Z.md`
- `00_STATE.json` history entry appended.

---

```
CARD: OA-2  STATUS: PARTIAL
CHANGED: reports/oa2_capacity_report_result_20260930T1556Z.md; 00_STATE.json
TESTS: Cloud Shell capacity report (read-only) -> AD-1/AD-2/AD-3 ALL OUT_OF_HOST_CAPACITY (1/6 and 2/12), available-count null; no create/modify
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: manual recheck ~2026-10-01T04:00-08:00Z (off-peak) / periodically; re-run report; if capacity appears, request one create attempt
BLOCKERS: ASK OWNER — no A1 host capacity in any us-chicago-1 AD (per official report)
```
