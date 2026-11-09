# Offered means callable: seven tools hidden, 27 unclaimed tools decided, seven jobs queued

2026-11-09, reg-03. Three jobs on top of reg-01's registry: make the offer list derive from
handlers, give every unclaimed `chat_tools.TOOLS` entry an owner or a retirement, and file one
build job per handler-less tool at the end of the ranked queue.

## 1. The offer rule is now derived

`offered` used to mean "a key exists in `TOOLS`". It now means **a callable handler exists**, and
that rule is applied at every point where Bojo's tools are offered:

| place | before | now |
|---|---|---|
| `chat_tools.tool_names()` | `list(TOOLS.keys())` | `offered_names()` — handler present, not retired (`chat_tools.py:2549`) |
| `chat_tools.ollama_tool_schemas()` | `TOOLS.get(name)` | skips any name that is not offered, **even when asked for by name** (`chat_tools.py:2554`) |
| `chat_tools.run_tool()` | assumed a handler | refuses a spec with no handler honestly (`chat_tools.py:2647`) |
| `bojo_tools_registry.names()` | `sorted(tools())` | `offered()` — callable and not retired (`bojo_tools_registry.py:47`) |
| `chat_tools.SERVICES` / `service_catalog` | counted `TOOLS` | counts the offered list (`chat_tools.py:1786`) |
| `ty/bojo_tool_list.json` | generated | regenerated; every `wired` entry is now an offered tool |

The chat adapter (`chat_router.py:257`) already builds its `tools` array from
`ollama_tool_schemas(tools_for_focus(...))`, so a stale focus list can no longer smuggle an
unimplemented name into the model's tool array — the filter is inside `ollama_tool_schemas`.
`bojo_tools_registry.tools()` still returns retired/kept handlers, because `call()` is how the
handler's own tests reach it; only `names()`/`offered()` gate the model.

`config/tool-surface.json` **does not exist in this repository.** A file by that name exists only
under `backups/ty_rollback/*/external/` and it is the Chrome Connect *host* surface declaration
(`raw_browser_tools_visible`), not a Bojo tool list. There was nothing there to change, and adding
a second tool-surface file that nothing reads would have been dead config, so I did not create one.

### The seven handler-less tools are not offered

`build_dieline, compose_listing, margin_report, plan_campaign, scan_products, track_keywords,
watch_competitor` are still declared on their services (`status: declared`, with the reason
recorded), but none of them appears in `tool_names()` or in any schema. They are absent because no
handler exists, not because a skip list names them.

## 2. The 27 unclaimed tools: 23 attached, 4 retired

Attached by adding a `wired` entry to the owning service's `bojo_tool` block
(`also_declares`) in `ty/service_registry.json`; the generated tool list follows. Every reason
cites the handler's own docstring or behaviour, not the tool's name.

