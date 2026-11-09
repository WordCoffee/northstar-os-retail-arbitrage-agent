# reg-01 — the service registry

**Branch** `ty/reg-01` · **Date** 2026-11-08 · **Scope** record and generate, no rebuild

## What was built

One tracked artefact is the source of truth; three more are generated from it and
cannot drift because the tests regenerate them.

| File | Role |
| --- | --- |
| `ty/service_registry.json` | **Source of truth.** 29 entries, one per service in `ty/services.json`. |
| `ty/bojo_tool_list.json` | Generated: every tool a service owns, with wired/declared status. |
| `ty/northstar_workspaces.json` | Generated: the default-view workspace spec per service. |
| `ty/registry_gaps.json` | Generated: the services with `has_controls: false` and what is missing. |

Code: `tools/registry/backend_index.py` (mounted-route + tool-surface index),
`vision_walk.py` (Ty's Vision walk), `apply_vision.py` (merges a walk into the
registry's evidence), `schema.py` (validation), `build.py` (generator + `--check`).

## How each field was filled

**Backend.** `backend_index.MODULES` is the set of modules `main.py` actually
imports and includes (32 files, lines 52–163 and 2952–3032). Indexing every
`*.py` would have invented endpoints: the repo still carries `_main_dbg*.py`
copies that declare the same paths at earlier line numbers. That index resolves
**452 mounted routes**; each action stores its verb and path, and `build.py`
resolves the `file:line` from the decorator itself. A citation that moves is a
build failure (test: `test_every_action_citation_still_resolves`).

**Ty's Vision.** `python -m tools.registry.vision_walk` probes the desktop, the
dev server and Chrome, then opens each route through `tools/vision/chrome_uia.py`
and describes it with `tools/vision/understand.describe_page` when all three are
available. They were not available in this lane:

```
{"windows": 8, "foreground": "WindowsTerminal.exe", "chrome_windows": [],
 "locked": false, "server_8101": false, "server_8000": true}
```

So the walk fell back per route, exactly as instructed, and recorded *why*:

| vision | routes | what it means |
| --- | --- | --- |
| `live` | **0** | no Chrome window existed and nothing listened on 127.0.0.1:8101 |
| `screenshot` | **12** | committed capture named in `evidence.vision_note` (`reports/ui_audit_20261016/*.png`) |
| `audit` | **6** | title + controls recorded by the committed live walk in `ty/ux_audit.json` |
| `backend` | **11** | no page, no capture, no rendered audit row; backend only |

The desktop was **not** locked at walk time (`foreground: WindowsTerminal.exe`).
The blockers were the missing dev server and the absent Chrome window. Port 8000
did serve `/ui/`, but nothing here may start a browser or a server, so it was not
navigated. `ty/ux_audit_shots/` and `ty/dogfood_shots/` do not exist in this tree;
`reports/ty/shots/services/manifest.json` lists 24 captures whose PNGs are not
committed, so those could not be cited either.

The six `audit` rows and the two screenshot rows that also have audit data carry
shell chrome in their controls list (search box, zoom, Operator). That is labelled
`controls (shell chrome included)` in the note so it is not mistaken for the
service's own surface.

## Coverage

- **29 of 29** services described; **452** mounted routes indexed; **79** actions recorded.
- **Vision evidence: 29 of 29** — 0 live, 12 screenshot, 6 audit, 11 backend-only.
- **Controls: 16 of 29** services expose an input or a backend action; **13** do not.
- **10** services reach a write or external effect (`offerchisel`, `towncrier`,
  `autothink`, `jobs`, `keywords`, `beta-signup`, `design-studio`, `golden-goose`,
  `listingforge`, `adpilot`).
- **4** services make no backend call at all: `beta`, `beta-support`, `product-finder`, `socialpulse`.

## The generated Bojo tool list

21 tools claimed by services — 14 wired, 7 declared-but-unwired — 27 of the 41
`chat_tools.TOOLS` entries remain unclaimed (they belong to areas that are not
rooms: corpus, voice, SEO profile, creative surfaces).

| Tool | Status | Owning service | Also used by |
| --- | --- | --- | --- |
| `ads_math` | wired | auctioneer | adpilot, profitability |
| `build_dieline` | declared | design-studio | — |
| `catalog_pull` | wired | prospector | product-finder |
| `compose_listing` | declared | listingforge | — |
| `generate_image` | wired | design-studio | — |
| `golden_goose_scan` | wired | goldengoose | golden-goose |
| `handoff_to_autothink` | wired | autothink | — |
| `hub_status` | wired | hub | — |
| `list_templates` | wired | design-studio | — |
| `listing_audit` | wired | listings | — |
| `margin_report` | declared | profitability | — |
| `offer_recommendation` | wired | offerchisel | — |
| `optimize_listing` | wired | listings | — |
| `plan_campaign` | declared | adpilot | — |
| `plan_social` | wired | towncrier | socialpulse |
| `ppc_plan` | wired | auctioneer | adpilot |
| `scan_products` | declared | product-finder | — |
| `seo_check` | wired | keywords | keyword-tracker |
| `track_keywords` | declared | keyword-tracker | — |
| `watch_competitor` | declared | competitor-monitor | — |
| `write_content` | wired | towncrier | listingforge |

The seven `declared` tools are exactly the names `ty/services.json` advertises with
no handler in `chat_tools.TOOLS` or `bojo_tools_registry`: `build_dieline`,
`compose_listing`, `margin_report`, `plan_campaign`, `scan_products`,
`track_keywords`, `watch_competitor`. Each one records the nearest wired
equivalent, so the gap is visible instead of being papered over with a rename.

The 27 unclaimed tools are listed in `ty/bojo_tool_list.json["unclaimed"]`, and
`chat_service_areas` records where the coarser `chat_tools.SERVICES` mapping still
points at unclaimed tools (`knowledge_lookup`, `creative_plan`, the `seo_*` family,
the corpus tools, voice, `service_catalog`).

## Default-view workspaces

29 specs, each written from that service's own inputs/outputs. Layouts:

| Layout | Count | Services |
| --- | --- | --- |
| `feed` | 9 | hub, goldengoose, autothink, thewatch, account, foundation, beta-support, keyword-tracker, competitor-monitor |
| `split` | 8 | ledger, prospector, auctioneer, keywords, product-finder, golden-goose, adpilot, profitability |
| `board` | 6 | rankledger, rivalboard, jobs, beta-ops, listings, socialpulse |
| `wizard` | 5 | offerchisel, towncrier, beta, beta-signup, listingforge |
| `canvas` | 1 | design-studio |

`data_shown` and `inputs_required` are copied from the registry at generation time,
so an edit to an entry changes the workspace. `primary_action_source` names a real
registry action (or `local` where the only control is the page's own). The test
`test_workspaces_are_purpose_built_not_copies` requires the `why` to name at least
one of the service's own input/output words, rejects a restated label, and rejects
two services sharing one justification.

## Gaps — 13 services with no controls

`ty/registry_gaps.json`. These are recorded, not rewritten; the advanced view was
not touched.

| Service | Route | What is missing |
| --- | --- | --- |
| hub | /hub | `Run batch` / `Pin snapshot` only toast; gate switches are display-only |
| ledger | /ledger | nothing but two reads; no period control, no export |
| thewatch | /thewatch | no watch/unwatch, no threshold, no scan trigger |
| rankledger | /rankledger | no sort selector, no band threshold, no export |
| rivalboard | /rivalboard | no risk threshold, no seller filter, no drill-down |
| account | /account | entitlements and usage read-only; no plan change, export or seat request |
| foundation | /foundation | Refresh repeats the same twelve reads; no probe trigger, approval decision or export |
| beta | /beta | landing only; both buttons navigate |
| beta-support | /beta#support | static section; no ticket form, ticket queue lives at /support |
| beta-ops | /beta-ops | org open / export / audit are all navigation; no cohort filter |
| listings | /listings | New Rule toasts, History and Escalate navigate; no diff review or rule creation |
| keyword-tracker | /keyword-tracker | Track New, Reports and Verify only toast |
| competitor-monitor | /competitor-monitor | no ASIN add, no refresh, no comparison selector |

## Findings worth carrying forward

1. **SourceScout does not call its own API.** `ProductFinder.jsx` starts from
   `const PRODUCTS = []`, and adding an ASIN stages a row of `UNKNOWN`s in local
   state; `/api/products/finder` appears only in comments (:18–21, :124). The
   registry records zero actions for `product-finder` — the page is a workbench
   shell, not a reader. Its `has_controls: true` stands (the ASIN input exists),
   but the data behind it does not.
2. **`build_dieline`, `compose_listing`, `margin_report`, `plan_campaign`,
   `scan_products`, `track_keywords`, `watch_competitor` are advertised and
   unimplemented.** Seven of the fifteen tools `ty/services.json` names have no
   handler. This is a tool-surface gap, not a UI gap.
3. **The AdPilot capture is titled "ListingForge"** in `ty/ux_audit.json`, which is
   recorded verbatim in that entry's vision note. The route rendered; its document
   title did not change.
4. **`Listing Guardian` (`/listings`) and `Keyword Tracker` are the most
   control-starved working rooms**: both present buttons that only toast. They are
   the strongest candidates for a purpose-built Northstar workspace.

## Verification

```
$ python -m tools.registry.build --check
registry, tool list, workspaces and gaps agree

$ python -m pytest Northstar_backend/test_service_registry.py -q
................                                                         [100%]
16 passed in 1.08s
```

Sixteen tests: coverage, full-schema validation, action citations, vision honesty,
tool status truthfulness, declared-tool coverage, tool-list agreement with
`chat_tools.TOOLS`, tool-list derivation, owning-service integrity, workspace
coverage, workspace schema, purpose-built `why`, workspace derivation from the
registry, gap set equality, gap reasons, and generated-file freshness.

No Amazon host was contacted. No paid API was called. No dev server was started or
stopped. `App.jsx`, the shell and every advanced-view page are untouched.
