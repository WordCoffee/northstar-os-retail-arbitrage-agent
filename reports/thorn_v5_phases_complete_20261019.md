# Project Thorn v5.0 — phases T-2 … T-9 complete

**Date:** 2026-10-19 · **Branch:** `feature/v4.1-mesh`
**Operator instruction:** *"continue without stopping until all phases are complete."*

Reconciliation first, as always: the v5.0 document is written as a completed
programme and it is not one. `reports/thorn_v5_reconciliation_and_plan_20261019.md`
records the measured facts (0 repo matches for Thorn/v5.0/purpose-command, 0 for
gRPC, no LLM LoRA pipeline, the vector lane unencrypted, and the "-64% latency"
figure unsupported). What follows is what was actually built, card by card, with
the evidence for each.

---

## Cards shipped

### T-2 — Preset-driven galactic visual shifts → **DONE**
The active focus now drives the canvas atmosphere (`u_tint` / `u_horizon` /
`u_planet`), eased at 0.022 per frame (~3.4–3.8 s measured), never a hard cut.

**Deliberate design boundary:** the theme touches the *atmosphere* only — nebula
warmth, a horizon band, a distant planet limb. The accretion disc and photon ring
stay **film-gold in every mode**, because tinting the hero object is what made the
previous background read as fake — and the operator's own last instruction was that
a cartoon purple planet looked fake, so the limb is a small, mostly-cropped,
low-contrast edge element, never a hero.

The plan's `gRPC / Local API Bridge … zero-latency shader adjustments` clause is
**not implemented by design**: the shift is driven by local focus state, so it is
already instant and a bridge would buy nothing.

*New harness* `verify-galactic-themes.cjs` **18/0**: canvas mounts live (no CSS
fallback); every unlocked focus settles to its exact target tint; the transition is
caught **mid-flight** (a hard cut fails); all five measured palettes are distinct;
and the reading system is provably untouched (composer 16.5 px, column 820 px,
panel alpha ≥ 0.94). AutothinK is locked on this plan → **honestly skipped**.

### T-3 — Input flexibility paths → **DONE**
`input_paths.py`: `guided()` asks only about slots it can **prove** are missing
from the request (four task families, ≤3 questions, reports the slots already
answered and any vague markers); `discovery()` emits named lateral moves with the
template applied and a seed, so a run is reproducible and invents no facts;
`bulk()` reports which multi-modal lanes are **implemented** versus **queued**
(PDF and log ingestion are queued and are not advertised as working).

### T-4 — Deep-research graph → **DONE (local corpus only)**
`research_graph.py`: deconstruct → traverse → cross-validate → synthesise. A node
reports exactly the sources it retrieved; a failing searcher is reported per node
and never raised; zero evidence is an explicit result ("not an answer"); a claim in
one source is labelled `single_source`, never "verified"; two sources disagreeing
on a number are surfaced as a **conflict**, never averaged into a fake consensus.
No outbound call of any kind — live web stays operator-gated via Chrome Connect.

### T-5 — Privacy boundaries + memory tiers → **DONE**
`privacy.py`: the consent gate **fails closed**; markers are reported by **kind and
length only**, and the tests assert the matched value never appears in the result
(a scanner that echoes the secret it found is a leak with extra steps).
`scrub_telemetry()` drops identifier-shaped keys, turns text into a shape, buckets
counts and adds Laplace noise — and reports `formal_dp: False` in plain words,
because redaction + noisy local aggregation is not a guaranteed DP mechanism and
must not borrow the term.

`memory_tiers.py` **extends** the existing memory bank (tier rides in `tags` as
`tier:<name>` — no second store, no schema change): transient needs a `session_id`
so it can be flushed; `flush_transient()` retires exactly that session's rows;
`promote_to_global()` **sanitises** (URLs, emails, paths, long numbers, quoted
strings stripped) and refuses when fewer than four meaningful words survive — the
global tier holds lessons, not evidence. `encryption_status()` states plainly that
the knowledge store is **not** encrypted, points at what is (AES-256-GCM secrets
vault, key outside the repo) and records the gap as owner decision **D3**.

### T-6 — Self-critique evaluator → **DONE**
`self_critique.py`: the deterministic layer **quotes the span** it complains about
(unhedged absolutes, numbers absent from the provided context, topic drift, a
missing verification step on price/listing/compliance work, concrete constraints,
unclosed fences and emphasis). The model layer is optional and reports
`available: False` with the real reason when it has no caller or the caller raises
— and the deterministic layer still runs. `refine()` returns an **outline**, never
a rewritten answer: a checker that rewrites the thing it checks is not a check.

