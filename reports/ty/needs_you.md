# UX rebuild — needs you

Owner-only actions. Everything else continues without them.

## 1. ~~Close the Tailscale serve on port 8000 so the dev stack can start~~ — RESOLVED 2026-11-03

`tailscale serve status` returned **No serve config**; `scripts/dev-start.ps1`'s safety gate passes,
the backend is on 127.0.0.1:8000 and the UI on 127.0.0.1:8101. No action needed.

## 2. Studio top-up payment processor (future; interface stubbed only)

Per the work order, the billing interface is a stub in this run. When the real top-up ships it
needs an owner-configured processor (Stripe or equivalent), merchant account, and price table.
Not blocking any current unit.

## 3. Decision: does the Design Studio page keep a chat box? (2026-11-03, U14 adjudication)

Six e2e specs (`acceptance-mogra` T-auth, `asset_picker`, `chat_composer_stability`) still fail
because they open `/ui/design-studio` and wait for `data-testid="chat-input"`. That route renders the
real studio page, not the chat shell — `App.jsx` keeps `/design-studio` out of the Northstar chat
replacement, and the chat composer lives in the workbench dock (`/ui/workbench`) and in advanced
view. This was already true at the U0 baseline commit, so it is not a regression: those specs predate
the mode gate.

**What I need from you:** one of these, and I will do it in a later unit —

- **(a)** the Design Studio keeps its chat box (a studio-scoped Bojo inside the page), and I re-point
  the specs at it; or
- **(b)** the chat stays in the workbench only, and I rewrite those three specs to drive
  `/ui/workbench` instead (the `acceptance-mogra` render requests would then be asserted through the
  workbench chat, which is the surface a user actually has today).

Silence means (b) is implemented as a spec-alignment task, not a product change.

Meanwhile the two `asset_dashboard` lane-trigger failures are **not** this: at HEAD the lane was
reachable and reported `media_generation_disarmed (MEDIA_GEN_LIVE is not 1)`. **Resolved 2026-11-03** —
you asked for FLUX 3 to be armed, the lane is now armed and both tests pass without the spec changing.
See `docs/FLUX3_LANE.md`. Nothing is left on you for that one.

## 4. Item 0 candidates are ready for your eye (not a blocker)

`renders/mogra_lions_mane/product_front.png` and `product_back.png` (1024×1536) are the first
service-produced product pictures: FLUX 3 plate, designed panel in perspective, OCR gate passed.
What only you can judge is whether the *design* is right — the cream label on kraft, the lion's-mane
mark, the composition. The loop will not pick a style silently. Say what to change and it becomes
the next design task; silence leaves the current artwork as the declared design.

## 5. Amazon ad-video spec (standing gate — operator document, not a request to browse)

The two Amazon video presets are `verified: false` on purpose because reading Amazon's own specs is
a standing gate. To flip them, upload or hand over the current ad-video spec as a document; the code
will then record `verified: true` with the checked date. No Amazon request is made by the loop.

## 6. Nutrition values and UPC (before print, not before a picture)

The Supplement Facts values (2 g serving, 85 servings, 2,000 mg), the UPC and the best-by format are
the values you stated; the panel carries `DRAFT · VERIFY BEFORE PRINT` for that reason. A product
picture does not need them final; a print order does.



## 7. ~~A 15 s video render is a time commitment~~ — DELIVERED 2026-11-03

The 15 s TikTok master is rendered and checked: `renders/mogra_lions_mane/video_15s/video_ad.mp4`
(7,772,276 B, 15.0 s, 450 frames, 1080×1920, h264+aac, -16.0 LUFS, captions OCR-checked, 12.3 min
wall clock). It used the item-0 product picture as the source. Nothing is left on you; if you want a
different script, hook or scene count, say so and it becomes the next render. `POST
/api/design-studio/video-ad/plan` still shows the cost before a render.

## 8. Product decision: is advanced view gated to top tiers? (2026-11-03)

