# Tooling adoptions - D-S2 (2026-10-14)

- **Standing line:** 0 new / 0 known-active / 231 allowlisted. Tests: 219/219 (unchanged - tooling lives outside the repo).
- **What ran:** version resolution (PyPI JSON, npm view, GitHub releases), trivy download + SHA256 verification against the release checksums file, `uv tool install` x3, `npm i -g` x1, `opencode mcp add` (context7), verification commands.

## Verification evidence
- **trivy 0.76.0** - `sha256 VERIFIED: 7b4762a5a5326cb4b83dfd2bb5d9aaf15a1ed867c75cad7dd8b38840a28e7be6`; `trivy --version` -> `Version: 0.76.0`; `trivy fs --scanners secret northstar` -> exit 0, no findings ("No issues detected with scanner(s)").
- **pip-audit 2.10.1** - `pip-audit --version` -> `pip-audit 2.10.1` (uv tool).
- **semgrep 1.181.0** - `semgrep --version` -> `1.181.0` (uv tool; executables `semgrep`, `pysemgrep`).
- **schemathesis 4.31.1** - `schemathesis --version` -> `schemathesis, version 4.31.1` (uv tool).
- **promptfoo 0.124.1** - `promptfoo --version` -> `0.124.1` (npm global).
- **context7 MCP** - `opencode mcp add context7 --global --url https://mcp.context7.com/mcp` -> "MCP server context7 added to opencode.json"; in-session tools `resolve-library-id` + `query-docs` connected.

## Non-claims / follow-ups
- trivy's first vulnerability scan will download its vuln DB (not run yet); image/FS vuln scans not yet performed.
- schemathesis has no demo run yet (needs a running app); promptfoo has no eval config yet; semgrep rules demo not run (registry rules need network; run with `SEMGREP_SEND_METRICS=off`).
- CI/`security_checks.ps1` wiring NOT done (follow-up decision).

## Machine changes (reversible)
- Tool installs per the docs table; OpenCode global config gained the context7 MCP entry (backup `opencode.json.bak.20261014b`). PATH untouched. Nothing else.
- Also observed via `opencode mcp list`: the app project's `playwright` MCP entry fails with its retirement notice (spawns nothing - by design) and `northstar-gateway` is disabled by design; both left unchanged.