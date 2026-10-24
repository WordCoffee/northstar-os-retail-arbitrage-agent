---
name: operator-setup
description: Guided Northstar OS onboarding with verified checkpoints; never asks for secrets in chat
triggers: setup, install, onboarding, first run, configure, api key missing, env setup
---

# Operator setup (checkpoint-verified)

Adapted for Northstar from the AgentConnect setup-skill pattern (`.claude/skills/
agentconnect-setup`, Apache-2.0): walk the operator through configuration, but every
checkpoint is **verified by a real command before moving on**, and no step ever asks
the operator to paste a secret into chat. Keys are edited in `.env` by the operator
themselves; the harness only ever checks *presence*, never value.

## Checkpoints (in order; do not skip ahead)

1. **State readable.** Run:
   `python -c "import json;json.load(open('00_STATE.json',encoding='utf-8'));print('state ok')"`
   → pass = prints `state ok`; fail = STOP, report, nothing else proceeds.
2. **Backend import surface.** Run:
   `cd Northstar_backend && python -c "import data_layer, provider_suite; print('imports ok')"`
   → proves the Python surface the rest depends on.
3. **Credential presence (values are never read).** Run:
   `python Northstar_backend/provider_suite.py --check <tool> --provider <lane>` for
   the tools the operator plans to use. `not_installed`/`ready` is expected and fine;
   `gate_not_armed` per armed gate is an operator decision, not a fix.
4. **Gates armed on the lane.** Run `python Northstar_backend/provider_suite.py --catalog`
   and read it back to the operator as a table before anything live is allowed.
5. **Offline proof first.** Only after 1-4 pass: `python -m pytest test_skills_plane.py
   test_decision_layer.py test_loop_breaker.py -q`. A clipped/failed count is a FAIL;
   never narrate around it.

## Hard rules while guiding

- Never echo, print or transcribe any `.env` value or key.
- Never disable a gate, permit-list entry or rate limiter to "make a checkpoint pass".
- A failed checkpoint is a stop with the real reason, not a workaround.
- Real-money or live-purchase work is out of scope for setup entirely.

## What "done" means

All five checkpoints pass and the operator can name, in one sentence each: what their
lanes are, which gates are armed, and where the stop switch is. Otherwise setup is
PARTIAL and says so.
