# Replace later

Dev tools and models installed for the local lane that are not production-clean, with the
free or commercial-safe replacement still to be found. Nothing here ships to a customer;
it is development-only and logged so it cannot be forgotten.

| date | thing | why not production-clean | replacement to find |
|---|---|---|---|
| 2026-11-07 | `pynput` (LGPL-3.0) | LGPL-3.0; used unmodified as a dev dependency for the global kill-hotkey listener. Linking terms for a shipped binary are unreviewed. | A permissive hotkey library, or a small Win32 `RegisterHotKey` binding written in-house (BSD/MIT). |
| 2026-11-07 | Ollama 0.40.4 runtime | Not a licence problem: it cannot see this GPU (`library=cpu`), so it cannot meet the VRAM budget in PATCH 1 item 4. | A CUDA-13 build that sees sm_120, or llama.cpp with CUDA 13; evaluated in D7. |
