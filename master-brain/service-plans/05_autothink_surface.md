# Northstar AutothinK Surface — Plan & Architecture

> **Status:** Approved for construction (Autonomous Zone).
> **Current state:** AutothinK chat workspace already exists at `autothink/ui/index.html`
> (FastAPI backend, galaxy/edge-gradient theme, chat + quick-execute widgets +
> session memory). This pass **polishes and links**, does not rip out.

## 1. SURFACE IDENTITY

**Public:** Northstar AutothinK (capital **A**uto, capital **T**hink).
**Tier:** Tier 2 premium "build-anything" layer (Perplexity Computer / Claude Code
comparables). Say what you want; the Master Brain automates, builds, delivers end-to-end,
pulling whichever services are needed.
**Design direction:** the "Spatial Canvas" (per `Northstar_AutothinK_UI_Design_Guide.md`)
— deep space, star particles, floating HUD panels, glowing nodes, constellation project
map, directional compass, light-speed transitions.

## 2. SCOPE OF THIS PASS (polish + integration, not rebuild)

1. **Shell link** — suite shell's `#/autothink` route opens the AutothinK workspace
   (embedded iframe or launch), keeping one Northstar OS identity.
2. **Brand alignment** — apply Northstar OS tokens (steel/gold on `#050505` space) to
   the AutothinK header/edge-text so both surfaces share the star identity while
   AutothinK keeps its own spatial feel.
3. **Service invocation affordance** — composer quick buttons ("Ask SourceScout",
   "Ask AdPilot", "Ask ListingForge", "Ask SocialPulse") that prefill the prompt with
   the service name so the Master Brain router (action verb > domain keyword) routes
   correctly.
4. **Status/readiness lamps** — show availability of the local Ollama backend
   (detected, not probed at build time) with the existing fallback marker convention.
5. **Docs pointer** — footer/side note referencing `master-brain/` so AutothinK chat
   exports and edits feed the master brain learning loop.

## 3. TEST CONTRACT

- Shell `#/autothink` route exists and mounts the workspace container.
- Quick buttons render with correct labels and prefill composer value.
- Local-backend lamp renders "detected" or "offline" label without performing a
  network call.
- Existing AutothinK python tests remain untouched/green.

## 4. BUILD ORDER

1. Shell link + container (Phase 5 slot after Phases 0–4).
2. Token/brand alignment of AutothinK header.
3. Quick-invocation buttons.
4. Lamps + docs pointer.
5. Tests green; commit; state update.

## 5. GATED-LIVE PATHS

No new live paths in this pass. AutothinK already has its own LLM call handling;
executing local/cloud LLM calls is governed by the existing AutothinK backend gates and
the Hard Stop rules for paid cloud models (openai-gpt-4o fallback stays gated).