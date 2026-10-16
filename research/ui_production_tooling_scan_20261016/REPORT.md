# Production-Quality Tooling Scan — would these repos fix Northstar OS? (2026-10-16)

Operator question: would OpenDesign, Open Builder, CopilotKit OpenIntelligentUI, or
the Awesome Generative UI lists get Northstar OS to production quality — and if not,
what does. Every repo below was checked against GitHub / official docs during this
session (VERIFIED) or is labeled otherwise. Labels follow the repo convention:
VERIFIED (seen this session) / STANDARD (well-known, not re-verified now).

## 1. Verdict on the four suggested tools

| Tool | Real? | What it actually is | Fit for Northstar OS |
|---|---|---|---|
| **OpenDesign** (`nexu-io/open-design`) | VERIFIED — Apache-2.0, local-first agent-driven design workspace; "Figma alternative" is a workflow claim, not a canvas | Renders prototypes/pages/dashboards from a brief + portable `DESIGN.md`, driving *your* coding agent (17 adapters incl. OpenCode). Has an alpha `od-code-migration` plugin: point at a git repo + DESIGN.md → get a PR | **NARROW.** Useful for brand/design-system consistency later; does NOT fix services or incompleteness. Optional experiment, not the fix |
| **Open Builder** (`Amery2010/open-builder`) | VERIFIED — browser-based AI app *generator* (Tauri 2 + Sandpack, 79★, v1.3.0) | Greenfield only: creates NEW projects in an in-memory FS; its file tools cannot open an existing repo; preview is a sandbox | **NO.** Wrong direction for a large existing codebase |
| **CopilotKit OpenIntelligentUI** | VERIFIED — ~3.1k★ generative-UI chat framework on Google's A2UI | A chat surface that answers with live tables/interfaces. Something you build INTO a product | **NO as a repair tool.** Possible later product feature; Northstar already has AutothinK chat |
| **Awesome Generative UI lists** (narrowin / DonFungible / rapidpages / awesomegenerativeui.com) | VERIFIED — several real curated lists | Directories of links (v0, thesysdev/openui, google/A2UI, E2B …) | **NO direct value.** Index for later browsing |

Net: none of the four is a "make my half-built system production-grade" tool. Three
generate new material; one is an index. The "drop in your existing UI and it fixes it"
framing matches only the alpha code-migration plugin inside OpenDesign.

## 2. What actually moves an existing codebase to production quality

Ordered by leverage for *this* repo (FastAPI backend, ~253 routes, live
`/openapi.json`; React 18 + Vite 5 UI; one workflow file in `.github/workflows/`).

1. **Contract sync — HIGHEST.** Backend already owns the truth. Generate TS
   types/clients from the OpenAPI schema (Hey API / `openapi-typescript`), then
   replace the hand-rolled `fetch()` layer incrementally. Evidence: FastAPI docs
   "Generating SDKs" (Hey API, VERIFIED); `openapi-typescript` + `openapi-fetch`
   (VERIFIED); CI regeneration guide on propelauth.com (VERIFIED). Kills the
   largest class of "UI looks broken vs. backend" bugs by construction.
2. **Property-based API fuzzing — HIGH, near-zero effort.** Schemathesis generates
   test cases straight from the OpenAPI schema and fuzzes every route for crashes /
   schema violations / edge cases (schemathesis docs + repo, testdriven.io, Capital
   One writeup — VERIFIED). With ~253 routes this finds real 500-class bugs with no
   test authoring.
3. **Repo-scale coding agents — HIGH for the backlog.** OpenHands: open-source,
   self-hostable coding-agent platform; ships a GitHub **resolver** that fixes issues
   and opens PRs (openhands.dev blog + repo, VERIFIED). This is the correct shape of
   "AI fixes our repo" tooling — it operates ON the existing repo. Local equivalents
   (Aider / Cline / OpenCode — the last is already in use here).
4. **Visual repair on the real React app — MEDIUM.** Onlook: open-source visual
   editor for EXISTING React/Vite codebases; Figma-like UI; edits written back to
   TypeScript source (onlook.com/for/vite + `onlook-dev/onlook`, VERIFIED). Fits the
   Vite 5 + React 18 UI for layout/visual passes; not logic fixes.
5. **CI quality gates — HIGH, mechanical.** Today: one workflow
   (`.github/workflows/security.yml`, VERIFIED). Add: backend `pytest` + `ruff`;
   UI `npm run build` + typecheck + lint; Playwright smoke across key rooms; the
   contract-sync step from (1) as a check. All free on GitHub-hosted runners.
6. **Static sweeps — MEDIUM (STANDARD tools).** `semgrep` SAST, `pip-audit`,
   `bandit`; `knip`/`vulture` dead-code; Renovate for dependency churn.
7. **Finish the PARTIAL rooms — the actual "very broken" work.** The repo's own
   readiness map (`00_STATE.json`) already names every partial room and its missing
   half (mostly external-account decisions or wiring jobs — not rot). No third-party
   tool replaces this; it's the roadmap.

## 3. Concrete sequence for Northstar OS

1. CI gates + Schemathesis nightly against `/openapi.json` → find crash-class bugs now.
2. OpenAPI → TS types; migrate the design-studio `fetch()` call sites first.
3. Point OpenHands at this repo for the issue backlog.
4. Onlook (or Playwright visual snapshots) for the visual pass on PARTIAL rooms.
5. Optional later: an OpenDesign `DESIGN.md` as the brand source for studio renders.

## 4. Evidence links (all VERIFIED this session)

- https://github.com/nexu-io/open-design · https://open-design.ai/alternatives/figma/
- https://github.com/Amery2010/open-builder
- https://github.com/CopilotKit/OpenIntelligentUI · https://www.copilotkit.ai/blog/introducing-open-intelligent-ui
- https://github.com/narrowin/awesome-generative-ui · https://awesomegenerativeui.com/
- https://www.openhands.dev/ · https://www.openhands.dev/blog/open-source-coding-agents-in-your-github-fixing-your-issues
- https://github.com/onlook-dev/onlook · https://www.onlook.com/for/vite
- https://github.com/schemathesis/schemathesis · https://schemathesis.readthedocs.io/
- https://fastapi.tiangolo.com/advanced/generate-clients/ · https://openapi-ts.dev/ · https://evilmartians.com/chronicles/lifes-too-short-to-hand-write-api-types-openapi-driven-react
- https://www.propelauth.com/post/autogenerating-clients-with-fastapi-and-github-actions
