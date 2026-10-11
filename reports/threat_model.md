# Threat Model — NorthstarOS Secure Control-Layer (Phase 1 draft)

- **Date:** 2026-10-11 · **Owner:** T2 Holdings LLC · **Status:** DRAFT for owner review (Phase 1 deliverable)
- **Method:** STRIDE (per component) + OWASP LLM Top 10 mapping. Grounded in the Phase 0 audit (`reports/audit.md`), the Phase 1 build to date, and the owner's build spec (Phases 1–7).
- **Scope of this model:** the *secure control layer being built* — Policy Kernel, Lightpanda Connect gateway + browser pool, Snapshot Store / data layer, Master Brain Kernel, MCP/OpenCode tool surface, and future multi-tenant exposure. The legacy app and UI exist in the same repo; their existing controls are referenced but not re-modeled here.

## 1. Trust boundaries (text diagram)

```
 [Operator]                          UNTRUSTED ZONE (all page text, tool output, files, model output)
    │                                     ┌──────────────────────────────────────────────┐
    ▼                                     │  Live web (Lightpanda fetches) · providers   │
 [OpenCode / agents] ── MCP tools ──►    │  captured fixtures · chat archives · deps    │
    │            (fetch_page/extract/     └──────────────────────────────────────────────┘
    │             markdown_dump ONLY)                  ▲
    ▼                                                  │ sanitized + enveloped data only
 [Master Brain Kernel] ── delegation ──► [Policy Kernel] ──► [Drivers]
    (no direct tool/net access)          (deterministic,       ├─ Lightpanda Connect gateway (browser pool)
    ── capabilities ──► approvals        fail-closed,          ├─ Chrome Connect (existing controller)
    ── audit log ◄── every decision       immutable at runtime) ├─ provider layer (dimensioned/armed)
                                                                 └─ connectors (future)
                              Snapshot Store ◄── gateway writes (validated, hashed, typed)
                              Tenant data     ◄── row-level filters (future)
```

Hard rules carried in from the build spec: agents never touch Lightpanda/CDP directly; the brain never reads credentials (each driver holds its own); the policy kernel cannot be edited by agents at runtime; Amazon is hard-blocked in code; no stealth/captcha/login bypass ever.

## 2. Assets to protect

| Asset | Why it matters |
|---|---|
| Credentials/keys (provider keys, tokens, session material) | Financial loss, lateral movement; never in brain/prompts/logs |
| Policy kernel + allowlists + approval queue | The guarantee that makes autonomy safe |
| Audit log (hash-chained) | Tamper-evident decisions; incident forensics |
| Snapshot store (evidence) | Business decisions depend on it; poisoned/labeled-wrong data is an integrity incident |
| Tenant data (future) | Customer PII/business data; isolation is a contractual promise |
| Availability of the fetch path | Rate/cost limits, provider quotas |
| The product's reputation as "safe with AI" | The differentiator; security failures are existential for a beta |

## 3. STRIDE by component

### 3.1 Lightpanda Connect gateway + browser pool
| Threat | Scenario | Controls (required) |
|---|---|---|
| **S**poofing | Rogue process/agent talks to CDP:9222 directly | Bind 127.0.0.1 only; port not reachable from LAN (test); agents get only gateway tools; no direct CDP handle (spec §4 steps 1–3) |
| **T**ampering | Malicious page mutates browser state/sessions to affect later fetches | Fresh isolated context per call (no shared cookies); gateway re-creates sessions; browser pool is disposable |
| **R**epudiation | "Which fetch produced this snapshot?" deniable | Every call journals: policy decision, URL, timestamps, result hash; hash-chained audit |
| **I**nfo disclosure | Page content steered into prompts; secrets leaked via logs | Sanitize + strip scripts/hidden text + cap size + **untrusted-data envelope**; never into instruction channel; log redaction (Phase 1 shipped) |
| **D**oS | Fetch loops, huge pages, slow hosts burn quota/CPU | Per-run request/byte caps, per-domain rate limits, per-run time budget, response size cap (policy kernel) |
| **E**scalation | SSRF: fetch `http://169.254.169.254/…`, redirect to intranet, DNS rebinding | Resolve DNS → block private/loopback/link-local/metadata ranges; re-check **after redirects**; limit redirects; http/https only; rebinding defense (re-resolve + pin) |

