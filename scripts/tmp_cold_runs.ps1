$ErrorActionPreference = "Continue"
$root = "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
$pidFile = Join-Path $root "dev-start.pids"
$results = @()

function Stop-DevServers {
    if (Test-Path $pidFile) {
        $ids = (Get-Content $pidFile -Raw).Trim() -split ","
        foreach ($id in $ids) {
            if ($id -match '^\d+$') {
                Get-CimInstance Win32_Process -Filter "ParentProcessId=$id" -ErrorAction SilentlyContinue |
                    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
                Stop-Process -Id ([int]$id) -Force -ErrorAction SilentlyContinue
            }
        }
        Remove-Item $pidFile -ErrorAction SilentlyContinue
    }
    Get-CimInstance Win32_Process -Filter "CommandLine like '%uvicorn%main:app%' OR CommandLine like '%vite --port 8101%'" -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
}

for ($i = 1; $i -le 5; $i++) {
    Write-Host ("===== RUN {0} / 5 =====" -f $i)
    Stop-DevServers

    $wrapper = Start-Process powershell -ArgumentList "-ExecutionPolicy","Bypass","-File","$root\scripts\dev-start.ps1" -WindowStyle Hidden -PassThru
    Write-Host ("dev-start wrapper PID={0}" -f $wrapper.Id)

    $ok = $false
    for ($t = 0; $t -lt 40; $t++) {
        Start-Sleep -Seconds 1
        try {
            $b = (Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -ErrorAction Stop).StatusCode
            $u = (Invoke-WebRequest -Uri "http://127.0.0.1:8101/" -TimeoutSec 2 -ErrorAction Stop).StatusCode
            if ($b -eq 200 -and $u -eq 200) { $ok = $true; break }
        } catch { }
    }
    if (-not $ok) {
        Write-Host ("RUN {0}: servers did not become ready" -f $i)
        $results += ("RUN {0}: FAILED (servers not ready)" -f $i)
        Stop-DevServers
        Stop-Process -Id $wrapper.Id -Force -ErrorAction SilentlyContinue
        continue
    }

    Push-Location $root
    $out = & npx playwright test tests/e2e/signin.spec.ts --project=chromium-desktop 2>&1 | Out-String
    $code = $LASTEXITCODE
    Pop-Location

    if ($code -eq 0) {
        $results += ("RUN {0}: PASS (exit 0)" -f $i)
        Write-Host ("RUN {0}: PASS" -f $i)
    } else {
        $results += ("RUN {0}: FAIL (exit {1})" -f $i, $code)
        Write-Host ("RUN {0}: FAIL" -f $i)
        Write-Host $out
    }

    Stop-DevServers
    Stop-Process -Id $wrapper.Id -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "===== SUMMARY ====="
$results | ForEach-Object { Write-Host $_ }
$passes = ($results | Where-Object { $_ -match "PASS" }).Count
Write-Host ("TOTAL: {0} / 5 passed" -f $passes)
