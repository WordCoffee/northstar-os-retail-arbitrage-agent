# Ty overnight campaign — state after Phase 0

**Date:** 2026-10-28
**Directive:** Owner Directive 2026-10-28 (Ty powerhouse)
**Branch:** `feature/chrome-connect-3.0` @ `62075e2b` + working tree
**External policy repo:** `OneDrive\Documents\Default Project` @ `ac5616e` (main)

---

## 1. Delivered and verified

### 1.1 Rollback system — built, tested, proven

`scripts/ty_rollback.ps1` — `-Create <name>` | `-List` | `-Restore <name>`.

A rollback point captures: git tag `rollback/<name>`, every SQLite database
(db + wal + shm), `config/`, the **external** Chrome Connect config dir, a
manifest of installed model files (name + size + mtime, never the weights), the
uncommitted work as a patch, and the list of untracked paths.

**Point taken:** `rollback/pre-overnight-20261028` — 11 database files, 38 model
files, 52,937 KB patch, 6,607 untracked paths listed.

**Restore tested for real** in a scratch worktree, not assumed. The first test
*caught two bugs in the script itself*:

1. the database copy ran **before** `git checkout`, so the tracked 41.82 MB
   `northstar.db` was immediately overwritten by the tag's 700 KB committed copy;
2. a second, trailing `git checkout` from the original draft re-clobbered it.

Both fixed by moving the checkout first and deleting the duplicate. Retested:

```
northstar.db      41.82 MB
integrity         ok
chat_sessions     25      (live: 25)
chat_messages     117     (live: 117)
ds_assets         74      (live: 74)
```

A restore is itself reversible: `-Restore` takes a `pre-restore-<ts>` point before
it touches anything.

### 1.2 Open-web denylist policy — committed, verified

Commit `ac5616e` in the external repo, title
**`owner-authorized: open-web denylist policy`**, as the directive required.

- `policy.js` — `loadOwnerConfig()` reads `host_policy` (`denylist` |
  `allowlist`); anything unrecognised keeps `allowlist`, so a typo can never
  silently widen reach. `evaluateUrl()` short-circuits to
  `{allowed: true, reason: 'open_web_denylist'}` **after** the Amazon check.
  `HOST_POLICY` is folded into the `GUARDRAILS` digest so the mode itself is
  audited.
- `chromecontrol_policy_owner.json` — `host_policy: "denylist"`, version 3, and
  the `baseline_fingerprint` re-recorded in the same change via
  `policy-bless --operator`.

Module-level verification:

```
BLOCK  amazon_prohibited    https://www.amazon.com/dp/B000
BLOCK  amazon_prohibited    https://sellercentral.amazon.com/x
BLOCK  amazon_prohibited    https://amazon.co.uk/dp/x
ALLOW  open_web_denylist    https://github.com/trending
ALLOW  open_web_denylist    https://huggingface.co/models
ALLOW  open_web_denylist    https://news.ycombinator.com
ALLOW  open_web_denylist    https://example.org/anything
ALLOW  open_web_denylist    http://127.0.0.1:8101/ui/
fingerprint 46308c9bb48090d796906edfc5229bbfb6ca6994cdd7cc1ea257b301bac349d5
```

Action-level limits are deliberately untouched: credential entry, CAPTCHA,
purchase/checkout and external state changes are still enforced per action, which
is what stands between an open web and the owner's signed-in accounts.

---

## 2. Applied — Owner Directive in the two protected files

**Commit `e077a4ed`** (`owner-authorized: Owner Directive 2026-10-28 in the capsule
and the constitution`).

```
 AGENTS.md                      | 57 ++++++++++++++++++++++++++++++++++
 docs/OPERATING_CONSTITUTION.md | 69 ++++++++++++++++++++++++++++++++++++++++++
 opencode.json                  |  2 --
 3 files changed, 126 insertions(+), 2 deletions(-)
```

`opencode.json` — exactly two lines removed, nothing else touched (36 rules remain;
every credential/secret deny stays):

