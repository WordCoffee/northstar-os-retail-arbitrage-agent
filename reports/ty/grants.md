# Grants

Capability grants: one dedicated commit each, message `GRANT: <what and why>`, rollback tag
immediately before, guardrail baseline re-recorded in the same commit, supervisor still running after.

| # | Date | What | Why | Rollback tag | Commit | Supervisor after |
|---|---|---|---|---|---|---|
| 01 | 2026-11-05 | Register three tools in `shared/provider-suite.json`: `mcp_client` (MIT), `web_research_trafilatura` (Apache-2.0), `web_research_ddgs` (MIT). New `tools/mcp_client.py`, `tools/web_research.py`, `tests/fixtures/mcp_echo_server.py`, two test modules, three `provenance.csv` rows. | The file is outside the loop's commit allowlist by design. Without the entries the adoption gate refuses every one of them with `unknown_tool`, so Ty could not consume an MCP server and could not research the web — the first two Phase B blockers, in dependency order (research first). | `autonomy-grant-01-pre` | `f029dd2b` | required: `scripts/continuous_loop.py --ready` run after this commit, fingerprint recorded below |
| 02 | 2026-11-05 | Change the local vision QC model in `shared/model-suite.json` (V1/V2/V3 `understand.local`) and `shared/provider-suite.json` from `qwen2.5vl:7b` to `gemma3:4b`, with `llava:7b` as the one-shot fallback. `Northstar_backend/local_vision.py` defaults to it, requests `format=json`, and retries once on the fallback. | Measured, not assumed: qwen2.5vl:7b returned 200 tokens of backslash/brace garbage for a JSON rubric prompt (and ` ``` ` for a prose one) on this runner, while gemma3:4b returned valid JSON in 16.9 s and llava:7b in 17.5 s. Vision QA was therefore reporting `unparsed` for every image — the instrument was broken, not the images. | `autonomy-grant-02-pre` | `4e69f0f1` | supervisor untouched |

## Guardrail / policy fingerprint after both grants

`scripts/continuous_loop.py` `policy_fingerprint()` -> `ok: true`, all five files
`match: true` (`AGENTS.md`, `config/continuous_loop_tasks.json`,
`scripts/continuous_loop.py`, `scripts/ty_task_runner.py`,
`tools/autonomy_patches.py`). The supervisor was not disabled, bypassed or
edited around; it still refuses unauthorized work (`--status` -> `stop=queue_blocked`,
2 policy blockers reported).

## Grant 02 details

**Scope (exact files):**

```
shared/model-suite.json        (V1/V2/V3 understand.local: qwen2.5vl:7b -> gemma3:4b)
shared/provider-suite.json     (local_vision_qc entry: name, licence, notes, evidence)
Northstar_backend/local_vision.py        (default + FALLBACK_MODEL + format=json + one retry)
Northstar_backend/test_local_vision.py   (4 new tests; 1 test pinned to behaviour, not default)
reports/ty/grants.md
```

**Why a grant:** both files sit outside the loop's commit allowlist, so this is a
registry/policy edit by the owner's standing authorization for this work order.

**Licence note:** gemma3:4b ships under the Gemma Terms of Use (not OSI). It is
pulled from the local Ollama store, makes no network call and produces no
resold artifact; `commercial_ok` is recorded as true for local QC use only. The
production-safe replacement (an Apache-2.0 VL model that actually answers JSON
on this runner) is logged in `replace_later.md`.

**Evidence at grant time:**

- `state/evidence/vision_model_probe.json`: gemma3:4b `valid_json: true` 16.9 s;
  llava:7b `valid_json: true` 17.5 s; qwen2.5vl:7b `valid_json: false`, garbage;
  moondream `valid_json: false`, rambles past its JSON.
- `probe_image_lanes.py --probe a9` -> verdict `ok`, `matches_brief: true`,
  one real issue ("Label text is unreadable"), 17.3 s, model `gemma3:4b`.
- `pytest test_local_vision.py` -> **24 passed**.

## Grant 01 details

**Scope (exact files):**

```
shared/provider-suite.json          (3 new tool entries; no existing entry changed)
tools/mcp_client.py                 (new)
tools/web_research.py               (new)
tests/fixtures/mcp_echo_server.py   (new, probe fixture)
Northstar_backend/test_mcp_client.py      (new, 4 tests)
Northstar_backend/test_web_research.py    (new, 16 tests)
provenance.csv                      (3 appended rows)
reports/ty/grants.md                (this file)
```

**What it does NOT do:** it does not touch the Chrome Connect host policy, the hardcoded
Amazon blocklist, the profile lease, the capability grants, the budget caps or the audit-hash chain.
`tools/web_research.py` *adds* a second enforcement point for the Amazon rule rather than
weakening the first: the blocklist is hardcoded, evaluated before any request leaves the
machine, and cannot be overridden by a CLI flag.

**Evidence at grant time:**

- `provider_suite.py --check mcp_client --provider local` -> `available on local (MIT, free_local)`
- `provider_suite.py --check web_research_trafilatura` -> `available on local (Apache-2.0)`
- `provider_suite.py --check web_research_ddgs` -> `available on local (MIT)`
- `pytest test_web_research.py test_mcp_client.py` -> **20 passed**
- `mcp_client.py --arg tests/fixtures/mcp_echo_server.py --list --call add` -> 2 tools, `sum: 5`
- `web_research.py --fetch https://www.amazon.com/dp/B01FYY3M38` -> `REFUSED: amazon_refused`, exit 1
