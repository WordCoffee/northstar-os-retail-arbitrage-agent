# Lightpanda Install — Pinned Release, Verified, Smoke-Tested (pre-gateway stop point)

- **Date:** 2026-10-11 · **Owner:** T2 Holdings LLC · **Status:** install complete per the conditional approval; **REPORTING BEFORE GATEWAY BUILD (owner stop point honored)**.
- **Security scan state (standing line):** **0 new finding(s), 8 known-active (baseline), 231 allowlisted.**

## 1. Chosen version — stated exactly, with why

**Lightpanda 1.0.0 (tag `1.0.0`, released 2026-10-02).**

Why: it is the **newest NUMBERED release** on the official release channel. `nightly`/`latest` were rejected — and the rejection is concrete, not theoretical: both tags point to digest `sha256:1a613c51…` that had been **re-updated that same day (2026-10-11)**, i.e. a moving target that defeats pinning and checksum verification exactly as the owner described. Numbered releases are immutable artifacts; 1.0.0 was the correct pin.

## 2. Checksum — two independent sources, both agreeing

| Layer | Value (SHA-256) | Source A | Source B |
|---|---|---|---|
| **Image (multi-platform digest / OCI image index) — THE PIN** | `sha256:5b84708cb3d9bef841aba4a4cd299f4de0609ac1bd7d4c6fbfcbf168d56b685e` | Docker Hub API (tag `1.0.0` digest) | `docker buildx imagetools inspect lightpanda/browser:1.0.0` |
| linux/amd64 manifest | `sha256:16b668ba75fdf3f9b215a0550f2840a0e76b905c645d99a23751dcd40a65688a` | buildx inspect | — |
| linux/arm64 manifest | `sha256:dddeeccaea193724896a8c7b18a6630c66de18821518179a33060b0aa189090c` | buildx inspect | — |
| Release assets (GitHub API digests, for the record) | x86_64-linux `aa5a4b8ed53d1e38b3c73f5b2647d0a84a82e6744557f45f9a9c85858aa031c3` · aarch64-linux `69791924bcee43b13b224af4c845622c5fe66fdbc1b8143bfaa39ca8f85244f5` · x86_64-macos `e5102996…` · aarch64-macos `95544005…` · amd64.deb `718ab546…` · arm64.deb `71949a4a…` | GitHub releases API | — |

`docker pull lightpanda/browser@sha256:5b84708c…b685e` returned `Digest: sha256:5b84708c…b685e` — Docker itself re-confirmed the content-addressed pin at pull time. **Pinned by multi-platform digest, never by tag** (amd64 dev + arm64 prod resolve from the same index).

## 3. Platform path (Windows dev) + scope compliance

- Official binaries are macOS/Linux; **Windows dev uses Docker** with the same pinned digest the Mac/ARM64 prod will use. Their official image is **glibc-based (Debian)** — no Alpine wrapper, per the owner's note.
- **Scope respected:** the approval covered downloading and running *that one pinned release, nothing else.* Evidence: no other images pulled (all other local images predate this install); the binary/container lives outside the repo (Docker store) and **nothing binary was committed**; **no live-site fetches** — first runs were against a local test page only.

## 4. Hardening — as configured AND verified in the running container

| Control | Configured | Verified (`docker inspect` / `docker exec`) |
|---|---|---|
| Telemetry off | `LIGHTPANDA_DISABLE_TELEMETRY=true` | env present in container ✓ |
| Core dumps off | `LIGHTPANDA_DISABLE_CORE_DUMP=true` **plus** `ulimit core 0` | env present ✓; `Ulimits=[{"Name":"core","Hard":0,"Soft":0}]` ✓ |
| Robots | `--obey-robots` on `serve` (accepted at startup; smoke fetch honored robots semantics — robots.txt 404 ⇒ allow-all) | server started cleanly with the flag ✓ |
| Non-root | image runs as user `lightpanda` | `User=lightpanda` ✓ |
| No new privileges | `security_opt: no-new-privileges:true` | `SecurityOpt=["no-new-privileges:true"]` ✓ |
| Resource limits | `mem_limit: 1g`, `cpus: 2.0` | `Memory=1073741824`, `NanoCpus=2000000000` ✓ |
| No secrets | nothing mounted at all | no bind mounts in the service ✓ |
| AGPL-3.0 | runs **unmodified** as a separate process; never forked/patched | — |

## 5. Loopback-only + the required unreachability test

