# NorthstarOS acceptance campaign — checkpoint

**Updated:** 2026-10-23 (session started 2026-10-23)
**Campaign status:** ACTIVE — browser layer proven working, blocked at the app sign-in wall.

---

## Repositories (verified this session, not assumed)

| Repo | Root | Branch | HEAD | Dirty |
|---|---|---|---|---|
| Product (NorthstarOS) | `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent` | `feature/v4.1-mesh` | `10a1062c` | 597 entries (mostly data/db artefacts; my edits listed below) |
| Controller (Chrome Connect) | `C:\Users\T2Hol\OneDrive\Documents\Default Project` | `main` | `fcc0942` | 4 files, all pre-existing: `config/chromecontrol.json`, `lib/chromecontrol/plan.js`, `lib/chromecontrol/pw-tool.js`, `scripts/chromecontrol-playwright-bridge.js` |

Uncommitted controller work is **preserved untouched** (it adds the `diagnose` verb; it is not mine and was not reset).

## Services (live)

Launch command (secrets never printed): `powershell -File scripts\launch_alpha.ps1 -Restart`

| Service | Address | State |
|---|---|---|
| SPA + API | `http://127.0.0.1:8000/ui/` | up, health OK, assets served |
| AutothinK | `http://127.0.0.1:8000/autothink/ui/index.html` | up |
| Vite dev | `http://127.0.0.1:8101/ui/` | up (PID 23564) |
| ComfyUI | `127.0.0.1:8188` | up |
| Ollama | `127.0.0.1:11434` | up |
| Local voice | `127.0.0.1:8321` | up |
| Public tunnel | `https://warrant-springer-subtle-capabilities.trycloudflare.com` | up (URL is unguessable; do not share) |

## Chrome Connect (verified, not assumed)

- Controller: `chromeconnect (agent-loop)`; `model_owns_browser: false`; `gate_in_loop: false`.
- Guardrails: fingerprint `5ae23cde…70f37` **matches** the recorded baseline; owner config loaded; `127.0.0.1` and `localhost` are on the operator allowlist.
- Profile: pinned `Profile 6` ("Work"), `transport_profile_binding: VERIFIED`, MCP child PID 24920 alive, `mcp_session_state: CONNECTED`, `extension_answered: true`.
- **Isolation: NOT provable.** `chrome_signed_out` FAILED (Chrome identity `northstarosllc@gmail.com` signed in); `no_sensitive_session_cookies` UNAVAILABLE (`cookie_metadata_inspection_not_authorized`). Every run below is therefore reported as **non-isolated, operator profile**.
- The earlier "awaiting profile selection" state from a prior Oracle task is gone.

## Proof the browser layer actually controls a page

| Run | Result |
|---|---|
| `…_mvkkkpb7` | REFUSED — `isolated_profile_required` (see D-01) |
| `…_mvkknj8r` | **COMPLETE**, 4 steps, 8 Playwright calls, 0 refusals, screenshot written |
| follow-up read | `COMPLETE` — URL `http://127.0.0.1:8000/ui/sign-in`, title `NorthstarOS — Retail Arbitrage Suite`, page_status `READ` |

Screenshot: `reports/northstar_acceptance_20261023/screenshots/01-landing.png` (30,936 B).

## BLOCKER B-01 — the app sign-in wall

The local UI redirects to `/ui/sign-in`; the operator Chrome profile holds no valid `ns_session` cookie for `127.0.0.1:8000` (the live session was created against an earlier tunnel address, and every `launch_alpha -Restart` rotates it).

I cannot enter credentials and will not automate a login submission. **Action needed from the operator:** sign in manually in the already-open Chrome window (Profile 6 → `http://127.0.0.1:8000/ui/sign-in`), then tell me to resume. Nothing else blocks the browser campaign.

## Resolved without asking — brand

The spoken request says "Mocha Organics"; project sources say **Mogra**. Evidence: 237 occurrences of `Mogra` across the repo, **0** occurrences of `Mocha Organics`, and the operator's own logo asset renders `MOGRA ORGANICS`. The approved brand is **Mogra Organics**; "Mocha" is a speech-to-text artefact.

## Spend

Cloud engine **disarmed** (`launch_alpha` reports "Cloud engine: disarmed"). The mandatory creative scenarios are expected to run on the local lanes (ComfyUI Flux / Wan / SDPA voice) at zero provider cost. No billable call has been made this session. If any lane turns out to require a paid provider I will request approval *before* it runs.

## Completed this session (before this campaign)

Interface repair — see `reports/ui_ux_repair_20261023.md` and `00_STATE.json → interface_repair_20261023`. Highlights: the 1216 px render rejection is gone (aspect-preserving fit), a new `apply_label` tool composites the real logo + copy onto a render (the "empty bag" is fixed), reloaded artefacts keep their name/kind, the voice 422 is fixed and served same-origin, and Simple mode now fills the viewport with a fluid reading column and one icon family.

## Exact next safe action

1. **Operator decision on D-14:** either grant this account `advanced_view` (plan gate or admin role) so the rooms can be acceptance-tested, or confirm the chat-only surface is the intended product for `whetstone`.
2. Re-run nothing that already passed — scenario A and D-12 are closed with artifacts on record.
3. Next batch: scenarios B (product imagery set) and C (A+ package) through the chat-driven path, which is reachable at this tier.
4. Scenario D (5 s video): verify the video lane actually supports a 5-second duration **before** any credit is spent.

## First batch results (appended after the sweep started)

- Capability denominator built: **96** (53 routes / 25 chat tools / 18 routers) → `capability_matrix.{json,csv}`.
- Scenario A complete and persisted: asset `2136ae5b-6b63-4a8a-b02b-e76909f43c9d`, 832×1216, `composite`,
  produced by chat → `generate_image` → `apply_label` in the live UI. Quality is a partial (flat plate).
- Controller suites: 72/0 and 145/145, both exit 0. Product modules: 33 + 19 + 13 + 13 + 25 + 4 passed.
- New defects: D-07 (run `data` = last step), D-09 (fullPage captures), D-10 (strict-mode click),
  D-11 (plan draft had no artifact — **fixed**), D-12 (label could cover the pack — **fixed and
  re-run through the UI**, asset `7367995f…`), D-13 (corrupted URL in evidence), D-14 (no
  `advanced_view` → every room unreachable), O-02 (**corrected**: focus-scoped tools, not model
  disobedience), O-03 (one transient engine error, self-recovered).
- Service sweep (batch 2): 6 Simple routes + 3 advanced attempts read through Chrome Connect.
  **Coverage now 13/96**, per-route results in `capability_matrix.json`.
- Full report: `final_report.md` (§10 is batch 2).
