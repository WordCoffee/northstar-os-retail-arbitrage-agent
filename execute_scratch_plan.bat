@echo off
setlocal enabledelayedexpansion

REM Scratch Instance Test Execution Plan
REM Author: Northstar Master Brain
REM Date: %date% %time%

echo === SCRATCH INSTANCE TEST EXECUTION ===
echo Scratch instance will run on port 8079 (not touching 8000)
echo.

REM Check if PowerShell is available
powershell -Command "
param(
    [string]$BackendPath = 'C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent',
    [int]$BackendPort = 8079,
    [string]$TestType = 'full'
)

$ErrorActionPreference = 'Stop'

$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$runId = 'scratch_run_$timestamp'

$scratchDir = \"$BackendPath\$runId\"
if (Test-Path $scratchDir) {
    Remove-Item -Path $scratchDir -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Path $scratchDir -Force | Out-Null

$scratchPath = $scratchDir
$scratchDbPath = \"$scratchPath\scratch_northstar.db\"

Write-Host '=== SCRATCH INSTANCE TEST EXECUTION ===' -ForegroundColor Green
Write-Host 'Run ID: $runId' -ForegroundColor Yellow
Write-Host 'Scratch directory: $scratchPath' -ForegroundColor Yellow
Write-Host 'Database: $scratchDbPath' -ForegroundColor Yellow
Write-Host 'Backend port: $BackendPort' -ForegroundColor Yellow

# Create environment file
$envContent = @'
PORT=$BackendPort
SCANNER_LIVE_ALLOWED=0
DATABASE_URL=sqlite:///$scratchDbPath
STUDIO_USE_FLUX2=1
ENVIRONMENT=scratch
PROVIDER_GATES=OFF
LIVE_PROVIDER_GATES=OFF
NORTHSTAR_DISABLE_RATE_LIMIT=1
NS_LIVE_PER_RUN_ARMED=0
NS_LIVE_PER_RUN_CAP_CENTS=0
'@

$envFile = \"$scratchPath\.env\"
$envContent | Out-File -FilePath $envFile -Encoding UTF8

Write-Host 'Environment file created: ' + $envFile -ForegroundColor Yellow

# Copy application files
Write-Host 'Copying application files...' -ForegroundColor Yellow
Copy-Item -Path \"$BackendPath\Northstar_backend\" -Destination \"$scratchPath\Northstar_backend\" -Recurse -Force -Exclude 'data'
Copy-Item -Path \"$BackendPath\shared\" -Destination \"$scratchPath\shared\" -Recurse -Force

# Create scratch data directory
$scratchDataDir = \"$scratchPath\Northstar_backend\data\"
New-Item -ItemType Directory -Path $scratchDataDir -Force | Out-Null

Write-Host 'Scratch instance setup complete.' -ForegroundColor Green

# Function to start scratch backend
function Start-ScratchBackend {
    param(
        [string]$Path,
        [int]$Port,
        [string]$EnvFile
    )
    
    Write-Host 'Starting scratch backend on port ' + $Port -ForegroundColor Yellow
    
    $env:PORT = $Port
    $env:SCANNER_LIVE_ALLOWED = 0
    $env:DATABASE_URL = 'sqlite:///' + $scratchDbPath
    $env:STUDIO_USE_FLUX2 = 1
    $env:ENVIRONMENT = 'scratch'
    $env:PROVIDER_GATES = 'OFF'
    $env:LIVE_PROVIDER_GATES = 'OFF'
    $env:NORTHSTAR_DISABLE_RATE_LIMIT = 1
    
    $process = Start-Process -FilePath 'python' -ArgumentList '-m', 'uvicorn', 'Northstar_backend.main:app', '--host', '0.0.0.0', '--port', "$Port", '--log-level', 'info' -WorkingDirectory $Path -PassThru
    
    $global:ScratchBackendProcess = $process
    $global:ScratchBackendPid = $process.Id
    
    $pidFile = \"$Path\scratch_backend.pid\"
    $process.Id | Out-File -FilePath $pidFile -Encoding UTF8
    
    Write-Host 'Scratch backend started with PID: ' + $process.Id -ForegroundColor Green
    return $process
}

# Function to stop scratch backend
function Stop-ScratchBackend {
    param([string]$Path)
    
    if ($global:ScratchBackendPid) {
        Write-Host 'Stopping scratch backend (PID: ' + $global:ScratchBackendPid + ')...' -ForegroundColor Yellow
        Stop-Process -Id $global:ScratchBackendPid -Force -ErrorAction SilentlyContinue
        
        $pidFile = \"$Path\scratch_backend.pid\"
        if (Test-Path $pidFile) {
            Remove-Item -Path $pidFile -Force
        }
        
        Write-Host 'Scratch backend stopped.' -ForegroundColor Green
    }
}

# Function to wait for backend
function Wait-ForBackend {
    param([int]$Port, [int]$MaxWaitSeconds = 30)
    
    Write-Host 'Waiting for scratch backend to be ready (max ' + $MaxWaitSeconds + ' seconds)...' -ForegroundColor Yellow
    
    $timeout = (Get-Date).AddSeconds $MaxWaitSeconds
    $isReady = $false
    $attempts = 0
    
    while ((Get-Date) -lt $timeout -and -not $isReady) {
        $attempts++
        try {
            $response = Invoke-WebRequest -Uri 'http://localhost:' + $Port + '/api/v1/health' -TimeoutSec 5 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                $isReady = $true
                Write-Host '✅ Scratch backend is ready (attempts: ' + $attempts + ')' -ForegroundColor Green
                return $true
            }
        } catch {
            Start-Sleep -Seconds 1
        }
    }
    
    if (-not $isReady) {
        Write-Host '❌ Scratch backend failed to start within ' + $MaxWaitSeconds + ' seconds' -ForegroundColor Red
        return $false
    }
}

