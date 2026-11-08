# D1 — director probe

Measured 2026-11-08T04:50:57Z on this machine. Every line is command output, not an assumption.

## Headless session launch

- executable: `C:\Users\T2Hol\AppData\Roaming\npm\opencode.CMD`
- state: **ok**
- version exit: `0` — `opencode v2.2.5`
- `opencode run` flags present: `--agent, --format, --auto, --model, --session, --continue`

```
DESCRIPTION
  Run OpenCode with a message

USAGE
  opencode run [flags] [<message...>]

ARGUMENTS
  message... string    Message to send (optional)

FLAGS
  --continue, -c          Continue the last session
  --session, -s string    Session ID to continue, or to create if it does not exist
  --fork                  Fork the session before continuing
  --model, -m string      Model to use in the format provider/model#variant
  --agent string          Agent to use
  --format choice         Output format (choices: default, json)
  --file, -f string       File to attach to the message
  --title string          Session title
  --thinking              Show thinking blocks
  --auto                  Auto-approve permissions that are not explicitly denied

GLOBAL FLAGS
  --help, -h                                                          Show help information
  --version, -v                                                       Show version information
  --wizard                                                            Start wizard mode for a command
  --completions <bash|zsh|fish|powershell|sh|pwsh>                    Print shell completion script (choices: bash, zsh, fish, powershell, sh, pwsh)
  --log-level <all|trace|debug|info|warn|warning|error|fatal|none>    Sets the minimum log level (choices: all, trace, debug, info, warn, warning, error, fatal, none)
  --print-logs                                                        Print logs to stderr (server logs require --standalone
```

## Concurrency (OpenCode Go)

- **not probed yet** — run with --concurrency N. The cap stays at 4 until a measured number replaces it.

## Ollama inference device

- device: **gpu**
- last `inference compute`: `time=2026-11-07T22:47:57.706-06:00 level=INFO source=types.go:32 msg="inference compute" id=0 filter_id=0 library=CUDA compute=12.0 name=CUDA0 description="NVIDIA GeForce RTX 5080 Laptop GPU" libdirs=ollama,cuda_v13 driver=13.4 pci_id=0000:01:00.0 type=discrete total="15.9 GiB" available="14.7 GiB"`
- "no usable GPU found" seen in server.log: 1 times
- Measured separately: `qwen2.5vl:7b` loads 7.4 GB into system RAM at 100% CPU and 0 VRAM; a fresh server with `CUDA_VISIBLE_DEVICES=0` behaves identically. Ollama 0.40.4 cannot see this GPU (RTX 5080 Laptop, sm_120; driver CUDA UMD 13.4). The VRAM budget in PATCH 1 item 4 is therefore unmet for Ollama models until the runtime is upgraded or replaced; ComfyUI is the GPU path that does work.

## GPU

- state: **ok**
- `NVIDIA GeForce RTX 5080 Laptop GPU, 16303, 0, 16003, 0`

```
NAME                           ID              SIZE      MODIFIED           
bojo:latest                    0ff3112e9497    2.7 GB    About a minute ago    
bojo:cpu-quarantine            270a26491e3b    2.7 GB    About a minute ago    
gemma3:4b                      68ceab7e468a    3.4 GB    3 days ago            
llava:7b                       8dd30f6b0cb1    4.7 GB    3 days ago            
moondream:latest               55fc3abd3867    1.7 GB    3 days ago            
qwen3.5:4b                     d8b0f5e9760c    3.3 GB    6 days ago            
qwen2.5-coder:7b-parser-f16    577c810f2253    4.7 GB    6 days ago            
qwen3:8b                       500a1f067a9f    5.2 GB    6 days ago            
qwen2.5-coder:7b               dae161e27b0e    4.7 GB    6 days ago            
qwen2.5-coder:3b               f72c60cabf62    1.9 GB    6 days ago            
bojo:gpu-orig                  5f1256d250e9    2.7 GB    11 days ago           
qwen3.5:2b                     0689d44085e0    2.7 GB    11 days ago           
qwen2.5vl:7b                   5ced39dfa4ba    6.0 GB    2 weeks ago           
qwen3-embedding:0.6b           ac6da0dfba84    639 MB    2 weeks ago
```

## Host

- Windows-11-10.0.26200-SP0, python 3.14.5, 24 cpus
- RAM free 7.2 of 15.4 GB; disk free 11.17 GB

## Capture, UI Automation and input libraries

| library | importable | version |
|---|---|---|
| `mss` | yes | 10.2.0 |
| `dxcam` | no | ModuleNotFoundError: No module named 'dxcam' |
| `PIL` | yes | 12.3.0 |
| `uiautomation` | yes |  |
| `comtypes` | yes | 1.4.17 |
| `pywinauto` | no | ModuleNotFoundError: No module named 'pywinauto' |
| `pyautogui` | yes | 0.9.54 |
| `pynput` | yes |  |

## What this means for D6-D8

- **Dependencies are not installed.** No capture library, no UI Automation binding and no input library imported. D6 installs them (pre-approved) and records each in `provenance.csv`; D1's answer is the gap, not a failure.
- Capture: prefer a library that is importable *and* reports a real frame size in D6's acceptance test; importability alone is not capture.
- Structure first: UI Automation and the browser DevTools protocol are the primary read; pixels are the fallback.
- Concurrency: the measured ceiling is the cap. If it is below 4, the Director uses the measured number.
- The RAM figure above was read while the full test suite was running; D6 re-reads it idle before any GPU budget is claimed.
