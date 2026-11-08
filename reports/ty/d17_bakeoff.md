# D17 — REA vs Craft Anything bake-off

**Result:** both tools ran on all three targets. **Craft Anything wins all three** on the
composite, with REA as backup. Every cell below has a command line, an exit code and an
artefact — nothing here is a README claim.

- Harness: `tools/tool_bakeoff.py` (re-run: `python tools/tool_bakeoff.py --run`)
- Machine-readable result: `ty/bakeoff_results.json` (tracked)
- Raw artefacts + run records: `state/bakeoff/out/` (gitignored, tool install output)

---

## 1. Tools

| | REA | Craft Anything |
|---|---|---|
| installed version | `rea-agents@6.5.0` (`rea` on PATH) | `craft-anything-cli.exe` 0.5.0 |
| licence | **MIT** (`package.json`, `github.com/morluto/rea`) | **MIT OR Apache-2.0** dual (`LICENSE-MIT`, `LICENSE-APACHE`); the work order calls it Apache 2.0 |
| install | already installed globally via npm (no action taken) | prebuilt Windows portable zip from the v0.5.0 GitHub release, SHA-256 verified against `SHA256SUMS.txt` (`45dbe342…`); **no Rust toolchain, no build** |
| source clone | n/a | `git clone --depth 1` into `state/vendor/craft-anything` (56aa319) |
| AI key needed | no | **no** for static study (`js-app-map`); `rebuild`/`chat` would need a configured coding agent |
| deep engines | Hopper/Ghidra/IDA/JADX reported missing by `rea doctor`; built-in JS analyzer works | built-in parser only (`engine: builtin`) |

`rea doctor` exit 0 but reports `environment_healthy: false` because no native decompilers are
configured. That affects **native** work only; the JS path used here is built in.

## 2. Targets

| id | kind | how it was reached |
|---|---|---|
| `oss-repo` | open-source repo already on this machine | sparse clone of `github.com/tastejs/todomvc`, `examples/javascript-es6` (MIT), `state/vendor/todomvc` |
| `hosted` | hosted non-Amazon tool, read-only over the network | `https://opencode.ai/` page (195,128 B) + entry bundle (26,807 B) fetched with a plain read-only GET into `state/bakeoff/hosted` |
| `local-app` | this repo's own web app on 127.0.0.1 | `northstar-os-ui/dist` served at `http://127.0.0.1:8123/ui/`, index + two bundles fetched with a plain GET into `state/bakeoff/local` |

No Amazon host, no credentials, no spend, no browser automation. Chrome Connect remains the
controller for browser work; both tools analyse the same saved artefacts, which is also what
makes the comparison apples-to-apples. A headless render would add nothing to a static SPA
and would put a second browser driver on the box.

## 3. Commands, exit codes, artefacts

REA (each cell):
`rea analyze-javascript-application <target> --format json`

Craft Anything (each cell):
`craft-anything-cli.exe --deep js-app-map --input-path <target> --output-format json`
(`--deep` is required: without it the tool correctly refuses with `feature_missing`
/`clean_room` and exit 1 — that refusal is itself the evidence that the guard is real).

| target | tool | exit | seconds | artefact bytes | sha256 (16) |
|---|---|---|---|---|---|
| oss-repo | rea | 0 | 3.469 | 7,097,908 | `0b0d768174d2555f` |
| oss-repo | craft-anything | 0 | 0.044 | 72,619 | `d333f96cc260a97c` |
| hosted | rea | 0 | 9.156 | 3,405,683 | `b25b637c6d6ac173` |
| hosted | craft-anything | 0 | 0.030 | 113,618 | `2265b1d9ef4e24b1` |
| local-app | rea | 0 | 13.425 | 74,210,521 | `d9072c6df99d68ee` |
| local-app | craft-anything | 0 | 0.067 | 556,992 | `d462c67f43f1204b` |

Artefacts: `state/bakeoff/out/<tool>-<target>.json`, stderr next to them, and
`*.run.json` sidecars holding the exact command line, exit code and timing that
`--score-only` re-reads.

## 4. Scores and decision

Ground truth is a fixed fact list per target, read off the target itself (source, page, built
bundle). Accuracy = facts the tool's own output names. Detail = distinct non-hash strings,
1,000 = 1.0. Speed and token cost are normalised against the better tool; tokens are
`bytes/4`, an **estimate**, labelled as such. Weights: accuracy .40, detail .25, speed .15,
tokens .10, reliability .10.

