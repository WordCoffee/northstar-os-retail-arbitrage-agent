# REA scan + pattern clone: AgentConnect (2026-10-24)

Operator task: *"use REA to fully scan AgentConnect and clone every aspect that can
improve our master brain"* — followed by *"you have full approval"* (covers the
operator-gated steps of the REA protocol for this task only).

## 1. REA capture status

| Path | Result |
|---|---|
| Source-level scan (GitHub API, raw docs, design specs) | **COMPLETE** — no browser needed, read-only |
| Live capture via Chrome Connect (`www.agentconnect.md` + console) | **BLOCKED** — see below |

**Blocker (recorded once, not retried):** the controller serves the policy loaded at
startup. The allowlist edit (agentconnect hosts added, commit `11d495c`) is valid on disk
(re-verified with `python json.load` after an encoding bug in my first edit was caught and
fixed), but `chromeconnect_run` still reports `url_refused:host_not_allowlisted` and
`chromeconnect_guardrails` reports the pre-edit fingerprint. Fix = restart Chrome Connect
(operator-side; the port is locked to one controller by design). Capture stays BLOCKED,
never simulated.

Live capture would have added little anyway: the public site is static and the console
(`app.agentconnect.md`) would stop at its login boundary per the hard rule — the clone
value lives in the design docs, which are fully public and fully scanned.

## 2. Scanned surface

- `docs/designs/architecture.md` (376 lines: control/data plane split, trust model §9.1,
  degraded semantics §7)
- `docs/designs/decisions.md` (2,176 lines: the reusable-D / Jev contract, consumer
  matching, observation windows, previews)
- `docs/designs/loop-breaker-design.md` (764 lines: L0–L3 layered loop protection,
  durable latch, admission order, restart/replay)
- `CONTEXT.md` (ubiquitous language: observation vs admission, coordinates,
  source-cache vs workspace-snapshot)
- `docs/` index + `docs/designs/` index (89 design docs catalogued)
-Licences re-verified: Apache-2.0 (repo), HyperFrames Apache-2.0 where referenced.

## 3. What was cloned → the master brain

| # | AgentConnect concept | Where it now lives | Commit |
|---|---|---|---|
| 1 | **Reusable Decisions** — a decision is a *resource* (question, type, criteria defining each answer), owns no trigger, output never grants permission; consumers evaluate with their own state | `Northstar_backend/decision_layer.py`: declarative `DECISIONS` registry with per-label criteria, deterministic `probabilities` distributions on every output, `consumer_match()` with the Jev matching rules | `29cf0ca6` |
| 2 | **Loop breaker L1** — fixed-window counters with strict >-thresholds, durable OPEN latch with **no auto-expiry**, poison fast path, dedup never counted, trusted human clears the automatic streak but not the total backstop, operator-only `confirmed` reset, L2 trusted hop guard for agent-to-agent chains | `Northstar_backend/loop_breaker.py` + `cie_loop.run_cycle()` guard (one admission per cycle, outcomes noted without double-counting) | `98507611` |
| 3 | **Organisation Knowledge revisions** — agent edits to approved knowledge stay visible as proposals while retrieval serves approved content only; "never silently remap" generalized | `Northstar_backend/memory_bank.py`: `propose_revision` / `approve_revision` / `reject_revision` / `pending_revisions`, plus a revision-gate test file | `a85ab5e0` |
| 4 | **Setup-skill pattern** — checkpoints verified by *real commands*, never asks for secrets in chat, a failed checkpoint is a stop | `skills/operator-setup/SKILL.md` (5 checkpoints, wired into the skills plane, base-first ordering verified) | `7b21f02c` |

Deliberately **not** cloned: daemon/relay/control-plane topology, Docker/PostgreSQL/Logto/
TURN stack, Slack/Telegram adapters, k8s duty ledger, and the multi-agent visibility policy
—all team-scale or second-harness surface that duplicates the Master Brain (same verdict as
the original rejection; recorded in `shared/provider-suite.json`).

Ideas parked for later (in AgentConnect's own docs, not yet needed):
`memory-dreaming.md`, `memory-evolution.md`, `agent-capability-benchmark-harness.md`,
observation windows (bounded 100-msg/24h slices) — relevant if the assistant ever runs
autonomous chat admission.

## 4. Test evidence

```
test_loop_breaker.py            17 passed   (12 unit + note semantics + CIE seam)
test_decision_layer.py          35 passed   (incl. 12 new Jev-contract tests)
test_memory_revision_gate.py     7 passed   (proposal isolation, one-approve, reject-keeps)
test_memory_tiers.py            10 passed   (no regressions)
test_skills_plane.py            14 passed   (operator-setup routes, base-first)
test_cie.py                     19 passed   (invariant holds)
```

## 5. Filing (REA discipline)

Four entries filed into agent memory (`memory_bank.ingest`, source
"REA scan: agentconnect 2026-10-24"): the Decisions contract, the loop-breaker semantics,
the revision gate, the setup-skill pattern — each with provenance pointing at the module
that now carries it.

## 6. Guardrail cross-check

- Chrome Connect remained the only browser path; zero live-browser actions succeeded
  (both attempts refused by the controller itself) ✅
- No credential values read, printed or stored; no login attempted ✅
- Allowlist change logged in a dedicated commit (`11d495c`); fingerprint baseline needs an
  operator re-bless after restart (fingerprint will move) ⚠️
- No push, no protected-branch operation ✅
- Apache-2.0 attribution: every ported pattern records its upstream in its module docstring ✅

## 7. Open items for the operator

1. **Restart Chrome Connect** if a live REA capture of agentconnect.md is wanted on a
   future task; the allowlist entry is already in place. Then re-bless the new fingerprint.
2. `blocker_escalation` and `respond_now` decisions exist with rule backends; wire the
   first real consumer (the §2B blocker protocol) when convenient.
4. During this task one `updated_by` edit briefly invalidated the operator policy JSON
   (non-ASCII ellipsis introduced a line-4 control character); caught by validation,
   repaired, and re-verified the same session. Logged because a malformed policy file
   fails closed and would have silently refused every host.
3. Fingerprint re-bless step belongs to the operator-only policy flow (chromeconnect_guardrails
   will report a mismatch until done — that mismatch is correct behavior, not a fault).
