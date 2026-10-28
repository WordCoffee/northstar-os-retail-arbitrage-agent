# NorthstarOS local LLM - high-performance lane (llama.cpp, CUDA)
# Model: Qwen3.8-27B GSQ-RCO IQ3_XXS + MTP (10.4GB, base Qwen/Qwen3.8-27B)
# Usage: powershell -ExecutionPolicy Bypass -File scripts\start-northstar-llm.ps1
# Serves an OpenAI-compatible API on http://127.0.0.1:8080/v1
#
# MEASURED CONFIG (2026-10-27, RTX 5080 Laptop 16GB):
# - Builder: llama.cpp b11889 CUDA at %USERPROFILE%\.config\northstar-llm\bin
# - Model: ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp (10.4GB)
# - MTP speculative decoding: --spec-type draft-mtp --spec-draft-n-max 4
# - Context: -c 65536 (fits in 16GB with q4_0 KV cache)
# - KV cache: q4_0 (K and V) - required for 64K on 16GB; q8_0 caps at ~32K
# - GPU: full offload -ngl 99 (10.4GB model + ~2.6GB CUDA/MTP overhead = ~13GB, fits 16GB)
# - Decode: ~69 tok/s with MTP, ~47 tok/s without; prompt eval ~70 tok/s
# - Pre-launch: kills background GPU processes (MSI Center, Edge WebView, etc.)
#
# To restore vision (after upgrading to 32GB+ VRAM):
#   Add: --mmproj $mmproj

$ErrorActionPreference = "Stop"
$cudaServer = "$env:USERPROFILE\.config\northstar-llm\bin\llama-server.exe"
$srvFallback = "$env:USERPROFILE\tools\llama-cuda\llama-server.exe"
$srv = if (Test-Path $cudaServer) { $cudaServer } else { $srvFallback }
$model = "$env:USERPROFILE\models\northstaros-qwen3.8\Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf"
$mmproj = "$env:USERPROFILE\models\northstaros-qwen3.8\mmproj-Qwen3.8-27B-BF16.gguf"

# --- Free the GPU: drain EVERY resident Ollama model + kill background GPU processes ---
# This used to evict one hard-coded id ("northstaros-qwen3.8:27b") that no longer
# exists — the 27B moved to this llama.cpp server — so it evicted nothing and
# reported success. It now reads /api/ps and unloads whatever is actually
# resident. Bojo is CPU-pinned (scripts/bojo-cpu.Modelfile) and therefore holds no
# VRAM, but it still holds ~2.4 GB of SYSTEM RAM, and RAM is this box's binding
# constraint for a 10.4 GB model plus a 64K q4_0 KV cache.
try {
  $ps = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/ps" -TimeoutSec 30
  $resident = @($ps.models | Where-Object { $_.name } | ForEach-Object { $_.name })
  if ($resident.Count -eq 0) {
    Write-Host "Ollama already has nothing resident."
  } else {
    foreach ($m in $resident) {
      Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:11434/api/generate" -TimeoutSec 60 `
        -Body (@{ model = $m; keep_alive = 0 } | ConvertTo-Json) -ContentType "application/json" | Out-Null
    }
    Write-Host ("Ollama unloaded: {0}" -f ($resident -join ", "))
  }
} catch { Write-Host "Ollama unload skipped (server not reachable)." }

# Kill background GPU consumers that eat VRAM (MSI Center, Edge WebView, etc.)
$gpuHogs = @("SoundTune", "MSI.TerminalServer", "LEDKeeper2", "DCv2", "msedgewebview2", "PhoneExperienceHost")
foreach ($hog in $gpuHogs) {
  Get-Process -Name $hog -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
}
Write-Host "Background GPU processes cleared."

& $srv `
  -m $model `
  --alias "northstaros-qwen3.8:27b" `
  -ngl 99 `
  -c 65536 -fa on `
  -ctk q4_0 -ctv q4_0 `
  -np 1 --jinja `
  --spec-type draft-mtp --spec-draft-n-max 4 `
  --host 127.0.0.1 --port 8080 `
  --temp 0.35
