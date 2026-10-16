# tools/install-git-hooks.ps1
# ============================
# Installs the versioned git hooks (tools/git-hooks/*) into .git/hooks.
# Safe to re-run after every clone or hook change.
#
# ASCII-only on purpose: PowerShell 5.1 misreads non-ASCII .ps1 without a BOM.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File tools\install-git-hooks.ps1

$ErrorActionPreference = "Stop"

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$SourceDir = Join-Path $PSScriptRoot "git-hooks"
$HookDir = Join-Path $RepoRoot ".git\hooks"

if (-not (Test-Path $SourceDir)) {
    Write-Host ("No hooks source directory: {0}" -f $SourceDir) -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $HookDir)) {
    Write-Host ("No .git\hooks directory at {0} - is this a git repo?" -f $RepoRoot) -ForegroundColor Red
    exit 1
}

$count = 0
Get-ChildItem $SourceDir -File | ForEach-Object {
    $dest = Join-Path $HookDir $_.Name
    # Normalize to LF so the shell hooks run correctly from Git for Windows sh.
    $content = [System.IO.File]::ReadAllText($_.FullName) -replace "`r`n", "`n"
    [System.IO.File]::WriteAllText($dest, $content, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host ("installed hook: {0}" -f $_.Name) -ForegroundColor Green
    $count++
}

Write-Host ("Done - {0} hook(s) installed into {1}" -f $count, $HookDir)
exit 0
