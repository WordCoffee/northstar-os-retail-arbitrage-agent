# Bake-off (item 3 / D17) — independent verification

Verifier session, 2026-11-09. Branch `staging` at `433c5d87`. I did not build this bake-off.
Nothing was fixed. The only file written inside the repo is this report.

Method: read the scorer, re-derived every metric from the committed artefacts without
importing `tools/tool_bakeoff.py`, re-fetched the hosted target myself, and re-ran two cells
in a throwaway detached worktree at `433c5d87` (`state/worktrees/verify-bakeoff`, removed
afterwards).

| # | item | verdict | command | key output |
|---|---|---|---|---|
| 1 | hosted target is a live capture | **AGREE** | `python -c "urllib.request … https://opencode.ai/"` | `status 200`, `final https://opencode.ai/`, `bytes 194113`, `sha256 4b016d4d43bda7daa0730d1d6a0d83302328bcdc891122c2a4342ecb5d3e378` — equal to `_fetch.json` and to `research/bakeoff/targets/hosted/index.html` |
| 2 | accuracy is against ground truth; weights; composite vs accuracy | **AGREE** (one wrong explanatory string) | `python <own rescore of out/*.json.gz>` | all six cells recomputed exactly: accuracy 10/10, 9/10, 7/7, 7/7, 7/7, 7/7; detail 5430/595/51241/3543/44043/3154; composites 0.753/0.859/0.751/1.000/0.753/1.000 — every one equals the recorded value. Weights 0.40/0.25/0.15/0.10/0.10 |
| 3 | two cells reproduce | **AGREE** | `powershell -ExecutionPolicy Bypass -File research/bakeoff/run_all.ps1 -Tool craft-anything -Target hosted` and `… -Tool rea -Target oss-repo` | both `EXITCODE=0`, `status ran`, `exit_code 0`, non-empty artefact; byte-for-byte sha differs only by the injected absolute input path + content ids (see below) |
| 4 | artefacts are tracked, not in a worktree | **AGREE**, with a caveat | `git ls-files research/bakeoff \| wc -l` | `977` tracked files; `research/bakeoff/out` = 18 tracked (6 `*.json.gz`, 6 `*.run.json`, 6 `*.err`); a fresh checkout of `433c5d87` contained all 18, and `python tools/tool_bakeoff.py --unpack` restored 6/6 with `sha256 verified`, exit 0 |
| 5 | the crates.io vet was vacuous | **AGREE** | `https://crates.io/api/v1/crates/craft-anything` and `…/crates?q=craft-anything` | `HTTP 404 Not Found`; search `{"crates":[],"meta":{"total":0}}` — the crate is not published, so an OSV match had nothing to match |

No item is **FAILED** and none is **NOT VERIFIABLE**.

## 1. The hosted target

`research/bakeoff/targets/hosted/` holds 26 tracked files whose names are derived from
URL paths by `prepare_targets()` (e.g. `_build_assets_routes-index-D7RFA9SK.js`,
`favicon-v3.ico.html`, `stylesheet_entry-client-…css`) — the fetch routine's own naming, not
something a person types. My own read-only GET (same `User-Agent` the code uses,
`northstar-bakeoff/1.0 (read-only study)`) returned the identical 194,113 bytes and the
identical sha256, and all seven declared `hosted` facts
(`anomalyco/opencode`, `npm install -g @opencode/cli`, `docs`, `install`, `sdk`, `github`,
`opencode`) are present in the tracked `index.html`. A hand-written file could not hash to the
live page.

Two caveats, neither of which changes the verdict:

- `_fetch.json` is **not tracked**. `research/` is ignored (`.gitignore:134`) and the bake-off
  files were force-added individually; `_fetch.json` was missed. `git log --all --
  research/bakeoff/targets/hosted/_fetch.json` is empty. It exists only in this working tree,
  written at `07:29:01Z` by the untracked `tools/bakeoff_fetch_proof.py`, i.e. **after** the
  `06:59:53Z` run it is offered as proof for.
- Because of that, a checker on a fresh checkout has the page but not the fetch record. The
  sha comparison above is the substitute, and it passes.

