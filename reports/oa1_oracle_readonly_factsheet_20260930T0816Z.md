# OA-1 — Oracle Console READ-ONLY Fact Sheet

- **When:** 2026-09-30T08:16Z
- **Scope:** OA-1 / DEPLOY-F2 — read-only inspection inside the already signed-in Oracle Console
- **Connection:** selection-aware Playwright MCP only (`tools.playwright.*`); `chrome-t2` remained **disabled**
- **Mode:** READ-ONLY. No create/modify/delete/start/stop/resize/upgrade/subscribe/accept/terms/billing/DNS/IAM action.

---

## 1. Tenancy and account (observed)

| Fact | Value | Where observed |
|---|---|---|
| Tenancy display name | `northstarosllc` | Home top bar "Tenancy:"; Tenancy details |
| Tenancy status | Active | Tenancy details |
| Home region | **ORD** = US Midwest (Chicago) = `us-chicago-1` | Tenancy details → Home region = "ORD"; region menu = "Home region" |
| Current selected region | **US Midwest (Chicago)** (`us-chicago-1`) | Top-nav region menu "active region is US Midwest (Chicago)"; URL `?region=us-chicago-1` |
| Subscribed regions | **only 1** ("You're subscribed to only one region") | Region menu |
| **us-chicago-1 = home AND selected AND only subscribed** | CONFIRMED | region menu + tenancy details |
| Tenancy OCID | **present**; Console → Tenancy details → General Information → OCID; masked prefix `oci1.tenancy.oc1..aaaaaaaahchw5…xyn6q` | Tenancy details (full non-secret value visible in-console; recorded presence/location per policy) |
| Object storage namespace | `axgyk3tcoos1` | Tenancy details |
| Audit retention | 365 days | Tenancy details |
| Amazon S3 compat. designated compartment | `northstarosllc (root)` | Tenancy details |
| Account tier | **Free Tier account — currently in a Free Trial** | horizontal banner on every console page |
| Free Trial banner text | "You are in a Free Trial. When your trial is over, your account is limited to Always Free resources." (links: Upgrade, Learn more) | banner |
| Trial expiration / remaining credits | **UNKNOWN** — not surfaced on Tenancy details, Limits, Cost Analysis, or `/account-management` | attempted |
| Current billed cost | **No costs** for Sep 1–30 2026 ("There are no costs associated with grouping by Service") | Cost Management → Cost Analysis |

> Trial note: the Free Trial banner and "No costs" view are **temporary** and are **NOT** treated as evidence of permanent Always Free capacity.

## 2. Always Free / limit evidence (Limits, Quotas and Usage; region us-chicago-1)

Exact console labels captured. "Service Limit" is the visible limit; "Usage" is current; "Available" = limit − usage.

**Compute**
| Console label | Limit name | Status | Service Limit | Usage | Available |
|---|---|---|---|---|---|
| Cores for Standard.A1 based VM and BM Instances | `standard-a1-core-count` | Active | **Dynamic** | 0 | Dynamic |
| Memory for Standard.A1 based VM and BM Instances | `standard-a1-memory-count` | Active | **Dynamic** | 0 | Dynamic |
| Cores for Standard.E2.1.Micro VM Instances | `standard-e2-micro-core-count` | Active | **2** | 0 | 2 |
| VM.Standard.E2.1.Micro | `vm-standard-e2-1-micro-count` | Deprecated | **2** | 0 | 2 |

**Block Volume**
| Console label | Limit name | Status | Service Limit | Usage | Available |
|---|---|---|---|---|---|
| **Free Tier Volume Quota (GB) in the Region** | `total-free-storage-gb-regional` | Active | **200** | 0 | 200 |
| **Free Backup Counts** | `free-backup-count` | Active | **5** | 0 | 5 |
| Backup Count | `backup-count` | Active | 100,000 | 0 | 100,000 |

**Object Storage** (scope us-chicago-1)
| Console label | Limit name | Status | Service Limit | Usage |
|---|---|---|---|---|
| Bucket count | `bucket-count` | Active | 10,000 | 0 |
| Storage capacity (bytes) | `storage-bytes` | Active | **Unlimited** (paid quota) | 0 |

**Networking**
| Console label | Limit name | Status | Service Limit | Usage |
|---|---|---|---|---|
| Flexible Network Load Balancer Count | `max-nlb-flexible-count` | Active | **1** | 0 |
| Number of SecurityRules allowed per NetworkSecurityGroup | `securityrules-per-networksecuritygroup-count` | Active | 120 | – |
| FlowLogConfig Count | `flow-log-config-count` | Active | 100 | – |
| Max public ip pools per region per tenant | `public-ip-pools-per-region` | Active | 115 | 0 |
| Max byoip ranges per region per tenant | `byoip-ranges-per-region` | Active | 50 | 0 |
| Max compartment limit for IP Inventory per region per tenant | `ip-inventory-compartments` | Active | 20 | – |

VCN limits page shows only the two flow-log/NSG rows for this tenancy; VCN/subnet/IGW counts are applied **per VCN** (console warning) and are N/A while no VCN exists.

**Explicit "Always Free-eligible" badge:** **NOT OBSERVED.** That label is rendered on resource-creation shape pickers (e.g. Create instance), which were not opened per the no-create rule. Above limit labels are the observed evidence; the literal eligibility badge is UNKNOWN.

