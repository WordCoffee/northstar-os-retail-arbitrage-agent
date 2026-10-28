# REA regression gate - fails on a regressed OR lost metric.
#
#   .\tools\verify-rea.ps1                 # quick probes + focused tests
#   .\tools\verify-rea.ps1 -Full           # also warp + video probes
#   .\tools\verify-rea.ps1 -WithBuild      # add `npm run build`
#
# Exit code 0 = no regression, 1 = regression / lost metric.
param(
    [switch]$Full,
    [switch]$WithBuild
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    $argv = @("tools/rea_regress.py", "--with-tests")
    if (-not $Full) { $argv += "--quick" }
    if ($WithBuild) { $argv += "--with-build" }
    python @argv
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
