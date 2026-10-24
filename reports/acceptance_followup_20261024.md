# Acceptance follow-up — items 2, 4, 11, 12 (2026-10-24)

**Scope:** the items the parallel session was not doing while it worked theme v3.
**Verdict:** item 2 is built and unit-proven (not yet exercised live, deliberately); item 4 is already evidenced and now reconciled; item 11 is written but cannot be registered; item 12 is done in two coherent commits. One real blocker surfaced: **the operator-owned guardrail baseline no longer matches the policy file**, and I did not touch it.

---

## 1. Item 2 — mobile capture path (D-09): viewport control

**Before:** `screenshot` was hard-coded `fullPage: true` at whatever size the operator's window happened to be. Every mobile acceptance check in every brief was therefore unprovable, not failed.

**Change (controller repo, additive):**

| File | Change |
|---|---|
| `lib/chromecontrol/plan.js` | new grammar suffix `screenshot <path> @WxH`; `parseViewport()` bounded to 320–3840 × 320–2160; exported for tests. A bare `screenshot <path>` produces exactly the old step. |
| `scripts/chromecontrol-playwright-bridge.js` | `resize` added to the tool map; `normalizeViewport()`; screenshot branch reads the page's own `innerWidth/innerHeight` via a controller-owned function, resizes, captures, then restores in a `finally`. |
| `test/chromecontrol-tests.js` | +1 test covering both parsers (valid, absurd, string-coerced, absent). |

**Design decision worth stating:** the bridge **refuses** the capture (`refused: previous_viewport_unknown`) when the page will not report its current size. Resizing an operator's window to 390×844 and not being able to put it back would silently break every later run on that browser. A refusal is visible; a stuck phone-width window is not.

**Proof:** `node test/chromecontrol-tests.js` → **73 passed, 0 failed** (was 72).

**Not committed:** the controller repo is on `main` and already carries the operator's own uncommitted work, so the change sits in that working tree. It is additive, and the running MCP child has the old module cached, so nothing the parallel session is doing changes behaviour until the server is restarted — which is the moment this becomes live.

**Not proven yet, on purpose:** no live mobile capture. A parallel session is driving that same browser, and a resize is a visible change to a window the operator is using. The first live use should be a single run that captures desktop and mobile in one plan:

```
STEPS:
screenshot reports/<batch>/screenshots/desktop.png
screenshot reports/<batch>/screenshots/mobile.png @390x844
```

The bridge reports `previous_viewport`, `viewport` and `restored`, so the run itself is the evidence that the window was put back.

---

## 2. Item 4 — Package Designer P4: already evidenced

`reports/northstar_acceptance_20261023/screenshots/phase3-back.png` already satisfies P4:

- **Ingredients** — "Organic Lion's Mane (Hericium erinaceus) fruiting body powder"
- **Warnings** — "Consult a physician if pregnant, nursing or taking medication."
- **Company** — Mogran/Mogra Organics LLC
- **Address** — 123 Main St, Austin, TX 78701, USA
- **Country of origin** — USA
- **Barcode zone** — boxed, labelled `BARCODE ZONE (RESERVED)` / `supply GTIN/UPC at print`, no fake barcode drawn
- **Missing facts** — `LOT [MISSING: lot code]`, i.e. P6's discipline is visible in the same capture

So the "P4 needs one capture" line was stale. P1–P7 are all evidenced; what is outstanding is the **operator's sign-off**, which is not mine to give.

**One real cosmetic defect, recorded not hidden:** the address line already ends `USA` and the origin line prints a second `USA` underneath. It is not a P4 failure (both required fields are present and correct), and it is not fixed here because changing panel artwork would invalidate the capture above.

---

## 3. Item 11 — L6 lesson (written, cannot be registered)

The proposed lesson, in the controller's PROPOSED-only form:

> **L6 — nested keylines read as a sticker.** When a label panel is composited into a dieline that already draws the die/keyline, the panel must not draw its own keyline. Either suppress it or inset it by the die stroke width. Two keylines a few pixels apart are what makes a printed wrap read as a sticker on a photograph.

It is **not registered in the lessons store**. See §5: lesson writes are currently refused because the requested write fails the operator-baseline check, which is correct fail-closed behaviour, not a bug to route around. The text above should be submitted once the baseline is blessed.

---

## 4. Item 12 — commit split

The product tree had **649 dirty entries and no commits from the acceptance work**. Two commits landed, both restricted to source and tests:

| Commit | Contents | Files |
|---|---|---|
| `9916943e` | `feat(chat)`: fit box, `pouch_label`/`apply_label`, `asset_meta`, voice fallback, shell-focus reachability | 15 files, +1628 |
| `570be634` | `feat(specialists)`: panel router, package-designer panels, gateway ledger | 28 files, +3779 |

**Proof before committing:** 158 passed / 0 failed across `test_chat_tools`, `test_pouch_label`, `test_voice_speak`, `test_shell_modes`, `test_turn_contract`, `test_creative_plan`, `test_creative_execute_artifact`, `test_specialists`, `test_scope`; plus 62 passed across `test_gateway`, `test_panel_map`, `test_image_rules`, `test_ppc_bulk`, `test_lessons`, `test_creative_agents`.

**What was deliberately left out, and why:**

