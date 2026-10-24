# Termly CLI install — 2026-10-19

## What was installed
`@termly-dev/cli@1.9.5` (npm, MIT, repo `termly-dev/termly-cli`, ~316 stars) added as a **devDependency** of the root `package.json`.

Package identified from npm search: the only maintained "termly cli" on npm. It is the AI-session-mirroring CLI (`termly.dev`), **not** the termly.io cookie-consent vendor, which ships no CLI.

## Install
```
npm install --save-dev @termly-dev/cli   # root of project
added 108 packages, removed 1 package, audited 109 packages in 6s
```

## Verification
| Check | Result |
|---|---|
| Binary linked | `node_modules/.bin/termly` → `bin/cli.js` |
| `npx --no-install termly --version` | `1.9.5` |
| `npx --no-install termly --help` | 9 commands: setup, start, status, stop, list, tools, config, cleanup, help |
| `npm audit --omit=dev` | 0 vulnerabilities |
| `npm audit` (incl. dev) | 2 moderate, inside the CLI's dependency tree |
| node_modules gitignored | yes (`.gitignore:1`) |

## Side effect (investigated, not caused by install)
`package-lock.json` was pruned of ~172 stale entries (`eslint`, `express`, `nodemon`, `prettier`, …). Those packages were **already absent from disk** — `node_modules/@eslint` mtime is 2026-09-26, three weeks before this install. The lockfile was simply out of sync with reality; npm rewrote it to match. No working dependency was removed.

## Not done (deliberately)
`termly setup` / `termly start` were **not** run. Setup is an interactive flow that registers this machine with termly.dev and mirrors AI session traffic to their cloud + mobile app. That is an operator decision, not an install step.

## Rollback
```
npm uninstall @termly-dev/cli
```
