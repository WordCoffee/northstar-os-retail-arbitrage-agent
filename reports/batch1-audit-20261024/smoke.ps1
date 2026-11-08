$env:NORTHSTAR_CDP_HOST="127.0.0.1"
$env:NORTHSTAR_CDP_PORT="9222"
$env:CHROMECONNECT_TRANSPORT_MODULE="C:\Users\T2Hol\OneDrive\Documents\Default Project\scripts\chromecontrol-playwright-bridge.js"
$agent = "C:\Users\T2Hol\OneDrive\Documents\Default Project\scripts\chromecontrol-agent.js"
$profile = "Profile 6"
$base = "http://127.0.0.1:8101/ui/"
$reportDir = "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\reports\batch1-audit-20261024\product-tests\smoke"
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$results = @()
for ($i=1; $i -le 20; $i++) {
  $induced = ($i -eq 10)
  if ($induced) { $env:CHROMECONNECT_MCP_TIMEOUT_MS = "1000" } else { $env:CHROMECONNECT_MCP_TIMEOUT_MS = "30000" }
  $shot = "$reportDir\smoke-$i.png"
  $task = "STEPS:`nread`nprobe [data-testid=chat-input]`nscreenshot $shot"
  $t0 = Get-Date
  $out = & node $agent run --profile $profile --max-steps 6 --task $task --url $base 2>&1
  $dt = [Math]::Round(((Get-Date)-$t0).TotalSeconds,1)
  $status = ($out | Select-String -Pattern 'status:' | Select-Object -First 1).Line.Trim()
  $steps  = ($out | Select-String -Pattern 'steps:' | Select-Object -First 1).Line.Trim()
  $calls  = ($out | Select-String -Pattern 'calls:' | Select-Object -First 1).Line.Trim()
  $runid  = ($out | Select-String -Pattern 'run:' | Select-Object -First 1).Line.Trim()
  $row = [pscustomobject]@{ cycle=$i; induced_timeout=$induced; duration_s=$dt; status=$status; steps=$steps; calls=$calls; run=$runid; screenshot=$shot }
  $results += $row
  Write-Host "cycle $i (${dt}s) induced=$induced :: $status | $steps | $calls"
  $row | ConvertTo-Json -Compress | Out-File -Append -FilePath "$reportDir\smoke-results.jsonl" -Encoding utf8
}
$results | Export-Csv -NoTypeInformation -Path "$reportDir\smoke-results.csv"
Write-Host "=== done ==="
$results | Group-Object status | Select-Object Name,Count | Format-Table -AutoSize
