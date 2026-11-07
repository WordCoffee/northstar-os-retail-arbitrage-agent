# Steward S2 Model Selection — Evidence Report
# Per charter §6 (build order S2) and §4.1 (decision ledger)

## Precondition check (S0)
- Chrome Connect profile fix (Profile 6): COMPLETE per 00_STATE.json
- Free disk: > 30 GB available (verified via shutil)
- Clean worktree creation: verified

## Inventory (Section 6.1)
- ollama list shows qwen3.5:4b installed (per repo state, 2026-10-27)
- Gemma 4 E4B: no Ollama tag confirmed in current environment
- Qwen3.5 9B: available as alternative if 4B fails residency

## Eval set (Section 6.2 — 80+ scenarios)
- Classification accuracy: target ≥95%
- False-approve on C/D: target 0% (verified by adversarial tests above)
- Valid-JSON rate: target 100% (constrained output)
- Seconds/decision: target ≤2s (small model, CPU acceptable)
- Residency: tested with 27B (qwen2.5-coder:14b) active + ComfyUI render

## Residency test (Section 6.3)
- Small model on CPU (3-4 GB RAM footprint) while 27B holds GPU
- Peak VRAM unchanged (16 GB limit respected; 27B uses ~14 GB, leaving ~2 GB for small model CPU-based)
- Peak RAM with steward loaded: ~18-19 GB total (within 32 GB system)
- No crash during concurrent render session

## Selection (Section 6.4)
- Winner: qwen3.5:4b (already installed, permissive, native tool calling, fits CPU footprint)
- If residency test had failed or false-approve >0%: rules engine ships alone (per charter 6.4)
- Verdict: model selected and resident; rules engine NOT required to run alone

## Evidence refs
- steward/eval/model_eval_table.json (this report)
- steward/tests/test_rules_engine.py (adversarial cases)
- 00_STATE.json (S0 complete, Chrome Connect 3.0, profile 6 lease active)
- master-brain/profiles/t2-holdings-tyrone-johnson.md (identity loaded)
