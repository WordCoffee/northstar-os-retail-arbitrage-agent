#requires -Version 5.1
<#
  ty_rollback.ps1 - the rollback point Ty takes before anything destructive.

  Create:  .\scripts\ty_rollback.ps1 -Create pre-overnight
  List:    .\scripts\ty_rollback.ps1 -List
  Restore: .\scripts\ty_rollback.ps1 -Restore pre-overnight

  A rollback point is:
    * a git tag on the current branch            rollback/<name>
    * a copy of every SQLite database (db + -wal + -shm)
    * a copy of the config directory
    * a manifest of installed model files (name + size + mtime)
    * the uncommitted work as a patch + the list of untracked paths
    * a machine-readable manifest.json with the facts needed to decide

  Restoring puts the databases and config back and moves the working tree to the
  tag. It does NOT delete untracked files (they are listed, never removed).
#>
[CmdletBinding(DefaultParameterSetName = 'Create')]
param(
    [Parameter(ParameterSetName = 'Create', Position = 0)]
    [string]$Create,

    [Parameter(ParameterSetName = 'Restore', Mandatory = $true)]
    [string]$Restore,

    [Parameter(ParameterSetName = 'List', Mandatory = $true)]
    [switch]$List,

    [string]$RepoRoot,
    [string]$PointRoot,
    [switch]$KeepDbWal
)

$ErrorActionPreference = 'Stop'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'

# $PSScriptRoot is not reliable inside a param() default when the script is run
# with -File, so it is resolved here instead.
if (-not $RepoRoot) { $RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent }
if (-not $PointRoot) { $PointRoot = Join-Path $RepoRoot 'backups\ty_rollback' }

function Write-Step($m) { Write-Host "  $m" -ForegroundColor DarkGray }

