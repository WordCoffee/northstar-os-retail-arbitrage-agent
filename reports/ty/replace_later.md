# Replace later

Dev tools and models installed for the local lane that are not production-clean, with the
free or commercial-safe replacement still to be found. Nothing here ships to a customer;
it is development-only and logged so it cannot be forgotten.

| date | thing | why not production-clean | replacement to find |
|---|---|---|---|
| 2026-11-07 | `pynput` (LGPL-3.0) | LGPL-3.0; used unmodified as a dev dependency for the global kill-hotkey listener. Linking terms for a shipped binary are unreviewed. | A permissive hotkey library, or a small Win32 `RegisterHotKey` binding written in-house (BSD/MIT). |
| 2026-11-07 | ~~Ollama 0.40.4 runtime~~ | **Resolved, not a defect.** It was pinned to CPU by `OLLAMA_LLM_LIBRARY=cpu` and `OLLAMA_NUM_GPU=0`; with those cleared it discovers `library=CUDA compute=12.0`. See `reports/ty/d7_gpu_diagnosis.md`. | none |
| 2026-11-09 | `ultralytics` (AGPL-3.0) | AGPL-3.0 with a network clause. Installed **dev-only** for the OmniParser-class grounding benchmark under a logged `GRANT:` (`reports/ty/grants.md`, 2026-11-09). It is imported only by `tools/vision/grounding.py` behind the `omniparser` backend, is never served and never shipped. If a grounding model is ever adopted into the product, the AGPL component must go. | A permissive icon detector with a compatible model licence: evaluate **YOLOv8-nano weights under a commercial licence from Ultralytics**, **Grounding DINO (Apache-2.0)** with a small open-vocabulary detector, or **OmniParser's own icon weights (CC-BY-4.0, attribution)** once their runner is licence-reviewed. |
| 2026-11-09 | `OmniParser` weights/method (CC-BY-4.0) | CC-BY-4.0, not AGPL, but attribution is mandatory and the model card's training-data provenance is not documented for commercial resale. Used as a reference for the benchmark, not adopted. | A model with a clear commercial grant, or keep UIA + DOM primary (the current default) until one is measured to beat 61.7 % by 10 points. |
