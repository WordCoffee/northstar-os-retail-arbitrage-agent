# pass@3 for the local coder lane (work order: pending pass@3, n was 1).
# Three INDEPENDENT cold attempts at the same 9-file concurrency spec, same
# acceptance (npx tsc --noEmit), 48 steps each, zero deterministic patches.
# Writes exports/pass3_20261030/summary.json.
$ErrorActionPreference = "Stop"
$root = "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
$outRoot = Join-Path $root "exports\pass3_20261030"
New-Item -ItemType Directory -Force -Path $outRoot | Out-Null
$env:TYS_CODING_MAX_TOKENS = "8192"
$objectivePath = Join-Path $root "exports\pass1_coder_20261029\OBJECTIVE.md"
$objective = Get-Content $objectivePath -Raw
$results = @()

for ($i = 1; $i -le 3; $i++) {
  $ws = Join-Path $outRoot "attempt_$i"
  New-Item -ItemType Directory -Force -Path $ws | Out-Null
  Copy-Item (Join-Path $root "exports\agent_arch2\package.json") $ws -Force
  Copy-Item (Join-Path $root "exports\agent_arch2\tsconfig.json") $ws -Force
  if (-not (Test-Path (Join-Path $ws "node_modules"))) {
    Copy-Item (Join-Path $root "exports\agent_arch2\node_modules") (Join-Path $ws "node_modules") -Recurse -Force
  }
  $log = Join-Path $ws "run_stdout.txt"
  Push-Location $root
  try {
    $raw = & python tools\run_coding_agent.py --workspace $ws --objective $objective `
      --command "npx tsc --noEmit" --required-file src/index.ts --max-steps 48 --builder --max-repairs 4 2>&1
    $raw | Out-File -FilePath $log -Encoding utf8
  } finally { Pop-Location }

  # Independent verification, not the harness's own claim.
  Push-Location $ws
  try { npx tsc --noEmit 2>&1 | Out-Null; $tsc = $LASTEXITCODE } finally { Pop-Location }
  $steps = 0
  if ($raw -match '"steps":\s*(\d+)') { $steps = [int]$Matches[1] }
  $ok = ($raw -match '"ok":\s*true') -or ($tsc -eq 0)
  $files = 0
  if (Test-Path (Join-Path $ws "src")) { $files = (Get-ChildItem (Join-Path $ws "src") -Filter *.ts | Measure-Object).Count }
  $sab = $false
  $q = Join-Path $ws "src\queue.ts"
  if (Test-Path $q) { $sab = (Select-String -Path $q -Pattern "SharedArrayBuffer" -Quiet) }

  $results += [pscustomobject]@{
    attempt = $i; tsc_exit = $tsc; ok = $ok; steps = $steps; files = $files; queue_uses_sab = $sab
  }
  Write-Host ("attempt {0}: tsc={1} ok={2} steps={3} files={4} sab={5}" -f $i, $tsc, $ok, $steps, $files, $sab)
}

$passes = ($results | Where-Object { $_.tsc_exit -eq 0 }).Count
$summary = [pscustomobject]@{
  generated_at = (Get-Date -Format o)
  lane = "Qwen3.8-27B coder on 127.0.0.1:8080, n_ctx 17408"
  attempts = $results
  pass_at_3 = "$passes/3"
  verified_by = "npx tsc --noEmit run outside the harness"
}
$summary | ConvertTo-Json -Depth 5 | Out-File (Join-Path $outRoot "summary.json") -Encoding utf8
Write-Host ("PASS@3 = {0}/3" -f $passes)
