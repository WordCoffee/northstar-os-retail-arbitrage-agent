<#
.SYNOPSIS
  Snapshot and restore this build (see ROLLBACK.md).

.DESCRIPTION
  snapshot : tag HEAD, copy the databases, record the served bundle identity.
  list     : show every snapshot.
  restore  : create + switch to rollback/<name> at the snapshot commit and restore
             the databases. Your current branch is never moved or deleted.

  Restore backs up the CURRENT databases first, so a restore can itself be undone.

.EXAMPLE
  .\tools\rollback.ps1 -Action snapshot -Name pre-bojo
  .\tools\rollback.ps1 -Action list
  .\tools\rollback.ps1 -Action restore -Name pre-bojo
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidateSet('snapshot', 'list', 'restore')][string]$Action,
    [string]$Name = '',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$backups = Join-Path $repo 'backups\rollback'
$dataDir = Join-Path $repo 'Northstar_backend\data'
$dbFiles = @('northstar.db', 'foundation.db')

function Get-Head { (git -C $repo rev-parse --short HEAD).Trim() }

function Get-BundleHash {
    $assets = Join-Path $repo 'northstar-os-ui\dist\assets'
    if (-not (Test-Path $assets)) { return 'not-built' }
    $js = Get-ChildItem $assets -Filter 'index-*.js' -ErrorAction SilentlyContinue |
          Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $js) { return 'not-built' }
    return $js.Name
}

switch ($Action) {
    'snapshot' {
        if (-not $Name) { throw '-Name is required for snapshot (e.g. -Name pre-bojo)' }
        $tag = "snapshot/$Name"
        $dir = Join-Path $backups $Name
        if (Test-Path $dir) {
            if (-not $Force) { throw "snapshot '$Name' already exists (use -Force to replace the DB copies)" }
        }
        New-Item -ItemType Directory -Force -Path $dir | Out-Null

        $dirty = (git -C $repo status --porcelain | Measure-Object -Line).Lines
        $manifest = [ordered]@{
            name      = $Name
            tag       = $tag
            commit    = (git -C $repo rev-parse HEAD).Trim()
            branch    = (git -C $repo rev-parse --abbrev-ref HEAD).Trim()
            created   = (Get-Date).ToString('o')
            bundle    = Get-BundleHash
            dirty_files = $dirty
            databases = @()
        }

        git -C $repo tag -f $tag | Out-Null
        foreach ($f in $dbFiles) {
            $src = Join-Path $dataDir $f
            if (Test-Path $src) {
                Copy-Item $src (Join-Path $dir $f) -Force
                $manifest.databases += @{ file = $f; bytes = (Get-Item $src).Length }
            }
        }
        $manifest | ConvertTo-Json -Depth 5 | Set-Content (Join-Path $dir 'manifest.json') -Encoding utf8

        Write-Host "SNAPSHOT '$Name' created" -ForegroundColor Green
        Write-Host "  tag      : $tag  (commit $($manifest.commit.Substring(0,7)))"
        Write-Host "  branch   : $($manifest.branch)"
        Write-Host "  bundle   : $($manifest.bundle)"
        Write-Host "  dirty    : $dirty working-tree file(s) NOT captured (run git stash/commit first if they matter)"
        Write-Host "  databases: $($manifest.databases.Count) copied to backups\rollback\$Name"
        if ($dirty -gt 0) {
            Write-Host "  NOTE: uncommitted changes are not part of the snapshot." -ForegroundColor Yellow
        }
    }

    'list' {
        if (-not (Test-Path $backups)) { Write-Host "no snapshots yet (run -Action snapshot -Name <name>)"; break }
        $tags = git -C $repo tag --list 'snapshot/*'
        if (-not $tags) { Write-Host "no snapshot tags"; break }
        Write-Host "SNAPSHOTS"
        foreach ($t in $tags) {
            $n = $t -replace '^snapshot/', ''
            $m = Join-Path $backups "$n\manifest.json"
            $when = ''; $commit = ''
            if (Test-Path $m) {
                $j = Get-Content $m -Raw | ConvertFrom-Json
                $when = $j.created; $commit = $j.commit.Substring(0, 7)
            }
            Write-Host ("  {0,-24} {1,-10} {2}" -f $n, $commit, $when)
        }
    }

    'restore' {
        if (-not $Name) { throw '-Name is required for restore' }
        $tag = "snapshot/$Name"
        $commit = (git -C $repo rev-parse --verify "refs/tags/$tag" 2>$null)
        if (-not $commit) { throw "snapshot '$Name' not found (run -Action list)" }
        if ((git -C $repo status --porcelain | Measure-Object -Line).Lines -gt 0 -and -not $Force) {
            throw "working tree has uncommitted changes; commit or stash them, or pass -Force"
        }

        # 1. back up the CURRENT databases so this restore can be undone
        $pre = Join-Path $backups ("pre-restore-" + (Get-Date).ToString('yyyyMMdd-HHmmss'))
        New-Item -ItemType Directory -Force -Path $pre | Out-Null
        foreach ($f in $dbFiles) {
            $src = Join-Path $dataDir $f
            if (Test-Path $src) { Copy-Item $src (Join-Path $pre $f) -Force }
        }
        Write-Host "current databases backed up to backups\rollback\$(Split-Path -Leaf $pre)"

        # 2. a NEW branch at the snapshot commit — the current branch is untouched
        $branch = "rollback/$Name"
        $exists = git -C $repo branch --list $branch
        if ($exists) { git -C $repo switch $branch | Out-Null }
        else { git -C $repo switch -c $branch $commit | Out-Null }
        Write-Host "switched to $branch at $($commit.Substring(0,7))" -ForegroundColor Green

        # 3. restore the databases (if the snapshot captured them)
        $dir = Join-Path $backups $Name
        foreach ($f in $dbFiles) {
            $snap = Join-Path $dir $f
            if (Test-Path $snap) { Copy-Item $snap (Join-Path $dataDir $f) -Force }
        }

        # 4. rebuild the served bundle so it matches the restored source
        Push-Location $repo
        try { npm --prefix northstar-os-ui run build 2>&1 | Select-Object -Last 2 | ForEach-Object { Write-Host "  $_" } }
        finally { Pop-Location }

        Write-Host ""
        Write-Host "RESTORED to '$Name'" -ForegroundColor Green
        Write-Host "  branch : $branch"
        Write-Host "  commit : $((git -C $repo rev-parse --short HEAD).Trim())"
        Write-Host "  bundle : $(Get-BundleHash)"
        Write-Host "  forward: git switch <your-branch>   (nothing was deleted)"
    }
}
