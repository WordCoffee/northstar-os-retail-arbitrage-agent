# OpenCode x northstaros-qwen3.8 - reasoning-effort fix (operator machine config)

- Date: 2026-10-14. Symptom: sessions on `ollama-local/northstaros-qwen3.8:27b` failed with
  "Jinja Exception: Unexpected reasoning effort high. Supported types are xhigh (default), medium, and low."
  and retried in a loop.
- Root cause: OpenCode offered a generic effort ladder (low/medium/high) for the custom provider; a session
  stored variant "high", which sent `reasoning_effort: "high"` - the Qwen3.8 GGUF chat template (rendered by
  Ollama) rejects any value outside {xhigh, medium, low}.
- Extra quirk (probed 2026-10-14 on Ollama /v1): `xhigh` is normalized to `"max"` (also rejected), `high`
  passes through as-is (rejected); only `low` and `medium` pass through cleanly, and an OMITTED field reaches
  the template default (`xhigh` = max reasoning).
- Fix (config: ~/.config/opencode/opencode.json; backup: opencode.json.bak.20261014):
  moved `ollama-local` into the V2-native `providers` block (the legacy `provider` shape rejects `variants`
  -> "kind=invalid, skipped malformed recognized value"), then remapped variants:
  low -> low, medium -> medium, high -> (omit field), xhigh -> (omit field). No model-level default.
  Result: every selectable variant sends a value the template accepts; high/xhigh = max reasoning (xhigh default).
- Verified: API probes (low/medium/omitted = HTTP 200; high = 500 "high"; xhigh = 500 "max") plus live
  OpenCode runs (medium in-session by the operator; `#high` via CLI = "ok", exit 0, 2026-10-14).
- Note: this is operator-machine config, outside any repo; the rationale lives here so future sessions do not
  re-derive the Ollama xhigh->max quirk.