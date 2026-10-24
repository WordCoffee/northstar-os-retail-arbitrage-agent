# OA-2 prep — Always Free shape/labels read + corrected approval packet

- **When:** 2026-09-30T08:21Z
- **Scope:** OA-2 prep / DEPLOY-F3 — READ-ONLY
- **Authorization used:** "Open Compute > Create instance only to read the shape list, Always Free-eligible labels, and A1 limits."
- **Discipline:** Did **not** fill any field, did **not** click Create/Upgrade/Select shape, and left the wizard (Cancel) before any create action.

---

## 1. What was read on Compute > Create instance (observed)

Page: `https://cloud.oracle.com/compute/instances/create?region=us-chicago-1`
(Default form state only; nothing entered.)

Placement warning shown:
- "You can create **Ampere A1** compute instances in **any availability domain**."
- "You can create instances using the **VM.Standard.E2.1.Micro** shape in the **sqDB:US-CHICAGO-1-AD-1** availability domain."
- Availability domains listed: AD 1 / AD 2 / AD 3 (`sqDB:US-CHICAGO-1-AD-1/2/3`).

Image default: Oracle Linux 9 (build 2026.09.18-0).

**Shape section (default selection + label):**
- Shape: **VM.Standard.A1.Flex** — label **"Always Free-eligible"**
- Build description: "Virtual machine, 1 core OCPU, 6 GB memory, 1 Gbps network bandwidth"

**Shape browser — Ampere series (read):**
| Shape name | Label | OCPU | Memory (GB) |
|---|---|---|---|
| **VM.Standard.A1.Flex** | **Always Free-eligible** | 1 (80 max) | 6 (512 max) |
| VM.Standard.A2.Flex | — | 1 (78 max) | 6 (946 max) |

**Shape browser — AMD series (read):** `VM.Standard.E5.Flex` (1–126 OCPU, 12–2,098 GB); **no** Always Free label.

**Shape browser — Specialty and previous generation:** showed **"No items to display"** under the default image (Oracle Linux 9); the micro Always Free shape is not offered for this image. (The `VM.Standard.E2.1.Micro` limit of **2 cores, 0 used** was already captured from the Limits page on 2026-09-30T08:16Z.)

Note: the shape browser's "(80 max / 512 max)" is the **flexible paid range**, not the Always Free cap.

## 2. Corrected Always Free compute cap (owner/authoritative)

- **Ampere A1 Always Free = 2 OCPU / 12 GB total** (tenancy-wide). Supersedes the earlier 4 OCPU / 24 GB figure.
- Always Free A1 capacity must exist in the **home region**; here the home region is `us-chicago-1` and it is the only subscribed region.
- The console confirms A1 is **"Always Free-eligible"** and can be created in **any** AD.

## 3. Revised deployment packet — PROPOSAL ONLY (not executed)

| Item | Revised proposal | Evidence | Status |
|---|---|---|---|
| Region | `us-chicago-1` (home + only subscription) | region menu; tenancy details (ORD) | observed |
| Compartment | new `northstar-beta` | only root exists | proposal |
| Compute | **VM.Standard.A1.Flex, 2 OCPU / 12 GB total** (Arm64) — within the Always Free cap; matches `deploy/images.lock` linux/arm64 | shape label "Always Free-eligible"; cap corrected to 2/12 | eligibility label observed |
| Compute alternative | VM.Standard.E2.1.Micro (x86), ≤2 cores (AD-1 only) | limits: `standard-e2-micro-core-count` = 2, usage 0 | limit observed |
| Block storage | boot + data within **200 GB** regional free quota; ≤**5** free backups | `total-free-storage-gb-regional` = 200 (0 used); `free-backup-count` = 5 | observed |
| Object storage | backups only | bucket count 10,000; Always Free GB allowance UNKNOWN | GB UNKNOWN |
| Network | new VCN + 1 subnet; **only Caddy publishes 80/443**; api/postgres/worker/scheduler publish nothing; 1 public IP | `tests/test_hosted_compose.py`; flexible NLB count 1 | proposal |
| Hostname/HTTPS | DuckDNS + Caddy auto-TLS | — | **owner approval + login required (F4)** |
| Cost status | **POSSIBLY $0 → leaning $0 with 2/12 cap**, but **not VERIFIED $0** | A1 labeled "Always Free-eligible"; free-tier 200 GB quota visible; account still in Free Trial | not VERIFIED |
| Rollback | tear down by name/OCID + `deploy/backup.sh` restore; environment currently empty | — | plan only |

