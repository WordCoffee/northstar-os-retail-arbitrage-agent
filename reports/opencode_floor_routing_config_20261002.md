# OpenCode Floor Routing — Configuration Report

**Date:** 2026-10-02
**Installed version:** `opencode v2.0.20`
**Scope:** OpenCode harness configuration only. No NorthstarOS application or production routing changes. No provider-account or credential changes. No paid calls, installs, or commits.

---

## 1. Files changed and backups

### Backups (created before any edit)

```
C:\Users\T2Hol\AppData\Local\Temp\opencode\opencode-floor-backup_20261002-220835\
  global-opencode.json      (copy of ~/.config/opencode/opencode.json,  1322 bytes)
  project-opencode.jsonc    (copy of <repo>/opencode.jsonc,              1183 bytes)
  BACKUP_PATH.txt
```

### Files modified

| File | Change |
|---|---|
| `C:\Users\T2Hol\.config\opencode\opencode.json` | Added `provider.openrouter.models` block with the three `:floor` entries; changed `model` and `small_model` to `openrouter/deepseek/deepseek-v4.1-flash:floor`. |
| `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\opencode.jsonc` | Converted `deepseek/deepseek-v4-flash-0731` and `z-ai/glm-5.3-flash` entries to their `:floor` keys; added the `deepseek/deepseek-v4.1-flash:floor` entry. `~anthropic/claude-sonnet-latest` untouched. |

Repo diff: `opencode.jsonc | 15 insertions(+), 8 deletions(-)`. No files committed.

### Preserved untouched (verified present in effective config)

- `provider.ollama-local` + all 4 local models (`northstar-qwen3:rev1`, `qwen3:14b`, `qwen3:4b`, `qwen2.5vl:7b`) and its `baseURL`.
- `tool_output`, `compaction`, `shell`, `mcp.browser` (still `enabled: false`), `plugins` (`-@crixue/opencode-voice-stt`).
- `mcp.playwright`, project `compaction`, `~anthropic/claude-sonnet-latest`.
- All agent permission rules (`.env` read-ask, external-directory prompts, etc.) — untouched.
- No credentials were read, printed, written, or modified. Only `options.apiKey` was used in a **throwaway temp config** pointing at a localhost mock, with the literal string `mock-not-a-real-key`.

### Self-detected defect and fix

My first global edit produced a **duplicate top-level `"provider"` key** (two `provider` objects). Caught by post-edit validation, merged into a single `provider` object. Verified: `duplicate top-level keys: none`, `providers: ['ollama-local','openrouter']`.

---

## 2. Effective defaults

| Setting | Value |
|---|---|
| `model` | `openrouter/deepseek/deepseek-v4.1-flash:floor` |
| `small_model` | `openrouter/deepseek/deepseek-v4.1-flash:floor` |

Confirmed via `opencode debug config` and `opencode api get /api/model/default`:

```json
{"id":"deepseek/deepseek-v4.1-flash:floor","modelID":"deepseek/deepseek-v4.1-flash:floor",
 "providerID":"openrouter","name":"DeepSeek V4.1 Flash (Floor)",
 "package":"@opencode/ai/providers/openrouter",
 "settings":{"baseURL":"https://openrouter.ai/api/v1","provider":{"allow_fallbacks":true}},
 "capabilities":{"tools":true,"input":["text","image"],"output":["text"]},
 "limit":{"context":1048576,"output":943718},
 "cost":[{"input":0.0198,"output":0.396,"cache":{"read":0.00291,"write":0}}],
 "status":"active","enabled":true}
```

`small_model` resolves into the built-in `title` agent: `agents.title.model = openrouter/deepseek/deepseek-v4.1-flash:floor`.

---

## 3. Selectable Floor model IDs

Registered with OpenCode's supported custom-model (`modelID` alias) schema. Outgoing ID = `modelID`, i.e. **no `openrouter/` prefix**.