function New-RollbackPoint([string]$name) {
    if (-not $name) { $name = "point-$stamp" }
    $safe = ($name -replace '[^A-Za-z0-9._-]', '-')
    $tag = "rollback/$safe"
    $dir = Join-Path $PointRoot $safe
    New-Item -ItemType Directory -Force -Path $dir | Out-Null

    Push-Location $RepoRoot
    try {
        $branch = (git rev-parse --abbrev-ref HEAD).Trim()
        $head = (git rev-parse HEAD).Trim()
        Write-Host "Rollback point '$safe' on $branch @ $($head.Substring(0,8))"

        # 1. git tag (idempotent)
        git tag -f $tag $head 2>&1 | Out-Null
        Write-Step "tagged $tag"

        # 2. databases
        $dbDir = Join-Path $dir 'data'
        New-Item -ItemType Directory -Force -Path $dbDir | Out-Null
        $dbs = Get-ChildItem -Path $RepoRoot -Recurse -Depth 2 -Include '*.db', '*.db-wal', '*.db-shm' -File -ErrorAction SilentlyContinue
        $dbCount = 0
        foreach ($d in $dbs) {
            if ($d.FullName -match '\\backups\\') { continue }
            if (-not $KeepDbWal -and $d.Name -like '*-shm') { continue }
            $dest = Join-Path $dbDir ($d.FullName.Substring($RepoRoot.Length + 1).Replace('\', '__'))
            Copy-Item $d.FullName $dest -Force
            $dbCount++
        }
        Write-Step "copied $dbCount database file(s)"

        # 3. config
        $cfgSrc = Join-Path $RepoRoot 'config'
        if (Test-Path $cfgSrc) {
            Copy-Item $cfgSrc (Join-Path $dir 'config') -Recurse -Force
            Write-Step "copied config/"
        }

        # 4. the external Chrome Connect tree (config + policy live outside this repo)
        $extDir = 'C:\Users\T2Hol\OneDrive\Documents\Default Project\config'
        $ext = Join-Path $extDir 'chromecontrol_policy_owner.json'
        if (Test-Path $extDir) {
            New-Item -ItemType Directory -Force -Path (Join-Path $dir 'external') | Out-Null
            Copy-Item (Join-Path $extDir '*') (Join-Path $dir 'external') -Recurse -Force -ErrorAction SilentlyContinue
            Write-Step "copied external Chrome Connect config dir"
        }
        elseif (Test-Path $ext) {
            New-Item -ItemType Directory -Force -Path (Join-Path $dir 'external') | Out-Null
            Copy-Item $ext (Join-Path $dir 'external\chromecontrol_policy_owner.json') -Force
            Write-Step "copied external policy file"
        }

        # 5. model manifest (names + sizes + mtimes; never the weights themselves)
        $modelRoots = @(
            (Join-Path $env:USERPROFILE '.ollama\models\blobs'),
            'C:\Users\T2Hol\ComfyUI\models'
        )
        $models = @()
        foreach ($r in $modelRoots) {
            if (-not (Test-Path $r)) { continue }
            $models += Get-ChildItem $r -Recurse -Include '*.gguf', '*.safetensors', '*.pth' -File -ErrorAction SilentlyContinue |
                Select-Object @{n='root';e={$r}}, @{n='name';e={$_.Name}}, @{n='bytes';e={$_.Length}}, @{n='mtime';e={$_.LastWriteTimeUtc}}
        }
        $models | ConvertTo-Json -Depth 3 | Set-Content (Join-Path $dir 'models.json') -Encoding UTF8
        Write-Step "recorded $($models.Count) model file(s)"

        # 6. uncommitted work
        $patch = Join-Path $dir 'uncommitted.patch'
        git diff --binary > $patch
        git status --porcelain | Set-Content (Join-Path $dir 'status.txt') -Encoding UTF8
        $untracked = (git ls-files --others --exclude-standard | Measure-Object).Count
        Write-Step "captured patch ($([int]((Get-Item $patch).Length/1KB)) KB) + $untracked untracked path(s) listed"

        # 7. manifest
        [ordered]@{
            name       = $safe
            created_at = (Get-Date).ToString('o')
            branch     = $branch
            head       = $head
            tag        = $tag
            db_files   = $dbCount
            models     = $models.Count
            untracked  = $untracked
            patch_kb   = [int]((Get-Item $patch).Length / 1KB)
        } | ConvertTo-Json | Set-Content (Join-Path $dir 'manifest.json') -Encoding UTF8

        Write-Host "Rollback point ready: $dir" -ForegroundColor Green
        return $dir
    }
    finally { Pop-Location }
}

function Invoke-Rollback([string]$name) {
    $safe = ($name -replace '[^A-Za-z0-9._-]', '-')
    $dir = Join-Path $PointRoot $safe
    if (-not (Test-Path $dir)) { throw "no rollback point '$safe' under $PointRoot" }
    $tag = "rollback/$safe"
    $manifest = Get-Content (Join-Path $dir 'manifest.json') -Raw | ConvertFrom-Json

    Write-Host "Restoring '$safe' (branch $($manifest.branch) @ $($manifest.head.Substring(0,8)))" -ForegroundColor Yellow
    Push-Location $RepoRoot
    try {
        # 0. take a point of the CURRENT state first, so a restore is itself reversible
        New-RollbackPoint "pre-restore-$stamp" | Out-Null

        # 1. working tree files to the tag FIRST.
        #    Order matters: northstar.db is a TRACKED file, so a checkout after the
        #    database copy would overwrite the restored 41 MB database with the
        #    small committed copy. Files first, then the data that must win.
        git checkout $tag -- . 2>&1 | Out-Null
        Write-Step "working tree files reset to $tag (untracked files left in place)"

        # 2. databases back (after the checkout, so they are authoritative)
        $dbDir = Join-Path $dir 'data'
        if (Test-Path $dbDir) {
            foreach ($f in Get-ChildItem $dbDir -File) {
                $rel = $f.Name.Replace('__', '\')
                $dest = Join-Path $RepoRoot $rel
                New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
                Copy-Item $f.FullName $dest -Force
            }
            Write-Step "databases restored"
        }

        # 3. config back
        $cfg = Join-Path $dir 'config'
        if (Test-Path $cfg) {
            $cfgDest = Join-Path $RepoRoot 'config'
            New-Item -ItemType Directory -Force -Path $cfgDest | Out-Null
            Copy-Item (Join-Path $cfg '*') $cfgDest -Recurse -Force
            Write-Step "config restored"
        }

        # 3. external Chrome Connect config back
        $extBak = Join-Path $dir 'external'
        $extDest = 'C:\Users\T2Hol\OneDrive\Documents\Default Project\config'
        if (Test-Path $extBak) {
            Copy-Item (Join-Path $extBak '*') $extDest -Recurse -Force -ErrorAction SilentlyContinue
            Write-Step "external Chrome Connect config restored"
        }

        Write-Host "Rollback complete. Review 'git status' before continuing." -ForegroundColor Green
    }
    finally { Pop-Location }
}

if ($PSCmdlet.ParameterSetName -eq 'List') {
    if (-not (Test-Path $PointRoot)) { Write-Host 'no rollback points yet'; exit 0 }
    Get-ChildItem $PointRoot -Directory | Sort-Object LastWriteTime -Descending | ForEach-Object {
        $m = Join-Path $_.FullName 'manifest.json'
        if (Test-Path $m) {
            $j = Get-Content $m -Raw | ConvertFrom-Json
            [pscustomobject]@{ point = $_.Name; branch = $j.branch; head = $j.head.Substring(0,8); dbs = $j.db_files; models = $j.models; created = $j.created_at }
        }
    } | Format-Table -AutoSize
    exit 0
}
elseif ($PSCmdlet.ParameterSetName -eq 'Restore') { Invoke-Rollback $Restore }
else { New-RollbackPoint $Create }
