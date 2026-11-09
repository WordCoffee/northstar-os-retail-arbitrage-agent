# Item 3 — D17 reverse-study bake-off (reproducible)

Branch `ty/item3`. Scope: `research/bakeoff/**`, `tools/tool_bakeoff.py`,
`ty/bakeoff_results.json`, `provenance.csv`, this report.

## Verdict

Both tools ran on all three non-Amazon targets with exit code 0 and a non-empty artefact.
**Craft Anything wins every target type**; REA is the recorded backup. REA is not wrong
anywhere — it found every ground-truth fact on all three targets — but it emits 76–96 MB of
JSON per target and takes 3–23 s, against 0.04–0.22 s and 72 KB–702 KB.

| target | default | score | backup | score |
|---|---|---|---|---|
| open-source repo | craft-anything | 0.859 | rea | 0.753 |
| hosted, read-only | craft-anything | 1.000 | rea | 0.751 |
| local app (127.0.0.1) | craft-anything | 1.000 | rea | 0.753 |

## Six cells

| target | tool | exit | artefact | bytes | sec | accuracy |
|---|---|---|---|---|---|---|
| oss-repo | rea | 0 | `research/bakeoff/out/rea-oss-repo.json` | 7,097,922 | 3.50 | 10/10 |
| oss-repo | craft-anything | 0 | `research/bakeoff/out/craft-anything-oss-repo.json` | 72,633 | 0.04 | 9/10 |
| hosted | rea | 0 | `research/bakeoff/out/rea-hosted.json` | 96,013,591 | 22.90 | 7/7 |
| hosted | craft-anything | 0 | `research/bakeoff/out/craft-anything-hosted.json` | 702,110 | 0.11 | 7/7 |
| local-app | rea | 0 | `research/bakeoff/out/rea-local-app.json` | 76,031,486 | 13.29 | 7/7 |
| local-app | craft-anything | 0 | `research/bakeoff/out/craft-anything-local-app.json` | 642,948 | 0.22 | 7/7 |

The one miss: Craft Anything's graph does not name `memoryStorage` on TodoMVC, so 9/10 there.
Exact command lines, exit codes and per-run sha256 are in `out/*.run.json`.

## What was fixed

A previous run recorded artefacts that could not be verified. Two causes, both fixed here:

1. **Text-mode writes.** `run_cell` used `write_text`, so Windows stored `\r\n` and the file on
   disk never equalled the bytes that had been hashed. It now uses `write_bytes`; all six
   artefacts hash-match their sidecars.
2. **No reproducible evidence trail.** Vendor and targets were under `state/` (gitignored).
   They now live under the tracked `research/bakeoff/`, all six artefacts are committed as
   `*.json.gz` with a `--unpack` step that re-checks each sha256, and `run_all.ps1` rebuilds
   the whole sweep (or one cell) with a checksum-pinned binary download.

Also fixed: the hosted fetch now sends a real `User-Agent` (opencode.ai returns 403 to
`Python-urllib`) and skips `data:` URLs.

## Vet

- `rea-agents@6.5.0` (npm): clear, no malicious advisories, no vulnerabilities. Substantive.
- `craft-anything@0.5.0` (crates.io): clear, **but the crate is not published to crates.io**
  (`NotFound`), so that check is vacuous and is recorded as vacuous. The controls are the code
  read (`Cargo.toml`, CLI `main.rs`, `js_tools.rs`) and an exact SHA-256 match against the
  release's own `SHA256SUMS.txt`
  (`45dbe3420d6254aa39ab8e15160a09539dd241ac1d1cc20fec9e7b175654a1fc`).

## Install

Craft Anything v0.5.0 windows-x64 portable release, checksum-verified, no cargo build (no Rust
toolchain on this box). Binary under `research/bakeoff/vendor/craft-anything-bin/`, source
vendored at `b8371ab97bd53d7b9b10289f061eb7e3adacba09` under `research/bakeoff/vendor/craft-anything/`.
REA 6.5.0 was already installed; nothing was installed for it.

## Not run

- Build from source: no `rustc`/`cargo` present.
- GPG check of `SHA256SUMS.txt`: no `gpg` present. Integrity = HTTPS + checksum file.
- `--include-node-modules`: no `node_modules` in either target.
- REA `analyze-web-bundle`: would drive a browser and break the shared-evidence comparison.
- No Amazon host, no credentials, no paid API, no spend, at any point.
