# NorthstarOS acceptance campaign — final report (first durable batch)

**Date:** 2026-10-23
**Scope executed:** Chrome Connect repair + verification, interface defects from the operator's review video, and the first mandatory creative scenario (A — branded packaging mockup) driven through the real UI.
**Verdict:** the browser layer and the chat→render→label chain work end to end and produced a real, persisted artifact. Scenario A **passes on completion and persistence**, **partially passes on photographic quality**. One controller integration defect remains open (D-01), one capture-method defect is documented (D-09).

---

## 1. Repositories

| Repo | Root | Branch | HEAD | Dirty at start |
|---|---|---|---|---|
| Product | `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent` | `feature/v4.1-mesh` | `10a1062c` | 597 entries (mostly data/db artefacts) |
| Controller | `C:\Users\T2Hol\OneDrive\Documents\Default Project` | `main` | `fcc0942` | 4 files (pre-existing operator work: `config/chromecontrol.json`, `plan.js`, `pw-tool.js`, `chromecontrol-playwright-bridge.js`) |

The controller's uncommitted `diagnose` work was left untouched — it is not mine and was never reset.

## 2. Chrome Connect — health and what was repaired

Verified this session (not inherited from the blueprint):

- Guardrail fingerprint `5ae23cde…70f37` **matches** the operator baseline; owner config loaded; no policy table was edited.
- `127.0.0.1` and `localhost` are on the operator allowlist (they were added by the operator before this campaign, not by me).
- Profile pinned `Profile 6` ("Work"); transport binding **VERIFIED**; MCP child alive; `mcp_session_state: CONNECTED`; `extension_answered: true`.
- **Isolation is not provable** (`chrome_signed_out` FAILED — profile signed into `northstarosllc@gmail.com`; cookie inspection not authorized). Every run in this report is a **non-isolated run on the operator's signed-in profile**, explicitly stated, never claimed as isolated.

Repairs landed earlier in this session (interface), verified live in the browser:
The app now renders real artefact identities in the transcript (`DIELINE` chips, `Doypack 95.0x160.0mm + 25.0mm gusset (SVG)`), a wide reading column, one icon family, and a single-row composer with an Options disclosure — all visible in captures 02–05.

Defects found **in the controller integration** this session:

| ID | Finding | State |
|---|---|---|
| D-01 | `chromeconnect_run` is refused (`isolated_profile_required`) unless `require_isolated:false` is passed explicitly, even though `policy.isAlibabaHost()` is false for loopback and the MCP server code computes `!!(requireIsolated \|\| restricted)`. Hypothesis (unproven): the host fills the omitted boolean with `true`, or the running child predates part of the tree. | **open** — a controlled restart of the MCP server is the test, but the host may not respawn it, so it needs an operator decision |
| D-07 | A run's `data` is the **last** step's result: `read`+`screenshot`+`console` returned console text as "page data" | open — workaround: put `read` last |
| D-09 | `screenshot` is hard-coded `fullPage: true` | open — documented |
| D-10 | `click` on a repeated test id fails with a StrictMode violation (3 plan cards in history); grammar has no `nth` | open — scope the selector in the plan |

Working around D-01 is transparent: every run passes `require_isolated:false` and reports `isolated_verified:false`.

## 3. Test evidence (assertion totals AND native exit codes)

Controller (repo: Default Project, branch `main`, HEAD `fcc0942`):

| Command | Result | Exit |
|---|---|---|
| `node test/chromecontrol-tests.js` | `72 passed, 0 failed` | **0** |
| `node test/agent-loop-tests.js` | `145/145 checks passed` | **0** |

Product (repo: Northstar OS Retail Arbitrage Agent, branch `feature/v4.1-mesh`, HEAD `10a1062c`):

| Command | Result | Exit |
|---|---|---|
| `python -m pytest test_shell_modes.py -q` | 33 passed | 0 |
| `python -m pytest test_pouch_label.py -q` | 19 passed | 0 |
| `python -m pytest test_creative_execute_artifact.py -q` | 4 passed | 0 |
| `python -m pytest test_chat_tools.py -q` | 13 passed | 0 |
| `python -m pytest test_voice_speak.py -q` | 13 passed | 0 |
| `python -m pytest test_creative_plan.py -q` | 25 passed | 0 |
| chat/studio/creative selection (`-k "chat or studio or design or compositor or voice or print or creative or provider or pouch"`, `--ignore=costco_non_kirkland --ignore=autothink`) | 647 passed, 19 skipped | 0 |
| `npm run build` (northstar-os-ui) | 0 errors, 1.24–2.0 s | 0 |

**Full-suite caveat (recorded, not explained away):** the complete backend suite could not be run in one process. It dies mid-run with `MemoryError` (e.g. `Out of memory interning an attribute name`) at ~30 % because this 15.4 GB box also hosts ComfyUI, Ollama, Chrome and the agent. Individual modules pass when run alone. I did **not** claim a full-suite pass; the last documented full baseline in `00_STATE.json` remains the reference.