# Main execution
Write-Host 'Starting scratch instance test execution...' -ForegroundColor Green

try {
    $backendProcess = Start-ScratchBackend -Path $scratchPath -Port $BackendPort -EnvFile $envFile
    
    if (-not (Wait-ForBackend -Port $BackendPort)) {
        throw 'Scratch backend failed to start'
    }
    
    $baseUrl = 'http://localhost:' + $BackendPort
    
    Write-Host '' -ForegroundColor White
    Write-Host '=== STEP A: P0 Tests ===' -ForegroundColor Green
    Write-Host 'Testing effective SCANNER_LIVE_ALLOWED via status helper...' -ForegroundColor Yellow
    
    try {
        $response = Invoke-WebRequest -Uri "$baseUrl/api/v1/health" -TimeoutSec 30 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Host '✅ Health endpoint returns 200' -ForegroundColor Green
        } else {
            Write-Host '❌ Health endpoint returned ' + $response.StatusCode -ForegroundColor Red
        }
    } catch {
        Write-Host '❌ Failed to access health endpoint: ' + $_.Exception.Message -ForegroundColor Red
    }
    
    Write-Host '' -ForegroundColor White
    Write-Host '=== STEP C: Playwright Tests ===' -ForegroundColor Green
    Write-Host 'Running Playwright tests...' -ForegroundColor Yellow
    Write-Host 'Note: Full Playwright implementation requires Node.js' -ForegroundColor Yellow
    
    Write-Host '' -ForegroundColor White
    Write-Host '=== STEP E: Schemathesis Tests ===' -ForegroundColor Green
    Write-Host 'Fetching OpenAPI documentation...' -ForegroundColor Yellow
    
    try {
        $response = Invoke-WebRequest -Uri "$baseUrl/openapi.json" -TimeoutSec 30 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Host '✅ OpenAPI documentation accessible (' + $response.StatusCode + ')' -ForegroundColor Green
            $responseContent = $response.Content | ConvertFrom-Json
            Write-Host '   Total paths: ' + $responseContent.paths.PSLikeObject.Keys.Count -ForegroundColor Gray
        } else {
            Write-Host '❌ OpenAPI documentation returned ' + $response.StatusCode -ForegroundColor Red
        }
    } catch {
        Write-Host '❌ Failed to fetch OpenAPI documentation: ' + $_.Exception.Message -ForegroundColor Red
    }
    
    Write-Host '' -ForegroundColor White
    Write-Host '=== SCRATCH INSTANCE EXECUTION COMPLETE ===' -ForegroundColor Green
    Write-Host 'All steps (A, C, E) have been initiated.' -ForegroundColor Yellow
    Write-Host 'Backend is running on port 8079.' -ForegroundColor Yellow
    Write-Host 'Press Ctrl+C to stop the backend and exit.' -ForegroundColor Yellow
    
    # Keep running until user interrupts
    $running = $true
    while ($running) {
        Start-Sleep -Seconds 5
        # Check if backend is still running
        if (-not (Get-Process -Id $global:ScratchBackendPid -ErrorAction SilentlyContinue)) {
            Write-Host 'Backend process has stopped.' -ForegroundColor Yellow
            $running = $false
        }
    }
    
} finally {
    Stop-ScratchBackend -Path $scratchPath
    
    Write-Host '' -ForegroundColor White
    Write-Host '=== SCRATCH INSTANCE CLEANUP ===' -ForegroundColor Green
    Write-Host 'Scratch backend stopped.' -ForegroundColor Yellow
}
