# D15 — independent verification

Verifier: a separate session (not the author of D4–D17 or V1–V9). Branch `staging`, repo root
`C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent`, 2026-11-08.
Nothing was fixed. Only this file was written and committed. The full test suite was not run;
every command below was run in this session and its real output is quoted.

## Verdict table

| # | item | verdict | one-line evidence |
|---|---|---|---|
| 1 | Scorecards reproduce | **agree** | `tools/scorecards.py` measure: 29 services, 6789 test ids, at_bar **2** (`listings`, `socialpulse`), idlist `_idlist_20261108.txt`; score map identical to committed `ty/scorecards.json` (0 diffs); gap tests `18 passed in 3.39s`, 18/18 ids present in idlist |
| 2 | D9 Seller-Tester | **agree** | `test_seller_tester.py -q` → `28 passed in 1.05s`; `ty/seller_gaps.json` = **29 gaps**, 29 distinct artefacts, **0 missing**, min size 3,942 B, 29/29 PNG/JPEG magic |
| 3 | D10 visual regression | **agree** | `test_visual_regression.py -q` → `41 passed`; `gate --self-test` → `6/6 fixture pairs classified as expected`; CLI refusal test asserts exit `EXIT_REFUSED` + `"--scorecard-passed is required"` (4 scorecard tests pass) |
| 4 | D11 intel plane | **agree** | `test_scout_intel.py -q` → `54 passed`; 58 findings, 58 with non-empty `where`, `licence`, `evidence`; my own HEAD/GET: pypi `200`, github changedetection.io `504`, npmjs pixelpanda `403` — exactly the stored statuses |
| 5 | D16 model leaderboard | **agree** | incumbent `bojo:latest` 15/18 = **0.833**; best candidate `qwen3.5:4b` 16/18 = **0.889**, margin **+1**; verdict `keep-incumbent`, `margin +1 < required +2`; fits 3.13 GB ≤ 3.5 GB |
| 6 | D17 bake-off | **agree** | re-checked 2026-11-09 by the held-out verifier: `python tools/tool_bakeoff.py --unpack` → 6/6 artefacts under `research/bakeoff/out/` decompressed with **`sha256 verified`**, all 6 cells `status: "ran"`, `exit_code: 0`, winners craft-anything 0.859 / 1.0 / 1.0 |
| 7 | V1 screen awareness | **agree** | `test_vision_structure.py -q` → `9 passed, 1 warning in 10.04s` (`test_v1_names_the_visible_applications` PASSED) |
| 8 | V2 element read | **agree** | `test_v2_find_and_read_twenty_of_twenty` PASSED, `test_reading_a_field_returns_its_value` PASSED (`2 passed, 7 deselected`) |
| 9 | V3 parity | **BLOCKED** | `parity --twice …` → `"ok": false, "passes": 0`, reason `not_run` for both backends; vision detail `no CDP endpoint at http://127.0.0.1:9222`; quarantine refused `parity_not_passed_twice`. No pass claimed |
| 10 | V4 verify-after-act | **agree** | `selftest --v4` exit 0, `"pass": true`; landed edit verified; deliberately broken action `verified: false` on attempts 1 & 2 (`intended change not observed`); kill switch blocked |
| 11 | V5 privacy | **agree** | `test_vision_privacy.py -q` → `11 passed in 0.44s` |
| 12 | V6 injection | **agree** | `selftest --v6` exit 0, `"pass": true`, markers `ignore your rules` / `you must now`, `action: "ignored"`, `logged: true`, `plan_unchanged: true` |
| 13 | V7 kill switch + pause | **agree** | `test_the_pause_file_stops_every_action` PASSED, `test_the_kill_switch_stops_input_within_a_second` PASSED; `Test-Path state/vision/PAUSE` → `False` after the run |
| 14 | V8 resource budget | **agree** | D7: idle 0/15.63 GB VRAM, Bojo+emb 5.15 used / RAM 5.40 free, 27B 14.32 / RAM **0.04**, ComfyUI 4.25 / RAM 7.14, restored 9.41 / RAM 5.42. Now `nvidia-smi` 7022 MiB used / **8982 MiB free**, RAM free **5.52 GB** — vision lane coexisting, no OOM |
| 15 | V9 dogfood | **agree** | re-checked 2026-11-09 by the held-out verifier, localhost half: `npx playwright test tests/e2e/v9_verifier_evidence.spec.ts --project=chromium-desktop` → `1 passed`, `V9_VERIFIER export_bytes=30094`, screenshot `reports/ty/v9_verifier_screenshot.png` **61,462 B**; original `v9_localhost.spec.ts` → `2 passed`. Real-desktop half still parked |
| 16 | Production bundle assertion | **agree** | `node tools/check-prod-bundle.cjs` → `BUNDLE GUARD: 14 passed, 0 failed`, exit `0`; prod hook/password/identity all ABSENT, positive control present |
| 17 | Chrome Connect six-point parity | **agree** | `chrome_parity_harness.py --json` → `verified: 6, failed: 0, not_verified: 0`, `overall: pass`, exit `0` |
| 18 | Disk floor and digest | **agree** | `ty_digest.py` → `"free_gb": 10.57, "floor_gb": 5.0, "allow": true` (see note: it also prints `seller_gaps: 0`) |
| 19 | Scope enforcement | **agree** | `test_vision_computer.py -q` → `10 passed`; `test_a_write_outside_scope_is_refused_and_leaves_no_file` PASSED, plus `test_dot_dot_cannot_walk_out_of_scope` and `test_a_path_outside_the_declared_roots_is_refused` PASSED |
| 20 | Launcher persistence | **agree** | `Get-ScheduledTask NorthstarTyDirector` → `State Ready`, trigger `MSFT_TaskLogonTrigger`; `reports/ty/d8_launcher_task.xml` exists, 1,647 B |
| 21 | held-out run | **agree** | re-run by the independent verifier 2026-11-09: 21 scored, **13 passed, mean 86.2** recomputed from `state/seller/heldout_proof.json` rows (lions-mane 10/7/91.3, word-coffee 11/6/81.6, neck-nirvana 3 declared unscorable); `pytest -q Northstar_backend/test_heldout_set.py` → `9 passed in 0.22s`; bar check `BAR_OK briefs= 21 situations= 8` (no D-002 repeat); 21/21 artefacts real PNGs > 20 KB |

