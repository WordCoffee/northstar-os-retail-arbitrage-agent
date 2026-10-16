# Production-stack scan — what actually gets NorthstarOS into daily brand use (2026-10-16)

**Operator question:** scan GitHub for AI tools / anything that can *fully fix*
NorthstarOS so the operator and their business partner can start using it for
their brands. REA-style app scans are acceptable if they help.

**Scope of this scan:** the gaps the two existing scans do NOT cover — the ops
layer (backups, monitoring), the in-app media-runner plumbing, the deterministic
image-finishing primitives, and an Amazon-OSS reality check. Companion scans:
`research/ui_production_tooling_scan_20261016/REPORT.md` (code/UI quality) and
`reports/tooling_deep_dive_20261015.md` (AI/creative tooling). Every repo fact
below was read from the GitHub API this session (VERIFIED; rows in
`research/production_stack_scan_20261016/SOURCES.csv`).

---

## 1. The direct answer

**No GitHub tool "fully fixes" NorthstarOS — and it does not need fixing to be
used.** The 2026-10-15 readiness audit already certified the stack
*operationally ready* (security posture all green; one open action: partner
account). What stands between you and daily brand work is **four concrete
wiring/ops items**, not missing software:

1. **Start the stack** — right now the app stack and ComfyUI are DOWN by choice
   (Ollama brain is up). Daily use needs them running.
2. **Partner account** — the invite flow exists; currently **1 user**.
3. **In-app media runner** — the stated next build step (MEDIA_GEN_LIVE).
   ComfyUI's own HTTP API is the reference; **no new dependency is required**.
4. **Ops confidence** — backups (the `deploy/backup.sh` upload leg is a
   placeholder) and monitoring.

Each closure below is verified and license-checked. Adopt only what maps to a
gap; everything else is noise.

## 2. Verified scan (new findings only)

### Ops — for daily confidence

| Tool | License / facts (verified 2026-10-16) | Closes |
|---|---|---|
| **restic** + **rclone** | BSD-2 / 36.6k★ / active · MIT / 60.3k★ / active | The real fix for `deploy/backup.sh`: encrypted, deduped repo + an actual off-machine destination (B2/S3/Drive). The current script encrypts and stops at "ready". |
| **Uptime Kuma** | MIT / 92.6k★ / active | Health monitoring for API/UI/tunnel with alerts — so you hear about downtime before your partner does. |
| **Dozzle** | MIT / 14.6k★ / active | Read-only real-time container logs in the browser; zero config. |
| **GlitchTip** | MIT / **GitLab-hosted** (`gitlab.com/glitchtip/glitchtip-backend`, ~359★; GitHub org is a readme mirror) | Sentry-compatible error tracking (Django+Postgres, 512 MB). Optional — only if you want error history beyond docker logs. |
| **Coolify** | Apache-2.0 / 63k★ / active | Only relevant IF you move off local-first+tunnel to a hosted deploy. Not needed today; the compose + Cloudflare tunnel path already works. |

### The in-app media runner (next build step) — reference, not a library

- **ComfyUI** (installed): GPL-3.0, 137.9k★, pushed today. The runner talks to
  its **HTTP API** (`/prompt`, `/history`, `/view`) plus websocket progress.
  That is a few hundred lines of code against an API you already run — do NOT
  add a client-library dependency. **comfy-cli** (GPL-3.0, 1k★) is a
  convenience for model/node management only.

### Deterministic finishing primitives (the "boring" quality layer)

| Tool | License / facts | Use |
|---|---|---|
| **rembg** | MIT (code) / 25.1k★ / active | White-background main images by code, no diffusion model. |
| **BiRefNet** | MIT / 4.3k★ / active | Higher-quality matting for hero cutouts. |
| **SAM 2** (Meta) | Apache-2.0 / 20k★ | Precise promptable masks for compositing the REAL product. |
| **Real-ESRGAN** | BSD-3 / 37.1k★ / last push 2024-08 (mature) | Upscaling to Amazon zoom sizes. SeedVR2 (already installed) covers most finishing; adopt only if a gap shows. |
| **IOPaint** | Apache-2.0 / 23.3k★ / **ARCHIVED 2025-04-29** | **Do not adopt.** ComfyUI's native inpainting nodes cover this ground. |

### Flags that protect commercial brand work

