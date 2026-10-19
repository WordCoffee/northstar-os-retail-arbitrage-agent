# Operator decisions — resolved (2026-10-19)

The instruction was *"complete everything with what's recommended"*. Each open
decision below is therefore resolved to the **recommended** option, and each
resolution is chosen so it can be reversed without data loss. Nothing irreversible
was done.

---

## D1 — Preset family: **RESOLVED — additive (BUILD family)**

Thorn's four presets (Product Design / Coding / System Architecture / General Chat)
live in `build_presets.py` as a **separate BUILD family**. The six work foci
(`auto/create/grow/research/operate/autothink`) are unchanged.

- Why: the plan's presets are *code/architecture* work; this product's surface is
  retail ops. Replacing the foci would have deleted capability to satisfy a
  document.
- Guard: a test asserts `shell_focus.FOCUS_MODES` still has exactly six entries and
  that no BUILD preset leaks into it (the V3 shell gate asserts six chips).
- Reversible: delete `build_presets.py` + its tool entry.

## D2 — LoRA fine-tuning: **RESOLVED — not now (proposal-only)**

No training runs. `self_evolution.weight_updates()` stays `blocked` on D2 and lists
exactly what it would need (GPU hours on the shared 16 GB card, a pinned training
toolchain, a held-out eval set).

- Why: it is a real spend of the same GPU the product runs on, and the register's
  own rule (item 498) is that a capability without a test is a claim.
- To unblock later: approve GPU hours + pick the toolchain; the proposal loop
  already produces the candidates it would train on.

## D3 — Memory-vault key: **RESOLVED — reuse the existing out-of-repo secrets vault**

Key management will use `foundation/secrets.py` (AES-256-GCM, key outside the repo)
rather than inventing a second store.

- **Not yet implemented:** encrypting the knowledge rows themselves. `memory_tiers.
  encryption_status()` continues to report `knowledge_store_encrypted: False`, and
  the gap text names D3. Encrypting the tier is pending work; the *decision* about
  where the key lives is now settled.

## D4 — `_main_dbg*.py` orphans: **RESOLVED — leave in place, prevent a fourth**

The three untracked ~2,085-line forks of `main.py` are **not deleted**. Unfamiliar
files are treated as potential operator work; they are also untracked, so deleting
them is irreversible.

- Instead: `test_ops_status.py::test_no_new_debug_fork_files` fails if a **new**
  `*_dbg*.py` appears in the backend tree.
- Recommended operator action (yours, not mine): move them outside the repo
  (`..\_archive\`) if you do not need them; the test lists them as known.

## FIXTURES — benchmark/scanner data: **RESOLVED — do not fabricate**

The 26 skipped tests need benchmark/scanner/review data that is **untracked and
absent from both the working tree and a clean checkout**. Synthetic stand-ins were
**rejected** because the same paths are read by the *decision* path
(`proof_batch_run.load_benchmark_reference()`), so a fake file there would produce
false proof-batch reports — fabricated evidence in a decision lane.

- What would turn the skips into coverage: drop the real datasets at
  `data/benchmarks/asin_benchmark_reference.json`,
  `data/benchmarks/raw/Rank-Product-ASIN-Reviews-Price-BSR.csv` and
  `data/scanner-search-cache.json` (plus
  `data/batch/manual-mapping-review/B0CP6LXPLK-review.json`), and the skips clear
  themselves — the guards are `os.path.exists`, not permanent exclusions.

---

## What this unlocked (N-2 shipped in the same pass)

**The trust surface** — `ops_status.py` + `GET /api/ops/status` (authenticated):

- disk headroom with warn/critical thresholds (the 0-byte incident is now visible
  before it bites);
- database existence, size, WAL size, table count and `PRAGMA integrity_check`;
- measured lane aggregates reusing the ONE telemetry store;
- resident local models (and an explicit reason when none is loaded);
- GPU **delegated** to `/api/shell/hardware` rather than duplicated;
- and a rule the code enforces: **a null is an explicit "could not measure", never
  a zero**, and an unknown never reads as "healthy".

Live on this machine: `status: healthy`, disk 19.67 GB free, DB 51 tables / 41.5 MB
with integrity `ok`, lane `chat:default` measured, no model resident (with reason).
