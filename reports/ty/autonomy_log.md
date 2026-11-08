# Ty Director — autonomy log

One line per cycle: workstream, role, cycle, score before/after, tag, tokens.

| date | unit | role | score before -> after | tag | tokens |
|---|---|---|---|---|---|
| 2026-11-07 | D0 | director | n/a (baseline) | `director-baseline` / `ty-dir-D0` | — |
| 2026-11-07 | D0 | director | suite RED (12-17 order-dependent failures) -> GREEN 6617 passed, 0 failed | `ty-dir-D0` | — |
| 2026-11-07 | D1 | director | probe: 4/4 concurrent sessions, GPU 16 GB free, Ollama library=cpu | `ty-dir-D1` | — |
| 2026-11-07 | D2 | director | kill 32556 -> restart 25644 in 5s; heartbeat 0 model calls | `ty-dir-D2` | 0 |
| 2026-11-08 | D3 | director | queue store + overlap serialisation + worktrees + staging merge; 9 tests | `ty-dir-D3` | 0 |
| 2026-11-08 | D4 | director | 29 services scored from artefacts; bar is per-dimension so 0 of 29 pass; top gap prospector 63 | `ty-dir-D4` | 0 |
| 2026-11-08 | D5 | director | gap-ranked bundles (>=5 points or >=3 gaps); replan writes a defect instead of idling | `ty-dir-D5` | 0 |
| 2026-11-08 | D6 | director | V5+V7 pass: blocked window yields no pixels; pause and kill stop input in <1s; 11 tests | `ty-dir-D6` | 0 |
| 2026-11-08 | D7 | director | V1+V2+V8 pass: llava 0.8s JSON, 20/20 element reads, 10.29GB VRAM with Bojo | `ty-dir-D7` | 0 |
