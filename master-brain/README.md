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
    ├── manifest.json                                <- canonical index of subscriber profiles
    └── t2-holdings-tyrone-johnson.md                <- the T2 / Tyrone Johnson master seed profile
```

## Purpose

- **`northstar-os-master-plan.md`** is the *platform brain*: what Northstar OS is,
  every agent/service it offers, what each can do, the tech stack, the operating
  constitution, and the roadmap. This is the "how to build and operate the product"
  knowledge.
- **`profiles/`** is the *user brain*: one profile per subscriber. The master brain
  loads **only the requesting subscriber's profile** for a session (identity,
  brands, preferences, judgment signals, thresholds, history).
- **`profiles/manifest.json`** is the canonical index of *who exists*. It is the
  single source of truth for profile ids, the default profile, and each profile's
  active state. Unknown ids **fail closed** — never fabricated.

## Per-user profile loading model (implemented)

```
Session start (AGENTS.md §0.1)
    │
    ├─ 1. Load platform brain (always, shared):
    │      master-brain/README.md + northstar-os-master-plan.md
    │
    ├─ 2. Resolve who is asking:
    │      python Northstar_backend/master_brain_profiles.py --resolve
    │         -> identity resolver chain (priority-ordered, pluggable):
    │              two_step_auth (future) > login_session (future)
    │              > ip_address (future, weak factor) > local_default (active now)
    │         -> identity today: NORTHSTAR_PROFILE env override
    │            or manifest default (t2-holdings-tyrone-johnson)
    │
    ├─ 3. Load ONLY the resolved profile (never any other):
    │      master_brain_profiles .load_profile(<id>) -> validated path + sha256
    │
    └─ 4. Optional append-only audit:
           master_brain_profiles --bootstrap (writes shared/master-brain/audit.log.jsonl)
```

1. **Shared platform brain** — loaded for every user; contains the product/agent
   capabilities, guardrails, and constitution. Not secret, not personal.
2. **Per-subscriber user profile** — loaded only for the active subscriber;
   contains their brands, thresholds, voice preferences, and judgment history.
3. **Identity resolution** is a pluggable, priority-ordered chain in
   `Northstar_backend/master_brain_profiles.py`. Today the **local_default**
   resolver is the only active source (`NORTHSTAR_PROFILE` env override, else the
   manifest default). The **login session**, **IP address**, and **two-step (2FA)**
   resolvers are registered as future plug-in slots — they return "no match" until
   real auth is wired, so the chain naturally falls back to the bootstrap default.
   When subscribers are onboarded, each gets their own `profiles/<id>.md` +
   manifest entry, and future auth factors resolve to them before the local
   default.

## CLI reference

```
python Northstar_backend/master_brain_profiles.py --list        # canonical profile ids
python Northstar_backend/master_brain_profiles.py --resolve     # active profile + resolver
python Northstar_backend/master_brain_profiles.py --load <id>   # validate + load (path, sha256, head)
python Northstar_backend/master_brain_profiles.py --bootstrap   # resolve + load + audit (session start)
```

All offline, no LLM, no network, no credentials. Identity tokens may be passed
with `--identity <token>` for future factors.

## Relationship to this repo's operating rules

- The master brain's operating constitution (Autonomous Zone / Hard Stop Zone,
  circuit breaker, reporting discipline) lives in the repo-root `AGENTS.md` and is
  enforced regardless of which profile loads. `AGENTS.md §0.1` now instructs every
  session to run this bootstrap on start.
- `Northstar_backend/config/brain_policy.json` holds the machine-readable
  behavioral policy (e.g., `min_roi_target_pct: 20.0`, live-call gating defaults).
  User-profile preferences in `profiles/` are *compatible with and may refine*
  those defaults — they never override Hard Stop Zone rules.
- The resolver chain and audit integrate with the existing deterministic gateway
  (`Northstar_backend/master_brain_gateway.py` + `shared/master-brain/`):
  profile-load events are recorded in the same append-only `audit.log.jsonl`.

## Provenance

Consolidated 2026-09-07 from every file in
`C:\Users\T2Hol\Desktop\All AI Chat Markdowns` (16+ markdown chats/exports covering
the master vision session, local setup, AutoThink PPC service, ads/PPC analysis,
FBA strategy, listing optimizer, retail arbitrage, and the full Word Coffee brand).
All credential values were excluded — only **names** (env-var keys) appear.