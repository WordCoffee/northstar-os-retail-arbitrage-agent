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

## 5. Blocker found — guardrail drift (needs one operator word)

```
fingerprint()  727f78e56cb4dfd513677c21d44ed40dafc4a5bcc68d52867c5d9b223ea993e9
baseline       5ae23cde016a53b29e4f6c9b59da06bf8249fcb72b142dd559386b412a570f37
intact: false
```

- `config/chromecontrol_policy_owner.json` is **clean in git** (no uncommitted edit).
- The file itself records `"updated_at": "2026-10-23"` and
  `"updated_by": "operator (authorized: Packify Tier B behaviour study, 2026-10-23)"`.
- So the tables were changed **with** authorisation, but `baseline_fingerprint` was never recomputed.

Consequences, all fail-closed and all visible:

- `chromeconnect_status` reports `guardrails.intact: false`.
- `node test/agent-loop-tests.js` → **143/145**; the two failures are `D0 policy guardrails are intact before any lesson write` and `D3 a legitimate selector lesson is accepted as PROPOSED`.
- Every lesson write (including L6 above) is refused.

I did **not** run `policy-bless` and did not edit the baseline. Recomputing an operator-owned baseline is a guardrail action, and the constitution reserves it to the operator. One word — *"bless the 2026-10-23 policy"* — and it is a one-command fix that restores 145/145 and unblocks lessons.

---

## 6. Item-by-item state after this session

| # | Item | State |
|---|---|---|
| 1 | Theme v3 | **not mine, still open** — parallel session; last capture `theme-v3b-desktop.png` still reads as a smudge |
| 2 | Mobile capture path | **done + unit-proven**; first live use needs the browser to itself |
| 3 | Simple Mode brief | blocked on **operator approval** (S1–S7 unverified) |
| 4 | Package Designer brief | **P1–P7 evidenced** (P4 was already on disk); awaiting sign-off |
| 5 | BOJO-UTIL executor | not started — router classifies (`specialists/router.py` `_UTILITY`), no executor exists |
| 6 | Autothink send path | not started — `scope()` offers a priced handoff, no transport |
| 7 | Phase 7 cloud rehearsal | blocked — needs a provider choice + keys |
| 8 | Phase 1 study debt | not started (7 Tier A repos, 10 Tier B products) |
| 9 | Manager benchmark | blocked — 27B ctx ceiling fixed earlier; gpt-oss/Gemma weights not on disk |
| 10 | Render evidence | blocked — needs the GPU lane; memory-bound box (ComfyUI + Ollama + Chrome) |
| 11 | L6 lesson | **written**, registration blocked by §5 |
| 12 | Commit | **done** — two commits, 43 files |

---

## 7. Decisions I need from you

1. **Bless the 2026-10-23 guardrail baseline?** (unblocks lessons + restores 145/145)
2. **Sign off Package Designer P1–P7?** (evidence is complete; nothing left to build)
3. **Approve the Simple Mode brief?** (nothing can be verified until it is approved)
4. **A `.gitignore` policy for `data/`, `reports/*.png`, `*.part0`?** (this is the remaining 634 entries)