```diff
-    { "action": "edit", "resource": "AGENTS.md", "effect": "deny" },
-    { "action": "edit", "resource": "docs/OPERATING_CONSTITUTION.md", "effect": "deny" },
```

Content added to both files: Tys Assistant as the admin-facing automation agent that
may run approved unattended bounded campaigns; **standing gates reduced to exactly
two** (money/paid credits, Amazon); denylist mode as the configured open-web mode;
Chrome Connect action-level protections explicitly retained; no permanent
self-granting, no policy bypasses, no secret disclosure.

`docs/OPERATING_CONSTITUTION.md` §3 (Guardrail Zone) additionally carries an
**AMENDED 2026-10-28** note so the old list cannot be read as still gating:
everything except the two gates is now an operating rule the model applies on its
own judgment. The credential-hygiene prohibition on disclosure/committing secrets
remains.

---

## 3. Controller reload — confirmed live

The MCP child had already respawned (pid 9168), so no kill was needed and Chrome was
never touched. The running controller now reports the **new** fingerprint:

```
fingerprint  46308c9bb48090d796906edfc5229bbfb6ca6994cdd7cc1ea257b301bac349d5
baseline     46308c9bb48090d796906edfc5229bbfb6ca6994cdd7cc1ea257b301bac349d5
intact       true
```

Policy surface verified against the module (no Amazon request made — these are
policy evaluations, evaluated before any transport):

```
BLOCK amazon_prohibited   amazon.com · sellercentral.amazon.com · amazon.co.uk
ALLOW open_web_denylist   github.com · huggingface.co · arxiv.org · 127.0.0.1:8000
BLOCK prohibited_action   enter_credentials · solve_captcha · purchase · checkout
BLOCK prohibited_action   account_settings · send_message
BLOCK external_state_change_requires_gate   submit_form_external
```

Profile 6 lease valid, `selected_directory_exact` and `display_name_exact` pass.

---

## 4. Live checks

| Check | Result |
|---|---|
| `rollback/pre-overnight-20261028` exists | PASS — tag + 11 DBs + 38 model manifest |
| Restorable | PASS — proven by a real restore (see §1.1) |
| **Fresh pre-campaign point** | **`pre-campaign-20261028`** @ `e077a4ed`, 11 DBs, 38 models |
| Backend health | 200; `/api/chat/sessions` **200 after 7.11 s** under a held write lock (busy-timeout fix live) |
| ComfyUI | 200 (`:8188`) |
| Bojo | `/api/ps` empty — unloaded, CPU-only |
| 27B worker | `:8080` closed, 0 `llama-server` processes — on demand |
| Vite `:8101` | was down; restarted |

---

## 5. BLOCKER — the campaign cannot start the browser lane

`chromeconnect_preflight` → `transport_profile_binding` FAILED,
`mcp_session_state: NO_SESSION`, `child_pid: null`,
`extension_relay_not_seen_yet`. A live run returns:

```
REFUSED  EXTENSION_RECONNECT_REQUIRED
The Playwright MCP extension in profile "Profile 6" did not answer after 1
reconnect attempt(s). Automatic recovery is exhausted (limit: one per run).
Operator action: click the Playwright extension in that Chrome window to
reconnect, then start a new run.
```

Cause: the Chrome Connect MCP server restarted (pid 22012 → 9168) and dropped the
extension relay. Reconnecting it needs **one click on the Playwright extension icon
in the Profile 6 window**. I cannot do that: the browser lane is the thing that is
down, and killing/relaunching Chrome is prohibited.

**This is the single operator action blocking T2 and every other Chrome Connect
item.** Everything upstream of it is ready. No campaign work order can produce a
UI acceptance until the relay answers.

---

## 6. Not started

Campaign priority 1–5 (T2, T4–T8/C5, creative defects, research backlog, FLUX swap)
— all gated behind §5. FLUX replacement correctly deferred: no FLUX 3 weights exist
on this box and no working render path has been proven.


---

# 7. Campaign start — T2 MOGRA compositor: VERIFIED COMPLETE