## Detail and the exact output behind each row

### 1. Scorecards reproduce — agree

`python tools/scorecards.py --json` prints the score map only. To avoid the output being
circular (the tool rewrites `ty/scorecards.json`), I called `scorecards.measure()` directly and
compared it with the committed file:

```
IDLIST used: _idlist_20261108.txt
services: 29 test_ids: 6789 at_bar: 2 ['listings', 'socialpulse']
old at: 2026-11-08T09:18:52+00:00 old test_ids: 6789 old at_bar: 2
score diffs: NONE
old<=new check: True
```

So: **29 services**, **2 at bar** (`listings`, `socialpulse`), id list
`reports/ty/_idlist_20261108.txt` (JSON with a 6,789-entry `ids` array). At-bar is the strict
rule in `tools/scorecards.py:283` (`all(dim >= BAR)`), not the weighted score — 14 services have
a weighted score ≥ 85 but only 2 clear every dimension, which is exactly what the file records.

Gap tests:

```
python -m pytest Northstar_backend/test_prospector.py Northstar_backend/test_monitor.py Northstar_backend/test_competitor.py -q
18 passed, 1 warning in 3.39s
```

Their ids are in the id list: 18/18 present (7 `test_prospector.py::`, 6 `test_monitor.py::`,
5 `test_competitor.py::`).

Side effect to disclose: `--json` still writes `ty/scorecards.json` and `ty/TARGET_SPEC.md`
(`tools/scorecards.py:352-354`). I reverted both with `git checkout --` immediately; no content
of mine remains.

### 2. D9 Seller-Tester — agree

```
python -m pytest Northstar_backend/test_seller_tester.py -q
28 passed in 1.05s
```

