# Unit 2026-11-11 — lease, security classification, and the folded fixes

Owner: Tyrone. Mode: autonomous, no reports between cycles. Everything below is a command that
was run or a count that was measured; nothing is asserted from memory.

---

## 1. Queue lease: there was no live director, and there had not been for days

Step (1) of the resume order, measured before any work:

| check | result |
|---|---|
| `state/director/director.pid` | pid 8864, written `2026-11-11T00:32:40Z` — **process gone** |
| live `--agent director` session | **none** |
| `NorthstarTyDirector` task | **Running** since 2026-11-09 09:59:35, last result `267009` |
| launcher children | **every one dies in under a second**: `Agent not found: "director"` — 73 identical errors in `logs/ty_director_stream.jsonl`, restarts every five minutes since 2026-11-10T19:40 |
| `NorthstarTysWatchdog` | Ready, last result `-1073741510` (control-C) — not keeping anything alive |
| queue lock | none exists; the pid file **is** the lease (`scripts/ty_director.py:find_director`) |

**Conclusion:** no other director held the queue, so this session claimed every unclaimed job. The
lease was re-pointed at the opencode process serving this session (pid 21844) and proved with a
model-free tick:

```
python scripts/ty_director.py --once
{"state": "running", "director_pid": 21844, ...}
```

**Defect fixed:** `opencode.jsonc` defined `tys`, `verifier` and `research`, but **not `director`**.
The launcher has been starting a lane that does not exist since it was installed, so the director
program only ever ran when a human opened a chat. A `director` agent is now defined with
`model: opencode-go/deepseek-v4.1-flash` (pinned, never a fallback) and the repository guard passes:

```
python tools/guard_agents.py
agents: director, research, tys, verifier
OK
```

## 2. Step (3)/(4): the three daemons and the dev stack

- **Launcher:** `NorthstarTyDirector` Running; `pythonw.exe scripts\ty_director.py` pid 12256 alive.
- **Unlock watcher:** **was not running** (last log line 2026-11-09T15:30). Restarted, pid 11100.
  `python tools/ty_unlock_checks.py --status` → `{"locked": true, "reason": "no foreground window"}`,
  so V3/V9-desktop stay parked on the owner, as ordered.
- **RAM governor:** consulted by the launcher on every start decision; `state/director/ram_gate.jsonl`
  and `ram_min_daily.json` were written at 18:32 local by `ty_director:start`.
- **Dev stack:** 127.0.0.1:8000 (uvicorn, pid 11664) and 127.0.0.1:8101 (vite, pid 15472), both
  healthy (`/health` 200, `/ui/` 200). **Caveat, recorded rather than papered over:**
  `dev-start.pids` holds five pids of which three are gone, and it does not contain vite's live pid.
  The stack is up and loopback-only, but its provenance is only partly provable from that file. Not
  restarted mid-session; the pid-file defect is filed below.

## 3. `stage_guard`: a refusal is typed now, everything else stops the run

The old contract tolerated bare `ValueError`/`RuntimeError`. That is tolerance by exception *type*,
and it is how a bug gets a refusal's clothing: a numpy shape error **is** a `ValueError`, and a
`KeyError` wrapped in a `RuntimeError` was swallowed the same way.

New contract (`tools/seller_tester/stage_guard.py`):

- `StageRefused` — the only exception a stage may use to decline. Recorded, run continues.
- everything else — `ValueError` and `RuntimeError` included — becomes `StageFailed` and aborts.
- `declined("name", fn, ...)` converts a **named** third-party step's `ValueError`/`RuntimeError`
  into `StageRefused` at the call site, so every tolerated failure has a name.

`tools/seller_tester/generators.py` was updated at exactly five call sites (`fit_aspect`,
`infographic`, `panel_warp`, `cutout`, `rgba_png_bytes`, `place_product`, `compose_label`,
`warp_label`); `raise RuntimeError("the cutout is empty")` became a `StageRefused`.

Tests, measured:

```
python -m pytest Northstar_backend/test_stage_guard.py -q
17 passed in 0.81s
python -m pytest Northstar_backend/test_seller_tester_composite.py Northstar_backend/test_stage_guard.py -q
38 passed in 2.63s
```

Two of the 17 are behavioural, not source-string assertions: a `ValueError` raised from an
**undeclared** step (`_resize_png`) aborts the run, and a `ValueError` from a **declared** cutout is
recorded as a refusal and the plate is kept.

## 4. PPC's real primary action, on the PPC surface

