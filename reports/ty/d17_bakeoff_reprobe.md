# D17 re-probe, 2026-11-08 — the earlier bake-off result was not reproducible

The independent verifier (D15) found that the six bake-off cells had commands and exit codes
in the report but **no artefacts on disk**: the builder wrote them under `state/bakeoff/`, which
is gitignored, inside a worktree that was removed after the merge. By the rule the work order
sets — *a bake-off result is "tool did not run" unless there is a command line, an exit code
and an output artefact* — the earlier verdict cannot stand.

## What the re-probe actually did

```
python tools/tool_bakeoff.py --run --out reports/ty/d17_reprobe.json
```

Target 1 (`oss-repo`) did not exist in the merged tree either, so it was restored first:

```
git clone --depth 1 --filter=blob:none --sparse https://github.com/tastejs/todomvc state/vendor/todomvc
git sparse-checkout set examples/javascript-es6
```

## Result

| target | REA | Craft Anything | verdict |
|---|---|---|---|
| open-source repo (`todomvc/examples/javascript-es6`, MIT) | **ran**, exit 0, accuracy 1.0 (10/10 facts), 2.9 s, 7.1 MB artefact | **not installed** (`binary not found`) | REA default |
| hosted non-Amazon tool (opencode.ai, read-only GET) | did-not-run, exit 1 | not installed | **no result** |
| local app (`127.0.0.1:8123/ui/`) | did-not-run, exit 1 | not installed | **no result** |

The artefact for the cell that did run is tracked at
`reports/ty/d17_artefacts/rea-oss-repo.json` (7.1 MB) with its run log beside it, so it cannot
vanish with a worktree again.

The earlier claim — Craft Anything default on all three targets with composites
0.859 / 0.858 / 1.000 — came from a run whose outputs no longer exist and whose Craft Anything
install no longer exists. It is **withdrawn**, not contradicted: it may have been true in that
worktree, and it is not evidence now.

## State of D17

- **Open-source repo:** REA is the default by measurement, with an artefact to cite.
- **Hosted and local-app:** no result. REA exits 1 on both in this environment (its hosted
  path needs a provider configuration; the local app has no built `dist/` to serve), and
  Craft Anything is not installed.
- **To finish D17:** install Craft Anything (`storytold/craft-anything`, Apache-2.0), build
  `northstar-os-ui/dist`, and re-run all three targets. Nothing here costs credits: the
  scorer estimates tokens as bytes/4 and starts no model.