| OpenCode selector | Outgoing OpenRouter ID |
|---|---|
| `openrouter/deepseek/deepseek-v4.1-flash:floor` | `deepseek/deepseek-v4.1-flash:floor` |
| `openrouter/deepseek/deepseek-v4-flash-0731:floor` | `deepseek/deepseek-v4-flash-0731:floor` |
| `openrouter/z-ai/glm-5.3-flash:floor` | `z-ai/glm-5.3-flash:floor` |

All three appear in `opencode models` and in `/api/model` with `enabled: true`.

### Base IDs verified against official documentation

OpenRouter's *Model Variants* docs confirm `:floor` is a **routing variant**, not a catalog entry:

> "Routing variants are accepted on any model ID and are never an entry in the models API. It changes provider ordering or eligibility for the request, and nothing else about the model. Context length, capabilities, supported parameters, and the base per-token price all come from the base model's entry."
> "…a picker built from `GET /api/v1/models` will not show them. To make them selectable, derive them from the base entries."

> "`:floor` — Sorts providers by price and admits flex service tier endpoints."

The installed catalog (`~/.cache/opencode/models.json`) has the three base slugs and **no** `:floor` entries, so registration was required. Base IDs matched official docs exactly.

### Metadata source — not invented

Every field was copied verbatim from the installed models.dev catalog entry for the corresponding **base** model (`attachment`, `reasoning`, `temperature`, `tool_call`, `modalities`, `limit`, `cost`). No capabilities, limits, or SDK settings were guessed.

| Base model | context | output | input cost | output cost | modalities |
|---|---|---|---|---|---|
| `deepseek/deepseek-v4.1-flash` | 1,048,576 | 943,718 | 0.0198 | 0.396 | text+image → text |
| `deepseek/deepseek-v4-flash-0731` | 1,048,576 | 943,718 | 0.01 | 1.28 | text → text |
| `z-ai/glm-5.3-flash` | 1,048,576 | 943,717 | 0.15 | 0.5 | text+image+video → text |

> **Deliberate change to call out:** the project's previous `deepseek/deepseek-v4-flash-0731` and `z-ai/glm-5.3-flash` entries carried `limit: {context: 120000, output: 8192}`. Those values did not match the catalog. Since the brief forbids inventing limits, the Floor entries use the real catalog values (1M context). **If the 120k/8k caps were a deliberate cost control, re-add them under the `:floor` keys in both files.**

---

## 4. Agent overrides

Full agent list from `opencode debug agents`:

| Agent | Mode | Model |
|---|---|---|
| `build` | primary | inherits root default |
| `plan` | primary | inherits root default |
| `compaction` | primary (hidden) | inherits root default |
| `summary` | primary (hidden) | inherits root default |
| `title` | primary (hidden) | inherits root default → resolved to `small_model` |
| `explore` | subagent | inherits root default |
| `general` | subagent | inherits root default |

**There were no pre-existing agent-specific model assignments to convert.** The only agent-level model in the tree was the implicit `title` binding derived from `small_model` (`ollama-local/qwen3:4b` → now the V4.1 Floor model). No `agents` block, no `.opencode/agent/*.md`, and no `command` model references exist in any discovered config.

Unresolved exceptions: **none.**

### Other active model assignments (reported, not replaced)

| Assignment | Status |
|---|---|
| `provider.ollama-local` → `northstar-qwen3:rev1`, `qwen3:14b`, `qwen3:4b`, `qwen2.5vl:7b` | **Still selectable**, untouched. |
| `~anthropic/claude-sonnet-latest` (project) | **Still selectable**, untouched. |
| `ollama-local/qwen3:4b` was the previous `small_model` | **No longer referenced by any setting**, but still registered and selectable. Its display name still reads "titles, voice-parse, small_model" — now stale wording only. |

### Application-layer model references — NOT touched (out of bounds)