| tool | decision | evidence |
|---|---|---|
| `apply_label` | **attach → design-studio** | handler composites the operator's real logo + copy onto a rendered pouch plate (`_t_apply_label`) |
| `build_package` | **attach → design-studio** | "Complete package: designed panels + dieline + mockup, gated on real inputs" |
| `build_preset` | **attach → autothink** | resolves BUILD presets — tools, memory retention, model family — that shape an AutothinK run |
| `build_utility` | **attach → design-studio** | builds one self-contained HTML page and stores it as `asset_type: utility-app` |
| `canvas_edit` | **attach → design-studio** | "Propose one bounded edit to the canvas the operator has open" — the studio canvas |
| `create_dieline` | **attach → design-studio** | layered SVG/PDF dieline from a print template; the wired form of the declared `build_dieline` |
| `creative_plan` | **attach → design-studio** | plan → confirm → reserve/generate/commit, i.e. the studio's create flow |
| `design_brief` | **attach → design-studio** | structured brief: palette, product, suggested dielines, before any render |
| `improvement_status` | **attach → hub** | knowledge coverage, rule count, open gaps — the knowledge-plane side of hub's posture |
| `knowledge_lookup` | **attach → hub** | sourced do/don't rules for every service; hub is the shared entry point |
| `place_logo` | **attach → design-studio** | logo at a measured anchor, with contrast and coverage reported |
| `plan_aplus` | **attach → design-studio** | A+ modules, eligibility, identity lock and copy checks — the studio's A+ surface |
| `plan_project` | **attach → autothink** | agent-kernel plan with lanes; "this is a plan, not an execution", approved in the build workspace |
| `plan_video` | **attach → design-studio** | UGC storyboard: scenes, fps, frames, claims check — the studio's video surface |
| `seo_negatives` | **attach → adpilot** | handler is documented as the "AdPilot hook" and returns a "AdPilot term triage" card |
| `seo_profile` | **attach → keywords** | shows the account's brand SEO profile and its keyword clusters |
| `seo_propose` | **attach → keywords** | proposes profile keyword additions from imported SQP rows, read-only |
| `seo_retitle` | **attach → listingforge** | handler is documented as the "SourceScout / ListingForge hook"; rewrites a title toward head terms |
| `service_catalog` | **attach → hub** | lists every service area and its tool — the suite map the hub routes from |
| `system_status` | **attach → hub** | engine + model posture; hub's own outputs include "engine and credit posture" |
| `voice_dub` | **attach → design-studio** | dubs a script through the local voice adapter (Creative Studio voiceovers) |
| `voice_list` | **attach → design-studio** | lists voice profiles for ad voiceovers |
| `voice_tts` | **attach → design-studio** | renders a script to a voiceover through the local voice adapter |
| `corpus_search` | **retire** | local research corpus search; no service in the registry owns a corpus or a research room |
| `corpus_vector_search` | **retire** | semantic corpus search; same missing owner |
| `corpus_drift` | **retire** | embedding-drift instrumentation; same missing owner |
| `purpose_command` | **retire** | read-only self-analysis of this repository (Thorn purpose commands); not a seller service |

Counts: **23 attached, 4 retired**. design-studio takes 13 because it is the only room that
produces assets; hub takes 4 because it is the entry point and posture page.

### How retirement is recorded, and one schema limit

Retirement is "not offered", not deletion. Each retired spec stays in `chat_tools.TOOLS` with
`"status": "retired"` and a one-line `retired_reason`; the handler and its tests still run, and
`run_tool` still answers a direct call (the existing corpus/purpose tests prove that). The single
source of truth for the reasons is the `RETIRED` map at `chat_tools.py:2514`.

They remain in the generated `unclaimed` list, which is the only place the tool-list schema can
carry a name with no owner. `tools/registry/schema.py:273` accepts only `wired|declared` for a
tool entry and `BOJO_STATUS = (wired, declared, none)` for a registry block, so a `retired` status
cannot be written into `ty/bojo_tool_list.json` or a service's `bojo_tool` block without editing
`tools/registry/*` — outside this lane's write scope and a collision risk with the registry lane.
The retirement record therefore lives in `chat_tools.RETIRED` (with `bojo_tools_registry.RETIRED`
as the same mechanism for domain tools) and the four names stay visible under `unclaimed`.
Re-attach them by moving the name out of `RETIRED` and into a service when a Research/Corpus
service exists.

## 3. Seven handler jobs, ranked by seller impact

Filed through `tools/director_queue.py` (`add_job` → `set_rank` → `mirror`), never by editing the
JSON. The store already held 28 jobs with a highest rank of **10**; the seven were queued
`+1 … +7`, and no existing job was re-ranked by this task (`events` shows rank writes only for the
seven new ids).

Order and why: the front of the funnel and the two deliverables a seller actually ships come
first; ranking/competitor work comes next; internal analysis comes last.

