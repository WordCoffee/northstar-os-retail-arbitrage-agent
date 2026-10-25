# Northstar Simple Mode — fix plan (customer-facing main view)

Companion to `reports/northstar-simple-mode-issue-scan.md`. Each item has an owner, a concrete action, and an acceptance check. Items marked **OP** need an operator action; **MB** are autonomous Master Brain work.

## Phase A — unblock verification (OP, ~5 min)
- [ ] **A1 (OP)** Sign out Chrome Profile 6 ("Work") / pin an isolated profile; restart the Chrome Connect controller. Acceptance: `chromeconnect_preflight require_isolated=true` reports `chrome_signed_out: true` and `isolated: true`.
- [ ] **A2 (OP)** Merge decision on canvas composition: keep lightened celestial (commits 433b3661/561dffd7/2e67213b/487f04b2) OR revert to a brighter hero band. Acceptance: one written decision in this file (append under A2).

## Phase B — verification pass (MB, after A1)
- [ ] **B1 (MB)** S1–S7 capture pass: desktop + mobile (390×844) per `reports/acceptance_followup_20261024.md` §1; file evidence per check in `briefs/simple_mode.md`. Acceptance: 7/7 checks have a screenshot + measured note.
- [ ] **B2 (MB)** Portrait render end-to-end: one 896×1344 generation through chat + apply_label mockup; screenshot both. Acceptance: both artifacts present and named in the transcript.
- [ ] **B3 (MB)** BOJO-UTIL click test: open one built `.html` asset, enter values, confirm numbers move; record. Acceptance: a 5-line note in briefs with pass/fail.
- [ ] **B4 (MB)** Voice 422 re-verify: one PTT turn; confirm fallback voice + same-origin audio. Acceptance: HTTP 200 + audio served.
- [ ] **B5 (MB)** Typography measured pass: one real plate per format family (doypack, pouch, box); record measured vs. geometric delta and gate `apply_label` on a measured/geometric flag in the asset note.
- [ ] **B6 (MB)** Voice labeling decision implementation (interim honest dictation): rename mic affordance to "Dictate", tooltip explains record→transcribe→answer→TTS; no "voice chat" wording anywhere in Simple Mode. Acceptance: grep shows zero "voice chat" strings in `northstar-os-ui/src`.

## Phase C — design decisions (OP)
- [ ] **C1 (OP)** Voice: streaming build (named budget) vs. honest dictation labeling (done in B6). Record decision.
- [ ] **C2 (OP)** Standalone AutothinK UI: redirect :8100 → React `/autothink` + deprecate in launchers (recommended) vs. restyle. Record decision.
- [ ] **C3 (OP)** Costco files: finish enrichment adapter vs. delete. Record decision.
- [ ] **C4 (OP, optional)** Snyk token for full agent-scan.

## Phase D — implement decided items (MB)
- [ ] **D1 (MB)** Standalone AutothinK UI: implement C2 decision. If redirect: `autothink/backend/server.py` serves a 302 to `http://127.0.0.1:8101/ui/autothink`; remove :8100 from `launch-all.ps1` default; keep `autothink/launch.*` as a documented legacy entry.
- [ ] **D2 (MB)** Costco: implement C3 decision. If finish: add `build_enrichment_manifest` + `is_costco_product_url` (and any other call-site-referenced symbols) to `brightdata_costco_enrichment.py` per test call-site evidence; run the 3 test files to green. If delete: remove the four untracked files + module and update the canonical runner's ignore list.
- [ ] **D3 (MB)** Canvas composition: implement A2 decision; add a measured luminance check (gutter ≥ 5%) to the capture harness.
- [ ] **D4 (MB)** If C1 = streaming: scope + build voice streaming (separate batch, named budget). If C1 = dictation: B6 already done.
- [ ] **D5 (MB)** Update `briefs/simple_mode.md` evidence table with Phase B results; final report to `reports/simple_mode_verification_<ts>.md`.

## Phase E — perfect UI/UX design spec (MB, ongoing)

Design principles for Simple Mode as the customer-facing main view (celestial pack):

1. **One reading column, full viewport height.** Prose caps at 78ch; cards/artefacts use the whole column; only the stream scrolls. (Already in simple.css §17.)
2. **Honest affordances.** Mic = dictation unless streaming is actually built. No "voice chat" promise. Every AI capability that is local-only is labeled local-only.
3. **One icon family, one optical weight.** Shared 24px stroke Icon set (already in §18). No OS glyphs.
4. **Composer is the smallest thing that works.** One row of controls; six dropdowns behind a disclosure showing current mode/style/thinking; hint is one short sentence.
5. **Assets carry their name, kind, size.** Never "asset" — always the real filename + kind + dimensions (already via asset_meta).
6. **Composition over black void.** Gargantua shader is the backdrop, not the subject: hero band stays ≥ 5% luminance in gutters; text sits on a 95.5% opaque panel; no element is occluded by the shadow.
7. **Mobile is a first-class target.** 390×844 capture is part of every acceptance pass; rail becomes a drawer; composer stacks.
8. **Reduced motion + fallback.** Static frame under prefers-reduced-motion; honest CSS fallback when WebGL is unavailable.
9. **No dead bands.** Flex chain from page to stream; document pinned to viewport; no white band at any capture size.
10. **Evidence before approval.** Every UI change ships with a capture; approval ≠ verification.

Open design questions for the operator (append answers here):
- Q1. Should the hero band behind the chat be a brighter nebula band or stay near-black with the panel carrying contrast? (A2)
- Q2. Is the standalone AutothinK UI still needed at all, or fully superseded by the React focus? (C2)
- Q3. Dictation labeling vs. streaming voice budget? (C1)

## Acceptance gates (all must be green to declare Simple Mode ship-ready)
- `npm run build` 0 errors.
- Backend: test_shell_modes + test_cie + test_skills_plane + test_chat_tools + test_turn_contract + test_voice_speak + test_utility_apps + test_mockup_compositor all green.
- Chrome Connect: S1–S7 7/7 evidenced; portrait render + apply_label end-to-end; BOJO-UTIL click; voice 422 re-verify.
- No "voice chat" string in Simple Mode source.
- Guardrails intact (fingerprint == baseline).
- Standalone AutothinK UI either restyled or redirected+deprecated.
- Costco canonical runner green (finish or delete decided and executed).