The registry listed AdPilot's actions and the UI's own primary button was:

```jsx
onClick={() => toast('Bulk actions operate on the local campaign records below …', 'info')}
```

A toast is not an action. The real workflow already existed in the backend
(`POST /amazon-files/upload` → `/proposals` → `/proposals/{id}/approve` → `/{uid}/write` →
`/change/{cid}/download`, with version, checksum and a round-trip proof) and in one UI component
(`design-studio/AmazonFiles.jsx`). AdPilot now mounts that component behind its primary button —
one implementation, no re-implementation — with `data-testid="ap-bulk-action"`.

Evidence:

```
cd northstar-os-ui && npm run build
✓ built in 1.52s   (0 errors)
npx playwright test tests/e2e/ppc_primary_action.spec.ts --project=chromium-desktop
1 passed (3.3s)
npx playwright test tests/e2e/ppc_primary_action.spec.ts --project=chromium-mobile
1 passed (2.8s)
```

The spec proves the button is a toggle with honest state (`aria-expanded`), that nothing mounts until
it is pressed, that the panel contains a real file input, and that the panel names the transaction
(upload → bulk). **Not yet proven at this timestamp:** an actual file upload through the panel with
a live session, because `studio_account` requires a real session and the dev lane serves a demo one
for the legacy surface only. That is the next unit (`ppc-upload-live`), not a claim.

The "save campaign plan" write stays, but it is now the *secondary* record: the persisted artefact a
seller returns to is the written change file, which the backend stores with a version and checksum.

## 5. Security: the classifications the owner asked for (counts only)

`tools/history_credential_classify.py` reads every added line on all 189 refs (1,715 commits) and
prints counts. No user, password, token, address or line is recorded; the only strings it writes are
hostnames, and only for a URL that reaches a real host.

### Credential URLs — 88 total

| class | count |
|---|---|
| fixture / reserved / example host | 42 |
| documentation placeholder (`host`, `dbhost`, `postgres`, `bar.com`, …) | 28 |
| localhost / 127.0.0.1 | 15 |
| **real host** | **2** |
| unparseable | 1 |

The two real-host URLs: `github.com` (1) and `www.packify.ai` (1).

### Credential assignments — 535 total

| class | count |
|---|---|
| code reference (`os.environ`, `getenv`, `process.env`, a call) | 274 |
| literal value, no host on the line | 188 |
| placeholder value | 57 |
| **line also names a real host** | **17** |
| line names a fixture host | 1 |

The 17 real-host lines name `github.com` (10), `www.aboutamazon.com` (3), `www.packify.ai` (2),
`api.scrape.do` (1), `www.w3.org` (1). Three of those are credential endpoints; two are a corporate
link and an XML namespace on a line that also carries a token-shaped assignment.

**Rotation entries filed:** `needs_you.md` `SEC-1` names `github.com`, `www.packify.ai` and
`api.scrape.do` with counts. No Amazon request was made to reach that conclusion — the host came out
of local git history.

### Non-machine emails — 674 total (935 − 261 machine)

| class | count |
|---|---|
| business / vendor domain (corporate or matched vendor list) | 452 |
| owner handles (`wordcoffee`, `northstar`, `mogra`, `t2holdings`, …) | 93 |
| third-party personal (free-mail domain, no owner handle) | 85 |
| business, matched exactly | 44 |

### Phones — 319 total

| class | count |
|---|---|
| business (same line names a brand) | 266 |
| owner (same line names an owner brand) | 2 |
| US/CA format, unattributed | 51 |

`unattributed` is deliberate. A phone number carries no owner; attributing the 51 would be guessing,
and this report will not guess.

## 6. The other nine public WordCoffee repos

`tools/wordcoffee_repo_scan.py` shallow-clones each repo, reads text files under 400 KB, and writes
`reports/ty/wordcoffee_repos_scan.md` + `.json`. Counts only; no value, line or filename is recorded.

