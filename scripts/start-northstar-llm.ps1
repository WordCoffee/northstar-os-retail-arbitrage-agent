# NorthstarOS local LLM — high-performance lane (llama.cpp)
# Model: northstaros-qwen3.8:27b  (ISTA-DASLab GSQ-RCO IQ3_XXS + MTP head)
# Usage: powershell -ExecutionPolicy Bypass -File scripts\start-northstar-llm.ps1
# Serves an OpenAI-compatible API on http://127.0.0.1:8080/v1 (plus the built-in web UI on /)
#
# NOTES
# - MTP speculative decoding is bound via: --spec-type draft-mtp --spec-draft-n-max 4 --spec-draft-p-min 0.65
#   (the -mtp GGUF carries the multi-token-prediction head; no separate draft model needed).
# - Vision: --mmproj loads the BF16 projector (this is the only lane that gives the model eyes;
#   Ollama's local-create has no mmproj support).
# - VRAM: Ollama (the app lane) and llama-server both want the 16GB card. Unload Ollama first:
#     curl.exe -s http://127.0.0.1:11434/api/generate -d '{\"model\":\"northstaros-qwen3.8:27b\",\"keep_alive\":0}'
#   Ollama auto-reloads on the next request.

$ErrorActionPreference = "Stop"
$srv = "C:\Users\T2Hol\AppData\Local\Microsoft\WinGet\Packages\ggml.llamacpp_Microsoft.Winget.Source_8wekyb3d8bbwe\llama-server.exe"
$modelDir = "$env:USERPROFILE\models\northstaros-qwen3.8"
$model = Join-Path $modelDir "Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf"
$mmproj = Join-Path $modelDir "mmproj-Qwen3.8-27B-BF16.gguf"

& $srv `
  -m $model `
  --mmproj $mmproj `
  --alias "northstaros-qwen3.8:27b" `
  -ngl 99 -ngld 99 `
  --spec-type draft-mtp --spec-draft-n-max 4 --spec-draft-p-min 0.65 `
  -c 64576 -fa on `
  -ctk q8_0 -ctv q8_0 `
  -np 1 --jinja `
  --host 127.0.0.1 --port 8080 `
  --temp 0.35
