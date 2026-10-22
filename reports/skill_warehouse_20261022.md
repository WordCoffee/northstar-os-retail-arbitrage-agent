# Bojo skill warehouse — 2026-10-22

Bojo's tools now cover every service area, not just creative and SEO. A request
about a listing, an ad, A+, Creator Connections, a store page or a reseller rule
has a real tool behind it — no guessing.

## The warehouse

**24 tools**, grouped into **9 service areas**, all read-only or explicitly
gated (no spend, no publishing):

| service | tools |
|---|---|
| listing | `listing_audit`, `knowledge_lookup`, `seo_check`, `seo_retitle` |
| ads | `ads_math`, `knowledge_lookup`, `seo_negatives` |
| A+ | `knowledge_lookup`, `creative_plan` |
| Creator Connections | `knowledge_lookup`, `creative_plan` |
| brand-store | `knowledge_lookup`, `creative_plan` |
| reseller | `knowledge_lookup`, `listing_audit` |
| creative | `creative_plan`, `generate_image`, `design_brief`, `create_dieline`, `voice_*`, `list_templates` |
| research | `corpus_search`, `corpus_vector_search`, `corpus_drift`, `knowledge_lookup` |
| system | `system_status`, `improvement_status`, `service_catalog`, `purpose_command` |

### New this pass

| tool | what it does |
|---|---|
| `knowledge_lookup` | returns the verified DO/DON'T rules with source, confidence and pack version; below a 0.25 match it says it has nothing rather than quote an unrelated rule |
| `listing_audit` | deterministic audit of a title and up to 5 bullets: length, promo language, all-caps, prohibited claims, plus the rules that apply |
| `ads_math` | ACOS, break-even ACOS from unit margin, profit per ad dollar, TACOS |
| `improvement_status` | coverage, rule count, open gaps, pack versions, last cycle |
| `service_catalog` | the service → tool map, so Bojo can describe what it can do without improvising |

`service_catalog` is the "skill warehouse" Bojo reads about itself: every service
entry names the tools that handle it, and the test asserts those tools exist.

### Every focus gets the core skills

`tools_for_focus` now merges `CORE_TOOLS` (the five above) into every curated
focus list, so no focus can strand Bojo without a rule lookup or a listing audit.
`auto` already had all tools.

## Evidence — the model actually uses them

A live probe with the real local model, asked to audit
`BEST SELLER FREE SHIPPING Organic Mushroom Powder 8oz!!!`, produced:

```
CALL listing_audit  {"title": "BEST SELLER FREE SHIPPING Organic Mushroom Powder 8oz!!!"}
   -> 2 problem(s) found.  ok: True
CALL knowledge_lookup {"query": "Amazon listing title prohibited promotional language ..."}
   -> 5 rule(s) matched.  ok: True
```

It chose the right skills, with the right arguments, unprompted.

## UI

- The chat engine line now reads `Engine: <model> · 24 skills across 9 services`.
- `/api/chat/health` returns `tools` and `services` so any surface can show
  coverage without hard-coding it.
- Reading system verified in the shipped CSS: `--simple-col: 820px`,
  `--simple-msg: 16.5px`, 1.72 line-height — the requested measure and type size.
- `npm run build`: 0 errors. UI routes `/ui/` and `/ui/improvement` return 200.

## Gates

- 19 new tests in `test_skill_warehouse.py`; 101 passed across the chat/turn/
  shell/skill suites.
- Every service names only tools that exist (asserted).
- Unknown tool and bad arguments return honest results, never exceptions.

## Still needs your eyes (I cannot screenshot without a browser tool)

1. Sign in and confirm the palette, type and spacing match your reference.
2. Send the audit prompt above — expect the two tool calls and a corrected title.
3. Switch modes and confirm the composer controls read Creative / Standard /
   Thinking and that the answer shape changes.
4. Open Improvement and confirm the coverage tile and the GPU tile.