**Still requires explicit owner approval (each):** create compartment; VCN/subnet/IGW/security lists; the compute instance; block volume(s)/backup policy; public IP; bucket; DNS/TLS; and any non-Always-Free SKU or upgrade.

## 4. Container memory estimate vs 12 GB

No enforced memory limits exist in `docker-compose.yml` / `docker-compose.hosted.yml` (no `mem_limit`/`deploy.resources`). Values below are **typical RSS estimates**, not measured.

| Container | Base | Estimated RSS | Notes |
|---|---|---|---|
| postgres (`postgres:15-alpine`) | debian/alpine PG 15 | **~150–250 MB** | default `shared_buffers` 128 MB; tiny DB |
| api (`python:3.12-slim` + uvicorn/FastAPI, single worker) | ~120–200 MB | **~120–200 MB** | 1 uvicorn worker; no gunicorn |
| worker (`foundation_worker.py`) | Python loop | **~100–180 MB** | jobs concurrency policy default `max_concurrent=3` |
| scheduler (`foundation_scheduler.py`) | Python loop | **~90–150 MB** | periodic dispatch only |
| **Requested four total** | | **≈ 0.46–0.78 GB** | |
| (caddy reverse proxy, also in stack) | Go static+caddy | ~30–50 MB | publishes 80/443 |
| migrate | Python, ephemeral | transient | exits after migrations |

**Fit:** the four requested containers consume roughly **0.5–0.8 GB of the 12 GB** Always Free A1 memory — leaving **~11+ GB headroom** (and ample CPU within 2 OCPU). This stack fits comfortably. Even adding caddy (~50 MB) and transient migrate, utilization stays well under 1 GB.

Caveats: estimates assume no large concurrent job fan-out and default Postgres settings; if provider data jobs or future services add heavy workers, revisit. Recommend pinning explicit `mem_limit`/reservations before beta if desired.

## 5. Confirmation

No resource created/changed/deleted; no form field filled; no Create/Upgrade/Select shape clicked; no billing/IAM/DNS change; no credentials/MFA/cookies/tokens/payment/identity inspected. Wizard exited via Cancel; console left on Oracle home. `chrome-t2` stayed disabled.

## 6. Artifacts

- This report: `reports/oa2_prep_always_free_packet_20260930T0821Z.md`
- Prior fact sheet: `reports/oa1_oracle_readonly_factsheet_20260930T0816Z.md`
- `00_STATE.json` history entry appended.

---

```
CARD: OA-2  STATUS: PARTIAL
CHANGED: reports/oa2_prep_always_free_packet_20260930T0821Z.md; 00_STATE.json
TESTS: read-only Create-instance shape read -> VM.Standard.A1.Flex labeled "Always Free-eligible" (1..80 OCPU / 6..512 GB flexible; cap corrected to 2 OCPU/12 GB), A2.Flex unlabeled, E5.Flex unlabeled, Specialty tab empty for OL9; container estimate 0.46-0.78 GB of 12 GB; zero create/submit actions
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: OA-2 — await owner approval of corrected 2 OCPU/12 GB packet (DEPLOY-F3), then provision
BLOCKERS: ASK OWNER — explicit approval to provision; confirm 2 OCPU/12 GB cap accepted
```