## 2. What the composite actually measures

`WEIGHTS = {"accuracy": 0.40, "detail": 0.25, "speed": 0.15, "tokens": 0.10,
"reliability": 0.10}` (`tools/tool_bakeoff.py:61`), and `accuracy = len(hits)/len(facts)`
with `fact_hits` doing a case-insensitive substring search over the tool's own output
(`:368`, `:406`). Each target's `facts` list is read off the target itself — I checked all
17 facts against the tracked targets: all 10 `oss-repo` names occur in
`targets/todomvc/examples/javascript-es6/src/*.js`, all 7 `local-app` names in
`targets/local/*`, all 7 `hosted` names in `targets/hosted/index.html`.

**60% of the composite is not accuracy** (detail 25% + speed 15% + tokens 10%), plus 10%
reliability that is a constant 1.0 for any cell that runs, so in practice the discriminating
part of the composite is 40% accuracy against 50% cost/size and 25% output volume.

- **Yes, one target's composite winner differs from its accuracy leader.**
  `oss-repo`: accuracy leader is **rea** (10/10 vs craft-anything 9/10, `memoryStorage`
  missed), composite winner is **craft-anything** (0.859 vs 0.753).
  `hosted` and `local-app` are accuracy ties (7/7 both) and craft-anything wins on cost.
- `detail` is effectively saturated: it is `min(1.0, units/1000)`, and rea reaches the cap on
  all three targets. It discriminates only once, on `oss-repo` (595 vs 5430 units).
- Minor inaccuracy worth correcting: the uncommitted `accuracy_verdict` block in
  `ty/bakeoff_results.json` says of `oss-repo` *"both surfaced the same ground truth"*. That
  is false — craft-anything is 9/10 there and `facts_missing` is `["memoryStorage"]`. The
  verdict itself (`disagree: true`) is right; the sentence is not.
- `ty/bakeoff_results.json` is currently **modified and uncommitted** in this working tree
  (only the `accuracy_verdict` block added; the six cells and decisions match `HEAD`). The
  block was generated by the untracked `tools/bakeoff_accuracy.py`. My independently computed
  numbers agree with it.

## 3. Reproducing two cells

Environment: detached worktree of `433c5d87`, no edits to `staging`. The commands were run
exactly as documented; no extra or undocumented arguments were needed.

| cell | exit | artefact | bytes | sha256 | accuracy | detail |
|---|---|---|---|---|---|---|
| craft-anything / hosted, reproduced | 0 | `research/bakeoff/out/craft-anything-hosted.json` | 702,128 | `442926c0e040276e1bc5f3a23aa3d73a2f5c2dd5603925cfea3a8ec052800294` | 7/7 | 3543 |
| craft-anything / hosted, recorded | 0 | same path, 702,110 B in `out/craft-anything-hosted.json.gz` | 702,110 | `824ce4c521b0242a46c8244912eedbfdc3c12d70c7aa9fb0441b5005b0b30944` | 7/7 | 3543 |
| rea / oss-repo, reproduced | 0 | `research/bakeoff/out/rea-oss-repo.json` | 7,097,940 | `29160e9d92fd326ee282cbc673cecae4ae2d709cdd593782d2e01ea94f74ca5a` | 10/10 | 5430 |
| rea / oss-repo, recorded | 0 | same path, 7,097,922 B in `out/rea-oss-repo.json.gz` | 7,097,922 | `d91da29c2ec55c93598dd979fb305b2d50e641b00902d9920683955735643256` | 10/10 | 5430 |

The sha256 values **do not** match, and cannot: both tools embed the absolute input path and
derive content ids (`ev_<sha256>`) from it. The recorded runs used
`…\state\worktrees\item3\…`; mine used `…\state\worktrees\verify-bakeoff\…`, which is exactly
9 characters longer and occurs twice — i.e. the **+18 bytes** seen in both artefacts. After
masking the absolute root and every 32+ hex id, both artefacts are **structurally identical**
to the recorded ones (`json` compare: `True` for both cells), and every scored metric
(accuracy, facts, detail units, bytes, composite for the two-tool file) is identical.