### T-7 — Lane telemetry → **DONE and wired live**
`lane_telemetry.py`: nearest-rank p50/p95 and success rate over actual recorded
rows; a lane that has never run is reported as never run, never as fast.
`recommend()` **refuses to emit a policy before evidence** — it names which
candidates never ran or are below `MIN_SAMPLES=30`. "No policy before data" is
enforced in code, not in a comment.

**Wired into `chat_router.turn_event_stream`'s `finally` block**, so every turn
records a real measurement on every exit path (done / cancelled / error /
disconnect). A failure there is **logged**, never swallowed.

### T-8 — Recursive self-evolution loop → **DONE (proposal-only)**
`self_evolution.py`: steps 1–4 (collect → analyse → propose → verify) with effects
injected, so the loop is fast, deterministic and testable. Every proposal carries
the evidence that produced it and the gates that would verify it; with no evidence
it proposes nothing. `verify()` runs what it is given and records `not_run` when
given nothing — it never claims a gate it did not execute.

**There is no `apply()`.** A test asserts the module has no `apply`/`mutate`
attribute: silent self-modification is precisely the failure mode this design
prevents. Step 5 (LoRA weight updating) reports `blocked` on owner decision **D2**
with what it would need, rather than implying a training pipeline exists.

A real pass against this repository produced **5 traceable proposals** (a prompt
guard for the most repeated finding kinds, and a split proposal for
`agents/golden_goose_finder/main.py`) and honestly reported that routing is still
unmeasured.

### T-9 — BUILD presets → **DONE (additive)**
`build_presets.py`: the plan's four presets (Product Design, Coding, System
Architecture, General Chat) as a separate **BUILD family** — the brain working on
its own materials — deliberately **not** pushed into
`shell_focus.FOCUS_MODES`, because the V3 shell gate asserts exactly six chips and
a preset is not a room. A test now guards that invariant. Every preset tool is
validated against `chat_tools.TOOLS`, so a preset can never advertise a tool that
is not registered. Exposed read-only via the `build_preset` chat tool.

---

## Two real defects found by exercising the live path

Neither was visible to the unit tests; both came from actually running a turn and
reading the server log. Both are now regression-tested.

1. `data_layer.DataLayer` has **no `executescript`** — a `db.executescript(...)`
   call raised `AttributeError`.
2. The chat path passes `data_layer.NorthstarDB`, which is a **container**: it has
   no `execute()` at all, and its raw layer lives on `._layer`.

`lane_telemetry._handle()` now normalises all three handle shapes (raw sqlite3,
`DataLayer`, `NorthstarDB`) and reports an unusable handle instead of raising.
The first fix attempt silently swallowed this behind `except Exception: pass` —
which is why the handler now **logs** its failure. A silently dead producer is
worse than no producer.

**Live evidence (T-7), from a real turn through the API** — real local model, 811
bytes of SSE, `status: done`:

```
lane=chat:default latency_ms=2513 ok=1 tools=0 focus=auto at=2026-10-19T07:32:16
```

---

## Gates

| Gate | Result |
|---|---|
| Thorn v5.0 suites (T-1 … T-9), 17 files | **107 passed** |
| `verify-shell-v3.cjs` (the V3 Simple-shell contract) | **28 passed / 0 failed — unchanged** |
| `verify-galactic-themes.cjs` | **18 passed / 0 failed** |
| `verify-stale-shim-signin.cjs` | **8 passed / 0 failed** |
| `npm run build` | **0 errors** |

One commit was **blocked by this repository's own gitleaks hook**, which correctly
flagged a credential-shaped test fixture. The fixtures are now built at runtime, so
no credential-shaped literal lives in the tree.

---

## Commits

`7ffc718` T-3+T-4 · `159904f` T-5 · `6b779f2` T-6+T-7 · `5c321e9` T-8+T-9
(plus the earlier `3e41215` T-2, `6bc6e9e` T-1 + reconciliation).

---

## Owner decisions still open (unchanged, asked once)

- **D1** — BUILD presets live alongside the six work foci (implemented that way) or
  should they replace them?
- **D2** — approve local GPU LoRA training, or keep self-improvement proposal-only?
  (Step 5 stays `blocked` until answered.)
- **D3** — memory-vault key store for encrypting the knowledge tier.
- **D4** — delete the three orphaned `_main_dbg*.py` files (~6,250 lines, fan-in 0,
  untracked)? They have **not** been touched.

## Declined, with reasons

- **gRPC local bridge** — SSE already streams offline-first; the conduit adds
  infrastructure for no measured gain.
- **Telemetry "opt-in global pattern pool"** — nothing is transmitted from this
  repository. `scrub_telemetry()` exists and is local-only by construction.

---

<!-- REGRESSION-RECONCILIATION -->