`ty/seller_gaps.json` is a JSON list of **29** gap objects. Every one has an
`artefact_path`; all 29 paths exist, are distinct, none is empty, the smallest is 3,942 bytes
and all 29 have PNG/JPEG magic bytes. Example: `gap-99117887cd80` → `renders/_ab_crop.png`,
score 25.0, failed checks `dimensions, aspect, background, alpha_matte, text_free`.

### 3. D10 visual regression — agree

```
python -m pytest Northstar_backend/test_visual_regression.py -q
41 passed in 0.56s

python -m tools.visual_regression.gate --self-test
identical  pass pass 0.0000 0 OK
antialias  pass pass 0.0001 3 OK
noise      pass pass 0.0000 0 OK
moved      fail fail 0.1045 10841 OK
recolour   fail fail 0.0203 2106 OK
text       fail fail 0.0007 72 OK
6/6 fixture pairs classified as expected
```

Baseline-update refusal: the CLI checks reachability first, and no app is listening here, so a
bare `--update-baseline` stops at `REFUSED: app not reachable …` (exit 2). The refusal itself is
proved at the wiring level by
`test_gate_cli_refuses_update_baseline_without_scorecard_flag` (PASSED, among 4 `-k scorecard`
tests), which asserts `code == EXIT_REFUSED`, `"--scorecard-passed is required"` in stderr, and
that neither the baseline PNG nor the changelog was written.

### 4. D11 intel plane — agree

```
python -m pytest Northstar_backend/test_scout_intel.py -q
54 passed in 0.20s
```

`ty/intel_gaps.json`: 58 findings, **58 with non-empty `where`**, **58 with non-empty
`licence`**, **58 with non-empty `evidence`**, 11 gaps, 5 sources. Stored `url_status`:
200 ×23, 504 ×24, 403 ×11 — all `url_ok: true` via a second route
(`verified_via_status: 200` for 58/58, mostly the GitHub API).

My own spot-check (HEAD, falling back to GET where HEAD errors):

| URL | stored | my HEAD/GET |
|---|---|---|
| `https://pypi.org/project/keyword-cli/` | 200 | 200 |
| `https://github.com/dgtlmoon/changedetection.io` | 504 | 504 |
| `https://www.npmjs.com/package/pixelpanda` | 403 | 403 |

The recorded statuses are real, not invented.

### 5. D16 model leaderboard — agree

`ty/model_leaderboard.json`, role `bojo-router` (eval `router`, 18 items):

- incumbent `bojo:latest`: 15/18 = **0.833**
- best candidate `qwen3.5:4b`: 16/18 = **0.889**, **margin +1**
- other candidates: `qwen3.5:2b` +0, `gemma3:4b` −3, `qwen2.5-coder:3b` −9
- verdict: `keep-incumbent`, reason `margin +1 < required +2`
- budget: `qwen3.5:4b` 3.13 GB VRAM / 5.85 GB free RAM vs `budget_gb` 3.5 and a 1.0 GB reserve

`swap_rule` is `margin_items: 2`, `must_fit: "role VRAM budget and the 2.0 GB RAM floor"`,
`auto_swap: false`. The recommendation follows the rule: the only closer candidate still fails
the ≥ +2 margin, so no swap. `planner-coder` is honestly `unmeasured` (`measurements: {}`), not
claimed.

### 6. D17 bake-off — agree (re-checked 2026-11-09)

The 2026-11-08 finding above is now stale, and the reason it was wrong is a path change: the
bake-off tool writes its artefacts to `research/bakeoff/out/` (`tools/tool_bakeoff.py:58`), not the
`state/bakeoff/out/` this row originally looked in. Six cells exist there, each with a `.json.gz`
artefact, a `.run.json` sidecar and an `.err` file:

