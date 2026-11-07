# GPU Isolation Script — forces all apps to iGPU except llama-server
# Run once after reboot. Sets Windows GPU preferences via registry.
#
# What it does:
#   - Sets GPU-hogging apps to "Power saving" (integrated GPU)
#   - Sets llama-server.exe to "High performance" (dedicated NVIDIA GPU)
#   - Result: dedicated GPU is ONLY used for local AI inference
#
# Registry: HKCU\Software\Microsoft\DirectX\UserGpuPreferences
#   GpuPreference=1; = Power saving (iGPU)
#   GpuPreference=2; = High performance (dGPU)

$ErrorActionPreference = "Stop"
$regPath = "HKCU:\Software\Microsoft\DirectX\UserGpuPreferences"

# --- Apps to force onto iGPU (power saving) ---
$igpuApps = @(
  "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
  "C:\Program Files\Google\Chrome\Application\chrome.exe",
  "C:\Program Files (x86)\MSI\MSI Center\MSI.TerminalServer.exe",
  "C:\Program Files (x86)\MSI\MSI Center\Sound Tune\pro\SoundTune.exe",
  "C:\Program Files (x86)\MSI\MSI Center\Mystic Light\LEDKeeper2.exe",
  "C:\Program Files\WindowsApps\Microsoft.YourPhone_1.26082.121.0_x64__8wekyb3d8bbwe\PhoneExperienceHost.exe",
  "C:\Windows\System32\ApplicationFrameHost.exe",
  "C:\Windows\SystemApps\MicrosoftWindows.Client.CBS_cw5n1h2txyewy\TextInputHost.exe",
  "C:\Windows\SystemApps\MicrosoftWindows.Client.CBS_cw5n1h2txyewy\SearchHost.exe"
)

# --- Apps to force onto dGPU (high performance) ---
$dgpuApps = @(
  "$env:USERPROFILE\tools\llama-cuda\llama-server.exe"
)

# Create registry key if it doesn't exist
if (-not (Test-Path $regPath)) {
  New-Item -Path $regPath -Force | Out-Null
}

# Set iGPU preferences
foreach ($app in $igpuApps) {
  if (Test-Path $app) {
    Set-ItemProperty -Path $regPath -Name $app -Value "GpuPreference=1;" -Type String -Force
    Write-Host "iGPU: $(Split-Path $app -Leaf)"
  }
}

# Set dGPU preferences
foreach ($app in $dgpuApps) {
  if (Test-Path $app) {
    Set-ItemProperty -Path $regPath -Name $app -Value "GpuPreference=2;" -Type String -Force
    Write-Host "dGPU: $(Split-Path $app -Leaf)"
  }
}

Write-Host ""
Write-Host "GPU isolation configured. Dedicated GPU reserved for llama-server only."
Write-Host "Restart apps for changes to take effect."
