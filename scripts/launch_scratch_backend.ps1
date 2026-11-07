# PowerShell script to launch scratch backend on port 8079
# Requirements: SCANNER_LIVE_ALLOWED=0, scratch SQLite DB, provider gates off

$ErrorActionPreference = "Stop"

# Create scratch instance directory
$scratchDir = "scratch_instance_$(Get-Date -Format 'yyyyMMdd_HHmmss')"
$scratchPath = "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\$scratchDir"

Write-Host "Creating scratch instance directory: $scratchPath" -ForegroundColor Green
New-Item -ItemType Directory -Path $scratchPath -Force | Out-Null

# Create scratch SQLite database path
$scratchDbPath = "$scratchPath\scratch_northstar.db"
Write-Host "Scratch database path: $scratchDbPath" -ForegroundColor Yellow

# Create environment file
$envFile = "$scratchPath\.env"
@"
# Scratch instance configuration
PORT=8079
SCANNER_LIVE_ALLOWED=0
DATABASE_URL=sqlite:///$scratchDbPath
STUDIO_USE_FLUX2=1
NORTHSTAR_DISABLE_RATE_LIMIT=1
ENVIRONMENT=scratch

# Provider gates off
PROVIDER_GATES=OFF
LIVE_PROVIDER_GATES=OFF
"@" | Out-File -FilePath $envFile -Encoding UTF8

Write-Host "Environment file created: $envFile" -ForegroundColor Yellow

# Copy necessary files to scratch directory
Write-Host "Copying application files to scratch directory..." -ForegroundColor Yellow

# Copy Northstar_backend directory
Copy-Item -Path "Northstar_backend\" -Destination "$scratchPath\Northstar_backend\" -Recurse -Force -Exclude "data"

# Copy shared directory (for provider-suite.json)
Copy-Item -Path "shared\" -Destination "$scratchPath\shared\" -Recurse -Force

# Create scratch data directory for the scratch instance
$scratchDataDir = "$scratchPath\Northstar_backend\data"
New-Item -ItemType Directory -Path $scratchDataDir -Force | Out-Null

Write-Host "Scratch instance setup complete." -ForegroundColor Green
Write-Host "Running scratch backend on port 8079..." -ForegroundColor Green
Write-Host "Environment file: $envFile" -ForegroundColor Yellow
Write-Host "Database: $scratchDbPath" -ForegroundColor Yellow

# Start scratch backend in the background
$process = Start-Process -FilePath "cmd" -ArgumentList "/c", "cd /d $scratchPath && set PORT=8079 && set SCANNER_LIVE_ALLOWED=0 && set DATABASE_URL=sqlite:///$scratchDbPath && set STUDIO_USE_FLUX2=1 && uvicorn Northstar_backend.main:app --host 0.0.0.0 --port 8079 --log-level info" -WindowStyle Hidden -PassThru

Write-Host "Scratch backend started with PID: $($process.Id)" -ForegroundColor Green

# Save PID to file for later cleanup
$pidFile = "$scratchPath\scratch_backend.pid"
$process.Id | Out-File -FilePath $pidFile -Encoding UTF8

# Wait a moment for the backend to start
Write-Host "Waiting for scratch backend to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Check if the backend is running
$isRunning = $false
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8079/api/v1/health" -TimeoutSec 10 -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        $isRunning = $true
        Write-Host "✅ Scratch backend is running successfully!" -ForegroundColor Green
        Write-Host "Health check response: $($response.Content)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "❌ Scratch backend failed to start: $($_.Exception.Message)" -ForegroundColor Red
}

if (-not $isRunning) {
    Write-Host "Failed to start scratch backend. Exiting..." -ForegroundColor Red
    Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    exit 1
}

# Display running processes
Write-Host "Running processes:" -ForegroundColor Yellow
Get-Process -Id $process.Id | Format-Table -AutoSize

# Keep the script running until user interrupts
Write-Host "" -ForegroundColor White
Write-Host "Scratch backend is running. Press Ctrl+C to stop..." -ForegroundColor Cyan
Write-Host "Backend logs can be viewed in the console above." -ForegroundColor Yellow
Write-Host "Environment: $envFile" -ForegroundColor Yellow
Write-Host "Database: $scratchDbPath" -ForegroundColor Yellow

# Wait for user interrupt or timeout
$timeout = 300  # 5 minutes timeout
$endTime = (Get-Date).AddSeconds $timeout

while ((Get-Date) -lt $endTime) {
    Start-Sleep -Seconds 10
    Write-Host "Running... ($(Get-Date -Format 'HH:mm:ss'))" -ForegroundColor DarkGray
}

Write-Host "" -ForegroundColor White
Write-Host "Timeout reached. Stopping scratch backend..." -ForegroundColor Yellow

# Stop the backend
Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue

# Clean up PID file
if (Test-Path $pidFile) {
    Remove-Item -Path $pidFile -Force
}

Write-Host "Scratch backend stopped." -ForegroundColor Green

# Optional: Delete scratch directory (comment out if you want to keep it)
# Remove-Item -Path $scratchPath -Recurse -Force
# Write-Host "Scratch directory cleaned up." -ForegroundColor Green

Write-Host "Script completed." -ForegroundColor Yellow