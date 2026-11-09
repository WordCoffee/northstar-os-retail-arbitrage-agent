# run_all.ps1 - reproduce the D17 bake-off (item 3) on Windows.
#
# Reproduces all six cells (two tools x three targets) from a fresh checkout and
# writes research/bakeoff/out/*.json plus ty/bakeoff_results.json.
#
#   .\research\bakeoff\run_all.ps1                       # everything, from source
#   .\research\bakeoff\run_all.ps1 -Tool craft-anything -Target hosted
#   .\research\bakeoff\run_all.ps1 -SkipFetch -SkipBuild  # reuse committed targets
#
# Exit 0 only when every requested cell produced exit code 0 and a non-empty
# artefact. Anything else prints the reason and exits 1.

[CmdletBinding()]
param(
    [ValidateSet("", "rea", "craft-anything")] [string]$Tool = "",
    [ValidateSet("", "oss-repo", "hosted", "local-app")] [string]$Target = "",
    [switch]$SkipBuild,
    [switch]$SkipFetch
)

$ErrorActionPreference = "Stop"
$bakeoff = $PSScriptRoot
$root = Split-Path -Parent (Split-Path -Parent $bakeoff)
Set-Location $root

$CraftVersion = "0.5.0"
$CraftZip = "craft-anything-$CraftVersion-windows-x64-portable.zip"
$CraftDir = Join-Path $bakeoff "vendor\craft-anything-bin"
$CraftExe = Join-Path $CraftDir "craft-anything-$CraftVersion-windows-x64-portable\craft-anything-cli.exe"
$ReleaseBase = "https://github.com/storytold/craft-anything/releases/download/v$CraftVersion"

function Need([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name is not on PATH; this cell cannot run here."
    }
}

function Get-CraftAnything {
    if (Test-Path $CraftExe) {
        Write-Host "craft-anything-cli: present"
        return
    }
    Write-Host "craft-anything-cli: downloading v$CraftVersion ($CraftZip)"
    New-Item -ItemType Directory -Force $CraftDir | Out-Null
    $sums = Join-Path $CraftDir "SHA256SUMS.txt"
    Invoke-WebRequest -Uri "$ReleaseBase/SHA256SUMS.txt" -OutFile $sums -UseBasicParsing `
        -Headers @{ "User-Agent" = "northstar-bakeoff/1.0" }
    $zip = Join-Path $CraftDir $CraftZip
    Invoke-WebRequest -Uri "$ReleaseBase/$CraftZip" -OutFile $zip -UseBasicParsing `
        -Headers @{ "User-Agent" = "northstar-bakeoff/1.0" }

    $expected = ((Get-Content $sums | Where-Object { $_ -match [regex]::Escape($CraftZip) }) -split '\s+')[0]
    $actual = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
    if (-not $expected -or $actual -ne $expected.ToLower()) {
        throw "craft-anything checksum mismatch: expected $expected, got $actual"
    }
    Write-Host "craft-anything-cli: SHA-256 verified ($actual)"
    Expand-Archive -Path $zip -DestinationPath $CraftDir -Force
}

function Get-Todomvc {
    # Tracked in research/bakeoff/targets/todomvc. A fresh checkout already has it;
    # this restores it from upstream if someone deleted the vendored copy.
    $src = Join-Path $bakeoff "targets\todomvc\examples\javascript-es6\src"
    if (Test-Path $src) { return }
    Write-Host "todoMVC: cloning examples/javascript-es6 (MIT)"
    $dest = Join-Path $bakeoff "targets\todomvc"
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    git clone --depth 1 --filter=blob:none --sparse https://github.com/tastejs/todomvc $dest
    git -C $dest sparse-checkout set examples/javascript-es6
    Remove-Item -Recurse -Force (Join-Path $dest ".git")
}

function Get-Dist {
    $dist = Join-Path $root "northstar-os-ui\dist"
    if ((Test-Path $dist) -or $SkipBuild) {
        if (-not (Test-Path $dist)) { throw "no build at $dist and -SkipBuild was given" }
        return
    }
    Write-Host "northstar-os-ui: npm ci && npm run build"
    Push-Location (Join-Path $root "northstar-os-ui")
    try {
        if (-not (Test-Path "node_modules")) { npm ci | Out-Host }
        npm run build | Out-Host
    } finally { Pop-Location }
}

Need "python"
Get-CraftAnything
Get-Todomvc
Get-Dist

$pyArgs = @("tools/tool_bakeoff.py", "--run")
$resultsPath = Join-Path $root "ty\bakeoff_results.json"
if (-not $SkipFetch) { $pyArgs += "--prepare" }
if ($Tool) { $pyArgs += @("--tools", $Tool) }
if ($Target) { $pyArgs += @("--targets", $Target) }
if ($Tool -or $Target) {
    # A filtered run must not overwrite the six-cell decision file.
    $resultsPath = Join-Path $bakeoff "out\run_all.partial.json"
    $pyArgs += @("--out", $resultsPath)
}

Write-Host "running: python $($pyArgs -join ' ')"
python @pyArgs | Tee-Object -FilePath (Join-Path $bakeoff "run_all.last.log")
if ($LASTEXITCODE -ne 0) { throw "tool_bakeoff.py exited $LASTEXITCODE" }

# One check the score file does not make on its own: the artefact is on disk.
$results = Get-Content $resultsPath -Raw | ConvertFrom-Json
$bad = @()
foreach ($row in $results.targets) {
    foreach ($cell in $row.cells) {
        $path = Join-Path $root $cell.artefact
        $ok = ($cell.status -eq "ran") -and ($cell.exit_code -eq 0) -and (Test-Path $path) -and
              ((Get-Item $path).Length -gt 0)
        if (-not $ok) { $bad += "$($cell.tool)/$($cell.target): $($cell.reason)" }
    }
}
if ($bad.Count -gt 0) {
    $bad | ForEach-Object { Write-Error $_ }
    exit 1
}
Write-Host "all requested cells: exit 0 and a non-empty artefact"
exit 0