Two pre-existing tests (	est_shell_modes.py) assert that mover (and above) carry the
dvanced_view UI gate while foundation/scout do not. uth.PLAN_ENTITLEMENTS currently has
ui_gates: [] for every plan, so the tests fail. Either restore the gate and name the plans, or tell
me the current all-plans access is intended and I will align the tests. I will not guess a pricing
decision.

## Docs

docs/CREATIVE_LANES.md is the operator-facing map of the surfaces, endpoints, contracts and gaps.
eports/ty/SESSION_20261103.md is the index of this session's units, commits, probes and artifacts.


---

# Autonomy program — needs you (2026-11-05)

Five owner actions. None of them block the program; each is the one thing only you can do.

## A1. A reference set of your *preferred* listing style (blocks W2's held-out set)

The listing workstream (rank 1 by impact x gap) can be measured mechanically — length, claim
safety, keyword coverage — but "is this a good listing" needs a target. Please give me 10-40
listings you consider good (your own, or published ones you admire). Without them W2 can only clear
the mechanical bar, and I will say so in every report rather than call it production ready.

## A2. The current Amazon ad-video spec, as a document

The two Amazon video presets stay `verified: false` because reading Amazon's own pages is a standing
gate. Upload the spec (or paste the requirements) and the presets flip to verified with a checked
date. No Amazon request is made by the loop either way.

## A3. Final nutrition values, UPC and best-by format

Needed for print, not for pictures. The panel currently carries `DRAFT · VERIFY BEFORE PRINT`.

## A4. A top-up payment processor (parks W13)

Stripe or equivalent, a merchant account, and a price table. Until then the credit ledger runs in
meter-only mode and the billing workstream stays parked.

## A5. The product-picture design call

`renders/mogra_lions_mane/product_front.png` / `product_back.png` are service-produced: FLUX 3 plate,
designed panel, OCR gate passed. What only you can judge is whether the *design* is right. Say what
to change and it becomes the next design task; silence leaves the current artwork as the declared
design.

---

# Director program — needs you

Queued by the Director (work order §2: hard lines go here as one exact action, and work
continues without them).

## DIR-1. Rotate three credentials that are already committed

`reports/ty/GITLEAKS_TRIAGE.md` found three real-looking credentials in two tracked
root-level chat exports (commits `a299d6e9`, `21aed4e3`):

1. `SCAVIO_API_KEY` — `FirstNorthstarautomationchat.md:1143,1291`
2. `BRIGHTDATA_API_KEY` — `FirstNorthstarautomationchat.md:1148,1296`
3. a GitHub personal access token — `autothink-ui-chat-export.md:7852`

Exact action: rotate all three at their providers, then say so and the history purge
becomes a Director job. Deletion alone is not enough — the values are in git history.
Nothing here is blocked by this; the loop continues.

## DIR-3. OpenCode Go concurrency ceiling (only if D1 cannot measure it)

D1 probes the real concurrent-session limit. If the probe cannot establish it, the
Director caps at 4 cloud workers as the work order states and records the assumption in
`reports/ty/director_probe.md`. No action needed unless the reply below is empty.

## DIR-5. Turn off lock-on-idle and sleep while plugged in (2026-11-09)

Settings → Accounts → Sign-in options → *If you've been away, when should Windows require you to
sign in again?* → **Never**; and Settings → System → Power & battery → **Screen and sleep** →
plugged-in sleep = **Never**. Ty never touches the lock screen and never enters a Windows
password; this is the only way the vision lane can run unattended. One action, two toggles.

## DIR-6. Reboot once after saving work (2026-11-09)

Reboot this machine once when convenient, then leave it to come back up and sign in. The
`NorthstarTyDirector` logon task starts itself; its first run writes `reports/ty/reboot_proof.md`
with the boot time, the task's last result, the director pid and the queue state. Ty verifies that
file the moment it appears. Nothing else is needed from you, and no password is involved.

## DIR-7. First staging review pack (2026-11-09)

`reports/ty/staging_review_<date>.md` is waiting: before/after images, scorecard deltas, the merged
job list, and one command to promote or revert. Visual and creative bundles stay on `staging`
until you read it. Code-only bundles promote themselves once the suite is green and the verifier
reproduces the deltas.

