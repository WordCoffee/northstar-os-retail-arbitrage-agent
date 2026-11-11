# Independent verification — `block7-verification`

Verifier lane, 2026-11-11. Repo `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent`,
branch `staging`, HEAD `80eaf72c` ("handoff: cycle 30 - UI defects and seller depth merged;
19 of 29 at the bar and the rest of the zeros are real").

I built none of this. Read-only everywhere except this file. No browser, no dev stack, no
GPU, no installs, no `git add` / `git commit`. One temporary `git worktree` was created under
`%LOCALAPPDATA%\Temp\opencode\ns-verify-b7` for claim 6 and removed afterwards (confirmed gone
from `git worktree list`).

---

## 1. Claims, commands, real output

| # | claim | command | real output | verdict | proof |
|---|---|---|---|---|---|
| 1 | production assertion green | `python Northstar_backend/production_assert.py --json` | `"ok": true`, `"summary": {"advisory": 10, "fail": 0, "pass": 12, "skip": 0}`, `generated_at 2026-11-11T17:43:31Z` | **AGREE** | quoted verbatim below the table |
| 2 | readiness suites pass | `python -m pytest Northstar_backend/test_production_health.py Northstar_backend/test_production_sqlite_backup.py -q` | **`8 passed, 21 errors`, exit 1** — every error `PermissionError: [WinError 5] Access is denied: 'C:\Users\T2Hol\AppData\Local\Temp\pytest-of-T2Hol'` (error at *setup*, `tmp_path` fixture) | **FAILED as issued** (environment, not code) | same command with `--basetemp`: **`29 passed, 2 warnings in 2.57s`**, exit 0 |
| 3 | seller sample depth 21/19/0 | `python -m tools.seller_tester services` | `"scored": 21, "passed": 19, "refused": 0`, `by_path` listing 6/6, ppc 5/5, golden_goose 5/3 mean 95.6, research 5/5 — **exit 1** | **AGREE** (numbers exact; exit 1 is the two recorded findings) | `state/seller/services_proof.json` |
| 3a | seller 100.0 / 95.6 / 95.6 | `ty/scorecards.json`, `ty/seller_scores.json` | `listingforge 100.0` (6 service-path outputs), `goldengoose 95.6`, `golden-goose 95.6` (5 outputs each, paths `golden_goose`) | **AGREE** | `ty/seller_scores.json` `service_path.paths` |
| 3b | design-studio 96.2 / 32 pictures, unblended | same | evidence string: *"32 Seller-Tester outputs (generated/composite), mean 96.2, 32 passed; 40 replayed artefact(s) excluded as context (mean 22.1); 5 service-path output(s) (mean 100.0) are a separate population and are not averaged in here"* | **AGREE** | if the 5 ppc rows were blended the mean would be `(32×96.2 + 5×100)/37 = 96.7` — a +0.5 delta that did **not** happen |
| 3c | GG-002/GG-003 kept as findings | read artefacts + `reports/ty/lane_services.md` | `state/seller/services/golden_goose/GG-002.json`, `GG-003.json` present; `lane_services.md:60-76` names both (`reject_tier_dropped`, `best_row_is_first`) | **AGREE** — recorded, not deleted | `ls state/seller/services/golden_goose` → 5 files |
| 4 | 29 services, 19 at/above 85, 10 below | `python -c` over `ty/scorecards.json` | `total 29`, `score>=85: 19`, `score<85: 10`, mean **82.97**, `seller = 0.0` on **6** | **AGREE on the numbers**, with a naming defect (below) | weakest dims for the ten are listed in §2 |
| 4a | no borrowed population | same | seller is non-null only on `listingforge` (service-path `listing`), `goldengoose` + `golden-goose` (service-path `golden_goose`), `design-studio` (generated pictures). `listings`, `adpilot`, `offerchisel`, `socialpulse`, `product-finder` stay `0.0` with "no path exists" / "would be a false attribution"; `research` 5/5 is explicitly unattributed | **AGREE** | `ty/seller_scores.json` `service_path.attribution` |
| 5 | registry integrity | `python -m tools.registry.repair_citations --check`; `python -m tools.registry.build --check`; `pytest Northstar_backend/test_service_registry.py -q` | exit **0** (silent) / exit **0** `registry, tool list, workspaces and gaps agree` / **`19 passed, 1 warning in 1.05s`** | **AGREE** | also green inside the fresh worktree |
| 6 | fresh-checkout claim | `git status --porcelain`; `git ls-files`; fresh `git worktree add --detach HEAD` | status = 4 modified `reports/ty/*` **plus `?? dev-start.pids.json`** (untracked, **not** gitignored, mtime 10:52:30 today); all three imported files **TRACKED**; worktree suite `129 passed, 2 skipped, 1 warning in 37.54s` | **FAILED on "only reports churn"** (minor); fresh-worktree claim **AGREE**, and better than reported (129 vs 124) | `git ls-files`: `tools/seller_tester/services.py`, `tools/seller_tester/stray_report.py`, `northstar-os-ui/scripts/sync-workspaces.mjs` all tracked |
| 7 | rollback discipline | `git tag --list 'ty-dir-*'` (41), `git tag --list 'rollback/pre-*'` (25), `git rev-parse <unit>^` vs `git tag --points-at` | 4 units that changed code today have **no** `rollback/pre-*` tag; the registry repair commit is untagged; `ty-dir-D7` message describes a different unit | **FAILED** | gaps named in §3 |

### Claim 1, quoted verbatim

```json
  "ok": true,
  "schema": "northstar.production_assert.v1",
  "strict": false,
  "summary": {
    "advisory": 10,
    "fail": 0,
    "pass": 12,
    "skip": 0
  }
```

The 10 advisories are all registered and honest: 44 findings outside shipped code, 11 479
tracked files not scanned, 4 import-time keys and 3 hosted keys documented as gaps, plus two
secrets-scan scope notes. Nothing advisory hides a failure.

### Claim 2 — what a 200 on `/readyz` requires

`Northstar_backend/main.py:1004-1010` returns `200` iff `production_health.readiness_snapshot()["status"] == "ready"`, else `503`. `readiness_snapshot()`
(`production_health.py:169-192`) runs six checks and fails when any **critical** one is not ok
(`production_health.py:179-182`):

| check | critical? | what a 200 therefore requires |
|---|---|---|
| `rate_limit_posture` | always | rate-limit posture valid (`production_health.py:50-61`) |
| `redaction` | always | log redaction wired (`:64-83`) |
| `data_dir_writable` | always | the data directory is writable (`:86-91`) |
| `ui_build` | **only in production-like envs** (`:96-109`) | `northstar-os-ui/dist/index.html` + `dist/assets` present; outside production/staging a missing build is non-critical |
| `foundation_store` | always for sqlite; **non-critical** for a `postgres*` `DB_URL`/`FOUNDATION_DB_URL` (`:112-122`) | sqlite store exists, opens read-only, `SELECT 1` works, `PRAGMA quick_check == ["ok"]` |
| `live_posture` | always | `live_gate.live_posture_problems()` is empty (`:158-166`) |

So: **200 = all six, with `ui_build` waived outside production-like environments and
`foundation_store` waived on Postgres.** `failed_checks` names any that failed. The test
(`test_production_health.py:144-152`) documents the contract honestly: 503 on an
unprovisioned tree "is the contract, not a bug", and it skips with the check's own reason
rather than passing by luck. Both skips in the fresh worktree are exactly this.

---

## 2. The ten below 85, and their weakest dimension (claim 4)

| service | score | weakest | that dimension |
|---|---|---|---|
| `towncrier` | 55.0 | seller | 0.0 |
| `beta-support` | 63.2 | complete | 0.0 |
| `offerchisel` | 67.0 | seller | 0.0 |
| `adpilot` | 67.0 | seller | 0.0 |
| `socialpulse` | 67.0 | seller | 0.0 |
| `beta` | 74.7 | complete | 0.0 |
| `beta-signup` | 74.7 | complete | 0.0 |
| `beta-ops` | 74.7 | complete | 0.0 |
| `product-finder` | 77.0 | seller | 0.0 |
| `listings` | 77.0 | seller | 0.0 |

**Naming defect (the one real seam in claim 4).** `ty/scorecards.json` carries two different
notions of "at the bar":

- `score >= 85` (weighted score) → **19 of 29** — this is what the claim, `lane_services.md:126`
  ("16 at or above the 85 **score**"), and the HEAD commit message mean;
- `meets_bar` in the same file → **4 of 29** (`hub`, `prospector`, `keyword-tracker`,
  `profitability`), because `tools/scorecards.py:390` is
  `meets = all(value["score"] >= BAR for value in applicable.values())` — **every** dimension
  ≥ 85, not the weighted score.

Eight services sit at 86.2 with `meets_bar: false` (`ledger`, `auctioneer`, `autothink`,
`thewatch`, `rankledger`, `rivalboard`, `account`, `foundation`, `jobs`, `keywords`) purely
because `complete` or `contract` is below 85. Both readings are defensible; quoting "19 at the
bar" while a reader opens the file and sees `meets_bar: false` on 15 of them is the defect.
`lane_services.md:128-130` is the only place that gets this exactly right ("Four services are
at the bar before and after").

## 3. Claim 7 — the rollback gaps, named

`ty-dir-*` tags: 41. `rollback/pre-*` tags: 25. Tag→commit subjects match their unit except
`ty-dir-D7`, whose message is "checkpoint before D8-D17 batch: worktree state at 2026-11-08" and
which points at the **same commit** as `rollback/pre-d8-20261108` (`e5dccbba`) — a pre-existing
mislabelling, not introduced today.

Units that changed code today with **no `rollback/pre-*` tag before them**
(`git rev-parse <tag>^` → `git tag --points-at`):

| unit | tag commit | parent | tag on parent |
|---|---|---|---|
| `block4-seller-tests` | `10:47` | `e48b7cd0` | **none** |
| `block3-workspaces` | `10:59` | `77707671` | **none** |
| `block5-hardening` | `11:21` | `80b8b2ff` | **none** |
| `ui-defects` | `11:41` | `cd86fae0` | **none** |
| `seller-depth` | `11:42` | `00d857b7` | `ty-dir-ui-defects` (recoverable via the previous unit tag) |

Also: `149ca718 registry: citations repaired from the code…` changed code today and carries
**no tag at all** (no `ty-dir-*`, no `rollback/pre-*`).

The last `rollback/pre-*` created before this block is `rollback/pre-d027-20261111` (10:12),
itself created **retroactively** "after the independent verifier found the tag the report cited
did not exist" — i.e. the same omission has now happened twice, and the countermeasure did not
stick. That is the process gap a release claim would trip over.

---

## 4. Overstatements

Read against my own re-measurement:

1. **`lane_block4.md:38` — "`python -m tools.seller_tester services` (exit 0 …)".** Stale. The
   same command now exits **1** (19 of 21 passed, GG-002/GG-003). The five-brief table that
   follows was accurate for its epoch; the exit code no longer is, and a CI reader would take
   the harness as green.
2. **"19 at or above the 85 bar"** (this brief, and the HEAD commit message). Not an
   overstatement of the score, but it collides with `meets_bar: false` on 15 services in the
   same artefact. Say "19 at or above an 85 weighted score; 4 meet every dimension's 85 bar".
3. **`reports/ty/handoff.md:115` — "124 passed, 2 skipped" on a fresh worktree.** *Understated*,
   not overstated: at HEAD the eight suites give **129 passed, 2 skipped**. The two extra units
   added five tests.
4. **`lane_block5.md`** — 12/12/0/10 exit 0, `68 passed`, `218 passed + 19 subtests`: I
   reproduced all three **exactly** (68 in 26.04s, 218 + 19 subtests in 12.65s). No
   overstatement. It also documents the `--basetemp` workaround, which is why its run was green
   while my as-issued run of claim 2 was not.
5. **`lane_services.md`** — 21/19/0, means 100.0/95.6/95.6, `seller = 0.0` 9→6, mean 82.97,
   design-studio's 5 ppc rows "reported and not blended": reproduces exactly. Its only weak
   spot is the phrase "at the bar" at `:128`, which it then uses correctly for the strict four.
6. **`lane_ui_defects.md` and `lane_block3.md`** — the e2e headlines (`6 passed (18.2s)`,
   `56 passed`, `28 passed` ×2) are **outside my lane**: verifying them needs a browser, which I
   am not permitted to start. The spec files exist (`tests/e2e/a11y/tabbar_a11y.spec.ts`,
   `tests/e2e/workspace-tabs.spec.ts`), the referenced lines exist, and `lane_block3.md`
   already declares its own three pre-existing e2e failures. **Unverified, not disputed.**

Residual risk not in any report: `lane_block5.md:15-25` records that an autonomous lane
(`tools/tys_launcher.py`, `_revert_candidate()`) reverted the block5 work at 16:11:59Z and the
module is still installed. That path can revert a verified tree again between verification and
release.

## 5. Verdict

The substance holds: the production assertion is genuinely green with ten honest advisories, the
seller dimension now measures a real sample instead of a zero, the blended/unblended boundary is
enforced in code and visible in evidence (`96.2` vs the `96.7` a blend would have produced),
the registry is self-consistent, and a fresh worktree of HEAD runs the eight suites green at
**129 passed / 2 skipped** with every imported file tracked. Three things block a clean release
claim. **The rollback gap is the worst**: four code-changing units today (`block4`,
`block3`, `block5`, `ui-defects`) plus the registry repair have no restore point, and the
`pre-d026`/`pre-d027` tags prove this omission recurs and that the retroactive fix was not
turned into a habit. Second, the documented readiness command does not run on this box — any
test that needs `tmp_path` dies at setup on an inaccessible
`C:\Users\T2Hol\AppData\Local\Temp\pytest-of-T2Hol` (`WinError 5`), so `--basetemp` must be part
of the written procedure, not folklore discovered per lane. Third, `dev-start.pids.json` sits
untracked and unignored in the tree, so `git status` is not clean enough to underwrite a
"fresh checkout" statement without a caveat. None of these is a fabricated number; all three are
bookkeeping that a release claim would otherwise silently inherit. Fix the tmp-dir ACL, add the
five missing rollback points or state plainly that unit tags are the restore points, gitignore
the pid file, and relabel "19 at the bar" — then the claim is defensible on this evidence.