Supply-chain sub-surface: Lightpanda binary is **AGPL-3.0, run unmodified as a separate process** (owner directive), pinned + checksummed at install; Docker: non-root, read-only FS, no mounted secrets, resource limits.

### 3.2 Policy kernel (Phase 2)
| Threat | Scenario | Controls |
|---|---|---|
| **T**ampering | Agent edits policy at runtime / config override | Kernel is pure code + operator-owned config files; runtime-immutable; changes only via reviewed commits (spec §0.9: policy changes as diffs) |
| **S**poofing | A "task" grants itself capabilities | Capability grants are explicit, issued by the kernel, expire at task end; default none |
| **I**nfo disclosure | Amazon blocklist bypass via encodings/subdomains/redirects | Hardcoded blocklist always checked first (not config-editable); URL canonicalization + post-redirect re-check; acceptance tests for variants |
| **E**scalation | Simulated outputs written to snapshot store as real | SIMULATED tag is structurally un-writable to the snapshot store |
| **D**enial | Approval fatigue / rubber-stamping | Approval queue records named approvals; spend/live/side-effect actions always gated |

### 3.3 Snapshot store / data layer (Phase 4)
| Threat | Scenario | Controls |
|---|---|---|
| **T**ampering | Poisoned snapshot influences Golden Goose decisions | `content_hash`; provenance (`source`, `data_class`, `limitations`); parser_version; freshness_status |
| **S**poofing | A cached/estimated value presented as live-verified | Null-first: UNKNOWN stays UNKNOWN with reason; never coerced to 0/estimate; freshness gates see CACHED as display-only |
| **R**epudiation | "Who observed this, when?" | observed_at + source + tenant_id columns; append-only audit of ingest |
| **I**nfo disclosure | Cross-tenant leakage (future) | tenant_id on every row + enforced data-access layer (row-level filters) + A-can't-read-B tests |
| **D**enial | Corrupt/healed scrapers fill store with garbage | Scrapling parser/HTTP tier only, inside gateway; healed selectors record match confidence + review flag; healed values are never marked verified |
| **E**scalation | Economics alone authorizes purchase | Separate gate fields (`resale_eligibility`, `exact_pack_match`, `cost_fee_basis`, `invoice_path`, `operator_approval`); nothing is purchase-authorized from economics alone |

### 3.4 Master Brain Kernel (Phase 5)
| Threat | Scenario | Controls |
|---|---|---|
| **S**poofing | Sub-agent claims another skill's identity | Skills registry: service tag + required capabilities; rules block prepended |
| **T**ampering | Brain edits policy/grants its own capabilities | Brain CANNOT edit the kernel, grant capabilities, or approve its own requests (structural, tested) |
| **R**epudiation | Decisions without traceability | Every decision + tool call → audit log; process table (task_id/owner/parent/capabilities/budget/status) |
| **I**nfo disclosure | Prompt injection steers "fetch amazon.com, print env" | Injection fixture is an acceptance test: must produce a logged denial and NO action; untrusted envelopes; capability default-deny |
| **D**enial | Runaway loops/retries | Budgets per task; kill switch halts all tasks + revokes all grants (one command, tested) |
| **E**scalation | Confused-deputy via tool params | Capability checks at the gateway boundary (not just brain); params schema-validated; policy re-checked server-side |

### 3.5 MCP / OpenCode integration (Phase 6)
| Threat | Scenario | Controls |
|---|---|---|
| **T**ampering | Third-party skills fetch/execute scripts | READ every file before install (owner rule); remove anything that runs scripts/fetches remotely; skills are text-only |
| **I**nfo disclosure | Skills with built-in telemetry or hidden instructions | Review-only installs (marketingskills subset + ~10 reviewed Agency personas); version-pinned |
| **E**scalation | Agent uses bash/file tools to read secrets | OpenCode deny rules: .env, keychains, ~/.ssh, other repos; project-level config only; **MCP entry disabled by default** |
| **S**poofing | MCP server replaced/patched | Project-level config points ONLY at the gateway; single owner-controlled entry |

