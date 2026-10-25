# Northstar Simple Mode — issue register (customer-facing main view)

**Generated:** 2026-10-25 (agent scan, replaces the Perplexity draft)
**Owner of record:** Master Brain (this repo) + operator for approvals
**Scope:** Simple Mode as the customer-facing main view (`DEFAULT_MODE = 'simple'`, `northstar-os-ui` React SPA, plus the standalone `autothink/ui/index.html` seam).
**Baseline verified this session:** `npm run build` 0 errors (1.87s); backend suites `test_utility_apps` 12/0, `test_shell_modes`+`test_cie`+`test_skills_plane` 68/0, `test_chat_tools`+`test_turn_contract`+`test_voice_speak` 48/0, `test_mockup_compositor` 8/0. Chrome Connect guardrails intact (fingerprint == baseline).

---

## 0. Gating blocker — captures cannot run yet

**B0. Chrome Connect isolated profile is NOT signed out.**
Preflight (`chromeconnect_preflight require_isolated=true`) reports `chrome_signed_out: FAILED` — Profile 6 "Work" carries `user_name = northstarosllc@gmail.com` (signed-in Chrome identity), and the cookie store is not authorized for inspection. The constitution forbids driving a signed-in profile or entering credentials. Consequence: **S1–S7 captures, the BOJO-UTIL click test, the portrait render end-to-end proof, and the deep visual pass are all blocked on the operator signing out of Profile 6 (or pinning an isolated profile) and restarting the controller.** Nothing below can be visually verified until B0 is cleared. This is the single highest-leverage operator action.

**B1. Controller restart pending.** The viewport-screenshot change (item 2) and the guardrail bless (727f…) are committed in the controller but cached by the running MCP child; `chromeconnect_guardrails` here already shows intact, but the live child must restart before mobile captures land.

---

## 1. Verified solid — do not re-fix

Type scale (16.5px body / 28.4px line-height, measured live), 820→clamp(760,78vw,1360)px reading column, 95.5% opaque panel, film-faithful Gargantua shader, table rendering, `apply_label` exact-text lane, asset metadata persistence, voice 422 fallback, icon system, plan cards, intent router (6f6f0bc), sign-in race fixed. 28/0 shell gate, 18/0 galactic harness, 0 build errors. Tests cited above green.

---

## 2. Blockers for customers seeing Simple Mode

### S1–S7 captures never ran
- **Status:** approved (briefs/simple_mode.md, 2026-10-24) ≠ verified. Only S1 desktop has screenshot evidence; 6 of 7 checks unproven.
- **Owner:** Master Brain once B0/B1 clear.
- **Action:** single Chrome Connect run capturing desktop + mobile (390×844) per `reports/acceptance_followup_20261024.md` §1, then file evidence per check in briefs/simple_mode.md. Until then the approved design is unproven.

### Canvas "black" report (Oct 22) unresolved at design level
- **Status:** shader works; Jul composition makes it read as void (hero occluded, gutters ~1% luminance). Parallel theme-v3 session's latest capture "still reads as a smudge." Two sessions converging without a merged decision.
- **Evidence:** commits 433b3661 / 561dffd7 / 2e67213b / 487f04b2 progressively lighten `.cb-sky`, body bg, top-nav, scrim; celestial.css exists.
- **Owner:** operator (merge decision) + Master Brain (implement).
- **Action:** pick ONE composition (either keep the lightened celestial theme or revert to a brighter hero band) and lock it; add a measured luminance check (gutter ≥ 5% luminance) to the capture pass. Do not let two sessions keep diverging.

### Standalone AutothinK UI (`autothink/ui/index.html`, :8100) never received Simple Mode
- **Status:** 913 lines (actually 37.6 KB) of the old cyan/neon style; no Simple Mode tokens, no celestial theme, no Gargantua. Reachable via `autothink/launch.bat|ps1` and `launch-all.ps1`.
- **Owner:** Master Brain.
- **Decision needed:** (a) restyle to Simple Mode theme, (b) redirect :8100 → React `/autothink`, or (c) mark deprecated and remove from launchers. Recommended: (b) + (c) — the React app already ships AutothinK as a focus; the standalone surface is a visible seam and duplicate maintenance burden.

---

## 3. Major UX (from operator review video, partially fixed, needs live re-verification)