| repo | size KB | Pages | files | text scanned | secret shapes | recommendation |
|---|---|---|---|---|---|---|
| `word-coffee` | 12,464 | yes (CNAME `www.word-coffee.com`) | 38 | 13 | 0 | **candidate for private** — a 12 MB public storefront, business content, no credential shapes |
| `Word-coffee.co` | 1,553 | yes | 144 | 47 | 0 | can stay public |
| `house-finder` | 77 | yes | 5 | 5 | **12** | **make private now** — 12 `generic_secret` shapes in 5 files |
| `Word-coffee-website` | 86 | yes | 8 | 8 | 0 | can stay public |
| `WordCoffee.co` | 17 | yes | 4 | 4 | 0 | can stay public |
| `Amazon-Ads-Bid-Adjustment-Calc` | 4 | yes | 2 | 2 | 0 | can stay public |
| `WordCoffee` | 2 | no | 1 | 0 | 0 | can stay public |
| `wordcoffee.github.io` | 0 | yes | 1 | 1 | 0 | can stay public |
| `Wordcoffee-website` | 0 | no | 0 | 0 | 0 | empty — make private or delete |

`house-finder`'s 12 hits are `generic_secret` (a `password`/`token` assignment shape), not
private keys or provider tokens; a 5-file, 77 KB calculator site is far more likely to contain form
code than a live credential. The recommendation is still "make private now" because the check that
would prove otherwise (reading the values) is exactly what this mode refuses to do. The owner can
confirm in one look.

## 7. History rewrite plan, extended, and a remap tool that is tested

`reports/ty/history_rewrite_plan.md` now carries: the commit-map procedure (and the fact that the
September mirror **lost** its map, so it must be re-captured and composed), the 11-step quiet-window
procedure with a check per step, the local re-pointing rules (worktrees first, then tracking, then
reset), the hash-remap plan, and an evaluation of **delete-and-recreate-private**.

Measured blast radius (`python tools/remap_hashes.py --scan`): **90 files cite a hash — 39 full
40-char hashes, 2,160 short candidates** across `reports/ty/*`, `ty/*.json`,
`state/director/*.json`, `docs/*.md`, `tests/BASELINE.json` and `00_STATE.json`.

`tools/remap_hashes.py` has `--scan` / `--check` / `--apply`, rewrites only map-covered hashes,
skips ambiguous prefixes, reports unmapped hashes instead of keeping them silently, and writes a
`.remap-backup` per file. Tests: `Northstar_backend/test_remap_hashes.py` → **7 passed**.

**Recommendation in the plan: delete-and-recreate-private, with a full `git bundle` first.** The
rewrite's two hardest steps exist only to preserve history that holds nothing a seller needs and
five pages we want gone. Owner-only either way.

## 8. `main` at `ef9cad1d`, rescanned with the fixed config and no file-size cap

```
gitleaks dir . --config .gitleaks.toml --max-target-megabytes 0 --redact
scanned ~116,137,899 bytes (116.14 MB) in 5.62s
leaks found: 5
```

3,816 tracked files, **8 files over 1 MB included**, 5 findings, all three credentials:

| file | line | rule |
|---|---|---|
| `FirstNorthstarautomationchat.md` | 1143 | generic-api-key |
| `FirstNorthstarautomationchat.md` | 1148 | generic-api-key |
| `FirstNorthstarautomationchat.md` | 1291 | generic-api-key |
| `FirstNorthstarautomationchat.md` | 1296 | generic-api-key |
| `autothink-ui-chat-export.md` | 7852 | github-pat |

Large-file scanning changed nothing: the totals are identical with a 0 MB cap, and no finding lives
in a large file. Artefact: `reports/ty/main_rescan_ef9cad1d_large.json`.

## 9. Why prompt-only briefs score exactly 90.0 — measured, and the first answer was wrong

The score is a weighted sum of **binary** checks normalised by the weights of the graded checks
(`tools/seller_tester/scorers.py:combine_checks`). A prompt-only brief does not grade
`reference_subject`, so the denominator is exactly `1.00`:

```
dimensions 0.20 + aspect 0.10 + background 0.20 + subject_fill 0.20
+ alpha_matte 0.10 + file_size 0.05 + text_free 0.15 = 1.00
```

One failing check at weight 0.10 gives `100 × 0.90 / 1.00 = 90.0`. That part is arithmetic.

The **first explanation in this unit was wrong**: it said `alpha_matte` was being failed because a
text-to-image plate has no alpha channel. The check's own detail says otherwise — the failing mode is
`white_matte`, the brightness passes, and the **border variance** fails:

| brief | border mean (≥ 249) | border std (≤ 6.0) | brief std limit |
|---|---|---|---|
| PO-001 | 252.1 | **7.19** | 6.0 |
| PO-003 | 251.8 | **7.68** | 6.0 |
| PO-004 | 252.1 | **7.17** | 6.0 |
| PO-006 | 250.8 | **9.00** | 4.0 |
| PO-011 | 251.2 | **8.43** | 6.0 |
| PO-012 | 251.7 | **7.79** | 6.0 |

