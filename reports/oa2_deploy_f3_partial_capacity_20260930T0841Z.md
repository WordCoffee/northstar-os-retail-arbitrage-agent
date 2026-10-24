# OA-2 / DEPLOY-F3 — Limited-scope provisioning (PARTIAL: network built, instance blocked by host capacity)

- **When:** 2026-09-30T08:41Z
- **Approval:** owner, limited scope, home region `us-chicago-1` only
- **Result:** Compartment + VCN + IGW + route + security list + public subnet **CREATED**; **compute instance NOT created** — `Out of capacity for shape VM.Standard.A1.Flex in availability domain AD-1`.
- **Circuit breaker:** stopped, persisted success, recorded failure. **No auto-retry.**

## Created resources (all in `northstar-beta`, region `us-chicago-1`)

| Resource | Name | State | OCID | Notes |
|---|---|---|---|---|
| Compartment | `northstar-beta` | Active | present (Tenancy→Compartments; masked `…ocid1.compartment.oc1..aaaaaaaagocg…`) | child of root; root now shows 1 subcompartment |
| VCN | `ns-beta-vcn` | Available | `ocid1.vcn.oc1.us-chicago-1.amaaaaaaqrhdy6ya6jbhoyuhylyojsa77jc6puqvtxjs4fwi3vbwxjvyqlpq` | IPv4 `10.0.0.0/16`; DNS `nsbetavcn.oraclevcn.com` |
| Internet Gateway | `ns-beta-igw` | Available | present (Gateways page) | created 08:27:34 UTC |
| Route Table | `Default Route Table for ns-beta-vcn` | Available | `ocid1.routetable.oc1.us-chicago-1.aaaaaaaay7n45ixv6nx2vad4pfwui376bzem66chewzednbhmqfqiahhzwpq` | 1 rule: `0.0.0.0/0` → Internet Gateway `ns-beta-igw` (Static) |
| Security List | `Default Security List for ns-beta-vcn` | Available | `ocid1.securitylist.oc1.us-chicago-1.aaaaaaaa66lessigist7ajzunku3nmuggqfcwt357iyg7tukdghampa4hdka` | **Ingress = TCP 80 + TCP 443 only** (SSH 22 + default ICMP rules removed); Egress = 0.0.0.0/0 all (default outbound) |
| Subnet | `ns-beta-public-subnet` | Available | present (Subnets page) | `10.0.1.0/24`, **Public (Regional)**, default route table + default security list |
| Compute instance | `ns-beta-api` (attempted) | **NOT CREATED** | — | API Error: out of capacity (see below) |

**No additional block volumes; no backup policy; no load balancer; no SSH exposure; one ephemeral public IPv4 would only exist on the (uncreated) instance.**

## Failure record (scrubbed)

- **Action:** Create compute instance `ns-beta-api` — VM.Standard.A1.Flex, 1 OCPU / 6 GB, Oracle Linux 9, AD-1, boot 50 GB, subnet `ns-beta-public-subnet`, ephemeral public IPv4, no SSH key.
- **Pre-create reconfirmations (all passed):** region = US Midwest (Chicago) `us-chicago-1`; shape visibly **"Always Free-eligible"**; allocation **1 OCPU / 6 GB** (≤ Always Free 2/12); no paid charge / trial-credit / upgrade / non-Always-Free indication.
- **Error observed:** `API Error — Out of capacity for shape VM.Standard.A1.Flex in availability domain AD-1. Create the instance in a different availability domain or try again later.` (two attempts, same failure).
- **Interpretation:** transient Always Free A1 host-capacity exhaustion in AD-1. Not a billing/trial/upgrade issue.
- **No retry performed** (circuit breaker).

## Cost / eligibility status

- Nothing created incurs a charge: compartment, VCN, IGW, route table, security list, subnet are free; the A1 instance was never created.
- Cost Analysis previously showed no costs. **Status: POSSIBLY $0 → the created network is $0; compute unprovisioned.**

## Observed console evidence (this session)

- Shape browser: `VM.Standard.A1.Flex` labeled **"Always Free-eligible"** (`1 (80 max) OCPU / 6 (512 max) GB` flexible).
- `standard-a1-core-count` / `-memory` limits Active, usage 0; `E2.1.Micro` = 2 cores; Free Tier Volume Quota = 200 GB (0 used); Free Backups = 5; flexible NLB = 1.
- Security list after edit: Ingress rows = `0.0.0.0/0 TCP 80` (HTTP), `0.0.0.0/0 TCP 443` (HTTPS) only.

## Actions still requiring explicit owner approval

1. **Retry / relocate the compute instance** — recommended next step: retry `VM.Standard.A1.Flex 1 OCPU/6 GB` in **AD-2 or AD-3** (A1 is creatable in any AD), or retry AD-1 later. Needs owner go-ahead (circuit breaker).
2. TLS/hostname (DuckDNS/Caddy) — **out of scope** of this approval; not started.
3. Application container deployment — **not started** (owner: "do not deploy application containers yet").
4. Any non-Always-Free SKU or upgrade.

## Confirmation

No paid charge, trial-credit use, account upgrade, DNS/IAM/billing change, or non-Always-Free resource was created. No SSH exposure. No credentials/MFA/cookies/tokens/payment/identity inspected. `chrome-t2` stayed disabled; only the selection-aware Playwright MCP was used.

## Artifacts

- This report: `reports/oa2_deploy_f3_partial_capacity_20260930T0841Z.md`
- `00_STATE.json` history entry appended.

---

```
CARD: OA-2 / DEPLOY-F3  STATUS: PARTIAL
CHANGED: reports/oa2_deploy_f3_partial_capacity_20260930T0841Z.md; 00_STATE.json
TESTS: created northstar-beta compartment + ns-beta-vcn + ns-beta-igw + route 0.0.0.0/0->IGW + security list ingress 80/443 only + ns-beta-public-subnet; instance create -> API Error out of capacity AD-1 (no auto-retry)
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: retry VM.Standard.A1.Flex 1 OCPU/6 GB in AD-2/AD-3 (or AD-1 later) on owner go-ahead; then stop
BLOCKERS: ASK OWNER — A1 host capacity exhausted in AD-1; authorize retry in another AD or later
```
