<#
.SYNOPSIS
Benchmarks qwen3.8-27b-coder on Windows (native Ollama) and WSL2 (Ollama in Ubuntu).
Run on BOTH platforms and compare outputs.
#>

param(
    [string]$Model = "qwen3.8-27b-coder",
    [int]$Runs = 3,
    [string]$OutFile = "bench-results-$(Get-Date -Format 'yyyyMMdd-HHmmss').json"
)

$ErrorActionPreference = "Stop"

# --- Test prompts (identical on both platforms) ---
$prompts = @(
    @"
Write a Python class `RateLimiter` implementing token bucket algorithm with:
- async `acquire(tokens=1)` method that blocks until tokens available
- configurable rate (tokens/sec) and burst capacity
- thread-safe for concurrent callers
- type hints, docstrings, no placeholders
"@
    ,
    @"
Write a Rust function `parse_jsonl_validated` that:
- reads a JSONL file line by line
- validates each line against a serde_json::Value schema
- returns Vec<(usize, String)> of (line_number, error_message) for invalid lines
- uses `std::fs::File` and `std::io::BufRead`
- no unwrap/expect, proper error handling
"@
    ,
    @"
Create a TypeScript React component `DataTable` that:
- accepts `columns: ColumnDef<T>[]` and `data: T[]` as props
- supports sorting by clicking column headers (asc/desc toggle)
- supports row selection with checkboxes
- uses TanStack Table v8 patterns
- generic over T, fully typed
- no placeholder comments
"@
    ,
    @"
Write a Go function `ConcurrentFetch` that:
- takes a slice of URLs and maxConcurrency int
- fetches all URLs concurrently with semaphore limiting
- returns map[url]string{body} and error slice
- uses context.WithTimeout(5s) per request
- proper error handling, no goroutine leaks
"@
    ,
    @"
Write a SQL query (PostgreSQL) that:
- finds all users who placed orders in the last 30 days
- includes user_id, email, order_count, total_spent
- filters to users with order_count >= 3
- uses CTEs, proper indexes hinted
- no SELECT *
"@
)

# --- Helper: run one prompt, capture metrics ---
function Invoke-BenchPrompt {
    param($Prompt, $RunIndex)
    Write-Host "  Run $RunIndex..." -NoNewline
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $result = ollama run $Model $Prompt 2>&1
        $sw.Stop()
        $output = $result -join "`n"
        # Extract eval rate if Ollama prints it (--verbose)
        $tokSec = if ($output -match 'eval rate:\s+([\d.]+)\s+tok/s') { [double]$matches[1] } else { $null }
        $loadTime = if ($output -match 'load time:\s+([\d.]+)\s*([mun]?s)') { [double]$matches[1] } else { $null }
        $vram = (nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>$null | Measure-Object -Maximum).Maximum
        [pscustomobject]@{
            promptIndex = $RunIndex
            promptChars = $Prompt.Length
            responseChars = $output.Length
            tokPerSec = $tokSec
            loadTimeSec = $loadTime
            vramUsedMB = $vram
            elapsedSec = [math]::Round($sw.Elapsed.TotalSeconds, 2)
            success = $true
            error = $null
        }
    }
    catch {
        $sw.Stop()
        [pscustomobject]@{
            promptIndex = $RunIndex
            promptChars = $Prompt.Length
            responseChars = 0
            tokPerSec = $null
            loadTimeSec = $null
            vramUsedMB = $null
            elapsedSec = [math]::Round($sw.Elapsed.TotalSeconds, 2)
            success = $false
            error = $_.Exception.Message
        }
    }
}

# --- Warmup ---
Write-Host "Warming up..."
ollama run $Model "Hello" > $null

# --- Run benchmarks ---
$allResults = @()
$promptIdx = 0
foreach ($prompt in $prompts) {
    $promptIdx++
    Write-Host "`nPrompt $promptIdx/${prompts.Count}: $($prompt.Substring(0,60))..."
    $promptResults = @()
    for ($i = 1; $i -le $Runs; $i++) {
        $promptResults += Invoke-BenchPrompt -Prompt $prompt -RunIndex $i
    }
    $allResults += [pscustomobject]@{
        prompt = $prompt
        runs = $promptResults
    }
}

# --- Aggregate ---
$summary = $allResults | ForEach-Object {
    $ok = $_.runs | Where-Object success
    [pscustomobject]@{
        promptPreview = $_.prompt.Substring(0,80)
        avgTokPerSec = if ($ok) { ($ok | Measure-Object -Property tokPerSec -Average).Average } else { $null }
        avgVramMB = if ($ok) { ($ok | Measure-Object -Property vramUsedMB -Average).Average } else { $null }
        avgElapsed = ($_.runs | Measure-Object -Property elapsedSec -Average).Average
        successRate = ($ok.Count / $_.runs.Count)
    }
}

# --- Output ---
$report = [pscustomobject]@{
    platform = "Windows"
    model = $Model
    timestamp = Get-Date -Format "o"
    gpu = (nvidia-smi --query-gpu=name --format=csv,noheader 2>$null).Trim()
    vramTotalMB = (nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>$null | Measure-Object -Maximum).Maximum
    runsPerPrompt = $Runs
    results = $summary
    raw = $allResults
}

$report | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 $OutFile
Write-Host "`n=== SUMMARY ==="
$summary | Format-Table -AutoSize
Write-Host "`nSaved: $OutFile"