| rank | job | tool → service | why it sits here |
|---|---|---|---|
| 11 | `reg-03-scan-products` | scan_products → Product Finder / Prospector | you cannot list what you have not found |
| 12 | `reg-03-compose-listing` | compose_listing → ListingForge | the listing is the deliverable everything downstream scores |
| 13 | `reg-03-build-dieline` | build_dieline → Design Studio | a packaging picture is a real seller output; the geometry is already proven by `create_dieline` |
| 14 | `reg-03-track-keywords` | track_keywords → Keyword Tracker | coverage grows a listing that must exist first |
| 15 | `reg-03-watch-competitor` | watch_competitor → Competitor Monitor | ongoing grow work, below the listing that competes |
| 16 | `reg-03-margin-report` | margin_report → Profitability | internal maths over numbers the seller already entered; `ads_math` covers part of it |
| 17 | `reg-03-plan-campaign` | plan_campaign → AdPilot | spend follows a listing that already converts |

Each job carries unit `D12`, `write_paths` for the handler module and its test
(`Northstar_backend/bojo_tools/<tool>.py` + `Northstar_backend/test_bojo_tools_<tool>.py`), a
`rollback/pre-reg03-<tool>` tag, and its pytest as the acceptance gate.

Open queue after ranking:

```
rank  3  queued   reg-01-service-registry
rank  4  queued   sel-02-design-studio
rank  5  queued   sel-03-aplus
rank  6  queued   sel-04-packaging
rank  7  queued   ux-06-shell
rank  8  queued   ux-07-tabs
rank  9  queued   ux-08-scene
rank 10  queued   ux-09-design-studio-canvas
rank 11  queued   reg-03-scan-products
rank 12  queued   reg-03-compose-listing
rank 13  queued   reg-03-build-dieline
rank 14  queued   reg-03-track-keywords
rank 15  queued   reg-03-watch-competitor
rank 16  queued   reg-03-margin-report
rank 17  queued   reg-03-plan-campaign
```

Ranks 3-10 are the live director store's order. This branch's committed mirror was older (max
rank 9) and had `sel-02` at 2; taking the live store meant the mirror now shows the Director's
current order. I re-ranked nothing — the diff's rank changes for `sel-0*`/`ux-0*`/`reg-01` are the
Director's own `ranked` events, not this task's.

## Evidence

```
python -m pytest Northstar_backend/test_tool_offering.py -q
18 passed in 0.15s

python -m pytest Northstar_backend/test_service_registry.py Northstar_backend/test_chat_tools.py \
  Northstar_backend/test_chat_tools_domain.py Northstar_backend/test_skill_warehouse.py \
  Northstar_backend/test_shell_modes.py Northstar_backend/test_bojo_tools_registry.py \
  Northstar_backend/test_tool_gateway.py Northstar_backend/test_build_presets.py -q
107 passed, 1 warning in 21.22s

python -m pytest Northstar_backend/test_corpus.py Northstar_backend/test_corpus_drift.py \
  Northstar_backend/test_purpose_commands.py Northstar_backend/test_creative_plan.py \
  Northstar_backend/test_place_logo_tool.py Northstar_backend/test_plan_project_tool.py -q
113 passed, 3 warnings in 12.91s

python -m tools.registry.build --check
registry, tool list, workspaces and gaps agree
```

Tool list after regeneration: **44 owned tools — 37 wired, 7 declared, 4 unclaimed**.

`test_tool_offering.py` proves both directions: a spec with no handler (or a non-callable one) is
absent from `tool_names()` and from `ollama_tool_schemas()` even when named explicitly, a tool
with a handler is present, and a handler landing later (`scan_products` monkeypatched) makes the
tool appear with no catalogue edit. It also pins the generated list: every `wired` entry is
offered, every `declared` entry is not, and `unclaimed` is exactly the retired set.

## What I could not decide / did not do

- **Retirement has no first-class slot in the generated artefacts** (see the schema note). The
  decision is recorded — `chat_tools.RETIRED` + spec status + report — but `ty/bojo_tool_list.json`
  can only show the four as `unclaimed`.
- **Corpus tools are retired, not re-homed.** They are the strongest candidates to come back the
  day a Research/Corpus service exists; until then no room owns them.
- **`improvement_status` / `knowledge_lookup` went to `hub`** rather than being retired. Both are
  cross-service skills; hub is the only room that is a shared entry point and posture page.
  If the owner disagrees, moving either is a one-line registry change plus a `RETIRED` entry.
