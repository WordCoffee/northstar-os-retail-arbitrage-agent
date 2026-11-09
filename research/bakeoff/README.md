# D17 — reverse-study bake-off: REA vs Craft Anything (item 3)

Two tools that claim to study an application and explain how it works, run on three
non-Amazon targets, scored the same way, with every cell reproducible from this folder.

Everything here is read-only study. No Amazon host, no credentials, no paid API, no spend.
The two network targets are `https://opencode.ai/` and this repo's own local build.

---

## 1. Craft Anything — cloned, read, vetted, installed

**Source (tracked in this folder):** `vendor/craft-anything/` — clone of
`https://github.com/storytold/craft-anything` at commit
`b8371ab97bd53d7b9b10289f061eb7e3adacba09` (2026-11-09). The nested `.git` was removed so
the tree is vendored content, not a gitlink; the upstream commit is recorded here.

### What it actually is

A Rust workspace (`resolver = "3"`, edition 2024) of layered crates — `evidence`, `formats`,
`disasm`, `js`, `analysis`, `platform`, `engines`, `engine`, `ai`, `mcp`, `setup`, `ui-egui` —
with three apps: a desktop egui shell, a CLI (`apps/craft-anything-cli`) and a browser viewer.
Every user-visible capability is a `ToolSpec` in `crates/engine/src/tools/`, dispatched by id
from the GUI, the CLI, the MCP server and the AI agent alike. It statically parses a target
(ELF/PE/Mach-O/WASM/APK/ASAR/JS) and returns evidence records; it does not execute the target.
"Clean room" (default) and "Deep" modes decide whether it may read inside the original, and
`js_app_map` is listed in `crates/engine/src/clean_room.rs`, so Deep is not required for it.

**Subcommand used: `js-app-map`** (tool id `js_app_map`, toolset `javascript`) — confirmed in
`apps/craft-anything-cli/src/main.rs` (`#[command(external_subcommand)]`, `cli_name()` =
id with `-`), and listed by `craft-anything-cli commands` (321 tools; see
`vendor/craft-anything-bin/commands.json` and `js-app-map-help.txt`).

Its arguments, from `js-app-map --help`:

```
--input-path <string>   (required) app.asar, unpacked app/web bundle folder, ZIP, or one .js/.html
--format                input format (any)
--if-tampered           integrity policy
--include-node-modules  also parse code under node_modules
--limit, --offset, --max-nodes, --max-files, --max-file-bytes, --max-total-bytes
--source-paths          extra absolute paths
--output-format         json | jsonl | md | text
```

Command used for every cell:

```
craft-anything-cli.exe --deep js-app-map --input-path <target> --output-format json
```

`--deep` is kept deliberately: both tools are being asked the same thing (read the target and
map it), so both are allowed to look inside it.

### Vet verdict

```
python tools/vet_package.py --name craft-anything --ecosystem crates.io --version 0.5.0 --json
-> {"ok": true, "verdict": "clear", "malicious": [], "vulnerabilities": []}   exit 0
```

**That result is vacuous and is recorded as such.** `crates.io` returns `NotFound` for
`craft-anything`, so OSV had no package to match against. It is not evidence of safety. The
real controls here are (a) the code read above, and (b) an exact checksum:

```
craft-anything-0.5.0-windows-x64-portable.zip
computed SHA-256 45dbe3420d6254aa39ab8e15160a09539dd241ac1d1cc20fec9e7b175654a1fc
SHA256SUMS.txt   45dbe3420d6254aa39ab8e15160a09539dd241ac1d1cc20fec9e7b175654a1fc  MATCH
```

REA's vet is substantive, because `rea-agents` is a real npm package:

```
python tools/vet_package.py --name rea-agents --ecosystem npm --version 6.5.0 --json
-> {"ok": true, "verdict": "clear", "malicious": [], "vulnerabilities": []}   exit 0
```

### Install method

Prebuilt release binary, not a `cargo build`: this box has no Rust toolchain (`rustc`/`cargo`
absent), and the release is the artefact upstream ships. `craft-anything-cli.exe` v0.5.0
(38.7 MB) lives in `vendor/craft-anything-bin/craft-anything-0.5.0-windows-x64-portable/`.

