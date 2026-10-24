# OA-2 — Capacity-report command execution attempt (READ-ONLY) — could not execute

- **When:** 2026-09-30T15:48Z
- **Requested:** run the provided `oci compute compute-capacity-report create` script to check A1 capacity in `us-chicago-1`, AD-1/AD-2/AD-3.
- **Outcome:** **NOT EXECUTED — no read-only capacity-report capability was usable from this environment. STOP.**

## What was attempted

1. **Local OCI CLI (the pasted script):** not runnable.
   - `oci` **not found** on PATH or common install paths; **no `~/.oci/config`**. Shell is PowerShell (Windows); no OCI CLI available. The pasted bash script cannot run as-is.
2. **Oracle Console capacity-report UI:** **does not exist.**
   - Compute left-nav has only *Capacity Reservations* (paid reservation feature). Routes `/compute/capacity-reports` and `/compute/capacity` redirect to Create-instance. Console search "capacity report" returns documentation links only.
3. **Oracle Cloud Shell** (pre-authenticated OCI CLI — the intended vehicle for the pasted command): **opened but the terminal does not render in this automated browser.**
   - The Cloud Shell panel loaded (toolbar: `Network: Public`, `Cloud Shell session region: us-chicago-1`), but the terminal body stayed **blank**; no `xterm`/canvas/textarea existed in the frame DOM after ~60 s. Input/output could not be driven or read.
   - Cloud Shell was opened solely as the read-only vehicle (ephemeral, free, console-provided) and then **closed**. **No persistent Oracle resource was created or modified.**

## Result

- **Capacity report available: NO** (from this environment).
- **Per-AD capacity result (AD-1/AD-2/AD-3): UNKNOWN** — nothing to report.
- **A1 remains visibly Always Free-eligible: YES** (read-only label check earlier this session; shape page shows `VM.Standard.A1.Flex` = "Always Free-eligible").
- **Paid/trial-credit/upgrade indication: NONE.**
- **No create/modify actions, no retries, no configuration changes.** Network (`ns-beta-vcn` / `ns-beta-public-subnet`) and all cloud resources unchanged.

## How to obtain the report (recommended)

Run the provided command **interactively** in Cloud Shell (a human session renders the terminal normally), after opening Cloud Shell from the Developer-tools (`>_`) menu. It is pre-authenticated as `northstarosllc@gmail.com` and read-only:

```bash
T=$(oci iam compartment list --include-root --compartment-id-in-subtree false --query 'data[0]."compartment-id"' --raw-output 2>/dev/null); [ -z "$T" ] && T=$OCI_TENANCY
cat > shape.json <<'EOF'
[{"instance-shape":"VM.Standard.A1.Flex","instance-shape-config":{"ocpus":2,"memory-in-gbs":12}}]
EOF
for AD in $(oci iam availability-domain list --compartment-id "$T" --query 'data[*].name' --raw-output | tr -d '[]", '); do
  echo "== $AD"
  oci compute compute-capacity-report create --compartment-id "$T" --availability-domain "$AD" \
    --shape-availabilities file://shape.json \
    --query 'data."shape-availabilities"[*].{Status:"availability-status",Available:"available-count"}' --output table
done
```

Note: the command as pasted reports a **2 OCPU / 12 GB** config; the approved instance is **1 OCPU / 6 GB**. For the approved size, use `{"ocpus":1,"memory-in-gbs":6}` in `shape.json`.

## Recommendation (report unavailable branch → STOP)

- **Next manual recheck:** in ~**12–24 h**, around **2026-10-01T04:00–08:00Z** (region off-peak), and periodically thereafter (every ~6–12 h). Repeating the console check of the A1 "Always Free-eligible" label plus a single create attempt (on fresh one-attempt authorization) remains the only in-console method accessible here.
- Alternatively, the owner may run the Cloud Shell command above and paste the per-AD table; if it shows capacity, authorize exactly one create attempt in the named AD.

## Artifacts

- This report: `reports/oa2_capacity_report_exec_20260930T1548Z.md`
- `00_STATE.json` history entry appended.

---

```
CARD: OA-2  STATUS: PARTIAL
CHANGED: reports/oa2_capacity_report_exec_20260930T1548Z.md; 00_STATE.json
TESTS: local oci CLI absent (no config); console capacity-report UI absent; Cloud Shell opened but terminal did not render (blank, no xterm DOM) -> report NOT obtained; no create/modify
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: owner runs Cloud Shell command (per-AD table) OR manual recheck ~2026-10-01T04:00-08:00Z, then fresh one-attempt authorization if capacity appears
BLOCKERS: ASK OWNER — no usable read-only capacity-report capability in this environment
```
