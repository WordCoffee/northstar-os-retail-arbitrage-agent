#!/usr/bin/env bash
# Northstar OS — All Tests Runner (A5) — thin wrapper.
# The canonical runner is scripts/run_all_tests.ps1 (PowerShell; works natively on
# the Windows host and via powershell-core elsewhere). This wrapper just locates
# and executes it so the same command form works everywhere:
#
#   bash scripts/run_all_tests.sh          (or: ./scripts/run_all_tests.sh)
#
# Exit code is the runner's: 0 = GREEN (baseline match, known failures only),
# 1 = regression / mismatch. No CI integration — local runner only.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v powershell.exe >/dev/null 2>&1; then
    PS="powershell.exe"
elif command -v powershell >/dev/null 2>&1; then
    PS="powershell"
else
    echo "ERROR: no powershell runner found (needed for scripts/run_all_tests.ps1)" >&2
    exit 1
fi
exec "$PS" -NoProfile -File "$SCRIPT_DIR/run_all_tests.ps1" "$@"