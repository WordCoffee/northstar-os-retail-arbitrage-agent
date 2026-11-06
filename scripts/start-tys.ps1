# Start the Tys watchdog detached, so the loop outlives this terminal and any
# chat session. Idempotent: a second call reports the existing watchdog.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-tys.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\start-tys.ps1 -Stop

param([switch]$Stop, [int]$Interval = 20, [int]$BackoffMinutes = 5)

$root = (Get-Item (Join-Path $PSScriptRoot "..")).FullName
$watchdog = Join-Path $PSScriptRoot "tys-watchdog.ps1"
$log = Join-Path $root "logs\tys_watchdog.log"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

$existing = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -match "tys-watchdog\.ps1" }

if ($Stop) {
    foreach ($p in $existing) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    & powershell -NoProfile -ExecutionPolicy Bypass -File $watchdog -Stop | Out-Null
    Write-Host "watchdog stopped"
    exit 0
}

if ($existing) {
    Write-Host ("watchdog already running pid={0}" -f $existing[0].ProcessId)
    exit 0
}

$proc = Start-Process -FilePath "powershell" `
    -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$watchdog`"", `
                    "-Interval", "$Interval", "-BackoffMinutes", "$BackoffMinutes" `
    -WorkingDirectory $root -WindowStyle Hidden -PassThru
$proc.Id | Out-File -FilePath (Join-Path $root "state\tys_runner\watchdog.pid") -Encoding ASCII
Write-Host ("watchdog started pid={0}; log: {1}" -f $proc.Id, $log)
