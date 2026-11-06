# Tys watchdog: keep exactly one launcher alive, across crashes and turn ends.
#
# The chat-attached agents (subagent sessions) are not this. They complete their
# task and stop, by design. What has to stay running is the loop: a plain OS
# process that does not depend on any session being open.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\tys-watchdog.ps1
#
# Behaviour:
#   * exactly one `tools/tys_launcher.py` process; a second is never started
#   * if it exits, it is restarted after -Interval seconds
#   * after a fast failure (model lane down) it backs off -BackoffMinutes instead
#     of hammering the model endpoint
#   * a STOP file ends the watchdog; it does not restart through it
#   * every decision is appended to logs/tys_watchdog.log

param(
    [int]$Interval = 20,
    [int]$BackoffMinutes = 5,
    [int]$MaxCycles = 200,
    [int]$MaxHours = 8,
    [string]$Worker = "deepseek",
    [switch]$Stop
)

$ErrorActionPreference = "Continue"
$root = (Get-Item (Join-Path $PSScriptRoot "..")).FullName
$log = Join-Path $root "logs\tys_watchdog.log"
$stopFile = Join-Path $root "STOP"
$heartbeat = Join-Path $root "state\tys_runner\heartbeat.json"
New-Item -ItemType Directory -Force -Path (Split-Path $log) | Out-Null

function Write-Log([string]$message) {
    $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:ss"), $message
    Add-Content -Path $log -Value $line -Encoding UTF8
}

function Get-Launcher {
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -match "tys_launcher\.py" }
}

if ($Stop) {
    foreach ($p in Get-Launcher) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
    Write-Log "watchdog stop requested; launcher stopped"
    exit 0
}

Write-Log ("watchdog starting (interval={0}s backoff={1}m worker={2})" -f $Interval, $BackoffMinutes, $Worker)

while ($true) {
    if (Test-Path $stopFile) {
        Write-Log "STOP file present; watchdog exiting"
        exit 0
    }

    $running = @(Get-Launcher)
    if ($running.Count -eq 0) {
        # Backoff after a fast failure: a dead model lane is not a reason to
        # restart every 20 seconds.
        $skip = $false
        if (Test-Path $heartbeat) {
            try {
                $hb = Get-Content $heartbeat -Raw | ConvertFrom-Json
                $ageMin = ((Get-Date) - [datetime]::Parse($hb.at)).TotalMinutes
                if ($hb.state -eq "stopped" -and $hb.reason -eq "model_lane_down" -and $ageMin -lt $BackoffMinutes) {
                    Write-Log ("launcher stopped: model_lane_down {0:N1}m ago; backing off" -f $ageMin)
                    $skip = $true
                }
            } catch { }
        }
        if (-not $skip) {
            $args = @("tools\tys_launcher.py", "--worker", $Worker,
                      "--max-cycles", "$MaxCycles", "--max-hours", "$MaxHours")
            $out = Join-Path $root "logs\tys_launcher.out.log"
            $err = Join-Path $root "logs\tys_launcher.err.log"
            $proc = Start-Process -FilePath "python" -ArgumentList $args -WorkingDirectory $root `
                -WindowStyle Hidden -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
            Write-Log ("started launcher pid={0}" -f $proc.Id)
        }
    } else {
        Write-Log ("launcher alive pid={0}" -f $running[0].ProcessId)
    }

    Start-Sleep -Seconds $Interval
}