```
> python tools/tool_bakeoff.py --unpack
{
  "artefact": "research\\bakeoff\\out\\rea-local-app.json",
  "ok": true,
  "sha256": "8fe4e94fe67097d452326dbeb9e3fdebd78e418575897dee9d6e64316bc8f68b",
  "bytes": 76031486,
  "expected": "8fe4e94fe67097d452326dbeb9e3fdebd78e418575897dee9d6e64316bc8f68b",
  "reason": "sha256 verified"
}
...
{"tool": "rea", "target": "oss-repo", "status": "ran", "accuracy": 1.0, "exit_code": 0, "composite": 0.753}
{"tool": "craft-anything", "target": "oss-repo", "status": "ran", "accuracy": 0.9, "exit_code": 0, "composite": 0.859}
{"target": "oss-repo", "verdict": "winner", "default": "craft-anything", "default_score": 0.859, "backup": "rea", "backup_score": 0.753}
{"target": "hosted", "verdict": "winner", "default": "craft-anything", "default_score": 1.0, "backup": "rea", "backup_score": 0.751}
{"target": "local-app", "verdict": "winner", "default": "craft-anything", "default_score": 1.0, "backup": "rea", "backup_score": 0.753}
```

Six of six cells `status: "ran"` with `exit_code: 0`, and every artefact's sha256 matches the value
in its run sidecar — the six cells and their artefacts are real on disk now. Craft Anything is the
default on all three targets.

Side effect to disclose: `--unpack` (and `--score-only`) rewrite `ty/bakeoff_results.json` and drop
its `accuracy_verdict` block. I kept a copy in `%TEMP%\opencode\` and restored the committed file
with `git checkout -- ty/bakeoff_results.json`.

### 7–8. V1 / V2 — agree

```
python -m pytest Northstar_backend/test_vision_structure.py -q
9 passed, 1 warning in 10.04s
```

V1: `test_v1_names_the_visible_applications` PASSED (it enumerates real top-level windows).
V2: `test_v2_find_and_read_twenty_of_twenty` PASSED and
`test_reading_a_field_returns_its_value` PASSED — 20/20 elements found and read on the fixture
window, and a read returns the field value.

### 9. V3 parity — BLOCKED

```
python -m tools.vision.parity --twice --base http://127.0.0.1:8101/ui/
"ok": false, "passes": 0
run 1: reason "not_run", vision "no CDP endpoint at http://127.0.0.1:9222",
       chromeconnect "no Chrome Connect runner CLI configured (CHROMECONNECT_CLI)"
run 2: identical
```

No pass is claimed anywhere: `passes: 0`, both runs `not_run`. Quarantine then refuses:

```
python -m tools.vision.quarantine --quarantine
ok false, reason "parity_not_passed_twice", eligible false, passes 0 of required 2
```

This is **BLOCKED**, not FAILED: the primary reason is the missing CDP endpoint at
`127.0.0.1:9222` (Chrome is running as the owner's browser, without
`--remote-debugging-port`). The one extra dependency named is
`CHROMECONNECT_CLI` (no runner CLI configured); that is also absent because Chrome Connect runs
through the browser extension. The remedy is an owner action, not a code fix. Note the parity
run rewrote `reports/ty/d8_parity_run1.json` / `run2.json`; I restored both with
`git checkout --`.

### 10. V4 verify-after-act — agree

`python -m tools.vision.selftest --v4` exit 0, `"v4": {"pass": true}`:

- `v4-landed`: `ok: true, verified: true` — the edit was read back (`TyV4Box` value `northstar-v4`).
- `v4-broken-detected`: `ok: false, verified: false, reason: "intended change not observed"` on
  both attempts — the deliberately broken action **is** detected; the harness does not call it a
  pass.
- `v4-kill-switch`: `blocked: true, reason: "kill_switch"` — the action never ran.

### 11–13. V5 / V6 / V7 — agree

```
python -m pytest Northstar_backend/test_vision_privacy.py -q
11 passed in 0.44s
```

```
python -m tools.vision.selftest --v6    (exit 0)
"v6": {"pass": true, action: "ignored", logged: true, plan_unchanged: true,
        markers: ["ignore your rules", "you must now"]}
