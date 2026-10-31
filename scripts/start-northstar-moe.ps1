# NorthstarOS MoE lane - llama.cpp (CUDA, RTX 5080 Laptop 16GB)
# Two lanes, both 64K context, MTP speculative decoding, q4_0 KV (hybrid attention -> KV is tiny).
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\start-northstar-moe.ps1 -Lane coder
#   powershell -ExecutionPolicy Bypass -File scripts\start-northstar-moe.ps1 -Lane creative
# Optional: -Ctx 131072 (coder has ~1.3 GiB headroom at 128K), -Ncmoe 2 (spill experts to RAM if OOM)
param(
  [ValidateSet("coder","creative")] [string]$Lane = "creative",
  [int]$Ctx = 17408,
  [int]$Ncmoe = 0,
  [int]$MtpNmax = 8,
  [double]$MtpPmin = 0.8,
  [int]$Port = 8080,
  [string]$Kv = "",
  [switch]$Restart
)
$ErrorActionPreference = "Stop"

# Quantized KV cache + FlashAttention for any Ollama backend on this host.
# This lane is CUDA, so q8_0 is the default; use -Kv q4_0 for >32K context.
$env:OLLAMA_KV_CACHE_TYPE = "q8_0"
$env:OLLAMA_FLASH_ATTENTION = "1"

$srv = "$env:USERPROFILE\.config\northstar-llm\bin\llama-server.exe"
if (-not (Test-Path $srv)) { $srv = "$env:USERPROFILE\tools\llama-cuda\llama-server.exe" }
$dir = "$env:USERPROFILE\models\northstar-moe"

$lanes = @{
  coder    = @{ file = "Qwen3.8-27B-IQ4_XS_4BPW.gguf"; alias = "northstaros-27b-coder" }
  creative = @{ file = "Qwen3.8-27B-IQ4_XS_4BPW.gguf"; alias = "northstaros-thinking" }
}
$m = $lanes[$Lane]
$mpath = Join-Path $dir $m.file
if (-not (Test-Path $mpath)) { throw "Model not found: $mpath" }

# --- Free VRAM: drain every resident Ollama model (bojo/qwen2.5vl hold RAM/VRAM) ---
try {
  $ps = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/ps" -TimeoutSec 30
  $resident = @($ps.models | Where-Object { $_.name } | ForEach-Object { $_.name })
  foreach ($x in $resident) {
    Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:11434/api/generate" -TimeoutSec 60 `
      -Body (@{ model = $x; keep_alive = 0 } | ConvertTo-Json) -ContentType "application/json" | Out-Null
  }
  if ($resident.Count -gt 0) { Write-Host ("Ollama unloaded: {0}" -f ($resident -join ", ")) }
} catch { Write-Host "Ollama unload skipped (not reachable)." }

# --- Free VRAM: kill background GPU consumers ---
foreach ($hog in @("SoundTune","MSI.TerminalServer","LEDKeeper2","DCv2","msedgewebview2","PhoneExperienceHost")) {
  Get-Process -Name $hog -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}

$kv = if ($Kv) { $Kv } else { "q8_0" }
$argv = @(
  "-m", $mpath,
  "--alias", $m.alias,
  "-ngl", "99",
  "-c", "$Ctx",
  "-fa", "on",
  "-ctk", $kv, "-ctv", $kv,
  "-np", "1",
  "--jinja",
  "-b", "2048", "-ub", "512",
  "--spec-type", "draft-mtp",
  "--spec-draft-n-max", "$MtpNmax",
  "--spec-draft-p-min", "$MtpPmin",
  "--temp", "0.1",
  "--host", "127.0.0.1", "--port", "$Port"
)
if ($Ncmoe -gt 0) { $argv += @("--n-cpu-moe", "$Ncmoe") }

# An earlier instance holds ~14 GB of VRAM; a second load then dies with
# "cudaMalloc failed: out of memory" even though nvidia-smi shows free memory.
try {
  $h = (Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 "http://127.0.0.1:$Port/health").Content
} catch { $h = "" }
if ($h -match "ok" -and -not $Restart) {
  Write-Host "already serving on 127.0.0.1:$Port (use -Restart to reload)"; exit 0
}
if ($Restart) {
  Get-Process -Name "llama-server" -ErrorAction SilentlyContinue | Stop-Process -Force
  Start-Sleep -Seconds 4
}

$logDir = "$env:USERPROFILE\.config\northstar-llm"
$outLog = Join-Path $logDir "moe-$Lane.out"
$errLog = Join-Path $logDir "moe-$Lane.err"

Write-Host ("Lane={0} ctx={1} ncmoe={2} mtp={3}/{4}" -f $Lane, $Ctx, $Ncmoe, $MtpNmax, $MtpPmin)

# Start DETACHED. A foreground `& $srv @argv` dies with the calling shell, which is
# how an unattended build lost its model server mid-run on 2026-10-29 (the next call
# failed with WinError 10054 and every later step was wasted).
$p = Start-Process -FilePath $srv -ArgumentList $argv -WindowStyle Hidden -PassThru `
       -RedirectStandardOutput $outLog -RedirectStandardError $errLog

$sw = [Diagnostics.Stopwatch]::StartNew()
for ($i = 0; $i -lt 180; $i++) {
  Start-Sleep -Seconds 2
  if ($p.HasExited) {
    $tail = if (Test-Path $errLog) { (Get-Content $errLog -Tail 12) -join "`n" } else { "" }
    throw "server exited (code $($p.ExitCode)) - see $errLog`n$tail"
  }
  try {
    if ((Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 "http://127.0.0.1:$Port/health").Content -match "ok") {
      $sw.Stop()
      Write-Host ("ready on http://127.0.0.1:{0}  pid={1}  ctx={2}  ({3:N0}s)" -f $Port, $p.Id, $Ctx, $sw.Elapsed.TotalSeconds)
      exit 0
    }
  } catch {}
}
throw "not ready after 360 s - see $errLog"