These are NorthstarOS production routing, explicitly excluded by the boundaries. Flagged for your decision:

- `shared/model-suite.json` — `deepseek/deepseek-v4-flash-0731:free`, `deepseek/deepseek-v4-flash-0731`, `deepseek/deepseek-v4.1-flash` (unsuffixed)
- `autothink/memory/session-history.json` — same three slugs
- `autothink/backend/llm_adapter.py` — posts unsuffixed slugs to OpenRouter
- `00_STATE.json`, `HANDOFF.md`, `docs/PRODUCTION_BLUEPRINT.md`, `docs/*`, `reports/*` — narrative/doc references to the same slugs

No Nitro/Exacto settings were found anywhere in the config tree (searched `~/.config/opencode`, `%APPDATA%`, `%LOCALAPPDATA%`, `~/.local/share/opencode` config files, and the repo). The only binary matches were inside `opencode.db` session/message history — not routing settings. Nothing to remove.

**Redundant `provider.sort: "price"` removed** from the three Floor entries. Per OpenRouter docs, `provider.sort` does *not* opt into service tiers, whereas `:floor` is a strict superset (price sort **plus** flex-tier admission). Keeping it added nothing. `allow_fallbacks: true` was preserved on all three (endpoint-level fallback for the same model, not cross-model). No cross-model fallback was configured anywhere.

---

## 5. Offline validation results

**No live inference request was made. No credits spent.** All traffic went to `127.0.0.1`.

### 5a. Schema / parse validation
- Both files parse: `project jsonc parses OK`, `global json parses OK`.
- `opencode debug config` → 2 documents discovered (`~/.config/opencode/opencode.json`, repo `opencode.jsonc`) plus 2 directories. No errors.
- `opencode reload` → `Configuration reloaded`.

### 5b. Resolution validation
- `opencode models` → all three `:floor` selectors listed.
- `/api/model` → all three `enabled: true`, correct `modelID`, `package: @opencode/ai/providers/openrouter`, correct `limit`.
- `/api/model/default` → V4.1 Floor, `baseURL: https://openrouter.ai/api/v1`.

### 5c. Mock-transport request-construction test (the strong check)

Method: a Node HTTP mock on `127.0.0.1:8799` captured the outgoing request body. Ran OpenCode fully isolated via `OPENCODE_CONFIG` + `OPENCODE_CONFIG_DIR` + `OPENCODE_CONFIG_PROJECT_DISABLE=1` + `OPENCODE_DISABLE_MODELS_FETCH=1`, with `baseURL` pointed at the mock and a dummy key. Your real config, credentials, and the OpenRouter endpoint were never touched.

Captured bodies — **all three IDs arrive at `/api/v1/chat/completions` with no `openrouter/` prefix and with the `:floor` suffix intact**:

```
POST /api/v1/chat/completions   model=deepseek/deepseek-v4.1-flash:floor     <- root model (main path)
POST /api/v1/chat/completions   model=deepseek/deepseek-v4-flash-0731:floor  <- --model override
POST /api/v1/chat/completions   model=z-ai/glm-5.3-flash:floor               <- --model override
POST /api/v1/chat/completions   model=deepseek/deepseek-v4-flash-0731:floor  <- agent "general" override
POST /api/v1/chat/completions   model=z-ai/glm-5.3-flash:floor               <- agent "explore" override
POST /api/v1/chat/completions   model=deepseek/deepseek-v4.1-flash:floor     <- small_model / title agent
```

All request paths verified: **main model, `--model` override, small_model (title agent), and per-agent overrides.**

### 5d. Limitation (stated honestly)

The mock test ran against an **isolated scratch config** with a redirected `baseURL`, not against your live config file. It proves the outgoing body carries `modelID` verbatim through `@opencode/ai/providers/openrouter`'s OpenAI-compatible transport. What was *not* observed is a request built from the live `~/.config/opencode/opencode.json` itself, because doing so would require real OpenRouter traffic and credits — which the brief forbids. The live config is instead verified by `/api/model/default`, which reports the identical `modelID`, package, and baseURL.

