# Competitor Reverse-Engineering — Packify.ai & DYP.ai

- **Date:** 2026-10-16
- **Targets:** `https://www.packify.ai` (Pacdora PTE LTD) and `https://dyp.ai`
- **Tooling:** REA 6.5.0 (`rea-agents`) — CLI/MCP reverse-engineering toolkit (`morluto/rea`), passive CDP attach to a dedicated Chrome 155 profile, static bundle analysis, script export + JS application analysis
- **Evidence pack:** `research/packify_dyp_re_20261016/` (in-repo). Raw working set: `C:\Users\T2Hol\Desktop\packify-dyp-re\`
- **Scope discipline:** public surfaces only — public HTML/JS bundles, public API docs, public marketing pages, and passive observation of the operator's own signed-in session (operator drove every action; no credentials entered, no CAPTCHA touched, no form submitted by the agent; no secrets captured — REA retains value-free body *shapes*, drops cookies/auth headers, redacts storage values). No competitor code was copied; findings are interface/behavior level for reimplementation with our own or OSS code.

---

## 1. Executive summary

Both products are **AI packaging-design tools** with the same core recipe:

> chat/prompt → LLM interprets brief → structured design spec → multi-image generation → canvas editor over a parametric dieline (SVG) → print-ready export → credit-metered subscription.

| | **Packify.ai** | **DYP.ai** |
|---|---|---|
| Owner / maturity | Pacdora PTE LTD — AI layer on Pacdora's 9-year-old 3D packaging engine; "200,000+ brands"; 20+ human designers; factory network | Small startup ("DYP"), #2 of the same niche, launched ~2025; solo-ish team signals (one Sentry project, Tally feedback form) |
| Frontend | Vue 3 + Vite + Pinia + Vue Router (MPA), ant-design-vue, Lottie | Next.js (App Router) + React, Radix, dark design system |
| Hosting/data | Own stack behind `www.packify.ai` + `api.pacdora.com`; Cloudflare CDN | Vercel + Supabase (auth + `user_subscription_state`) + `cdn.dyp.ai/save-points` |
| Agent | **"Deep Agents" layered generation** (`/api/deep-agents/run` + `layer/pause/regenerate/retry`), chat-first UX, "Initial Analysis" step | Single-shot generation + mockup scene composer; no agent chat |
| Differentiators | Pacdora 3D engine, layered editable dielines, team/enterprise, **public API** (`PackifyApiKey`, webhook callbacks), factories + AI quotation | Simplicity, print-ready files + mockup studio, cheap credits, Polar billing |
| Billing | Stripe. Free 100cr → $19.9/1,000cr → $29.9/2,500cr → $49.9/3,500cr (+10,000cr tier); API = Business tier | **Polar** (polar.sh). Credits w/ subscription+flexible balances; observed 15→12cr for one mockup op |
| Runtime verification | Operator ran one design generation (result observed; capture windows missed later actions — static evidence complete) | Operator ran one mockup creation; live capture confirmed credit polling + response schemas |

**Bottom line for us:** ~80% of both products is commodity "wheel" (billing rails, credit meter, canvas editor, dieline SVG math, background removal, upscaling, vectorize, PDF/zip export, i18n, analytics). The genuinely proprietary/moat pieces are exactly four: **(1) the layered agent generation loop with pause/regenerate + paid continuation, (2) the chat→structured-spec→dieline pipeline (prompt → editable, layer-separated vector dielines), (3) the scene/product-type mockup compositor with a curated template economy, and (4) model-access tiering + credit metering per feature.** Northstar OS already owns substrates for all four (AutothinK orchestration, design-studio engine, credit ledger, durable jobs) — see §6–§7.

---

## 2. Method & evidence inventory

REA workflows used (reproducible):

```bash
# passive page capture + script sources
rea inspect-web-page http://127.0.0.1:9222 <TARGET_ID> --observation-ms 1500 --include-script-sources --json
# saved-capture → script export → static JS application analysis
rea export-web-scripts <capture.json> <outdir> --json
rea analyze-javascript-application <outdir>/files --json
# static bundle intelligence (routes, endpoint candidates, vendor fingerprints)
rea analyze-web-bundle http://127.0.0.1:9222 <TARGET_ID> --fetch-source-maps --json
# live passive observation of operator-driven actions (value-free shapes)
rea inspect-web-page http://127.0.0.1:9222 <TARGET_ID> --observation-ms 360000 --include-json-body-shapes --include-websocket-shapes --json
# UI evidence
rea capture-web-screenshot http://127.0.0.1:9222 <TARGET_ID> --json
```

Coverage achieved:
- **Packify:** homepage capture (75 resources / 59 scripts), docs page, pricing page, signed-in app chat (56 scripts), full static analyzer run (1.62M AST nodes across 59 files, 1,709 findings), bundle analysis (57 route candidates, 9 endpoint candidates, vendor fingerprints), **115 API-ish paths + 294 URLs** mined from the exported app bundle.
- **DYP:** homepage capture (188 resources / 72 scripts), app dashboard (83 scripts, 1.47MB), **27 API paths** from app chunks; Sentry/Tolgee/Polar/Supabase fingerprints; Next.js route literals.
- **Live:** two 4-min + two 6-min passive windows; DYP window captured 8 real requests with body shapes (see below); operator-generated **actual outputs** for both tools (screenshots in evidence pack).

Key evidence files (in `research/packify_dyp_re_20261016/`):
| File | What it proves |
|---|---|
| `packify_web_endpoint_scan.txt` | 294 URLs + 115 client API paths + provider fingerprints (Packify) |
| `packify_app_endpoint_scan.txt` | Signed-in app bundle scan (297 URLs / 112 API paths) |
| `packify_docs_endpoint_scan.txt` | Docs chunk scan (nested docs SPA) |
| `packify_public_api_docs_extract.txt` | **Full public API documentation text** (auth scheme, endpoints, params, webhook contract) |
| `dyp_web_endpoint_scan.txt` / `dyp_app_endpoint_scan.txt` | DYP URL + 27 API surface paths (credits enum, print, mockup) |
| `runtime_dyp_live_capture.json` | Live passive capture: 8× `/api/credits/balance` with value-free response schema |
| `packify_design_chat_result.png` | Operator's generated design (agent narrative + "Version 1" render) |
| `dyp_mockup_studio_result.png` | Operator's mockup studio result (1328×1328 canvas, credit badge 15→12 in session) |
| `packify_api_docs_page.png`, `packify_design_chat_view.png` | UI structure evidence |

---

## 3. Packify.ai teardown

### 3.1 Identity
- Built by **Pacdora** (cdn assets `cdn.pacdora.com`, the client loads `Pacdora-v1.1.7-beta14.10.js` — Pacdora's 3D packaging engine — and bridges projects via `/api/pacdora/link`). Brand entity "Pacdora PTE LTD" (seen in the Stripe payment element config).
- Positions as "The first AI packaging design agent"; manufacturing connect ("2,000+ custom design projects"), human design services (20+ designers), enterprise logos (Morton Salt, Sourceful…).

### 3.2 Stack (confirmed fingerprints)
Vue 3 + Vite + Pinia + Vue Router (multi-page entries under `/mpa/`), ant-design-vue, Lottie, localForage; **socket.io** (`path:"/io/"`, join-room per generation, connect/disconnect handlers); **AWS S3 direct browser upload** (`/api/aws/token` → `@aws-sdk/client-s3` PutObject); **jsPDF + JSZip** client-side export; **Stripe** payments element mounted inline (`/api/pay/*`); Google OAuth + reCAPTCHA Enterprise; GA4/GTM + Microsoft Clarity + Facebook Pixel + Amplitude/Segment (analytics stack); caniuse-lite-era polyfills. Public docs SPA bundled inside the main router (`/docs` route).

### 3.3 Client API surface (BFF under `www.packify.ai/api/*` — 115 paths mined, highlights)
- **Chat/agent:** `/api/chat/{hello,message,action,action/retry,analyze,history,history/share,image/start,insert/message,package_data,suggestions,social_post_copy}` · `/api/quotation/{hello,message}` (AI quotation for manufacturing)
- **Deep-agents pipeline:** `/api/deep-agents/run` · `/run/layer` · `/run/pause` · `/run/regenerate` · `/run/retry` — layered, pausable, regeneratable generation; client event `onContinueDeepAgentLayering`, `deepAgentPaidContinuation` + `deepAgentPreviewElementUuid` billing hooks.
- **Generation:** `/api/generate/{prompt,text,text2image,image2image,fill,upscale,record,edit/expand/v2,edit/expand/process-text,edit/retry,composite/text/v2,mockup/removebg,project/images}` · `/api/paint/{imagine,retry}` · `/api/video/{generate,options}` · `/api/photoshoot/*` (templates, background w/ `extracted_coordinates`, image test)
- **Mockup/composite:** `/api/mockup/{erase,result,template/list,template/info,template/cate/list,custom}` · `/api/composite/material[/list]` · `/api/material`
- **Projects:** `/api/project` (create w/ `{fork_from, type, language}`), `/detail,/info,/view,/child,/child/list,/analyze,/name,/others,/like/image,/share/status,/package/list,/cate_preview_list`
- **Users/teams/pay:** `/api/user/*` (guest_login, accountLogin, oauth/token, me, consume, api_intention, upload/history) · `/api/team/*` · `/api/pay/*` (checkout, subscribe, topup, portal, upgrade, cancel, promotion)
- **Design data:** `/api/brand_kit[/apply,/generate_content]`, `/api/nutrition-table/edit`, `/api/font/list`, `/api/vector/search` (`{imageUrl}` → similar-design search), `/api/factory/list` + `/factory/search/city`, `/api/design_request/intent`, `/api/segment/box`, `/api/assets/upload`

### 3.4 Public API (docs text extracted — this is their B2B wedge)
- Base: `https://www.packify.ai/api/open/2025-10/` (**dated API versioning**)
- Auth: header `Authorization: PackifyApiKey <YOUR_API_KEY>`; keys issued on Business plan only; "API usage is metered in credits… only successful generation requests consume credits."
- **Create a design** (`packaging-design`, POST, direct generation now / conversational mode "coming soon"): `image_count`, `callback_url` (async webhook), `prompt`, `logo_url`, `aspect_ratio` (1:1 default; 1:1,3:2,2:3,4:3,3:4,16:9,9:16), `resolution` (1K/2K; 2K only for 1:1/16:9/9:16)
- **Create a photoshoot** (`packaging-photoshoot`, POST): target image URL + `coordinates[]` (`x,y,display_w/h,crop_x/y/w/h,rotation,source_w/h`) + either `background_url` or background `prompt`
- **Callback contract:** POST JSON to callback URL on completion; retries on non-200 (periodic) / unreachable (limited period); 200 = delivered. "Callback Request Body" section exists in docs.

### 3.5 Editor & production pipeline
- Chat-first: "What would you like to design?" → agent "Initial Analysis" narrative → `Version N` renders → suggestion chips ("Make an Amazon main image from this pack", "Create two more flavor variants…") → refine loop.
- Editor: Mockup/Dieline switch over Pacdora's knife/dieline canvas (`data-pacdora-ui="dieline"`), dieline settings (dimensions, bleed), element editor (text groups incl. **Nutrition Facts Panel**, net-weight, badges), 3D view + "Edit in 3D & Download PDF", layered export (`Export dieline…` chat command), client-side jsPDF/JSZip export, S3 uploads.
- **Layered dieline generation is their crown jewel:** "generate a **layered, editable dieline**. Credit cost varies with the number of generated layers" · preview **5 credits**, full **~100 credits** ("~100 credits · 50% Off").

### 3.6 Economy (from bundle + pricing page)
- Free 100 one-time credits; **10 credits** per AI design/edit; **5** per photoshoot image; ~10cr per generated image in editor flows; dieline-layer generation ~100cr (5cr preview). Top-up credits (12-month validity) after subscription credits.
- Plans: Basic **$19.9/mo** (1,000cr, personal license, standard queue) · Pro **$29.9/mo** (2,500cr, priority queue, **premium image models**, **advanced understanding agent**, beta models) · Business **$49.9/mo** (3,500cr, company license, team, **API access**, **export dielines**, high-quality exports) · 10,000cr tier. Yearly: $179/yr (~$14.9/mo). Seats $9.9/mo. Model quality tiers visible in client: `Fastest · Latest · Smart · Newest` (Pro).

### 3.7 Moat vs wheel classification (Packify)
- **MOAT:** layered "deep agents" generation w/ pause/regenerate/paid-continuation · prompt→layered-editable-dieline pipeline · Pacdora 3D engine + model library (ctree/materials/fonts) · factories + AI-quotation marketplace · tiered model access as a subscription lever.
- **HYBRID:** chat UX (commodity pattern, strong execution), mockup compositing (Pacdora templates = catalog moat, tech = commodity), brand kit (commodity pattern), vector search (commodity tech).
- **WHEEL:** auth, teams, Stripe billing, credits meter, S3 upload, jsPDF/JSZip export, i18n, analytics, reCAPTCHA.

---

## 4. DYP.ai teardown

### 4.1 Identity & stack
- Positioning: "Generative AI Packaging Design & Print-Ready Files." Single public marketing page + `/app` workspace. No public docs, no public pricing page (both 404 server-side).
- **Next.js App Router on Vercel** (high-confidence fingerprints ×3), React, Radix UI primitives, dark brand theme (verified visually), Tolgee i18n SaaS (`app.tolgee.io`), GTM/GA, lite-youtube-embed, Sentry (heavily instrumented, filters `/api/generate`, `/api/upload`, `/monitoring` from perf traces).
- **Supabase** (`*.supabase.co`): client-side auth + reads of table **`user_subscription_state`** (`plan_name` per user). Server does the rest.
- **Polar (polar.sh) billing** (`/api/polar/subscriptions`; `planType` check `"starter"` in layout); CDN `cdn.dyp.ai/save-points/{user_id}/{design_id}/thumbnail.png`.

### 4.2 App routes (from literals)
`/app` (dashboard: "Turn your idea into Packaging" → **Print Design** / **Mockup Design** cards) · `/app/dashboard` · `/app/editor/workspace?designId=` · `/app/mockup/studio?designId=` · `/app/gallery` · `/app/account`, `/app/account/pricing` · `/app/sign-in`, `/app/sign-up`.

### 4.3 API surface (27 paths, full list in evidence)
- **Credits:** `/api/credits` (feature_costs) · `/credits/balance` (→ `{balance, flexible_balance, subscription_balance, has_unlimited_access}` **confirmed live**) · `/credits/cost` (`{featureName}`) · `/credits/use` (`{featureName, metadata}`, `quotaExceeded` handling, client event `creditDeducted`) · `/credits/history?limit&type=usage`. Feature enum: `generation · image_generation · mockup_generation · export_300 · export_600 · export_vectorize · upscale_2x · upscale_4x · bg_remove · vectorize` (+`legacy_mode`).
- **Generation:** `/api/generate` (primary) · `/api/upload` · `/api/llm/translate`
- **Mockup:** `/api/mockup/classification` (uploaded-image classification) · `/text2img` (`{prompt, product_type_id, product_name, design_id, scene_id, aspect:"match_input_image", tool:"mockup generation"}`) · `/image-edit` · `/upload-images` · `/designs/{create,update,delete}`
- **Print:** `/api/dieline_generator/label` (`{type, length, width, radius?, save}` → `{svg_string, id}` — **server-side parametric label/dieline SVG generator**; types incl. `rounded_rectangle`) · `/print/designs` (CRUD, `{title, description, product_id}`) · `/print/save-designs` (multipart: `thumbnail` PNG + `design_id` + `canvas_data` JSON + `image_url_id`; GET by `design_id`) · `/print/upload-images` · `/print/work-history`
- Misc: `/api/projects` · `/api/favorites/toggle` · `/api/gallery/try-now` · `/api/broadcast` · `/api/polar/subscriptions`

### 4.4 Flows
- **Mockup flow (observed live by operator):** upload → classification → pick **product type** + **scene style** (or custom prompt / keep-original-scene) → create mockup design whose description is annotated `[CUSTOM PROMPT]/[SCENE]/[PRODUCT]` (their prompt-assembly convention) → `/mockup/text2img` → studio canvas (Edit/Product/Scene/History rail; prompt→Generate; Auto-Saved; Export). Credits consumed 15→12 for one operator run.
- **Print flow:** choose dieline (label types with dimensions) → server returns SVG dieline → create design record → `/app/editor/workspace?designId=` canvas editor (fabric-style `serializeCanvasData`, thumbnail PNG, dieline layer) → save via multipart → exports at 300/600 DPI, vectorized export, upscales (2×/4×), bg removal — each a metered credit feature.

### 4.5 Moat vs wheel (DYP)
- **MOAT (thin):** curated product-type + scene template economy (their `[SCENE]/[PRODUCT]` prompt assembly) · mockup-compositing prompt recipes · print-ready pipeline UX (dieline→editor→300/600DPI+vectorize export chain).
- **HYBRID:** credits UX, gallery/try-now onboarding.
- **WHEEL:** everything else — Next.js/Vercel/Supabase/Polar/Sentry/Tolgee are all off-the-shelf rails. DYP is a **small product placed on commodity rails**; nothing here is harder to clone than a weekend of wiring given our existing stack.

---

## 5. The shared recipe (what actually makes these products work)

1. **Prompt → structured spec → images** (not raw prompt→image). Packify runs an explicit multi-step agent ("Initial Analysis", layers); DYP assembles `[SCENE]/[PRODUCT]/[CUSTOM PROMPT]` structured prompts.
2. **A canvas editor over a parametric dieline (SVG)** is the lock-in: the AI output feeds an editable, layer-separated, print-parametrized artifact. Packify sells this as "layered dielines" (~100cr); DYP has the simpler parametric version.
3. **Scene/product template economy** (mockups): curated products × scenes = consistent quality at low cost.
4. **Fine-grained credit metering per feature** (gen/edit/export/upscale/vectorize/bg-remove) is the monetization engine.
5. **Async job + webhook contract** (Packify's public API) is how they sell B2B without a real platform.
6. Commodity rails everywhere else (auth, payments, i18n, analytics, CDN, queue).

---

## 6. Gap analysis — what's MISSING for Northstar (only the pieces)

From a full sweep of our repo (inventory in `reports/` subagent notes; pointers inline). Statuses: ✅ exists / 🟡 partial / ❌ missing.

| Capability (from the recipe) | Our status | Where | Gap to close |
|---|---|---|---|
| Image generation | 🟡 local ComfyUI FLUX.2 klein + Wan video, gated `MEDIA_GEN_LIVE`; `/api/design-studio/generate` synchronous | `Northstar_backend/studio_generation.py`, `design_studio_api.py` | Async + queue; cloud fallback provider client (fal/Replicate/OpenRouter declared in `shared/model-suite.json`, no client) |
| Image **editing** (img2img/inpaint) | ❌ | — | Need one edit lane (FLUX edit / mask inpaint graph in ComfyUI + API passthrough) |
| Background removal | ❌ | only a label | Deterministic removal (rembg/BRIA) — cheap wheel |
| Upscaling | 🟡 SeedVR2 smoke test only | `tools/comfy_smoke.py` | Wire to endpoint + credits |
| Vectorization (raster→SVG) | ❌ | — | vtracer/potrace wheel |
| **Dieline/label SVG generation** | ❌ explicitly out of scope today (`outputPacks.js:"This build does not generate dielines"`) | — | Parametric SVG generators (label types + FEFCO-style carton templates) — this is the keystone gap |
| Print-ready export (PDF/CMYK/ZIP) | ❌ (raster export pipeline ✅, CSV/MD ✅, xlsx ✅) | `studio/engine/compose.js` | Add PDF/ZIP export lane on top of existing export pipeline |
| Chat→design agent | ❌ (AutothinK chat exists; generation takes a single `brief` string; not connected) | `autothink/`, `GenerateIn` | **The single most valuable gap**: connect AutothinK orchestration → design-studio jobs as a chat design agent |
| Layered/stepwise generation w/ pause/regenerate | 🟡 deterministic 4-step plan labels only | `autothink/orchestration/router.py` | Real multi-step executor w/ pause/resume + per-layer artifacts |
| Mockup compositing | ✅ (canvas-vector + 3D box + layered compositing — already better-suited than DYP's) | `northstar-os-ui/src/studio/engine/{mockups,render3d,presets}.js` | Add scene/product template gallery + prompt assembly |
| Credits ledger | ✅ reserve→commit/release, idempotent | `credit_ledger.py` | Wire per-feature charging (currently `credits_used: 0`) |
| Billing | 🟡 test-mode processor (no Stripe/Polar client) | `foundation/billing` | Add real PSP when desired — pure wheel |
| Durable queue/jobs | ✅ claim/lease/retry/DLQ | `foundation/jobs*.py` | Route design jobs through it (ds_jobs rows exist but nothing consumes) |
| Outbound webhooks (public API) | 🟡 stub `webhook_notify()` never sends | `gg_workflow.py` | Implement sender + retry policy + public API keys |
| Vector search over assets | ❌ (vector search absent; memory-bank search exists) | — | Local embedding index over generated designs (wheel) |

**Northstar assets they don't have (differentiation substrate):** Amazon compliance/spec engine (`compliance.js`, `specRegistry.js`), disclosure/provenance XMP marking in exports, local-model margin structure (no per-credit cloud cost), durable jobs + credit ledger (−advanced), arbitrage research pipeline feeding design briefs (products you're already going to sell).

---

## 7. Build plan — wheels vs proprietary, and how we make it *ours*

Principle: **reimplement behavior, don't copy code; adopt OSS for wheels; build custom only the four moat pieces; differentiate the where-we-play.**

### 7.1 Wheels (use OSS/standard — ~2 weeks of wiring total)
| Piece | Suggested | License |
|---|---|---|
| Canvas editor (dieline/mockup) | fabric.js (matches DYP's `canvas_data` model) or Konva | MIT |
| Parametric dielines/labels | own SVG generators (rounded_rectangle etc.) + FEFCO/standard carton templates (math is commodity); optional Boxes.py ideas (GPL — keep at arm's length) | — |
| PDF/ZIP export | client: pdf-lib/jspdf+jszip (their pattern) or server: reportlab + svglib | MIT/BSD |
| Background removal | rembg (U²-Net) local, or BRIA RMBG API | MIT / vendor |
| Upscale | SeedVR2 (already smoke-tested) / Real-ESRGAN | Apache/BSD |
| Vectorize | vtracer | MIT |
| Billing rails | Stripe (Packify's choice) or Polar (DYP's) — we already have test-mode foundation | — |
| Queue/async | **existing** `foundation/jobs*` — zero new tech | — |
| i18n/analytics | skip until needed | — |

### 7.2 Proprietary cores to build (the four pieces actually worth cloning-with-a-twist)
1. **Chat → layered design generation agent.** Wrap our existing image lane in AutothinK: chat message → structured spec (brand, product, format, claims) → step plan (layout → art → copy → dieline layers) → artifacts per layer, with **pause / regenerate-layer / retry** and socket/SSE progress. *Differentiation:* grounded in the operator's real product + Amazon listing context (title/benefit copy from listing data), not a generic prompt box; expose "why" (each layer cites the brief + brand kit).
2. **Layered editable dieline generation.** Prompt/brand → parametric dieline template instantiated as **separate vector layers** (background, panels, copy, nutrition panel, badges) exported as SVG + flattened preview. Preview-cheap / full-expensive metering (their exact trick, we already have the ledger). *Differentiation:* **Amazon-native panels** (FNSKU/label area, net weight, nutrition auto-fill from product data), compliance-checked before export.
3. **Scene/product mockup compositor.** Scene gallery (prompts pre-baked once, reused) × product-type presets × our existing canvas compositor; custom-prompt escape hatch with their `[SCENE]/[PRODUCT]` structured assembly. *Differentiation:* deterministic compositing first (zero credit cost), AI fill only where needed — margin play.
4. **Metered public API + webhooks** (`/api/open/<version>/packaging-design|photoshoot`-style): async submit → webhook callback with retry policy (their exact contract), API keys gated to a plan. *Differentiation:* webhook payloads carry compliance evidence + disclosure provenance (our XMP marker) — a trust feature they can't match today.

### 7.3 Deliberate divergences (creatively *not* copying)
- **Local-first margin:** they pay per image (cloud models); our FLUX lane makes design generation near-free → we can under-price or include unlimited mockups while charging only for edits/exports/API.
- **Arbitrage-native:** "design the packaging for the product you're about to flip" — pull product photos + listing copy straight from our research pipeline; one-click "Make an Amazon main image from this pack" (Packify's own chip shows the demand) but wired to our compliance engine.
- **Trust & provenance:** compliance gates + disclosure XMP + "generated-by" labels — aimed at Amazon-safe sellers (their tools hand you files with zero compliance context).
- **Human loop, not slot machine:** operator approval gates on final exports (our existing pattern), because our users ship real inventory, not mockups.

### 7.4 Suggested sequencing (design-studio track)
1. Route generation through durable jobs + credit charging (unblocks async + metering).
2. Dieline/label SVG generators + canvas editor (fabric.js) + PDF/ZIP export → *print lane complete*.
3. AutothinK ↔ design-studio chat agent with layered plan + pause/regenerate.
4. Scene/product gallery + mockup templates on the existing compositor.
5. Public API + webhooks (with compliance evidence payloads) behind a plan gate.

---

## 8. Limitations & compliance notes

- **Static vs runtime:** all API shapes/route names are from public bundles and docs; only DYP credit-polling was confirmed live (value-free shapes). Response schemas for the heavy generation endpoints are inferred from client usage (field names reliable; envelope details unverified). Packify chat window was idle during both capture attempts (operator ran the generation outside the windows — result verified visually).
- **No secrets:** no credentials, cookies, or tokens were captured/printed; OAuth redirects were observed but not interfered with (no login attempted by the agent; the operator signed in themselves; no CAPTCHA/jailbreak activity occurred).
- **Copyright:** findings are behavioral/interface-level. No competitor source was copied into our code. All OSS wheels above carry permissive licenses (verify GPL items before use).
- **ToS risk note:** this was research on publicly served content + the operator's own account, for interoperability/product analysis. Keep derived artifacts internal; don't republish their docs text verbatim.
- **Follow-up capture windows (recorded failure):** two opportunistic 10-minute observation windows armed after the main investigation ended with `provider_unavailable / disconnected` — the dedicated Chrome profile was closed post-investigation. Failure envelopes are persisted in the working set (`*_live3.json`); per the circuit-breaker rule, no retry was attempted. All deliverable evidence predates these windows and is unaffected (commit `297f90a`).

---

## 9. Appendix — quick facts

- Packify route inventory (57): tools pages (`/tools/*-label-generator` ×20+), `/design-chat/:name*`, `/projectList`, `/my_project`, `/photoshoot`, `/aimockup`, `/aiquotation`, `/inspirations`, `/print`, `/pricing`, `/docs`, `/api-key`, `/share/p/:id`, `/chat`, `/design-ideas/*`.
- Packify sockets: `io(<base>,{path:"/io/"})`, join-room per generation; engine.io default path also present.
- DYP Next.js chunks of interest: `5079` (print/dieline/mockup create flows), `5169` (image-edit, translate, designs), `5854` (canvas save-designs), `7444` (credits/plans/feature costs), `6654` (credits UI polling 30s), `1339` (Next runtime).
- DYP credit economics observed: 15 → 12 after one operator mockup run; feature costs fetched dynamically (`/api/credits/cost`).
- Both sites require login before real generation; Packify exposes guest login API (`/api/user/guest_login`) — DYP drives sign-in on cold `/app/design` entry.
