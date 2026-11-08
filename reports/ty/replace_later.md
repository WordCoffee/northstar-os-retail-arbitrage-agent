# Replace later

Dev tools and models installed for the local lane that are not production-clean, with the
free or commercial-safe replacement still to be found. Nothing here ships to a customer;
it is development-only and logged so it cannot be forgotten.

| date | thing | why not production-clean | replacement to find |
|---|---|---|---|
| 2026-11-07 | `pynput` (LGPL-3.0) | LGPL-3.0; used unmodified as a dev dependency for the global kill-hotkey listener. Linking terms for a shipped binary are unreviewed. | A permissive hotkey library, or a small Win32 `RegisterHotKey` binding written in-house (BSD/MIT). |
| 2026-11-07 | ~~Ollama 0.40.4 runtime~~ | **Resolved, not a defect.** It was pinned to CPU by `OLLAMA_LLM_LIBRARY=cpu` and `OLLAMA_NUM_GPU=0`; with those cleared it discovers `library=CUDA compute=12.0`. See `reports/ty/d7_gpu_diagnosis.md`. | none |