**Distinguishing observed vs unknown**
- Observed: A1 and E2.1.Micro compute limits with 0 usage; Free Tier Volume Quota 200 GB (0 used); Free Backup Counts 5; flexible NLB count 1; bucket count 10,000; region subscription (single).
- UNKNOWN: the explicit "Always Free-eligible" badge text; the Always Free **object-storage GB** allowance (only "Unlimited" paid quota shown); trial expiration/credits; load-balancer Always-Free GB/Mbps figure.

## 3. Existing environment (read-only, compartment `northstarosllc (root)`)

| Resource | Result |
|---|---|
| Compartments | Only `northstarosllc (root)`, Active, 0 subcompartments (created Sep 30 2026 01:10 UTC) |
| VCNs | **None** ("No items to display") |
| Compute instances | **None** |
| Block volumes | **None** |
| Object-storage buckets | **None** |
| Reserved public IPs | **None** |
| Load balancers | None observed |
| Region subscriptions | Only `us-chicago-1` |

→ No compartment, network, compute, storage, IP, or bucket exists yet. Nothing to reuse; nothing was modified.

## 4. Proposed Northstar deployment packet — **PROPOSAL ONLY (not executed)**

| Item | Proposal | Eligibility evidence | Status |
|---|---|---|---|
| Home/proposed region | `us-chicago-1` (US Midwest (Chicago)) — also the only subscribed region, so Always Free compute **must** be here | region menu "home region"; single subscription | observed |
| Compartment | New dedicated compartment, proposed `northstar-beta` | none exists (only root) | proposal |
| Compute shape | **VM.Standard.A1.Flex** (Arm64) within A1 Dynamic limit; matches existing `deploy/images.lock` linux/arm64 | `standard-a1-core-count`/`-memory` Active, usage 0 | eligibility badge UNKNOWN |
| Compute alternative | VM.Standard.E2.1.Micro (x86) up to 2 cores | `standard-e2-micro-core-count` = 2 | badge UNKNOWN |
| Block storage | Boot + data volume within 200 GB regional free quota; ≤5 free backups | `total-free-storage-gb-regional` = 200 (0 used); `free-backup-count` = 5 | observed limit |
| Object storage | Backups only, within Always Free object-storage allowance (GB) | bucket-count 10,000; GB allowance UNKNOWN | GB allowance UNKNOWN |
| Network | New VCN + 1 subnet; only Caddy publishes **80/443**; api/postgres/worker/scheduler/migrate publish **nothing**; 1 public IP | matches `tests/test_hosted_compose.py`; NLB count 1 (if used) | proposal |
| Hostname/HTTPS | Neutral free hostname (DuckDNS candidate) + Caddy auto-TLS | — | **requires owner approval + login (DEPLOY-F4)** |
| Cost status | **POSSIBLY $0** | current cost $0 (Cost Analysis, Sep 1–30) + 200 GB free-tier quota visible; BUT account in Free Trial and no explicit "Always Free-eligible" badge observed | **not VERIFIED $0** |
| Rollback | Tear down created resources by name/OCID; restore DB via `deploy/backup.sh` snapshot; environment is currently empty so no destructive rollback risk | — | plan only |

**Actions that would each still require explicit owner approval before execution**
1. Create compartment `northstar-beta`.
2. Create VCN / subnet / internet gateway / route table / security lists or NSGs.
3. Create the compute instance (A1 or E2.1.Micro).
4. Create/attach block volume(s); configure backup policy.
5. Reserve/assign a public IP.
6. Create object-storage bucket.
7. Any DNS/hostname step (DuckDNS) and Caddy TLS issuance.
8. Any resource or SKU beyond Always Free, or any upgrade/billing change.

## 5. Confirmation of no changes

Confirmed: no cloud resource created/changed/deleted; no home-region selection or change; no IAM, DNS, or billing change; no upgrade; no trial credits spent; no terms accepted; no external communication; no Amazon action. Only read-only navigation + read-only view filters (Limits Service filter, region menu) were used. No credentials, MFA, sessions, cookies, tokens, recovery, payment, or identity data were inspected. `chrome-t2` stayed disabled.

## 6. Artifacts

- This report: `reports/oa1_oracle_readonly_factsheet_20260930T0816Z.md`
- `00_STATE.json` history entry appended (`oa1_oracle_readonly_factsheet`).
- Console tab left on Oracle home; ChromeConnect durable run `oracle-20260930T003129Z` preserved.

---

```
CARD: OA-1  STATUS: PARTIAL
CHANGED: reports/oa1_oracle_readonly_factsheet_20260930T0816Z.md; 00_STATE.json
TESTS: read-only console reads via Playwright MCP -> tenancy(Active, home ORD), region menu(single subscription), limits(Compute A1 Dynamic/usage0, Micro 2, Block Free Tier Volume Quota 200GB/usage0, Free Backups 5, NLB flexible 1, Object Storage bucket 10000), resources all empty; no create/modify action
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: OA-2 — owner approves the exact free-eligible resource packet (DEPLOY-F3), then provision
BLOCKERS: ASK OWNER — explicit "Always Free-eligible" badge + object-storage GB allowance + trial expiry not observable without a create screen; owner approval still required
```