Measured seconds differ (0.604 s vs 0.113 s; 5.23 s vs 3.499 s) — wall clock on a busy box,
not a claim of the bake-off.

Two things a reader should know:

- A **single-tool** filtered run normalises speed and tokens to 1.0 because
  `add_composites` normalises across the tools that ran on the target. So the filtered run's
  `"default": "rea", "default_score": 1.0` is an artefact of there being one tool, and is not
  a counter-result to the six-cell decision (`craft-anything` 0.859 vs `rea` 0.753). The
  script does write the filtered run to `out/run_all.partial.json`, not over
  `ty/bakeoff_results.json`, as it claims.
- The three prerequisites `run_all.ps1` needs on a genuinely clean checkout are **not**
  committed: the 68 MB `craft-anything-0.5.0-windows-x64-portable.zip` / the extracted
  `craft-anything-cli.exe`, and `northstar-os-ui/dist`. `Get-CraftAnything` downloads and
  sha256-checks the release if absent (documented in README §4, not in the script header),
  and `Get-Dist` runs `npm ci && npm run build` **even for a hosted-only cell** because
  `prepare_targets()` always fetches both network targets. `-SkipFetch -SkipBuild` does not
  help from a fresh checkout: with no `dist/` it throws
  `no build at …northstar-os-ui\dist and -SkipBuild was given`.
  For this verification I avoided both the download and any install by copying the extracted
  binary (and `dist/`) from the existing `state/worktrees/item3`, after checking the zip's
  hash myself: `45DBE3420D6254AA39AB8E15160A09539DD241AC1D1CC20FEC9E7B175654A1FC`, which is
  the entry for `craft-anything-0.5.0-windows-x64-portable.zip` in the committed
  `vendor/craft-anything-bin/SHA256SUMS.txt`. The claim in the report is correct.

## 4. Tracking

`git ls-files research/bakeoff` → **977** files; `git ls-files research/bakeoff/out` → **18**
(6 `*.json.gz`, 6 `*.run.json`, 6 `*.err`). The uncompressed `*.json` are deliberately not
committed (96 MB for `rea-hosted` alone), so **`out/*.json` do not exist in a checkout until
`--unpack` runs** — in the fresh worktree the directory held only the 18 compressed/sidecar
files. `python tools/tool_bakeoff.py --unpack` there reported 6/6 `sha256 verified`, exit 0,
and wrote all six `.json` back at the recorded sizes (702,110 / 642,948 / 72,633 / 96,013,591 /
76,031,486 / 7,097,922).

That check is not a rubber stamp: after my two re-runs replaced two sidecars, the same
`--unpack` failed those two cells with `sha256 does not match the run sidecar` and exit 1.
The verification is real.

The sidecars record absolute paths under `state/worktrees/item3` (where the builder ran), which
is why a fresh run cannot byte-match; the artefacts themselves are in the checkout, which is
what the item asks.

## 5. The craft-anything vet

`GET https://crates.io/api/v1/crates/craft-anything` → **404**. `GET
https://crates.io/api/v1/crates?q=craft-anything&per_page=5` → `200`,
`{"crates":[],"meta":{"total":0}}`. The crate is unpublished, so `vet_package.py` (which
queries `https://api.osv.dev/v1/query`, `tools/vet_package.py:30`) returned "clear" for a
package that does not exist. **The report's word "vacuous" is correct.** I did not run
`vet_package.py` itself: it calls `api.osv.dev`, outside the two sites this verification is
allowed to reach, and the registry answer settles the question on its own. Integrity here
rests on the checksum match in §3, which I confirmed independently.

## Summary

The recorded result is true as recorded: both tools ran to exit 0 on all three non-Amazon
targets, the artefacts are committed and hash-verify, the accuracy figures are a real
fraction of target-derived facts, and Craft Anything is the composite default on every target
with REA as backup. The composite is a cost-weighted decision, not an accuracy ranking —
accuracy is 0.40 of it, and on `oss-repo` the composite winner is the *less* accurate tool.