| target | tool | accuracy | detail | seconds | tokens (est) | composite |
|---|---|---|---|---|---|---|
| oss-repo | rea | **10/10** | 1.000 | 3.47 | 1,774,477 | 0.753 |
| oss-repo | craft-anything | 9/10 | 0.595 | **0.04** | **18,154** | **0.859** |
| hosted | rea | 1/7 | 0.438 | 9.16 | 851,420 | 0.270 |
| hosted | craft-anything | **5/7** | **0.890** | **0.03** | **28,404** | **0.858** |
| local-app | rea | **7/7** | 1.000 | 13.43 | 18,552,630 | 0.752 |
| local-app | craft-anything | **7/7** | 1.000 | **0.07** | **139,248** | **1.000** |

### Decision table

| target kind | default | backup | why |
|---|---|---|---|
| open-source JavaScript repo | **Craft Anything** | REA | REA finds every fact but emits 7 MB and takes ~3.5 s; craft is 100× faster and 390× smaller, missing one internal name (`memoryStorage`) |
| hosted web tool (read-only) | **Craft Anything** | REA | craft reads page + bundle semantics (5/7 facts); REA's code-only map misses page-level behaviour (1/7) |
| this repo's local web app | **Craft Anything** | REA | equal accuracy (7/7); craft 0.07 s / 557 KB vs REA 13.4 s / 74 MB |

REA remains the backup and the better **depth** tool when the question is code structure rather
than behaviour: it surfaced all 10 TodoMVC facts, including internals craft omits. Its output
volume is the cost, and `--token-limit` exists to trim it, but the default is what was measured.

**Not tested, so not claimed:** native binaries, APK/ELF/Mach-O, and Craft Anything's `rebuild`
path. REA's native engines are not configured on this box (`rea doctor`), and `rebuild` needs a
coding agent and may spend model credits — out of scope for this unit.

## 5. Provenance rows to append

Append these two lines to the **main repo's** `provenance.csv` (outside this builder's write
scope, so they are written here verbatim instead). Header in that file is
`component,status,source,license,reviewer,notes`.

```csv
tools/rea (bake-off only),INSTALLED,https://github.com/morluto/rea v6.5.0,MIT,builder-d16 (D17),"npm install -g rea-agents@6.5.0 (already installed). Studied three targets read-only; no Amazon target, no credentials, no spend."
tools/craft-anything (bake-off only),INSTALLED,https://github.com/storytold/craft-anything v0.5.0,MIT OR Apache-2.0 (dual; the work order calls it Apache 2.0),builder-d16 (D17),"prebuilt portable zip from github.com/storytold/craft-anything/releases/tag/v0.5.0, SHA-256 verified; no Rust toolchain and no build. Studied three targets read-only; no Amazon target, no credentials, no spend."
```

## 6. Blocked / needs you

Nothing blocked the bake-off. Three honest notes for `needs_you.md`:

1. **Native/APK targets are unmeasured.** `rea doctor` reports Hopper, Ghidra 12.1.x, IDA and
   JADX unconfigured. If native reverse study matters, the owner must install a decompiler
   (Ghidra is free) and D17 must be re-run on a binary target.
2. **Craft Anything `rebuild` was not exercised.** It needs a coding agent and can spend model
   credits, which is the standing spending gate. Static study needs neither.
3. **Disk:** `state/vendor` now holds the craft-anything clone (~28 MB) and the 68 MB portable
   zip. Free space was 7.11 GB before the download and remains above the 5 GB install floor.
   The zip can be deleted once the portable folder is kept.

## 7. Evidence

```
$ python -m pytest Northstar_backend/test_tool_bakeoff.py -q
19 passed in 0.12s
```

Covered: evidence gating (non-zero exit, blocked, missing artefact, error payload, unparsable
output all become `did-not-run`), fact accuracy, hash-excluding detail count, composite
normalisation, winner + backup selection, no-result verdict, provenance header, no Amazon
target, explicit `--deep`/`--format json`, weight sum.

```
$ python tools/tool_bakeoff.py --run
… six cells, all exit_code 0 …
{"event": "written", "path": "…/ty/bakeoff_results.json"}
```
