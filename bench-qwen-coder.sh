#!/usr/bin/env bash
# bench-qwen-coder.sh — identical benchmark for WSL2/Linux
# Run in WSL2 terminal: bash bench-qwen-coder.sh

set -euo pipefail

MODEL="${1:-qwen3.8-27b-coder}"
RUNS="${2:-3}"
OUTFILE="bench-results-$(date +%Y%m%d-%H%M%S).json"

# --- Test prompts (MUST match Windows version exactly) ---
read -r -d '' PROMPT1 <<'EOF'
Write a Python class `RateLimiter` implementing token bucket algorithm with:
- async `acquire(tokens=1)` method that blocks until tokens available
- configurable rate (tokens/sec) and burst capacity
- thread-safe for concurrent callers
- type hints, docstrings, no placeholders
EOF

read -r -d '' PROMPT2 <<'EOF'
Write a Rust function `parse_jsonl_validated` that:
- reads a JSONL file line by line
- validates each line against a serde_json::Value schema
- returns Vec<(usize, String)> of (line_number, error_message) for invalid lines
- uses `std::fs::File` and `std::io::BufRead`
- no unwrap/expect, proper error handling
EOF

read -r -d '' PROMPT3 <<'EOF'
Create a TypeScript React component `DataTable` that:
- accepts `columns: ColumnDef<T>[]` and `data: T[]` as props
- supports sorting by clicking column headers (asc/desc toggle)
- supports row selection with checkboxes
- uses TanStack Table v8 patterns
- generic over T, fully typed
- no placeholder comments
EOF

read -r -d '' PROMPT4 <<'EOF'
Write a Go function `ConcurrentFetch` that:
- takes a slice of URLs and maxConcurrency int
- fetches all URLs concurrently with semaphore limiting
- returns map[url]string{body} and error slice
- uses context.WithTimeout(5s) per request
- proper error handling, no goroutine leaks
EOF

read -r -d '' PROMPT5 <<'EOF'
Write a SQL query (PostgreSQL) that:
- finds all users who placed orders in the last 30 days
- includes user_id, email, order_count, total_spent
- filters to users with order_count >= 3
- uses CTEs, proper indexes hinted
- no SELECT *
EOF

PROMPTS=("$PROMPT1" "$PROMPT2" "$PROMPT3" "$PROMPT4" "$PROMPT5")

# --- Helper: run one prompt ---
run_prompt() {
    local prompt="$1"
    local run_idx="$2"
    echo -n "  Run $run_idx... "
    local start=$(date +%s.%N)
    local output
    output=$(ollama run "$MODEL" "$prompt" 2>&1)
    local end=$(date +%s.%N)
    local elapsed
    elapsed=$(echo "$end - $start" | bc -l)
    local tok_sec
    tok_sec=$(echo "$output" | grep -oE 'eval rate:[[:space:]]+[0-9.]+[[:space:]]+tok/s' | head -1 | sed -E 's/.*eval rate:[[:space:]]+([0-9.]+).*/\1/')
    local load_time
    load_time=$(echo "$output" | grep -oE 'load time:[[:space:]]+[0-9.]+[[:space:]]*[mun]?s' | head -1 | sed -E 's/.*load time:[[:space:]]+([0-9.]+).*/\1/')
    local vram_used
    vram_used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | sort -nr | head -1)
    local success=true
    local error=""
    if [[ $? -ne 0 ]]; then
        success=false
        error="ollama failed"
    fi
    # Output JSON for this run
    jq -n \
        --argjson promptIndex "$run_idx" \
        --argjson promptChars "${#prompt}" \
        --argjson responseChars "${#output}" \
        --argjson tokPerSec "${tok_sec:-null}" \
        --argjson loadTimeSec "${load_time:-null}" \
        --argjson vramUsedMB "${vram_used:-null}" \
        --argjson elapsedSec "$(printf '%.2f' "$elapsed")" \
        --argjson success "$success" \
        --arg error "$error" \
        '{promptIndex: $promptIndex, promptChars: $promptChars, responseChars: $responseChars, tokPerSec: $tokPerSec, loadTimeSec: $loadTimeSec, vramUsedMB: $vramUsedMB, elapsedSec: $elapsedSec, success: $success, error: $error}'
}

# --- Check dependencies ---
command -v ollama >/dev/null || { echo "ollama not in PATH"; exit 1; }
command -v nvidia-smi >/dev/null || { echo "nvidia-smi not found"; exit 1; }
command -v jq >/dev/null || { echo "jq not installed: sudo apt install jq bc"; exit 1; }
command -v bc >/dev/null || { echo "bc not installed: sudo apt install bc"; exit 1; }

# --- Warmup ---
echo "Warming up..."
ollama run "$MODEL" "Hello" >/dev/null

# --- Run benchmarks ---
ALL_RESULTS=()
PROMPT_IDX=0
for prompt in "${PROMPTS[@]}"; do
    PROMPT_IDX=$((PROMPT_IDX + 1))
    echo -e "\nPrompt $PROMPT_IDX/${#PROMPTS[@]}: ${prompt:0:60}..."
    PROMPT_RESULTS=()
    for ((i=1; i<=RUNS; i++)); do
        PROMPT_RESULTS+=("$(run_prompt "$prompt" "$i")")
    done
    ALL_RESULTS+=("$(jq -n --arg prompt "$prompt" --argjson runs "$(printf '%s\n' "${PROMPT_RESULTS[@]}" | jq -s '.')" '{prompt: $prompt, runs: $runs}')")
done

# --- Aggregate ---
SUMMARY=$(printf '%s\n' "${ALL_RESULTS[@]}" | jq -s '
    map({
        promptPreview: .prompt[0:80],
        avgTokPerSec: ( .runs | map(select(.success).tokPerSec) | select(length>0) | add/length ),
        avgVramMB: ( .runs | map(select(.success).vramUsedMB) | select(length>0) | add/length ),
        avgElapsed: ( .runs | map(.elapsedSec) | add/length ),
        successRate: ( .runs | map(select(.success)) | length / (.runs | length) )
    })
')

# --- GPU info ---
GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1 | xargs)
VRAM_TOTAL=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | sort -nr | head -1)

# --- Final report ---
jq -n \
    --arg platform "WSL2" \
    --arg model "$MODEL" \
    --arg timestamp "$(date -Iseconds)" \
    --arg gpu "$GPU_NAME" \
    --argjson vramTotalMB "$VRAM_TOTAL" \
    --argjson runsPerPrompt "$RUNS" \
    --argjson results "$SUMMARY" \
    --argjson raw "$(printf '%s\n' "${ALL_RESULTS[@]}" | jq -s '.')" \
    '{platform: $platform, model: $model, timestamp: $timestamp, gpu: $gpu, vramTotalMB: $vramTotalMB, runsPerPrompt: $runsPerPrompt, results: $results, raw: $raw}' \
    > "$OUTFILE"

echo -e "\n=== SUMMARY ==="
echo "$SUMMARY" | jq -r '.[] | "\(.promptPreview) | tok/s: \(.avgTokPerSec // "N/A") | VRAM: \(.avgVramMB // "N/A") MB | elapsed: \(.avgElapsed)s | success: \(.successRate*100)%"'
echo -e "\nSaved: $OUTFILE"