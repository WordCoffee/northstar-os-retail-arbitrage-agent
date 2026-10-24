# OA-2 / DEPLOY-F3 — AD-2 capacity retry (FAILED: out of capacity; stopped)

- **When:** 2026-09-30T08:51Z
- **Authorization:** owner — exactly one manual retry, AD-2 only, region `us-chicago-1`, compartment `northstar-beta`, existing network only, A1.Flex 1 OCPU/6 GB, OL9/Arm64, boot 50 GB, ephemeral public IPv4, no SSH, ingress 80/443 only.
- **Result:** **FAILED — `Out of capacity for shape VM.Standard.A1.Flex in availability domain AD-2.`** One Create attempt made; circuit breaker invoked; **no instance created; stopped**.

## Pre-create confirmations (all passed)

1. Region `us-chicago-1` (US Midwest (Chicago)) and compartment `northstar-beta` — confirmed.
2. `VM.Standard.A1.Flex` — visibly **"Always Free-eligible"** on the Image-and-shape step.
3. Sizing **1 OCPU / 6 GB**, boot volume **50 GB** (custom), no paid / trial-credit / upgrade indication.
4. Ingress re-verified live before Create (**fresh tab**, then closed): exactly **TCP 80 + TCP 443**, nothing else.

## Attempt record

- Instance `ns-beta-api`, shape `VM.Standard.A1.Flex`, **AD-2**, Oracle Linux 9, boot 50 GB, subnet `ns-beta-public-subnet`, VCN `ns-beta-vcn`, ephemeral public IPv4, no SSH key.
- Confirmed the "no SSH access" dialog ("Yes, create instance anyway").
- **Exact error:** `API Error — Out of capacity for shape VM.Standard.A1.Flex in availability domain AD-2. Create the instance in a different availability domain or try again later.`
- Instances list (compartment `northstar-beta`): **No items to display** — nothing was created.

## Circuit breaker honored

- Exactly **one** Create attempt in AD-2.
- **No** retry, **no** AD-3, **no** AD-1 retry, **no** substitution (E2.1.Micro or any paid/non-Always-Free shape not attempted).
- Stopped and reporting; awaiting next authorization.

## Unchanged state (from the prior approved step)

- Compartment `northstar-beta`; VCN `ns-beta-vcn` (`10.0.0.0/16`); IGW `ns-beta-igw`; Default Route Table (`0.0.0.0/0`→IGW); Default Security List (**ingress 80/443 only**); Subnet `ns-beta-public-subnet` (`10.0.1.0/24`, Public Regional). **No compute instance.**
- No load balancer, bucket, block volume, backup policy, DNS/Caddy/TLS, IAM, or billing change. No paid charge or trial-credit use.

## Observation for the owner

Both AD-1 (previous) and AD-2 (this attempt) report A1 host-capacity exhaustion in `us-chicago-1`. This is an availability condition, not a policy/billing issue. Options (all require fresh owner authorization): retry later, or try AD-3, or (only with new approval) a different Always-Free-eligible shape. No automatic action taken.

## Artifacts

- This report: `reports/oa2_deploy_f3_ad2_retry_20260930T0851Z.md`
- Prior: `reports/oa2_deploy_f3_partial_capacity_20260930T0841Z.md`
- `00_STATE.json` history entry appended.

---

```
CARD: OA-2 / DEPLOY-F3  STATUS: PARTIAL
CHANGED: reports/oa2_deploy_f3_ad2_retry_20260930T0851Z.md; 00_STATE.json
TESTS: 1 Create attempt AD-2 -> API Error out of capacity (VM.Standard.A1.Flex); instances list (northstar-beta) empty; ingress re-verified 80/443 only; no retry
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: await owner authorization (retry later / AD-3 / other) — no action taken
BLOCKERS: ASK OWNER — A1 host capacity exhausted in AD-1 and AD-2 in us-chicago-1
```
