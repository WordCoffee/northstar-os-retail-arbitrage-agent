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
| 2026-11-08 | D8 | director | risk classes, verify-after-act (V4 live), injson (V6 live), Profile 6 lease, CDP browser layer; six-point parity 6/6 verified twice; V3 not_run (no CDP endpoint, needs owner); quarantine refused; qwen2.5vl retest reverses D7; grounding 61.7% on 40 screens | `ty-dir-D8` | 0 |
| 2026-11-08 | D9 | director | seller-tester: 32 briefs, programmatic scorers, gap filing, escalation; 28 tests; real pass 30 artefacts scored, 29 gaps filed | `ty-dir-D9` | 0 |
| 2026-11-08 | D10 | director | visual regression gate: 31 views, frozen seeded scenes, perceptual diff; 6/6 fixture pairs classified; live capture refused without a server (exit 2); 41 tests | `ty-dir-D10` | 0 |
| 2026-11-08 | D11 | director | intel plane A18-A21: 5 source connectors, licence policy, atomic write; live run 58 findings, 58/58 URLs verified; 54 tests | `ty-dir-D11` | 0 |
| 2026-11-08 | D13 | director | live mode text-first: observe narrates windows + element counts, asks answered from the observation, blocked windows yield no pixels; demo passes; 8 tests | `ty-dir-D13` | 0 |
| 2026-11-08 | D14 | director | computer mode behind scope+grants: write outside scope refused and leaves no file; PC mode needs flag AND grant; plan printed, not executed; 8 tests | `ty-dir-D14` | 0 |
| 2026-11-08 | D16 | director | model scout: router eval fixed (think=false); bojo 15/18, qwen3.5:4b 16/18 (+1 < margin 2) so incumbent kept; leaderboard written | `ty-dir-D16` | 0 |
| 2026-11-08 | D17 | director | REA vs Craft Anything on 3 targets, all six cells ran with artefacts; Craft Anything default (0.859/0.858/1.000), REA backup (0.753/0.270/0.752) | `ty-dir-D17` | 0 |
| 2026-11-08 | D17 | director | re-probe: REA ran on the open-source repo (exit 0, 10/10, artefact tracked); hosted and local-app have no result (REA exit 1, Craft Anything not installed). Earlier 3-target verdict withdrawn as unreproducible | `ty-dir-D17` | 0 |
| 2026-11-08 | D15 | director | independent verifier: 17 agree, 2 FAILED (D17 artefacts lost -> re-probed, V9 not done), 1 BLOCKED (V3 no CDP); digest bug fixed; risks stated, not hidden | `ty-dir-D15` | 0 |
| 2026-11-08 | D12 | director | 6 bundles merged to staging under gates: competitor-monitor 15->85, prospector/thewatch/rivalboard 15->75/75/75, 13 services +10 from the measured dimension, 2 at bar (listings, socialpulse 100); 53 new test ids from a real run | `ty-dir-D12` | 0 |
| 2026-11-11 | D12 | director | rerender-prompt-only: same seeds, 9/12 86.4 -> 10/12 93.9; the six 90.0 rows were a clipped contact shadow (bottom band 243.5) not the flat() branch; judge (gemma3:4b) 11/12 83.5 and names lettering as the remaining gap | ollback/pre-rerender-prompt-only-20261111 | 0 |
| 2026-11-11 | D3/D12 | director | queue/mirror divergence repaired (16 jobs recovered, 14 refreshed, rank migrated); heartbeat red on a lane error; dev-start pids resolved from listeners; PPC path proven through the API | - | 0 |
| 2026-11-11 | sel-06b | director | a second packaging form: brand_art dispatch + carton renderers; pouch sha256 unchanged; 17 tests; OCR gate both carton faces; judge 4/4 95 (plate synthetic, MEDIA_GEN_LIVE not 1) | `ty-dir-sel06b` | 0 |
| 2026-11-11 | D-011 | director | seller harness renders through product_picture.build: prompt-only 12/12 mean 97.5 mech, 11/12 94.9 judged; seller dimension now the app path; design-studio 75.9 -> 89.3, 4 at bar | `ty-dir-sel06`/`ty-dir-d11-scores` | 0 |
| 2026-11-11 | sel-07 | director | bundles measure as bundles: package_components + find_panel_quads + build(units); PO-004/PO-012 3 quads, fill 25.9%, 100; judged 12/12 98.3; seller 98.3, design-studio 89.8 | `8555c670` | 0 |
| 2026-11-11 | sel-refs | director | Openverse reference library: cc0/by/by-sa only, landing URL + size + packaging-term gates, file verified; 17 kept / 51 refused, 7 families, licence+URL per row; 8 tests | `09fd6521` | 0 |
| 2026-11-11 | sel-08 | director | 8 prompt-only briefs now reach the app path (8/8 97.5); 24 refused for six missing packaging forms; seller sample 12 -> 20 at 98.0; media flag now reads .env, status corrected | `abdfd917`/`1cd092cc` | 0 |
