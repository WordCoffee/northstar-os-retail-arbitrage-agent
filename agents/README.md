# Agent roster

Bojo is the router. Each folder here is one specialist, materialised from
`Northstar_backend/specialists/registry.py` by `tools/build_agent_folders.py`.

| Agent | Folder | Chat tool | Status |
|---|---|---|---|
| Package Designer | `agents/package_designer/` | `build_package` | **BUILT + TESTED** |
| Listing Optimizer | `agents/listing_optimizer/` | `optimize_listing` | **BUILT + TESTED** |
| PPC Analyst | `agents/ppc_agent/` | `ppc_plan` | **BUILT + TESTED** |
| Research | `agents/research/` | — | exists as `agents/golden_goose_finder`, not routed yet |
| Amazon Image & A+ | `agents/image_aplus/` | — | **SPEC ONLY** |
| Social & Ad Graphics | `agents/social_graphics/` | — | **SPEC ONLY** |
| Video & UGC | `agents/video_ugc/` | — | **SPEC ONLY** |
| Content Writer | `agents/content/` | — | **SPEC ONLY** |

Each folder holds `prompt.md`, `inputs.json`, `tools.json`, `schema.json`, `README.md`.

## How a turn flows

```
operator message
   → specialists/router.py        deterministic classify + required-input check
   → chat_router                  prepends "[router] <agent> — …" to the system directive
   → model                        chooses the specialist tool and asks for gaps
   → specialists/<agent>.py       does the work, validates, returns assets
   → ChatSurface                  renders artefacts with real names/kinds
```

## Adding an agent

1. Add the spec to `specs/<agent>.md`.
2. Add the entry to `specialists/registry.py` (inputs, outputs, validators, keywords).
3. Implement `specialists/<agent>.py` with the same contract:
   `ok`, `status`, `summary`, `questions`, `assets`, `data`.
4. Add a chat tool in `chat_tools.py` and register it in `SERVICES` + the focus subset.
5. Add tasks to `tests/agents/tasks.json` and a case to `Northstar_backend/test_specialists.py`.
6. Run `python tests/agents/run_suite.py` and `pytest test_specialists.py test_no_egress.py`.

A folder regenerates from the registry, so the documentation cannot drift from the contract.