| Left out | Reason |
|---|---|
| `northstar-os-ui/src/**` | a parallel session is mid-theme (`celestial.css` is a new untracked file); committing half a theme breaks the build |
| `Northstar_backend/data/**` (184 files), `data/northstar.db*` | runtime state, not source |
| 259 `.json` + 78 `.png` evidence artefacts | evidence belongs with its report, not in a source commit |
| 7 × multi-GB `.part0` model weights | must never enter git |
| ~60 root-level `show_*/diag_*/probe_*/test_qwen*` scripts | unfamiliar one-off scratch work; untracked is reversible, committing it is not |

Remaining dirty count after both commits: **634** — almost all data/evidence, which needs a `.gitignore` decision the operator should make rather than one I make for them.

---

## 5. Guardrail drift — RESOLVED by operator bless (2026-10-24)

```
fingerprint()  727f78e56cb4dfd513677c21d44ed40dafc4a5bcc68d52867c5d9b223ea993e9
baseline       5ae23cde016a53b29e4f6c9b59da06bf8249fcb72b142dd559386b412a570f37   ← before
intact: false
```

- `config/chromecontrol_policy_owner.json` was **clean in git** (no uncommitted edit).
- The file itself recorded `"updated_at": "2026-10-23"` and
  `"updated_by": "operator (authorized: Packify Tier B behaviour study, 2026-10-23)"`.
- So the tables were changed **with** authorisation, but `baseline_fingerprint` was never recomputed.
  (The allowlist commit `475e09a policy(chromeconnect): allow packify.ai for the Tier B behaviour study`
  is that edit.)

**Resolved.** The operator approved the bless, and `node scripts/chromecontrol.js policy-bless --operator`
recorded `727f78e5…` as the new baseline. Verified as a *record*, not a policy change: every key except
`baseline_fingerprint` / `updated_at` / `updated_by` compares **equal to HEAD, key by key** — no host added
or removed, no prohibited action changed. `node test/agent-loop-tests.js` → **145/145 checks passed**
(was 143/145). Committed in the controller as `df98b2b`.

**One thing still pending, and it is not a defect:** the running MCP child caches the policy file at
`require` time, so `chromeconnect_guardrails` will keep reporting `intact: false` (old baseline `5ae2…`)
until that child restarts. The same restart is what makes the viewport change live. A parallel session was
mid-run (`reload_northstaros_with_the_fresh_bundle_mvlzpn5v`, 06:00:39Z), so the restart was left to the
operator rather than pulled out from under it.


---

## 6. Item-by-item state after this session

| # | Item | State |
|---|---|---|
| 1 | Theme v3 | **not mine, still open** — parallel session; last capture `theme-v3b-desktop.png` still reads as a smudge |
| 2 | Mobile capture path | **done + unit-proven**; first live use needs the browser to itself |
| 3 | Simple Mode brief | **approved 2026-10-24**; S1–S7 still need captures (S1 desktop done, mobile needs one restart) |
| 4 | Package Designer brief | **signed off 2026-10-24** — P1–P7 evidenced, duplicate-country defect accepted |
| 5 | BOJO-UTIL executor | not started — router classifies (`specialists/router.py` `_UTILITY`), no executor exists |
| 6 | Autothink send path | not started — `scope()` offers a priced handoff, no transport |
| 7 | Phase 7 cloud rehearsal | blocked — needs a provider choice + keys |
| 8 | Phase 1 study debt | not started (7 Tier A repos, 10 Tier B products) |
| 9 | Manager benchmark | blocked — 27B ctx ceiling fixed earlier; gpt-oss/Gemma weights not on disk |
| 10 | Render evidence | blocked — needs the GPU lane; memory-bound box (ComfyUI + Ollama + Chrome) |
| 11 | L6 lesson | **written**; registration now unblocked by the bless, needs the controller restart to be accepted by the live child |
| 12 | Commit | **done** — four commits, 44 files; tree 649 → 211 entries |

---

## 7. Decisions — all four answered 2026-10-24

| Decision | Answer | What was done |
|---|---|---|
| Bless the 2026-10-23 guardrail baseline? | **yes** | `policy-bless --operator` → `727f78e5…` recorded; tables unchanged key-by-key; 145/145; controller commit `df98b2b`. Takes effect for the live child at its next restart. |
| Sign off Package Designer P1–P7? | **yes** | Recorded in `briefs/package_designer.md` with the evidence file per check, and the duplicate-country cosmetic defect accepted rather than hidden. |
| Approve the Simple Mode brief? | **yes** | Recorded in `briefs/simple_mode.md` with the S1–S7 evidence state per check. Approval is of the design; S1–S7 still need captures. |
| A `.gitignore` policy for generated output? | **yes** | `Northstar_backend/data/`, `*.db*`, `*.part0`/`*.gguf`/`*.safetensors`, `out_sb/`, `renders/`, `reports/**/*.png` (with `reports/**/screenshots/**` kept committable as evidence), `*.bak*`. Tree: 428 → 211 entries. Commit `86c9e4f`. |

**What this leaves open, in order:** S1–S7 captures (needs one controller restart), BOJO-UTIL executor,
Autothink transport, then the blocked-by-spend items (cloud provider, GPU render evidence, benchmark
weights).