### Portrait renders rejected before reaching engine (fitbox fixed, unproven end-to-end)
- **Status:** `studio_generation._fit_box()` scales into the 1216 px box on one factor; schema accepts 64..4096; verified unit-level (896×1344 → 816×1216, etc.). No browser-driven generation run.
- **Owner:** Master Brain after B0/B1.
- **Action:** one live generation of an 896×1344 portrait through the chat, confirm the render + the apply_label mockup both succeed, screenshot both.

### BOJO-UTIL pages compute correctly in tests but never clicked
- **Status:** `specialists/utility_apps.py` + `build_utility` tool, 12 tests pass, arithmetic mirrored Python↔JS, page self-contained. No human has clicked a built page.
- **Owner:** operator (30-second manual) or a capture once B0/B1 clear.
- **Action:** open one built `.html` asset, enter values, confirm the numbers move; record result in briefs.

### Voice is record→transcribe→answer→separate TTS, not live conversation
- **Status:** current S3 is push-to-talk dictation with a separate TTS reply. As the main view, users will read the mic icon as "voice chat."
- **Owner:** operator (feature decision) + Master Brain (build if approved).
- **Decision needed:** (a) build streaming voice (flagged feature, real scope), or (b) present honestly as dictation (rename icon/tooltip to "dictate", drop the "voice chat" affordance). Recommended interim: (b) — ship honest labeling now; (a) only on named approval with budget.

---

## 4. Debt that will bite later

### Two stale prompt-equality tests go red on any system-prompt change
- **Status:** FIXED this session — `test_shell_modes`, `test_cie`, `test_skills_plane` now assert containment (`CHAT_SYSTEM_PROMPT in …`, `DELIVERABLE_ROUTING in …`) instead of brittle exact equality. All 68 pass.
- **Owner:** Master Brain (done).

### Canonical test runner RED on four untracked costco files
- **Status:** `costco_non_kirkland/tests/test_brightdata_*` fail at collection (missing `build_enrichment_manifest`, `is_costco_product_url` in `brightdata_costco_enrichment.py`). Four untracked files + module.
- **Owner:** operator decision (finish or delete); Master Brain implements.
- **Decision needed:** finish the enrichment adapter (add the missing symbols per call-site evidence) OR delete the four test files + module. Do not silently delete — protected-data discipline. Recommended: finish, since the module is already wired into the pipeline; but requires an authoritative spec for the missing symbols.

### compose/typography unverified since Oct 16
- **Status:** `mockup_compositor` tests pass (8/0) but no measured quad pass on a real plate; a customer uploading a new dieline silently gets a geometric guess, disclosed only in the asset note.
- **Owner:** Master Brain.
- **Action:** re-run the measured face pass on at least one real plate per format family (doypack, pouch, box) and record measured vs. geometric delta; gate `apply_label` on a "measured / geometric-guess" flag in the asset note (already partially there).

### Backend started without the launcher drops its env silently
- **Status:** FIXED this session — `main.py` now loads the repo-root `.env` (override=False) before module imports, so root-only keys (DATAFORSEO_*, FIRECRAWL_*, etc.) resolve even without a launcher. Health now reflects real login state.
- **Owner:** Master Brain (done).

### Voice 422 fallback + mixed-content audio
- **Status:** fixed (voice_id 'bojo-narrator' → first real voice, same-origin audio serve). Needs a live re-verification pass once B0/B1 clear (one capture).

---

## 5. Operator actions required (batched)

1. **Sign out Chrome Profile 6 ("Work")** or pin an isolated profile, then restart the controller (unblocks B0/B1 and the entire capture pass).
2. **Merge decision on the canvas composition** (lightened celestial vs. brighter hero band).
3. **Decision on standalone AutothinK UI** (redirect/deprecate vs. restyle).
4. **Decision on voice** (streaming build vs. honest dictation labeling).
5. **Decision on costco files** (finish vs. delete).
6. **(Optional) Snyk token** if full agent-scan analysis is wanted (currently local-inspection only).

---

## 6. Recommended execution order

Phase A (operator, ~5 min): B0 + B1.
Phase B (Master Brain, autonomous): S1–S7 capture pass (desktop + mobile) → file evidence; portrait render end-to-end proof; BOJO-UTIL click; voice 422 re-verify; typography measured pass; standalone AutothinK redirect/deprecation; canvas composition lock.
Phase C (operator decisions): voice streaming, costco finish/delete, canvas composition (if not decided in Phase A).
Phase D (Master Brain): implement decided items; update briefs/simple_mode.md evidence table; final report.

Evidence: this register + `reports/acceptance_followup_20261024.md` + `briefs/simple_mode.md`.
