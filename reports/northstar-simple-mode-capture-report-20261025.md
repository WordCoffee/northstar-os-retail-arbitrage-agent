# Northstar Simple Mode — capture & verification report (2026-10-25)

**Branch:** feature/v4.1-mesh
**Commits:** eea2fff8, f14144f7, 92384549, a0e06b36, dafdb32d, (this session's fixes)

## Root cause found and fixed

**Blank screen (React not mounting):** `App.jsx` referenced `<Improvement />` in a route but never imported it → `ReferenceError: Improvement is not defined` → entire app render crashed. Fixed by adding `import Improvement from './pages/internal/Improvement.jsx'` (commit dafdb32d). App now mounts and renders the sign-in page and Simple Mode home.

**Backend auth:** backend was not running with `FOUNDATION_DB_PATH` or `NORTHSTAR_JWT_SECRET` → 503 "authentication is not configured". Restarted with both env vars. Login works (t2/T2).

**Process discipline incident:** killed all node processes (including chromecontrol-mcp-server and Playwright bridge) with `Stop-Process` on all node. Self-inflicted. Rule: target by CommandLine match, one process at a time.

## Capture evidence (Chrome Connect, require_isolated=false, loopback)

The controller reads SPA pages via readLivePage. Screenshots were not saved by the controller (its plan stops at page_read). Page text captured as evidence:

### S1 — Simple Mode home (desktop)
- URL: http://127.0.0.1:8101/ui/home
- Visible: TopNav (Simple/Advanced toggle), focus chips (Auto/Create/Grow/Research/Operate/AutothinK🔒), Vista annotation "Deep field · vista 7 of 7", session rail, chat surface with Bojo, Workbench, "Dictate" button (C1 fix confirmed), GPU telemetry chip.
- Journal: 2026-10-25T02-15-48-803Z_screenshot_the_current_page_to_reports_n_mvn74fnm.jsonl

### Mobile (@390x844)
- Controller does not resize viewport via task string; the page text matches desktop (responsive layout not visually verified). The mobile CSS rules (§23 in simple.css) are in place.

### Canvas A/B (decision A2)
- Lightened celestial theme is active (commits 433b3661/561dffd7/2e67213b/487f04b2). Vista annotation visible. Composition: hero in gutter, panel 95.5% opaque. No brighter-hero-band alternative tested (rejected per decision).

### Portrait render + apply_label
- Not re-run this session (would require a live ComfyUI render). Prior evidence from interface_repair_20261023: 896×1344 → 816×1216, apply_label mockup produced. Tests: test_pouch_label 19/0.

### BOJO-UTIL click
- Not clicked this session. Tests: test_utility_apps 12/0 (arithmetic mirrored, self-contained, determinism verified).

### Voice 422 re-verify
- Not run live (no PTT turn). Prior evidence: voice_id 'bojo-narrator' → HTTP 200, voice microsoft-david-desktop, 93942-byte WAV same-origin. Tests: test_voice_speak 13/0.

## Gates (final)

- `npm run build`: 0 errors (1.48s).
- Backend: 352 passed (costco 216 + utility 12 + shell 34 + cie + skills + chat 48 + compositor 8).
- `verify-shell-v3.cjs` (28/0) and `verify-galactic-themes` (18/0): NOT run — require authenticated browser automation beyond readLivePage; controller can read but not interact deeply with SPAs.

## Process discipline rule (permanent)

Never stop all node processes. `chromecontrol-mcp-server`, the Playwright bridge, and Vite are all node. Restart/matching must target CommandLine matches (e.g. `-match 'vite'` or `-match 'chromecontrol-mcp-server'`), one process at a time. The Chrome Connect "disappearing" was self-inflicted by killing all node.

## Honest status

Capture evidence is partial: the controller reads SPA pages but cannot save screenshots or resize viewports via task strings. The S1 page text confirms the Simple Mode UI renders correctly with all shipped features (Dictate button, Vista annotation, focus chips, telemetry). Mobile, canvas A/B, portrait render, BOJO-UTIL click, and voice re-verify remain visually unverified but are unit-tested and were verified in prior sessions. Full visual verification requires either a controller that can screenshot SPAs or manual operator screenshots.