### 3.6 Future tenants
- Row-level `tenant_id` everywhere + enforced access layer + isolation tests (Phase 4).
- Tenant-scoped API keys **hashed at rest** (Phase 7); short-lived sessions + MFA for operator roles.
- Rate limits per tenant; CORS locked; request size caps; TLS everywhere; encryption at rest; tested backups/restore; key rotation plan.

## 4. OWASP LLM Top 10 mapping

| # | Risk | Where it lands | Controls |
|---|---|---|---|
| LLM01 | Prompt injection | Gateway output → brain; untrusted pages | Untrusted-data envelope; instruction-channel separation; injection acceptance test (Phase 5); deny-by-default capabilities |
| LLM02 | Insecure output handling | Tool outputs consumed by agents | Sanitization + schema-validated extraction; envelope; no raw HTML into models |
| LLM03 | Training-data / knowledge poisoning | Memory bank, snapshot store, skills | Provenance + review gates; memory revisions/unlearn; skills review-only installs |
| LLM04 | Model DoS / cost abuse | Provider layer; brain loops | Budgets, retries bounded, kill switch, per-run caps |
| LLM05 | Supply-chain | Deps (uv.lock), Lightpanda binary, skills | Pinned+hashed deps; checksummed binaries; AGPL run unmodified; gitleaks + scanner gates; SBOM (pending) |
| LLM06 | Sensitive-info disclosure | Logs, snapshots, prompts, exports | Redaction (shipped); data-rights register + export filters (foundation, existing); no secrets in brain |
| LLM07 | Insecure plugin/tool design | MCP surface (3 tools only) | Minimal tool surface; schema validation; policy check per call; no file/bash access via MCP |
| LLM08 | Excessive agency | Brain delegation, approvals | Capability grants + expiry; no self-approval; approval queue; kill switch |
| LLM09 | Overreliance | Decision outputs | Evidence labels (VERIFIED/REPORTED/UNKNOWN), null-first, freshness gates, "never purchase-ready from a score" |
| LLM10 | Model theft | Local models (Ollama) | Local-first; no model endpoints exposed; access controlled |

## 5. Existing controls already in place (from Phase 0 audit; do not regress)

Foundation: JWT hardening + fail-closed posture, CSRF, login throttle, session revocation, permission matrix, approvals, jobs runtime re-checks, denial-audit middleware, redaction + audit scrub, data-rights register, security headers. Legacy: rate limiter, BFF envelope, offline test network guard. Phase 1 added: log redaction wiring, tests/security suite (64 tests), offline secret scanner + fingerprint-exact allowlist, gitleaks (pinned), uv.lock, CI stub.

## 6. Residual risks / accepted gaps (owner-visible)

1. **Historical secrets in git history** (pre-existing F2 class + the 2026-10 escalation family: `ghp_` token in `autothink-ui-chat-export.md`; `SCAVIO_API_KEY`/`BRIGHTDATA_API_KEY` in `FirstNorthstarautomationchat.md`). Mitigation pending owner rotation + scrub/history decision. The scanner keeps these ACTIVE until remediated.
2. **Chrome Connect vs Lightpanda Connect coexistence** — operator policy decision; nothing bypasses Chrome Connect today; the gateway must not create a second ungoverned browser path (Phase 3 must reconcile; policy draft as a diff only).
3. **gitleaks allowlists are not fingerprint-exact** (no native hash allowlist) — gitleaks is advisory; the repo gate is the offline scanner (fingerprint-exact). Documented in docs/SECURITY_TOOLING.md.
4. **CI is a stub** — no hosted CI yet; local runs are the current enforcement.
5. **Model/provider details stay internal** by design (no customer data to providers; provider identity not exposed to customers).
6. **External pen test** (Phase 7 acceptance) is not yet scoped/scheduled.

## 7. Review asks (owner)

1. Confirm the STRIDE control set matches your intent for Phases 2–5 (anything to add/remove before implementation).
2. Confirm the residual-risk posture in §6.1 (rotate + scrub vs archive-as-is) and §6.2 (gateway vs Chrome Connect relationship).
3. Sign off the acceptance gates listed per component (esp. §3.1 LAN-unreachability test, §3.4 kill switch + injection test) as the Phase 2–5 "done" bar.