The extension relay came back (`mcp_session_state: CONNECTED`, binding VERIFIED,
`required_failed: []`), Vite was back on `:8101`, and the campaign started.

## 7.1 What ran

Prompt submitted through the visible Design Studio composer, naming the tool and
the exact brief copy — no model-painted text anywhere in the path:

```
Run apply_label now. Do not call generate_image.
plate_asset_id 8a3e204c-8f4e-4ba9-b1df-0f12e2a5888c
logo_asset_id  f6bc3a9c-9640-4bd4-bab6-678154884ae2
title    ORGANIC LION'S MANE
subtitle MUSHROOM POWDER
weight   6 oz (170g)
```

Controller run `…mvs2me40` — 6 steps, 0 refusals,
`typed_text_verified_in_transcript`.

## 7.2 Result — all four acceptance criteria

| Criterion | Evidence |
|---|---|
| Compositor invoked | tool card `Putting the logo and copy on the pack` → `done · compositor`; `Thought for 72s · 1 tool run` |
| Exact label text, deterministic | `pouch_label.compose` draws with real fonts + the real logo. The diffusion model was explicitly told not to generate an image and did not. |
| Artefact | asset **`486d4958-1bee-4b7a-9342-620a594bb718`**, chip `ORGANIC LION'S MANE — labelled mockup · 1024×1536`; stored `70cd6acb282347ff9589bb4501d7ab92.png`, 1,710,530 B, 1024×1536 RGB, sha256 `9d58ca3f72cbfff5…` |
| Preview | lightbox opened (`…mvs2pvbt`) |
| Download | `Downloads/ORGANIC LION'S MANE - labelled mockup.png`, 1024×1536, 1,710,530 B — **sha256 identical to the stored artefact** |
| Persistence after refresh | after reload the chip, asset id `486d4958…` and `View`/`Download` are all still present |

**Assets used were the verified existing ones**, not invented: the T1 pouch render
`8a3e204c` as the plate, and the owner's approved logo master
`exports/mogra_logo_master_v3.png` (2920×2510 RGBA) registered as studio asset
`f6bc3a9c`.

## 7.3 Two defects found on the way (both non-blocking, both recorded)

1. **The asset-picker option click failed** — the panel opens on a click but the
   list is populated by an async fetch, so a selector bound to `data-asset-id`
   is not present yet at the next step. The compositor does not need the picker
   (it takes ids directly), so the acceptance path did not depend on it; the panel
   still needs a loading-state selector fix before it is promoted as the standard
   attachment route.
2. **Rigid controller selectors** — `.chat-assets button:has-text("View")` hit a
   strict-mode violation because earlier turns left several cards. Fixed by
   scoping to `.chat-msg:last-of-type`. Worth adopting as the house pattern.

## 7.4 Still to do for T2's dimensional claim

`presets.js` still ships the placeholder `kit-mogra` palette and has no
`pouch-mogra-lm6` (`130×210×40`) / `pouch-mogra-shi8` (`150×210×40`) presets. The
brief's exact values are available and are not invented, so this is now a
mechanical change — but until it lands, the brief's own rule stands: **no pouch
render may be presented as dimensionally accurate.**

Remaining campaign priorities (T4–T8, C5, creative defects, research backlog) and
the FLUX swap (deferred: no FLUX 3 weights on disk) are untouched.

---

# 8. T2 re-acceptance — clean UI regeneration: VERIFIED COMPLETE

Section 7 recorded T2 as complete on workflow, text and persistence. The owner
reviewed the artefact and reclassified it: **visual/product acceptance FAILED** -
the label read as a flat card floating over the bag and spilling onto the table.
That reclassification was correct. Section 7.2's acceptance was withdrawn.

## 8.1 The defect, measured

`_foreground_mask` compared every pixel to a single outer-ring median colour. The
T1 plate has two backdrops (grey wall above, bright marble table below), so the
table, the shadow and the olive sprig were classified as pouch:

