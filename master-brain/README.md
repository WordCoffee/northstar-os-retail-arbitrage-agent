# MASTER BRAIN — Knowledge Base & User Profile Architecture

> Home of the Northstar OS "master brain" seed knowledge. This directory is the
> canonical store the brain loads to understand the platform, the brands, and the
> operator it serves.

## How this directory is organized

```
master-brain/
├── README.md                                        <- this file (architecture & index)
├── northstar-os-master-plan.md                      <- the full platform breakdown
│                                                      (Northstar OS Services + Northstar AutoThink)
└── profiles/
    └── t2-holdings-tyrone-johnson.md                <- the T2 / Tyrone JohnsON master seed profile
```

## Purpose

- **`northstar-os-master-plan.md`** is the *platform brain*: what Northstar OS is,
  every agent/service it offers, what each can do, the tech stack, the operating
  constitution, and the roadmap. This is the "how to build and operate the product"
  knowledge.
- **`profiles/`** is the *user brain*: one profile per subscriber. The master brain
  loads **only the requesting subscriber's profile** for a session (identity,
  brands, preferences, judgment signals, thresholds, history).

## Per-user profile loading model (the subscriber model)

```
User request ──▶ Master Brain ──▶ load <subscriber>'s profile from master-brain/profiles/
                     │
                     ├── platform brain (northstar-os-master-plan.md)  [shared, read-only]
                     ├── user brain (profiles/<user>.md)               [per-subscriber]
                     │
                     └── route to agents (TaskRouter) ──▶ execute & validate
```

1. **Shared platform brain** — loaded for every user; contains the product/agent
   capabilities, guardrails, and constitution. Not secret, not personal.
2. **Per-subscriber user profile** — loaded only for the active subscriber;
   contains their brands, thresholds, voice preferences, and judgment history.
3. **For now** the only profile is `t2-holdings-tyrone-johnson.md` — the T2 master
   profile, deliberately merged with the master brain so we can develop the core
   basis of what will power **Northstar AutoThink**. When other subscribers are
   onboarded, each gets their own file under `profiles/` and the brain loads only
   that file.

## Relationship to this repo's operating rules

- The master brain's operating constitution (Autonomous Zone / Hard Stop Zone,
  circuit breaker, reporting discipline) lives in the repo-root `AGENTS.md` and is
  enforced regardless of which profile loads.
- `Northstar_backend/config/brain_policy.json` holds the machine-readable
  behavioral policy (e.g., `min_roi_target_pct: 20.0`, live-call gating defaults).
  User-profile preferences in `profiles/` are *compatible with and may refine*
  those defaults — they never override Hard Stop Zone rules.

## Provenance

Consolidated 2026-09-07 from every file in
`C:\Users\T2Hol\Desktop\All AI Chat Markdowns` (16+ markdown chats/exports covering
the master vision session, local setup, AutoThink PPC service, ads/PPC analysis,
FBA strategy, listing optimizer, retail arbitrage, and the full Word Coffee brand).
All credential values were excluded — only **names** (env-var keys) appear.