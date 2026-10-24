# Phase 0 — Audit (read-only)

**Date:** 2026-10-23 · **Repo:** `Northstar OS Retail Arbitrage Agent` @ `feature/v4.1-mesh`
**Scope:** inventory what exists today, and explain why the two reported failures happen.
No code changed in this phase.

---

## 1. What already exists

### 1.1 The conversation layer

| Piece | Where | What it is |
|---|---|---|
| Bojo chat surface | `northstar-os-ui/src/chat/ChatSurface.jsx` | Simple-mode chat: SSE turns, tool rows, artefacts, plan cards, attachments |
| Turn streaming | `Northstar_backend/chat_router.py` | session → model → tool loop (max 4 steps) → persisted message with `parts_json` |
| Focus modes | `Northstar_backend/shell_focus.py` | `auto · create · grow · research · operate · autothink`, each with its own **tool subset** |
| Engine line | `chat_adapter.CHAT_MODEL` | local Ollama `northstaros-qwen3.8:27b` (ctx 16384) |
| Composer contract | `chat_router._MODE_CONTRACT` | creative / standard / thinking posture + style |

**Finding:** Bojo is a single chat assistant that both routes *and* does the work. There is no
router, no specialist registry, and no required-input contract anywhere in the stack. This is
exactly the condition the blueprint calls out in §2 problem 3.

### 1.2 The tool inventory (25 tools, all flat)

```
system_status, list_templates, design_brief, create_dieline, generate_image, apply_label,
seo_check, seo_propose, seo_profile, seo_negatives, seo_retitle, corpus_search,
corpus_vector_search, corpus_drift, knowledge_lookup, listing_audit, ads_math,
creative_plan, improvement_status, service_catalog, purpose_command, voice_list,
voice_tts, voice_dub, build_package*, optimize_listing*, ppc_plan*      (* added Phase 3–4)
```

Every tool is offered to the model as a flat list. The model picks. Nothing enforces that a
packaging request reaches the packaging code path.

### 1.3 The creative pipeline (real, local, verified)

| Lane | Implementation | Status |
|---|---|---|
| Image | `studio_generation.generate_image` → ComfyUI Flux.2-Klein GGUF | working; 1216 px ceiling, aspect-preserving fit added this session |
| Label composite | `pouch_label.py` (new) | working; real logo + real fonts, measured face fit |
| Dieline | `design_studio_print.py` — 8 templates incl. `doypack` | working; draft geometry only |
| Video | `studio_generation.generate_video` (Wan 2.2 TI2V) | working; never exercised at final tier |
| Voice | `local_voice.py` (piper → SAPI) + `tools/local_voice_service.py` on :8321 | working, one-shot synthesis |
| Mockup compositor | `mockup_compositor.py` | working, but needs a per-plate quad preset |

### 1.4 Listing and SEO

| Piece | Where | What it does |
|---|---|---|
| Title/bullet checks | `chat_tools._TITLE_CHECKS`, `_BULLET_CHECKS` + `cie_eval.grade` | deterministic rule checks |
| SEO profile | `brand_seo_profiles` table + `design_studio_imports` | versioned keyword clusters |
| SEO scoring | `seo_score.py` | keyword coverage on supplied copy |
| Listing store | `listing_forge.py`, `ds_listing_revisions` | revisions of listing copy |

**Finding:** there is a *checker* and a *scorer*, but no optimizer: nothing rewrites a listing
toward a keyword set, and nothing enforces the 250-byte backend limit. That matches §2 problem 2.

---

## 2. Why the two reported failures happen

### 2.1 "Package images are incomplete — no front/back/side/dieline"

Chain as it existed before this session:

```
"Create a product image for Mogra Lion's Mane 6 oz pouch"
  → model calls generate_image
  → ComfyUI renders ONE photograph with a no-text suffix
  → model shows the blank pouch and explains that text "must be authored as layers"
  → the turn ends. No panels. No dieline. No copy.
```

Three separate causes, all confirmed in code:

1. **No panel model.** `generate_image` has one output: one image. There is no concept of a
   package having a front, a back and a side.
2. **No required-input gate.** Nothing asks for ingredients, address, origin, or net weight,
   so even a labelling pass would have nothing legal to print.
3. **The dieline existed but was never joined to the render.** `create_dieline` and
   `generate_image` were separate tools the model could call in either order, or not at all.

### 2.2 "Listing optimization is weak"

```
"Optimize my listing"
  → model calls seo_check or listing_audit
  → receives a list of rule failures and a coverage percentage
  → replies with prose advice
```

There is no rewrite step, no before/after score, no backend-term builder, and no required
keywords gate. `seo_check` scores *supplied* content; it does not produce new content.

### 2.3 "Bojo is overloaded"

Confirmed structurally: 25 flat tools, one model, no classifier, no hand-off. Any improvement to
one capability competes with every other capability for the same model's attention.

### 2.4 "The managing AI is unproven"

There was **no test suite** for Bojo's routing or specialist behaviour. Nothing measured whether
it asks the right questions, picks the right tool, or fabricates. `test_chat_tools.py` covers
plumbing (argument parsing, honest errors), not task quality.

---

## 3. What this audit did NOT establish

- No Tier A repository was cloned and no Tier B product was observed in this pass. Behaviour
  specs in `/specs` are therefore marked **UNVERIFIED** against their named target and describe
  only what Northstar built and why. Copying a competitor's rubric without observing it would
  violate §3.5 (anti-fabrication).
- GPU contention under a real packaging job was not measured (one render at a time was observed).

---

## 4. Consequences carried into the build

1. A deterministic router with a required-input checklist (no model in the loop).
2. A package designer that refuses to build without the legal facts and always emits three
   panels plus a dieline.
3. A listing optimizer with an explicit rubric, a rewrite, and a hard byte limit.
4. A PPC agent that validates an upload before proposing anything.
5. An acceptance suite (22 tasks) that scores routing and outputs, so "is the manager good"
   becomes a number instead of an opinion.
