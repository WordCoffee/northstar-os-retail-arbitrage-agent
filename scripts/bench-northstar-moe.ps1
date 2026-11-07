# Benchmark harness for the two MoE lanes (64K, MTP).
# Starts llama-server for one lane, waits for /health, runs 3 workloads, reports real t/s, stops it.
param(
  [ValidateSet("coder","creative")] [string]$Lane = "coder",
  [ValidateSet("smoke","architect")] [string]$Workload = "smoke",
  [switch]$Think,
  [int]$Ctx = 65536,
  [int]$Ncmoe = 0,
  [int]$NPredict = 256,
  [int]$Port = 8080
)
$ErrorActionPreference = "Stop"

$srv = "$env:USERPROFILE\.config\northstar-llm\bin\llama-server.exe"
if (-not (Test-Path $srv)) { $srv = "$env:USERPROFILE\tools\llama-cuda\llama-server.exe" }
$dir = "$env:USERPROFILE\models\northstar-moe"
$lanes = @{
  coder    = "Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf"
  creative = "Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf"
}
$mpath = Join-Path $dir $lanes[$Lane]
if (-not (Test-Path $mpath)) { throw "Model not found: $mpath" }

$kv = if ($Lane -eq "coder") { "q8_0" } else { "q4_0" }
$argv = @(
  "-m", $mpath, "--alias", "bench", "-ngl", "99",
  "-c", "$Ctx", "-fa", "on", "-ctk", $kv, "-ctv", $kv,
  "-np", "1", "--jinja", "-b", "2048", "-ub", "512",
  "--spec-type", "draft-mtp", "--spec-draft-n-max", "8", "--spec-draft-p-min", "0.8",
  "--temp", "0.35", "--host", "127.0.0.1", "--port", "$Port"
)
if ($Ncmoe -gt 0) { $argv += @("--n-cpu-moe", "$Ncmoe") }

$proc = Start-Process -FilePath $srv -ArgumentList $argv -PassThru -WindowStyle Hidden
try {
  $ok = $false
  for ($i = 0; $i -lt 240; $i++) {
    Start-Sleep -Seconds 2
    if ($proc.HasExited) { throw "server exited early (code $($proc.ExitCode))" }
    try { $h = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 3; if ($h.status -eq "ok") { $ok = $true; break } } catch {}
  }
  if (-not $ok) { throw "server did not become healthy within 8 min" }

  $promptFile = Join-Path (Split-Path -Parent $PSScriptRoot) "tests\bench\architect_prompt.txt"
  if ($Workload -eq "architect") {
    if (-not (Test-Path $promptFile)) { throw "prompt file missing: $promptFile" }
    $prompts = @(@{ name = "architect"; prompt = [string](Get-Content -Raw $promptFile) })
    if ($NPredict -lt 8192) { $NPredict = 8192 }
  } else {
    $prompts = @(
      @{ name = "refactor";  prompt = "Refactor this Python function to add type hints and docstrings:`n`ndef calc(x):`n    return x*2 if x>0 else 0" },
      @{ name = "recital";   prompt = "Write a Python function that merges two sorted lists, then explain each line." },
      @{ name = "reasoning"; prompt = "A shop buys 120 units at 4.20 each, sells 95 at 9.99 and discounts the rest by 30 percent. Compute gross profit and explain each step." }
    )
  }
  $results = @()
  foreach ($p in $prompts) {
    if ($Workload -eq "architect") {
      $prompt = [string]$p.prompt + "`n`nWrite the complete implementation now. Reply with Markdown containing the full source files. Do not ask questions."
      $body = @{ prompt = $prompt; n_predict = $NPredict; temperature = 0.2; cache_prompt = $false } | ConvertTo-Json
      $r = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$Port/completion" -Body $body -ContentType "application/json" -TimeoutSec 1800
      $msg = $null
      $text = [string]$r.content
      $reasoning = ""
    } else {
      $messages = @(
        @{ role = "system"; content = "You are a coding agent in a sandbox with NO tools available. Never emit tool calls, XML function tags, or file-read requests. Write the requested files directly in your response." },
        @{ role = "user"; content = [string]$p.prompt }
      )
      $body = @{ messages = $messages; n_predict = $NPredict; temperature = 0.2; cache_prompt = $false; chat_template_kwargs = @{ enable_thinking = [bool]$Think } } | ConvertTo-Json -Depth 6
      $r = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$Port/v1/chat/completions" -Body $body -ContentType "application/json" -TimeoutSec 1800
      $msg = $r.choices[0].message
      $reasoning = [string]$msg.reasoning_content
      $text = [string]$msg.content
    }
    if ($Workload -eq "architect") {
      $outMd = Join-Path $dir ("out_{0}_{1}.md" -f $Lane, (Get-Date -Format "yyyyMMdd_HHmmss"))
      ("## REASONING`n`n" + $reasoning + "`n`n## ANSWER`n`n" + $text) | Set-Content -Path $outMd -Encoding UTF8
      Write-Host ("Saved model output: {0} (reasoning chars={1}, answer chars={2})" -f $outMd, $reasoning.Length, $text.Length)
    }
    $results += [pscustomobject]@{
      lane    = $Lane
      prompt  = $p.name
      gen_tps = [math]::Round([double]$r.timings.predicted_per_second, 1)
      pp_tps  = [math]::Round([double]$r.timings.prompt_per_second, 1)
      tokens  = $r.timings.predicted_n
    }
  }
  $results | Format-Table -AutoSize | Out-String
  $out = Join-Path $dir ("bench_{0}_{1}.json" -f $Lane, (Get-Date -Format "yyyyMMdd_HHmmss"))
  $results | ConvertTo-Json -Depth 3 | Set-Content $out
  Write-Host "Saved $out"
}
finally {
  if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
}
