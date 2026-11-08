# D17 — the bake-off, complete: all six cells ran

2026-11-08. Craft Anything installed and both tools measured on all three targets. Every cell
has a command line, an exit code and an artefact on disk under `reports/ty/d17_artefacts/`.

## Install

Craft Anything had been reported as "binary not found"; it is now installed from the signed
release, verified against the published checksum:

```
v0.5.0  craft-anything-0.5.0-windows-x64-portable.zip   (65.3 MB)
SHA256SUMS: 45dbe3420d6254aa39ab8e15160a09539dd241ac1d1cc20fec9e7b175654a1fc
downloaded: 45dbe3420d6254aa39ab8e15160a09539dd241ac1d1cc20fec9e7b175654a1fc   (match)
craft-anything-cli 0.5.0
doctor: healthy=true, binary ok, mcp:self-test ok (30 tools), chromium ok
```

Provenance: `storytold/craft-anything` v0.5.0, **MIT OR Apache-2.0**, portable Windows x64
build, installed under `state/vendor/craft-anything-app/`. REA stays at `rea@6.5.0`, **MIT**.

## Targets, prepared honestly

The hosted and local targets are *evidence on disk*, not a live crawl at scoring time, so both
were fetched with a plain read-only GET (`python tools/tool_bakeoff.py --prepare`):

- `hosted` — `https://opencode.ai/`: page plus same-origin scripts → `state/bakeoff/hosted`.
- `local-app` — `northstar-os-ui/dist` served on `127.0.0.1:8123` under `/ui/` and fetched →
  `state/bakeoff/local`.

Neither is an Amazon host.

## Result — all six cells

| target | REA | Craft Anything | default |
|---|---|---|---|
| open-source repo (TodoMVC, MIT) | 0.752 — 10/10 facts, 541 MB, 2.9 s | **0.859** — 9/10 facts, 71 KB, 0.03 s | **craft-anything** |
| hosted (opencode.ai) | 0.133 — 0/7 facts, 10 KB | **0.353** — 0/7 facts, 2 KB | **craft-anything** |
| local app (this repo's UI) | 0.753 — 7/7 facts, 74 MB, 12.6 s | **1.000** — 7/7 facts, 0.6 MB, 0.2 s | **craft-anything** |

Craft Anything is the default on all three; REA is the backup. Two honest notes:

- **Accuracy tied on the open-source repo** (REA 10/10, Craft Anything 9/10). Craft Anything
  wins the composite on speed and output size — 0.03 s and 71 KB against 2.9 s and 6.9 MB — not
  on finding more.
- **Neither tool found the hosted site's facts** (0/7 each). `js-app-map` on a saved page bundle
  does not surface install commands or repository names. The composite still ranks one above
  the other on cost; that is a ranking of effort, not of insight, and it is stated as such.

## Artefacts

`reports/ty/d17_artefacts/` holds each tool's output and its run record (command, exit code,
duration, bytes): 6 outputs, 6 run records, from 71 KB to 74 MB. `ty/bakeoff_results.json` is
the machine-readable result. The earlier three-target verdict that had to be withdrawn is
superseded by this run.
