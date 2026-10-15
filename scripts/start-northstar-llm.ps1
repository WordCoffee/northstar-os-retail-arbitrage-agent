# NorthstarOS local LLM — high-performance lane (llama.cpp, CUDA)
# Model: northstaros-qwen3.8:27b  (ISTA-DASLab GSQ-RCO IQ3_XXS + MTP head)
# Usage: powershell -ExecutionPolicy Bypass -File scripts\start-northstar-llm.ps1
# Serves an OpenAI-compatible API on http://127.0.0.1:8080/v1 (plus the built-in web UI on /)
#
# MEASURED CONFIG (2026-10-14, RTX 5080 Laptop 16GB):
# - Builder: llama.cpp b11632 CUDA 13.4 (official release) at %USERPROFILE%\tools\llama-b11632\cuda
#   (the winget b11580 Vulkan build is a measured ~2-3x-slower fallback; keep it only as a spare)
# - MTP speculative decoding: --spec-type draft-mtp --spec-draft-n-max 6 --spec-draft-p-min 0.65
#   measured 70.1 tok/s gen at 92.7% draft acceptance (vs 41.8 tok/s with spec off = +68%);
#   draft-max 4 measured 54.6 tok/s; draft-max 8 was unstable on this box — do not raise past 6.
# - HIGH MODE (max reasoning) pinned on this lane: --reasoning on --reasoning-effort xhigh
#   --reasoning-budget -1 (unrestricted).
# - Vision: --mmproj loads the BF16 projector (this is the only lane that gives the model eyes;
#   Ollama's local-create has no mmproj support).
# - VRAM: Ollama (the app lane) and llama-server both want the 16GB card, so this script
#   automatically unloads the Ollama model first (Ollama auto-reloads on its next request).
# - For best throughput keep RAM/GPU headroom: stop leftover media servers (ComfyUI etc.) and
#   other GPU apps before long agent runs — measured memory pressure can halve token speed.
#
# Ollama lane notes (2026-10-14 measurements): leave OLLAMA_FLASH_ATTENTION UNSET (auto) and
# OLLAMA_KV_CACHE_TYPE at f16/default — forcing flash-attn on measured a ~6x gen regression on
# this model, and q8_0 KV quantization is not usable with this engine/architecture.

$ErrorActionPreference = "Stop"
$cudaServer = "$env:USERPROFILE\tools\llama-b11632\cuda\llama-server.exe"
$srvFallback = "C:\Users\T2Hol\AppData\Local\Microsoft\WinGet\Packages\ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe\llama-server.exe"
$srv = if (Test-Path $cudaServer) { $cudaServer } else { $srvFallback }
$modelDir = "$env:USERPROFILE\models\northstaros-qwen3.8"
$model = Join-Path $modelDir "Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf"
$mmproj = Join-Path $modelDir "mmproj-Qwen3.8-27B-BF16.gguf"

# free the GPU: unload the Ollama app-lane model (it auto-reloads when the app next calls it)
try {
  Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:11434/api/generate" -TimeoutSec 30 `
    -Body '{"model":"northstaros-qwen3.8:27b","keep_alive":0}' -ContentType "application/json" | Out-Null
  Write-Host "Ollama model unloaded (auto-reloads on next app request)."
} catch { Write-Host "Ollama unload skipped (server not reachable)." }

& $srv `
  -m $model `
  --mmproj $mmproj `
  --alias "northstaros-qwen3.8:27b" `
  -ngl 99 -ngld 99 `
  --spec-type draft-mtp --spec-draft-n-max 6 --spec-draft-p-min 0.65 `
  -c 64576 -fa on `
  -ctk q8_0 -ctv q8_0 `
  -np 1 --jinja `
  --reasoning on --reasoning-effort xhigh --reasoning-budget -1 `
  --host 127.0.0.1 --port 8080 `
  --temp 0.35