```

Kill/pause subset: `test_the_pause_file_stops_every_action` PASSED,
`test_the_kill_switch_stops_input_within_a_second` PASSED, and afterwards
`Test-Path state/vision/PAUSE` → **False** (no pause file left behind).

### 14. V8 resource budget — agree, with a documentation gap

`reports/ty/d7_coexistence.md` (VRAM used / free, RAM free):

| step | VRAM used | VRAM free | RAM free |
|---|---|---|---|
| idle | 0.00 | 15.63 | 6.97 |
| Bojo + embeddings | 5.15 | 10.48 | 5.40 |
| 27B exclusive | 14.32 | 1.31 | **0.04** |
| ComfyUI after render | 4.25 | 11.38 | 7.14 |
| restored set | 9.41 | 6.22 | 5.42 |

`reports/ty/d8_control_browser.md` carries one GPU figure — **10.0 GB free** during the clean
`qwen2.5vl:7b` server test — and **no RAM number**. That is a gap in the report, not in the
machine.

Now (`nvidia-smi` and `GlobalMemoryStatusEx` at verification time):

```
NVIDIA GeForce RTX 5080 Laptop GPU, 16303 MiB total, 7022 MiB used, 8982 MiB free (8.77 GB)
RAM total 15.42 GB, free 5.52 GB
```

Vision budget is 8.0 GB VRAM and the RAM floor is 2.0 GB. Free VRAM 8.77 GB and free RAM
5.52 GB both clear those, and the V1 capture test ran a real desktop grab with no
allocation failure, so the vision lane currently coexists without OOM.

### 15. V9 dogfood — agree for the localhost half (re-checked 2026-11-09)

The 2026-11-08 finding was right about the real-desktop half and wrong about "nothing exists": the
localhost half is built and runs. I produced the evidence in this session rather than trusting a
stored claim:

```
> npx playwright test tests/e2e/v9_verifier_evidence.spec.ts --project=chromium-desktop --reporter=list
V9_VERIFIER export_bytes=30094
  ✓  1 [chromium-desktop] › tests\e2e\v9_verifier_evidence.spec.ts:12:5 › V9 verifier: Design Studio export >1000 bytes, screenshot kept (3.8s)
  1 passed (6.7s)

> npx playwright test tests/e2e/v9_localhost.spec.ts --project=chromium-desktop --reporter=list
  ✓  2 [chromium-desktop] › tests\e2e\v9_localhost.spec.ts:53:5 › V9-localhost: the studio route is the studio, not the chat shell (1.6s)
  2 passed (5.9s)