- **LTX-2** (`Lightricks/LTX-2`, ~9.6k★, active): the **weights are under the
  LTX-2 Community License**, and a HuggingFace discussion states plainly the
  model is "not open source or open weights due to commercial use restrictions".
  The older LTX-Video repo is Apache-2.0 for *code* — weights are a separate
  question. **Before any Mogra/client commercial output: legal review of the
  LTX-2 license.** Same class as the repo's existing FLUX non-commercial
  non-pick. Video generation is a "later" anyway (RAM upgrade first).
- **Model weights ≠ repo license** everywhere: rembg/BiRefNet code is MIT, but
  each weight file has its own terms — check per model before client work.

### Amazon OSS reality check (searched, verified)

GitHub search for Amazon bulksheet tooling returns only 0–2★ hobby scripts
(`amalytix/amazon-advertising-bulksheets`, `anujjare-cell/bulksheet-tool`,
`Sneakahugquick/amazon-sp-bulksheet-builder`, …). **VERIFIED: there is no
adoptable OSS engine for this niche — Northstar's file-only engine (parsers,
change files, round-trip validator, report matching) stands alone.** The
SP-API wrapper (`saleweaver/python-amazon-sp-api`, MIT) is a documented
**non-pick**: the file-only architecture forbids Amazon APIs by design.

## 3. What this means for "fully fix"

| Remaining gap | Closure | Tool needed? |
|---|---|---|
| In-app generation wiring | Build the MEDIA_GEN_LIVE runner against ComfyUI's HTTP API | No new tool |
| Off-machine backups | restic + rclone into `backup.sh` | Yes — both MIT/BSD |
| Monitoring | Uptime Kuma (+ Dozzle; GlitchTip optional) | Yes — MIT |
| Partner access | Invite flow (already built); or tunnel URL for remote | No new tool |
| Deterministic finishing | rembg / BiRefNet / SAM 2 (pick per gap) | Optional |
| Commercial video | Legal review of LTX-2 weights before use | Decision, not a tool |
| Code/UI quality | Companion scan's stack (OpenAPI type sync, Schemathesis, CI gates) | Separate scan |

## 4. REA (scan-other-apps) — honest value ranking

The Packify/DYP RE build already shipped its value (print lane, async lane,
design agent, mockup scenes, public API — see `reports/re_build_design_studio_20261016.md`).
Further app scans, ranked honestly:

1. **Skip Amazon console/A+ assembly flows** — login-gated; the compliant
   guardrails (Chrome Connect) forbid it. Nothing to gain.
2. **Low value:** more competitor UX teardowns (Canva/Packify done; Photoroom/
   Pebblely public pages add little we don't have — IC-Light-class relighting
   plus the studio).
3. **The real constraint is not knowledge of other apps — it is the runner
   wiring + ops items above.** REA time is better spent AFTER the runner is
   live, scanning what real Mogra workflows still lack.

## 5. Suggested order (smallest path to daily use)

1. Start the stack (compose + ComfyUI), create the **partner invite**, confirm
   both sign in. *(This alone = "we can use it".)*
2. Wire the **MEDIA_GEN_LIVE runner** (ComfyUI HTTP API) — the next build step
   already named by the readiness audit.
3. Add **restic+rclone** to `backup.sh`; stand up **Uptime Kuma + Dozzle**.
4. First real Mogra pass: brand kit → product photo (IC-Light) → A+ pack →
   listing change file (file-only) → real Amazon round-trip.
5. Later: finishing primitives as gaps show; LTX-2 only after legal review.

## 6. Gates / honesty

- **Zero product live or paid calls.** This scan used public GitHub/GitLab reads
  (no login, no API key, no paid provider). The product's own posture is
  unchanged (generation still armed only via MEDIA_GEN_LIVE, default off).
- **VERIFIED (this session):** every repo fact, license and push date in §2/§3
  and in `SOURCES.csv` (GitHub API reads; GlitchTip via GitLab pages; LTX-2
  license via GitHub + HuggingFace pages).
- **REPORTED:** LTX-2 commercial-restriction interpretation (a HuggingFace
  discussion thread; treat as a flag for legal review, not a final legal
  opinion).
- **UNKNOWN:** whether any specific weight file's terms block a specific Mogra
  deliverable — per-model review needed; Coolify's fit if you ever move hosted.
- **NOT RUN:** nothing was installed or configured by this scan; the stack was
  already down (operator choice) and was left as found.

**Owner checklist:** (1) start stack + partner invite; (2) approve the runner
wiring as the next build; (3) approve restic/rclone + Uptime Kuma additions;
(4) schedule the LTX-2 license review before any video work.

**Next action:** on your go, wire the MEDIA_GEN_LIVE runner against the local
ComfyUI HTTP API — that is the single build item between here and daily brand
use.