The mock process was stopped; scratch artifacts remain at `C:\Users\T2Hol\AppData\Local\Temp\opencode\floor-mock\` (`mock-server.js`, `scratch-opencode.json`, `captured.json`).

---

## 6. Switching among the three models in v2.0.20

**In the TUI (current session only, does not rewrite config):**
```
/models
```
Pick any of `DeepSeek V4.1 Flash (Floor)`, `DeepSeek V4 Flash 0731 (Floor)`, `GLM 5.3 Flash (Floor)`.

**One-off run:**
```powershell
opencode run --model openrouter/deepseek/deepseek-v4-flash-0731:floor "your prompt"
opencode run --model openrouter/z-ai/glm-5.3-flash:floor "your prompt"
opencode run --model openrouter/deepseek/deepseek-v4.1-flash:floor "your prompt"
```

**Change the persistent default** — edit `model` (and `small_model`, if you want it moved too) in `C:\Users\T2Hol\.config\opencode\opencode.json`, then `opencode reload`.

**Pin an agent to one of the other two** — add to the global config, e.g.:
```json
"agents": {
  "general": { "model": "openrouter/deepseek/deepseek-v4-flash-0731:floor" },
  "explore": { "model": "openrouter/z-ai/glm-5.3-flash:floor" }
}
```

Notes for this version:
- `opencode run --model` takes `provider/model#variant` (`#` = reasoning-effort variant, **not** the OpenRouter suffix). The three Floor models also expose `#low`, `#medium`, `#high` reasoning variants.
- **Do not append `#` to `:floor`.** V2 treats everything after `#` as a reasoning variant.
- **The root default does not retain a variant** in v2.0.20 — use the `:floor` suffix in the ID (as configured) rather than a `#` variant.

> **These defaults are not a lock.** An explicit `opencode run --model ...`, a `/models` picker selection, or an agent-level `model` field always takes precedence over the configured default. This configuration sets defaults; it cannot prevent later explicit CLI or user overrides.

---

## 7. Restart / new-session instructions

1. `opencode reload` — already run; returns `Configuration reloaded`. Service healthy at `http://127.0.0.1:49374`.
2. If the TUI still shows the old model, restart the shared service:
   ```powershell
   opencode service restart
   opencode service status
   ```
3. **Start a new session** to pick up the new default. An already-running session keeps the model it was started with. Config files normally reload automatically, but an in-flight request keeps the settings it began with.
4. Verify:
   ```powershell
   opencode api get /api/model/default
   opencode models | Select-String floor
   opencode debug config
   ```

---

## 8. Rollback

```powershell
$bk = "C:\Users\T2Hol\AppData\Local\Temp\opencode\opencode-floor-backup_20261002-220835"
Copy-Item "$bk\global-opencode.json" "C:\Users\T2Hol\.config\opencode\opencode.json" -Force
Copy-Item "$bk\project-opencode.jsonc"   "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\opencode.jsonc" -Force
opencode reload
```

Pre-change state restored: `model: openrouter/deepseek/deepseek-v4-flash-0731`, `small_model: ollama-local/qwen3:4b`, project entries back to the unsuffixed 0731 / GLM 5.3 Flash keys with `sort: "price"` and the 120000/8192 limits.

The repo-side rollback will show as a revert of `opencode.jsonc` in `git diff` — nothing was committed, so no git operation is required.

Other pre-existing backups in `~/.config/opencode/` (`opencode old.json`, `opencode.json.BACKUP_20260914_202907`, `opencode.json.pre-safety-hardening-20260901-105918.bak`) were **not** touched.

Optionally clean up test scratch: `Remove-Item -Recurse -Force "C:\Users\T2Hol\AppData\Local\Temp\opencode\floor-mock"`.