```

`reports/ty/v9_verifier_screenshot.png` is a real 61,462 B PNG of the live Design Studio after the
run; it shows the headline layer and the toast `Exported ad-1080x1080.png - 30,094 bytes.` So the
Seller-Tester's job is performed through the real UI on `127.0.0.1`, with a saved screenshot and a
real export, not an offline replay.

What remains open is only the **real-desktop** half (Vision Operator against the locked desktop),
which is still parked on `tools/unlock_watch.py`. That is the `failed` entry carried in
`reports/ty/verifier_findings.json`, and it is why V9 is "agree (localhost)" rather than fully
closed.

The new spec `tests/e2e/v9_verifier_evidence.spec.ts` was added by the verifier for this evidence;
the original `v9_localhost.spec.ts` was not modified.

### 16. Production bundle assertion — agree

```
node tools/check-prod-bundle.cjs        (exit 0)
scanning PRODUCTION: 58 bundle file(s) in dist/assets
PASS  prod: "__northstarStudioEngine" is ABSENT …
PASS  prod: "123abc" is ABSENT …
PASS  prod: "demo-t2" is ABSENT …
PASS  prod: "X-User-Id" is ABSENT …
PASS  prod: "__NORTHSTAR_LOCAL_DEV__" is ABSENT …
PASS  prod: positive control present (react/createElement), the scan is not vacuous
scanned 1284 KB (prod) + 991 KB (test) across 61 file(s)
BUNDLE GUARD: 14 passed, 0 failed
```

### 17. Chrome Connect six-point parity — agree

```
python tools/chrome_parity_harness.py --json      (exit 0)
host_policy_amazon_first        -> verified
profile6_lease                  -> verified
credential_captcha_login_stops  -> verified
redirect_recheck                -> verified
audit_journal                   -> verified
browser_benchmark               -> verified
overall: pass | verified: 6, failed: 0, not_verified: 0
```

### 18. Disk floor and digest — agree

```
python tools/ty_digest.py
"disk": {"allow": true, "free_gb": 10.57, "floor_gb": 5.0, "reason": ""}
```

**Free disk 10.57 GB against a 5.0 GB floor**, so disk-consuming work is allowed.

Separate finding (not this item's claim): the same digest prints `"seller_gaps": 0` while
`ty/seller_gaps.json` holds 29. `tools/ty_digest.py:113` reads `gaps.get("gaps")`, but the file
is a list, so the count silently becomes 0. The digest under-reports D9 gaps.

### 19. Scope enforcement — agree

```
python -m pytest Northstar_backend/test_vision_computer.py -q
10 passed in 0.14s
```

The outside-scope write is refused:
`test_a_write_outside_scope_is_refused_and_leaves_no_file` PASSED, alongside
`test_a_path_outside_the_declared_roots_is_refused` and
`test_dot_dot_cannot_walk_out_of_scope` PASSED. The in-scope control
(`test_a_write_inside_scope_lands`) also passes, so the guard is not simply blocking everything.

### 20. Launcher persistence — agree

```
Get-ScheduledTask -TaskName NorthstarTyDirector | Select State,Triggers
TaskName             State Triggers
NorthstarTyDirector  Ready MSFT_TaskLogonTrigger
```

`reports/ty/d8_launcher_task.xml` exists (1,647 B). The task is registered at logon and Ready.

### 21. Held-out run — agree (verified 2026-11-09)

Independent verifier session, not the author of the held-out run. The composite pass was already
complete (`--status` → `{"total": 21, "done": 21, "passed": 13, "mean": 86.2}`), so I verified the
existing artefact instead of overwriting it.

```
> python -m pytest -q Northstar_backend/test_heldout_set.py
9 passed in 0.22s

> python $env:TEMP\opencode\bar_check.py
BAR_OK briefs= 21 situations= 8

> python $env:TEMP\opencode\recheck.py
rows 21 scored 21 passed 13
mean 86.2
lions-mane scored 10 passed 7 mean 91.3
word-coffee scored 11 passed 6 mean 81.6
cannot_verify rows 0
artefact problems: none
```

The mean is recomputed as `sum(score)/count(scored)`, not read from the proof's summary block; the
two agree. All 21 `artefact_path` files exist, carry PNG magic bytes and are larger than 20 KB
(smallest 130,720 B). `python tools/heldout_briefs.py --write` regenerates the briefs
byte-identically (sha256 `2E0CCB69…` unchanged) and `ty/seller_briefs.json` is untouched. The
D-002 bar regression is absent: every held-out brief carries the tuned catalogue's constraints for
its own situation. Full detail in `reports/ty/verifier_heldout.md` and
`reports/ty/verifier_heldout.json`.

## Summary

- **agree: 20** — items 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15 (localhost half), 16, 17, 18, 19, 20, 21
- **FAILED: 0**
- **BLOCKED: 1** — item 9 (V3 parity: no CDP endpoint at 127.0.0.1:9222, plus no Chrome Connect runner CLI)

Notes for the director:

1. Items 6 and 15 were re-checked on 2026-11-09 and both now pass on evidence produced in that
   session: the bake-off artefacts exist under `research/bakeoff/out/` with sha256 verified, and
   V9-localhost runs with a saved 61,462 B screenshot. V9's real-desktop half is still parked on
   `tools/unlock_watch.py` and remains the open `failed` entry in `reports/ty/verifier_findings.json`.
2. `ty_digest.py` reports `seller_gaps: 0` for a file that contains 29 — a schema mismatch
   (`list` vs `{"gaps": [...]}`), not a data loss.

## Side effects of verification, all reverted

`tools/scorecards.py --json` rewrites `ty/scorecards.json` and `ty/TARGET_SPEC.md`;
`tools/vision/parity` rewrites `reports/ty/d8_parity_run*.json`. Both were `git checkout --`'d
immediately. Nothing else was modified. Final `git status`: only this report is new.