## DIR-8. One Neck Nirvana product photograph (2026-11-09)

The held-out run covers three lines as asked. Two are real: **Lion's Mane** (Mogra photographs) and
**Word Coffee** (your `pictures for seller umbrella` folder) — 21 briefs, all with a real product
photograph as the reference. **Neck Nirvana has no imagery anywhere on this machine**: the brand
folder under `Desktop\t2-os\brands\neck-nirvana` exists and is empty, and a whole-drive search by
name found nothing. Its three briefs are declared as `declared_unscorable` in
`ty/seller_briefs_heldout.json` rather than scored against an invented product.

Exact action: drop **one** Neck Nirvana product photo (front of pack is enough) somewhere obvious —
`Desktop\t2-os\brands\neck-nirvana\` is where the pipeline already looks. The three briefs then
become runnable with no code change. Until then the held-out mean is published over two lines, and
the third line is named as missing in `reports/ty/heldout_<date>.md`.

## DIR-9. More Lion's Mane product photographs (2026-11-09)

The held-out set runs **21 briefs over 10 distinct product images**: seven Word Coffee product
images (the box, two on white and five in scene) and **three** Mogra images. The Mogra side is the
limit — there are exactly three product images of the Lion's Mane / Shiitake pouches on this machine
(`renders/references/mogra/mogra_pair_main.png`, `mogra_pair_lifestyle.png`,
`mogra_forest_dusk.png`), so ten Lion's Mane briefs cycle through those three. The report says so
under *Limits of this run*.

Exact action: drop five to ten more photographs of the actual pouches (different angles, front and
back, any lighting) into `renders/references/mogra/`. Nothing else needs doing — the brief generator
uses what it finds and the independence note clears itself. Pipeline-made art from
`Northstar_backend/data/studio_generated/` is deliberately **not** used as a reference: scoring the
pipeline against its own output would be circular.

**Also useful, but not blocking:** more Word Coffee box photographs (product in a hand, on a shelf,
in sunlight). The eleven Word Coffee briefs currently share seven images.

## DIR-4. Chrome debugging: replaced by the UIA route (2026-11-08)

The old entry asked for a Chrome restart. It has been replaced after trying the alternatives.

**Tried, with evidence:**

1. **Version.** Chrome `156.0.8078.80`, already running (pid 28428) on the default
   user-data-dir with `Profile 6`, no `--remote-debugging-port`.
2. **Relaunch with the flag.** `chrome.exe --profile-directory="Profile 6"
   --remote-debugging-port=9222` handed off to the running instance: `http://127.0.0.1:9222/json/version`
   still refuses, and no Chrome process carries the flag. Chrome will not open a debugging
   port on a second launch while the first is alive.
3. **`chrome://inspect`.** No such toggle exists: the page discovers *existing* endpoints,
   it cannot enable one on a running browser, and Chrome ignores `chrome://` URLs passed on
   the command line to a running instance (`start chrome://inspect` opened nothing).
4. **Fallback adopted instead:** `tools/vision/chrome_uia.py` drives **Profile 6 itself**
   through UI Automation with the pixel fallback — no throwaway profile, no profile copy.
   It refuses any blocklisted window, verifies the foreground before every keystroke, opens
   its own tab, and closes that tab. 10 tests; parity gained a `uia` backend.

**What is needed now: the desktop is locked.** `GetForegroundWindow` is
`Windows Default Lock Screen` / `LockApp.exe`, so no keystroke can reach Chrome and UIA can
only read the lock window. The UIA parity backend reports exactly that and refuses
(`reports/ty/d8_parity_uia.json`).

**One action:** unlock and sign in to the Windows session, then leave it unlocked while Ty
runs. Ty needs no password and will not attempt to unlock anything.

Optional, only if you prefer CDP over UIA: with Chrome fully closed, reopen it once with

```
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --profile-directory="Profile 6" --remote-debugging-port=9222
```

Either route closes V3; UIA needs nothing from you but presence.



