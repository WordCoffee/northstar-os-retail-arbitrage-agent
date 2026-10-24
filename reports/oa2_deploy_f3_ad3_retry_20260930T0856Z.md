# OA-2 / DEPLOY-F3 — AD-3 final capacity retry (FAILED: out of capacity; stopped)

- **When:** 2026-09-30T08:56Z
- **Authorization:** owner — exactly one manual instance-create attempt, **AD-3 only**, immutable config.
- **Result:** **FAILED — `Out of capacity for shape VM.Standard.A1.Flex in availability domain AD-3.`** One attempt; circuit breaker invoked; **no instance; stopped.**

## Pre-create reconfirmations (all passed)

1. Region `us-chicago-1`; compartment `northstar-beta`; shape `VM.Standard.A1.Flex`; **AD-3**; sizing **1 OCPU / 6 GB**; image **Oracle Linux 9** (build 2026.09.18-0); boot volume **50 GB** (custom) — all confirmed on the Review screen.
2. **"Always Free-eligible"** marker visible on the shape.
3. No paid / upgrade / trial-credit indication.
4. Ingress re-verified live (fresh tab, then closed): exactly **TCP 80 + TCP 443**.

## Attempt record

- `ns-beta-api`, VM.Standard.A1.Flex, **AD-3**, OL9, boot 50 GB, VCN `ns-beta-vcn`, subnet `ns-beta-public-subnet`, ephemeral public IPv4, no SSH key. Confirmed the "no SSH access" dialog.
- **Exact error:** `API Error — Out of capacity for shape VM.Standard.A1.Flex in availability domain AD-3. Create the instance in a different availability domain or try again later.`
- Instances list (`northstar-beta`): **No items to display** — nothing created.

## Circuit breaker honored

One attempt only; no retry; no AD-1/AD-2 retry, no "retry later", no fault-domain change, no E2.1.Micro substitution, no paid SKU, no upgrade, no VCN/security-rule change. Stopped and reporting.

## Summary across all three ADs

| AD | Attempt | Result |
|---|---|---|
| AD-1 | earlier approved step | Out of capacity |
| AD-2 | owner-authorized retry | Out of capacity |
| AD-3 | this final retry | Out of capacity |

All three availability domains in `us-chicago-1` currently report A1 host-capacity exhaustion. This is an availability condition, not policy/billing.

## Unchanged state

Compartment `northstar-beta`; VCN `ns-beta-vcn` (`10.0.0.0/16`); IGW `ns-beta-igw`; Default Route Table (`0.0.0.0/0`→IGW); Default Security List (**ingress 80/443 only**); Subnet `ns-beta-public-subnet` (`10.0.1.0/24`, Public Regional). **No compute instance.** No load balancer/bucket/block volume/backup policy/DNS/TLS/IAM/billing change; no paid charge or trial-credit use.

## Artifacts

- This report: `reports/oa2_deploy_f3_ad3_retry_20260930T0856Z.md`
- `00_STATE.json` history entry appended.

---

```
CARD: OA-2 / DEPLOY-F3  STATUS: PARTIAL
CHANGED: reports/oa2_deploy_f3_ad3_retry_20260930T0856Z.md; 00_STATE.json
TESTS: 1 Create attempt AD-3 -> API Error out of capacity (VM.Standard.A1.Flex); instances list (northstar-beta) empty; ingress 80/443 only; no retry
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: await owner authorization — no action taken
BLOCKERS: ASK OWNER — A1 host capacity exhausted across AD-1, AD-2, AD-3 in us-chicago-1
```