**Root cause:** `generators.flat()` returned `background.mode != "uniform"`, so a **white-matte**
brief was composited onto the *generated scene* rather than a flat canvas. The scene edge is bright
but grainy; that is a real compositing defect, not a rubric constant.

**Fixed:** `flat()` now means a flat field (uniform value, or `matte.mode == white_matte`), the compose
step writes a flat canvas at the brief's level, and an alpha matte is no longer graded on a
full-generation route (an opaque plate cannot produce one; it would be a constant). Three tests in
`test_seller_tester_composite.py` plus one in `test_seller_tester.py`; `92 passed` across the three
seller suites.

Rescored the **existing** (pre-fix) artefacts with the current scorer:

| brief | situation | score | passed | failed checks (weight) |
|---|---|---|---|---|
| PO-001 | white_background_main | 90.0 | yes | alpha_matte (0.10) |
| PO-002 | lifestyle | 63.6 | no | subject_fill (0.20) |
| PO-003 | scale_reference | 90.0 | yes | alpha_matte (0.10) |
| PO-004 | bundle_multipack | 90.0 | yes | alpha_matte (0.10) |
| PO-005 | background_swap | 70.0 | no | background (0.20), alpha_matte (0.10) |
| PO-006 | series_consistency | 90.0 | yes | alpha_matte (0.10) |
| PO-007 | infographic | 100.0 | yes | — |
| PO-008 | packaging_mockup | 100.0 | yes | — |
| PO-009 | white_background_main | 100.0 | yes | — |
| PO-010 | lifestyle | 63.6 | no | subject_fill (0.20) |
| PO-011 | scale_reference | 90.0 | yes | alpha_matte (0.10) |
| PO-012 | bundle_multipack | 90.0 | yes | alpha_matte (0.10) |

**Six** briefs sit on exactly 90.0 in this run (the count is "how many fail only that check", so it
moves with the outputs; the order's "four" was an earlier run). Prompt-only: **n 12, pass 9, mean
86.4** — a per-mode number, never blended.

**The fix cannot show up until the twelve are re-rendered.** They were produced by the old branch, so
`86.4` stands as the measured value of the artefacts on disk. The re-render is queued as
`rerender-prompt-only`, not claimed.

Per-mode table, unchanged by this unit and stated without a headline blend:

| mode | n | pass | mean |
|---|---|---|---|
| prompt-only | 12 | 9 | 86.4 |
| stored-reference | 12 | 11 | 91.8 |
| uploaded-reference | 21 | 16 | 90.0 |


## 10. `keys_rotated` watcher

`tools/keys_rotated_watch.py` polls every **300 s with no model call** for
`state/security/keys_rotated.json`; on appearance it runs, in order: `retire_chat_exports.py
--retire`, the gitleaks gate, and `promote_closure.py --dry-run` (a throwaway-worktree promotion
test that does not touch `main`). It records `state/security/keys_rotated_result.json`, is
idempotent per marker digest, and honours `STOP` / `PAUSE`. Running now (pid 4480); status:

```
python tools/keys_rotated_watch.py --once
{"state": "waiting", "reason": "no keys_rotated.json"}
```

## 11. What this unit did NOT do (so the next one starts honest)

- **Seller reference coverage is still 12 of 56 briefs.** The rank-1 blocker is unchanged.
- **ux-06…ux-09 are not verified live on desktop and iPhone 12 WebKit.** `ty_unlock_checks.py
  --status` reports `locked: true`, so the live walk cannot run; the order parks it, and it stays
  parked rather than skipped.
- **The visual regression gate was not re-run** on the final shell.
- **PPC upload was not exercised end-to-end** through the new panel with a real session (see §4).
- **The promotion closure test has not run**, because it is gated on the rotation marker.

## Defects filed

- **D-008** — `alpha_matte` is graded on prompt-only briefs, where no transparent cutout can exist;
  it caps the route at exactly 90.0. Fix in the brief or the export, never by lowering the weight
  silently.
- **D-009** — `dev-start.pids` is stale: three recorded pids are gone and the live vite pid is not
  recorded, so "started by `scripts/dev-start.ps1`" cannot be proven from the file alone.
- **D-010** — the launcher was pointing at a non-existent agent for days; a launcher that cannot
  start its lane must surface as a red heartbeat within one interval, not as 73 silent JSON errors
  in a stream file nobody reads.