The `.exe` files and the 68 MB zip are **not** committed (see `.gitignore`); `run_all.ps1`
downloads them from the pinned v0.5.0 release and checks them against `SHA256SUMS.txt`, which
is committed next to them. REA was already installed globally (`rea@6.5.0`); nothing was
installed for it.

Both tools are appended to `provenance.csv`.

---

## 2. Targets

| target | what it is | how it got here |
|---|---|---|
| `oss-repo` | TodoMVC `examples/javascript-es6` (MIT) | shallow sparse clone of `github.com/tastejs/todomvc` at `ff43b02e59dfa604386bb382034b2cd07c2bcd8a`, tracked in `targets/todomvc` |
| `hosted` | `https://opencode.ai/` (non-Amazon, public) | page + same-origin scripts fetched with a plain read-only GET into `targets/hosted` |
| `local-app` | `northstar-os-ui/dist` served on `127.0.0.1:8123` under `/ui/` | `npm ci && npm run build`, served by the fetch step, page + entry scripts saved into `targets/local` |

The hosted fetch needs a real `User-Agent` — opencode.ai answers 403 to Python's default
`Python-urllib/3.14`. `prepare_targets()` now sends
`northstar-bakeoff/1.0 (read-only study)` and skips `data:` URLs. No browser is driven: both
tools read the same saved bytes, so the comparison is apples-to-apples and no Chrome profile
is involved.

Ground-truth facts are read off the targets, not guessed, and were re-checked against the saved
artefacts in this run:

- `oss-repo`: `Controller Model View Store setView addItem removeItem toggleComplete showActive memoryStorage` (all in `src/*.js`)
- `hosted`: `anomalyco/opencode`, `npm install -g @opencode/cli`, `docs`, `install`, `sdk`, `github`, `opencode`
- `local-app`: `/design-studio`, `/listings`, `Northstar`, `product-finder`, `beta-ops`, `golden-goose`, `/documents`

---

## 3. The six cells

Scored by `tools/tool_bakeoff.py` (reused, not forked). Weights: accuracy 0.40, detail 0.25,
speed 0.15, token cost 0.10, reliability 0.10. `seconds` is wall clock for the tool process;
`bytes` is the artefact size and tokens are labelled as a bytes/4 estimate.

| target | tool | exit | artefact | bytes | sec | accuracy | detail units | composite |
|---|---|---|---|---|---|---|---|---|
| oss-repo | rea | 0 | `out/rea-oss-repo.json` | 7,097,922 | 3.50 | 1.0 (10/10) | 5430 | 0.753 |
| oss-repo | craft-anything | 0 | `out/craft-anything-oss-repo.json` | 72,633 | 0.04 | 0.9 (9/10) | 595 | 0.859 |
| hosted | rea | 0 | `out/rea-hosted.json` | 96,013,591 | 22.90 | 1.0 (7/7) | 51,241 | 0.751 |
| hosted | craft-anything | 0 | `out/craft-anything-hosted.json` | 702,110 | 0.11 | 1.0 (7/7) | 3543 | 1.000 |
| local-app | rea | 0 | `out/rea-local-app.json` | 76,031,486 | 13.29 | 1.0 (7/7) | 44,043 | 0.753 |
| local-app | craft-anything | 0 | `out/craft-anything-local-app.json` | 642,948 | 0.22 | 1.0 (7/7) | 3154 | 1.000 |

Exact command lines are in each `out/<tool>-<target>.run.json` (`command`, `command_line`,
`exit_code`, `seconds`, `bytes`, `sha256`). The two commands, with the target substituted:

```powershell
rea analyze-javascript-application <target> --format json

research\bakeoff\vendor\craft-anything-bin\craft-anything-0.5.0-windows-x64-portable\craft-anything-cli.exe `
  --deep js-app-map --input-path <target> --output-format json