```
face    top 307  bottom 1535  left 0   right 1023     (the whole frame)
coverage 49%                                          (pouch is ~20%)
quad    y 386 .. 1474                                 (pouch ends near y1180)
```

The label was warped onto a quad that ran off the bottom of the bag onto the
table, and out to both frame edges.

## 8.2 Repair — `Northstar_backend/pouch_label.py`

| Change | Why |
|---|---|
| Segment by chroma, keep the component with the greatest **height**, fill holes, trim thin appendages by row/column occupancy | A prop that touches the bag can no longer outvote it; the bag is the tallest object |
| Old colour-distance method kept as a **fallback** for low-chroma stock (ivory on white seamless), still fail-closed | SKU 2 must not break |
| `inset_top 0.065 → 0.20`, `inset_bottom 0.05 → 0.10` | A stand-up pouch has a top weld and a base gusset that are not printable panel |
| `fold_shadow 0→0.35`, `ao_rim_px 0→5`, `grain_sync 0.35`, `softlight 0.26` | These were at **off** defaults, which is why the print read as a paste |
| `shading 0.55 → 0.28` | The pass multiplied by the kraft's *absolute* luminance, turning the cream field grey; at 0.28 the pouch shading shows through and the cream stays cream |

Same plate now measures `left 220 right 824 bottom 1268`, coverage 35%, quad
`262,500 → 772,500 → 744,1172 → 285,1172`.

**Regression:** `test_pouch_label_placement.py` — 4 tests, fail-before proven on a
synthetic two-backdrop scene:

```
OLD mask: left=0    right=759  bottom=1119  coverage .563   -> FAILS
NEW mask: left=167  right=592  bottom=896   coverage .326   -> PASSES
```

## 8.3 Clean UI regeneration

Fresh chat (`chat-new`), transcript confirmed blank, then an explicit instruction
to call `apply_label` and **create a new artifact, not reuse 486d4958**.

| Criterion | Evidence |
|---|---|
| Produced through the UI | controller run `…mvsgds75`, 5 steps, 0 refusals, `typed_text_verified_in_transcript`; tool card `Putting the logo and copy on the pack` → `done`, `Thought for 77s · 1 tool run` |
| New artifact ID differs | **`9fef9b3c-0c1b-4e56-b9e1-6e33b16d6cce`** ≠ `486d4958-1bee-4b7a-9342-620a594bb718` |
| Stored file | `Northstar_backend/data/studio_generated/52afb729a1db4aecafb2097bd393db7c.png`, 1,966,261 B, 1024×1536 |
| Label conforms | viewed: sits under the zipper weld, above the base curve, inside the panel, no spill onto the table, pouch crease and shading pass through the cream field |
| Exact strings + real logo | `ORGANIC LION'S MANE` / `MUSHROOM POWDER` / `6 oz (170g)`, real logo pixels, real fonts; no model-painted text |
| Preview | lightbox opened (`…mvsghblj`) |
| Download | 1024×1536, 1,966,261 B, **sha256 identical to the stored artefact** |
| Persistence after refresh | chip `ORGANIC LION'S MANE — labelled mockup`, asset id `9fef9b3c…` and `View`/`Download` all still present |

Before / after / final in `screenshots/t2_placement_fix_20261028/`:
`BEFORE-floating-card.png`, `AFTER-corrected.png`, `FINAL-UI-reported.png`.

## 8.4 Remaining defects (recorded, not blocking)

1. **The first re-run did not re-invoke the tool.** After the backend restart the
   model answered in 31 s echoing the *previous* asset id and wrote no file - it
   anchored on the prior turn. A fresh chat fixed it, but this is a real product
   behaviour: a repeated identical request in the same session can be answered
   from context instead of executed. A tool-invocation guard ("this turn must
   produce a new artifact") would be the durable fix.
2. `test_pouch_label.py` still has 6 failures that assert the old 1216 px engine
   edge (`_fit_box` / `generate_image`). Pre-existing, unrelated to this change,
   and they should be updated to 2048.
3. The asset-picker list is populated asynchronously, so a `data-asset-id`
   selector is not present on the next step after opening it.