Two apparent failures during the campaign (`test_shell_modes` F at position 15; `test_pouch_label` MemoryError) were re-run with memory free and both passed. They were environment starvation, not regressions — now proven rather than asserted.

## 4. Capability matrix (the denominator)

`reports/northstar_acceptance_20261023/capability_matrix.{json,csv}`, generated from the real sources (SPA `<Route>` table, `chat_tools.TOOLS`, `main.py` router imports):

**96 inventoried capabilities** = 53 UI routes + 25 chat tools + 18 service routers.

| Status | Count |
|---|---|
| tested | 3 (chat composer typing, `creative_plan`, `generate_image`→`apply_label` chain, plus UI `/home` render) |
| passed | 3 |
| failed | 1 (D-01, controller-level, not a product capability) |
| blocked | 0 |
| not run | 93 |

That is ~3 % of the inventory. It is deliberately honest: the first batch proved the browser layer, the shell, and the headline creative chain. The service sweep is the next batch.

## 5. Scenario A — branded packaging mockup (chat-driven entry point)

**Path exercised through the real UI:** typed brief in the composer → `press Enter` → `creative_plan` → plan card → approved draft → `generate_image` → `apply_label` → persisted asset → link in the answer.

| Evidence | Value |
|---|---|
| Typing acceptance | controller predicate `stop_reason: typed_text_verified_in_transcript` (text present in a **persisted message**, not the composer) |
| Controller run ids | `…_mvkknj8r`, `…_mvkkrph5`, plus the click/read runs journalled under `data/agent-journal/` |
| Plan id | `plan_67155819af1b04c9` |
| Final asset | `2136ae5b-6b63-4a8a-b02b-e76909f43c9d`, `Mogra Organics Lion's Mane 6oz labelled`, **832 × 1216**, 1,075,419 B, `asset_type: composite` |
| Plate asset | `180a9675-81f2-43ba-b217-9a65b882bf74`, 832 × 1216, `generated-image` |
| Chat answer | 4 tool runs; link `[View labelled PNG](/api/design-studio/assets/2136ae5b…/file)`; states the mockup-fit caveat and the certification-licence caveat |
| Captures | `screenshots/05-scenarioA-chat-result.png`, `screenshots/scenarioA-labelled-mockup.png` (UI output), `screenshots/scenarioA-labelled-v2.png` (after the fit fix) |
| Spend | 34 metered credits on a **local** Flux render; `DESIGN_CREDITS_ENFORCE` unset → meter-only; cloud engine disarmed. **Real spend: $0.00** |

**What passed:** a completed image is visible in the UI, the brand and product are correct, the copy is exact (it is drawn, not generated), the asset persists and is retrievable by id after the turn.
**What is short of a pass on quality:** the underlying Flux plate fills the frame and is flatly lit, so the labelled result reads as a printed label panel more than as a photoreal standing pouch. The face-fit inset was widened (3.5 % → 7.5 % x / 6.5 % top / 5 % bottom, plus a hard "label ≤ 86 % of the measured face" rule) and the recomposed v2 keeps the pack's edges visible — but the plate itself is the limiting factor. **This is reported as a partial, not a pass.**

## 6. Defects fixed in this batch

| ID | Defect | State |
|---|---|---|
| D-02 | `apply_label` missing from the `create` focus tool subset — the new lane would have been unreachable where it is needed | verified-fixed (regression assertion in `test_shell_modes`) |
| D-03 | every portrait `generate_image` request died with "height is above the maximum (1216)" | verified-fixed (`896x1344 → 816x1216`, aspect kept) |
| D-04 | a render came back as a blank bag with no way to finish it in chat | verified-fixed — produced asset `2136ae5b…` through the UI |
| D-05 | every spoken turn died with `unknown voice 'bojo-narrator'` | verified-fixed (HTTP 200, real voice, same-origin WAV) |
| D-06 | reloaded artefacts lost name/kind ("asset" cards) | **verified in the live UI** (DIELINE chips + real filenames) |
| D-08 | the Simple shell did not fill the viewport (page scrolled to 2717 CSS px; 5434 px capture) | verified-fixed by capture (5434 → 1520, no white band) |
| D-11 | `creative_plan` draft charged credits, rendered, and returned **no asset id/URL** (`default_generate` ran with `account_id: None` and no db, so persistence was skipped) — this is the "charged draft with no artifact" the model reported live | verified-fixed + 4 regression tests; the artifact now persists |
| D-12 | the composited label could cover the entire pack and erase its silhouette | code-fixed; verified by recompose (v2), **UI re-render not re-run** |

## 7. UI modernisation delivered

