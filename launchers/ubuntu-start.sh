#!/usr/bin/env bash
# launchers/ubuntu-start.sh
# Called from Windows: wsl -d Ubuntu -e bash "/mnt/c/.../launchers/ubuntu-start.sh"
# Starts Ollama (Ubuntu) + OpenCode service inside WSL Ubuntu.

set -euo pipefail

# --- config ---
PROJECT_ROOT="/mnt/c/Users/T2Hol/Desktop/Northstar OS Retail Arbitrage Agent"
OPENCODE_PORT=4097
OLLAMA_PORT=11434
OLLAMA_LOG="$HOME/ollama.log"
PASSWORD_FILE="$HOME/.northstar/opencode-password"
# ----------

echo "=== Northstar Ubuntu Launcher ==="
echo "Project root: $PROJECT_ROOT"
echo ""

# --- safety checks ---
# 1) Other mode running?
echo "[1/6] Checking for conflicting processes..."
if pgrep -f "opencode" >/dev/null 2>&1; then
  echo "  WARNING: opencode process found in Ubuntu. This may conflict with Windows mode."
  echo "  Run 'opencode service stop' in Ubuntu first, then retry."
  exit 1
fi
if pgrep -f "chromecontrol-mcp-server" >/dev/null 2>&1; then
  echo "  ERROR: chromecontrol-mcp-server process found in Ubuntu."
  echo "  Stop it first, then retry."
  exit 1
fi
# Check Windows processes via wslpath/ps (best-effort)
if command -v powershell.exe >/dev/null 2>&1; then
  if powershell.exe -Command "Get-Process -Name 'opencode' -ErrorAction SilentlyContinue" 2>/dev/null | grep -q .; then
    echo "  ERROR: OpenCode is running on Windows. Stop it there first."
    exit 1
  fi
fi
echo "  OK: no conflicting OpenCode/chromecontrol processes."

# 2) Ollama conflict (Windows side)
echo "[2/6] Checking for Windows Ollama..."
if command -v powershell.exe >/dev/null 2>&1; then
  if powershell.exe -Command "Get-Process -Name 'ollama' -ErrorAction SilentlyContinue" 2>/dev/null | grep -q .; then
    echo "  ERROR: ollama.exe is running on Windows. Close it (Task Manager) first."
    exit 1
  fi
fi
echo "  OK: no Windows ollama.exe running."

# 3) Port checks
echo "[3/6] Checking ports $OPENCODE_PORT (OpenCode) and $OLLAMA_PORT (Ollama)..."
for port in $OPENCODE_PORT $OLLAMA_PORT; do
  if ss -ltn 2>/dev/null | grep -q ":$port " || netstat -ltn 2>/dev/null | grep -q ":$port "; then
    owner=$(ss -ltnp 2>/dev/null | grep ":$port " | head -1 || netstat -ltnp 2>/dev/null | grep ":$port " | head -1)
    echo "  WARNING: Port $port is in use by: $owner"
    echo "  If this is an unknown process, stop it and retry."
    # Don't exit - let user decide
  else
    echo "  OK: Port $port is free."
  fi
done

# 4) Project path exists
echo "[4/6] Verifying project path..."
if [[ ! -d "$PROJECT_ROOT" ]]; then
  echo "  ERROR: Project root not found: $PROJECT_ROOT"
  exit 1
fi
echo "  OK: $PROJECT_ROOT"

# 5) Password file
echo "[5/6] Reading OpenCode password..."
if [[ ! -f "$PASSWORD_FILE" ]]; then
  echo "  ERROR: Password file not found: $PASSWORD_FILE"
  echo "  Create it with: mkdir -p ~/.northstar && echo 'your-password' > ~/.northstar/opencode-password && chmod 600 ~/.northstar/opencode-password"
  exit 1
fi
OPENCODE_PASSWORD=$(cat "$PASSWORD_FILE")
if [[ -z "$OPENCODE_PASSWORD" ]]; then
  echo "  ERROR: Password file is empty: $PASSWORD_FILE"
  exit 1
fi
echo "  OK: Password loaded (not printed)."

# 6) Project dir check (already done)
echo "[6/6] All pre-flight checks passed."
echo ""

# --- start Ollama ---
echo "=== Starting Ollama (Ubuntu) ==="
if ss -ltn 2>/dev/null | grep -q ":$OLLAMA_PORT " || netstat -ltn 2>/dev/null | grep -q ":$OLLAMA_PORT "; then
  echo "Ollama already listening on port $OLLAMA_PORT — skipping start."
else
  echo "Starting ollama serve with optimized env..."
  # Use exact env from spec (no OLLAMA_NUM_GPU_LAYERS)
  OLLAMA_GPU_OVERHEAD=4294967296 \
  OLLAMA_FLASH_ATTENTION=1 \
  OLLAMA_MAX_LOADED_MODELS=1 \
  OLLAMA_KEEP_ALIVE=30s \
  OLLAMA_CONTEXT_LENGTH=8192 \
  nohup ollama serve >> "$OLLAMA_LOG" 2>&1 &
  OLLA_PID=$!
  echo "  Started ollama (PID $OLLA_PID), logging to $OLLAMA_LOG"

  # wait for readiness
  echo "Waiting for Ollama on port $OLLAMA_PORT (timeout 30s)..."
  for i in {1..30}; do
    if curl -s "http://127.0.0.1:$OLLAMA_PORT" >/dev/null 2>&1; then
      echo "  Ollama ready."
      break
    fi
    sleep 1
    if [[ $i -eq 30 ]]; then
      echo "  ERROR: Ollama did not become ready in 30s. Check $OLLAMA_LOG"
      exit 1
    fi
  done
fi

# --- start OpenCode service ---
echo ""
echo "=== Starting OpenCode Service ==="
cd "$PROJECT_ROOT"

# Configure hostname/port (idempotent)
echo "Setting OpenCode hostname to 127.0.0.1..."
opencode service set hostname 127.0.0.1
echo "Setting OpenCode port to $OPENCODE_PORT..."
opencode service set port $OPENCODE_PORT

# Start if stopped
STATUS=$(opencode service status 2>/dev/null || echo "unknown")
if echo "$STATUS" | grep -qi "stopped\|not running"; then
  echo "Starting OpenCode service..."
  OPENCODE_SERVER_PASSWORD="$OPENCODE_PASSWORD" opencode service start
else
  echo "OpenCode service already running (status: $STATUS) — skipping start."
fi

# --- summary ---
echo ""
echo "=== SUMMARY ==="
echo "Project: $PROJECT_ROOT"
opencode service status
echo ""
if command -v tailscale >/dev/null 2>&1; then
  echo "Tailscale serve status (from Ubuntu):"
  tailscale serve status 2>/dev/null || echo "  (not configured or not running in Ubuntu)"
else
  echo "Tailscale not installed in Ubuntu — skipping."
fi
echo ""
echo "Ollama log: $OLLAMA_LOG"
echo "OpenCode port: $OPENCODE_PORT"
echo "Ollama port: $OLLAMA_PORT"
echo ""
echo "=== HOW TO STOP ==="
echo "  OpenCode:  opencode service stop"
echo "  Ollama:    kill $OLLA_PID  (or: pkill ollama)"
echo "  All:       opencode service stop && pkill ollama"
echo ""
echo "Window will stay open. Press Ctrl+C to exit this script (services keep running)."
# Keep window open
read -p "Press Enter to exit this window (services will continue)..."