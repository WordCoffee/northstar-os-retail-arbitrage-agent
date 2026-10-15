# First audit pass with the D-S2 tools - 2026-10-14

- **Standing line:** 0 new / 0 known-active / 231 allowlisted (before this pass; nothing in this pass added tracked files).
- Commands run and observed results:
  - `uv export --frozen --no-emit-project --directory Northstar_backend` -> requirement export from the product lock (used as pip-audit input).
  - `pip-audit -r <export>` -> **"No known vulnerabilities found"** (exit 0). Audits the pinned Northstar_backend dependency set against advisory data.
  - `semgrep --config p/python --quiet --disable-version-check northstar` (with `SEMGREP_SEND_METRICS=off`) -> **exit 0, no findings reported**. Scope: the new `northstar/` packages only.
  - `trivy config Dockerfile.api` -> **0 misconfigurations**.
  - `trivy config docker-compose.lightpanda.yml` -> not scanned by `trivy config` in this run (recorded as a tool limitation to revisit).
  - (earlier) `trivy fs --scanners secret northstar` -> no findings (exit 0); trivy uses entropy heuristics - low-entropy fake samples are intentionally not flagged.

## Non-claims (explicit)
- No container-image vulnerability scan yet (first vuln scan downloads trivy's vuln DB - not done).
- `Northstar_backend/` legacy code was NOT semgrep-scanned in this pass (follow-up).
- No fixes were applied; findings-based follow-ups (if any later) are separate decisions.