- Simple mode is a real flex frame: the panel fills the viewport, only the stream scrolls, and the page no longer scrolls (D-08).
- Reading column is fluid (`clamp(760px, 78vw, 1360px)`); prose caps at 78ch while cards/artefacts use the width.
- One icon family replaces every unicode glyph (⚙ ✎ ⌥ ⏸ ▶ 📎 🎙 ● ■ ✗ ×).
- Composer collapsed from three stacked rows to one, with the six dropdowns behind an Options disclosure that states the current mode/style/effort.
- Artefact cards carry a real kind chip, a neutral checkerboard behind transparent images, and a lightbox that closes on Escape.
- Space scene: the scrim reached 0.80 alpha and crushed the Gargantua shader to near-black; it is now a 0.00→0.52 vignette and the exposed margin was widened (`padding: clamp(16px, 2.8vw, 64px)`), so a planet limb and nebula band are visible in captures 03–05. The shader itself (lensed accretion disc, photon ring, Doppler beaming, star lensing) was **not** rebuilt.

## 8. Not done / next batch

1. **Service sweep** — 93 of 96 capabilities untested. `/home` and chat are proven; the rooms (Design Studio, Listing Forge, AdPilot, Golden Goose, Memory Bank, Beta Ops…) are untouched.
2. **Scenarios B, C, D** — product imagery set, A+ content package, and the five-second video ad were not attempted. The video duration option must be verified as supported before any credit is spent.
3. **D-01** — needs an operator decision on restarting the Chrome Connect MCP server.
4. **D-12** — re-run the scenario through the UI so the corrected fit is the artifact on record.
5. **Real-source editing/compositing** — blocked until an approved product photograph exists in the library; uploads are not expressible in the current controller grammar (`ACTION_MAP` has no file-input action).
6. **Live voice** is not streaming — record → transcribe → answer → synthesise, one turn at a time. It must not be called "live".
7. Full backend suite — run when the GPU stack is idle, in batches.

## 10. Batch 2 — the service sweep, and what it actually found

Six Simple-mode routes were opened and read through Chrome Connect:
`/design-studio`, `/listings`, `/adpilot`, `/golden-goose`, `/memory-bank`, `/beta-ops`.
`?shell=advanced` was then tried on three of them.

| Observation | Consequence |
|---|---|
| Every room route rendered the **chat shell**, not the room | In Simple mode a room is a chat FOCUS by design (`MasterBrainShell` PATH_FOCUS). The room itself only exists in Advanced. |
| `?shell=advanced` was rewritten to `?shell=simple` | `capabilities.advanced_view` is **false** for this account. |
| `/beta-ops` redirected to `/home` | The operator's own account cannot open Beta Ops at all. |

**D-14 (root cause):** the signed-in identity is role `operator` on plan `whetstone`.
`shell_router` grants advanced view only to `ADMIN_ROLES = ("admin", "internal_platform_admin")`, a plan
carrying the explicit `advanced_view` ui gate, or an org with `advanced_reports`. None apply.

So the entire operator experience reviewed in the video is **chat-only**, and every purpose-built
workspace the assignment asks for (Design Studio, Listing Guardian, AdPilot, Golden Goose, Memory Bank,
Beta Ops, Admin) is unreachable **by entitlement, not by defect**. That is a product decision to
confirm, not something I should flip: `shared/subscription-plans.json` and the gate were left untouched.

**Correction to O-02.** I initially recorded "the model ignores an explicit tool instruction" as a
defect. That was wrong, and the record is corrected here: my sweep had left the session on the **Grow**
focus, and `tools_for_focus("grow")` does not include `apply_label`. The model could not see the tool
and said so honestly ("whether the image/label lane is down or just not exposed to me here"). After
switching the focus back to **Create**, the same instruction ran `apply_label` immediately.

**D-12 closed.** The corrected fit was re-run through the UI and produced
`7367995f-d008-4379-923b-a5f3c0854972` ("Lion's Mane — labelled mockup", 832×1216, 1,193,099 B,
06:41). Byte-identical to the local recompose, so the composite is deterministic.
Evidence: `screenshots/scenarioA-labelled-v3-ui.png`.

**O-03.** One turn failed with the engine's own honest error ("Ollama is not running… nothing was
fabricated") minutes after an explicit model-eviction request. Ollama was in fact up and serving the
27B; the next identical turn succeeded. Transient cold-runner failure, surfaced correctly — not a
silent failure.

**Coverage after batch 2: 13 of 96 capabilities tested** (11 UI routes/tools + the two chat-chain
calls), recorded in `capability_matrix.json` with per-route results and the entitlement block.

---

## 9. Commits

No commit was made in this batch. The product working tree carries the interface repair plus this batch's fixes (`chat_tools.py`, `chat_voice.py`, `chat_router.py`, `chat_adapter.py`, `creative_execute.py`, `shell_focus.py`, `studio_generation.py`, `pouch_label.py`, `App.jsx`, `Icon.jsx`, `simple.css`, tests) and the controller tree carries the operator's pre-existing uncommitted work; neither was committed to avoid mixing operator work with mine. A coherent commit split is proposed in `checkpoint.md`.
