# Northstar OS Launchers

Two double-click launchers for running the full Northstar stack with optimized local-model settings.

## Files

| File | Purpose |
|------|---------|
| `Launch-Northstar-Ubuntu.cmd` | Windows → WSL Ubuntu launcher (runs `launchers/ubuntu-start.sh`) |
| `Launch-Northstar-Windows.cmd` | Native Windows launcher (starts Ollama + OpenCode on Windows) |
| `ubuntu-start.sh` | Runs inside Ubuntu: starts Ollama + OpenCode service |
| `README.md` | This file |

---

## What Each Launcher Does

### Launch-Northstar-Ubuntu.cmd (WSL Ubuntu)
1. **Pre-flight checks** (both modes):
   - No other OpenCode/chromecontrol process running on either OS
   - No conflicting Ollama instance on the other OS
   - Ports 4097 (OpenCode) and 11434 (Ollama) free
   - Project path exists
   - Password file exists outside repo (`~/.northstar/opencode-password`)
2. **Starts Ollama (Ubuntu)** with optimized env:
   - `OLLAMA_GPU_OVERHEAD=4294967296`
   - `OLLAMA_FLASH_ATTENTION=1`
   - `OLLAMA_MAX_LOADED_MODELS=1`
   - `OLLAMA_KEEP_ALIVE=30s`
   - `OLLAMA_CONTEXT_LENGTH=8192`
   - Logs to `~/ollama.log`
3. **Waits** for Ollama on port 11434 (30s timeout)
4. **Configures & starts OpenCode service**:
   - `opencode service set hostname 127.0.0.1`
   - `opencode service set port 4097`
   - `opencode service start` (only if stopped)
5. **Prints summary** with `opencode service status` and Tailscale serve URL (if available)

### Launch-Northstar-Windows.cmd (Native Windows)
Same checks/behavior but runs **natively on Windows**:
- Starts Windows Ollama with identical env vars
- Starts Windows OpenCode service for the project
- Does NOT start Chrome Connect separately (OpenCode starts it)
- Logs: `%TEMP%\ollama-windows.log`, `%TEMP%\opencode-windows.log`

---

## Safety Rules (Both Launchers)

| Check | Action on Fail |
|-------|----------------|
| Other OpenCode running (any OS) | Print which one, exit |
| Other chromecontrol-mcp-server running | Print which one, exit |
| Other Ollama on other OS | Print which one, exit |
| Port 4097/11434 taken by unknown process | Report owner, stop |
| Project path missing | Exit with path |
| Password file missing/empty | Print how to create, exit |

**Never kills another process.** Always tells you what to stop manually.

---

## Password Setup (Required Once)

**Windows:**
```cmd
mkdir "%USERPROFILE%\.northstar"
echo your-opencode-password > "%USERPROFILE%\.northstar\opencode-password.txt"
```

**Ubuntu (inside WSL):**
```bash
mkdir -p ~/.northstar
echo 'your-opencode-password' > ~/.northstar/opencode-password
chmod 600 ~/.northstar/opencode-password
```

**Alternative:** Set env var `OPENCODE_SERVER_PASSWORD` (both launchers check it first).

**Never commit passwords.** Both password files are outside the repo.

---

## How to Run

### Ubuntu (WSL) Mode
1. Double-click `Launch-Northstar-Ubuntu.cmd`
2. A bash window opens, runs all checks, starts services
3. Window stays open — services keep running after you close it

### Windows Mode
1. Double-click `Launch-Northstar-Windows.cmd`
3. A cmd window opens, runs all checks, starts services
4. Window stays open — services keep running after you close it

**Run only ONE mode at a time.** The launchers enforce this.

---

## How to Stop

### Ubuntu Mode
```bash
# In Ubuntu terminal:
opencode service stop
pkill ollama
# Or just close the launcher window and run the above
```

### Windows Mode
```cmd
REM In cmd/powershell:
opencode service stop
taskkill /IM ollama.exe /F
```

---

## What Was Not Verified (Static Checks Only)

| Item | Status |
|------|--------|
| `ubuntu-start.sh` syntax | ✅ `bash -n` passes |
| `.cmd` line-by-line review | ✅ No syntax errors |
| Actual runtime behavior | ❌ Not executed (would start services) |
| Tailscale integration | ❌ Not tested (requires Tailscale auth) |
| GPU env vars effectiveness | ❌ Hardware-dependent |

---

## Environment Variables Used (Both Launchers)

### Ollama (identical on both OS)
```
OLLAMA_GPU_OVERHEAD=4294967296     (4 GB reserved for GPU overhead)
OLLAMA_FLASH_ATTENTION=1           (enable flash attention)
OLLAMA_MAX_LOADED_MODELS=1         (one model at a time)
OLLAMA_KEEP_ALIVE=30s              (unload after 30s idle)
OLLAMA_CONTEXT_LENGTH=8192         (context window)
```
**Note:** `OLLAMA_NUM_GPU_LAYERS` is deliberately NOT used (not a real Ollama setting).

### OpenCode
```
OPENCODE_SERVER_PASSWORD=<from file/env>  (never printed, never in repo)
```

---

## Ports

| Service | Port | Purpose |
|---------|------|---------|
| OpenCode | 4097 | API + UI |
| Ollama | 11434 | Local LLM API |

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| "Port in use" | Old process | `netstat -ano \| findstr :4097` → `taskkill /PID <pid> /F` |
| "Ollama not ready" | Model too large / VRAM | Use smaller model, or set `OLLAMA_NUM_GPU_LAYERS=35` (if supported) |
| "Password file empty" | File created but no content | Recreate with `echo 'password' > file` |
| "Other mode running" | Forgot to stop other launcher | Run the stop commands above |

---

## Git Ignore

Add to `.gitignore` (if not present):
```
# Launcher secrets (outside repo, but safe to ignore patterns)
**/opencode-password.txt
**/ollama*.log
**/opencode*.log
```