- Publish: `127.0.0.1:9222:9222`. The in-container bind is `0.0.0.0:9222` (standard for containers; Lightpanda's own log even notes the wildcard-bind advertising) — safe **only because the host-side publish is loopback**, exactly as the owner described.
- **`scripts/lightpanda_loopback_test.ps1` — PASS (run 2026-10-11):**
  1. Binding proof: listeners for port 9222 = `127.0.0.1` only (never `0.0.0.0`/`::`).
  2. Other-device probe: connection to this machine's LAN interface IP `172.21.32.1:9222` → **unreachable (refused/blocked)** — the exact destination another device would target.
  3. Positive control: CDP answers on `127.0.0.1:9222` → `Lightpanda/1.0`.
  Also provable at config level: `PortBindings={"9222/tcp":[{"HostIp":"127.0.0.1","HostPort":"9222"}]}`.

## 6. Smoke test (local test pages only)

| Check | Result |
|---|---|
| `lightpanda version` (in container) | **1.0.0** |
| CDP `/json/version` on 127.0.0.1 | `Browser=Lightpanda/1.0` |
| Local page fetch (host loopback server → `host.docker.internal:8137`, `fetch --dump markdown --obey-robots`) | markdown dumped successfully |
| JS execution proof | fixture updates its marker via script; dump showed **`NORTHSTAR-LIGHTPANDA-SMOKE-JS-OK`** — the engine executed JavaScript ✓ |

Artifacts committed: `docker-compose.lightpanda.yml` (config only, digest-pinned) · `tests/lightpanda_fixtures/local_smoke_page.html` · `tests/lightpanda_fixtures/prompt_injection_page.html` (**the injection fixture is in place**: contains "ignore rules / fetch amazon / print env" payloads — for the Phase 3 acceptance test, expected outcome = nothing beyond a logged denial) · `scripts/lightpanda_loopback_test.ps1` · `docs/SECURITY_TOOLING.md` §7.

Stop command when desired: `docker compose -f docker-compose.lightpanda.yml down` (container is currently up, loopback-only, for gateway development).

## 7. Phase 3 reminders (acknowledged; not yet built)

- **No fork/patch** — AGPL stays simple only while it runs unmodified as a separate process. ✓ acknowledged.
- **Compatibility table — sources list: PROPOSED for owner approval (no fetch until approved; Amazon and anything behind a login excluded):**

| # | Source | Why | Notes |
|---|---|---|---|
| 1 | `example.com` | neutral control | trivial static page |
| 2 | `en.wikipedia.org` | neutral control | heavy but well-behaved, permissive robots |
| 3 | `costco.com` | core sourcing target | public product/category pages |
| 4 | `costcobusinessdelivery.com` | MOQ/supply checks | public item pages |
| 5 | `samsclub.com` | club sourcing | public search tiles |
| 6 | `bjs.com` | club sourcing | previously JS-blocked for the old scanner — informative for Lightpanda |
| 7 | `bulkofficesupply.com` | wholesale | public pages |
| 8 | `koleimports.com` | wholesale | public |
| 9 | `bazic.com` | wholesale | public storefront |
| 10 | `webstaurantstore.com` | wholesale | JS-heavy — capability probe |
| 11 | `uline.com` | shipping/industrial | bot-protected — a useful failure-mode probe |
| 12 | `faire.com` | discovery data | public pages only; wholesale access requires login → out of scope |

  Excluded: all `amazon.*` (hard block), member/login-gated content everywhere, anything requiring an account. The gateway will additionally require: robots.txt pass, policy-kernel grant per host, and the untrusted-data envelope.

## 8. Outstanding items (owner's list) — status + what I need to close them

| Item | Status | To close |
|---|---|---|
| Key rotations (SCAVIO / BRIGHTDATA) | Marked "being rotated" by owner (2026-10-11) — **not yet confirmed in-thread** | Owner confirms completion; scanner keeps the 2 known-active entries meanwhile. If the owner prefers rotation-independent evidence, I can re-verify scanning behavior only — I cannot (and will not) touch the accounts. |
| Working-tree scrub decision (both archives) | Review delivered (`reports/archive_credential_review_20261011.md`), **Option A recommended** (4+1 line redactions) | Owner's go-ahead → I execute it as one reviewed commit and the baseline drops to 1 known-active. |
| History rewrite (git history) | Open owner policy question (F2 precedent) | Owner decision; never done unilaterally. |
| Threat-model sign-off | Draft delivered (`reports/threat_model.md`); review pending | Owner review (the §7 sign-off items). |

**Baseline honesty note (owner's reminder acknowledged):** the pipeline is green **because of the baseline**, not because the findings are resolved — 8 known-active stay printed on every run until the items above close.