```

### Winner per target

| target kind | default | score | backup | score | why |
|---|---|---|---|---|---|
| open-source repo | **craft-anything** | 0.859 | rea | 0.753 | ~90x faster, ~98x smaller output; one fact missed (`memoryStorage`) |
| hosted, read-only | **craft-anything** | 1.000 | rea | 0.751 | all 7 facts; ~203x faster and ~137x smaller on the same bytes |
| local app (127.0.0.1) | **craft-anything** | 1.000 | rea | 0.753 | all 7 facts; ~61x faster and ~118x smaller |

REA is never wrong here — it finds every fact on all three targets — but it pays for that in
size and time: 96 MB of JSON for a marketing page, ~23 s for one hosted target, and `detail`
is capped at 1.0 while the other lane reaches the same accuracy with 3 KB of strings. That is
the trade recorded in `ty/bakeoff_results.json`: Craft Anything as default, REA as backup for
when the question needs depth the smaller graph does not carry.

---

## 4. Reproduce

From the repo root. Windows, PowerShell.

```powershell
# all six cells, fetching targets and building the UI first
.\research\bakeoff\run_all.ps1

# one cell (what an independent verifier re-runs)
.\research\bakeoff\run_all.ps1 -Tool craft-anything -Target hosted
.\research\bakeoff\run_all.ps1 -Tool rea -Target oss-repo

# reuse the committed targets, skip the UI build
.\research\bakeoff\run_all.ps1 -SkipFetch -SkipBuild
```

`run_all.ps1` downloads and checksum-verifies the Craft Anything binary if it is absent,
restores the TodoMVC target if it is missing, builds the UI if `dist/` is absent, then runs
`tools/tool_bakeoff.py --run`. It exits non-zero unless every requested cell shows
`status=ran`, `exit_code=0` and a non-empty artefact. A filtered run writes
`out/run_all.partial.json` so it cannot overwrite the six-cell decision file.

Raw steps, if you want them individually:

```powershell
python tools/tool_bakeoff.py --unpack        # restore *.json.gz, verify against run sidecars
python tools/tool_bakeoff.py --score-only    # re-score what is on disk, no subprocess
python tools/tool_bakeoff.py --prepare       # re-fetch the hosted and local targets
python tools/tool_bakeoff.py --run           # all six cells -> ty/bakeoff_results.json
```

### Committed artefacts

REA writes tens of megabytes per target, so the tool output is committed as
`out/<tool>-<target>.json.gz` and the uncompressed file is **not** in git. `--unpack`
decompresses each one and compares its SHA-256 with the `sha256` field in the matching
`*.run.json`, refusing to write a file that does not match. Six of six verified in this run.

This mattered: the first pass could not have been verified. `run_cell` wrote the artefact with
`write_text`, which on Windows turns `\n` into `\r\n`, so the file on disk never matched the
bytes that were hashed. It now writes bytes (`write_bytes`) and the sidecar hash is true.

---

## 5. What did not run, and why

- **Craft Anything built from source:** no `cargo`/`rustc` on this machine, and the release
  binary is the same code. Vendored source is still here and was read.
- **GPG verification of `SHA256SUMS.txt`:** no `gpg` on this machine. Integrity rests on the
  HTTPS fetch plus a checksum taken from a separately downloaded file on the same release.
- **`--include-node-modules`:** off. Neither target ships a `node_modules` tree, so it would
  only add noise.
- **Browser-driven capture:** deliberately not used. Chrome Connect is the controller for
  browser work and a static SPA gains nothing from a render; both tools read the same saved
  bytes instead.
- **REA `analyze-web-bundle`:** not used. It captures a live page itself, which would mean
  driving a browser and would break the shared-evidence comparison.

## Licences

- Craft Anything: MIT OR Apache-2.0 (dual; the work order calls it Apache 2.0). `LICENSE-MIT`
  and `LICENSE-APACHE` are in the vendored tree and in the binary folder.
- REA: MIT.
- TodoMVC: MIT.
- Northstar OS UI (`targets/local`): this repository's own code.
- opencode.ai page and scripts (`targets/hosted`): fetched read-only for study; not vendored
  for redistribution, kept here only as the bake-off's evidence.
