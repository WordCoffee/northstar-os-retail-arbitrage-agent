# Capability toolkit release — six modules, four wired tools, two declared CLIs (2026-11-14)

**Outcome: integrated and verified.** Six capabilities now live in `tools/ty_toolkit/`. Four are
offered to Bojo as real tools (handler + chat spec + registry entry); two are operator CLIs
registered as `declared` because they are not chat tools. Nothing claims a capability it cannot
run offline.

## What was added

| capability | module | wiring | status |
|---|---|---|---|
| Capture → typed API client (reverse-api-engineer pattern) | `tools/ty_toolkit/capture.py` | `generate_api_client` (chat + bojo) | **wired** |
| Open-licensed reference media (Openverse) | `tools/ty_toolkit/openverse.py` | `find_reference_media` (chat + bojo) | **wired** |
| Scraper hardening evaluation (`bla-agents`) | `tools/ty_toolkit/hardening.py` | `evaluate_scraper_hardening` (registry) + `scripts/harden-ui.ps1` | **declared CLI** |
| Clean-room UI benchmarking (craft-anything pattern) | `tools/ty_toolkit/ui_benchmark.py` | `benchmark_ui_spec` (registry) | **declared CLI** |
| Proactive proposals (OpenDuet pattern) | `tools/ty_toolkit/proposals.py` | `propose_improvements` (chat + bojo) | **wired** |
| Local/mesh model routing (MeshLLM pattern) | `tools/ty_toolkit/mesh_route.py` + `config/local_models.example.json` | `route_local_model` (chat + bojo) | **wired** |

Registry after regeneration: **54 tools — 52 wired, 2 declared, 5 unclaimed** (the unclaimed are
retired corpus tools and `read_open_design`, unchanged). `repair_citations --check` and
`build --check` both exit **0**.

## External tooling — evaluated, not asserted

| tool | finding | what was done |
|---|---|---|
| `reverse-api-engineer` | **MIT**, GitHub `kalil0321` (3.6k stars); **not an npm package** | wrapper `capture.py` implements the capability from an operator-supplied HAR/JSON capture; `--status` reports the upstream as optional and **not installed**. No clone and no crawl. |
| Openverse | public API; **HTTP 504 twice today** from this network, one earlier call answered and every row was then refused by the 800 px gate | module names the 504 exactly and never substitutes a query; `find_reference_media` is wired and returns licence + licence URL + source page per row |
| `bla-agents` | npm **3.3.2, MIT** | `inspect-release` on a copy of the built UI: **69 files, 1,645,684 bytes, 0 findings, no network, target unmodified**. `harden` on the copy: 60+ JS assets written under `.bla-hardened/`, **3 refused by name** (`index`, `studio`, `vendor`) for a lane-independent gate, originals untouched. **The live `dist/` tree hash is unchanged** (`4DF81E11FD30A2B0`). |
| craft-anything / OpenDuet / MeshLLM | patterns, no dependency | implemented as the UI-spec comparator, the proposals surface and the local/mesh router; none installs anything |

**Hardening is applied to a copy, not shipped.** The live build is byte-identical, so runtime and
the test suites cannot change. `scripts/harden-ui.ps1` runs the same controlled copy; replacing
`dist/` stays a reviewed, smoke-tested step.

## Measured

| check | result |
|---|---|
| `test_ty_toolkit.py` + `test_chat_tools_handlers.py` | **21 passed** (capture compiles, HAR dedupe, licence/size refusals, 504 refusal, hardening allow-gate, UI deltas, proposals owner gates, mesh health rules, four chat tools forwarded) |
| `test_service_registry.py` + `test_tool_offering.py` | **39 passed** |
| combined toolkit + registry + offering | **60 passed** |
| `repair_citations --check` / `build --check` | exit **0** / exit **0** |
| Playwright `g1_research_persist` (desktop + iPhone 12 WebKit) | **2 passed (6.5 s)** on the restarted stack |
| `python -m tools.ty_toolkit.capture` (Python + TypeScript) | 2 endpoints, generated Python **compiles** |
| `python -m tools.ty_toolkit.ui_benchmark` | flags missing header/nav/footer, heading and control deltas |
| `python -m tools.ty_toolkit.proposals --write` | 41 measured proposals, 6 surfaced, owner gates flagged |

## Honest limits

- **No live reverse-engineering of any portal.** The client generator consumes a capture the
  operator already has; it opens no socket. That is deliberate: no ToS-violating crawl and no
  credential storage.
- **Openverse is currently unreliable from this network** (504). The wiring is real and the
  refusal is exact; a working API key or a working gateway is an external dependency, not a code
  gap.
- **Hardened copies are not shipped.** The tool itself refused three bundles by name, and shipping
  decoy-injected bundles without serving and smoke-testing them would violate "runtime and tests
  unaffected".
- **Local routing is disabled by default.** `config/local_models.example.json` is an example; the
  router falls back to the verified free cloud model and says why. No local endpoint is treated as
  healthy without a probe.
- Proposals never write the queue; the director remains the only writer.

## Still outstanding from the previous (interrupted) sweep

Not part of this capability release, and not silently done: `state/vision/PAUSE` is still
present, the media lane is still off, and the git-history purge was **not** applied — a full
backup bundle was created (`northstar-pre-final-20261114-214330.bundle`, SHA256
`82FA4660…D337A`), `gitleaks` reported **18 leaks** in history, and the prepared rewrite is
stale relative to current commits. That remains an owner-reviewed operation.
